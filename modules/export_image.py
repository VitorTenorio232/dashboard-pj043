#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Geração de imagens exportáveis do VIGIA com layout institucional e fundo do mapa."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from math import atan, floor, ceil, log, pi, sinh, tan
from urllib.request import Request, urlopen

import ee

from modules.products import PRODUCTS, LANDCOVER_PALETTE

TILE_SIZE = 256


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.strip().lstrip('#')
    if len(h) == 3:
        h = ''.join(ch * 2 for ch in h)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _download_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "VIGIA/1.0"})
    with urlopen(req, timeout=45) as response:
        return response.read()


def _download_image(url: str, mode: str = 'RGBA'):
    from PIL import Image
    return Image.open(BytesIO(_download_bytes(url))).convert(mode)


def _lonlat_to_world(lon: float, lat: float, zoom: int) -> tuple[float, float]:
    lat = max(min(lat, 85.05112878), -85.05112878)
    scale = TILE_SIZE * (2 ** zoom)
    x = (lon + 180.0) / 360.0 * scale
    lat_rad = lat * pi / 180.0
    y = (1 - log(tan(pi / 4 + lat_rad / 2)) / pi) / 2 * scale
    return x, y


def _world_to_lonlat(x: float, y: float, zoom: int) -> tuple[float, float]:
    scale = TILE_SIZE * (2 ** zoom)
    lon = x / scale * 360.0 - 180.0
    n = pi - 2.0 * pi * y / scale
    lat = 180.0 / pi * atan(sinh(n))
    return lon, lat


def _get_region_bounds(region) -> tuple[float, float, float, float]:
    coords = region.bounds(maxError=1000).getInfo()['coordinates'][0]
    lons = [pt[0] for pt in coords]
    lats = [pt[1] for pt in coords]
    return min(lons), min(lats), max(lons), max(lats)


def _fit_view(min_lon: float, min_lat: float, max_lon: float, max_lat: float,
              width_px: int, height_px: int) -> tuple[float, tuple[float,float,float,float]]:
    """Faz fit geográfico contínuo, sem degraus de zoom inteiro entre cidades/estados.

    Centralização é feita em coordenadas Web Mercator, não na média de latitudes.
    """
    span=max(max_lon-min_lon,max_lat-min_lat)
    pad=0.07 if span>6 else (0.04 if span>1 else 0.025)
    if span<0.15: limit=14
    elif span<0.5: limit=13
    elif span<1.5: limit=11
    elif span<6: limit=9
    else: limit=7
    x1,y1=_lonlat_to_world(min_lon,max_lat,0)
    x2,y2=_lonlat_to_world(max_lon,min_lat,0)
    bw=max(abs(x2-x1),1e-9)*(1+2*pad)
    bh=max(abs(y2-y1),1e-9)*(1+2*pad)
    zoom=max(0.0,min(float(limit),log(min(width_px/bw,height_px/bh),2)))
    cx=(x1+x2)/2 * 2**zoom
    cy=(y1+y2)/2 * 2**zoom
    west,north=_world_to_lonlat(cx-width_px/2,cy-height_px/2,zoom)
    east,south=_world_to_lonlat(cx+width_px/2,cy+height_px/2,zoom)
    return zoom,(west,south,east,north)


def _basemap_url(basemap: str, z: int, x: int, y: int) -> str:
    if basemap == 'Escuro':
        return f'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'
    if basemap == 'Satélite':
        return f'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
    return f'https://tile.openstreetmap.org/{z}/{x}/{y}.png'


