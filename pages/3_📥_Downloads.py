#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
import json

import pandas as pd
import streamlit as st

from modules.auth_gee import initialize_gee
from modules.maps import BASEMAPS, make_map, visual_image_with_overlays
from modules.products import PRODUCTS, image_count, period_image, safe_filename
from modules.regions import get_region, region_display_name, region_options, overlay_options, default_overlays
from modules.ui import regional_selector_ui, load_css, page_title, product_metadata, landcover_legend_ui

st.set_page_config(layout="wide", page_title="PJ043 | Downloads", page_icon="📥")
load_css("assets/style.css")
initialize_gee()

page_title("📥 Downloads", "Baixe produtos com shapes em PNG/JPEG/HTML e GeoTIFF analítico.")

with st.sidebar:
    st.header("Filtros do download")
    product_name = st.selectbox("Produto", list(PRODUCTS.keys()))
    region_name = st.selectbox("Região", region_options())

    bounds, country_name, admin1_name, city_name = regional_selector_ui(region_name)

    today = date.today()
    start = st.date_input("Data inicial", value=today - timedelta(days=30))
    end = st.date_input("Data final", value=today)

    scale = st.number_input(
        "Escala do GeoTIFF (m)",
        min_value=10,
        max_value=60000,
        value=PRODUCTS[product_name].scale,
        step=1000,
        help="Para América do Sul inteira, use escala maior para evitar erro por arquivo muito grande.",
    )

    overlays = st.multiselect(
        "Shapes no PNG/JPEG/HTML",
        overlay_options(region_name),
        default=default_overlays(region_name),
    )

    st.markdown("### Formatos")
    want_tif = st.checkbox("GeoTIFF / TIFF analítico", value=True)
    want_png = st.checkbox("PNG com shapes", value=True)
    want_jpeg = st.checkbox("JPEG com shapes", value=True)
    want_csv = st.checkbox("CSV de metadados", value=True)
    want_json = st.checkbox("JSON de metadados", value=True)
    want_html = st.checkbox("HTML do mapa interativo", value=True)

    basemap = st.selectbox(
        "Mapa base do HTML",
        BASEMAPS,
        index=0,
        help="Esta opção afeta o HTML interativo. PNG/JPEG são imagens do produto com shapes, sem mapa base externo.",
    )

product = PRODUCTS[product_name]

if start >= end:
    st.error("A data inicial precisa ser anterior à data final.")
    st.stop()

c1, c2 = st.columns([0.68, 0.32], gap="large")

with c2:
    product_metadata(product)
    if product_name == "Cobertura do Solo":
        landcover_legend_ui()
    st.warning(
        "GeoTIFF preserva os valores reais do produto. PNG/JPEG saem com os shapes. "
        "O mapa base claro/escuro/satélite é aplicado ao HTML interativo.",
        icon="⚠️",
    )

with c1:
    st.markdown("### Gerar arquivos")
    st.write(
        "GeoTIFF é recomendado para análise em SIG. PNG/JPEG são imagens visualizadas com shapes. "
        "HTML mantém o mapa interativo com o mapa base escolhido."
    )

    if st.button("Gerar opções de download", type="primary"):
        try:
            with st.spinner("Preparando produto no Earth Engine..."):
                region = get_region(
                    region_name,
                    bounds,
                    country_name=country_name,
                    admin1_name=admin1_name,
                    city_name=city_name,
                )
                n = image_count(product_name, start.isoformat(), end.isoformat(), region)

                if n == 0:
                    st.warning("Nenhuma imagem encontrada para o produto, região e período selecionados.")
                    st.stop()

                image = period_image(product_name, start.isoformat(), end.isoformat(), region)
                region_bounds = region.bounds(maxError=1000).getInfo()["coordinates"]

                reg_label = region_display_name(region_name, country_name, admin1_name, city_name)
                base_name = (
                    f"PJ043_{safe_filename(product_name)}_"
                    f"{safe_filename(reg_label)}_{start}_{end}_{safe_filename(product.statistic)}"
                )

                metadata = {
                    "arquivo_base": base_name,
                    "produto": product.key,
                    "variavel": product.out_band,
                    "unidade": product.unit,
                    "regiao": reg_label,
                    "data_inicio": start.isoformat(),
                    "data_fim": end.isoformat(),
                    "estatistica": product.statistic,
                    "escala_m": int(scale),
                    "fonte": product.source,
                    "colecao_gee": product.collection or product.image_id,
                    "banda_gee": ",".join(product.band) if isinstance(product.band, list) else product.band,
                    "imagens_no_periodo": n,
                    "shapes_png_jpeg_html": ", ".join(overlays),
                    "mapa_base_html": basemap,
                    "data_processamento_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }

                metadata_df = pd.DataFrame([metadata])

                links = {}
                if want_tif:
                    links["GeoTIFF"] = image.getDownloadURL(
                        {
                            "name": base_name,
                            "scale": int(scale),
                            "region": region_bounds,
                            "crs": "EPSG:4326",
                            "filePerBand": False,
                            "format": "GEO_TIFF",
                        }
                    )

                visual = visual_image_with_overlays(
                    image,
                    product_name,
                    region,
                    overlays,
                    region_name=region_name,
                    country_name=country_name,
                    admin1_name=admin1_name,
                    city_name=city_name,
                )

                thumb_params = {
                    "region": region_bounds,
                    "dimensions": 1600,
                }

                if want_png:
                    png_params = dict(thumb_params)
                    png_params["format"] = "png"
                    links["PNG"] = visual.getThumbURL(png_params)

                if want_jpeg:
                    jpeg_params = dict(thumb_params)
                    jpeg_params["format"] = "jpg"
                    links["JPEG"] = visual.getThumbURL(jpeg_params)

                html_bytes = None
                if want_html:
                    mapa, _, _ = make_map(
                        product_name,
                        start.isoformat(),
                        end.isoformat(),
                        region_name,
                        bounds=bounds,
                        overlays=overlays,
                        basemap=basemap,
                        country_name=country_name,
                        admin1_name=admin1_name,
                        city_name=city_name,
                    )
                    html_bytes = mapa.get_root().render().encode("utf-8")

            st.success("Opções de download geradas.")

            d1, d2, d3 = st.columns(3)

            with d1:
                if "GeoTIFF" in links:
                    st.link_button("Baixar GeoTIFF / TIFF", links["GeoTIFF"], use_container_width=True)
                if "PNG" in links:
                    st.link_button("Baixar PNG com shapes", links["PNG"], use_container_width=True)

            with d2:
                if "JPEG" in links:
                    st.link_button("Baixar JPEG com shapes", links["JPEG"], use_container_width=True)
                if want_csv:
                    st.download_button(
                        "Baixar CSV de metadados",
                        data=metadata_df.to_csv(index=False).encode("utf-8"),
                        file_name=f"{base_name}_metadados.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

            with d3:
                if want_json:
                    st.download_button(
                        "Baixar JSON de metadados",
                        data=json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"),
                        file_name=f"{base_name}_metadados.json",
                        mime="application/json",
                        use_container_width=True,
                    )

                if html_bytes:
                    st.download_button(
                        "Baixar HTML do mapa",
                        data=html_bytes,
                        file_name=f"{base_name}_mapa.html",
                        mime="text/html",
                        use_container_width=True,
                    )

            st.markdown("### Metadados")
            st.dataframe(metadata_df, use_container_width=True)

        except Exception as exc:
            st.error("Não foi possível gerar os downloads com os filtros selecionados.")
            st.exception(exc)
