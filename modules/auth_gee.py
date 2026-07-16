#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import tempfile

import ee
import streamlit as st


@st.cache_resource(show_spinner=False)
def initialize_gee() -> bool:
    """Inicializa o Google Earth Engine localmente ou no Streamlit Cloud."""
    try:
        if "earthengine" in st.secrets:
            info = dict(st.secrets["earthengine"])
            project_id = info.pop("gee_project_id", None) or info.get("project_id")

            with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as f:
                json.dump(info, f)
                f.flush()
                credentials = ee.ServiceAccountCredentials(info["client_email"], f.name)
                ee.Initialize(credentials, project=project_id)
        else:
            project_id = os.environ.get("EE_PROJECT", "eng-scene-497515-t2")
            ee.Initialize(project=project_id)

        return True

    except Exception as exc:
        st.error("Erro ao inicializar o Google Earth Engine.")
        st.error(str(exc))
        st.info(
            "No Streamlit Cloud, configure os Secrets em Settings > Secrets. "
            "Localmente, use `earthengine authenticate` e defina `EE_PROJECT`.",
            icon="🔐",
        )
        st.stop()
