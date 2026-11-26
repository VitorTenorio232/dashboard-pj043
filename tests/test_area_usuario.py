"""Área de interesse enviada pelo usuário: formatos, projeções e arquivos maliciosos (sem GEE)."""
from __future__ import annotations

from io import BytesIO
import json
import math
import os
import sqlite3
import struct
import tempfile
import zipfile

import folium
import pytest
import shapefile
import shapely
import streamlit as st
from pyproj import CRS, Transformer
from pyproj.enums import WktVersion
from shapely.geometry import Polygon, mapping, shape
from streamlit.testing.v1 import AppTest

import modules.auth_gee as auth_gee
import modules.maps as maps
import modules.ui as ui
from modules.regions import USER_AREA_REGION, map_center, normalize_bounds, region_display_name
from modules.user_area import (
    MAX_OUTPUT_VERTICES, UserArea, UserAreaError, load_user_area, safe_display_name,
)

# Quadrado de ~0,1° perto de Itajubá com um buraco no meio.
OUTER = [(-45.50, -22.50), (-45.40, -22.50), (-45.40, -22.40), (-45.50, -22.40), (-45.50, -22.50)]
HOLE = [(-45.46, -22.46), (-45.44, -22.46), (-45.44, -22.44), (-45.46, -22.44), (-45.46, -22.46)]
REFERENCE = Polygon(OUTER, [HOLE])


@pytest.fixture(autouse=True)
def _limpa_cache():
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def _zip(members: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _geojson(geometry=REFERENCE, **extra) -> bytes:
    doc = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": mapping(geometry)}]}
    doc.update(extra)
    return json.dumps(doc).encode()


def _kml(rings=(OUTER, HOLE)) -> bytes:
    def coords(ring):
        return " ".join(f"{x},{y},0" for x, y in ring)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
  <NetworkLink><Link><href>http://169.254.169.254/latest/meta-data</href></Link></NetworkLink>
  <Placemark><name>ponto</name><Point><coordinates>-45.45,-22.45,0</coordinates></Point></Placemark>
  <Placemark><name>área</name><Polygon>
    <outerBoundaryIs><LinearRing><coordinates>{coords(rings[0])}</coordinates></LinearRing></outerBoundaryIs>
    <innerBoundaryIs><LinearRing><coordinates>{coords(rings[1])}</coordinates></LinearRing></innerBoundaryIs>
  </Polygon></Placemark>
</Document></kml>""".encode()


def _shapefile(geometry=REFERENCE, epsg: int | None = 31983, with_prj: bool = True) -> dict[str, bytes]:
    if epsg and epsg != 4326:
        tr = Transformer.from_crs(4326, epsg, always_xy=True)
        geometry = shapely.transform(geometry, lambda c: __import__("numpy").column_stack(tr.transform(c[:, 0], c[:, 1])))
    shp, shx, dbf = BytesIO(), BytesIO(), BytesIO()
    writer = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON)
    writer.field("nome", "C")
    geometry = shapely.orient_polygons(geometry, exterior_cw=True)  # regra do shapefile: exterior horário
    writer.poly([list(geometry.exterior.coords), list(geometry.interiors[0].coords)])
    writer.record("teste")
    writer.close()
    files = {"area.shp": shp.getvalue(), "area.shx": shx.getvalue(), "area.dbf": dbf.getvalue()}
    if with_prj:
        files["area.prj"] = CRS.from_epsg(epsg or 4326).to_wkt(WktVersion.WKT1_ESRI).encode()
    return files


def _gpkg(geometry=REFERENCE, epsg: int = 4674) -> bytes:
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "t.gpkg")
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE gpkg_spatial_ref_sys (srs_name TEXT, srs_id INTEGER PRIMARY KEY, organization TEXT,
                organization_coordsys_id INTEGER, definition TEXT, description TEXT);
            CREATE TABLE gpkg_contents (table_name TEXT PRIMARY KEY, data_type TEXT, identifier TEXT, srs_id INTEGER);
            CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, geometry_type_name TEXT,
                srs_id INTEGER, z INTEGER, m INTEGER);
            CREATE TABLE "minha área" (fid INTEGER PRIMARY KEY, geom BLOB);
        """)
        conn.execute("INSERT INTO gpkg_spatial_ref_sys VALUES ('SIRGAS 2000', ?, 'EPSG', ?, 'x', '')", (epsg, epsg))
        conn.execute("INSERT INTO gpkg_contents VALUES ('minha área', 'features', 'a', ?)", (epsg,))
        conn.execute("INSERT INTO gpkg_geometry_columns VALUES ('minha área', 'geom', 'POLYGON', ?, 0, 0)", (epsg,))
        blob = b"GP" + bytes([0, 0b00000001]) + struct.pack("<i", epsg) + shapely.to_wkb(geometry, byte_order=1)
        conn.execute('INSERT INTO "minha área" (geom) VALUES (?)', (blob,))
        conn.commit()
        conn.close()
        with open(path, "rb") as handle:
            return handle.read()


