# Carto Test Service #
This is a service that's a proof of concept for getting a service that
renders vector tiles into images using CartoCSS.

You can exercise it with the following curl commands.

## Installation ##
Install Mapnik (OSX):
```
brew tap homebrew/versions
brew update
brew install mapnik2
```

Install Mapnik (Debian/Ubuntu):
```
sudo apt-get install python-mapnik2
```

Install Python Dependencies:
```
pip install -r requirements.txt
```

Render an image to `test.png`:
```
curl -o test.png localhost:4096/render -H 'Content-type: application/json' -d @carto_renderer/examples/main.json
```

## Start the Service ##
```
PYTHONPATH=. carto_renderer/service.py
```

## Testing ##
The tests are run using py.test and hypothesis

You can install them by running:
```
pip install 
```

Run tests from the root directory:
```
PYTHONPATH=. py.test
```
