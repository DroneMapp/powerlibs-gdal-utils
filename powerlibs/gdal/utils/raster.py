import logging
from multiprocessing import Pool as MultiProcessingPool
import os
import pickle
import threading
import time
import zlib

import gdal
from osgeo.gdalconst import GA_ReadOnly
import numpy

from saito import helpers
from .orthomosaic import Orthomosaic


PICKLE_PROTOCOL = 2
DEM_TILE_SIZE = 500

FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class AllNullError(Exception):
    pass


def generate_tiles_for_x(x, dem_file_path, target_dir):
    while True:
        try:
            dem_generator = DEM(dem_file_path)
            dem_generator.generate_tiles_for_x(x, target_dir)
        except Exception as ex:
            print(f'Exception on generate_tiles_for_x: {ex}')
            time.sleep(30)
            continue
        else:
            return


def clean_and_create(x, y, values, target_dir, no_data_flag):
    def do_mark(v):
        if v == no_data_flag:
            return None
        return v

    mark_as_none = numpy.vectorize(do_mark)

    try:
        cleaned_values = clean_values(values, no_data_flag, mark_as_none)
        logger.info(f'{x}x{y} cleaned')
        do_create_tile(x, y, target_dir, cleaned_values)
    except Exception as ex:
        logger.info(f'{x}x{y}: {ex}')
        return


def clean_values(values, no_data_flag, mark_as_none):
    for line in values:
        filtered_new_line = line[line != no_data_flag]
        if not filtered_new_line.any():
            raise AllNullError('All values are None!')

    cleaned_values = mark_as_none(values)
    return cleaned_values.tolist()


def do_create_tile(x, y, target_dir, values):
    logger.info(f'do_create_tile ({x},{y})')
    tile_name = f'{x}x{y}.gz'
    tile_path = os.path.join(target_dir, tile_name)

    if os.path.exists(tile_path):
        logger.info(f'{tile_name} already exists')
        return

    serialized_data = pickle.dumps(values, protocol=PICKLE_PROTOCOL)
    compress_data(serialized_data, tile_path)
    logger.info(f'{tile_name} created')


def compress_data(serialized_data, target_path):
    compressed_data = zlib.compress(serialized_data)
    save_compressed_data(compressed_data, target_path)
    logger.info(f'{target_path} compressed')


def save_compressed_data(compressed_data, target_path):
    with open(target_path, 'wb') as file_obj:
        file_obj.write(compressed_data)
    logger.info(f'saved into {target_path}')


class DEM():
    def __init__(self, dem_path, tile_size=DEM_TILE_SIZE):
        logger.info('opening DEM')

        self.dem_path = dem_path

        self.dataset = gdal.Open(dem_path, GA_ReadOnly)
        logger.info(' opened')
        self.tile_size = tile_size

        self.raster_band = self.dataset.GetRasterBand(1)
        self.width, self.height = self.raster_band.XSize, self.raster_band.YSize

        self.no_data_flag = self.raster_band.GetNoDataValue()

    def read_values(self, x, y):
        cols = self.tile_size
        if x + self.tile_size > self.width:
            cols = self.width - x

        rows = self.tile_size
        if y + self.tile_size > self.height:
            rows = self.height - y

        return numpy.array(self.raster_band.ReadAsArray(x, y, cols, rows))

    def read_tile_values(self, x, y, target_dir):
        values = self.read_values(x, y)
        if values is None:
            logger.info(f'values is None for ({x},{y})')
            return

        logger.info(f'read ({x},{y})')
        return values

    def generate_tiles_for_x(self, x, target_dir):
        max_threads = int(os.cpu_count())
        threads_list = []

        def join_threads(threads_list):
            for t in threads_list:
                t.join()

        counter = 0
        for y in range(0, self.height, self.tile_size):
            counter += 1
            values = self.read_tile_values(x, y, target_dir)
            t = threading.Thread(target=clean_and_create, args=(x, y, values, target_dir, self.no_data_flag), daemon=True)
            t.start()
            threads_list.append(t)

            if counter % max_threads == 0:
                join_threads(threads_list)

        join_threads(threads_list)

    @staticmethod
    def generate_tiles(dem_file_path, target_dir):
        helpers.ensure_dir(target_dir)

        tasks = []
        dem_file_path_str = str(dem_file_path)
        dem = Orthomosaic(dem_file_path_str)

        for x in range(0, dem.width, DEM_TILE_SIZE):
            tasks.append((x, dem_file_path_str, target_dir))

        num_processes = int(os.cpu_count())
        pool = MultiProcessingPool(num_processes)
        pool.starmap(generate_tiles_for_x, tasks)


if __name__ == '__main__':
    import sys

    dem_path = sys.argv[1]
    target_dir = sys.argv[2]

    DEM.generate_tiles(dem_path, target_dir)