def _confere(area: UserArea, fmt: str, tol: float = 1e-6):
    geom = shape(json.loads(area.geojson))
    assert area.source_format == fmt
    assert geom.symmetric_difference(REFERENCE).area < tol, area.source_crs
    assert len(geom.interiors if geom.geom_type == "Polygon" else []) == 1  # buraco preservado
    assert area.area_km2 == pytest.approx(109.3, rel=0.01)  # 11,07 km × 10,29 km − buraco de 4,55 km²


# ------------------------------------------------------------------------------------- formatos
def test_geojson():
    _confere(load_user_area((("área.geojson", _geojson()),)), "GeoJSON")


def test_kml_ignora_pontos_e_networklink():
    area = load_user_area((("fazenda.kml", _kml()),))
    _confere(area, "KML")
    assert area.n_features == 1 and area.source_crs == "EPSG:4326"


def test_kmz():
    data = _zip({"doc.kml": _kml(), "files/icone.png": b"\x89PNG"})
    _confere(load_user_area((("fazenda.kmz", data),)), "KMZ")


def test_shapefile_zip_em_utm_sirgas_reprojetado():
    area = load_user_area((("talhao.zip", _zip(_shapefile(epsg=31983))),))
    _confere(area, "Shapefile", tol=1e-7)
    assert "EPSG:31983" in area.source_crs


def test_shapefile_em_arquivos_soltos():
    files = tuple(_shapefile(epsg=31983).items())
    _confere(load_user_area(files), "Shapefile", tol=1e-7)


def test_shapefile_sem_prj_em_graus_avisa():
    area = load_user_area(tuple(_shapefile(epsg=4326, with_prj=False).items()))
    assert any(".prj" in w for w in area.warnings)


def test_shapefile_sem_prj_em_utm_e_recusado():
    with pytest.raises(UserAreaError, match="prj"):
        load_user_area(tuple(_shapefile(epsg=31983, with_prj=False).items()))


def test_geopackage_sirgas():
    area = load_user_area((("limite.gpkg", _gpkg()),))
    _confere(area, "GeoPackage", tol=1e-7)
    assert area.source_crs.startswith("EPSG:4674")


def test_geojson_antigo_com_crs_projetado():
    tr = Transformer.from_crs(4326, 31983, always_xy=True)
    utm = shapely.transform(REFERENCE, lambda c: __import__("numpy").column_stack(tr.transform(c[:, 0], c[:, 1])))
    data = _geojson(utm, crs={"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::31983"}})
    _confere(load_user_area((("utm.geojson", data),)), "GeoJSON", tol=1e-7)


