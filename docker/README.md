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

## Running ##
```
docker run -p 4096:4096 -d carto-renderer
```
