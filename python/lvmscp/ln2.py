#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-06-13
# @Filename: ln2.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio
import contextlib
import datetime
import io
import os
import smtplib
import sys
import traceback
from email.message import EmailMessage
from functools import partial

import click
from click_default_group import DefaultGroup

from clu.client import AMQPClient
from sdsstools.daemonizer import cli_coro


ALL_CAMERAS = ["r1", "b1", "z1", "r2", "b2", "z2", "r3", "b3", "z3"]
PURGE_OUTLET = ("sp1", "purge")

FD: io.StringIO | None = None


def get_now():
    """Returns the current time, formatted as a string."""

    now = datetime.datetime.utcnow()
    now_str = now.strftime("%H:%M:%S")

    return now_str


def write_to_stdout(
    message: str = "",
    with_time: bool = True,
    write_to_fd: bool = True,
):
    """Writes to stdout and optionally to a file."""

    if with_time and message != "":
        message = f"{get_now()}: {message}"

    print(message, file=sys.__stdout__)

    if write_to_fd and FD is not None:
        print(message, file=FD)


async def timer():
    is_container = os.getenv("IS_CONTAINER", False)
    if is_container:
        return

    secs = 0
    while True:
        await asyncio.sleep(1)
        secs += 1
        open_str = str(datetime.timedelta(seconds=secs))
        sys.stdout.write(f"\rValve open time: {open_str}")
        sys.stdout.flush()


@contextlib.asynccontextmanager
async def get_client(host="10.8.38.21"):
    """Get an AMQP client to the RabbitMQ exchange."""

    client = await AMQPClient(host=host).start()

    try:
        yield client
    finally:
        await client.stop()


async def outlet_on_off(
    spec: str,
    outlet: str,
    on: bool = True,
    off_after: int | None = None,
):
    """Turns outlet on/off."""

    assert spec in ["sp1", "sp2", "sp3"]

    async with get_client() as client:
        actor = f"lvmnps.{spec}"

        if off_after is None:
            command_string = f"{'on' if on else 'off'} {outlet}"
        else:
            if on is False:
                raise ValueError("off_after requires on=True.")
            command_string = f"on --off-after {off_after} {outlet}"

        command = await client.send_command(actor, command_string)
        if command.status.did_fail:
            raise RuntimeError(f"Command {actor} {command_string} failed")


async def camera_purge(
    camera_purge_time: float,
    cameras: list[str] = ALL_CAMERAS,
    parallel_specs: bool = True,
    show_timer: bool = True,
):
    """Purges the camera lines.

    This routine open all the ``cameras`` valves for a ``camera_purge_time``
    period no dislodge debris in the lines before a purge and camera fill.
    Since ``camera_purge_time`` is expected to be short, it is adjusted
    so that the effective time the camera lines are open (including the
    time wait between turning on different outlets) matches
    ``camera_purge_time``.

    Parameters
    ----------
    camera_purge_time
        Effective time to keep the camera lines open.
    cameras
        A list of cameras to purge.
    parallel_specs
        If `True`, commands to turn on/off valves are sent to each spectrograph
        in parallel. For each spectrograph only one outlet is operated at a time.
    show_timer
        Show a timer if the environment is interactive.

    """

    async def spec_on_off(
        spec: str,
        spec_cameras: list[str],
        on: bool = True,
        wait_time: float = 1.0,
    ):
        """Turns on/off cameras in one spec. Helper function."""

        for ii, cam in enumerate(spec_cameras):
            await outlet_on_off(spec, cam, on=on)
            if ii != len(spec_cameras) - 1:
                await asyncio.sleep(wait_time)

    MAX_TIME = 30
    OUTLET_WAIT = 1

    if camera_purge_time > MAX_TIME:
        raise RuntimeError(f"Maximum camera purge interval is {MAX_TIME}.")

    spec_to_cameras: dict[str, list[str]] = {}
    for camera in cameras:
        spec = f"sp{camera[-1]}"
        if spec in spec_to_cameras:
            spec_to_cameras[spec].append(camera)
        else:
            spec_to_cameras[spec] = [camera]

    max_cams_per_spec = max([len(gg) for gg in spec_to_cameras.values()])

    actual_purge_time = camera_purge_time
    if parallel_specs:
        actual_purge_time -= OUTLET_WAIT * max_cams_per_spec
    else:
        actual_purge_time -= OUTLET_WAIT * len(cameras)

    if actual_purge_time < 0:
        raise RuntimeError("Purge time is too short.")

    timer_task = asyncio.create_task(timer()) if show_timer else None

    errored = False
    try:
        write_to_stdout("Starting camera purge.")
        if parallel_specs is True:
            spec_coros = [
                spec_on_off(spec, spec_to_cameras[spec], on=True, wait_time=OUTLET_WAIT)
                for spec in spec_to_cameras
            ]
            await asyncio.gather(*spec_coros)
        else:
            for ii, camera in enumerate(cameras):
                spec = f"sp{camera[-1]}"
                await outlet_on_off(spec, camera, on=True)
                if ii != len(cameras) - 1:
                    await asyncio.sleep(OUTLET_WAIT)

        await asyncio.sleep(actual_purge_time)

    except Exception as err:
        errored = True
        raise RuntimeError(f"Failed running camera purge: {err}")

    finally:
        if not errored:
            write_to_stdout("Closing camera purge valves.")
        else:
            write_to_stdout("Closing camera purge valves due to exception.")

        if parallel_specs is True and not errored:
            spec_coros = [
                spec_on_off(
                    spec, spec_to_cameras[spec], on=False, wait_time=OUTLET_WAIT
                )
                for spec in spec_to_cameras
            ]
            await asyncio.gather(*spec_coros)
        else:
            for ii, camera in enumerate(cameras):
                spec = f"sp{camera[-1]}"
                await outlet_on_off(spec, camera, on=False)
                await asyncio.sleep(OUTLET_WAIT)

        if timer_task:
            if errored:
                print()
            timer_task.cancel()

        if not errored:
            write_to_stdout("Camera purge complete.")


