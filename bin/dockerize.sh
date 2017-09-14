#!/bin/bash
# Build a docker image locally!
set -e

cd "$(git rev-parse --show-toplevel 2>/dev/null)" 
bin/freeze-reqs.sh
docker build --rm -t carto-renderer .

