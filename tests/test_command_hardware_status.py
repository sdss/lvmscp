#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2022-05-15
# @Filename: test_command_hardware_status.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import TYPE_CHECKING

from clu.command import Command


if TYPE_CHECKING:
    from lvmscp.actor import SCPActor


async def test_command_hardware_status(actor: SCPActor, mocker):

    command = Command()
    command.set_result(command)

    mocker.patch.object(actor, "send_command", return_value=command)

    cmd = await actor.invoke_mock_command("hardware-status")
    await cmd

    assert cmd.status.did_succeed
