# Changelog

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
