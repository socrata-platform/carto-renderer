#!/bin/bash

set -ev

# Change to the project root.
cd "$(git rev-parse --show-toplevel 2>/dev/null)"

MAPNIK_DIR=$(dirname "$(python -c 'import mapnik; print(mapnik.__file__)')")

VENV_DIR="venv"
if [ "${HUDSON_HOME}" ]; then
    VENV_DIR="${HUDSON_HOME}/carto-renderer/${VENV_DIR}"
fi

if [ ! -d "${VENV_DIR}" ]; then
    virtualenv "${VENV_DIR}"
fi
source "${VENV_DIR}"/bin/activate

if [ ! -d "${VENV_DIR}"/lib/python2.7/site-packages/mapnik ]; then
    ln -s "$MAPNIK_DIR" "${VENV_DIR}"/lib/python2.7/site-packages/
fi

pip install --upgrade --requirement "dev-requirements.txt"

PYTHONPATH=. py.test -v carto_renderer