async def purge(
    purge_time: float | None = None,
    purge_spec: str = PURGE_OUTLET[0],
    purge_outlet: str = PURGE_OUTLET[1],
    show_timer: bool = True,
):
    """Turns on the purge solenoid. Waits for a confirmation on when to close it.

    Parameters
    ----------
    purge_time
        How long to purge for, in seconds. If `None`, a prompt will be
        issue for the user to decide when to stop the purge.
    purge_spec
        Spectrograph NPS that contains the outlet for the purge solenoid.
    purge_outlet
        Name of the outlet for the purge solenoid.

    """

    MAX_TIME = 30 * 60

    write_to_stdout("Opening purge valve ...")

    await outlet_on_off(purge_spec, purge_outlet)

    write_to_stdout("Started purge.")

    if purge_time is None:
        print("Press enter to close valve.")

    timer_task = asyncio.create_task(timer()) if show_timer else None
    errored = False

    try:
        if purge_time is None:
            ainput = asyncio.to_thread(input, "")
            await asyncio.wait_for(ainput, MAX_TIME)
        else:
            await asyncio.sleep(purge_time)
    except asyncio.TimeoutError:
        errored = True
        raise RuntimeError("Maximum purge time reached. Closing valve.")
    finally:
        if timer_task:
            if errored:
                print()
            timer_task.cancel()

        if not errored:
            write_to_stdout("Closing purge valve.")
        else:
            write_to_stdout("Closing purge valve due to exception.")

        await outlet_on_off(purge_spec, purge_outlet, on=False)

        if not errored:
            write_to_stdout("Purge complete.")


async def fill(
    fill_time: float = 300,
    cameras: list[str] = ALL_CAMERAS,
    show_timer: bool = True,
):
    """Fills the cryostats.

    Parameters
    ----------
    fill_time
        How long to fill the cryostats for, in seconds.
    cameras
        What cameras to fill. A list with the format ``['r1', 'z1', 'b2', ...]``.

    """

    MAX_TIME = 600

    if fill_time > MAX_TIME:
        raise RuntimeError(f"Fill time cannot be longer than {MAX_TIME} seconds.")

    # Close purge line
    write_to_stdout("Closing purge valve (just in case) ...")
    await outlet_on_off("sp1", "Purge", on=False)

    cameras_join = ", ".join(cameras)
    write_to_stdout(f"Started fill of cameras {cameras_join}.")

    timer_task = asyncio.create_task(timer()) if show_timer else None

    write_to_stdout("Turning on outlets ... ")
    on_coros = [outlet_on_off(f"sp{camera[-1]}", camera) for camera in cameras]
    for on_coro in on_coros:
        await on_coro
        await asyncio.sleep(2)

    await asyncio.sleep(fill_time)

    if timer_task:
        timer_task.cancel()

    write_to_stdout("Turning off outlets ... ")
    off_coros = [
        outlet_on_off(
            f"sp{camera[-1]}",
            camera,
            on=False,
        )
        for camera in cameras
    ]
    for off_coro in off_coros:
        await off_coro
        await asyncio.sleep(2)

    write_to_stdout("Fill complete.")


