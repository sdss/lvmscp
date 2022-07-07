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
@click.option(
    "-r",
    "--rmq_url",
    "rmq_url",
    default=None,
    type=str,
    help="rabbitmq url, eg: amqp://guest:guest@localhost:5672/",
)
@click.option(
    "-c",
    "--config",
    "config_file",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the user configuration file.",
)
@click.pass_context
def lvmscp(ctx, rmq_url: str | None = None, config_file: str | None = None):
    """LVM SCP actor."""

    ctx.obj = {"rmq_url": rmq_url, "config_file": config_file}


@lvmscp.group(cls=DaemonGroup, prog="scp_actor", workdir=os.getcwd())
@click.pass_context
@cli_coro_lvmscp
async def actor(ctx):
    """Runs the actor."""

    default_config_file = os.path.join(os.path.dirname(__file__), "etc/lvmscp.yml")
    config_file = ctx.obj["config_file"] or default_config_file

    lvmscp_obj = SCPActor.from_config(config_file, url=ctx.obj["rmq_url"])

    await lvmscp_obj.start()
    await lvmscp_obj.run_forever()  # type: ignore


if __name__ == "__main__":
    lvmscp()
