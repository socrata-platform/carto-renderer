# Carto Style Renderer Docker Config #

## Building ##
To build the image, run:
```
../bin/freeze-reqs
cp ../frozen.txt .
cp -r ../carto_renderer .
docker build -t carto-renderer .
```
 
Or, if you want to replace old versions:
```
../bin/freeze-reqs
cp ../frozen.txt .
cp -r ../carto_renderer .
docker build --rm -t carto-renderer .
```

## Required Environment Variables ##
* `STYLE_HOST` - The style renderer host.
* `STYLE_PORT` - The style renderer port.

## Running ##
```
docker run -p 4096:4096 -e STYLE_HOST=<HOST> -e STYLE_PORT=<PORT> -d carto-renderer
```

```
docker run -p 4096:4096 \
-e STYLE_HOST='carto-renderer.app.marathon.aws-us-west-2-staging.socrata.net' \
-e STYLE_PORT=80 \
-d carto-renderer
```
