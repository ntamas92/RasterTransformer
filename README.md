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

## Usage:

#### Input arguments:
```
-i, --input               The input file or folder.
-o, --output              The output file or folder.
-s, --sensor              The input sensor (Sentinel, Landsat, SPOT).

[-f, --outputformat]      The output format of the image (GeoTiff, Erdas). Default: GeoTiff.
[-p, --projection]        The target projection (EPSG code or full WKT representation).
[--local-execution]       Indicates whether the conversion should be executed in a local temp directory.
```

#### Dataset information:
- **Sentinel-2**: The sentinel-2 dataset is built up from multiple tiles (Granules). For each Granule, different files contain each band information. The script is capable of merging these tiles into one output image. To do this, the script needs to have the original directory and file structure as it is distributed:

  ```
root
├───S2A_OPER_MTD_SAFL1C_*.xml
└───GRANULE
        ├───subfolder1
        │   ├───IMG_DATA
        |       ├─── *_B01.jp2
        |       ├─── *_B02.jp2
        |       ...
        ├───subfolder2
        │   ├───IMG_DATA
        |       ├─── *_B01.jp2
        |       ├─── *_B02.jp2
        |       ...
        ...
  ```
  The root `S2A_OPER_MTD_SAFL1C_*.xml` file is the metadata of the dataset. The input can be either the root directory, or the path to the metadata. 
  The sentinel tiles can rely on different coordinate reference systems, so reprojection of the tiles is necessary. If no projection is specified as input argument, then the projection of the first tile will be used for the whole dataset.
  
- **Sentintel-2 Tiled mode**: The script can also convert only a specific tile from a Sentinel dataset. In this case, the directory path of the tile should be the input.

- **Landsat**: In a Landsat dataset, each band is stored in different files. The input can be a file from the dataset or the containing folder. The file with the `_MTL.txt` suffix will be chosen for the metadata file.

- **SPOT**: A SPOT dataset contains all information in one GeoTiff file. The input can be the GeoTiff file, or the containing folder. The file with the same name as the input will be chosen as the metadata file. 

#### Zipped input

The script is capable of extracting and converting from a zipped dataset if it is provided as the input.
