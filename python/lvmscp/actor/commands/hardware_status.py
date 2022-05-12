#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from . import parser


if TYPE_CHECKING:
    from archon.controller import ArchonController

    from lvmscp.actor.actor import CommandType


@parser.command()
async def hardware_status(
    command: CommandType,
    controllers: dict[str, ArchonController],
):
    """Actor command that prints the status of the connected hardware."""

    ieb_commands = ["wago status", "wago getpower", "transducer status"]

    for controller in controllers.values():
        ieb_commands.append(f"hartmann status {controller.name}")
        ieb_commands.append(f"shutter status {controller.name}")
        ieb_commands.append(f"transducer status {controller.name}")

    commands = [
        await command.send_command("lvmieb", ieb_command, new_command=False)
        for ieb_command in ieb_commands
    ]
    await asyncio.gather(*commands)

    return command.finish()
