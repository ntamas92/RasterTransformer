from osgeo import gdal
from os import path
from shutil import copyfile
import os
import sys
import argparse
import re
import tempfile

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

    @staticmethod
    def GetImageFormatFromString(imageFormatString):
        if imageFormatString is None or imageFormatString.lower() in ("gtiff", "geotiff", "tiff"):
            return ImageFormat.GTiff
        elif imageFormatString.lower() in ("hfa", "img", "erdas", "erdasimg"):
            return ImageFormat.HFA
        else:
            LogError("The specified output format is not supported: " + imageFormatString)


class Sensor:
    """ Represents a sensor format """
    Sentinel_2, Landsat, SPOT, Unknown = range(4)

    @staticmethod
    def GetBandsForSensor(sensor):
        """ Gets the bands for a specific sensor in order. """
        if sensor == Sensor.Landsat:
            return ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10", "B11", "BQA"]
        elif sensor == Sensor.Sentinel_2:
            return ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B10", "B11", "B12"]
        else:
            return None

    @staticmethod
    def GetSensorFromString(sensorString):
        if sensorString.lower() in ("sentinel_2", "sentinel2", "sentinel"):
            return Sensor.Sentinel_2
        elif sensorString.lower() == "landsat":
            return Sensor.Landsat
        elif sensorString.lower() == "spot":
            return Sensor.SPOT
        else:
            LogError("The specified sensor is not supported: " + sensorString)


class CustomArgumentParser(argparse.ArgumentParser):
    def format_help(self):
        print 'Usage: python RasterTransformer.py'
        print "Parameters:"
        parameters = [
            ('-i, --input', 'The input file or folder.'),
            ('-o, --output', 'The output file or folder.'),
            ('-s, --sensor', 'The input sensor (Sentinel, Landsat, SPOT).'),
            ('', ''),
            ('[-f, --outputformat]', 'The output format of the image (GeoTiff, Erdas). Default: GeoTiff.'),
            ('[-p, --projection]', 'The target projection.'),
            ('[--local-execution]', 'Indicates whether the conversion should be executed in a local temp directory.')]

        for helpKey, helpText in parameters:
            print " ".ljust(3), "%-25s %s" % (helpKey, helpText)


def main():
    # The argparse module has some issues with printing the help page so a custom help will be used
    parser = CustomArgumentParser(usage='python RasterTransformer.py [--help] -i <input> -o <output> -s <sensor>')
    parser.add_argument('-i', '--input', dest='Input', required=True)
    parser.add_argument('-o', '--output', dest='Output', required=True)
    parser.add_argument('-s', '--sensor', dest='Sensor', required=True)
    parser.add_argument('-f', '--outputformat', dest='OutputFormat')
    parser.add_argument('-p', '--projection', dest='Projection')
    parser.add_argument('--local-execution', dest='LocalExecution', action='store_true')

    args = parser.parse_args()

    args.Sensor = Sensor.GetSensorFromString(args.Sensor)
    args.OutputFormat = ImageFormat.GetImageFormatFromString(args.OutputFormat)

    if not (path.exists(args.Input)):
        LogError("The specified input does not exist!")

    try:
        if args.Sensor == Sensor.Sentinel_2:
            ConvertFromSentinel(args)
        elif args.Sensor == Sensor.Landsat:
            ConvertFromLandsat(args)
        elif args.Sensor == Sensor.SPOT:
            ConvertFromSpot(args)
        else:
            LogError("The specified sensor is not supported!")
    except Exception as ex:
        LogError("Exception occurred during execution:" + str(ex))


def ConvertFromSentinel(options):
    """ Converts a sentinel dataset or tile to a specified output image. """
    if path.isdir(options.Input):
        metadataFilePattern = "2A_OPER_MTD_SAFL1C_(.*)\.xml"
        metadataFound = False
        for fileEntry in os.listdir(options.Input):
            if re.search(metadataFilePattern, fileEntry) is not None:
                options.Input = path.join(options.Input, fileEntry)
                metadataFound = True
                break

        if not metadataFound:
            ConvertFromSentinelTile(options)
            return

    ConvertFromSentinelDataset(options)


