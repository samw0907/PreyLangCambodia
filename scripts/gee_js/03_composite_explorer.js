// 03_composite_explorer
// Build median composites for 2022, 2024 and 2026 dry season windows
// and display RGB and false colour visualisations with boundary overlay

// Load Prey Lang boundary
var preyLang = ee.FeatureCollection('projects/preylangcambodia/assets/prey_lang_boundary');
var boundary = preyLang.geometry();

// Cloud masking function using QA60 band
// Bits 10 and 11 are opaque cloud and cirrus cloud respectively
function maskS2clouds(image) {
  var qa = image.select('QA60');
  var cloudBitMask = 1 << 10;
  var cirrusBitMask = 1 << 11;
  var mask = qa.bitwiseAnd(cloudBitMask).eq(0)
               .and(qa.bitwiseAnd(cirrusBitMask).eq(0));
  return image.updateMask(mask).divide(10000);
}

// Function to build a median composite for a given date window
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

// Print band names to confirm structure
print('2022 composite bands:', composite2022.bandNames());

// Visualisation parameters
var rgbVis = {bands: ['B4', 'B3', 'B2'], min: 0, max: 0.3};
var falseColourVis = {bands: ['B8', 'B4', 'B3'], min: 0, max: 0.4};
var boundaryVis = {color: 'FFFFFF', fillColor: '00000000'};

// Display on map - centre on boundary
Map.centerObject(boundary, 10);

// Add RGB composites
Map.addLayer(composite2022, rgbVis, 'RGB 2022');
Map.addLayer(composite2024, rgbVis, 'RGB 2024');
Map.addLayer(composite2026, rgbVis, 'RGB 2026');

// Add false colour composites
Map.addLayer(composite2022, falseColourVis, 'False Colour 2022', false);
Map.addLayer(composite2024, falseColourVis, 'False Colour 2024', false);
Map.addLayer(composite2026, falseColourVis, 'False Colour 2026', false);

// Add boundary outline on top
Map.addLayer(preyLang, boundaryVis, 'Prey Lang Boundary');

// Print scene counts per window to console
var count2022 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(boundary)
  .filterDate('2022-01-01', '2022-02-28')
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
  .size();
var count2024 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(boundary)
  .filterDate('2024-01-01', '2024-02-28')
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
  .size();
var count2026 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(boundary)
  .filterDate('2026-01-01', '2026-02-28')
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
  .size();

print('Scenes available 2022:', count2022);
print('Scenes available 2024:', count2024);
print('Scenes available 2026:', count2026);