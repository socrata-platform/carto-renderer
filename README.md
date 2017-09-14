# Carto Test Service #
This is a service that's a proof of concept for getting a service that
renders vector tiles into images using CartoCSS.

## Start the Service (Uses Docker) ##
```
bin/start-renderer.sh
```

## Start the Service (without Docker) ##
This requires Mapnik3.0

Install Mapnik (OSX):
```
brew install mapnik
```

Install Mapnik (Debian/Ubuntu):
```
sudo apt-get install python-mapnik
```

Install Python Dependencies:
```
pip install -r dev-requirements.txt
```

## Start the Service ##
```
bin/start-renderer.sh --dev
```

## Examples ##
Render an image to `test.png`:
```
curl -o test.png localhost:4096/render -H 'Content-type: application/json' -d @carto_renderer/examples/main.json
```

## Testing ##
The tests are run using py.test and hypothesis

```
bin/test.sh
```

## Build Docker Image ##
```
bin/dockerize.sh
```