def ConvertFromSentinelTile(options):
    """ Converts a sentinel tile to a specified output image. """
    print "Converting Sentinel-2 tile..."

    vrt = GetVRTFromSentinelTile(options.Input)

    CreateOutputPath(options)

    if path.isdir(options.Output):
        firstFileName = path.splitext(path.basename(os.listdir(options.Input)[0]))[0]
        outputFileNameWithoutExtension = path.splitext(firstFileName)[0]

        outputFile = path.join(options.Output, outputFileNameWithoutExtension + ImageFormat.Extension(options.OutputFormat))

    inputMetadata = path.join(options.Input, "metadata.xml")
    outputMetadata = None
    if path.exists(inputMetadata):
        outputMetadata = path.join(path.dirname(outputFile), "metadata.xml")
    else:
        inputMetadata = None

    ProduceOutput(options, outputFile, vrt, inputMetadata, outputMetadata)


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

    vrts = []

    for tile in os.listdir(granulePath):
        tilePath = path.join(granulePath, tile)
        imageFolder = path.join(tilePath, "IMG_DATA")

        if not (path.exists(imageFolder)):
            LogError("Cannot find the image folder (IMG_DATA) for the following granule: " + tilePath)

        vrts.append(GetVRTFromSentinelTile(imageFolder))

    CreateOutputPath(options)

    if path.isdir(options.Output):
        inputFileName, extension = path.splitext(path.basename(options.Input))
        outputFileName = inputFileName + ImageFormat.Extension(options.OutputFormat)

        outputFile = path.join(options.Output, outputFileName)
    else:
        outputFile = options.Output

    outputMetadata = path.splitext(outputFile)[0] + ".xml"

    ProduceOutput(options, outputFile, vrts, options.Input, outputMetadata)


def GetVRTFromSentinelTile(tilePath):
    """ Gets a Virtual Raster Table (VRT) for a sentinel tile. """
    print "Building VRT from tile: " + tilePath

    imageFilesInOrder = []
    bandsNotFound = []
    files = os.listdir(tilePath)
    for band in Sensor.GetBandsForSensor(Sensor.Sentinel_2):
        imageWithBand = [x for x in files if x.upper().endswith(band + ".JP2")]
        if len(imageWithBand) != 1:
            bandsNotFound.append(band)
        else:
            imageFilesInOrder.append(path.join(tilePath, imageWithBand[0]))

    if len(bandsNotFound) != 0:
        LogError("Cannot find the appropriate file for " + ', '.join(bandsNotFound) + " band(s)!")
    if len(imageFilesInOrder) == 0:
        LogError("There are no image files to convert from!")

    return gdal.BuildVRT("", imageFilesInOrder, **{'separate': 'true'})


