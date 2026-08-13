# Catálogo técnico dos produtos do SIMQA

A data final informada na interface é tratada como **inclusiva**. Produtos estáticos não exibem campos de data. Para coleções temporais ativas, o SIMQA consulta a última cena disponível diretamente no Google Earth Engine e limita automaticamente o calendário.

## FIRMS / MODIS

| Produto | Disponibilidade | Resolução/escala | Cálculo no mapa |
|---|---:|---:|---|
| Focos de calor — FIRMS MODIS | 2000-11-01 – presente | 1000 m | Para cada imagem diária, são mantidos pixels com confiança MODIS ≥ 30%. Cada detecção válida recebe valor 1 e os valores são somados no período. |


## FIRMS / VIIRS NOAA-20

| Produto | Disponibilidade | Resolução/escala | Cálculo no mapa |
|---|---:|---:|---|
| Focos de calor — VIIRS NOAA-20 | 2023-10-08 – presente | 375 m | São mantidos apenas pixels de confiança nominal ou alta (confidence ≥ 1). Cada detecção válida recebe valor 1 e é somada no período. |


## FIRMS / VIIRS S-NPP

| Produto | Disponibilidade | Resolução/escala | Cálculo no mapa |
|---|---:|---:|---|
| Focos de calor — VIIRS S-NPP | 2023-09-03 – presente | 375 m | São mantidos pixels de confiança nominal ou alta (confidence ≥ 1), convertidos para 1 e somados no período. |


## NOAA / GOES-16

| Produto | Disponibilidade | Resolução/escala | Cálculo no mapa |
|---|---:|---:|---|
| Focos de calor — GOES-16 ABI FDCF | 2017-05-24 – 2025-04-07 | 2000 m | Usa somente as classes mais conservadoras do Mask: 10, 11, 30 e 31 (fogo processado ou saturado, com e sem filtro temporal). |


## NOAA / GOES-19

| Produto | Disponibilidade | Resolução/escala | Cálculo no mapa |
|---|---:|---:|---|
| Focos de calor — GOES-19 ABI FDCF | 2025-04-07 – presente | 2000 m | Usa somente as classes conservadoras do Mask: 10, 11, 30 e 31 e soma as detecções das varreduras de 10 minutos. |


## MODIS / NASA

| Produto | Disponibilidade | Resolução/escala | Cálculo no mapa |
|---|---:|---:|---|
| AOD 0,55 µm — MODIS MAIAC MCD19A2.061 | 2000-02-24 – presente | 1000 m | Aplica fator de escala 0,001 à banda Optical_Depth_055 e mantém apenas pixels com QA de AOD igual a 0 (melhor qualidade; bits 8–11 do AOD_QA). Depois calcula a média no período. |
| Temperatura da superfície — MODIS Terra | 2000-02-18 – presente | 1000 m | Calcula a média temporal, aplica escala 0,02 K e converte de Kelvin para °C. |


## Sentinel-5P NRTI

| Produto | Disponibilidade | Resolução/escala | Cálculo no mapa |
|---|---:|---:|---|
| Índice UV de aerossóis — Sentinel-5P NRTI | 2018-07-10 – presente | 1113 m | Calcula a média do absorbing_aerosol_index no período. |
| Fração de nuvens — Sentinel-5P NRTI | 2018-07-05 – presente | 1113 m | Calcula a média da banda cloud_fraction no período. |
| Monóxido de carbono — Sentinel-5P NRTI | 2018-11-22 – presente | 1113 m | Calcula a média da banda CO_column_number_density no período. |
| Formaldeído — Sentinel-5P NRTI | 2018-10-02 – presente | 1113 m | Calcula a média da coluna troposférica de HCHO no período. |
| Dióxido de nitrogênio troposférico — Sentinel-5P NRTI | 2018-07-10 – presente | 1113 m | Calcula a média da banda tropospheric_NO2_column_number_density no período. |
| Ozônio total — Sentinel-5P NRTI | 2018-07-10 – presente | 1113 m | Calcula a média da banda O3_column_number_density no período. |
| Dióxido de enxofre — Sentinel-5P NRTI | 2018-07-10 – presente | 1113 m | Calcula a média da banda SO2_column_number_density no período. |


## Sentinel-5P OFFL

