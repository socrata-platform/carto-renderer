#!/bin/bash

set -ev

# Change to the project root.
cd "$(git rev-parse --show-toplevel 2>/dev/null)"

MAPNIK_DIR=$(dirname "$(python -c 'import mapnik; print(mapnik.__file__)')")
if [ ! -d "venv" ]; then
    virtualenv venv
fi
source venv/bin/activate

if [ ! -d venv/lib/python2.7/site-packages/mapnik ]; then
    ln -s "$MAPNIK_DIR" venv/lib/python2.7/site-packages/
fi

DEV_FILE='dev-requirements.txt'
FROZEN_FILE='frozen.txt'

REQS=($(egrep --invert-match '# ?test' "${DEV_FILE}" | tr "\\n" ' '))
pip install --upgrade "${REQS[@]}"

pip freeze > "${FROZEN_FILE}"
