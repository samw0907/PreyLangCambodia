// 02_boundary_check
// Load Prey Lang boundary asset and display on map to confirm correct position

// Load the boundary asset
var preyLang = ee.FeatureCollection('projects/preylangcambodia/assets/prey_lang_boundary');

// Print properties to console to inspect the data
print('Boundary features:', preyLang);

// Display boundary on map
Map.centerObject(preyLang, 9);
Map.addLayer(preyLang, {color: 'FF0000'}, 'Prey Lang Boundary');