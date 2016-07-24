from osgeo import gdal
from os import path
from shutil import copyfile
import os
import sys
import getopt
import re


class ImageFormat:
    """ Represents an image format. """

    GTiff, HFA = range(2)

    @staticmethod
    def ToString(format):
        """ Returns the string representation of the image format. """
        if format == ImageFormat.GTiff:
            return "GTiff"
        if format == ImageFormat.HFA:
            return "HFA"

    @staticmethod
    def Extension(format):
        """ Returns the extension of the image format. """
        if format == ImageFormat.GTiff:
            return ".tif"
        if format == ImageFormat.HFA:
            return ".img"


class Sensor:
    """ Represents a sensor format """
    Sentinel_2, Landsat, SPOT, Unknown = range(4)

    @staticmethod
    def GetBandsForSensor(sensor):
        """ Gets the bands for a specific sensor in order. """
        if sensor == Sensor.Landsat:
            return ["_B1", "_B2", "_B3", "_B4", "_B5", "_B6", "_B7", "_B8", "_B9", "_B10", "_B11", "_BQA"]
        elif sensor == Sensor.Sentinel_2:
            return ["_B01", "_B02", "_B03", "_B04", "_B05", "_B06", "_B07", "_B08", "_B8A", "_B09", "_B10", "_B11", "_B12"]
        else:
            return None


class Options:
    """ Represents the options for running the script """
    def __init__(self, argv):
        self.Input = ""
        self.Output = ""
        self.OutputFormat = ImageFormat.GTiff
        self.Sensor = Sensor.Unknown
        self.Projection = ""

        try:
            opts, args = getopt.getopt(argv, "hi:o:f:s:p:", ["help", "input=", "output=", "outputformat=", "sensor=", "projection="])
            if len(opts) == 0:
                Usage()
        except getopt.GetoptError as err:
            print "Error occurred parsing the arguments: " + str(err)
            Usage()

        for opt, arg in opts:
            if opt in ("-h", "--help"):
                LongUsage()
            elif opt in ("-i", "--input"):
                self.Input = path.abspath(arg)
            elif opt in ("-o", "--output"):
                self.Output = path.abspath(arg)
                if arg.endswith(os.sep):
                    self.Output += os.sep
            elif opt.lower() in ("-f", "--outputformat"):
                if arg.lower() in ("gtiff", "geotiff", "tiff"):
                    self.OutputFormat = ImageFormat.GTiff
                elif arg.lower() in ("hfa", "img", "erdas", "erdasimg"):
                    self.OutputFormat = ImageFormat.HFA
                else:
                    LogError("The specified output format is not supported: " + arg)
            elif opt in ("-s", "--sensor"):
                if arg.lower() in ("sentinel_2", "sentinel2", "sentinel"):
                    self.Sensor = Sensor.Sentinel_2
                elif arg.lower() == "landsat":
                    self.Sensor = Sensor.Landsat
                elif arg.lower() == "spot":
                    self.Sensor = Sensor.SPOT
                else:
                    LogError("The specified sensor is not supported: " + arg)
            elif opt in ("-p", "--projection"):
                self.Projection = arg

        if self.Input == '':
            LogError("The input is not specified!")
        if self.Output == '':
            LogError("The output is not specified!")
        if self.Sensor == Sensor.Unknown:
            LogError("The input sensor is not specified!")


def Usage():
    """ Prints usage information about running the script. """
    print 'Usage: python RasterTransformer.py [--help] -i <input> -o <output> -s <sensor>'
    sys.exit(2)


def LongUsage():
    """ Prints detailed usage information about running the script. """
    print 'Usage: python RasterTransformer.py'
    print "Parameters:"
    parameters = [
        ('-i, --input', 'The input file or folder.'),
        ('-o, --output', 'The output file or folder.'),
        ('-s, --sensor', 'The input sensor (Sentinel, Landsat, SPOT).'),
        ('', ''),
        ('[-f, --outputformat]', 'The output format of the image (GeoTiff, Erdas). Default: GeoTiff.'),
        ('[-p, --projection]', 'The target projection.')]

    for helpKey, helpText in parameters:
        print " ".ljust(3), "%-25s %s" % (helpKey, helpText)

    sys.exit(2)


def LogError(text):
    """ Prints error information. """
    print 'Error occurred: ' + text
    sys.exit(2)


def LogWarning(text):
    """ Prints warning information. """
    print 'Warning: ' + text


def main(argv):
    options = Options(argv)

    if not (path.exists(options.Input)):
        LogError("The specified input does not exist!")

    if options.Sensor == Sensor.Sentinel_2:
        ConvertFromSentinel(options)
    elif options.Sensor == Sensor.Landsat:
        ConvertFromLandsat(options)
    elif options.Sensor == Sensor.SPOT:
        ConvertFromSpot(options)
    else:
        LogError("The specified sensor is not supported!")


