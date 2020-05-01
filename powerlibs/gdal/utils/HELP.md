# globalmaptiles.py

## Global Map Tiles as defined in Tile Map Service (TMS) Profiles

Functions necessary for generation of global tiles used on the web.

It contains classes implementing coordinate conversions for:

* GlobalMercator (based on EPSG:900913 = EPSG:3785) - for Google Maps,
  Yahoo Maps, Microsoft Maps compatible tiles
* GlobalGeodetic (based on EPSG:4326) - for OpenLayers Base Map and Google
  Earth compatible tiles


More info at:

* http://wiki.osgeo.org/wiki/Tile_Map_Service_Specification
  http://wiki.osgeo.org/wiki/WMS_Tiling_Client_Recommendation
  http://msdn.microsoft.com/en-us/library/bb259689.aspx
  http://code.google.com/apis/maps/documentation/overlays.html#Google_Maps_Coordinates

---

Created by Klokan Petr Pridal on 2008-07-03.

Google Summer of Code 2008, project GDAL2Tiles for OSGEO.


In case you use this class in your product, translate it to another
language or find it usefull for your project please let me know.

My email: klokan at klokan dot cz. I would like to know where it was used.


**Class is available under the open-source GDAL license (www.gdal.org).**

# TMS Global Geodetic Profile

Functions necessary for generation of global tiles in Plate Carre projection,
EPSG:4326, "unprojected profile".

Such tiles are compatible with Google Earth (as any other EPSG:4326 rasters)
and you can overlay the tiles on top of OpenLayers base map.

Pixel and tile coordinates are in TMS notation (origin [0,0] in bottom-left).

What coordinate conversions do we need for TMS Global Geodetic tiles?

```
  Global Geodetic tiles are using geodetic coordinates (latitude,longitude)
  directly as planar coordinates XY (it is also called Unprojected or Plate
  Carre). We need only scaling to pixel pyramid and cutting to tiles.
  Pyramid has on top level two tiles, so it is not square but rectangle.
  Area [-180,-90,180,90] is scaled to 512x256 pixels.
  TMS has coordinate origin (for pixels and tiles) in bottom-left corner.
  Rasters are in EPSG:4326 and therefore are compatible with Google Earth.
```

```
     LatLon      <->      Pixels      <->     Tiles

 WGS84 coordinates   Pixels in pyramid  Tiles in pyramid
     lat/lon         XY pixels Z zoom      XYZ from TMS
    EPSG:4326
     .----.                ----
    /      \     <->    /--------/    <->      TMS
    \      /         /--------------/
     -----        /--------------------/
   WMS, KML    Web Clients, Google Earth  TileMapService
```
