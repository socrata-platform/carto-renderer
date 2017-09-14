#!/bin/bash
# Build a docker image locally!
set -e

cd "$(git rev-parse --show-toplevel 2>/dev/null)" 
bin/freeze-reqs.sh

mv frozen.txt docker/
rm -rf docker/carto_renderer    # clean old version.
cp -r carto_renderer docker/
cd docker/

docker build --rm -t carto-renderer .