def test_varias_feicoes_viram_uma_area():
    a = Polygon([(-45.5, -22.5), (-45.45, -22.5), (-45.45, -22.45), (-45.5, -22.45)])
    b = Polygon([(-45.3, -22.5), (-45.25, -22.5), (-45.25, -22.45), (-45.3, -22.45)])
    doc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {}, "geometry": mapping(g)} for g in (a, b)]}
    area = load_user_area((("dois.geojson", json.dumps(doc).encode()),))
    assert area.n_features == 2 and shape(json.loads(area.geojson)).geom_type == "MultiPolygon"


def test_poligono_auto_intersectado_e_corrigido():
    bowtie = Polygon([(-45.5, -22.5), (-45.4, -22.4), (-45.4, -22.5), (-45.5, -22.4), (-45.5, -22.5)])
    area = load_user_area((("laco.geojson", _geojson(bowtie)),))
    assert shape(json.loads(area.geojson)).is_valid and area.area_km2 > 10


def test_contorno_muito_detalhado_e_simplificado():
    n = 60_000
    circle = Polygon([(-45.45 + 0.5 * math.cos(2 * math.pi * i / n), -22.45 + 0.5 * math.sin(2 * math.pi * i / n))
                      for i in range(n)])
    area = load_user_area((("circulo.geojson", _geojson(circle)),))
    assert area.n_vertices <= MAX_OUTPUT_VERTICES
    assert shape(json.loads(area.geojson)).area == pytest.approx(circle.area, rel=0.01)
    assert any("simplificado" in w for w in area.warnings)


# ------------------------------------------------------------------------------------- recusas e segurança
@pytest.mark.parametrize("name, data, message", [
    ("linha.geojson", _geojson(shapely.LineString(OUTER)), "não tem polígonos"),
    ("ruim.geojson", b"{nao e json", "JSON válido"),
    ("ruim.kml", b"<kml><Polygon>", "XML válido"),
    ("ruim.zip", b"PK\x03\x04lixo", "corrompido"),
    ("ruim.gpkg", b"SQLite format 3\x00" + b"\x00" * 100, "GeoPackage válido"),
    ("dados.csv", b"a,b\n1,2", "Formato não reconhecido"),
    ("fora.geojson", _geojson(Polygon([(500000, 7500000), (510000, 7500000), (510000, 7510000)])), "graus"),
])
def test_arquivos_invalidos_tem_mensagem_clara(name, data, message):
    with pytest.raises(UserAreaError, match=message):
        load_user_area(((name, data),))


def test_kml_com_entidades_xxe_e_billion_laughs_e_recusado():
    xxe = b"""<?xml version="1.0"?><!DOCTYPE kml [<!ENTITY x SYSTEM "file:///etc/passwd">]>
<kml><Placemark><name>&x;</name></Placemark></kml>"""
    laughs = b"""<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]><kml>&c;</kml>"""
    for data in (xxe, laughs):
        with pytest.raises(UserAreaError, match="DTD"):
            load_user_area((("x.kml", data),))


def test_zip_bomb_e_recusado():
    bomb = _zip({"area.geojson": b" " * (70 * 1024 * 1024)})
    assert len(bomb) < 200_000  # ~70 MB descompactados num zip pequeno
    with pytest.raises(UserAreaError, match="60 MB"):
        load_user_area((("bomba.zip", bomb),))


def test_envio_acima_do_limite_e_recusado():
    with pytest.raises(UserAreaError, match="20 MB"):
        load_user_area((("grande.geojson", b" " * (21 * 1024 * 1024)),))


def test_zip_com_muitos_membros_e_recusado():
    with pytest.raises(UserAreaError, match="mais de 50"):
        load_user_area((("muitos.zip", _zip({f"f{i}.txt": b"x" for i in range(60)})),))


def test_nome_com_caminho_no_zip_nao_escreve_no_disco(tmp_path):
    alvo = tmp_path / "evil.kml"
    data = _zip({f"../../../../{alvo}": _kml()})
    area = load_user_area((("trav.kmz", data),))
    assert area.source_format == "KMZ" and not alvo.exists()