async def purge_and_fill(
    purge_time: float,
    fill_time: float,
    camera_purge_time: float | None = None,
    cameras: list[str] = ALL_CAMERAS,
    show_timer: bool = True,
):
    """Purges and fills the spectrographs.

    Parameters
    ----------
    purge_time
        How long to purge for, in seconds.
    fill_time
        How long to fill the cryostats for, in seconds.
    camera_purge_time
        How long to purge the camera lines. If `None`, not camera purge will
        happen.
    cameras
        What cameras to fill. A list with the format ``['r1', 'z1', 'b2', ...]``.

    """

    if camera_purge_time:
        write_to_stdout("CAMERA PURGE", with_time=False)
        write_to_stdout("------------", with_time=False)
        write_to_stdout(f"Beginning camera purge ({camera_purge_time} seconds).")
        await camera_purge(camera_purge_time, cameras=cameras, show_timer=show_timer)

    write_to_stdout("PURGE", with_time=False)
    write_to_stdout("-----", with_time=False)
    write_to_stdout(f"Beginning LN2 purge ({purge_time} seconds).")
    await purge(purge_time, show_timer=show_timer)

    write_to_stdout("", with_time=False)
    write_to_stdout("FILL", with_time=False)
    write_to_stdout("----", with_time=False)
    write_to_stdout(f"Beginning LN2 fill ({fill_time} seconds).")
    await fill(fill_time, cameras=cameras, show_timer=show_timer)


async def close_all():
    """Closes all the outlets"""

    write_to_stdout("Closing all valves ... ")

    off_coros = [
        outlet_on_off(
            f"sp{camera[-1]}",
            camera,
            on=False,
        )
        for camera in ALL_CAMERAS
    ]
    for off_coro in off_coros:
        await off_coro
        await asyncio.sleep(1)

    # Purge valve
    await outlet_on_off(*PURGE_OUTLET, on=False)

    write_to_stdout("Done")


async def outlet_status():
    """write_to_stdouts the valve status."""

    async with get_client() as client:
        purge_spec, purge_outlet = PURGE_OUTLET

        write_to_stdout("Outlet status", with_time=False)
        write_to_stdout("-------------", with_time=False)

        for outlet in ALL_CAMERAS + [purge_outlet]:
            if outlet != purge_outlet:
                spec = f"sp{outlet[-1]}"
            else:
                spec = purge_spec

            actor = f"lvmnps.{spec}"
            command = await client.send_command(actor, f"status {spec} -o {outlet}")
            if command.status.did_fail:
                raise RuntimeError("Failed getting outlet status.")

            status = command.replies[-1].body["status"][spec]
            camera = list(status.keys())[0]
            state = "off" if status[camera]["state"] == 0 else "on"

            write_to_stdout(f"{camera}: {state}")


async def get_ln2_temps():
    """Returns the LN2 cryostat temperatures."""

    async with get_client() as client:
        write_to_stdout("LN2 temperatures", with_time=False)
        write_to_stdout("----------------", with_time=False)

        for spec in ["sp1", "sp2", "sp3"]:
            for cam, mod in [
                ("r", "mod2/tempb"),
                ("b", "mod2/tempc"),
                ("z", "mod12/tempb"),
            ]:
                actor = f"lvmscp.{spec}"
                status = await client.send_command(actor, "status")
                temp = float(status.replies[-2].body["status"][mod])

                write_to_stdout(f"{cam}{spec[-1]}: {temp:.2f}")


async def get_pressures():
    """Returns a list of cryostat pressures."""

    async with get_client() as client:
        write_to_stdout("Pressures", with_time=False)
        write_to_stdout("---------", with_time=False)

        for spec in ["sp1", "sp2", "sp3"]:
            status = await client.send_command(f"lvmieb.{spec}", "transducer status")
            spec_idx = spec[-1]
            for camera in ["r", "b", "z"]:
                key = f"{camera}{spec_idx}_pressure"
                try:
                    pressure = status.replies[-1].body["transducer"][key]
                    write_to_stdout(f"{camera}{spec_idx}: {pressure:.2g}")
                except KeyError:
                    pressure = "???"
                    write_to_stdout(f"{camera}{spec_idx}: {pressure}")


