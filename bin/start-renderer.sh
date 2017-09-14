#!/bin/bash

# Change to the project root.
cd "$(git rev-parse --show-toplevel 2>/dev/null)" || exit 1

if [ '--dev' = "$1" ]; then
    PYTHONPATH=. carto_renderer/service.py
else
    bin/dockerize.sh
    docker run -p 4096:4096 -e STYLE_HOST=localhost -e STYLE_PORT=4097 -e LOG_LEVEL=INFO carto-renderer
fi

