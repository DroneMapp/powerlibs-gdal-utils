import math

from .defines import MAXZOOMLEVEL


class GlobalGeodetic:
    def __init__(self, tile_size=256):
        self.tile_size = tile_size

    def LatLonToPixels(self, lat, lon, zoom):
        "Converts lat/lon to pixel coordinates in given zoom of the EPSG:4326 pyramid"

        res = 180.0 / self.tile_size / 2**zoom
        px = (180 + lat) / res
        py = (90 + lon) / res
        return px, py

    def PixelsToTile(self, px, py):
        "Returns coordinates of the tile covering region in pixel coordinates"

        tx = int(math.ceil(px / float(self.tile_size)) - 1)
        ty = int(math.ceil(py / float(self.tile_size)) - 1)
        return tx, ty

    def LatLonToTile(self, lat, lon, zoom):
        "Returns the tile for zoom which covers given lat/lon coordinates"

        px, py = self.LatLonToPixels(lat, lon, zoom)
        return self.PixelsToTile(px, py)

    def Resolution(self, zoom):
        "Resolution (arc/pixel) for given zoom level (measured at Equator)"

        return 180.0 / self.tile_size / 2**zoom

    def ZoomForPixelSize(self, pixelSize):
        "Maximal scaledown zoom of the pyramid closest to the pixelSize."

        for i in range(MAXZOOMLEVEL):
            if pixelSize > self.Resolution(i):
                if i != 0:
                    return i - 1
                else:
                    return 0  # We don't want to scale up

    def TileBounds(self, tx, ty, zoom):
        "Returns bounds of the given tile"
        res = 180.0 / self.tile_size / 2**zoom
        return (
            tx * self.tile_size * res - 180,
            ty * self.tile_size * res - 90,
            (tx + 1) * self.tile_size * res - 180,
            (ty + 1) * self.tile_size * res - 90
        )

    def TileLatLonBounds(self, tx, ty, zoom):
        "Returns bounds of the given tile in the SWNE form"
        b = self.TileBounds(tx, ty, zoom)
        return (b[1], b[0], b[3], b[2])
