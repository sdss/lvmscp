#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import pytest

from lvmscp.actor import SCPActor


@pytest.mark.asyncio
async def test_actor(actor: SCPActor):

    assert actor


@pytest.mark.asyncio
async def test_ping(actor: SCPActor):

    command = await actor.invoke_mock_command("ping")
    await command

    assert command.status.did_succeed
    assert len(command.replies) == 2
    assert command.replies[1].message["text"] == "Pong."
