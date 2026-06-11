// 04_index_calculations
// Calculate NDVI, EVI, NBR, NDRE and NDMI for each temporal composite
// and visualise with appropriate colour ramps

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

// Build the three composites
var composite2022 = buildComposite('2022-01-01', '2022-02-28');
var composite2024 = buildComposite('2024-01-01', '2024-02-28');
var composite2026 = buildComposite('2026-01-01', '2026-02-28');

// Index calculation functions
function calcNDVI(image) {
  return image.normalizedDifference(['B8', 'B4']).rename('NDVI');
}

function calcEVI(image) {
  return image.expression(
    '2.5 * ((B8 - B4) / (B8 + 6 * B4 - 7.5 * B2 + 1))', {
      'B8': image.select('B8'),
      'B4': image.select('B4'),
      'B2': image.select('B2')
    }).rename('EVI');
}

function calcNBR(image) {
  return image.normalizedDifference(['B8', 'B12']).rename('NBR');
}

function calcNDRE(image) {
  return image.normalizedDifference(['B8', 'B5']).rename('NDRE');
}

function calcNDMI(image) {
  return image.normalizedDifference(['B8', 'B11']).rename('NDMI');
}

// Calculate all indices for each composite
var ndvi2022 = calcNDVI(composite2022);
var ndvi2024 = calcNDVI(composite2024);
var ndvi2026 = calcNDVI(composite2026);

var evi2022 = calcEVI(composite2022);
var evi2024 = calcEVI(composite2024);
var evi2026 = calcEVI(composite2026);

var nbr2022 = calcNBR(composite2022);
var nbr2024 = calcNBR(composite2024);
var nbr2026 = calcNBR(composite2026);

var ndre2022 = calcNDRE(composite2022);
var ndre2024 = calcNDRE(composite2024);
var ndre2026 = calcNDRE(composite2026);

var ndmi2022 = calcNDMI(composite2022);
var ndmi2024 = calcNDMI(composite2024);
var ndmi2026 = calcNDMI(composite2026);

// Visualisation parameters
// Vegetation indices - red to green
var vegVis = {min: 0, max: 1, palette: ['red', 'yellow', 'green']};
// NBR - diverging to highlight disturbance
var nbrVis = {min: -0.5, max: 0.8, palette: ['red', 'yellow', 'green']};
// Boundary outline
var boundaryVis = {color: 'FFFFFF', fillColor: '00000000'};

// Centre map on boundary
Map.centerObject(boundary, 10);

// Add NDVI layers
Map.addLayer(ndvi2022, vegVis, 'NDVI 2022');
Map.addLayer(ndvi2024, vegVis, 'NDVI 2024', false);
Map.addLayer(ndvi2026, vegVis, 'NDVI 2026', false);

// Add EVI layers
Map.addLayer(evi2022, vegVis, 'EVI 2022', false);
Map.addLayer(evi2024, vegVis, 'EVI 2024', false);
Map.addLayer(evi2026, vegVis, 'EVI 2026', false);

// Add NBR layers
Map.addLayer(nbr2022, nbrVis, 'NBR 2022', false);
Map.addLayer(nbr2024, nbrVis, 'NBR 2024', false);
Map.addLayer(nbr2026, nbrVis, 'NBR 2026', false);

// Add NDRE layers
Map.addLayer(ndre2022, vegVis, 'NDRE 2022', false);
Map.addLayer(ndre2024, vegVis, 'NDRE 2024', false);
Map.addLayer(ndre2026, vegVis, 'NDRE 2026', false);

// Add NDMI layers
Map.addLayer(ndmi2022, vegVis, 'NDMI 2022', false);
Map.addLayer(ndmi2024, vegVis, 'NDMI 2024', false);
Map.addLayer(ndmi2026, vegVis, 'NDMI 2026', false);

// Add boundary outline on top
Map.addLayer(preyLang, boundaryVis, 'Prey Lang Boundary');

// Print sample statistics to console to confirm index ranges look sensible
print('NDVI 2022 stats:', ndvi2022.reduceRegion({
  reducer: ee.Reducer.mean().combine(ee.Reducer.min(), '', true)
            .combine(ee.Reducer.max(), '', true),
  geometry: boundary,
  scale: 20,
  maxPixels: 1e9
}));

print('NBR 2022 stats:', nbr2022.reduceRegion({
  reducer: ee.Reducer.mean().combine(ee.Reducer.min(), '', true)
            .combine(ee.Reducer.max(), '', true),
  geometry: boundary,
  scale: 20,
  maxPixels: 1e9
}));