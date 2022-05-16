#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import pathlib

import pytest as pytest

import clu.testing
from sdsstools import read_yaml_file

from lvmscp.actor import SCPActor


@pytest.fixture()
def test_config():
    yield read_yaml_file(os.path.join(os.path.dirname(__file__), "test_lvmscp.yml"))


@pytest.fixture()
async def actor(test_config: dict, tmp_path: pathlib.Path):

    tmp_credentials = tmp_path / "credentials.yml"
    with open(tmp_credentials, "w") as f:
        f.write(
            """
credentials:
  google: /opt/secrets/google.json
  dli:
    10.7.45.22:
      user: admin
      password: 1234
    10.7.45.29:
      user: admin
      password: 1234
    10.7.45.31:
      user: admin
      password: 1234
"""
        )

    test_config["credentials_file"] = str(tmp_credentials)

    _actor = SCPActor.from_config(test_config)
    _actor = await clu.testing.setup_test_actor(_actor)  # type: ignore

    yield _actor

    _actor.mock_replies.clear()
    await _actor.stop()