def ConvertFromLandsat(options):
    """ Converts a landsat dataset to a specified output image. """

    inputFiles = []

    if path.isfile(options.Input):
        fileNamePrefix = path.basename(options.Input)
        if fileNamePrefix.upper().endswith("_MTL.TXT") or fileNamePrefix.upper().endswith("_BQA.TXT"):
            fileNamePrefix = fileNamePrefix[:-8]
        else:
            fileNamePrefix = fileNamePrefix[:-7]

        directoryName = path.dirname(options.Input)
        inputFiles = [path.join(directoryName, x) for x in os.listdir(directoryName) if x.startswith(fileNamePrefix)]
    else:
        inputFiles = [path.join(options.Input, x) for x in os.listdir(options.Input)]

    print "Converting Landsat data under the specified path: " + options.Input

    landsatFiles = []
    metadataFile = ""

    for fileEntry in inputFiles:
        if fileEntry.upper().endswith("_MTL.TXT"):
            metadataFile = fileEntry
        elif path.splitext(fileEntry)[1].upper() == ".TIF":
            landsatFiles.append(fileEntry)

    imageFilesInOrder = []
    bandsNotFound = []
    for band in Sensor.GetBandsForSensor(Sensor.Landsat):
        imageWithBand = [x for x in landsatFiles if x.upper().endswith(band + ".TIF")]
        if len(imageWithBand) != 1:
            bandsNotFound.append(band)
        else:
            imageFilesInOrder.append(path.join(options.Input, imageWithBand[0]))

    if len(bandsNotFound) != 0:
        LogWarning("Cannot find the appropriate file for " + ', '.join(bandsNotFound) + " band(s)!")
    if len(imageFilesInOrder) == 0:
        LogError("There are no image files to convert from!")
    if metadataFile == "":
        LogWarning("Cannot find the metadata file!")

    print "Building VRT from the files..."
    vrt = gdal.BuildVRT("", imageFilesInOrder, **{'separate': 'true'})

    CreateOutputPath(options)

    if path.isdir(options.Output):
        firstFileName = path.splitext(path.basename(imageFilesInOrder[0]))[0]
        outputFileNameWithoutExtension = firstFileName[:-3]  # Remove the _B1 suffix from the filename

        outputFile = path.join(options.Output, outputFileNameWithoutExtension + ImageFormat.Extension(options.OutputFormat))
    else:
        outputFile = options.Output

    outputMetadata = path.splitext(outputFile)[0] + ".txt"

    ProduceOutput(options, outputFile, vrt, metadataFile, outputMetadata)


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
        if not inputFile.lower().endswith(".tif"):
            LogError("The specified input file is not a GeoTiff file!")
    else:
        LogError("The specified input file or folder does not exist!")

    inputMetadata = path.splitext(inputFile)[0] + ".xml"
    if not (path.exists(inputMetadata)):
        LogWarning("Cannot find metadata for the input file!")
        inputMetadata = ""

    print "Building VRT from the files..."
    vrt = gdal.BuildVRT("", inputFile)

    CreateOutputPath(options)

    if path.isdir(options.Output):
        outputWithoutExtension = path.splitext(path.basename(options.Input))[0]
        outputFile = path.join(options.Output, outputWithoutExtension + ImageFormat.Extension(options.OutputFormat))
    else:
        outputFile = options.Output

    outputMetadata = path.splitext(outputFile)[0] + ".xml"

    ProduceOutput(options, outputFile, vrt, inputMetadata, outputMetadata)


def ProduceOutput(options, outputFile, vrts, inputMetadata=None, outputMetadata=None):
    print "Translating VRT to the specified output..."
    warpOptions = BuildWarpOptions(options)
    gdal.Warp(outputFile, vrts, **warpOptions)

    if inputMetadata is not None and inputMetadata != "":
        print "Copying metadata file to the specified output..."
        copyfile(inputMetadata, outputMetadata)

    print "Done."


def CreateOutputPath(options):
    if path.isdir(options.Output) or options.Output.endswith(os.sep):
        outputDir = options.Output
    else:
        outputDir = path.dirname(options.Output)

    if not path.exists(outputDir):
        os.makedirs(options.Output)


def BuildWarpOptions(options):
    """ Builds GDALWarpOptions for the Warp method based on the input parameters. """
    warpOptions = {'format': ImageFormat.ToString(options.OutputFormat)}

    if options.OutputFormat == ImageFormat.GTiff:
        warpOptions['creationOptions'] = ['TILED=TRUE']
    if not (options.Projection == ""):
        warpOptions['dstSRS'] = options.Projection

    return warpOptions


def LogError(text):
    """ Prints error information. """
    print 'Error occurred: ' + text
    sys.exit(2)


def LogWarning(text):
    """ Prints warning information. """
    print 'Warning: ' + text

if __name__ == "__main__":
    main()
