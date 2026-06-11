// Orientation test - centre map on Prey Lang, Cambodia
// and confirm Sentinel-2 access

// Define a point at the centre of Prey Lang Wildlife Sanctuary
var preyLang = ee.Geometry.Point([105.5, 13.0]);

// Load Sentinel-2 collection, filter to Jan 2026, low cloud cover
var collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(preyLang)
  .filterDate('2026-01-01', '2026-02-28')
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20));

// Print number of scenes found to Console
print('Number of scenes found:', collection.size());

// Load the least cloudy single scene for visual check
var image = collection.sort('CLOUDY_PIXEL_PERCENTAGE').first();
print('Least cloudy scene date:', image.date());

// Display RGB composite on map
Map.centerObject(preyLang, 9);
Map.addLayer(image, {bands: ['B4', 'B3', 'B2'], min: 0, max: 3000}, 'RGB Jan 2026');