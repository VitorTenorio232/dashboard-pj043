#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from modules.auth_gee import initialize_gee
from modules.maps import BASEMAPS, make_map, visual_image_with_overlays, _display_image_and_vis, summarize_image
from modules.export_image import styled_map_bytes, png_to_jpeg
from streamlit_folium import st_folium
from modules.products import PRODUCTS, image_count, safe_filename
from modules.regions import default_overlays, get_region, overlay_options, region_display_name, region_options
from modules.ui import (
    date_range_ui, landcover_legend_ui, load_css, page_title,
    processing_time_warning, product_metadata, product_selector_ui,
    query_dates, regional_selector_ui, sidebar_brand,
)

load_css("assets/style.css")
initialize_gee()
page_title("Mapas interativos", "Consulte e visualize produtos ambientais com recortes espaciais e temporais personalizados.")
with st.sidebar:
    sidebar_brand()
    st.markdown("**01  ·  Fonte de dados**")
    quick_product = st.session_state.pop("produto_rapido", None)
    product_name = product_selector_ui("map", default_product=quick_product)
    product = PRODUCTS[product_name]
    st.divider()
    st.markdown("**02  ·  Área de interesse**")
    region_name = st.selectbox("Região", region_options(), key="map_region")
    bounds, country_name, admin1_name, city_name = regional_selector_ui(region_name)
    st.divider()
    st.markdown("**03  ·  Período**")
    start, end = date_range_ui(product, "map_dates")
    processing_time_warning(product, start, end)
    with st.expander("Configurações do mapa", expanded=False):
        basemap = st.selectbox("Mapa base", BASEMAPS, index=0, key="map_basemap")
        overlays = st.multiselect(
            "Contornos exibidos no mapa", overlay_options(region_name),
            default=default_overlays(region_name), key=f"map_overlays_{region_name}",
            help="A escolha de contornos pode aumentar o tempo de renderização.",
        )
    run = st.button("Gerar mapa", type="primary", width="stretch")

if product.temporal and start is not None and end is not None and start > end:
    st.error("A data inicial precisa ser anterior ou igual à data final.")
    st.stop()

st.caption(f"**Produto selecionado:** {product.label}  ·  **Banco:** {product.group}  ·  **Região:** {region_name}")
if run:
    try:
        with st.spinner("Consultando o Google Earth Engine e preparando as camadas..."):
            start_text, end_text = query_dates(product, start, end)
            region = get_region(region_name, bounds, country_name=country_name, admin1_name=admin1_name, city_name=city_name)
            n_images = image_count(product_name, start_text, end_text, region)
            if n_images == 0:
                st.warning("Nenhuma imagem disponível para esta combinação. Confira o período informado pela coleção.")
            else:
                previous = st.session_state.get("vigia_map_result")
                view = st.session_state.get("vigia_map_view") if previous and previous.get("region_name") == region_name else None
                map_object, image, region = make_map(product_name, start_text, end_text, region_name, bounds=bounds, overlays=overlays, basemap=basemap, country_name=country_name, admin1_name=admin1_name, city_name=city_name)
                if view and isinstance(view.get("center"), dict):
                    center = view["center"]
                    zoom = view.get("zoom")
                    if isinstance(center.get("lat"), (int, float)) and isinstance(center.get("lng"), (int, float)):
                        map_object.location = [center["lat"], center["lng"]]
                        if isinstance(zoom, (int, float)):
                            map_object.options["zoom"] = int(zoom)
                region_label = region_display_name(region_name, country_name, admin1_name, city_name)
                _, vis = _display_image_and_vis(product_name, image, region)
                summary = summarize_image(product_name, image, region)
                sequence = st.session_state.get("vigia_map_seq", 0) + 1
                st.session_state["vigia_map_seq"] = sequence
                st.session_state["vigia_map_result"] = {
                    "seq": sequence, "map": map_object, "product": product_name, "region_name": region_name,
                    "region_label": region_label, "start": start_text, "end": end_text, "n_images": n_images,
                    "basemap": basemap, "overlays": overlays, "summary": summary,
                    # VIGIA V5.5.11: exportacao sob demanda — mapa nao depende do PNG.
                    "ee_image": image, "ee_region": region, "vis": vis,
                    "country_name": country_name, "admin1_name": admin1_name, "city_name": city_name,
                    "png_bytes": None, "jpeg_bytes": None,
                    "base_name": f"VIGIA_{safe_filename(product_name)}_{safe_filename(region_label)}_{start_text}_{end_text}",
                }
    except Exception as exc:
        st.error("Não foi possível gerar o mapa. Confira filtros, disponibilidade e permissões do Earth Engine.")
        st.exception(exc)

