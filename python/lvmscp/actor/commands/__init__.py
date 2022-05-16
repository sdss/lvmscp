# /usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: Changgon Kim, Taeeun Kim, Mingyeong YANG (mingyeong@khu.ac.kr)
# @Date: 2021-03-22
# @Filename: __init__.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import glob
import importlib
import os

from archon.actor.commands import parser


# Autoimport all modules in this directory so that they are added to the parser.

exclusions = ["__init__.py"]

cwd = os.getcwd()
os.chdir(os.path.dirname(os.path.realpath(__file__)))

files = [
    file_ for file_ in glob.glob("**/*.py", recursive=True) if file_ not in exclusions
]

for file_ in files:
    if file_.startswith("deprecated"):
        continue
    modname = file_[0:-3].replace("/", ".")
    mod = importlib.import_module(
        "lvmscp.actor.commands." + modname
    )  # changged by CK 2021/03/30

os.chdir(cwd)
