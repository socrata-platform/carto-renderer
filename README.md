# [ARCHIVED] Carto Test Service #
*NOTE* As of December 2025 this service is deprecated.

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
sudo apt-get install python3-mapnik
```

Install Python Dependencies:
```
pip install -r dev-requirements.txt
```

## Start the Service ##
```
bin/start-renderer.sh --dev
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

## Releasing ##

Releases are managed by the shared release process.
