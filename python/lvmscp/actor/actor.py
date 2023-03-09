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
import re
import warnings
from typing import TYPE_CHECKING, ClassVar

from astropy.io import fits
from astropy.time import Time
from authlib.integrations.httpx_client import AsyncAssertionClient

from archon.actor import ArchonActor
from archon.actor.tools import get_schema
from archon.exceptions import ArchonWarning
from clu import Command
from sdsstools.configuration import read_yaml_file

from lvmscp import config
from lvmscp.controller import SCPController
from lvmscp.delegate import LVMExposeDelegate

from .commands import parser


if TYPE_CHECKING:
    from clu.model import Property


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

        self._log_lock = asyncio.Lock()
        self._log_values = {}

        assert self.model

        self.read_credentials()

        # Add Google API client
        try:
            self.google_client = self.get_google_client()
        except Exception as err:
            warnings.warn(f"Failed authenticating with Google: {err}", ArchonWarning)
            self.google_client = None

        # Model callbacks
        self._log_lock = asyncio.Lock()
        self.model["filenames"].register_callback(self.fill_log)

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

    def read_credentials(self):
        """Reads the credentials file."""

        credentials_file = self.config.get("credentials_file", None)
        if credentials_file is None:
            self.config["credentials"] = {}
        else:
            credentials_file = os.path.expanduser(credentials_file)
            self.config["credentials"] = read_yaml_file(credentials_file)["credentials"]

    @classmethod
    def from_config(cls, config, *args, **kwargs):
        """Creates an actor from a configuration file."""

        if config is None:
            if cls.BASE_CONFIG is None:
                raise RuntimeError("The class does not have a base configuration.")
            config = cls.BASE_CONFIG

        return super(SCPActor, cls).from_config(config, *args, **kwargs)

    def get_google_client(self) -> AsyncAssertionClient | None:  # pragma: no cover
        """Returns the client to communicate with the Google API."""

        credentials = self.config.get("credentials", None)
        if not credentials or "google" not in credentials:
            warnings.warn("No credentials for the Google API.", ArchonWarning)
            return None

        with open(credentials["google"]) as fd:
            conf = json.load(fd)

        token_uri = conf["token_uri"]
        header = {"alg": "RS256"}
        key_id = conf.get("private_key_id")
        if key_id:
            header["kid"] = key_id

        client = AsyncAssertionClient(
            token_endpoint=token_uri,
            issuer=conf["client_email"],
            audience=token_uri,
            claims={"scope": "https://www.googleapis.com/auth/spreadsheets"},
            subject=None,
            key=conf["private_key"],
            header=header,
        )

        return client

    def set_log_values(self, **values):
        """Sets additional values for the log."""

        self._log_values = values

    async def fill_log(self, key: Property):  # pragma: no cover
        if not self.config.get("write_log", False):
            return

        if self.google_client is None or "exposure_list" not in self.config:
            return

        path = key.value
        if not os.path.exists(path):
            self.write(
                "w",
                error=f"File {path} not found. Cannot write lab log entry.",
            )
            return

        header = fits.getheader(path)

        filename = os.path.basename(path)

        match = re.match(r".+-([0-9]+)\.fits(?:\.gz)$", filename)
        assert match

        exp_no = int(match.group(1))

        obsdate = Time(header["OBSTIME"], format="isot")
        mjd = int(obsdate.mjd)
        date_str = obsdate.strftime("%d/%m/%Y")
        location = os.environ.get("OBSERVATORY", "?")
        spec = header["SPEC"]
        channel = header["CCD"]
        image_type = header["IMAGETYP"]
        exptime = header["EXPTIME"]

        lamp_sources = []
        for lamp in self.config["lamps"].values():
            if lamp.upper() in header and header[lamp.upper()] == "ON":
                lamp_sources.append(lamp)
        lamp_sources = " ".join(lamp_sources)

        hartmanns = "?"
        if "HARTMANN" in header:
            if header["HARTMANN"].strip() == "0 1":
                hartmanns = "R"
            elif header["HARTMANN"].strip() == "1 0":
                hartmanns = "L"
            elif header["HARTMANN"].strip() == "1 1":
                hartmanns = "L R"
            elif header["HARTMANN"].strip() == "0 0":
                hartmanns = ""

        lamp_current = self._log_values.get("lamp_current", "")
        lab_temp = header.get("LABTEMP", -999)

        ccd_temp = header.get("CCDTEMP1", -999)
        if ccd_temp < -250:
            ccd_temp = "?"

        purpose = self._log_values.get("purpose", "")
        notes = self._log_values.get("notes", "")

        test_no = self._log_values.get("test_no", "")
        test_iteration = self._log_values.get("test_iteration", "")

        try:
            if header["DEPTHA"] != -999.0:
                depth_a = header["DEPTHA"]
                depth_b = header["DEPTHB"]
                depth_c = header["DEPTHC"]
                depth = f"A={depth_a}, B={depth_b}, C={depth_c}"
            else:
                depth = "?"
        except (ValueError, KeyError):
            depth = "?"

        data = (
            exp_no,
            filename,
            mjd,
            date_str,
            location,
            test_no,
            test_iteration,
            spec,
            channel,
            lamp_sources,
            lamp_current,
            hartmanns,
            image_type,
            exptime,
            lab_temp,
            ccd_temp,
            depth,
            purpose,
            notes,
        )

        async with self._log_lock:
            spreadsheet_id = self.config["exposure_list"]["id"]
            sheet = self.config["exposure_list"]["sheet"][spec]

            google_data = {
                "range": f"{sheet}!A1:A1",
                "majorDimension": "ROWS",
                "values": [data],
            }

            r = await self.google_client.post(
                f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/"
                f"values/{sheet}!A1:A1:append?valueInputOption=USER_ENTERED",
                json=google_data,
            )

            if not r.status_code == 200:
                warnings.warn("Failed writing exposure to spreadsheet.", ArchonWarning)


CommandType = Command[SCPActor]
