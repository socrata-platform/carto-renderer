#!/bin/bash
# Build a docker image locally!
set -e

cd "$(git rev-parse --show-toplevel 2>/dev/null)" 
docker build --rm -t carto-renderer .

