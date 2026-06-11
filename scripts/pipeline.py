# scripts/pipeline.py
# GEE Python API pipeline - Prey Lang Wildlife Sanctuary forest health monitoring
# Authenticates to Google Earth Engine, builds median composites for 2022, 2024 and 2026,
# calculates spectral indices and change detection, exports GeoTIFFs to Google Drive

import ee
import geopandas as gpd
import json
import time


def initialise_gee():
    ee.Initialize(project='preylangcambodia')
    print('GEE initialised successfully')


def load_boundary(shapefile_path):
    # Read shapefile, reproject to WGS84, convert to GEE geometry
    gdf = gpd.read_file(shapefile_path)
    gdf = gdf.to_crs('EPSG:4326')
    geojson = json.loads(gdf.geometry.to_json())
    boundary = ee.Geometry(geojson['features'][0]['geometry'])
    print(f'Boundary loaded: {gdf.shape[0]} feature(s)')
    return boundary


def mask_s2_clouds(image):
    # Mask cloud and cirrus using QA60 bitmask band (bits 10 and 11)
    qa = image.select('QA60')
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = (qa.bitwiseAnd(cloud_bit_mask).eq(0)
              .And(qa.bitwiseAnd(cirrus_bit_mask).eq(0)))
    return image.updateMask(mask).divide(10000)


def build_composite(boundary, start_date, end_date):
    # Build cloud-masked median composite for a given date window
    return (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(boundary)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            .map(mask_s2_clouds)
            .median()
            .clip(boundary))


def calc_indices(image):
    # Calculate all five spectral indices and return as multi-band image
    # All bands cast to Float32 for consistent export data type
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI').toFloat()
    evi  = image.expression(
        '2.5 * ((B8 - B4) / (B8 + 6 * B4 - 7.5 * B2 + 1))', {
            'B8': image.select('B8'),
            'B4': image.select('B4'),
            'B2': image.select('B2')
        }).rename('EVI').toFloat()
    nbr  = image.normalizedDifference(['B8', 'B12']).rename('NBR').toFloat()
    ndre = image.normalizedDifference(['B8', 'B5']).rename('NDRE').toFloat()
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI').toFloat()
    return ee.Image.cat([ndvi, evi, nbr, ndre, ndmi])


def calc_change_detection(composite_2022, composite_2024, composite_2026):
    # Calculate dNBR and dNDVI difference rasters between temporal composites
    # Convention: earlier minus later; positive dNBR = loss, negative = gain
    nbr_2022 = composite_2022.normalizedDifference(['B8', 'B12'])
    nbr_2024 = composite_2024.normalizedDifference(['B8', 'B12'])
    nbr_2026 = composite_2026.normalizedDifference(['B8', 'B12'])
    ndvi_2022 = composite_2022.normalizedDifference(['B8', 'B4'])
    ndvi_2026 = composite_2026.normalizedDifference(['B8', 'B4'])

    dnbr_2022_2024 = nbr_2022.subtract(nbr_2024).rename('dNBR_2022_2024')
    dnbr_2024_2026 = nbr_2024.subtract(nbr_2026).rename('dNBR_2024_2026')
    dnbr_2022_2026 = nbr_2022.subtract(nbr_2026).rename('dNBR_2022_2026')
    dndvi_2022_2026 = ndvi_2022.subtract(ndvi_2026).rename('dNDVI_2022_2026')

    # Classify dNBR 2022-2026: 1=Gain, 2=Stable, 3=Moderate loss, 4=High loss
    classified = (dnbr_2022_2026
        .where(dnbr_2022_2026.lt(-0.1), 1)
        .where(dnbr_2022_2026.gte(-0.1).And(dnbr_2022_2026.lt(0.1)), 2)
        .where(dnbr_2022_2026.gte(0.1).And(dnbr_2022_2026.lt(0.3)), 3)
        .where(dnbr_2022_2026.gte(0.3), 4)
        .rename('disturbance_class'))

    return dnbr_2022_2024, dnbr_2024_2026, dnbr_2022_2026, dndvi_2022_2026, classified


