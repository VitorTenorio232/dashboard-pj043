#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Área de interesse enviada pelo usuário: Shapefile, KML/KMZ, GeoJSON e GeoPackage.

Tudo é lido em memória e convertido para um polígono em WGS84 (EPSG:4326). Cuidados de segurança,
porque o arquivo vem de qualquer visitante:

- limite de tamanho do envio e do conteúdo descompactado (zip bomb), número de membros do zip e
  de vértices/feições antes de qualquer processamento pesado;
- nada é extraído para o disco com o nome original (evita path traversal); o GeoPackage vai para um
  arquivo temporário com nome aleatório, aberto só para leitura e apagado em seguida;
- KML é lido com defusedxml (sem DTD/entidades: bloqueia XXE e "billion laughs"); NetworkLink e
  outras referências externas são ignoradas, então o servidor nunca busca URLs vindas do arquivo;
- o nome exibido é reduzido a letras, números, espaço, ponto, hífen e sublinhado, porque aparece em
  textos Markdown, na prancha PNG e nos nomes de arquivo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import json
import math
import os
from pathlib import PurePosixPath
import re
import sqlite3
import tempfile
import zipfile

import numpy as np
import shapely
from shapely import wkb as shapely_wkb
from shapely.geometry import MultiPolygon, Polygon, mapping, shape

# ------------------------------------------------------------------------------------------ limites
MAX_UPLOAD_BYTES = 20 * 1024 * 1024          # soma dos arquivos enviados
MAX_UNCOMPRESSED_BYTES = 60 * 1024 * 1024    # soma do conteúdo dentro de zip/kmz
MAX_ZIP_MEMBERS = 50
MAX_INPUT_VERTICES = 2_000_000               # antes da simplificação (protege a CPU)
MAX_FEATURES = 20_000
MAX_OUTPUT_VERTICES = 5_000                  # cada consulta ao GEE carrega a geometria inteira
SOUTH_AMERICA_BBOX = (-93.0, -60.0, -30.0, 15.0)

ACCEPTED_EXTENSIONS = ["zip", "shp", "shx", "dbf", "prj", "cpg", "kml", "kmz", "geojson", "json", "gpkg"]
SHAPEFILE_PARTS = {".shp", ".shx", ".dbf", ".prj", ".cpg"}


class UserAreaError(ValueError):
    """Problema no arquivo que o usuário pode corrigir; a mensagem é exibida como está."""


@dataclass(frozen=True)
class UserArea:
    """Polígono pronto para o GEE. É imutável e comparável: entra direto na chave do cache."""

    name: str
    geojson: str                       # geometria (Polygon/MultiPolygon) em EPSG:4326
    bbox: tuple[float, float, float, float]
    area_km2: float
    n_features: int
    n_vertices: int
    source_format: str
    source_crs: str
    warnings: tuple[str, ...] = field(default=(), compare=False)

    @property
    def label(self) -> str:
        return f"Arquivo: {self.name}"

    def center_zoom(self) -> tuple[list[float], int]:
        lon_min, lat_min, lon_max, lat_max = self.bbox
        span = max(lon_max - lon_min, (lat_max - lat_min) * 1.5, 1e-4)
        zoom = int(max(2, min(14, math.floor(math.log2(360.0 / span)) + 1)))
        return [(lat_min + lat_max) / 2, (lon_min + lon_max) / 2], zoom


# ------------------------------------------------------------------------------------------ util
def safe_display_name(filename: str) -> str:
    stem = PurePosixPath(str(filename).replace("\\", "/")).name
    stem = re.sub(r"\.(zip|shp|shx|dbf|prj|cpg|kml|kmz|geojson|json|gpkg)$", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"[^\w .-]+", "_", stem, flags=re.UNICODE)
    stem = re.sub(r"[_\s]*_[_\s]*", "_", stem).strip(" ._-")
    return (stem or "area")[:60]


def _ext(name: str) -> str:
    return os.path.splitext(PurePosixPath(str(name).replace("\\", "/")).name)[1].lower()


