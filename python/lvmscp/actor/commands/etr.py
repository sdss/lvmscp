#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-08-26
# @Filename: etr.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import TYPE_CHECKING

from lvmscp.delegate import EXPECTED_READOUT_TIME

from . import parser


if TYPE_CHECKING:
    from lvmscp.actor import CommandType


@parser.command()
async def get_etr(command: CommandType, *_):
    """Gets the ETR of the exposure."""

    delegate = command.actor.exposure_delegate
    e_data = delegate.expose_data
    etr = delegate.get_etr()

    if etr is None or e_data is None:
        command.warning("ETR not available. The controllers may be idle.")

    assert e_data

    command.finish(etr=[etr, e_data.exposure_time + EXPECTED_READOUT_TIME])