def _fetch_basemap(basemap: str, bbox: tuple[float,float,float,float], width_px: int,
                   height_px: int, zoom: float):
    """Baixa tiles na resolução suficiente para um viewport de zoom fracionário."""
    from PIL import Image
    from concurrent.futures import ThreadPoolExecutor, as_completed
    west,south,east,north=bbox
    tile_zoom=max(0,min(16,int(ceil(zoom))))
    left_px,top_px=_lonlat_to_world(west,north,tile_zoom)
    right_px,bottom_px=_lonlat_to_world(east,south,tile_zoom)
    x0,x1=int(floor(left_px/TILE_SIZE)),int(floor((right_px-1)/TILE_SIZE))
    y0,y1=int(floor(top_px/TILE_SIZE)),int(floor((bottom_px-1)/TILE_SIZE))
    world_n=2**tile_zoom
    canvas=Image.new('RGB',((x1-x0+1)*TILE_SIZE,(y1-y0+1)*TILE_SIZE),(245,247,250))
    tasks=[]
    for tx in range(x0,x1+1):
        for ty in range(max(0,y0),min(world_n-1,y1)+1):
            tasks.append((tx,ty,_basemap_url(basemap,tile_zoom,tx%world_n,ty)))
    if not tasks or len(tasks)>250:
        raise RuntimeError('Extensão/zoom incompatível com exportação rápida de tiles.')
    def fetch(task):
        tx,ty,url=task
        try:return tx,ty,_download_image(url,mode='RGB')
        except Exception:return tx,ty,None
    downloaded=0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for fut in as_completed([pool.submit(fetch,t) for t in tasks]):
            tx,ty,tile=fut.result()
            if tile is not None:
                canvas.paste(tile,((tx-x0)*TILE_SIZE,(ty-y0)*TILE_SIZE))
                downloaded+=1
    if downloaded==0:
        raise RuntimeError('Falha ao obter mapa base. Confira conectividade e serviço de tiles.')
    crop=(round(left_px-x0*TILE_SIZE),round(top_px-y0*TILE_SIZE),
          round(right_px-x0*TILE_SIZE),round(bottom_px-y0*TILE_SIZE))
    crop_img=canvas.crop(crop)
    return crop_img.resize((width_px,height_px),resample=Image.Resampling.LANCZOS)


def _gradient_bar(draw, x: int, y: int, width: int, height: int, palette: list[str]):
    colors = [_hex_to_rgb(c) for c in palette]
    if len(colors) == 1:
        draw.rectangle((x, y, x + width, y + height), fill=colors[0])
        return
    segments = len(colors) - 1
    for i in range(width):
        t = i / max(1, width - 1)
        pos = t * segments
        idx = min(segments - 1, int(pos))
        frac = pos - idx
        c1 = colors[idx]
        c2 = colors[idx + 1]
        rgb = tuple(int(c1[j] + (c2[j] - c1[j]) * frac) for j in range(3))
        draw.line((x + i, y, x + i, y + height), fill=rgb)


def _wrap(draw, text: str, font, width: int) -> list[str]:
    words = text.split()
    lines, cur = [], ''
    for w in words:
        test = (cur + ' ' + w).strip()
        if draw.textlength(test, font=font) <= width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _draw_centered_lines(draw, lines: list[str], center_x: int, start_y: int, font, fill, line_gap: int = 18):
    y = start_y
    for line in lines:
        tw = draw.textlength(line, font=font)
        draw.text((center_x - tw / 2, y), line, font=font, fill=fill)
        y += line_gap
    return y




# Códigos e classes do Copernicus PROBA-V: apresentação da legenda categórica,
# sem alterar o remapeamento de cores usado pelo Earth Engine.
_LANDCOVER_SHORT = {
    0:"Sem dados", 20:"Arbustos", 30:"Herbáceas", 40:"Agricultura",
    50:"Urbano", 60:"Vegetação esparsa", 70:"Neve/gelo", 80:"Água",
    90:"Áreas úmidas", 100:"Musgos e líquens",
    111:"Fl. fechada perene, acículas", 112:"Fl. fechada perene, folhas largas",
    113:"Fl. fechada decídua, acículas", 114:"Fl. fechada decídua, folhas largas",
    115:"Fl. fechada mista", 116:"Outras florestas fechadas",
    121:"Fl. aberta perene, acículas", 122:"Fl. aberta perene, folhas largas",
    123:"Fl. aberta decídua, acículas", 124:"Fl. aberta decídua, folhas largas",
    125:"Fl. aberta mista", 126:"Outras florestas abertas", 200:"Oceano",
}


def png_to_jpeg(png_data: bytes, quality: int = 92) -> bytes:
    """Converte a mesma prancha PNG para JPEG sem recarregar tiles ou GEE."""
    from PIL import Image
    image = Image.open(BytesIO(png_data)).convert("RGB")
    output = BytesIO()
    image.save(output, format="JPEG", quality=quality, optimize=True)
    return output.getvalue()


