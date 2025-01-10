FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

LABEL org.opencontainers.image.authors="Jose Sanchez-Gallego, gallegoj@uw.edu"
LABEL org.opencontainers.image.source=https://github.com/sdss/lvmscp

WORKDIR /opt

COPY . lvmscp

ENV IS_CONTAINER=yes

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

ENV PATH="$PATH:/opt/lvmscp/.venv/bin"

RUN apt-get update && apt-get install -y build-essential libbz2-dev zlib1g-dev
RUN apt-get install -y git

# Sync the project
RUN cd lvmscp && uv sync --frozen --no-cache --extras fitsio

# Remove unused packages
RUN apt-get remove -y git && apt-get autoremove -y

ENTRYPOINT ["lvmscp", "actor", "start", "--debug"]
