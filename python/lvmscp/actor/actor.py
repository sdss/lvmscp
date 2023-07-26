# /usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: Mingyeong YANG (mingyeong@khu.ac.kr)
# @Date: 2021-03-22
# @Filename: actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import json
import os
import pathlib
from contextlib import suppress
from typing import ClassVar

from archon.actor import ArchonActor
from archon.actor.tools import get_schema
from clu import Command

from lvmscp import config
from lvmscp.controller import SCPController
from lvmscp.delegate import LVMExposeDelegate

from .commands import parser


__all__ = ["SCPActor", "CommandType"]


class SCPActor(ArchonActor):
    """The main actor class of the lvmscp."""

    parser = parser
    BASE_CONFIG: ClassVar[str | dict | None] = config
    DELEGATE_CLASS = LVMExposeDelegate
    CONTROLLER_CLASS = SCPController

    def __init__(self, *args, **kwargs):
        schema = self.merge_schemas(kwargs.pop("schema", None))

        # Just for typing.
        self.controllers: dict[str, SCPController]

        super().__init__(*args, schema=schema, **kwargs)

        assert self.model

        self.emit_status_task: asyncio.Task | None = None

    async def start(self):
        """Starts the actor."""

        start_result = await super().start()

        delay = self.config.get("status_delay", 30.0)
        self.emit_status_task = asyncio.create_task(self.emit_status(delay))

        return start_result

    async def stop(self):
        """Stops the actor and cancels tasks."""

        if self.emit_status_task and not self.emit_status_task.done():
            self.emit_status_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.emit_status_task

        return await super().stop()

    async def emit_status(self, delay: float = 30.0):
        """Emits the status of the controller on a timer."""

        await asyncio.sleep(5)

        while True:
            await Command(
                "status",
                actor=self,
                commander_id=f".{self.name}",
            ).parse()

            await asyncio.sleep(delay)

    def merge_schemas(self, scp_schema_path: str | None = None):
        """Merge default schema with SCP one."""

        schema = get_schema()  # Default archon schema.

        if scp_schema_path:
            root_path = pathlib.Path(__file__).absolute().parents[1]
            if not os.path.isabs(scp_schema_path):
                scp_schema_path = os.path.join(str(root_path), scp_schema_path)

            scp_schema = json.loads(open(scp_schema_path, "r").read())

            schema["definitions"].update(scp_schema.get("definitions", {}))
            schema["properties"].update(scp_schema.get("properties", {}))
            schema["patternProperties"].update(scp_schema.get("patternProperties", {}))

            if "additionalProperties" in scp_schema:
                schema["additionalProperties"] = scp_schema["additionalProperties"]

        return schema

    @classmethod
    def from_config(cls, config, *args, **kwargs):
        """Creates an actor from a configuration file."""

        if config is None:
            if cls.BASE_CONFIG is None:
                raise RuntimeError("The class does not have a base configuration.")
            config = cls.BASE_CONFIG

        return super(SCPActor, cls).from_config(config, *args, **kwargs)


CommandType = Command[SCPActor]
