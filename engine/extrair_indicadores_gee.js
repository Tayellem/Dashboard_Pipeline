// ============================================================
// Indicadores ambientais no entorno das árvores (Earth Engine)
// - EVI com reflectância na escala 0–1
// - mesmo período (jan–set) nos três anos
// - camadas no mapa por indicador e por ano (as mesmas imagens da tabela)
// ============================================================

// Carrega o polígono
var poligonos = ee.FeatureCollection("projects/pipeline-tcc-511716/assets/engine");
var geom = poligonos.geometry();

// true = mascara nuvem/sombra por pixel (banda SCL); false = só filtro por cena
var USAR_MASCARA_SCL = false;

// Períodos analisados (mesmo recorte nos três anos)
var periodos = [
  {ano: '2024', ini: '2024-01-01', fim: '2024-09-30'},
  {ano: '2025', ini: '2025-01-01', fim: '2025-09-30'},
  {ano: '2026', ini: '2026-01-01', fim: '2026-09-30'}
];

// ---------- Funções de cálculo ----------
function addNDVI(img) {
  return img.addBands(img.normalizedDifference(['B8', 'B4']).rename('NDVI'));
}

function addEVI(img) {
  // O Sentinel-2 SR vem multiplicado por 10000: dividir para ficar em 0–1,
  // senão o termo "+ 1" da fórmula perde o efeito e o EVI infla.
  var s = img.select(['B2', 'B4', 'B8']).divide(10000);
  return img.addBands(s.expression(
    '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
    {'NIR': s.select('B8'), 'RED': s.select('B4'), 'BLUE': s.select('B2')}
  ).rename('EVI'));
}

function mascaraSCL(img) {
  var scl = img.select('SCL');   // 3 sombra, 8/9 nuvem, 10 cirrus, 11 neve
  var ok = scl.neq(3).and(scl.neq(8)).and(scl.neq(9))
              .and(scl.neq(10)).and(scl.neq(11));
  return img.updateMask(ok);
}

// Imagens de cada indicador para um período (usadas na tabela E no mapa)
function construirImagens(inicio, fim) {
  var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(poligonos).filterDate(inicio, fim)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20));
  if (USAR_MASCARA_SCL) { s2 = s2.map(mascaraSCL); }

  return {
    n: s2.size(),
    ndvi: s2.map(addNDVI).select('NDVI').mean(),
    evi: s2.map(addEVI).select('EVI').mean(),
    // Precipitação acumulada (CHIRPS)
    precip: ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
      .filterBounds(poligonos).filterDate(inicio, fim)
      .select('precipitation').sum(),
    // Temperatura de superfície diurna (MODIS Terra LST): K * 0.02 - 273.15
    temp: ee.ImageCollection('MODIS/061/MOD11A1')
      .filterBounds(poligonos).filterDate(inicio, fim)
      .select('LST_Day_1km').mean()
      .multiply(0.02).subtract(273.15).rename('Temp_C')
  };
}

function media(img, banda, escala) {
  return img.reduceRegion({
    reducer: ee.Reducer.mean(), geometry: geom, scale: escala, maxPixels: 1e9
  }).get(banda);
}

// ---------- Extração da média espacial no polígono ----------
var extrairDados = function(rotulo, inicio, fim) {
  var im = construirImagens(inicio, fim);
  return ee.Feature(null, {
    'Ano': rotulo,
    'NDVI_Medio': media(im.ndvi, 'NDVI', 10),
    'EVI_Medio': media(im.evi, 'EVI', 10),
    'Precipitacao_mm': media(im.precip, 'precipitation', 5500),
    'Temperatura_C': media(im.temp, 'Temp_C', 1000),
    'N_cenas_S2': im.n               // conferência: nº de cenas usadas
  });
};

// ---------- Tabela com o MESMO período (jan–set) nos três anos ----------
var tabelaFinal = ee.FeatureCollection(periodos.map(function(p) {
  return extrairDados(p.ano + ' (Jan-Set)', p.ini, p.fim);
}));

// ---------- Visualização no mapa ----------
Map.centerObject(poligonos, 14);
Map.addLayer(
  poligonos.style({color: 'red', fillColor: 'ff000022', width: 2}),
  {}, 'Polígono do entorno');

var palVeg = ['#d73027', '#fee08b', '#1a9850'];
var palChuva = ['#f7fbff', '#6baed6', '#08306b'];
var palTemp = ['#313695', '#74add1', '#fee090', '#f46d43', '#a50026'];

periodos.forEach(function(p) {
  var im = construirImagens(p.ini, p.fim);
  var mostrar = (p.ano === '2026');   // só o NDVI de 2026 vem ligado
  Map.addLayer(im.ndvi.clip(geom), {min: 0, max: 0.8, palette: palVeg},
    'NDVI ' + p.ano + ' (jan–set)', mostrar);
  Map.addLayer(im.evi.clip(geom), {min: 0, max: 0.6, palette: palVeg},
    'EVI ' + p.ano + ' (jan–set)', false);
  Map.addLayer(im.precip.clip(geom), {min: 1000, max: 3000, palette: palChuva},
    'Precipitação ' + p.ano + ' (mm, jan–set)', false);
  Map.addLayer(im.temp.clip(geom), {min: 25, max: 40, palette: palTemp},
    'Temperatura superfície ' + p.ano + ' (°C, jan–set)', false);
});

print('Tabela consolidada de indicadores ambientais:', tabelaFinal);
// ============================================================
// EXPORTAÇÃO DOS RASTERS PARA O DASHBOARD
// ============================================================

function exportarRaster(imagem, nome, escala) {
  Export.image.toDrive({
    image: imagem.clip(geom),
    description: nome,
    folder: 'TCC_GEE_Rasters',
    fileNamePrefix: nome,
    region: geom,
    scale: escala,
    crs: 'EPSG:4326',
    fileFormat: 'GeoTIFF',
    maxPixels: 1e9
  });
}

periodos.forEach(function(p) {

  var im = construirImagens(p.ini, p.fim);

  // NDVI e EVI - resolução Sentinel-2
  exportarRaster(
    im.ndvi,
    'NDVI_' + p.ano,
    10
  );

  exportarRaster(
    im.evi,
    'EVI_' + p.ano,
    10
  );

  // Precipitação - resolução CHIRPS
  exportarRaster(
    im.precip,
    'Precipitacao_' + p.ano,
    5500
  );

  // Temperatura - resolução MODIS
  exportarRaster(
    im.temp,
    'Temperatura_' + p.ano,
    1000
  );
});
// ---------- Exportação para o Google Drive ----------
Export.table.toDrive({
  collection: tabelaFinal,
  description: 'Indicadores_Ambientais_TCC',
  fileFormat: 'CSV'
});

print('Tarefa de exportação para CSV criada com sucesso!');
