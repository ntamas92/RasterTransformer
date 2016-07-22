FROM ubuntu:latest

WORKDIR /opt/iqmulus/tmp 

RUN apt-get update
RUN apt-get install -y wget
RUN apt-get install -y python
RUN apt-get build-dep -y gdal

RUN wget http://download.osgeo.org/gdal/2.1.0/gdal-2.1.0.tar.gz
RUN tar -xzf gdal-2.1.0.tar.gz gdal-2.1.0/

WORKDIR gdal-2.1.0
RUN ./configure --prefix=/usr
RUN make
RUN make install

WORKDIR swig/python
RUN python setup.py install

WORKDIR /opt/iqmulus/
RUN rm -rf tmp

COPY RasterTransformer.py /opt/iqmulus/