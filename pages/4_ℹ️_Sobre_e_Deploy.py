#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from modules.ui import load_css, page_title
st.set_page_config(layout='wide', page_title='PJ043 | Sobre', page_icon='ℹ️')
load_css('assets/style.css')
page_title('ℹ️ Sobre e Deploy', 'Resumo da estrutura e do processo de publicação no GitHub/Streamlit Cloud.')
st.markdown('''
## Estrutura do aplicativo
```text
dashboard_pj043_sob_demanda/
├── app.py
├── pages/
├── modules/
├── assets/style.css
├── requirements.txt
├── .gitignore
└── .streamlit/config.toml
```
## Segurança
Não envie para o GitHub:
```text
.streamlit/secrets.toml
*.json
```
As credenciais devem ser colocadas apenas nos **Secrets** do Streamlit Cloud.
''')