def _draw_wrapped_center(draw, value, cx, y, width, font, fill, gap=22, limit=3):
    for s in _wrap(draw, str(value), font, width)[:limit]:
        draw.text((cx - draw.textlength(s, font=font) / 2, y), s, font=font, fill=fill)
        y += gap
    return y


def _font(size, bold=False):
    """Resolve uma fonte Unicode com tamanho real em Linux/Cloud/Windows.

    Nunca usa silenciosamente a fonte bitmap minuscula do Pillow: isso
    quebrava tamanhos e acentos nos boletins do VIGIA no Streamlit Cloud.
    """
    from functools import lru_cache
    from pathlib import Path
    from PIL import ImageFont

    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    candidates = []
    try:
        import matplotlib
        candidates.append(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / filename)
    except (ImportError, AttributeError, OSError):
        pass

    candidates.extend([
        filename,
        Path("/usr/share/fonts/truetype/dejavu") / filename,
        Path("/usr/local/share/fonts") / filename,
        Path("/usr/share/fonts/truetype/liberation2") / (
            "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf"
        ),
        Path("/usr/share/fonts/truetype/noto") / (
            "NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf"
        ),
        Path("C:/Windows/Fonts") / ("arialbd.ttf" if bold else "arial.ttf"),
    ])

    for candidate in candidates:
        try:
            font = ImageFont.truetype(str(candidate), int(size))
            # Fontes sem glyphs PT-BR desenham o mesmo caractere de substituicao.
            if bytes(font.getmask("ã")) == bytes(font.getmask("ç")):
                continue
            return font
        except (OSError, ValueError, AttributeError):
            continue

    raise RuntimeError(
        "Nao foi encontrada uma fonte Unicode adequada para a prancha VIGIA. "
        "Instale as dependencias com 'python -m pip install -r requirements.txt' "
        "(inclui matplotlib), e reinicie o Streamlit."
    )


