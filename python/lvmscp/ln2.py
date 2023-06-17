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

    client = await AMQPClient(name="ln2fill-client", host=host).start()

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

    write_to_stdout("Started fill.")

    # Close purge line
    write_to_stdout("Closing purge valve (just in case) ...")
    await outlet_on_off("sp1", "Purge", on=False)

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


async def purge_and_fill(
    purge_time: float,
    fill_time: float,
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
    cameras
        What cameras to fill. A list with the format ``['r1', 'z1', 'b2', ...]``.

    """

    write_to_stdout(f"Beginning LN2 purge ({purge_time} seconds).")
    await purge(purge_time, show_timer=show_timer)

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

        write_to_stdout("OUTPUT", with_time=False)
        write_to_stdout("------", with_time=False)

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

    write_to_stdout("")
    await outlet_status()
    write_to_stdout("")
    await get_ln2_temps()


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
@click.pass_context
@cli_coro()
async def purge_and_fill_cli(
    purge_time: float,
    fill_time: float,
    cameras: str | None = None,
    status: bool = False,
):
    """Purges the vent line and fill the cryostats."""

    if cameras is not None:
        camera_list = cameras.split(",")
    else:
        camera_list = ALL_CAMERAS

    await purge_and_fill(purge_time, fill_time, cameras=camera_list)

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
