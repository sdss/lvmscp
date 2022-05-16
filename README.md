# lvmscp

![Versions](https://img.shields.io/badge/python->3.8-blue)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Documentation Status](https://readthedocs.org/projects/lvmscp/badge/?version=latest)](https://lvmscp.readthedocs.io/en/latest/?badge=latest)
[![Test](https://github.com/sdss/lvmscp/actions/workflows/test.yml/badge.svg)](https://github.com/sdss/lvmscp/actions/workflows/test.yml)
[![Docker](https://github.com/sdss/lvmscp/actions/workflows/docker.yml/badge.svg)](https://github.com/sdss/lvmscp/actions/workflows/docker.yml)
[![codecov](https://codecov.io/gh/sdss/lvmscp/branch/main/graph/badge.svg?token=RYKAKyfNpZ)](https://codecov.io/gh/sdss/lvmscp)

SDSS-V LVM (Local Volume Mapper) control software for the spectrograph system.

## Quick Start

### Installation

`lvmscp` uses the [CLU](https://clu.readthedocs.io/en/latest/) framework and requires a RabbitMQ instance running in the background.

`lvmscp` can be installed using `pip`

```console
pip install sdss-lvmscp
```

or by cloning this repository

```console
git clone https://github.com/sdss/lvmscp
```

The preferred installation for development is using [poetry](https://python-poetry.org/)

```console
cd lvmscp
poetry install
```


### Basic ping-pong test

Start the `lvmscp` actor.

```console
lvmscp start
```

In another terminal, type `clu` and `lvmscp ping` for test.

```console
$ clu
lvmscp ping
07:41:22.636 lvmscp >
07:41:22.645 lvmscp : {
    "text": "Pong."
}
```

Stop `lvmscp` actor.

```console
lvmscp stop
```