def render_board(
    map_image,
    product_name: str,
    region_label: str,
    start_text: str | None,
    end_text: str | None,
    source_label: str,
    overlays: list[str],
    vis: dict,
    summary: dict | None,
    basemap: str,
    zoom: int,
    generated_at: datetime | None = None,
) -> bytes:
    """Composição determinística para teste visual sem conexão com GEE."""
    from PIL import Image, ImageDraw
    from modules.products import PRODUCTS, LANDCOVER_VALUES

    product = PRODUCTS[product_name]
    is_landcover = product_name == 'Cobertura do Solo'
    w, h = 1600, 1510 if is_landcover else 1400
    bg = (244, 247, 249)
    surface = (255, 255, 255)
    edge = (221, 229, 234)
    ink = (22, 36, 49)
    muted = (84, 100, 114)
    teal = (11, 91, 104)
    board = Image.new('RGB', (w, h), bg)
    d = ImageDraw.Draw(board)
    f_title, f_sub = _font(30, True), _font(17)
    f_card, f_body = _font(17, True), _font(15)
    f_small, f_brand = _font(13), _font(34, True)

    # Faixa superior: informação à esquerda, marca à direita; evita colisão.
    label = product.label
    for idx, piece in enumerate(_wrap(d, label, f_title, 1040)[:2]):
        d.text((60, 28 + idx * 38), piece, font=f_title, fill=ink)
    # VIGIA sidebar/export logo v5.5.10 — marca visual do relatório.
    try:
        from pathlib import Path
        icon_file = Path(__file__).resolve().parents[1] / "assets" / "icone_vigia.png"
        if icon_file.is_file():
            logo_icon = Image.open(icon_file).convert("RGBA")
            logo_icon.thumbnail((58, 58), Image.Resampling.LANCZOS)
            board.paste(logo_icon, (1207, 19), logo_icon)
            d.text((1278, 29), 'VIGIA', font=f_brand, fill=teal)
        else:
            d.text((1340 - d.textlength('VIGIA', font=f_brand)/2, 28), 'VIGIA', font=f_brand, fill=teal)
    except Exception:
        d.text((1340 - d.textlength('VIGIA', font=f_brand)/2, 28), 'VIGIA', font=f_brand, fill=teal)
    d.text((1335 - d.textlength('MONITORAMENTO AMBIENTAL', font=f_small)/2, 74),
           'MONITORAMENTO AMBIENTAL', font=f_small, fill=muted)
    period = 'Produto estático' if not product.temporal else f'{start_text} a {end_text}'
    header_sub = f'Área: {region_label}   |   Período: {period}   |   Fundo: {basemap}'
    for idx, piece in enumerate(_wrap(d, header_sub, f_sub, 1120)[:2]):
        d.text((60, 86 + idx * 23), piece, font=f_sub, fill=muted)

    # Mapa: grade 1450×720; recebe exatamente o fundo escolhido.
    d.rounded_rectangle((55, 135, 1545, 897), radius=17, fill=surface, outline=edge, width=2)
    from PIL import Image
    fitted = map_image.convert('RGB').resize((1450, 720), resample=Image.Resampling.LANCZOS)
    board.paste(fitted, (75, 155))

    # Cards institucionais centrados, largura consistente e sem texto invadindo bordas.
    cards = [
        ('BANCO / SENSOR', product.group),
        ('ÁREA DE INTERESSE', region_label),
        ('PERÍODO', period),
        ('RESULTADO NA ÁREA', (summary or {}).get('short','Não calculado')),
        ('BASE CARTOGRÁFICA', f'{basemap} • zoom {zoom:.1f}'),
    ]
    cx, top, cw, ch, gap = 55, 925, 282, 118, 20
    for i, (heading, value) in enumerate(cards):
        x = cx + (cw + gap) * i
        d.rounded_rectangle((x, top, x+cw, top+ch), radius=13, fill=surface, outline=edge, width=1)
        _draw_wrapped_center(d, heading, x+cw/2, top+16, cw-22, f_small, teal, limit=1)
        _draw_wrapped_center(d, value, x+cw/2, top+49, cw-24, f_body, ink, limit=3)

    # Bloco de legenda: nada à direita da barra, informações ficam abaixo.
    leg_top, leg_bottom = 1065, 1398 if is_landcover else 1287
    d.rounded_rectangle((55, leg_top, 1545, leg_bottom), radius=14, fill=surface, outline=edge, width=1)
    title = 'LEGENDA E INFORMAÇÕES'
    _draw_wrapped_center(d, title, w/2, leg_top+16, 1450, f_card, teal)

    if is_landcover:
        # Tabela visível, códigos não confundidos com valores contínuos.
        entries = list(zip(LANDCOVER_VALUES, LANDCOVER_PALETTE))
        x_cols = [95, 610, 1100]
        rows_per_col = 8
        for idx, (code, color) in enumerate(entries):
            col, row = idx // rows_per_col, idx % rows_per_col
            x, yy = x_cols[col], leg_top + 60 + row * 28
            d.rounded_rectangle((x, yy, x+25, yy+17), radius=3, fill=_hex_to_rgb(color))
            label = f'{code} · {_LANDCOVER_SHORT.get(code, "Classe")} '
            d.text((x+33, yy), label, font=f_small, fill=ink)
        _draw_wrapped_center(d, 'Classes apresentadas conforme a codificação do produto Copernicus.', w/2,
                             leg_bottom-32, 1380, f_small, muted, limit=1)
    else:
        # Barra e escalas fixas do catálogo, sem alterar conforme cidade/período.
        vmin, vmax = vis['min'], vis['max']
        palette = vis.get('palette', product.vis['palette'])
        title_line = f'{product.label} ({product.unit})'
        _draw_wrapped_center(d, title_line, w/2, leg_top+44, 1360, f_body, ink)
        bx, by, bw, bh = 350, leg_top+83, 900, 25
        _gradient_bar(d, bx, by, bw, bh, palette)
        d.rectangle((bx,by,bx+bw,by+bh), outline=edge, width=1)
        for frac in (0,.25,.5,.75,1):
            v = vmin + (vmax-vmin)*frac
            # Evita rstrip remover o próprio zero (erro observado em versões anteriores).
            label = f'{v:.4g}'
            xp = bx + bw*frac
            d.line((xp,by+bh,xp,by+bh+6), fill=muted)
            d.text((xp-d.textlength(label,font=f_small)/2,by+bh+9),label,font=f_small,fill=muted)

        _draw_wrapped_center(d, (summary or {}).get('headline','Estatística não calculada'), w/2,
                             leg_top+145, 1360, f_body, ink, limit=1)

    # Fonte e método: links/textos pequenos alinhados na metade inferior, sem invadir legenda.
    foot_start = leg_bottom + 22
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')
    attribution = {
        'Claro': 'Mapa base: © OpenStreetMap contributors',
        'Escuro': 'Mapa base: © CARTO; © OpenStreetMap contributors',
        'Satélite': 'Mapa base: Tiles © Esri',
    }.get(basemap, f'Mapa base: {basemap}')
    lines = [
        f'Fonte do produto: {source_label}   |   {attribution}',
        'Contornos: ' + (', '.join(overlays) if overlays else 'sem contornos adicionais'),
        f'VIGIA • Visualização Integrada de Gases, Incêndios e Atmosfera • Gerado em {generated}',
    ]
    for i, line in enumerate(lines):
        _draw_wrapped_center(d,line,w/2,foot_start + i*22,1430,f_small,muted,limit=1)
    data = BytesIO()
    board.save(data, format='PNG', optimize=True)
    return data.getvalue()



