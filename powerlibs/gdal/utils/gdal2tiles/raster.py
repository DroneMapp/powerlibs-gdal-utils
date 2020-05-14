import math

from .gdal2tiles import GDAL2Tiles
from .image_output import SimpleImageOutput
from .resampler import Resampler
from .xyzzy import Xyzzy


class Raster(GDAL2Tiles):
    def set_out_srs(self):
        self.out_srs = self.in_srs

    def adjust_zoom(self):
        def log2(x):
            return math.log10(x) / math.log10(2)

        self.nativezoom = int(
            max(math.ceil(log2(self.out_ds.RasterXSize / float(self.tile_size))),
                math.ceil(log2(self.out_ds.RasterYSize / float(self.tile_size))))
        )

        # Get the minimal zoom level (whole raster in one tile)
        if self.min_zoom is None:
            self.min_zoom = 0

        # Get the maximal zoom level (native resolution of the raster)
        if self.max_zoom is None:
            self.max_zoom = self.nativezoom

    def calculate_ranges_for_tiles(self):
        # Generate table with min max tile coordinates for all zoomlevels
        self.tminmax = list(range(0, self.max_zoom + 1))
        self.tsize = list(range(0, self.max_zoom + 1))
        for tz in range(0, self.max_zoom + 1):
            tsize = 2.0**(self.nativezoom - tz) * self.tile_size
            tminx, tminy = 0, 0
            tmaxx = int(math.ceil(self.out_ds.RasterXSize / tsize)) - 1
            tmaxy = int(math.ceil(self.out_ds.RasterYSize / tsize)) - 1
            self.tsize[tz] = math.ceil(tsize)
            self.tminmax[tz] = (tminx, tminy, tmaxx, tmaxy)

    def generate_base_tile_xyzzy(
        self,
        tx, ty, tz,
        querysize,
        tminx, tminy, tmaxx, tmaxy
    ):
        # tile_size in raster coordinates for actual zoom:
        tsize = int(self.tsize[tz])

        # size of the raster in pixels:
        xsize = self.out_ds.RasterXSize
        ysize = self.out_ds.RasterYSize

        if tz >= self.nativezoom:
            querysize = self.tile_size

        rx = (tx) * tsize
        rxsize = 0
        if tx == tmaxx:
            rxsize = xsize % tsize
        if rxsize == 0:
            rxsize = tsize

        rysize = 0
        if ty == tmaxy:
            rysize = ysize % tsize
        if rysize == 0:
            rysize = tsize
        ry = ysize - (ty * tsize) - rysize

        wx, wy = 0, 0
        wxsize = int(rxsize / float(tsize) * self.tile_size)
        wysize = int(rysize / float(tsize) * self.tile_size)

        if wysize != self.tile_size:
            wy = self.tile_size - wysize

        return Xyzzy(querysize, rx, ry, rxsize, rysize, wx, wy, wxsize, wysize)


class LeafletImageOutput(SimpleImageOutput):
    def get_tileposy(self, ty, cy):
        if ty:
            return cy % (2 * ty) * self.tile_size
        elif ty == 0 and cy == 1:
            return self.tile_size
        return 0


class Leaflet(Raster):
    def get_y_range(self):
        tminx, tminy, tmaxx, tmaxy = self.tminmax[self.max_zoom]
        return range(tminy, tmaxy + 1)

    def instantiate_image_output(self):
        resampler = Resampler(self.resampling_method)
        self.image_output = LeafletImageOutput(
            self.out_ds,
            self.tile_size,
            resampler,
            self.source_nodata,
            self.output_dir
        )

    def generate_base_tile_xyzzy(
        self,
        tx, ty, tz,
        querysize,
        tminx, tminy, tmaxx, tmaxy
    ):
        # tile_size in raster coordinates for actual zoom:
        tsize = int(self.tsize[tz])

        # size of the raster in pixels:
        xsize = self.out_ds.RasterXSize
        ysize = self.out_ds.RasterYSize

        if tz >= self.nativezoom:
            querysize = self.tile_size

        rx = (tx) * tsize
        rxsize = 0
        if tx == tmaxx:
            rxsize = xsize % tsize
        if rxsize == 0:
            rxsize = tsize

        rysize = 0
        if ty == tmaxy:
            rysize = ysize % tsize
        if rysize == 0:
            rysize = tsize
        ry = ty * tsize

        wx, wy = 0, 0
        wxsize = int(rxsize / float(tsize) * self.tile_size)
        wysize = int(rysize / float(tsize) * self.tile_size)

        return Xyzzy(querysize, rx, ry, rxsize, rysize, wx, wy, wxsize, wysize)
