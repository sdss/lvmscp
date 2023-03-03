#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2022-05-15
# @Filename: test_command_focus.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from clu.actor import Reply
from clu.command import Command


if TYPE_CHECKING:
    from lvmscp.actor import SCPActor


@pytest.mark.parametrize(
    "focus_command", ["focus sp2 5", "focus --dark sp2 5", "focus -n 3 sp2 5"]
)
async def test_command_focus(actor: SCPActor, focus_command: str, mocker):
    command = Command()
    command.replies.append(Reply("i", {"filename": "/data/sdr-0001.fits"}))
    command.set_result(command)

    mocker.patch.object(actor, "send_command", return_value=command)

    cmd = await actor.invoke_mock_command(focus_command)
    await cmd

    assert cmd.status.did_succeed
