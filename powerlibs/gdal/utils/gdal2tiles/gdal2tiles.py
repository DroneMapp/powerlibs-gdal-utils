from pathlib import PosixPath

import numpy
from osgeo import gdal
from osgeo import osr

from .image_output import SimpleImageOutput
from .resampler import Resampler


class GDAL2Tiles:
    def __init__(
            self,
            source_path, output_dir,
            min_zoom=None, max_zoom=None,
            resampling_method='average',
            source_srs=None, source_nodata=None
    ):
        self.source_path = PosixPath(source_path)
        self.output_dir = output_dir
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom

        self.resampling_method = resampling_method
        self.source_srs = source_srs
        self.source_nodata = source_nodata

        # Tile format
        self.tile_size = 256

        # Should we read bigger window of the input raster and scale it down?
        # Note: Modified later by open_input()
        # Not for 'near' resampling
        # Not for Wavelet based drivers (JPEG2000, ECW, MrSID)
        # Not for 'raster' profile
        self.scaledquery = True

        # Should we use Read on the input file for generating overview tiles?
        # Note: Modified later by open_input()
        # Otherwise the overview tiles are generated from
        # existing underlying tiles
        self.overviewquery = False

        self.srcnodata = None
        self.check_resampling_method_availability()
        self.set_querysize()

    def set_querysize(self):
        # How big should be query window be for scaling down
        # Later on reset according the chosen resampling algorightm

        if self.resampling_method == 'near':
            self.querysize = self.tile_size
        elif self.resampling_method == 'bilinear':
            self.querysize = self.tile_size * 2
        else:
            self.querysize = 4 * self.tile_size

    def check_resampling_method_availability(self):
        # Supported options
        if self.resampling_method == 'average':
            try:
                gdal.RegenerateOverview
            except Exception:
                raise Exception(
                    "'average' resampling algorithm is not available.",
                    "Please use -r 'near' argument or upgrade to newer version of GDAL."
                )

        elif self.resampling_method == 'antialias':
            try:
                numpy
            except Exception:
                raise Exception(
                    "'antialias' resampling algorithm is not available.",
                    "Install PIL (Python Imaging Library) and numpy."
                )

    # -------------------------------------------------------------------------
    def process(self):
        # Opening and preprocessing of the input file
        self.open_input()

        # Generation of the lowest tiles
        self.generate_base_tiles()

        # Generation of the overview tiles (higher in the pyramid)
        self.generate_overview_tiles()

    def open_input(self):
        """Initialization of the input raster, reprojection if necessary"""
        self.initialize_input_raster()

        self.set_out_srs()

        self.out_ds = None
        self.reproject_if_necessary()
        if not self.out_ds:
            self.out_ds = self.in_ds

        self.instantiate_image_output()
        self.configure_bounds()
        self.adjust_zoom()
        self.calculate_ranges_for_tiles()

    def reproject_if_necessary(self):
        pass

    def initialize_input_raster(self):
        gdal.SetConfigOption("GDAL_PAM_ENABLED", "NO")
        gdal.AllRegister()

        # Open the input file
        self.in_ds = gdal.Open(str(self.source_path), gdal.GA_ReadOnly)

        if not self.in_ds:
            # Note: GDAL prints the ERROR message too
            raise Exception(
                'It is not possible to open the '
                f'input file "{self.source_path}".'
            )

        # Read metadata from the input file
        if self.in_ds.RasterCount == 0:
            raise Exception("Input file '%s' has no raster band" % self.source_path)

        if self.in_ds.GetRasterBand(1).GetRasterColorTable():
            # TODO: Process directly paletted dataset by generating VRT in memory
            raise Exception(
                "Please convert this file to RGB/RGBA and run gdal2tiles on the result.",
                """From paletted file you can create RGBA file (temp.vrt) by:
gdal_translate -of vrt -expand rgba %s temp.vrt
then run:
gdal2tiles temp.vrt""" % self.source_path)

        # Get NODATA value
        # User supplied values overwrite everything else.
        if self.srcnodata:
            nds = list(map(float, self.srcnodata.split(',')))
            raster_count = self.in_ds.RasterCount
            if len(nds) < raster_count:
                self.source_nodata = (nds * raster_count)[:raster_count]
            else:
                self.source_nodata = nds
        else:
            # If the source dataset has NODATA, use it.
            self.source_nodata = []
            for i in range(1, self.in_ds.RasterCount + 1):
                if self.in_ds.GetRasterBand(i).GetNoDataValue() is not None:
                    self.source_nodata.append(self.in_ds.GetRasterBand(i).GetNoDataValue())

        #
        # Here we should have RGBA input dataset opened in self.in_ds

        # Spatial Reference System of the input raster
        self.in_srs = None

        if self.source_srs:
            self.in_srs = osr.SpatialReference()
            self.in_srs.SetFromUserInput(self.source_srs)
            self.in_srs_wkt = self.in_srs.ExportToWkt()
        else:
            self.in_srs_wkt = self.in_ds.GetProjection()
            if not self.in_srs_wkt and self.in_ds.GetGCPCount() != 0:
                self.in_srs_wkt = self.in_ds.GetGCPProjection()
            if self.in_srs_wkt:
                self.in_srs = osr.SpatialReference()
                self.in_srs.ImportFromWkt(self.in_srs_wkt)

        # Spatial Reference System of tiles
        self.out_srs = osr.SpatialReference()

    def set_out_srs(self):
        pass

    def instantiate_image_output(self):
        # Instantiate image output.
        self.image_output = ImageOutput(
            self.out_ds,
            self.tile_size,
            self.resampling_method,
            self.source_nodata,
            self.output_dir
        )

    def configure_bounds(self):
        # Read the georeference
        self.out_gt = self.out_ds.GetGeoTransform()

        # Report error in case rotation/skew is in geotransform
        # (possible only in 'raster' profile)
        # TODO: move to raster.Raster, somehow...
        if (self.out_gt[2], self.out_gt[4]) != (0, 0):
            raise Exception(
                "Georeference of the raster contains rotation or skew. "
                "Such raster is not supported. Please use gdalwarp first."
            )
            # TODO: Do the warping in this case automaticaly

        #
        # Here we expect: pixel is square, no rotation on the raster
        #

        # Output Bounds - coordinates in the output SRS
        self.ominx = self.out_gt[0]
        self.omaxx = self.out_gt[0] + self.out_ds.RasterXSize * self.out_gt[1]
        self.omaxy = self.out_gt[3]
        self.ominy = self.out_gt[3] - self.out_ds.RasterYSize * self.out_gt[1]
        # Note: maybe round(x, 14) to avoid the gdal_translate behaviour,
        # when 0 becomes -1e-15

    # -------------------------------------------------------------------------
    def generate_base_tiles(self):
        """Generation of the base tiles (the lowest in the pyramid)
        directly from the input raster"""

        # Set the bounds
        tminx, tminy, tmaxx, tmaxy = self.tminmax[self.max_zoom]
        querysize = self.querysize

        # Just the center tile
        # tminx = tminx+ (tmaxx - tminx)/2
        # tminy = tminy+ (tmaxy - tminy)/2
        # tmaxx = tminx
        # tmaxy = tminy

        tz = self.max_zoom
        for ty in self.get_y_range():
            for tx in range(tminx, tmaxx + 1):
                xyzzy = self.generate_base_tile_xyzzy(
                    tx, ty, tz,
                    querysize,
                    tminx, tminy, tmaxx, tmaxy
                )

                self.image_output.write_base_tile(tx, ty, tz, xyzzy)

    # -------------------------------------------------------------------------
    def generate_overview_tiles(self):
        """Generation of the overview tiles (higher in the pyramid)
        based on existing tiles"""
        # Usage of existing tiles:
        # from 4 underlying tiles generate one as overview.

        tcount = 0
        for tz in range(self.max_zoom - 1, self.min_zoom - 1, -1):
            tminx, tminy, tmaxx, tmaxy = self.tminmax[tz]
            tcount += (1 + abs(tmaxx - tminx)) * (1 + abs(tmaxy - tminy))

        # querysize = tile_size * 2
        for tz in range(self.max_zoom - 1, self.min_zoom - 1, -1):
            tminx, tminy, tmaxx, tmaxy = self.tminmax[tz]
            for ty in self.get_y_range():
                for tx in range(tminx, tmaxx + 1):
                    self.image_output.write_overview_tile(tx, ty, tz)

    def get_y_range(self):
        tminx, tminy, tmaxx, tmaxy = self.tminmax[self.max_zoom]
        return range(tmaxy, tminy - 1, -1)


def ImageOutput(out_ds, tile_size, resampling, nodata, output_dir):
    """Return object representing tile image output
    implementing given parameters."""

    resampler = Resampler(resampling)
    return SimpleImageOutput(
        out_ds, tile_size, resampler, nodata, output_dir
    )
