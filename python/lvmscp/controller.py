#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-03-08
# @Filename: controller.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from archon.controller import ArchonController


class SCPController(ArchonController):
    """A slight override of the `.ArchonController` for SCP."""

    def __init__(self, name: str, *args, **kwargs):
        super().__init__(name, *args, **kwargs)

        # The name of the lvmieb actor associated with this controller/actor.
        # This is useful when deploying multiple instances of the actors, e.g.,
        # lvmscp.sp1, lvmieb.sp1, etc.
        self.lvmieb: str = self.config["controllers"][name].get("lvmieb", "lvmieb")
