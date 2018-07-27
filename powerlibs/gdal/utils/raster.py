from osgeo import gdal, osr
from shapely.geometry import Point


class RasterFile:
    def __init__(self, orthomosaic_path):
        raster = gdal.Open(str(orthomosaic_path))
        self.raster = raster
        wkt = raster.GetProjection()
        width, height = raster.RasterXSize, raster.RasterYSize

        ulx, xres, _, uly, _, yres = raster.GetGeoTransform()
        lrx = ulx + (raster.RasterXSize * xres)
        lry = uly + (raster.RasterYSize * yres)
        native_bounds = (ulx, uly, lrx, lry)

        gsd_in_meters_x = abs(xres)
        gsd_in_meters_y = abs(yres)
        self.gsd_x = gsd_in_meters_x
        self.gsd_y = gsd_in_meters_y
        self.gsd = gsd_in_meters_x * 100  # centimeters

        self.raster_band = self.raster.GetRasterBand(1)
        self.no_data_value = self.raster_band.GetNoDataValue()
        stats = self.raster_band.GetStatistics(True, True)
        self.lower_altitude = stats[0]
        self.higher_altitude = stats[1]
        self.mean_altitude = stats[2]
        self.altitude_std_deviation = stats[3]

        # EPSG:4326 bounds:
        source_reference_system = osr.SpatialReference()
        source_reference_system.ImportFromWkt(wkt)

        self.epsg = None
        authority = source_reference_system.GetAttrValue("AUTHORITY", 0)
        code = source_reference_system.GetAttrValue("AUTHORITY", 1)
        if authority == 'EPSG':
            self.epsg = int(code)

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

        self.wkt = wkt
        self.native_bounds = native_bounds
        self.bounds = bounds

        self.center_coordinates = center_coordinates
        self.center = center