# VIGIA V5.5.11: thumbnail com segunda tentativa em resolucao reduzida.
def _fetch_thematic_thumbnail(visual_image, rect, size=(1450, 720)):
    """Consulta a imagem do GEE com fallback se houver timeout da rede/serviço."""
    from PIL import Image
    from urllib.error import HTTPError, URLError
    attempts = [size, (960, 480)]
    last_error = None
    for width, height in attempts:
        try:
            thumb_url = visual_image.getThumbURL({
                'region': rect,
                'dimensions': f'{width}x{height}',
                'format': 'png',
            })
            data = _download_image(thumb_url, mode='RGBA')
            if data.size != size:
                data = data.resize(size, resample=Image.Resampling.BILINEAR)
            return data
        except Exception as exc:
            msg = str(exc).lower()
            if isinstance(exc, HTTPError):
                transient = exc.code in (429, 500, 502, 503, 504)
            else:
                transient = (
                    isinstance(exc, (TimeoutError, URLError))
                    or any(token in msg for token in (
                        'timed out', 'timeout', 'deadline exceeded',
                        '429', '502', '503', '504', 'temporarily unavailable',
                    ))
                )
            if not transient:
                raise
            last_error = exc
    raise TimeoutError(
        'A imagem do Earth Engine excedeu o limite mesmo após uma tentativa em resolução reduzida.'
    ) from last_error


def styled_map_bytes(
    image: ee.Image, product_name: str, region, region_label: str,
    start_text: str | None, end_text: str | None, unit: str,
    source_label: str, overlays: list[str], visual_image: ee.Image,
    vis: dict, summary: dict | None = None, basemap: str = 'Claro',
    output_format: str = 'PNG',
) -> bytes:
    """Busca camadas e gera prancha; PNG/JPEG usam a mesma composição RGB."""
    # Manter argumento image para compatibilidade com as chamadas existentes.
    min_lon,min_lat,max_lon,max_lat = _get_region_bounds(region)
    zoom,bbox = _fit_view(min_lon,min_lat,max_lon,max_lat,1450,720)
    bg = _fetch_basemap(basemap,bbox,1450,720,zoom).convert('RGBA')
    west,south,east,north = bbox
    rect=[[[west,south],[east,south],[east,north],[west,north],[west,south]]]
    rgba = _fetch_thematic_thumbnail(visual_image, rect, size=(1450, 720))
    from PIL import Image
    if rgba.size != bg.size:
        rgba=rgba.resize(bg.size,Image.Resampling.BILINEAR)
    bg.alpha_composite(rgba)
    png = render_board(bg.convert('RGB'),product_name,region_label,start_text,end_text,
                       source_label,overlays,vis,summary,basemap,zoom)
    return png_to_jpeg(png) if output_format.upper()=='JPEG' else png