def test_nome_exibido_e_sanitizado():
    nome = safe_display_name("../[clique](javascript:alert(1)) **Fazenda São João**.kml")
    assert nome == "clique_javascript_alert_1_Fazenda São João"
    assert not set("[]()*<>/\\`") & set(nome)


def test_area_e_hashavel_e_entra_na_chave():
    a = load_user_area((("a.geojson", _geojson()),))
    b = load_user_area((("a.geojson", _geojson()),))
    assert a == b and hash(a) == hash(b)
    assert normalize_bounds(a) is a and normalize_bounds([1, 2, 3, 4]) == (1.0, 2.0, 3.0, 4.0)
    key = maps.region_key(USER_AREA_REGION, a)
    assert key[1] is a and maps.region_key(USER_AREA_REGION, a) == key
    assert region_display_name(USER_AREA_REGION, area=a) == "Arquivo: a"
    center, zoom = map_center(USER_AREA_REGION, a)
    assert center == pytest.approx([-22.45, -45.45]) and 9 <= zoom <= 12


# ------------------------------------------------------------------------------------- página
def test_pagina_de_mapas_com_arquivo_enviado(monkeypatch):
    monkeypatch.setattr(auth_gee, "initialize_gee", lambda: True)
    monkeypatch.setattr(ui, "latest_available_timestamp", lambda name: None)
    monkeypatch.setattr(maps, "cached_image_count", lambda *a, **k: 3)
    monkeypatch.setattr(maps, "cached_summary", lambda *a, **k: {"headline": "ok", "details": []})
    monkeypatch.setattr(maps, "_display_image_and_vis", lambda p, image, region: (image, dict(maps.PRODUCTS[p].vis)))
    chamadas = []

    def fake_make_map(product_name, start, end, region_name, bounds=None, **kwargs):
        chamadas.append((region_name, bounds))
        center, zoom = map_center(region_name, bounds)
        return folium.Map(location=center, zoom_start=zoom), "img", "reg"

    monkeypatch.setattr(maps, "make_map", fake_make_map)
    at = AppTest.from_file(os.path.abspath("app.py"), default_timeout=60)
    at.switch_page("pages/1_🗺️_Mapas_Interativos.py").run()
    at.selectbox(key="map_region").set_value(USER_AREA_REGION).run()
    assert any("Envie o arquivo" in i.value for i in at.info)

    uploader = at.get("file_uploader")[0]
    uploader.set_value([("talhao.zip", _zip(_shapefile()), "application/zip")]).run()
    assert not at.exception and not at.error
    assert any("Shapefile" in c.value and "EPSG:31983" in c.value for c in at.caption)
    next(b for b in at.button if b.label == "Gerar mapa").click().run()
    result = at.session_state["vigia_map_result"]
    assert result["region_label"] == "Arquivo: talhao"
    assert isinstance(chamadas[-1][1], UserArea)
    assert result["map"].location == pytest.approx([-22.45, -45.45])

    at.get("file_uploader")[0].set_value([("ruim.kml", b"<kml><Polygon>", "application/xml")]).run()
    assert not at.exception and any("XML válido" in e.value for e in at.error)


def test_dois_arquivos_de_area_sao_recusados_em_vez_de_usar_o_primeiro():
    # Encontrado no navegador: o segundo KML enviado era ignorado sem aviso.
    with pytest.raises(UserAreaError, match="mais de um arquivo de área"):
        load_user_area((("a.kml", _kml()), ("b.kml", _kml())))
    with pytest.raises(UserAreaError, match="mais de um arquivo de área"):
        load_user_area((("a.geojson", _geojson()), ("b.zip", _zip(_shapefile())),))
    # KMZ com KMLs anexos continua valendo (só o doc.kml conta).
    data = _zip({"doc.kml": _kml(), "files/outro.kml": b"<kml/>"})
    assert load_user_area((("fazenda.kmz", data),)).source_format == "KMZ"
