FROM socrata/python3-focal

WORKDIR /app

RUN DEBIAN_FRONTEND=noninteractive apt-get -y update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y install python3-mapnik

RUN mkdir -p /app/carto_renderer

ENV LOG_LEVEL INFO

COPY bin/freeze-reqs.sh /app/
COPY dev-requirements.txt /app/
RUN chmod +x /app/freeze-reqs.sh
RUN /app/freeze-reqs.sh
RUN pip install -r /app/frozen.txt

COPY ship.d /etc/ship.d/
ADD carto_renderer /app/carto_renderer
RUN date -u +"%Y-%m-%dT%H:%M:%SZ" > /app/build-time.txt
