# syntax=docker/dockerfile:1

FROM socrata/python-focal:3.11 AS base

WORKDIR /app

RUN DEBIAN_FRONTEND=noninteractive apt-get -y update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y install python3-mapnik

RUN mkdir -p /app/carto_renderer

ENV LOG_LEVEL=INFO

COPY dev-requirements.txt /app/

FROM base AS test

RUN pip install -r /app/dev-requirements.txt
COPY carto_renderer /app/carto_renderer

RUN PYTHONPATH=/app py.test -vv /app/carto_renderer

FROM base AS prod

COPY bin/freeze-reqs.sh /app/
RUN chmod +x /app/freeze-reqs.sh
RUN /app/freeze-reqs.sh
RUN pip install -r /app/frozen.txt

COPY carto_renderer /app/carto_renderer

COPY ship.d /etc/ship.d/
RUN date -u +"%Y-%m-%dT%H:%M:%SZ" > /app/build-time.txt