def _read_zip(data: bytes, budget: list[int]) -> dict[str, bytes]:
    """Lê os membros de um zip em memória, com limites; devolve {nome_base: bytes}."""
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise UserAreaError("O arquivo .zip/.kmz está corrompido ou não é um zip.") from exc
    members = [info for info in archive.infolist() if not info.is_dir()]
    if len(members) > MAX_ZIP_MEMBERS:
        raise UserAreaError(f"O arquivo compactado tem mais de {MAX_ZIP_MEMBERS} arquivos.")
    out: dict[str, bytes] = {}
    for info in members:
        base = PurePosixPath(info.filename.replace("\\", "/")).name
        if not base or base.startswith(".") or "__MACOSX" in info.filename:
            continue
        if info.flag_bits & 0x1:
            raise UserAreaError("Arquivos compactados com senha não são aceitos.")
        if info.file_size > budget[0]:
            raise UserAreaError("O conteúdo descompactado passa do limite de 60 MB.")
        with archive.open(info) as handle:
            content = handle.read(budget[0] + 1)   # não confia só no tamanho declarado no cabeçalho
        if len(content) > budget[0]:
            raise UserAreaError("O conteúdo descompactado passa do limite de 60 MB.")
        budget[0] -= len(content)
        out[base] = content
    return out


class _VertexBudget:
    def __init__(self) -> None:
        self.vertices = 0
        self.features = 0

    def add(self, geom) -> None:
        self.features += 1
        self.vertices += int(shapely.get_num_coordinates(geom))
        if self.features > MAX_FEATURES:
            raise UserAreaError(f"O arquivo tem mais de {MAX_FEATURES:,} feições.".replace(",", "."))
        if self.vertices > MAX_INPUT_VERTICES:
            raise UserAreaError("O arquivo tem vértices demais (mais de 2 milhões). Simplifique a área antes de enviar.")


# ------------------------------------------------------------------------------------------ leitores
def _parse_geojson(data: bytes, budget: _VertexBudget) -> tuple[list, str | None]:
    try:
        doc = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UserAreaError("O GeoJSON não é um JSON válido.") from exc
    if not isinstance(doc, dict):
        raise UserAreaError("O GeoJSON precisa ser um objeto (FeatureCollection, Feature ou geometria).")
    crs = None
    crs_member = doc.get("crs")
    if isinstance(crs_member, dict):  # GeoJSON antigo (2008); o RFC 7946 é sempre WGS84
        crs = (crs_member.get("properties") or {}).get("name")
    kind = doc.get("type")
    if kind == "FeatureCollection":
        raw = [f.get("geometry") for f in doc.get("features") or [] if isinstance(f, dict)]
    elif kind == "Feature":
        raw = [doc.get("geometry")]
    else:
        raw = [doc]
    geoms = []
    for item in raw:
        if not item:
            continue
        try:
            geom = shape(item)
        except Exception as exc:
            raise UserAreaError("O GeoJSON tem uma geometria inválida.") from exc
        budget.add(geom)
        geoms.append(geom)
    return geoms, crs


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _kml_ring(element) -> list[tuple[float, float]]:
    coords_el = next((c for c in element.iter() if _local(c.tag) == "coordinates"), None)
    points = []
    for token in (coords_el.text or "").split() if coords_el is not None else []:
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                points.append((float(parts[0]), float(parts[1])))
            except ValueError as exc:
                raise UserAreaError("O KML tem coordenadas inválidas.") from exc
    return points


def _parse_kml(data: bytes, budget: _VertexBudget) -> list:
    from defusedxml import ElementTree as SafeET
    from defusedxml.common import DefusedXmlException

    try:
        root = SafeET.fromstring(data, forbid_dtd=True)
    except DefusedXmlException as exc:
        raise UserAreaError("O KML contém DTD/entidades, que não são aceitos por segurança.") from exc
    except SafeET.ParseError as exc:
        raise UserAreaError("O KML não é um XML válido.") from exc
    geoms = []
    for polygon in (el for el in root.iter() if _local(el.tag) == "Polygon"):
        outer, holes = None, []
        for child in polygon:
            name = _local(child.tag)
            if name == "outerBoundaryIs":
                outer = _kml_ring(child)
            elif name == "innerBoundaryIs":
                holes.append(_kml_ring(child))
        if outer and len(outer) >= 3:
            geom = Polygon(outer, [h for h in holes if len(h) >= 3])
            budget.add(geom)
            geoms.append(geom)
    return geoms


