# encoding: utf-8
#
# added by CK 2021/04/06

# -*- coding: utf-8 -*-
#
# @Date: 2020-10-26
# @Filename: __main__.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio
import functools
import os

import click
from click_default_group import DefaultGroup

from sdsstools.daemonizer import DaemonGroup

from lvmscp.actor import SCPActor


def cli_coro(f):
    """Decorator function that allows defining coroutines with click."""

    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(f(*args, **kwargs))

    return functools.update_wrapper(wrapper, f)


@click.group(cls=DefaultGroup, default="actor", default_if_no_args=True)
@click.option(
    "-c",
    "--config",
    "config_file",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the user configuration file.",
    show_envvar=True,
)
@click.pass_context
def lvmscp(ctx, config_file: str | None = None):
    """LVM SCP actor."""

    ctx.obj = {"config_file": config_file}


@lvmscp.group(cls=DaemonGroup, prog="scp_actor", workdir=os.getcwd())
@click.pass_context
@cli_coro
async def actor(ctx):
    """Runs the actor."""

    default_config_file = os.path.join(os.path.dirname(__file__), "etc/lvmscp.yml")
    config_file = ctx.obj["config_file"] or default_config_file

    print("Configuration file", config_file)

    lvmscp_obj = SCPActor.from_config(config_file)

    await lvmscp_obj.start()
    await lvmscp_obj.run_forever()  # type: ignore


def main():
    lvmscp(auto_envvar_prefix="LVMSCP")


if __name__ == "__main__":
    main()
