#!/bin/bash

# Change to the project root.
cd "$(git rev-parse --show-toplevel 2>/dev/null)" || exit 1

if [ '--dev' = "$1" ]; then
    MAPNIK_DIR=$(dirname "$(python -c 'import mapnik; print(mapnik.__file__)')")
     
    if [ ! -d venv ]; then
        virtualenv venv
    fi
    source venv/bin/activate
     
    if [ ! -d venv/lib/python2.7/site-packages/mapnik ]; then
        ln -s "$MAPNIK_DIR" venv/lib/python2.7/site-packages/
    fi

    pip install --upgrade --requirement dev-requirements.txt
    PYTHONPATH=. carto_renderer/service.py
else
    bin/dockerize.sh
    rm frozen.txt
    docker run -p 4096:4096 -e STYLE_HOST=localhost -e STYLE_PORT=4097 -e LOG_LEVEL=INFO carto-renderer
fi

