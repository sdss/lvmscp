FROM python:3.11-slim-bullseye

MAINTAINER Jose Sanchez-Gallego, gallegoj@uw.ed
LABEL org.opencontainers.image.source https://github.com/sdss/lvmscp

WORKDIR /opt

COPY . lvmscp

RUN apt-get -y update
RUN apt-get -y install build-essential libbz2-dev

RUN pip3 install -U pip setuptools wheel
RUN cd lvmscp && pip3 install .
RUN rm -Rf lvmscp

ENTRYPOINT lvmscp actor start --debug
