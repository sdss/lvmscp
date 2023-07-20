# Changelog

## Next version

### ✨ Improved

* Added ``SMJD`` header keyword with the SDSS Modified Julian Date.


## 0.6.0 - July 18, 2023

### 🔧 Fixed

* [#20](https://github.com/sdss/lvmscp/issues/20) Update archon to 0.11 which solves the issue with exposure times being limited to 1000 seconds. Marking this as a minor release because archon 0.11 is a breaking change and requires a major modification to the ACF that is not backwards compatible.


## 0.5.2 - July 17, 2023

### ✨ Improved

* Round up telescope values in headers.
* Change `TRIMSEC` and `BIASSEC` header keywords. Fixed incorrect values due to the three prescan pixels and split `TRIMSEC` and `BIASEC` by amplifier.


## 0.5.1 - July 13, 2023

### ✨ Improved

* Bump `archon` to 0.10.0 with support for asynchronous readouts.


## 0.5.0 - July 9, 2023

### 🚀 New

* [#16](https://github.com/sdss/lvmscp/pull/16), [#17](https://github.com/sdss/lvmscp/pull/17), [#18](https://github.com/sdss/lvmscp/pull/18) CLI tools to control LN2 fills with camera and vent line purge.
* [DT-4](https://jira.sdss.org/browse/DT-4) Write checksums.

### ✨ Improved

* Updated `archon` to `0.9.0`.
* Add telescope and tile headers.

### ⚙️ Engineering

* Build Docker image using Python 3.11.


## 0.4.0 - March 4, 2023

### 🚀 New

* Add suport for spectrograph 3.
* Support Python 3.11.

### ✨ Improved

* Use `$OBSERVATORY` as spreadsheet location and use different spreadsheets for each spectrograph.
* Support specifying the `lvmieb` actor name. This is useful when `lvmscp` and `lvmieb` are deployed in multiple instances, one per spectrograph.

### 🏷️ Changed

* Use unbined flushing during idle.

### ⚙️ Engineering

* Use `python:3.11-slim-bullseye` base image for Docker image.
* Allow to set the configuration file to use using `$LVMSCP_CONFIG_FILE`.


## 0.3.0 - May 28, 2022

### 🔥 Breaking changes

* [#3](https://github.com/sdss/lvmscp/pull/3) Many changes, the main ones including:
  * The `lvmscp` actor now inherits from `ArchonActor`. There is no archon actor anymore and archon is only used as a library. This is analogous to how [yao](https://github.com/sdss/yao) works.
  * Removed the `Supervisor` class.
  * `lvmscp` now has all the archon commands, including an updated `expose` command.
  * General code clean-up, linting, testing, etc.

### ✨ Improved

* Reading sensor and system data is now done during integration using `ExposureDelegate.expose_cotasks()` instead of during readout, to avoid poetentially out of data information.
* Improved code to retrieve lamp status from the latest version of `lvmnps`.


## 0.1.3 - February 27, 2022

Major updates:

* *The code structure is modulized. The algorizmatic code is all in supervisor.py
* *The focus command was roll backed and the user can also make the API and run the sequence
* *linting, and also minor bugs were fixed.
* *there was a error the the arc lamp was wrongly added on the fits header.


## 0.1.2 - January 17, 2022

Major updates:

* *The cluplus is added for the modulization of the package
* *The focus command was removed since the user can make the API and run the sequence
* *docstrings were added on the functions
* *all of the commands are added on the module.py, so the user can run the API of the
 lvmscp as test.py
