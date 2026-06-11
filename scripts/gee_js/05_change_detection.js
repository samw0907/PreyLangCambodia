// 05_change_detection
// Calculate dNBR and dNDVI between 2022 and 2026 composites
// Classify disturbance severity and visualise results

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

// Calculate NBR for each composite
var nbr2022 = composite2022.normalizedDifference(['B8', 'B12']).rename('NBR');
var nbr2024 = composite2024.normalizedDifference(['B8', 'B12']).rename('NBR');
var nbr2026 = composite2026.normalizedDifference(['B8', 'B12']).rename('NBR');

// Calculate NDVI for each composite
var ndvi2022 = composite2022.normalizedDifference(['B8', 'B4']).rename('NDVI');
var ndvi2024 = composite2024.normalizedDifference(['B8', 'B4']).rename('NDVI');
var ndvi2026 = composite2026.normalizedDifference(['B8', 'B4']).rename('NDVI');

// Calculate difference rasters
// Convention: earlier minus later - negative values indicate loss
var dNBR_2022_2024 = nbr2022.subtract(nbr2024).rename('dNBR_2022_2024');
var dNBR_2024_2026 = nbr2024.subtract(nbr2026).rename('dNBR_2024_2026');
var dNBR_2022_2026 = nbr2022.subtract(nbr2026).rename('dNBR_2022_2026');

var dNDVI_2022_2026 = ndvi2022.subtract(ndvi2026).rename('dNDVI_2022_2026');

// Classify dNBR 2022-2026 into disturbance severity classes
// Positive dNBR = NBR has decreased = disturbance or loss
// Negative dNBR = NBR has increased = recovery or gain
var classified = dNBR_2022_2026
  .where(dNBR_2022_2026.lt(-0.1), 1)                           // Gain / recovery
  .where(dNBR_2022_2026.gte(-0.1).and(dNBR_2022_2026.lt(0.1)), 2)  // Stable
  .where(dNBR_2022_2026.gte(0.1).and(dNBR_2022_2026.lt(0.3)), 3)   // Moderate loss
  .where(dNBR_2022_2026.gte(0.3), 4);                          // High loss

// Visualisation parameters
var dNBRvis = {
  min: -0.4, max: 0.4,
  palette: ['1a9641', 'a6d96a', 'ffffbf', 'fdae61', 'd7191c']
};

var classVis = {
  min: 1, max: 4,
  palette: ['1a9641', 'ffffbf', 'fdae61', 'd7191c']
};

var boundaryVis = {color: 'FFFFFF', fillColor: '00000000'};

// RGB for reference
var rgbVis = {bands: ['B4', 'B3', 'B2'], min: 0, max: 0.3};

// Centre map
Map.centerObject(boundary, 10);

// Add RGB composites for reference
Map.addLayer(composite2022, rgbVis, 'RGB 2022', false);
Map.addLayer(composite2026, rgbVis, 'RGB 2026', false);

// Add continuous dNBR layers
Map.addLayer(dNBR_2022_2024, dNBRvis, 'dNBR 2022-2024', false);
Map.addLayer(dNBR_2024_2026, dNBRvis, 'dNBR 2024-2026', false);
Map.addLayer(dNBR_2022_2026, dNBRvis, 'dNBR 2022-2026');

// Add dNDVI for comparison
Map.addLayer(dNDVI_2022_2026, dNBRvis, 'dNDVI 2022-2026', false);

// Add classified disturbance layer
Map.addLayer(classified, classVis, 'Disturbance Class 2022-2026', false);

// Add boundary on top
Map.addLayer(preyLang, boundaryVis, 'Prey Lang Boundary');

// Print change statistics to console
print('dNBR 2022-2026 stats:', dNBR_2022_2026.reduceRegion({
  reducer: ee.Reducer.mean().combine(ee.Reducer.min(), '', true)
            .combine(ee.Reducer.max(), '', true)
            .combine(ee.Reducer.stdDev(), '', true),
  geometry: boundary,
  scale: 20,
  maxPixels: 1e9
}));

// Calculate area of each disturbance class in square kilometres
var classAreas = ee.Image.pixelArea().divide(1e6).addBands(classified)
  .reduceRegion({
    reducer: ee.Reducer.sum().group({
      groupField: 1,
      groupName: 'class'
    }),
    geometry: boundary,
    scale: 20,
    maxPixels: 1e9
  });

print('Area per disturbance class (km2):', classAreas);