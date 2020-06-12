import numpy
from osgeo import gdal
import osgeo.gdal_array as gdalarray
from PIL import Image

from .utils import gdal_write, ensure_dir_exists
from .exceptions import ImageOutputException


def Resampler(name):
    """Return a function performing given resampling algorithm."""

    def resample_average(path, dsquery, dstile, image_format):
        for i in range(1, dstile.RasterCount + 1):
            res = gdal.RegenerateOverview(
                dsquery.GetRasterBand(i), dstile.GetRasterBand(i), "average"
            )
            if res != 0:
                raise ImageOutputException(
                    "RegenerateOverview() failed with error %d" % res
                )

        gdal_write(path, dstile, image_format)

    def resample_antialias(path, dsquery, dstile, image_format):
        querysize = dsquery.RasterXSize
        tile_size = dstile.RasterXSize

        array = numpy.zeros((querysize, querysize, 4), numpy.uint8)
        for i in range(dstile.RasterCount):
            array[:,:,i] = gdalarray.BandReadAsArray(  # NOQA
                dsquery.GetRasterBand(i + 1), 0, 0, querysize, querysize
            )
        im = Image.fromarray(array, 'RGBA')  # Always four bands
        im1 = im.resize((tile_size, tile_size), Image.ANTIALIAS)

        if path.exists():
            im0 = Image.open(str(path))
            im1 = Image.composite(im1, im0, im1)

        ensure_dir_exists(path.parent)
        im1.save(str(path), image_format)

    if name == "average":
        return resample_average
    elif name == "antialias":
        return resample_antialias

    resampling_methods = {
        "near": gdal.GRA_NearestNeighbour,
        "bilinear": gdal.GRA_Bilinear,
        "cubic": gdal.GRA_Cubic,
        "cubicspline": gdal.GRA_CubicSpline,
        "lanczos": gdal.GRA_Lanczos
    }

    resampling_method = resampling_methods[name]

    def resample_gdal(path, dsquery, dstile, image_format):
        querysize = dsquery.RasterXSize
        tile_size = dstile.RasterXSize

        dsquery.SetGeoTransform((0.0, tile_size / float(querysize), 0.0, 0.0, 0.0, tile_size / float(querysize)))
        dstile.SetGeoTransform((0.0, 1.0, 0.0, 0.0, 0.0, 1.0))

        res = gdal.ReprojectImage(dsquery, dstile, None, None, resampling_method)
        if res != 0:
            raise ImageOutputException("ReprojectImage() failed with error %d" % res)

        gdal_write(path, dstile, image_format)

    return resample_gdal