def ConvertFromSentinel(options):
    """ Converts a sentinel dataset or tile to a specified output image. """
    if path.isdir(options.Input):
        metadataFileExpression = "2A_OPER_MTD_SAFL1C_(.*)\.xml"
        metadataFound = False
        for root, dirs, files in os.walk(options.Input):
            for name in files:
                if re.search(metadataFileExpression, name) is not None:
                    options.Input = path.join(root, name)
                    metadataFound = True
                    break
            break

        if not metadataFound:
            if len(os.listdir(options.Input)) == 0:
                LogError("There are no entires in the input path specified!")
            ConvertFromSentinelTile(options)
            return

    ConvertFromSentinelDataset(options)


def ConvertFromSentinelTile(options):
    """ Converts a sentinel tile to a specified output image. """
    print "Converting Sentinel-2 tile..."

    vrt = GetVRTFromSentinelTile(options.Input)

    if path.isdir(options.Output) or options.Output.endswith(os.sep):
        if not (path.exists(options.Output)):
            os.makedirs(options.Output)

        firstFileName = path.splitext(path.basename(os.listdir(options.Input)[0]))[0]
        outputFileNameWithoutExtension = path.splitext(firstFileName)[0]

        outputFile = path.join(options.Output,
                               outputFileNameWithoutExtension + ImageFormat.Extension(options.OutputFormat))
        outputMetadata = path.join(options.Output, outputFileNameWithoutExtension + ".xml")
    else:
        if not (path.exists(path.dirname(options.Output))):
            os.makedirs(options.Output)

    print "Translating VRT to the specified output..."
    warpOptions = BuildWarpOptions(options)
    gdal.Warp(outputFile, vrt, **warpOptions)

    print "Done."


def ConvertFromSentinelDataset(options):
    """ Converts a sentinel dataset to a specified output image. """
    print "Converting from Sentinel-2 dataset..."

    dataset = gdal.Open(options.Input)
    if dataset is None:
        LogError("The specified input cannot be opened as a Sentinel-2 dataset!")

    if options.Projection == "":
        subdatasets = dataset.GetSubDatasets()

        # Sentinel-2 should contain data as subdatasets.
        # If there are no subdatasets, the input is probably not a sentinel-2 dataset.
        if len(subdatasets) == 0:
            LogError("The specified input is not a valid Sentinel-2 dataset.")
        subdatasetName, description = subdatasets[0]
        options.Projection = gdal.Open(subdatasetName).GetProjection()

    granulePath = path.join(path.dirname(options.Input), "GRANULE")
    if not (path.exists(granulePath)):
        LogError("Cannot find GRANULE folder in the input dataset!")

    tiles = os.listdir(granulePath)
    vrts = []

    for tile in tiles:
        tilePath = path.join(granulePath, tile)
        imageFolder = path.join(tilePath, "IMG_DATA")

        if not (path.exists(imageFolder)):
            LogError("Cannot find the image folder (IMG_DATA) for the following granule: " + tilePath)

        vrts.append(GetVRTFromSentinelTile(imageFolder))

    if path.isdir(options.Output) or options.Output.endswith(os.sep):
        if not (path.exists(options.Output)):
            os.makedirs(options.Output)

        inputFileName, extension = path.splitext(path.basename(options.Input))
        outputFileName = inputFileName + ImageFormat.Extension(options.OutputFormat)
        outputMetadataName = inputFileName + extension

        outputFile = path.join(options.Output, outputFileName)
        outputMetadata = path.join(options.Output, outputMetadataName)
    else:
        if not (path.exists(path.dirname(options.Output))):
            os.makedirs(path.dirname(options.Output))

        outputFile = options.Output
        outputMetadata = path.splitext(outputFile)[0] + ".xml"

    warpOptions = BuildWarpOptions(options)

    print "Translating VRT to the specified output..."
    gdal.Warp(outputFile, vrts, **warpOptions)

    print "Copying metadata file to the specified output..."
    copyfile(options.Input, outputMetadata)

    print "Done."


def GetVRTFromSentinelTile(tilePath):
    """ Gets a Virtual Raster Table (VRT) for a sentinel tile. """
    print "Building VRT from tile: " + tilePath

    imageFilesInOrder = []
    bandsNotFound = []
    files = os.listdir(tilePath)
    for band in Sensor.GetBandsForSensor(Sensor.Sentinel_2):
        imageWithBand = [x for x in files if x.lower().endswith(band + ".jp2")]
        if len(imageWithBand) != 1:
            bandsNotFound.append(band)
        else:
            imageFilesInOrder.append(path.join(tilePath, imageWithBand[0]))

    if len(bandsNotFound) != 0:
        LogWarning("Cannot find the appropriate file for " + ', '.join(bandsNotFound) + " band(s)!")
    if len(imageFilesInOrder) == 0:
        LogError("There are no image files to convert from!")

    return gdal.BuildVRT("", imageFilesInOrder, **{'separate': 'true'})


