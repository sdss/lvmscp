FROM python:3.11-slim-bullseye

MAINTAINER Jose Sanchez-Gallego, gallegoj@uw.edu
LABEL org.opencontainers.image.source https://github.com/sdss/lvmscp

WORKDIR /opt

COPY . lvmscp

ENV IS_CONTAINER=yes

RUN apt-get update && apt-get install -y build-essential

RUN pip3 install -U pip setuptools wheel
RUN cd lvmscp && pip3 install .
RUN pip3 install fitsio
RUN rm -Rf lvmscp

ENTRYPOINT lvmscp actor start --debug
