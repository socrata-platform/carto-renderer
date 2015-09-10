FROM socrata/python

EXPOSE 4096

RUN DEBIAN_FRONTEND=noninteractive apt-get -y update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y install python-mapnik2

RUN mkdir -p /app/carto_renderer

ADD frozen.txt /app/
RUN pip install -r /app/frozen.txt

COPY ship.d /etc/ship.d/
ADD carto_renderer /app/carto_renderer
ADD style.js /app/
