import logging
from pathlib import PosixPath
import os

from osgeo import gdal

from .utils import get_gdal_driver


logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'WARNING'))


def get_tile_filename(tx, ty, tz, extension):
    return os.path.join(str(tz), str(tx), "%s.%s" % (ty, extension))


class BaseImageOutput:
    """Base class for image output."""

    def __init__(
        self, out_ds, tile_size, resampler, write_method,
        nodata, output_dir
    ):
        self.out_ds = out_ds
        self.tile_size = tile_size
        self.resampler = resampler
        self.write_method = write_method
        self.nodata = nodata
        self.output_dir = PosixPath(output_dir)

        self.mem_drv = get_gdal_driver("MEM")
        self.alpha_filler = None

        # For raster with 4-bands: 4th unknown band set to alpha
        raster_count = self.out_ds.RasterCount
        if raster_count == 4:
            band4 = self.out_ds.GetRasterBand(4)
            if band4.GetRasterColorInterpretation() == gdal.GCI_Undefined:
                band4.SetRasterColorInterpretation(gdal.GCI_AlphaBand)

        # Get alpha band (either directly or from NODATA value)
        self.alpha_band = self.out_ds.GetRasterBand(1).GetMaskBand()

        has_alpha = self.alpha_band.GetMaskFlags() & gdal.GMF_ALPHA
        logger.debug(f'has_alpha: {has_alpha}')
        logger.debug(f'raster_count: {raster_count}')
        if not has_alpha and raster_count in (2, 4):
            self.alpha_band = self.out_ds.GetRasterBand(raster_count)
            has_alpha = True

        if has_alpha:
            self.alpha_filler = "\xff" * (self.tile_size * self.tile_size)
            self.data_bands_count = self.out_ds.RasterCount - 1
        else:
            logger.debug("NO ALPHA CHANNEL")
            self.data_bands_count = self.out_ds.RasterCount

    def create_base_tile(self, tx, ty, tz, xyzzy, alpha):
        """Create image of a base level tile and write it to disk."""
        path = self.get_full_path(tx, ty, tz, 'png')

        num_bands = self.data_bands_count
        if alpha is not None:
            num_bands += 1

        data_bands = list(range(1, self.data_bands_count + 1))

        dstile = self.mem_drv.Create(
            '', self.tile_size, self.tile_size, num_bands
        )
        data = self.out_ds.ReadRaster(
            xyzzy.rx, xyzzy.ry, xyzzy.rxsize, xyzzy.rysize,
            xyzzy.wxsize, xyzzy.wysize, band_list=data_bands
        )

        """
        ReadRaster call signature:
        ReadRaster(
            xoff=0, yoff=0,
            xsize=None, ysize=None,
            buf_xsize=None, buf_ysize=None,
            buf_type=None, band_list=None,
            buf_pixel_space=None, buf_line_space=None,
            buf_band_space=None,
            resample_alg=gdalconst.GRIORA_NearestNeighbour
        )
        """

        # Query is in 'nearest neighbour' but can be bigger than the tile_size.
        # We scale down the query to the tile_size by supplied algorithm.
        if self.tile_size == xyzzy.querysize:
            # Use the ReadRaster result directly in tiles ('nearest neighbour' query)
            dstile.WriteRaster(
                xyzzy.wx, xyzzy.wy,
                xyzzy.wxsize, xyzzy.wysize,
                data, band_list=data_bands
            )
            if alpha is not None:
                dstile.WriteRaster(
                    xyzzy.wx, xyzzy.wy,
                    xyzzy.wxsize, xyzzy.wysize,
                    alpha, band_list=[num_bands]
                )

            logger.info(f'saving base tile: {path}')
            self.write_method(path, dstile, 'PNG')

            # Note: For source drivers based on WaveLet compression (JPEG2000, ECW, MrSID)
            # the ReadRaster function returns high-quality raster (not ugly nearest neighbour)
            # TODO: Use directly 'near' for WaveLet files
        else:
            # Big ReadRaster query in memory scaled to the tile_size - all but 'near' algo
            dsquery = self.mem_drv.Create(
                '', xyzzy.querysize, xyzzy.querysize, num_bands
            )

            if alpha is None:
                for band_index in range(self.data_bands_count):
                    dsquery.GetRasterBand(band_index + 1).Fill(self.nodata)

            dsquery.WriteRaster(
                xyzzy.wx, xyzzy.wy,
                xyzzy.wxsize, xyzzy.wysize,
                data, band_list=data_bands
            )
            if alpha is not None:
                dsquery.WriteRaster(
                    xyzzy.wx, xyzzy.wy,
                    xyzzy.wxsize, xyzzy.wysize,
                    alpha, band_list=[num_bands]
                )
            logger.info(f'saving resampled base tile: {path}')
            self.resampler(path, dsquery, dstile)

    def write_overview_tile(self, tx, ty, tz, precheck_existence=True):
        """Create image of a overview level tile and write it to disk."""

        path = self.get_full_path(tx, ty, tz, 'png')
        if precheck_existence and path.exists():
            logger.info(f'write_overview_tile: {path} already exists. Skipping.')
            return

        num_bands = self.data_bands_count + 1

        dsquery = self.mem_drv.Create(
            '', 2 * self.tile_size, 2 * self.tile_size, num_bands
        )

        # Fill alpha band with zeroes (why? IDK)
        dsquery.GetRasterBand(num_bands).Fill(0)

        for cx, cy in self.iter_children(tx, ty, tz):
            tileposy = self.get_tileposy(ty, cy)
            if tx:
                tileposx = cx % (2 * tx) * self.tile_size
            elif tx == 0 and cx == 1:
                tileposx = self.tile_size
            else:
                tileposx = 0

            origin_path = self.get_full_path(
                cx, cy, tz + 1, 'png'
            )
            dsquerytile = gdal.Open(str(origin_path), gdal.GA_ReadOnly)
            dsdata = dsquerytile.ReadRaster(
                0, 0, self.tile_size, self.tile_size
            )

            dsquery.WriteRaster(
                tileposx, tileposy, self.tile_size, self.tile_size,
                dsdata,
                band_list=list(range(1, dsquerytile.RasterCount + 1))
            )

            if dsquerytile.RasterCount != num_bands:
                dsquery.WriteRaster(
                    tileposx, tileposy, self.tile_size, self.tile_size,
                    self.alpha_filler, band_list=[num_bands]
                )

        dstile = self.mem_drv.Create(
            '', self.tile_size, self.tile_size, num_bands
        )
        logger.info(f'saving overview tile: {path}')
        self.resampler(path, dsquery, dstile)

    def get_tileposy(self, ty, cy):
        if (ty == 0 and cy == 1) or (ty != 0 and (cy % (2 * ty)) != 0):
            return 0
        else:
            return self.tile_size

    def iter_children(self, tx, ty, tz):
        """Generate all children of the given
        tile produced on the lower level."""
        for y in range(2 * ty, 2 * ty + 2):
            for x in range(2 * tx, 2 * tx + 2):
                if self.tile_exists(x, y, tz + 1):
                    yield x, y

    def read_alpha(self, xyzzy):
        if self.alpha_band is None:
            return None

        return self.alpha_band.ReadRaster(
            xyzzy.rx, xyzzy.ry,
            xyzzy.rxsize, xyzzy.rysize,
            xyzzy.wxsize, xyzzy.wysize
        )

    def tile_exists(self, tx, ty, tz):
        return self.get_full_path(
            tx, ty, tz, 'png'
        ).exists()

    def get_full_path(self, tx, ty, tz, extension):
        filename = get_tile_filename(tx, ty, tz, extension)
        return self.output_dir / filename


class SimpleImageOutput(BaseImageOutput):
    """Image output using only one image format."""

    def write_base_tile(self, tx, ty, tz, xyzzy, precheck_existence=True):
        if precheck_existence:
            path = self.get_full_path(tx, ty, tz, 'png')
            if path.exists():
                logger.info(
                    f'write_base_tile: {path} already exists. Skipping.'
                )
                return
        alpha = self.read_alpha(xyzzy)
        self.create_base_tile(tx, ty, tz, xyzzy, alpha)
