# encoding: utf-8
#
# added by CK 2021/04/06

# -*- coding: utf-8 -*-
#
# @Date: 2020-10-26
# @Filename: __main__.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import os

import click
from click_default_group import DefaultGroup

from clu.tools import cli_coro as cli_coro_lvmscp
from sdsstools.daemonizer import DaemonGroup

from lvmscp.actor import SCPActor


@click.group(cls=DefaultGroup, default="actor", default_if_no_args=True)
@click.pass_context
def lvmscp(ctx):
    """LVM SCP actor."""

    ctx.obj = {}


@lvmscp.group(cls=DaemonGroup, prog="scp_actor", workdir=os.getcwd())
@click.pass_context
@cli_coro_lvmscp
async def actor(ctx):
    """Runs the actor."""

    lvmscp_obj = SCPActor.from_config(None)

    await lvmscp_obj.start()
    await lvmscp_obj.run_forever()  # type: ignore


if __name__ == "__main__":
    lvmscp()
