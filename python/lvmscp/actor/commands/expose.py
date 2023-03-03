#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2022-05-12
# @Filename: expose.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import click

from archon.actor.commands.expose import expose


# HACK: we want to extend the archon expose command with some options that allow
# to define the values for the log. There's probably a better way to do this, but
# here I replace the callback for the archon expose command with a custom one
# that just does the log stuff and then calls the original callback.

assert expose.callback

ORIGINAL_CALLBACK = expose.callback


async def expose_callback(*args, **kwargs):
    lamp_current = kwargs.pop("lamp_current")
    test_no = kwargs.pop("test_no")
    test_iteration = kwargs.pop("test_iteration")
    purpose = kwargs.pop("purpose")
    notes = kwargs.pop("notes")

    args[0].actor.set_log_values(
        lamp_current=lamp_current,
        test_no=test_no,
        test_iteration=test_iteration,
        purpose=purpose,
        notes=notes,
    )

    await ORIGINAL_CALLBACK(*args, **kwargs)


expose.params.append(click.Option(["--lamp-current"], type=str))
expose.params.append(click.Option(["--test-no"], type=str))
expose.params.append(click.Option(["--test-iteration"], type=str))
expose.params.append(click.Option(["--purpose"], type=str))
expose.params.append(click.Option(["--notes"], type=str))

expose.callback = expose_callback