def ConvertFromLandsat(options):
    """ Converts a landsat dataset to a specified output image. """
    if path.isfile(options.Input):
        options.Input = path.dirname(options.Input)

    print "Converting Landsat data under the specified path: " + options.Input

    landsatFiles = []
    metadataFile = ""

    for root, dirs, files in os.walk(options.Input):
        for file in files:
            if file.upper().endswith("_MTL.TXT"):
                metadataFile = path.join(options.Input, file)
            elif path.splitext(file)[1].lower() == ".tif":
                landsatFiles.append(file)
        break

    imageFilesInOrder = []
    bandsNotFound = []
    for band in Sensor.GetBandsForSensor(Sensor.Landsat):
        imageWithBand = [x for x in landsatFiles if x.lower().endswith(band + ".tif")]
        if len(imageWithBand) != 1:
            bandsNotFound.append(band)
        else:
            imageFilesInOrder.append(path.join(options.Input, imageWithBand[0]))

    if len(bandsNotFound) != 0:
        LogWarning("Cannot find the appropriate file for " + ', '.join(bandsNotFound) + " band(s)!")
    if len(imageFilesInOrder) == 0:
        LogError("There are no image files to convert from!")

    print "Building VRT from the files..."
    vrt = gdal.BuildVRT("", imageFilesInOrder, **{'separate': 'true'})

    if path.isdir(options.Output) or options.Output.endswith(os.sep):
        if not (path.exists(options.Output)):
            os.makedirs(options.Output)

        firstFileName = path.splitext(path.basename(imageFilesInOrder[0]))[0]
        outputFileNameWithoutExtension = firstFileName[:-3]

        outputFile = path.join(options.Output,
                               outputFileNameWithoutExtension + ImageFormat.Extension(options.OutputFormat))
        outputMetadata = path.join(options.Output, outputFileNameWithoutExtension + ".txt")
    else:
        if not (path.exists(path.dirname(options.Output))):
            os.makedirs(options.Output)

        outputFile = options.Output
        outputMetadata = path.splitext(options.Output)[0] + ".txt"

    warpOptions = BuildWarpOptions(options)

    print "Translating VRT to the specified output..."
    gdal.Warp(outputFile, vrt, **warpOptions)

    if metadataFile != "":
        print "Copying the metadata file..."
        copyfile(metadataFile, outputMetadata)
    else:
        LogWarning("Could not find the metadata file for the image!")

    print "Done."


def ConvertFromSpot(options):
    """ Converts a SPOT dataset to a specified output image. """
    print "Converting SPOT data under the specified path: " + options.Input

    inputFile = ""

    if path.isdir(options.Input):
        files = os.listdir(options.Input)
        for f in files:
            if f.lower().endswith(".tif"):
                inputFile = path.join(options.Input, f)
                break

        if inputFile == "":
            LogError("Cannot find the input image file!")
    elif path.isfile(options.Input):
        inputFile = options.Input
    else:
        LogError("The specified input file or folder does not exist!")

    inputMetadata = path.splitext(inputFile)[0] + ".xml"
    if not (path.exists(inputMetadata)):
        LogWarning("Cannot find metadata for the input file!")
        inputMetadata = ""

    print "Building VRT from the files..."
    vrt = gdal.BuildVRT("", inputFile)

    if path.isdir(options.Output) or options.Output.endswith(os.sep):
        if not (path.exists(options.Output)):
            os.makedirs(options.Output)

        outputWithoutExtension = path.splitext(path.basename(options.Input))[0]

        outputFile = path.join(options.Output, outputWithoutExtension + ImageFormat.Extension(options.OutputFormat))
        outputMetadata = path.join(options.Output, outputWithoutExtension + ".xml")
    else:
        if not (path.exists(path.dirname(options.Output))):
            os.makedirs(options.Output)

        outputFile = options.Output
        outputMetadata = path.splitext(options.Output)[0] + ".xml"

    print "Translating VRT to the specified output..."
    warpOptions = BuildWarpOptions(options)
    gdal.Warp(outputFile, vrt, **warpOptions)

    if inputMetadata != "":
        print "Copying the metadata file..."
        copyfile(inputMetadata, outputMetadata)

    print "Done."


def BuildWarpOptions(options):
    """ Builds GDALWarpOptions for the Warp method based on the input parameters. """
    warpOptions = {'format': ImageFormat.ToString(options.OutputFormat)}

    if options.OutputFormat == ImageFormat.GTiff:
        warpOptions['creationOptions'] = ['TILED=TRUE']
    if not (options.Projection == ""):
        warpOptions['dstSRS'] = options.Projection

    return warpOptions


if __name__ == "__main__":
    main(sys.argv[1:])