def send_email(
    stream: io.StringIO,
    recipients: list[str],
    smtp_relay="localhost",
    **kwargs,
):
    """Send email to recipients."""

    sys.stdout.flush()
    sys.stderr.flush()

    exc_info = sys.exception()
    if (
        exc_info
        and isinstance(exc_info, click.exceptions.Exit)
        and exc_info.exit_code == 0
    ):
        error = False
    else:
        error = True
        write_to_stdout("")
        write_to_stdout("ERRORS", with_time=False)
        write_to_stdout("------", with_time=False)
        write_to_stdout("LN2 fill failed with error:\n", with_time=False)
        traceback.print_exception(exc_info, file=stream)

    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stdout__

    msg = EmailMessage()
    msg["From"] = "lvm-ln2@lco.cl"
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = ("SUCCESS" if not error else "ERROR") + ": LVM LN2 fill"

    stream.seek(0)
    msg.set_content(stream.read())

    with smtplib.SMTP(smtp_relay, port=25) as ss:
        ss.send_message(msg)


@click.group(cls=DefaultGroup, default="purge-and-fill", default_if_no_args=True)
@click.option(
    "--email",
    "-e",
    is_flag=True,
    help="Send stdout and stderr over email.",
)
@click.option(
    "--recipient",
    "-r",
    type=str,
    multiple=True,
    help="Email recipient (can be used multiple times).",
)
@click.option(
    "--smtp-relay",
    "-s",
    type=str,
    default="localhost",
    help="The SMTP relay host.",
)
@click.pass_context
def ln2fill(
    ctx: click.Context,
    email: bool = False,
    recipient: list[str] = [],
    smtp_relay: str = "localhost",
):
    """LN2 fill CLI."""

    global FD

    if email:
        if len(recipient) == 0:
            raise click.UsageError("--recipient is required with --email.")

        # Redirect stdout and stderr to buffer.
        stream = io.StringIO()
        FD = stream

        now = datetime.datetime.now()
        now_str = now.strftime("%D %H:%M:%S")
        write_to_stdout(f"Running on {now_str}")
        write_to_stdout("")

        # Add a finaliser function that will finish formatting the output
        # and send the email.
        ctx.call_on_close(
            partial(
                send_email,
                stream,
                list(recipient),
                smtp_relay=smtp_relay,
            )
        )


@ln2fill.command(name="status")
@cli_coro()
async def status_cli():
    """Reports valve and LN2 temperature status."""

    await outlet_status()
    write_to_stdout("")
    await get_ln2_temps()
    write_to_stdout("")
    await get_pressures()


@ln2fill.command(name="purge-and-fill")
@click.option(
    "-p",
    "--purge-time",
    type=float,
    required=True,
    help="Purge time, in seconds.",
)
@click.option(
    "-f",
    "--fill-time",
    type=float,
    required=True,
    help="Fill time, in seconds.",
)
@click.option(
    "-P",
    "--camera-purge-time",
    type=float,
    required=False,
    help="Camera purge time, in seconds.",
)
@click.option(
    "-c",
    "--cameras",
    type=str,
    help="Comma-separated cameras to fill. Defaults to all cameras.",
)
@click.option(
    "--status",
    is_flag=True,
    help="Report status after the fill.",
)
@cli_coro()
async def purge_and_fill_cli(
    purge_time: float,
    fill_time: float,
    camera_purge_time: float | None = None,
    cameras: str | None = None,
    status: bool = False,
):
    """Purges the vent line and fill the cryostats."""

    if status:
        await get_pressures()
        write_to_stdout("")

    if cameras is not None:
        camera_list = cameras.split(",")
    else:
        camera_list = ALL_CAMERAS

    await purge_and_fill(
        purge_time,
        fill_time,
        camera_purge_time=camera_purge_time,
        cameras=camera_list,
    )

    if status:
        write_to_stdout("")
        await outlet_status()
        write_to_stdout("")
        await get_ln2_temps()


@ln2fill.command(name="fill")
@click.option(
    "-f",
    "--fill-time",
    type=float,
    required=True,
    help="Fill time, in seconds.",
)
@click.option(
    "-c",
    "--cameras",
    type=str,
    help="Comma-separated cameras to fill. Defaults to all cameras..",
)
@cli_coro()
async def fill_cli(fill_time: float, cameras: str | None = None, status: bool = False):
    """Fills the cryostats."""

    if cameras is not None:
        camera_list = cameras.split(",")
    else:
        camera_list = ALL_CAMERAS

    await fill(fill_time, cameras=camera_list)

    if status:
        write_to_stdout("")
        await outlet_status()
        write_to_stdout("")
        await get_ln2_temps()


@ln2fill.command(name="purge")
@click.option(
    "-p",
    "--purge-time",
    type=float,
    help="Purge time, in seconds. If not provided, interactively waits "
    "for the user to cancel the purge.",
)
@cli_coro()
async def purge_cli(purge_time: float | None):
    """Purges the cryostats."""

    await purge(purge_time)


@ln2fill.command(name="abort")
@cli_coro()
async def abort_cli():
    """Closes all valves."""

    await close_all()
