#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2021-05-29
# @Filename: delegate.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, List, Literal, Tuple

import numpy
from astropy.io import fits

from archon.actor import ExposureDelegate
from archon.controller.controller import ArchonController


if TYPE_CHECKING:
    from .actor import SCPActor  # noqa


class LVMExposeDelegate(ExposureDelegate["SCPActor"]):
    """Expose delegate for LVM."""

    def __init__(self, actor: SCPActor):
        super().__init__(actor)

        self.use_shutter = True

        # Additional data from the IEB and environmental sensors.
        self.extra_data = {}

    def reset(self):
        self.extra_data = {}
        self.use_shutter = True
        return super().reset()

    async def check_expose(self) -> bool:
        """Performs a series of checks to confirm we can expose."""

        base_checks = await super().check_expose()
        if not base_checks:
            return False

        if self.use_shutter:
            assert self.expose_data
            controllers = self.expose_data.controllers
            jobs_status = []
            for controller in controllers:
                jobs_status.append(self.get_shutter_status(controller.name))

            results = await asyncio.gather(*jobs_status)
            for result in results:
                if result is False:
                    return self.fail("Failed getting shutter status.")
                if result["invalid"] or result["open"]:
                    return self.fail("Some shutters are in an invalid stated or open.")

        return True

    async def shutter(self, open, retry=False):
        """Operate the shutter."""

        if not self.use_shutter:
            return True

        assert self.expose_data
        expose_data = self.expose_data

        if expose_data.exposure_time == 0 or expose_data.flavour in ["bias", "dark"]:
            return True

        action = "open" if open else "close"

        self.command.debug(text=f"Moving shutters to {action}.")

        jobs = []
        for controller in self.expose_data.controllers:
            jobs.append(self.move_shutter(controller.name, action))
        results = await asyncio.gather(*jobs, return_exceptions=True)

        if not all(results):
            if action == "close" and retry is False:
                self.command.warning(text="Some shutters failed to close. Retrying.")
                return await self.shutter(False, retry=True)
            else:
                return self.fail("Some shutters failed to move.")

        if retry is True:
            return self.fail("Closed all shutters but failing now.")

        return True

    async def expose_cotasks(self):
        """Grab sensor data when the exposure begins to save time.

        We read the sensors during the exposure to avoid out of date information
        if, for example, the lamps are turned off during readout. However, in
        very short exposures or biases, the cotasks may take longer than the
        exposure itself and readout will have already begun.

        """

        self.command.debug("Grabbing sensor data and system status.")

        assert self.expose_data
        controllers = self.expose_data.controllers

        # Hartmanns status
        self.extra_data["hartmanns"] = {}
        for controller in controllers:
            name = controller.name
            self.extra_data["hartmanns"][name] = await self.get_hartmann_status(name)

        # Temperature/RH sensors.
        self.extra_data["sensors"] = {
            controller.name: (await self.get_sensors(controller.name))
            for controller in controllers
        }

        # Lamp status.
        self.extra_data["lamps"] = await self.get_lamps()

        # Pressure from SENS4
        self.extra_data["pressure"] = {}
        for controller in controllers:
            pressure_data = await self.get_pressure(controller.name)
            for ccd in self.actor.config["controllers"][controller.name]["detectors"]:
                value = pressure_data.get(f"{ccd}_pressure", -999.0)
                self.extra_data["pressure"][ccd] = value

        # Read depth probes
        self.extra_data["depth"] = await self.read_depth_probes()

        # Get telescope information.
        self.extra_data["telescope"] = await self.get_telescope_info()

        return

    async def post_process(
        self,
        controller: ArchonController,
        hdus: List[fits.PrimaryHDU],
    ) -> Tuple[ArchonController, List[fits.PrimaryHDU]]:
        """Post-process images."""

        self.command.debug(text="Running exposure post-process.")

        # Hartmanns
        hartmann = self.extra_data["hartmanns"][controller.name]
        for door in ["left", "right"]:
            key = f"{controller.name}_hartmann_{door}"
            if key not in hartmann or hartmann[key]["invalid"] is True:
                hartmann[key]["status"] = "?"
            else:
                hartmann[key]["status"] = "0" if hartmann[key]["open"] else "1"

        left = hartmann[f"{controller.name}_hartmann_left"]["status"]
        right = hartmann[f"{controller.name}_hartmann_right"]["status"]

        for hdu in hdus:
            hdu.header["HARTMANN"] = (f"{left} {right}", "Left/right. 0=open 1=closed")

            for lamp_name, value in self.extra_data.get("lamps", {}).items():
                hdu.header[lamp_name.upper()] = (value, f"Status of lamp {lamp_name}")

            ccd = hdu.header["CCD"]
            pressure = self.extra_data.get("pressure", {}).get(ccd, -999.0)
            hdu.header["PRESSURE"] = (pressure, "Cryostat pressure [torr]")

            hdu.header["LABTEMP"] = (
                self.extra_data["sensors"][controller.name].get("t3", -999.0),
                "Lab temperature [C]",
            )
            hdu.header["LABHUMID"] = (
                self.extra_data["sensors"][controller.name].get("rh3", -999.0),
                "Lab relative humidity [%]",
            )

            depth_camera = self.extra_data["depth"].get("camera", "")
            for ch in ["A", "B", "C"]:
                hdu.header[f"DEPTH{ch}"] = (
                    self.extra_data["depth"][ch] if ccd == depth_camera else -999.0,
                    f"Depth probe {ch} [mm]",
                )

            for key, value in self.extra_data.get("telescope", {}).items():
                hdu.header[key.upper()] = value

            if "TILE_ID" not in hdu.header:
                hdu.header["TILE_ID"] = (-999, "The tile_id of this observation")

            if "DPOS" not in hdu.header:
                hdu.header["DPOS"] = (0, "The dither position of this observation")

        return (controller, hdus)

    async def get_shutter_status(self, spec: str) -> dict | Literal[False]:
        """Returns the status of the shutter for a spectrograph."""

        lvmieb = self.actor.controllers[spec].lvmieb
        cmd = await self.command.send_command(lvmieb, f"shutter status {spec}")
        await cmd

        if cmd.status.did_fail:
            return False

        try:
            return cmd.replies.get(f"{spec}_shutter")
        except KeyError:
            return False

    async def get_hartmann_status(self, spec: str) -> dict:
        """Returns the status of the hartmann doors."""

        lvmieb = self.actor.controllers[spec].lvmieb
        cmd = await self.command.send_command(lvmieb, f"hartmann status {spec}")
        await cmd

        try:
            return {
                f"{spec}_hartmann_left": cmd.replies.get(f"{spec}_hartmann_left"),
                f"{spec}_hartmann_right": cmd.replies.get(f"{spec}_hartmann_right"),
            }
        except KeyError:
            self.command.warning(f"{spec}: failed retrieving hartmann door status.")
            return {}

    async def move_shutter(self, spec: str, action: str) -> bool:
        """Opens/closes a shutter."""

        lvmieb = self.actor.controllers[spec].lvmieb
        cmd = await self.command.send_command(lvmieb, f"shutter {action} {spec}")
        await cmd

        return cmd.status.did_succeed

    async def get_sensors(self, spec: str) -> dict:
        """Returns the spectrograph temepratues and RHs."""

        lvmieb = self.actor.controllers[spec].lvmieb
        cmd = await self.command.send_command(lvmieb, f"wago status {spec}")
        await cmd

        try:
            return cmd.replies.get(f"{spec}_sensors")
        except KeyError:
            self.command.warning(f"{spec}: failed retrieving sensor values.")
            return {}

    async def get_pressure(self, spec: str) -> dict:
        """Returns the cryostat pressures."""

        lvmieb = self.actor.controllers[spec].lvmieb
        cmd = await self.command.send_command(lvmieb, f"transducer status {spec}")
        await cmd

        try:
            return cmd.replies.get("transducer")
        except KeyError:
            self.command.warning(f"{spec}: failed retrieving pressure status.")
            return {}

    async def read_depth_probes(self) -> dict:
        """Returns the depth probe measurements."""

        spec_config = list(self.actor.config["controllers"].values())[0]
        lvmieb_name = spec_config.get("lvmieb", "lvmieb")

        cmd = await self.command.send_command(lvmieb_name, "depth status")
        await cmd

        try:
            return cmd.replies.get("depth")
        except KeyError:
            # Fail silently.
            pass

        return {}

    async def get_lamps(self) -> dict:
        """Retrieves lamp information."""

        lvmnps = self.actor.config.get("lvmnps", "lvmnps")
        cmd = await self.command.send_command(lvmnps, "status")
        await cmd

        # The config file includes the names of the lamps that should be present.
        lamps = self.actor.config.get("lamps", [])

        lamp_status = {}
        try:
            status = cmd.replies.get("status")
            for switch in status:
                for outlet in status[switch]:
                    if outlet in lamps:
                        state = "ON" if status[switch][outlet]["state"] == 1 else "OFF"
                        lamp_status[outlet] = state
        except Exception as err:
            self.command.warning(f"Failed retrieving lamp status: {err}")

        # Make sure all lamps are in the dictionary, even if the NPS did not
        # return some.
        for lamp_name in lamps:
            if lamp_name not in lamp_status:
                lamp_status[lamp_name] = "?"

        return lamp_status

    async def get_telescope_info(self) -> dict:
        """Retrieve telescope information."""

        data: dict[str, Any] = {"telescop": "SDSS 0.16m", "survey": "LVM"}

        telescopes = ["sci", "skye", "skyw", "spec"]
        keys = ["ra", "dec", "airm", "km", "foc"]

        for telescope in telescopes:
            pwi_status: dict = {}
            km_position: float = -999
            foc_position: float = -999

            pwi_cmd = await self.command.send_command(
                f"lvm.{telescope}.pwi",
                "status",
                internal=True,
            )
            if pwi_cmd.status.did_fail:
                self.command.warning(f"Failed getting {telescope} PWI status.")
            else:
                pwi_status = pwi_cmd.replies[-1].body

            if telescope != "spec":
                km_cmd = await self.command.send_command(
                    f"lvm.{telescope}.km",
                    "status",
                    internal=True,
                )
                if km_cmd.status.did_fail:
                    self.command.warning(f"Failed getting {telescope} k-mirror status.")
                else:
                    km_position = km_cmd.replies.get("Position")

            foc_cmd = await self.command.send_command(
                f"lvm.{telescope}.foc",
                "status",
                internal=True,
            )
            if foc_cmd.status.did_fail:
                self.command.warning(f"Failed getting {telescope} focus status.")
            else:
                foc_position = foc_cmd.replies.get("Position")

            for key in keys:
                if key == "km" and telescope == "spec":
                    continue

                if key == "km":
                    data[f"{telescope}km"] = (km_position, "K-mirror position [deg]")
                elif key == "foc":
                    data[f"{telescope}foc"] = (foc_position, "Focuser position [deg]")
                elif key == "ra":
                    ra_h: float = pwi_status.get("ra_j2000_hours", -999.0)
                    if ra_h > 0:
                        ra_h *= 15.0
                    data[f"{telescope}ra"] = (ra_h, "Telescope pointing RA [deg]")
                elif key == "dec":
                    dec = pwi_status.get("dec_j2000_degs", -999.0)
                    data[f"{telescope}dec"] = (dec, "Telescope pointing Dec [deg]")
                elif key == "airm":
                    alt = pwi_status.get("altitude_degs", None)
                    comment = "Telescope airmass"
                    if alt is None:
                        data[f"{telescope}airm"] = (-999.0, comment)
                    else:
                        airm = 1 / numpy.cos(numpy.radians(90 - alt))
                        data[f"{telescope}airm"] = (airm, comment)

        return data
