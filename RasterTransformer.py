from osgeo import gdal
from os import path
from shutil import copyfile
import os
import sys
import getopt
import time
import re

class ImageFormat:
    GTiff, HFA, JP2000 = range(3)
	
    @staticmethod
    def ToString(format):
        if(format == ImageFormat.GTiff):
            return "GTiff"
        if(format == ImageFormat.HFA):
            return "HFA"

    @staticmethod
    def Extension(format):
        if(format == ImageFormat.GTiff):
            return ".tif"
        if(format == ImageFormat.HFA):
            return ".img"

class SensorFormat:
	Sentinel_2, Landsat, SPOT, Unknown = range(4)
	
	@staticmethod
	def ToString(format):
		if(format == SensorFormat.Sentinel_2):
			return "Sentinel-2"
		if(format == SensorFormat.Landsat):
			return "Landsat"
		if(format == SensorFormat.SPOT):
			return "SPOT"            

class Bands:
	@staticmethod
	def GetBandsForSensor(sensorFormat):
		if(sensorFormat == SensorFormat.Landsat):
			return ["_B1","_B2","_B3","_B4","_B5","_B6","_B7","_B8","_B9","_B10","_B11","_BQA"]
		elif(sensorFormat == SensorFormat.Sentinel_2):
			return ["_B01","_B02","_B03","_B04","_B05","_B06","_B07","_B08","_B8A","_B09","_B10","_B11","_B12"]
	
class Options:
	def __init__(self, argv):
		self.Input = ""
		self.Output = ""
		self.OutputFormat = ImageFormat.GTiff
		self.Sensor = SensorFormat.Unknown
		self.Projection = ""

		try:
			opts, args = getopt.getopt(argv,"hi:o:f:s:p:",["help", "input=","output=", "outputFormat=", "sensor=" "projection="])
			if(len(opts) == 0):
				Usage()
			
		except getopt.GetoptError as err:
			print "Error occured parsing the arguments!"
			Usage()
		for opt, arg in opts:
			if opt in ("-h", "-help", "--help", "/h", "/help"):
				LongUsage()
			elif opt in ("-i", "-input" "--input", "/i", "/input"):
				self.Input = path.abspath(arg)
			elif opt in ("-o", "-output" "--output" "/o", "/output"):
				self.Output = path.abspath(arg)
				if(arg.endswith(os.sep)):
					self.Output += os.sep
			elif opt.lower() in ("-f", "-outputformat" "--outputformat", "/f", "/outputformat"):
				if(arg.lower() in ("gtiff", "geotiff", "tiff")):
					self.OutputFormat = ImageFormat.GTiff
				elif(arg.lower() in ("hfa", "img", "erdas", "erdasimg")):
					self.OutputFormat = ImageFormat.HFA
				else:
					LogError("The specified output format is not supported: " + arg)
			elif opt in ("-s", "-sensor", "--sensor", "/s", "/sensor"):
				if(arg.lower() in ("sentinel_2", "sentinel2", "sentinel")):
					self.Sensor = SensorFormat.Sentinel_2
				elif(arg.lower() == "landsat"):
					self.Sensor = SensorFormat.Landsat
				elif(arg.lower() == "spot"):
					self.Sensor = SensorFormat.SPOT
				else:
					LogError("The specified sensor is not supported!")
			elif opt in ("-p", "-projection" "--projection", "/p", "/projection"):
				self.Projection = arg
				
		if(self.Input == ''):
			LogError("The input is not specified!")
		if(sef.Output == ''):
			LogError("The output is not specified!")
		if(self.Sensor == SensorFormat.Unknown):
			LogError("The sensor format is not specified!")
	
def Usage():
	print 'Usage: python RasterTransformer.py [--help] -i <input> -o <output> -s <sensor>'
	sys.exit(2)
	
def LongUsage():
	print 'Usage: python RasterTransformer.py'
	print "Parameters:" 
	parameters = [
		('-i, --input', 'The input file or folder.'),
		('-o, --output', 'The output file or folder.'),
		('-s, --sensor', 'The input sensor format (Sentinel, Landsat, SPOT).'),
		('', ''),
		('[-f, --outputFormat]', 'The output format of the image (GeoTiff, Erdas). Default: GeoTiff.'),
		('[-p, --projection]',  'The target projection.')]

	for helpKey, helpText in parameters:
		print " ".ljust(3), "%-25s %s" % (helpKey, helpText)

	sys.exit(2)
	
def LogError(text):
	print 'Error: ' + text
	sys.exit(2)

def main(argv):
    options = Options(argv)

    if not(path.exists(options.Input)):
        LogError("The specified input does not exist!")
	
    if(options.Sensor == SensorFormat.Sentinel_2):
        ConvertFromSentinel(options)
    elif(options.Sensor == SensorFormat.Landsat):
        ConvertFromLandsat(options)
    elif(options.Sensor == SensorFormat.SPOT):
        ConvertFromSpot(options)
    else:
        LogError("The sensor format is not specified!")

def ConvertFromSentinel(options):
	if(path.isdir(options.Input)):
		metadataFileExpression = "2A_OPER_MTD_SAFL1C_(.*)\.xml"
		metadataFound = False
		for root, dirs, files in os.walk(options.Input):
			for name in files:
				if(re.search(metadataFileExpression, name) != None):
					options.Input = path.join(root, name)
					metadataFound = True
					break
			break
			
		if not(metadataFound):
			ConvertFromSentinelTile(options)
			return

	ConvertFromSentinelDataset(options)


