#!/bin/bash

set -ev

# Change to the project root.
cd "$(git rev-parse --show-toplevel 2>/dev/null)"

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
     PYTHONPATH=. py.test -v carto_renderer
else
    DOCKER_BUILDKIT=1 docker build \
    --target test \
    -t carto-renderer-test \
    . \
    --progress=plain
fi
