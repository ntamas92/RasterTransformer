# RasterTransformer
A simple console script to convert and merge remote sensed images into a specific output format. The script relies on the Geospatial Data Abstraction Library (GDAL).

## Prerequisites:
- Python 2.7 or later
- GDAL 2.1 or later

#### Installing the prerequisites on Windows: 
Python and GDAL can be easily installed by following the instructions of [this tutorial](http://sandbox.idre.ucla.edu/sandbox/tutorials/installing-gdal-for-windows). Upon download, please double-check the version of the GDAL binaries.

#### Installing the prerequisites on Linux:
The easiest way to install GDAL 2.1 on Linux systems is to download [the source](http://download.osgeo.org/gdal/2.1.0/gdal-2.1.0.tar.gz) directly, uncompress it and `make install`:

```
$ sudo apt-get build-dep gdal
$ cd gdal-2.1.0/
$ ./configure --prefix=/usr/
$ make
$ sudo make install
$ cd swig/python/
$ sudo python setup.py install
```

#### Deploying to Docker:
A docker image from the project can be created in a straightforward manner using the `Dockerfile` attached.

## Supported satellite images:
- [Sentinel-2](https://sentinel.esa.int/web/sentinel/missions/sentinel-2)
- [Landsat 8](http://landsat.usgs.gov/landsat8.php)
- [SPOT 5](http://www.satimagingcorp.com/satellite-sensors/other-satellite-sensors/spot-5/)