left, right = st.columns([.73, .27], gap="large", vertical_alignment="top")
with left:
    previous = st.session_state.get("vigia_map_result")
    if previous:
        result_label = PRODUCTS[previous["product"]].label
        st.markdown(f"### {result_label}")
        date_label = "Produto estático" if not PRODUCTS[previous["product"]].temporal else f"{previous['start']} a {previous['end']}"
        st.caption(f"Área: **{previous['region_label']}**  ·  Período: **{date_label}**  ·  Cenas: **{previous['n_images']}**")
        if previous["product"] != product_name or previous["region_name"] != region_name:
            st.info("Você alterou os filtros. O mapa abaixo ainda representa a última análise gerada; clique em **Gerar mapa** para atualizar.")
        view_data = st_folium(previous["map"], height=670, use_container_width=True, returned_objects=["center", "zoom"], key=f"vigia_map_canvas_{previous.get('seq', 0)}")
        if view_data and isinstance(view_data, dict):
            center, zoom = view_data.get("center"), view_data.get("zoom")
            if center and isinstance(zoom, (int, float)):
                st.session_state["vigia_map_view"] = {"center": center, "zoom": zoom}

        st.markdown("#### Informações do mapa")
        c1, c2, c3, c4 = st.columns(4, gap="small")
        with c1:
            with st.container(border=True):
                st.caption("Produto")
                st.markdown(f"**{result_label}**")
                st.write(PRODUCTS[previous["product"]].group)
        with c2:
            with st.container(border=True):
                st.caption("Área e mapa base")
                st.markdown(f"**{previous['region_label']}**")
                st.write(f"Mapa base: {previous['basemap']}")
        with c3:
            with st.container(border=True):
                st.caption("Período e cenas")
                st.markdown(f"**{date_label}**")
                st.write(f"Cenas no período: {previous['n_images']}")
        with c4:
            with st.container(border=True):
                st.caption("Resumo na área")
                st.markdown(f"**{previous['summary'].get('headline', 'n/d')}**")
                for line in previous['summary'].get('details', [])[:2]:
                    st.write(line)

        d1, d2 = st.columns([0.35, 0.65], gap="small")
        with d1:
            with st.container(border=True):
                st.caption("Baixar imagem")
                # Preparacao isolada: um timeout aqui nao derruba o mapa interativo.
                if st.button(
                    "Preparar PNG/JPEG",
                    key=f"vigia_prepare_image_{previous['seq']}",
                    width="stretch",
                    help="Monta a prancha com legenda, fundo selecionado, estatisticas e logo do VIGIA.",
                ):
                    try:
                        with st.spinner("Preparando a imagem para download no Earth Engine..."):
                            visual = visual_image_with_overlays(
                                previous["ee_image"], previous["product"], previous["ee_region"],
                                previous["overlays"], region_name=previous["region_name"],
                                country_name=previous.get("country_name"),
                                admin1_name=previous.get("admin1_name"),
                                city_name=previous.get("city_name"),
                            )
                            new_png = styled_map_bytes(
                                image=previous["ee_image"], product_name=previous["product"],
                                region=previous["ee_region"], region_label=previous["region_label"],
                                start_text=previous["start"], end_text=previous["end"],
                                unit=PRODUCTS[previous["product"]].unit,
                                source_label=PRODUCTS[previous["product"]].source,
                                overlays=previous["overlays"], visual_image=visual,
                                vis=previous["vis"], summary=previous["summary"],
                                basemap=previous["basemap"], output_format="PNG",
                            )
                            previous["png_bytes"] = new_png
                            previous["jpeg_bytes"] = png_to_jpeg(new_png)
                    except Exception as exc:
                        message = str(exc).lower()
                        if (isinstance(exc, TimeoutError)
                                or "timed out" in message or "timeout" in message
                                or "deadline exceeded" in message):
                            st.warning(
                                "A exportacao da imagem excedeu o tempo de resposta do serviço remoto. "
                                "O mapa interativo continua disponivel. Tente preparar novamente ou "
                                "selecione uma area/período menor."
                            )
                        else:
                            st.error("Não foi possível preparar o PNG/JPEG. O mapa interativo permanece disponível.")
                            st.exception(exc)
                if previous.get("png_bytes"):
                    st.download_button(
                        "Baixar PNG", previous["png_bytes"],
                        file_name=f"{previous['base_name']}.png", mime="image/png",
                        width="stretch", on_click="ignore",
                    )
                if previous.get("jpeg_bytes"):
                    st.download_button(
                        "Baixar JPEG", previous["jpeg_bytes"],
                        file_name=f"{previous['base_name']}.jpg", mime="image/jpeg",
                        width="stretch", on_click="ignore",
                    )
                if not previous.get("png_bytes"):
                    st.caption("O mapa já pode ser explorado. Prepare as imagens apenas se desejar baixar.")
        with d2:
            with st.container(border=True):
                st.caption("Contornos exibidos")
                if previous.get("overlays"):
                    st.write("  ·  ".join(previous["overlays"]))
                else:
                    st.write("Nenhum contorno adicional selecionado.")
                st.caption("Os downloads PNG/JPEG usam escala visual fixa do catálogo, fundo escolhido, recorte centralizado, legenda e rodapé institucional do VIGIA.")
    else:
        with st.container(border=True):
            st.markdown("#### Seu mapa aparecerá aqui")
            st.info("Configure fonte, área e período na barra lateral e clique em **Gerar mapa**.", icon="🗺️")
with right:
    with st.container(border=True):
        product_metadata(product)
        if product_name == "Cobertura do Solo":
            landcover_legend_ui()
        st.caption("A escala visual do mapa agora é fixa para todos os produtos, conforme definido no catálogo do VIGIA.")
