FROM ubuntu:20.04

LABEL maintainer="changgonkim@khu.ac.kr"

WORKDIR /opt

COPY . lvmscp

RUN apt-get -y update
RUN apt-get -y install python3 python3-pip build-essential libbz2-dev

RUN pip3 install -U pip setuptools wheel
RUN cd lvmscp && pip3 install .

# Connect repo to package
LABEL org.opencontainers.image.source https://github.com/sdss/lvmscp

ENTRYPOINT lvmscp actor start --debug
