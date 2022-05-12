# encoding: utf-8

from sdsstools import get_config, get_logger, get_package_version


# pip package name
NAME = "sdss-lvmscp"

# Loads config. config name is the package name.
config = get_config("lvmscp")

# Default logger instance
log = get_logger(NAME)


# package name should be pip package name
__version__ = get_package_version(path=__file__, package_name=NAME)
