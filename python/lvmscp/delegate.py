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
from astropy.coordinates import EarthLocation
from astropy.io import fits
from astropy.time import Time
from astropy.utils.iers import conf

from archon.actor import ExposureDelegate
from archon.controller.controller import ArchonController
from sdsstools.time import get_sjd

from lvmscp import __version__


if TYPE_CHECKING:
    from clu import Command

    from .actor import SCPActor


conf.auto_download = True
conf.remote_timeout = 10
conf.iers_degraded_accuracy = "ignore"


class LVMExposeDelegate(ExposureDelegate["SCPActor"]):
    """Expose delegate for LVM."""

    def __init__(self, actor: SCPActor):
        super().__init__(actor)

        self.use_shutter: bool = True
        self.shutter_failed: bool = False

        # Header values to be collected during integration.
        self.header_data: dict[str, Any] = {}

        # Pressure and depth probe data. These data is per CCD/cryostat.
        self.pressure_data: dict[str, float] = {}
        self.depth_data: dict[str, float | str] = {}

        # LCO
        self.location = EarthLocation.from_geodetic(
            lon=-70.70166667,
            lat=-29.00333333,
            height=2282.0,
        )

    def reset(self):
        self.header_data = {}
        self.pressure_data = {}
        self.depth_data = {}

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

    async def shutter(self, open, is_retry=False):
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
            self.shutter_failed = True
            if is_retry is False:
                self.command.warning(text="Some shutters failed to close. Retrying.")
                await asyncio.sleep(3)
                return await self.shutter(open, is_retry=True)
            else:
                self.command.error("Some shutters failed to move.")
        else:
            self.shutter_failed = False

        if self.shutter_failed:
            if open is True:
                return False
            else:
                self.command.warning(
                    "Shutter failed to close. Reading out exposure and failing."
                )

        return True

    async def readout(
        self,
        command: Command[SCPActor],
        extra_header: dict[str, Any] = {},
        delay_readout: int = 0,
        write: bool = True,
    ):
        """Reads detectors."""

        if self.shutter_failed:
            self.command.warning(
                "Frame was read out but shutter failed to close. "
                "There may be contamination in the image."
            )

        read_result = await super().readout(command, extra_header, delay_readout, write)

        return False if (self.shutter_failed or not read_result) else True

    async def expose_cotasks(self):
        """Grab sensor data when the exposure begins to save time.

        We read the sensors during the exposure to avoid out of date information
        if, for example, the lamps are turned off during readout. However, in
        very short exposures or biases, the cotasks may take longer than the
        exposure itself and readout will have already begun.

        """

        self.command.debug("Grabbing sensor data and system status.")

        assert self.expose_data

        # We expect only on controller in lvmscp.
        controller = self.expose_data.controllers[0]

        tasks = [
            self.get_hartmann_status(controller.name),
            self.get_sensors(controller.name),
            self.get_lamps(),
            self.get_pressure(controller.name),
            self.read_depth_probes(),
            self.get_telescope_info(),
        ]

        await asyncio.gather(*tasks)

        return

    async def post_process(
        self,
        controller: ArchonController,
        hdus: List[fits.PrimaryHDU],
    ) -> Tuple[ArchonController, List[fits.PrimaryHDU]]:
        """Post-process images."""

        self.command.debug(text="Running exposure post-process.")

        now = Time.now()
        now.location = self.location

        for hdu in hdus:
            ccd = str(hdu.header["CCD"])

            hdu.header["V_LVMSCP"] = __version__
            hdu.header["LMST"] = round(now.sidereal_time("mean").value, 6)

            # Update header with values collected during integration.
            for key in self.header_data:
                hdu.header[key] = self.header_data[key]

            # Add SDSS MJD.
            hdu.header["SMJD"] = get_sjd("LCO")
            hdu.header["PRESSURE"] = self.pressure_data.get(f"{ccd}_pressure", -999.0)

            depth_camera = self.depth_data.get("camera", "")
            for ch in ["A", "B", "C"]:
                depth = (self.depth_data[ch] if ccd == depth_camera else -999.0,)
                hdu.header[f"DEPTH{ch}"] = depth

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

    async def move_shutter(self, spec: str, action: str) -> bool:
        """Opens/closes a shutter."""

        lvmieb = self.actor.controllers[spec].lvmieb
        cmd = await self.command.send_command(lvmieb, f"shutter {action} {spec}")
        await cmd

        return cmd.status.did_succeed

    async def get_hartmann_status(self, spec: str):
        """Returns the status of the hartmann doors."""

        lvmieb = self.actor.controllers[spec].lvmieb

        cmd = await self.command.send_command(
            lvmieb,
            f"hartmann status {spec}",
            time_limit=5,
        )

        try:
            left = 0 if cmd.replies.get(f"{spec}_hartmann_left")["open"] else 1
            right = 0 if cmd.replies.get(f"{spec}_hartmann_right")["open"] else 1
            self.header_data["HARTMANN"] = f"{int(left)} {int(right)}"
        except KeyError:
            self.command.warning(f"{spec}: failed retrieving hartmann door status.")

    async def get_sensors(self, spec: str):
        """Returns the spectrograph temperatures and RHs."""

        lvmieb = self.actor.controllers[spec].lvmieb
        cmd = await self.command.send_command(
            lvmieb,
            f"wago status {spec}",
            time_limit=5,
        )

        try:
            sensors = cmd.replies.get(f"{spec}_sensors")
            self.header_data["LABTEMP"] = sensors.get("t3", -999.0)
            self.header_data["LABHUMID"] = sensors.get("rh3", -999.0)
        except KeyError:
            self.command.warning(f"{spec}: failed retrieving sensor values.")

    async def get_pressure(self, spec: str):
        """Returns the cryostat pressures."""

        lvmieb = self.actor.controllers[spec].lvmieb
        cmd = await self.command.send_command(
            lvmieb,
            f"transducer status {spec}",
            time_limit=5,
        )

        try:
            self.pressure_data = cmd.replies.get("transducer")
        except KeyError:
            self.command.warning(f"{spec}: failed retrieving pressure status.")

    async def read_depth_probes(self):
        """Returns the depth probe measurements."""

        spec_config = list(self.actor.config["controllers"].values())[0]
        lvmieb_name = spec_config.get("lvmieb", "lvmieb")

        cmd = await self.command.send_command(
            lvmieb_name,
            "depth status",
            time_limit=5,
        )

        try:
            self.depth_data = cmd.replies.get("depth")
        except KeyError:
            pass

    async def get_lamps(self):
        """Retrieves lamp information."""

        lvmnps = self.actor.config.get("lvmnps", "lvmnps")
        cmd = await self.command.send_command(
            lvmnps,
            "status",
            time_limit=10,
        )

        # The config file includes the names of the lamps that should be present.
        lamps = self.actor.config.get("lamps", [])

        try:
            status = cmd.replies.get("status")
            for switch in status:
                for outlet in status[switch]:
                    if outlet in lamps:
                        state = "ON" if status[switch][outlet]["state"] == 1 else "OFF"
                        self.header_data[outlet.upper()] = state
        except Exception as err:
            self.command.warning(f"Failed retrieving lamp status: {err}")

    async def get_telescope_info(self):
        """Retrieve telescope information."""

        telescopes = ["sci", "skye", "skyw", "spec"]

        for telescope in telescopes:
            pwi_cmd = await self.command.send_command(
                f"lvm.{telescope}.pwi",
                "status",
                internal=True,
                time_limit=5,
            )
            if pwi_cmd.status.did_fail:
                self.command.warning(f"Failed getting {telescope} PWI status.")
            else:
                pwi_status = pwi_cmd.replies[-1].body

                ra_h: float = pwi_status.get("ra_j2000_hours", -999.0)
                if ra_h > 0:
                    ra_d = ra_h * 15.0
                else:
                    ra_d = ra_h
                self.header_data[f"TE{telescope.upper()}RA"] = numpy.round(ra_d, 6)

                dec = pwi_status.get("dec_j2000_degs", -999.0)
                self.header_data[f"TE{telescope.upper()}DE"] = numpy.round(dec, 6)

                alt = pwi_status.get("altitude_degs", None)
                if alt is not None:
                    airm = numpy.round(1 / numpy.cos(numpy.radians(90 - alt)), 3)
                    self.header_data[f"TE{telescope.upper()}AM"] = airm

            if telescope != "spec":
                km_cmd = await self.command.send_command(
                    f"lvm.{telescope}.km",
                    "status",
                    internal=True,
                    time_limit=5,
                )
                if km_cmd.status.did_fail:
                    self.command.warning(f"Failed getting {telescope} k-mirror status.")
                else:
                    km_position = numpy.round(km_cmd.replies.get("Position"), 2)
                    self.header_data[f"TE{telescope.upper()}KM"] = km_position

            foc_cmd = await self.command.send_command(
                f"lvm.{telescope}.foc",
                "status",
                internal=True,
                time_limit=5,
            )
            if foc_cmd.status.did_fail:
                self.command.warning(f"Failed getting {telescope} focus status.")
            else:
                foc_position = numpy.round(foc_cmd.replies.get("Position"), 2)
                self.header_data[f"TE{telescope.upper()}FO"] = foc_position
