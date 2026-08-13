#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import datetime, timezone
import json

import pandas as pd
import streamlit as st

from modules.auth_gee import initialize_gee
from modules.maps import BASEMAPS, make_map, visual_image_with_overlays
from modules.products import PRODUCTS, image_count, period_image, safe_filename
from modules.regions import (
    default_overlays,
    get_region,
    overlay_options,
    region_display_name,
    region_options,
)
from modules.ui import (
    date_range_ui,
    landcover_legend_ui,
    load_css,
    page_title,
    processing_time_warning,
    product_metadata,
    product_selector_ui,
    query_dates,
    regional_selector_ui,
)

load_css("assets/style.css")
initialize_gee()

page_title(
    "📥 Downloads",
    "Gere GeoTIFF analítico, imagens com contornos, mapa HTML e metadados documentados.",
)

with st.sidebar:
    st.header("Filtros do download")
    product_name = product_selector_ui("download")
    product = PRODUCTS[product_name]

    region_name = st.selectbox("Região", region_options(), key="download_region")
    bounds, country_name, admin1_name, city_name = regional_selector_ui(region_name)

    start, end = date_range_ui(product, "download_dates")
    processing_time_warning(product, start, end)

    scale = st.number_input(
        "Escala do GeoTIFF (m)",
        min_value=10,
        max_value=60000,
        value=int(product.scale),
        step=100 if product.scale < 1000 else 1000,
        help="Para a América do Sul inteira, use escala maior para reduzir o tamanho e o custo do arquivo.",
    )

    overlays = st.multiselect(
        "Contornos no PNG/JPEG/HTML",
        overlay_options(region_name),
        default=default_overlays(region_name),
        key=f"download_overlays_{region_name}",
    )

    st.markdown("### Formatos")
    want_tif = st.checkbox("GeoTIFF analítico", value=True)
    want_png = st.checkbox("PNG com contornos", value=True)
    want_jpeg = st.checkbox("JPEG com contornos", value=False)
    want_csv = st.checkbox("CSV de metadados", value=True)
    want_json = st.checkbox("JSON de metadados", value=True)
    want_html = st.checkbox("HTML do mapa interativo", value=True)
    basemap = st.selectbox("Mapa base do HTML", BASEMAPS, index=0)

if product.temporal and start is not None and end is not None and start > end:
    st.error("A data inicial precisa ser anterior ou igual à data final.")
    st.stop()

left, right = st.columns([0.68, 0.32], gap="large")
with right:
    product_metadata(product)
    if product_name == "Cobertura do Solo":
        landcover_legend_ui()
    st.warning(
        "O GeoTIFF preserva valores analíticos. PNG/JPEG são visualizações RGB; o mapa base externo "
        "aparece apenas no HTML interativo.",
        icon="⚠️",
    )

with left:
    st.markdown("### Gerar arquivos")
    if st.button("Gerar opções de download", type="primary"):
        try:
            with st.spinner("Preparando os produtos no Earth Engine..."):
                start_text, end_text = query_dates(product, start, end)
                region = get_region(
                    region_name,
                    bounds,
                    country_name=country_name,
                    admin1_name=admin1_name,
                    city_name=city_name,
                )
                n_images = image_count(product_name, start_text, end_text, region)
                if n_images == 0:
                    st.warning("Nenhuma imagem foi encontrada para os filtros selecionados.")
                    st.stop()

                image = period_image(product_name, start_text, end_text, region)
                region_bounds = region.bounds(maxError=1000).getInfo()["coordinates"]
                region_label = region_display_name(region_name, country_name, admin1_name, city_name)

                date_token = f"{start_text}_{end_text}" if product.temporal else "estatico"
                base_name = (
                    f"SIMQA_{safe_filename(product_name)}_"
                    f"{safe_filename(region_label)}_{date_token}_{safe_filename(product.statistic)}"
                )

                metadata = {
                    "arquivo_base": base_name,
                    "produto": product.key,
                    "banco_plataforma": product.group,
                    "variavel": product.out_band,
                    "unidade": product.unit,
                    "regiao": region_label,
                    "data_inicio": start_text if product.temporal else None,
                    "data_fim_inclusiva": end_text if product.temporal else None,
                    "estatistica": product.statistic,
                    "metodo": product.method_note,
                    "limitacoes": product.limitations,
                    "escala_m": int(scale),
                    "fonte": product.source,
                    "colecao_gee": product.collection or product.image_id,
                    "banda_gee": ",".join(product.band) if isinstance(product.band, list) else product.band,
                    "imagens_no_periodo": n_images,
                    "contornos_png_jpeg_html": ", ".join(overlays),
                    "mapa_base_html": basemap,
                    "processamento_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
                metadata_df = pd.DataFrame([metadata])

                links: dict[str, str] = {}
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

                if want_png or want_jpeg:
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
                    common_thumb = {"region": region_bounds, "dimensions": 1600}
                    if want_png:
                        links["PNG"] = visual.getThumbURL({**common_thumb, "format": "png"})
                    if want_jpeg:
                        links["JPEG"] = visual.getThumbURL({**common_thumb, "format": "jpg"})

                html_bytes = None
                if want_html:
                    map_object, _, _ = make_map(
                        product_name,
                        start_text,
                        end_text,
                        region_name,
                        bounds=bounds,
                        overlays=overlays,
                        basemap=basemap,
                        country_name=country_name,
                        admin1_name=admin1_name,
                        city_name=city_name,
                    )
                    html_bytes = map_object.get_root().render().encode("utf-8")

            st.success("Opções de download geradas.")
            c1, c2, c3 = st.columns(3)
            with c1:
                if "GeoTIFF" in links:
                    st.link_button("Baixar GeoTIFF", links["GeoTIFF"], use_container_width=True)
                if "PNG" in links:
                    st.link_button("Baixar PNG", links["PNG"], use_container_width=True)
            with c2:
                if "JPEG" in links:
                    st.link_button("Baixar JPEG", links["JPEG"], use_container_width=True)
                if want_csv:
                    st.download_button(
                        "Baixar CSV de metadados",
                        metadata_df.to_csv(index=False).encode("utf-8"),
                        file_name=f"{base_name}_metadados.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
            with c3:
                if want_json:
                    st.download_button(
                        "Baixar JSON de metadados",
                        json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"),
                        file_name=f"{base_name}_metadados.json",
                        mime="application/json",
                        use_container_width=True,
                    )
                if html_bytes is not None:
                    st.download_button(
                        "Baixar HTML do mapa",
                        html_bytes,
                        file_name=f"{base_name}_mapa.html",
                        mime="text/html",
                        use_container_width=True,
                    )

            st.markdown("### Metadados")
            st.dataframe(metadata_df, use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error("Não foi possível gerar os downloads com os filtros selecionados.")
            st.exception(exc)
    else:
        st.info("Escolha os filtros e clique em **Gerar opções de download**.")
