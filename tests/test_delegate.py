#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2022-05-22
# @Filename: test_delegate.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import os
import pathlib

from typing import TYPE_CHECKING

import numpy
import pytest
from astropy.io import fits

from clu import Command, Reply


if TYPE_CHECKING:
    from lvmscp.actor import SCPActor
    from lvmscp.delegate import LVMExposeDelegate


@pytest.fixture()
def delegate(actor: SCPActor, monkeypatch, tmp_path: pathlib.Path, mocker):
    mocker.patch.object(actor.controllers["sp1"], "set_window")
    mocker.patch.object(actor.controllers["sp1"], "expose")
    mocker.patch.object(actor.controllers["sp1"], "readout")

    mocker.patch.object(
        actor.controllers["sp1"],
        "fetch",
        return_value=(numpy.ones((2048, 6144)), 1),
    )

    mocker.patch.object(actor.expose_delegate, "get_telescope_info", return_value={})

    mocker.patch.object(
        actor.expose_delegate,
        "_get_ccd_data",
        return_value=numpy.zeros((100, 100)),
    )

    mocker.patch.object(
        actor.controllers["sp1"],
        "get_device_status",
        return_value={
            "controller": "sp1",
            "mod2/tempa": -110,
            "mod2/tempb": -110,
            "mod2/tempc": -110,
            "mod12/tempa": -110,
            "mod12/tempb": -110,
            "mod12/tempc": -110,
        },
    )

    files_data_dir = tmp_path / "archon"

    monkeypatch.setitem(actor.config["files"], "data_dir", str(files_data_dir))

    actor.expose_delegate.reset()

    yield actor.expose_delegate


async def send_command_handler(actor: str, command_string: str, **kwargs):
    _child_command = Command(command_string)

    if actor == "lvmieb" and "shutter status" in command_string:
        spec = command_string.split()[-1]
        _child_command.replies.append(
            Reply(
                "i",
                message={f"{spec}_shutter": {"invalid": False, "open": False}},
            )
        )
    elif actor == "lvmieb" and "hartmann status" in command_string:
        spec = command_string.split()[-1]
        _child_command.replies.append(
            Reply(
                "i",
                message={
                    f"{spec}_hartmann_left": {
                        "power": True,
                        "open": True,
                        "invalid": False,
                        "bits": "01111111",
                    },
                    f"{spec}_hartmann_right": {
                        "power": True,
                        "open": True,
                        "invalid": False,
                        "bits": "10111111",
                    },
                },
            )
        )

    _child_command.finish()

    return _child_command


@pytest.fixture()
async def command(delegate: LVMExposeDelegate, mocker):
    _command = Command("", actor=delegate.actor)
    _command.send_command = send_command_handler  # type: ignore

    yield _command


async def test_delegate(delegate: LVMExposeDelegate, actor: SCPActor):
    assert actor.expose_delegate == delegate


@pytest.mark.parametrize("flavour", ["bias", "dark", "object"])
async def test_delegate_expose(
    delegate: LVMExposeDelegate,
    command: Command[SCPActor],
    flavour: str,
):
    result = await delegate.expose(
        command,
        [delegate.actor.controllers["sp1"]],
        flavour=flavour,
        exposure_time=0.01,
        readout=True,
    )

    assert result

    assert delegate.actor.model and delegate.actor.model["filenames"] is not None

    filenames = delegate.actor.model["filenames"].value
    assert os.path.exists(filenames[0])

    hdu = fits.open(filenames[0])
    assert hdu[0].data.shape == (100, 100)
    assert hdu[0].header["CCDTEMP1"] == -110


async def test_expose(delegate, command, actor: SCPActor, mocker):
    mocker.patch.object(actor.controllers["sp1"], "is_connected", return_value=True)

    command = await actor.invoke_mock_command("expose -c sp1 0.01")
    command.send_command = send_command_handler  # type: ignore

    await command

    assert command.status.did_succeed


async def test_shutter_fails_to_open(delegate, command, mocker):
    move_shutter = mocker.patch.object(delegate, "move_shutter", return_value=False)

    result = await delegate.expose(
        command,
        [delegate.actor.controllers["sp1"]],
        flavour="object",
        exposure_time=0.1,
        readout=True,
    )

    assert not result
    assert move_shutter.call_count == 2
    assert delegate.shutter_failed


async def test_shutter_fails_to_close(delegate, command, mocker):
    async def _move_shutter(_, action):
        if action == "close":
            return False
        return True

    move_shutter = mocker.patch.object(
        delegate,
        "move_shutter",
        side_effect=_move_shutter,
    )

    result = await delegate.expose(
        command,
        [delegate.actor.controllers["sp1"]],
        flavour="object",
        exposure_time=0.1,
        readout=True,
    )

    assert not result
    assert move_shutter.call_count == 3
    assert delegate.shutter_failed

    replies = [reply.body["text"] for reply in command.replies if "text" in reply.body]
    assert (
        "Frame was read out but shutter failed to close. "
        "There may be contamination in the image." in replies
    )
