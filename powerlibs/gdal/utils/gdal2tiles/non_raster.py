import os

from osgeo import gdal

from .global_mercator import GlobalMercator
from .global_geodetic import GlobalGeodetic
from .gdal2tiles import GDAL2Tiles
from .xyzzy import Xyzzy


class CommonProfile(GDAL2Tiles):
    def reproject_if_necessary(self):
        in_ds = self.in_ds

        zero_gcps = in_ds.GetGCPCount() == 0
        no_affine = in_ds.GetGeoTransform() == (0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
        if no_affine and zero_gcps:
            raise Exception(
                "There is no georeference - neither affine "
                "transformation (worldfile) nor GCPs. You can "
                "generate only 'raster' profile tiles.",
                "Either gdal2tiles with parameter -p 'raster' or use another "
                "GIS software for georeference e.g. "
                "gdal_transform -gcp / -a_ullr / -a_srs"
            )

        if not self.in_srs:
            raise Exception(
                "Input file has unknown SRS.",
                "Use --s_srs ESPG:xyz (or similar) to provide "
                "source reference system."
            )

        if (self.in_srs.ExportToProj4() != self.out_srs.ExportToProj4()) or (self.in_ds.GetGCPCount() != 0):
            # Generation of VRT dataset in tile projection, default 'nearest neighbour' warping
            self.out_ds = gdal.AutoCreateWarpedVRT(self.in_ds, self.in_srs_wkt, self.out_srs.ExportToWkt())

            # TODO: HIGH PRIORITY: Correction of AutoCreateWarpedVRT according the max zoomlevel for correct direct warping!!!

            # if verbose: self.out_ds.GetDriver().CreateCopy("tiles.vrt", self.out_ds)

            # Note: self.in_srs and self.in_srs_wkt contain still the non-warped reference system!!!

            # Correction of AutoCreateWarpedVRT for NODATA values
            if self.source_nodata != []:
                import tempfile
                tempfilename = tempfile.mktemp('-gdal2tiles.vrt')
                self.out_ds.GetDriver().CreateCopy(tempfilename, self.out_ds)
                # open as a text file
                s = open(tempfilename).read()
                # Add the warping options
                s = s.replace(
                    """<GDALWarpOptions>""",
                    """<GDALWarpOptions>
<Option name="INIT_DEST">NO_DATA</Option>
<Option name="UNIFIED_SRC_NODATA">YES</Option>"""
                )
                # replace BandMapping tag for NODATA bands....
                for i in range(len(self.source_nodata)):
                    s = s.replace("""<BandMapping src="%i" dst="%i"/>""" % ((i + 1), (i + 1)), """<BandMapping src="%i" dst="%i">
  <SrcNoDataReal>%i</SrcNoDataReal>
  <SrcNoDataImag>0</SrcNoDataImag>
  <DstNoDataReal>%i</DstNoDataReal>
  <DstNoDataImag>0</DstNoDataImag>
</BandMapping>""" % (
                        (i + 1), (i + 1),
                        self.source_nodata[i],
                        self.source_nodata[i])
                    )  # Or rewrite to white by: , 255 ))
                # save the corrected VRT
                # TODO: use TemporaryFile, here!!!
                open(tempfilename, "w").write(s)
                # open by GDAL as self.out_ds
                self.out_ds = gdal.Open(tempfilename)
                # delete the temporary file
                os.unlink(tempfilename)

                # set NODATA_VALUE metadata
                self.out_ds.SetMetadataItem('NODATA_VALUES', '%s' % " ".join(str(int(f)) for f in self.source_nodata))
#                        '%i %i %i' % (self.source_nodata[0],self.source_nodata[1],self.source_nodata[2]))

            # -----------------------------------
            # Correction of AutoCreateWarpedVRT for Mono (1 band) and RGB (3 bands) files without NODATA:
            # equivalent of gdalwarp -dstalpha
            if self.source_nodata == [] and self.out_ds.RasterCount in [1, 3]:
                import tempfile
                tempfilename = tempfile.mktemp('-gdal2tiles.vrt')
                self.out_ds.GetDriver().CreateCopy(tempfilename, self.out_ds)
                # open as a text file
                s = open(tempfilename).read()
                # Add the warping options
                s = s.replace("""<BlockXSize>""", """<VRTRasterBand dataType="Byte" band="%i" subClass="VRTWarpedRasterBand">
<ColorInterp>Alpha</ColorInterp>
</VRTRasterBand>
<BlockXSize>""" % (self.out_ds.RasterCount + 1))
                s = s.replace("""</GDALWarpOptions>""", """<DstAlphaBand>%i</DstAlphaBand>
</GDALWarpOptions>""" % (self.out_ds.RasterCount + 1))
                s = s.replace("""</WorkingDataType>""", """</WorkingDataType>
<Option name="INIT_DEST">0</Option>""")
                # save the corrected VRT
                open(tempfilename, "w").write(s)
                # open by GDAL as self.out_ds
                self.out_ds = gdal.Open(tempfilename)
                # delete the temporary file
                os.unlink(tempfilename)

            s = '''
            '''

    def geo_query(self, ds, ulx, uly, lrx, lry, querysize=0):
        """For given dataset and query in cartographic coordinates
        returns parameters for ReadRaster() in raster coordinates and
        x/y shifts (for border tiles). If the querysize is not given, the
        extent is returned in the native resolution of dataset ds."""

        geotran = ds.GetGeoTransform()
        rx = int((ulx - geotran[0]) / geotran[1] + 0.001)
        ry = int((uly - geotran[3]) / geotran[5] + 0.001)
        rxsize = int((lrx - ulx) / geotran[1] + 0.5)
        rysize = int((lry - uly) / geotran[5] + 0.5)

        if not querysize:
            wxsize, wysize = rxsize, rysize
        else:
            wxsize, wysize = querysize, querysize

        # Coordinates should not go out of the bounds of the raster
        wx = 0
        if rx < 0:
            rxshift = abs(rx)
            wx = int(wxsize * (float(rxshift) / rxsize))
            wxsize = wxsize - wx
            rxsize = rxsize - int(rxsize * (float(rxshift) / rxsize))
            rx = 0
        if rx + rxsize > ds.RasterXSize:
            wxsize = int(wxsize * (float(ds.RasterXSize - rx) / rxsize))
            rxsize = ds.RasterXSize - rx

        wy = 0
        if ry < 0:
            ryshift = abs(ry)
            wy = int(wysize * (float(ryshift) / rysize))
            wysize = wysize - wy
            rysize = rysize - int(rysize * (float(ryshift) / rysize))
            ry = 0
        if ry + rysize > ds.RasterYSize:
            wysize = int(wysize * (float(ds.RasterYSize - ry) / rysize))
            rysize = ds.RasterYSize - ry

        return (rx, ry, rxsize, rysize), (wx, wy, wxsize, wysize)

    def generate_base_tile_xyzzy(
        self,
        tx, ty, tz,
        querysize,
        tminx, tminy, tmaxx, tmaxy
    ):
        ds = self.out_ds
        b = self.get_tile_bounds(tx, ty, tz)
        rb, wb = self.geo_query(ds, b[0], b[3], b[2], b[1])

        querysize = self.querysize

        # Tile bounds in raster coordinates for ReadRaster query
        rb, wb = self.geo_query(
            ds, b[0], b[3], b[2], b[1], querysize=querysize
        )

        rx, ry, rxsize, rysize = rb
        wx, wy, wxsize, wysize = wb

        return Xyzzy(querysize, rx, ry, rxsize, rysize, wx, wy, wxsize, wysize)


class Mercator(CommonProfile):
    def set_out_srs(self):
        self.out_srs.ImportFromEPSG(900913)

    def calculate_ranges_for_tiles(self):
        # TODO: move it all to its own method:
        self.mercator = GlobalMercator()  # from globalmaptiles.py

        # Generate table with min max tile coordinates for all zoomlevels
        self.tminmax = list(range(0, 32))
        for tz in range(0, 32):
            tminx, tminy = self.mercator.MetersToTile(
                self.ominx, self.ominy, tz
            )
            tmaxx, tmaxy = self.mercator.MetersToTile(
                self.omaxx, self.omaxy, tz
            )
            # crop tiles extending world limits (+-180,+-90)
            tminx, tminy = max(0, tminx), max(0, tminy)
            tmaxx, tmaxy = min(2 ** tz - 1, tmaxx), min(2 ** tz - 1, tmaxy)
            self.tminmax[tz] = (tminx, tminy, tmaxx, tmaxy)

        # TODO: Maps crossing 180E (Alaska?)

        # Get the minimal zoom level (map covers area equivalent to one tile)
        max_dimension = max(self.out_ds.RasterXSize, self.out_ds.RasterYSize)
        if self.min_zoom is None:
            self.min_zoom = self.mercator.ZoomForPixelSize(
                self.out_gt[1] * max_dimension / float(self.tile_size)
            )

        # Get the maximal zoom level
        # (closest possible zoom level up on the resolution of raster)
        if self.max_zoom is None:
            self.max_zoom = self.mercator.ZoomForPixelSize(self.out_gt[1])

    def get_tile_bounds(self, tx, ty, tz):
        return self.mercator.TileBounds(tx, ty, tz)


class Geodetic(CommonProfile):
    def set_out_srs(self):
        self.out_srs.ImportFromEPSG(4326)

    def calculate_ranges_for_tiles(self):
        # TODO: move it all to its own method:
        self.geodetic = GlobalGeodetic()

        # Generate table with min max tile coordinates for all zoomlevels
        self.tminmax = list(range(0, 32))
        ominx = self.ominx
        ominy = self.ominy
        omaxx = self.omaxx
        omaxy = self.omaxy
        for tz in range(0, 32):
            tminx, tminy = self.geodetic.LatLonToTile(ominx, ominy, tz)
            tmaxx, tmaxy = self.geodetic.LatLonToTile(omaxx, omaxy, tz)

            # crop tiles extending world limits (+-180,+-90)
            tminx, tminy = max(0, tminx), max(0, tminy)
            tmaxx, tmaxy = min(2**(tz + 1) - 1, tmaxx), min(2 ** tz - 1, tmaxy)
            self.tminmax[tz] = (tminx, tminy, tmaxx, tmaxy)

        # TODO: Maps crossing 180E (Alaska?)

        # Get the maximal zoom level
        # (closest possible zoom level up on the resolution of raster)
        if self.min_zoom is None:
            max_dimension = max(
                self.out_ds.RasterXSize, self.out_ds.RasterYSize
            )
            self.min_zoom = self.geodetic.ZoomForPixelSize(
                self.out_gt[1] * max_dimension / float(self.tile_size)
            )

        # Get the maximal zoom level
        # (closest possible zoom level up on the resolution of raster)
        if self.max_zoom is None:
            self.max_zoom = self.geodetic.ZoomForPixelSize(self.out_gt[1])

    def get_tile_bounds(self, tx, ty, tz):
        return self.geodetic.TileBounds(tx, ty, tz)