def ConvertFromSentinelTile(options):
	vrt = GetVRTFromSentinelTile(options.Input)
	
	if(path.isdir(options.Output) or options.Output.endswith(os.sep)):
		if not (path.exists(options.Output)):
			os.makedirs(options.Output)
		
		firstFileName = path.splitext(path.basename(os.listdir(options.Input)[0]))[0]
		outputFileNameWithoutExtension = firstFileName[:-3]
		
		outputFile = path.join(options.Output, outputFileNameWithoutExtension + ImageFormat.Extension(options.OutputFormat))
		outputMetadata = path.join(options.Output, outputFileNameWithoutExtension + ".xml")
	else:
		if not (path.exists(path.dirname(options.Output))):
			os.makedirs(options.Output)
			
	warpOptions = BuildWarpOptions(options)
	gdal.Warp(outputFile, vrt, **warpOptions)
	
			
def ConvertFromSentinelDataset(options):
	dataset = gdal.Open(options.Input)        
	if(dataset == None):
		LogError("The specified input cannot be opened as a Sentinel-2 dataset!")

	if(options.Projection == ""):
		subdatasetName, description = dataset.GetSubDatasets()[0]
		options.Projection = gdal.Open(subdatasetName).GetProjection()

	granulePath = path.join(path.dirname(options.Input), "GRANULE")
	if not(path.exists(granulePath)):
            LogError("Cannot find GRANULE folder in the input dataset!")

	tiles = os.listdir(granulePath)
	vrts = []
	
	for tile in tiles:
		tilePath = path.join(granulePath, tile)
		imageFolder = path.join(tilePath, "IMG_DATA")
		
		if not(path.exists(imageFolder)):
			LogError("Cannot find the image folder (IMG_DATA) for the following granule: " + tilePath)
			
		vrts.append(GetVRTFromSentinelTile(imageFolder))

	if(path.isdir(options.Output) or options.Output.endswith(os.sep)):
		if not (path.exists(options.Output)):
			os.makedirs(options.Output)
			
		inputFileName, extension = path.splitext(path.basename(options.Input))
		outputFileName = inputFileName + ImageFormat.Extension(options.OutputFormat)
		outputMetadataName = inputFileName + extension
							
		outputFile = path.join(options.Output, outputFileName)
		outputMetadata = path.join(options.Output, outputMetadataName)
	else:
		if not(path.exists(path.dirname(options.Output))):
			os.makedirs(path.dirname(options.Output))
		
		outputFile = options.Output
		outputMetadata = path.splitext(outputFile)[0] + ".xml"

	warpOptions = BuildWarpOptions(options)

	gdal.Warp(outputFile, vrts, **warpOptions)
	copyfile(options.Input, outputMetadata)

def GetVRTFromSentinelTile(tilePath):        
	imageFilesInOrder = []
	files = os.listdir(tilePath)
	for band in Bands.GetBandsForSensor(SensorFormat.Sentinel_2) :
		imageFile = next(x for x in files if x.upper().endswith(band + ".JP2"))
		imageFilesInOrder.append(path.join(tilePath, imageFile))
	
	return gdal.BuildVRT("", imageFilesInOrder, **{'separate':'true'})

	
def ConvertFromLandsat(options):
	if(path.isfile(options.Input)):
		options.Input = path.dirname(options.Input)
		
	landsatFiles = []
		
	for root, dirs, files in os.walk(options.Input):
		for file in files:
			if(file.upper().endswith("_MTL.TXT")):
				metadataFile = path.join(options.Input, file)
			elif(path.splitext(file)[1].upper() == ".TIF"):
				landsatFiles.append(file)
		break
	
	imageFilesInOrder = []
	for band in Bands.GetBandsForSensor(SensorFormat.Landsat) :
		imageFile = next(x for x in landsatFiles if x.upper().endswith(band + ".TIF"))
		imageFilesInOrder.append(path.join(options.Input, imageFile))
	
	vrt = gdal.BuildVRT("", imageFilesInOrder, **{'separate':'true'})
	
	if(path.isdir(options.Output) or options.Output.endswith(os.sep)):
		if not (path.exists(options.Output)):
			os.makedirs(options.Output)
		
		firstFileName = path.splitext(path.basename(imageFilesInOrder[0]))[0]
		outputFileNameWithoutExtension = firstFileName[:-3]
		
		outputFile = path.join(options.Output, outputFileNameWithoutExtension + ImageFormat.Extension(options.OutputFormat))
		outputMetadata = path.join(options.Output, outputFileNameWithoutExtension + ".txt")
	else:
		if not (path.exists(path.dirname(options.Output))):
			os.makedirs(options.Output)
		
		outputFile = options.Output
		outputMetadata = path.splitext(options.Output)[0] + ".txt"
	
	warpOptions = BuildWarpOptions(options)
	
	gdal.Warp(outputFile, vrt, **warpOptions)
	copyfile(metadataFile, outputMetadata)
	
def ConvertFromSpot(options):
	pass

def BuildWarpOptions(options):
	warpOptions = {'format':ImageFormat.ToString(options.OutputFormat)}
	
	if(options.OutputFormat == ImageFormat.GTiff):
		warpOptions['creationOptions'] = ['TILED=TRUE']
	if not (options.Projection == ""):
		warpOptions['dstSRS'] = options.Projection
	
	return warpOptions
	
if __name__ == "__main__":
	main(sys.argv[1:])