def _parse_shapefile(parts: dict[str, bytes], budget: _VertexBudget) -> tuple[list, str | None]:
    import shapefile  # pyshp

    stems = {os.path.splitext(name)[0] for name in parts if _ext(name) == ".shp"}
    if not stems:
        raise UserAreaError("Envie o .shp junto com o .shx e o .prj (ou um .zip com todos eles).")
    if len(stems) > 1:
        raise UserAreaError("Envie um shapefile por vez (foram encontrados vários .shp).")
    stem = stems.pop()
    by_ext = {_ext(name): content for name, content in parts.items() if os.path.splitext(name)[0] == stem}
    if ".shx" not in by_ext:
        raise UserAreaError("Falta o arquivo .shx do shapefile.")
    try:
        reader = shapefile.Reader(shp=BytesIO(by_ext[".shp"]), shx=BytesIO(by_ext[".shx"]))
        if reader.shapeType not in (shapefile.POLYGON, shapefile.POLYGONZ, shapefile.POLYGONM):
            raise UserAreaError("O shapefile precisa ser de polígonos (pontos e linhas não definem uma área).")
        if len(reader) > MAX_FEATURES:
            raise UserAreaError(f"O shapefile tem mais de {MAX_FEATURES:,} feições.".replace(",", "."))
        geoms = []
        for shp in reader.iterShapes():
            if not shp.points:
                continue
            geom = shape(shp.__geo_interface__)
            budget.add(geom)
            geoms.append(geom)
    except UserAreaError:
        raise
    except Exception as exc:
        raise UserAreaError("Não foi possível ler o shapefile; confira se .shp e .shx são do mesmo arquivo.") from exc
    prj = by_ext.get(".prj")
    return geoms, prj.decode("utf-8", errors="replace") if prj else None


_GPKG_ENVELOPE_BYTES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


