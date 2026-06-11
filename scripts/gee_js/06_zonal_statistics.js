// 06_zonal_statistics
// Compute zonal statistics per index per temporal composite
// Results printed to console and exported as CSV to Google Drive

// Load Prey Lang boundary
var preyLang = ee.FeatureCollection('projects/preylangcambodia/assets/prey_lang_boundary');
var boundary = preyLang.geometry();

// Cloud masking function using QA60 band
function maskS2clouds(image) {
  var qa = image.select('QA60');
  var cloudBitMask = 1 << 10;
  var cirrusBitMask = 1 << 11;
  var mask = qa.bitwiseAnd(cloudBitMask).eq(0)
               .and(qa.bitwiseAnd(cirrusBitMask).eq(0));
  return image.updateMask(mask).divide(10000);
}

// Build median composite for a given date window
function buildComposite(startDate, endDate) {
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(boundary)
    .filterDate(startDate, endDate)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
    .map(maskS2clouds)
    .median()
    .clip(boundary);
}

// Build composites
var composite2022 = buildComposite('2022-01-01', '2022-02-28');
var composite2024 = buildComposite('2024-01-01', '2024-02-28');
var composite2026 = buildComposite('2026-01-01', '2026-02-28');

// Calculate all indices for each composite and stack as multi-band image
function calcAllIndices(image, year) {
  var ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI_' + year);
  var evi  = image.expression(
    '2.5 * ((B8 - B4) / (B8 + 6 * B4 - 7.5 * B2 + 1))', {
      'B8': image.select('B8'),
      'B4': image.select('B4'),
      'B2': image.select('B2')
    }).rename('EVI_' + year);
  var nbr  = image.normalizedDifference(['B8', 'B12']).rename('NBR_' + year);
  var ndre = image.normalizedDifference(['B8', 'B5']).rename('NDRE_' + year);
  var ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI_' + year);
  return ee.Image.cat([ndvi, evi, nbr, ndre, ndmi]);
}

var indices2022 = calcAllIndices(composite2022, '2022');
var indices2024 = calcAllIndices(composite2024, '2024');
var indices2026 = calcAllIndices(composite2026, '2026');

// Stack all indices across all years into one image
var allIndices = ee.Image.cat([indices2022, indices2024, indices2026]);

// Compute zonal statistics - mean, min, max, stddev for each band
var zonalStats = allIndices.reduceRegion({
  reducer: ee.Reducer.mean()
    .combine(ee.Reducer.min(), '', true)
    .combine(ee.Reducer.max(), '', true)
    .combine(ee.Reducer.stdDev(), '', true),
  geometry: boundary,
  scale: 20,
  maxPixels: 1e9
});

print('Zonal statistics - all indices all years:', zonalStats);

// Also compute change statistics
var nbr2022 = composite2022.normalizedDifference(['B8', 'B12']).rename('NBR');
var nbr2024 = composite2024.normalizedDifference(['B8', 'B12']).rename('NBR');
var nbr2026 = composite2026.normalizedDifference(['B8', 'B12']).rename('NBR');

var dNBR_2022_2024 = nbr2022.subtract(nbr2024).rename('dNBR_2022_2024');
var dNBR_2024_2026 = nbr2024.subtract(nbr2026).rename('dNBR_2024_2026');
var dNBR_2022_2026 = nbr2022.subtract(nbr2026).rename('dNBR_2022_2026');

var changeStats = ee.Image.cat([dNBR_2022_2024, dNBR_2024_2026, dNBR_2022_2026])
  .reduceRegion({
    reducer: ee.Reducer.mean()
      .combine(ee.Reducer.min(), '', true)
      .combine(ee.Reducer.max(), '', true)
      .combine(ee.Reducer.stdDev(), '', true),
    geometry: boundary,
    scale: 20,
    maxPixels: 1e9
  });

print('Change statistics:', changeStats);

// Format results as a feature for CSV export
// Each band stat becomes a property on a single feature
var exportFeature = ee.Feature(null, zonalStats.combine(changeStats));
var exportCollection = ee.FeatureCollection([exportFeature]);

// Export zonal statistics to Google Drive as CSV
Export.table.toDrive({
  collection: exportCollection,
  description: 'PreyLang_ZonalStats',
  folder: 'PreyLangCambodia',
  fileNamePrefix: 'prey_lang_zonal_statistics',
  fileFormat: 'CSV'
});

print('CSV export task submitted - check Tasks tab to run');