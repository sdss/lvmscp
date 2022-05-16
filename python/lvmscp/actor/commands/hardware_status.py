#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from . import parser


if TYPE_CHECKING:
    from archon.controller import ArchonController

    from lvmscp.actor.actor import CommandType


__all__ = ["hardware_status"]


@parser.command()
async def hardware_status(
    command: CommandType,
    controllers: dict[str, ArchonController],
):
    """Actor command that prints the status of the connected hardware."""

    ieb_command_strings = ["wago status", "wago getpower", "transducer status"]

    for controller in controllers.values():
        ieb_command_strings.append(f"hartmann status {controller.name}")
        ieb_command_strings.append(f"shutter status {controller.name}")
        ieb_command_strings.append(f"transducer status {controller.name}")

    ieb_commands = [
        await command.send_command("lvmieb", ieb_command_string, new_command=True)
        for ieb_command_string in ieb_command_strings
    ]
    print(ieb_commands)
    await asyncio.gather(*ieb_commands)

    for ieb_command in ieb_commands:
        for reply in ieb_command.replies:
            if reply.message != {}:
                command.info(message=reply.message)

    return command.finish()
