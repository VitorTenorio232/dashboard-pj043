#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import streamlit as st

from modules.products import PRODUCTS, product_groups, products_in_group
from modules.ui import load_css, page_title, product_metadata

load_css("assets/style.css")

page_title(
    "ℹ️ Sobre o SIMQA",
    "Finalidade, interpretação dos produtos, bancos de dados e cuidados de uso.",
)

st.markdown(
    """
    ## Sistema Integrado de Monitoramento de Queimadas e Atmosfera

    O **SIMQA** é uma aplicação do Projeto PJ043 voltada à consulta sob demanda de informações
    ambientais disponíveis no Google Earth Engine. O sistema organiza diferentes sensores e bancos
    de dados em uma única interface, permitindo gerar mapas interativos, séries temporais e arquivos
    para análise posterior.

    O painel foi estruturado para apoiar atividades acadêmicas, técnicas e exploratórias relacionadas
    a queimadas, composição atmosférica, aerossóis, nuvens, precipitação, vegetação, temperatura da
    superfície, relevo, cobertura do solo e modificação humana.

    ## Como interpretar os resultados

    - **Focos de calor:** são detecções feitas por sensores. Uma mesma ocorrência pode aparecer em
      passagens ou varreduras sucessivas; portanto, a soma não equivale necessariamente ao número de
      incêndios únicos.
    - **Sentinel-5P:** os produtos representam, em geral, colunas atmosféricas integradas ou índices
      orbitais. Eles não devem ser interpretados diretamente como concentração respirada ao nível do solo.
    - **AOD MAIAC:** representa a carga óptica de aerossóis integrada na coluna atmosférica e pode ter
      lacunas sob nuvens ou condições inadequadas de recuperação.
    - **CHIRPS v3:** é usado para precipitação histórica diária. Como a ingestão no Earth Engine pode
      apresentar defasagem, o SIMQA consulta automaticamente a última cena realmente disponível.
    - **ERA5-Land Hourly:** é usado como alternativa para precipitação recente. O Earth Engine fornece
      precipitação horária em metros; o SIMQA converte para milímetros e soma as horas do período.
      Por ser uma reanálise, deve ser interpretado de forma diferente de uma medição direta de chuva.
    - **Produtos estáticos:** relevo e modificação humana não possuem seletor de data porque o catálogo
      utilizado não representa uma série temporal operacional.
    - **NRTI e NRT:** são adequados para acompanhamento rápido, mas podem sofrer revisões e não
      substituem produtos validados para análises científicas definitivas.

    ## Processamento

    O SIMQA realiza as operações somente depois da solicitação do usuário. Períodos longos, regiões
    extensas, sensores de alta resolução e o GOES com cadência de minutos podem exigir mais tempo.
    As informações técnicas de cada variável aparecem no painel lateral direito das páginas de análise,
    incluindo definição, disponibilidade, cálculo aplicado, unidade, limitações e acesso ao catálogo oficial.
    """
)

st.markdown("## Catálogo organizado por plataforma")
for group in product_groups():
    with st.expander(group):
        for key in products_in_group(group):
            product_metadata(PRODUCTS[key], compact=True)
            st.markdown("---")

st.markdown(
    """
    ## Uso responsável

    Os mapas e valores produzidos pelo sistema devem ser analisados considerando resolução espacial,
    frequência temporal, cobertura de nuvens, qualidade da recuperação, diferenças entre sensores e
    limitações próprias de cada algoritmo. Para relatórios ou publicações, registre o produto, a coleção,
    a banda, a escala, o período e o método fornecidos nos metadados do download.
    """
)
