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

To tag a release to be built and deployed to RC:

1. Create a branch from main and run `bin/release.py`.
1. Follow the prompts to bump the version, which will create two commits.
1. Create a PR and get it merged to main.
