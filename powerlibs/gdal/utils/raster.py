from osgeo import gdal, osr
from shapely.geometry import Point


class RasterFile:
    def __init__(self, orthomosaic_path):
        raster = gdal.Open(str(orthomosaic_path))
        wkt = raster.GetProjection()
        width, height = raster.RasterXSize, raster.RasterYSize

        ulx, xres, _, uly, _, yres = raster.GetGeoTransform()
        lrx = ulx + (raster.RasterXSize * xres)
        lry = uly + (raster.RasterYSize * yres)
        native_bounds = (ulx, uly, lrx, lry)

        gsd_in_meters = abs(xres)
        gsd = gsd_in_meters * 100.0

        # EPSG:4326 bounds:
        source_reference_system = osr.SpatialReference()
        source_reference_system.ImportFromWkt(wkt)
        target_reference_system = osr.SpatialReference()
        target_reference_system.ImportFromEPSG(4326)

        transformation = osr.CoordinateTransformation(source_reference_system, target_reference_system)
        coordinates = ((ulx, uly), (lrx, lry))
        bounds = [transformation.TransformPoint(x, y)[:2] for x, y in coordinates]
        bounds = (bounds[0][0], bounds[0][1], bounds[1][0], bounds[1][1])
        center_coordinates = ((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)
        center = Point(center_coordinates)

        self.width = width
        self.height = height
        self.dimensions = (width, height)

        self.gsd = gsd

        self.wkt = wkt
        self.native_bounds = native_bounds
        self.bounds = bounds

        self.center_coordinates = center_coordinates
        self.center = center
