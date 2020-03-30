#!/bin/bash

set -ev

# Change to the project root.
cd /app

DEV_FILE='dev-requirements.txt'
FROZEN_FILE='frozen.txt'

REQS=($(grep -E --invert-match '# ?test' "${DEV_FILE}" | tr "\\n" ' '))
pip install --upgrade "${REQS[@]}"

pip freeze > "${FROZEN_FILE}"