def _gpkg_geometry(blob: bytes):
    if not blob or blob[:2] != b"GP":
        raise UserAreaError("O GeoPackage tem uma geometria em formato desconhecido.")
    flags = blob[3]
    if (flags >> 4) & 1:  # geometria vazia
        return None
    envelope = _GPKG_ENVELOPE_BYTES.get((flags >> 1) & 0b111)
    if envelope is None:
        raise UserAreaError("O GeoPackage tem um cabeçalho de geometria inválido.")
    return shapely_wkb.loads(bytes(blob[8 + envelope:]))


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _parse_gpkg(data: bytes, budget: _VertexBudget) -> tuple[list, str | None, list[str]]:
    notes: list[str] = []
    handle = tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False)
    try:
        handle.write(data)
        handle.close()
        conn = sqlite3.connect(f"file:{handle.name}?mode=ro", uri=True)
        try:
            conn.execute("PRAGMA trusted_schema = OFF")
            tables = conn.execute(
                "SELECT table_name, column_name, srs_id FROM gpkg_geometry_columns ORDER BY table_name"
            ).fetchall()
            if not tables:
                raise UserAreaError("O GeoPackage não tem camadas de geometria.")
            table, column, srs_id = tables[0]
            if len(tables) > 1:
                notes.append(f"O GeoPackage tem {len(tables)} camadas; foi usada a primeira ({table}).")
            srs = conn.execute(
                "SELECT organization, organization_coordsys_id, definition FROM gpkg_spatial_ref_sys WHERE srs_id = ?",
                (srs_id,),
            ).fetchone()
            crs = None
            if srs:
                organization, code, definition = srs
                if str(organization).upper() == "EPSG" and code and int(code) > 0:
                    crs = f"EPSG:{int(code)}"
                elif definition and definition.strip().lower() != "undefined":
                    crs = definition
            rows = conn.execute(
                f"SELECT {_quote_ident(column)} FROM {_quote_ident(table)} LIMIT ?", (MAX_FEATURES + 1,)  # nosec B608 - nomes vêm do catálogo do próprio GPKG e são citados
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise UserAreaError("O arquivo .gpkg não é um GeoPackage válido.") from exc
    finally:
        try:
            os.remove(handle.name)
        except OSError:
            pass
    if len(rows) > MAX_FEATURES:
        raise UserAreaError(f"A camada tem mais de {MAX_FEATURES:,} feições.".replace(",", "."))
    geoms = []
    for (blob,) in rows:
        try:
            geom = _gpkg_geometry(blob)
        except UserAreaError:
            raise
        except Exception as exc:
            raise UserAreaError("O GeoPackage tem uma geometria inválida.") from exc
        if geom is not None:
            budget.add(geom)
            geoms.append(geom)
    return geoms, crs, notes


# ------------------------------------------------------------------------------------------ geometria
def _polygonal(geoms: list):
    polys = []
    for geom in geoms:
        geom = shapely.force_2d(geom)
        if not geom.is_valid:
            geom = shapely.make_valid(geom)
        for part in shapely.get_parts(geom):
            if isinstance(part, (Polygon, MultiPolygon)) and not part.is_empty:
                polys.append(part)
            elif part.geom_type == "GeometryCollection":
                polys.extend(p for p in shapely.get_parts(part) if isinstance(p, (Polygon, MultiPolygon)))
    return polys


def _to_wgs84(geom, crs_text: str | None):
    """Reprojeta para EPSG:4326. Sem CRS declarado, aceita só se as coordenadas forem lon/lat."""
    if not crs_text:
        lon_min, lat_min, lon_max, lat_max = geom.bounds
        if not (-180 <= lon_min <= lon_max <= 180 and -90 <= lat_min <= lat_max <= 90):
            raise UserAreaError(
                "As coordenadas não estão em graus (longitude/latitude) e o arquivo não informa a projeção. "
                "Para shapefile, envie também o .prj."
            )
        return geom, "EPSG:4326 (presumido)"
    from pyproj import CRS, Transformer
    from pyproj.exceptions import CRSError

    try:
        crs = CRS.from_user_input(crs_text)
    except CRSError as exc:
        raise UserAreaError("Não foi possível interpretar a projeção do arquivo (.prj/CRS).") from exc
    label = crs.to_string() if crs.to_epsg() is None else f"EPSG:{crs.to_epsg()}"
    if crs.to_epsg() == 4326:
        return geom, label
    transformer = Transformer.from_crs(crs, 4326, always_xy=True)

    def reproject(coords: np.ndarray) -> np.ndarray:
        x, y = transformer.transform(coords[:, 0], coords[:, 1])
        return np.column_stack([x, y])

    out = shapely.transform(geom, reproject)
    if not np.all(np.isfinite(shapely.get_coordinates(out))):
        raise UserAreaError("A reprojeção do arquivo gerou coordenadas inválidas; confira a projeção (.prj).")
    return out, f"{label} → EPSG:4326"


def _limit_vertices(geom) -> tuple[object, float]:
    """Simplifica até MAX_OUTPUT_VERTICES; devolve a geometria e a tolerância usada (graus)."""
    if shapely.get_num_coordinates(geom) <= MAX_OUTPUT_VERTICES:
        return geom, 0.0
    lon_min, lat_min, lon_max, lat_max = geom.bounds
    tolerance = max(lon_max - lon_min, lat_max - lat_min) / 20_000
    simplified = geom
    for _ in range(25):
        simplified = geom.simplify(tolerance, preserve_topology=True)
        simplified = shapely.union_all(_flatten_polys(_polygonal([simplified])))
        if not simplified.is_empty and shapely.get_num_coordinates(simplified) <= MAX_OUTPUT_VERTICES:
            return simplified, tolerance
        tolerance *= 2
    raise UserAreaError("Não foi possível simplificar a área para um tamanho que o Earth Engine aceite.")


def _flatten_polys(polys: list) -> list[Polygon]:
    out = []
    for poly in polys:
        out.extend(poly.geoms if isinstance(poly, MultiPolygon) else [poly])
    return out


def _area_km2(geom) -> float:
    from pyproj import Geod

    # O sinal da área geodésica depende do sentido de cada anel: orienta exterior anti-horário e
    # buracos horário, senão os buracos seriam somados em vez de subtraídos.
    area, _ = Geod(ellps="WGS84").geometry_area_perimeter(shapely.orient_polygons(geom))
    return abs(area) / 1e6


# ------------------------------------------------------------------------------------------ entrada
def load_user_area(files: tuple[tuple[str, bytes], ...]) -> UserArea:
    """Converte os arquivos enviados (nome, bytes) numa única área em WGS84.

    Várias feições são unidas num só polígono/multipolígono. Lança UserAreaError com mensagem
    pronta para o usuário quando o arquivo não serve.
    """
    if not files:
        raise UserAreaError("Nenhum arquivo foi enviado.")
    if sum(len(content) for _, content in files) > MAX_UPLOAD_BYTES:
        raise UserAreaError("Os arquivos enviados passam do limite de 20 MB.")

    budget_bytes = [MAX_UNCOMPRESSED_BYTES]
    members: dict[str, bytes] = {}
    zipped_kml = False
    for name, content in files:
        ext = _ext(name)
        if ext in {".zip", ".kmz"}:
            inner = _read_zip(content, budget_bytes)
            if ext == ".kmz":
                # No KMZ vale só o documento principal (doc.kml); imagens e outros KML são anexos.
                kmls = [n for n in inner if _ext(n) == ".kml"]
                if not kmls:
                    raise UserAreaError("O KMZ não contém um arquivo .kml.")
                main = "doc.kml" if "doc.kml" in inner else kmls[0]
                inner = {main: inner[main]}
                zipped_kml = True
            members.update(inner)
        else:
            members[PurePosixPath(str(name).replace("\\", "/")).name] = content
    display_name = safe_display_name(files[0][0])

    # Uma área por vez: o envio múltiplo existe para as partes do shapefile (.shp/.shx/.dbf/.prj).
    # Antes, enviar um segundo KML/GeoJSON fazia o app usar o primeiro em silêncio.
    datasets = {n for n in members if _ext(n) in {".kml", ".gpkg", ".geojson", ".json"}}
    datasets |= {os.path.splitext(n)[0] + ".shp" for n in members if _ext(n) == ".shp"}
    if len(datasets) > 1:
        raise UserAreaError(
            "Foi enviado mais de um arquivo de área (" + ", ".join(sorted(datasets)[:4]) + "). "
            "Remova os anteriores e deixe só um; para shapefile, envie as partes do mesmo arquivo."
        )

    budget = _VertexBudget()
    notes: list[str] = []
    exts = {_ext(name) for name in members}
    crs_text: str | None = None
    if ".shp" in exts:
        shp_parts = {n: c for n, c in members.items() if _ext(n) in SHAPEFILE_PARTS}
        geoms, crs_text = _parse_shapefile(shp_parts, budget)
        fmt = "Shapefile"
        if crs_text is None:
            notes.append("O shapefile não tem .prj; as coordenadas foram tratadas como longitude/latitude (WGS84).")
    elif ".kml" in exts:
        kml_name = "doc.kml" if "doc.kml" in members else next(n for n in members if _ext(n) == ".kml")
        geoms = _parse_kml(members[kml_name], budget)
        fmt = "KMZ" if zipped_kml else "KML"
        crs_text = "EPSG:4326"  # a especificação KML define sempre WGS84 lon/lat
    elif ".gpkg" in exts:
        gpkg_name = next(n for n in members if _ext(n) == ".gpkg")
        geoms, crs_text, notes = _parse_gpkg(members[gpkg_name], budget)
        fmt = "GeoPackage"
    elif exts & {".geojson", ".json"}:
        json_name = next(n for n in members if _ext(n) in {".geojson", ".json"})
        geoms, crs_text = _parse_geojson(members[json_name], budget)
        fmt = "GeoJSON"
    else:
        raise UserAreaError("Formato não reconhecido. Use .zip/.shp (shapefile), .kml, .kmz, .geojson ou .gpkg.")

    polys = _polygonal(geoms)
    if not polys:
        raise UserAreaError("O arquivo não tem polígonos. Pontos e linhas não definem uma área de interesse.")
    merged = shapely.union_all(polys)
    merged, crs_label = _to_wgs84(merged, crs_text)
    if not merged.is_valid:
        merged = shapely.make_valid(merged)
    merged = shapely.union_all(_flatten_polys(_polygonal([merged])))
    if merged.is_empty or merged.area <= 0:
        raise UserAreaError("A área do arquivo é vazia depois da validação da geometria.")
    lon_min, lat_min, lon_max, lat_max = merged.bounds
    if not (-180 <= lon_min <= lon_max <= 180 and -90 <= lat_min <= lat_max <= 90):
        raise UserAreaError("A área tem coordenadas fora da Terra (longitude ±180°, latitude ±90°).")

    input_vertices = int(shapely.get_num_coordinates(merged))
    merged, tolerance = _limit_vertices(merged)
    if tolerance:
        meters = tolerance * 111_320
        notes.append(
            f"O contorno foi simplificado de {input_vertices:,} para {int(shapely.get_num_coordinates(merged)):,} "
            f"vértices (tolerância ≈ {meters:,.0f} m) para caber nas consultas ao Earth Engine.".replace(",", ".")
        )
    sa = SOUTH_AMERICA_BBOX
    if lon_max < sa[0] or lon_min > sa[2] or lat_max < sa[1] or lat_min > sa[3]:
        notes.append("A área fica fora da América do Sul; alguns produtos (ex.: GOES) podem não ter dados nela.")

    return UserArea(
        name=display_name,
        geojson=json.dumps(mapping(merged), separators=(",", ":")),
        bbox=tuple(round(v, 6) for v in merged.bounds),
        area_km2=_area_km2(merged),
        n_features=budget.features,
        n_vertices=int(shapely.get_num_coordinates(merged)),
        source_format=fmt,
        source_crs=crs_label,
        warnings=tuple(notes),
    )
