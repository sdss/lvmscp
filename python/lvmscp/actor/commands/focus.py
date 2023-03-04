#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2022-05-14
# @Filename: focus.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from archon.actor.commands import parser


if TYPE_CHECKING:
    from archon.controller import ArchonController

    from ..actor import CommandType

__all__ = ["focus"]


async def move_hds(
    command: CommandType,
    spectro: str,
    side: str = "all",
    action: str = "open",
    verbose: bool = False,
):
    """Helper to open/close HDs."""

    if verbose:
        if action == "open":
            command.info(f"Opening {side} Hartmann door(s).")
        else:
            command.info(f"Closing {side} Hartmann door(s).")

    hd_cmd = await (
        await command.send_command("lvmieb", f"hartmann {action} -s {side} {spectro}")
    )

    if hd_cmd.status.did_fail:
        command.fail(
            "Failed moving Hartmann doors. See lvmieb log for more information."
        )
        return False

    return True


# TODO: needs rewriting for different specs.


@parser.command()
@click.argument("SPECTRO", type=click.Choice(["sp1", "sp2", "sp3"]))
@click.argument("EXPTIME", type=float)
@click.option("-n", "--count", type=int, default=1, help="Number of focus cycles.")
@click.option("--dark", flag_value=True, help="Take a dark along each exposure.")
async def focus(
    command: CommandType,
    controllers: dict[str, ArchonController],
    spectro: str,
    exptime: float,
    count: int = 1,
    dark: bool = False,
):
    """Take a focus sequence with both Hartmann doors."""

    # TODO: add a check for arc lamps or, better, command them to be on.

    for n in range(count):
        if count != 1:
            command.info(f"Focus iteration {n+1} out of {count}.")

        for side in ["left", "right"]:
            # Open both HDs.
            if not (await move_hds(command, spectro, "all", "open", verbose=False)):
                return

            # Close HD.
            if not (await move_hds(command, spectro, side, "close", verbose=True)):
                return

            # Arc exposure.
            command.info("Taking arc exposure.")
            expose_cmd = await command.send_command(
                "lvmscp", f"expose --arc -c {spectro} {exptime}"
            )
            await expose_cmd

            if expose_cmd.status.did_fail:
                return command.fail("Failed taking arc exposure.")

            filenames = []
            for reply in expose_cmd.replies:
                if "filenames" in reply.message:
                    filenames += reply.message["filenames"]

            dark_filenames = []
            if dark:
                # Dark exposure, if commanded.
                command.info("Taking dark exposure.")
                dark_cmd = await command.send_command(
                    "lvmscp", f"expose --dark -c {spectro} {exptime}"
                )
                await dark_cmd

                if dark_cmd.status.did_fail:
                    return command.fail("Failed taking arc exposure.")

                for reply in dark_cmd.replies:
                    if "filenames" in reply.message:
                        dark_filenames += reply.message["filenames"]

            command.info(
                focus={
                    "spectrograph": spectro,
                    "iteration": n + 1,
                    "side": side,
                    "exposures": filenames,
                    "darks": dark_filenames,
                }
            )

    # Reopen HDs.
    command.info("Reopening Hartmann doors.")
    if not (await move_hds(command, spectro, "all", "open", verbose=False)):
        return

    command.finish()
