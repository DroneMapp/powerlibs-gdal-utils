from osgeo import gdal


PNG_DRIVER = gdal.GetDriverByName('PNG')


def get_gdal_driver(name):
    driver = gdal.GetDriverByName(name)
    if driver is None:
        raise Exception(
            f'The "{name}" driver was not found, '
            'is it available in this GDAL build?')
    else:
        return driver


def gdal_write(path, dstile, image_format):
    ensure_dir_exists(path)
    PNG_DRIVER.CreateCopy(str(path), dstile, strict=0)


def ensure_dir_exists(path):
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