| Produto | Disponibilidade | Resolução/escala | Cálculo no mapa |
|---|---:|---:|---|
| Índice de aerossóis absorventes — Sentinel-5P OFFL | 2018-07-04 – presente | 1113 m | Calcula a média das imagens OFFL no período. |
| Monóxido de carbono — Sentinel-5P OFFL | 2018-06-28 – presente | 7000 m | Calcula a média temporal e multiplica por 2241,15 para converter mol/m² em DU. |
| Metano — Sentinel-5P OFFL | 2019-02-08 – presente | 7000 m | Calcula a média das imagens no período. |


## CHIRPS v3 / UCSB-CHC

| Produto | Disponibilidade | Resolução/escala | Cálculo no mapa |
|---|---:|---:|---|
| Precipitação acumulada — CHIRPS v3 Daily Reanalysis | 1981-01-01 – última cena detectada automaticamente | 5566 m | Soma os campos diários em mm/dia em cada pixel. Nas séries regionais, calcula a média espacial do acumulado, preservando a unidade em milímetros. |

O produto utilizado é `UCSB-CHC/CHIRPS/V3/DAILY_RNL`. A data máxima não é fixada no código: ela é consultada no Earth Engine e apresentada na interface.

## Copernicus / ERA5-Land

| Produto | Disponibilidade | Resolução/escala | Cálculo no mapa |
|---|---:|---:|---|
| Precipitação acumulada — ERA5-Land Hourly | 1950-01-01 – última cena detectada automaticamente | 11132 m | Usa `total_precipitation_hourly`, já desagregada em valores horários no Earth Engine. Cada cena é convertida de metros para milímetros (`m × 1000`) e as horas do período são somadas. Nas séries regionais, calcula a média espacial do acumulado. |

O produto utilizado é `ECMWF/ERA5_LAND/HOURLY`. A data máxima não é fixada no código: ela é consultada diretamente no Earth Engine. Como a coleção é horária, a interface também mostra o horário UTC da última cena e avisa quando o último dia pode estar incompleto. O ERA5-Land é uma **reanálise**, e não uma medição direta de precipitação.


## Sentinel-2

| Produto | Disponibilidade | Resolução/escala | Cálculo no mapa |
|---|---:|---:|---|
| NDVI — Sentinel-2 SR Harmonized | 2017-03-28 – presente | 10 m | NDVI = (B8 − B4) / (B8 + B4); filtra cenas com CLOUDY_PIXEL_PERCENTAGE ≤ 40 e calcula a média. |


## SRTM

| Produto | Disponibilidade | Resolução/escala | Cálculo no mapa |
|---|---:|---:|---|
| Relevo / Elevação — SRTM | Estático | 30 m | Seleciona a banda elevation e recorta a região escolhida. |


## Copernicus Land

| Produto | Disponibilidade | Resolução/escala | Cálculo no mapa |
|---|---:|---:|---|
| Cobertura do solo — Copernicus CGLS 100 m | 2015-01-01 – 2019-12-31 | 100 m | Seleciona a imagem anual mais recente dentro do período e usa a banda de classe discreta. |


## CSP gHM

| Produto | Disponibilidade | Resolução/escala | Cálculo no mapa |
|---|---:|---:|---|
| Modificação Humana Global — gHM | Estático | 1000 m | Mosaica a coleção gHM e recorta a região selecionada. |


## Critério adotado para focos de calor

- **FIRMS MODIS:** pixels com `confidence >= 30`; cada detecção válida recebe 1 e é somada no período.
- **VIIRS NOAA-20 e S-NPP:** pixels de confiança nominal ou alta (`confidence >= 1`); cada detecção válida recebe 1.
- **GOES-16 e GOES-19:** classes conservadoras `Mask` 10, 11, 30 e 31; soma por varredura de 10 minutos.

Esses resultados representam detecções rasterizadas. Eles não são uma contagem de incêndios únicos.

## Precipitação nas séries

Para o **CHIRPS v3**, o mapa soma a precipitação diária em cada pixel. Para o **ERA5-Land Hourly**, cada valor horário de `total_precipitation_hourly` é convertido de metros para milímetros (`m × 1000`) antes da soma temporal. Em ambos os casos, a série regional calcula a **média espacial do acumulado**, mantendo a unidade em milímetros; não soma milímetros entre pixels.