def compute_zonal_stats(indices_2022, indices_2024, indices_2026,
                        dnbr_2022_2024, dnbr_2024_2026, dnbr_2022_2026,
                        boundary):
    # Stack all index bands and compute mean, min, max, stddev per band
    all_indices = ee.Image.cat([
        indices_2022.rename(['NDVI_2022','EVI_2022','NBR_2022','NDRE_2022','NDMI_2022']),
        indices_2024.rename(['NDVI_2024','EVI_2024','NBR_2024','NDRE_2024','NDMI_2024']),
        indices_2026.rename(['NDVI_2026','EVI_2026','NBR_2026','NDRE_2026','NDMI_2026']),
        dnbr_2022_2024, dnbr_2024_2026, dnbr_2022_2026
    ])

    zonal_stats = all_indices.reduceRegion(
        reducer=ee.Reducer.mean().combine(
            ee.Reducer.min(), '', True).combine(
            ee.Reducer.max(), '', True).combine(
            ee.Reducer.stdDev(), '', True),
        geometry=boundary,
        scale=20,
        maxPixels=1e9
    )

    stats_dict = zonal_stats.getInfo()
    print('Zonal statistics:')
    for key, value in sorted(stats_dict.items()):
        print(f'  {key}: {value:.4f}' if value is not None else f'  {key}: None')
    return stats_dict


def export_geotiffs(composite_2022, composite_2024, composite_2026,
                   indices_2022, indices_2024, indices_2026,
                   dnbr_2022_2026, classified, boundary):
    # Submit all GeoTIFF export tasks to Google Drive folder PreyLangCambodia
    export_tasks = [
        # RGB composites for each year
        {'image': composite_2022.select(['B4','B3','B2']),
         'description': 'PreyLang_RGB_2022'},
        {'image': composite_2024.select(['B4','B3','B2']),
         'description': 'PreyLang_RGB_2024'},
        {'image': composite_2026.select(['B4','B3','B2']),
         'description': 'PreyLang_RGB_2026'},
        # Index stacks per year (NDVI, EVI, NBR, NDRE, NDMI as bands)
        {'image': indices_2022.rename(['NDVI','EVI','NBR','NDRE','NDMI']),
         'description': 'PreyLang_Indices_2022'},
        {'image': indices_2024.rename(['NDVI','EVI','NBR','NDRE','NDMI']),
         'description': 'PreyLang_Indices_2024'},
        {'image': indices_2026.rename(['NDVI','EVI','NBR','NDRE','NDMI']),
         'description': 'PreyLang_Indices_2026'},
        # Change detection outputs
        {'image': dnbr_2022_2026,
         'description': 'PreyLang_dNBR_2022_2026'},
        {'image': classified,
         'description': 'PreyLang_Classified_2022_2026'},
    ]

    for task_params in export_tasks:
        task = ee.batch.Export.image.toDrive(
            image=task_params['image'],
            description=task_params['description'],
            folder='PreyLangCambodia',
            fileNamePrefix=task_params['description'],
            region=boundary,
            scale=20,
            crs='EPSG:4326',
            maxPixels=1e9
        )
        task.start()
        print(f'  Export started: {task_params["description"]}')

    print('All export tasks submitted')
    print('Monitor progress at: https://code.earthengine.google.com/tasks')
    print('Exports will appear in Google Drive folder: PreyLangCambodia')


def main():
    boundary_path = (
        r'raw_data\WDPA_WDOECM_Jun2026_Public_555703480_shp_0'
        r'\WDPA_WDOECM_Jun2026_Public_555703480_shp-polygons.shp'
    )

    initialise_gee()

    boundary = load_boundary(boundary_path)

    print('Building composites...')
    composite_2022 = build_composite(boundary, '2022-01-01', '2022-02-28')
    composite_2024 = build_composite(boundary, '2024-01-01', '2024-02-28')
    composite_2026 = build_composite(boundary, '2026-01-01', '2026-02-28')
    print('Composites built')

    print('Calculating indices...')
    indices_2022 = calc_indices(composite_2022)
    indices_2024 = calc_indices(composite_2024)
    indices_2026 = calc_indices(composite_2026)
    print('Indices calculated')

    print('Calculating change detection...')
    (dnbr_2022_2024, dnbr_2024_2026,
     dnbr_2022_2026, dndvi_2022_2026, classified) = calc_change_detection(
        composite_2022, composite_2024, composite_2026)
    print('Change detection calculated')

    print('Computing zonal statistics...')
    stats = compute_zonal_stats(
        indices_2022, indices_2024, indices_2026,
        dnbr_2022_2024, dnbr_2024_2026, dnbr_2022_2026,
        boundary)

    print('Submitting export tasks...')
    export_geotiffs(
        composite_2022, composite_2024, composite_2026,
        indices_2022, indices_2024, indices_2026,
        dnbr_2022_2026, classified, boundary)


if __name__ == '__main__':
    main()