# SIMQA — revisão V5.2.1

Esta revisão V5.2.1 foi preparada sobre a V5.2 do dashboard e mantém o `secrets.toml` fora do pacote.

## Ajuste da V5.2.1

- O aviso fixo da HOME sobre períodos superiores a sete dias foi removido.
- A HOME agora informa de forma geral que produtos de alta resolução, alta frequência temporal ou análises em áreas extensas podem exigir mais tempo de processamento.
- O novo aviso usa o ícone ⚙️ e evita associar a demora apenas ao tamanho do período.


## Alterações da V5.2 — precipitação recente

1. **CHIRPS v3 Daily Reanalysis foi mantido** (`UCSB-CHC/CHIRPS/V3/DAILY_RNL`) para histórico e climatologia;
2. o **GPM IMERG V07 foi removido** do catálogo do SIMQA nesta revisão;
3. foi adicionado **ERA5-Land Hourly** (`ECMWF/ERA5_LAND/HOURLY`) para precipitação mais recente;
4. a banda utilizada é `total_precipitation_hourly`, fornecida em metros por hora desagregada no Earth Engine;
5. o SIMQA converte cada cena horária para milímetros (`m × 1000`) e soma as horas do período;
6. a data máxima continua sendo detectada automaticamente a partir de `system:time_start`;
7. a interface mostra data e hora UTC da última cena ERA5-Land e alerta quando o último dia pode estar incompleto;
8. períodos longos de ERA5-Land recebem aviso adicional por envolverem muitas cenas horárias;
9. mapas, séries e downloads usam exatamente o mesmo cálculo do acumulado.

## Alterações principais

1. a página principal passa a aparecer como **🏠 HOME** na navegação;
2. `app.py` agora funciona como roteador usando `st.navigation`;
3. o GIF da HOME deixa de ser gerado pelo Earth Engine e passa a usar `assets/home_produtos.gif`, montado com exemplos reais fornecidos pelo projeto;
4. o GIF roda em loop e não adiciona processamento do Earth Engine à abertura da HOME;
5. remoção dos botões `❗` dos seletores e cards; as informações completas permanecem no painel direito das páginas de análise;
6. HOME reorganizada em três temas: queimadas/focos, atmosfera/qualidade do ar e ambiente/superfície, mantendo a identificação por banco/plataforma;
7. inclusão de indicadores rápidos na HOME;
8. botão **Gerar mapa** movido para a barra lateral esquerda, imediatamente abaixo do período e dos avisos de processamento;
9. correção da visualização categórica de **Cobertura do Solo — Copernicus CGLS 100 m**;
10. a cobertura do solo passa a usar remapeamento apenas visual dos códigos originais para índices consecutivos, evitando interpolação indevida de cores;
11. oceano e pixels desconhecidos ficam transparentes na visualização, preservando o mapa base;
12. a legenda lateral de cobertura do solo mostra nomes de classes e amostras de cor, sem exibir códigos hexadecimais da paleta.

## Aplicar sobre o dashboard atual

```bash
bash aplicar_atualizacao.sh \
  ~/Projeto-PJ043-2026/dashboard_pj043_sob_demanda_v2_build
```

O instalador cria um backup dos arquivos de código e preserva `.streamlit/secrets.toml`.

Depois:

```bash
cd ~/Projeto-PJ043-2026/dashboard_pj043_sob_demanda_v2_build
source .venv/bin/activate
pip install -r requirements.txt
streamlit cache clear
streamlit run app.py
```

Abra manualmente no Windows/WSL:

```text
http://localhost:8501
```

## Testes recomendados

- abrir **🏠 HOME** e confirmar que `home_produtos.gif` roda continuamente;
- usar um card da HOME e confirmar que o produto correto permanece selecionado ao gerar o mapa;
- testar **Cobertura do Solo** em América do Sul e confirmar cores categóricas e legenda lateral;
- confirmar que o oceano não aparece como grandes blocos azuis sobre o mapa base;
- selecionar período maior que sete dias e confirmar o aviso de demora e o botão **Gerar mapa** logo abaixo;
- testar produtos estáticos e confirmar ausência de seleção temporal;
- testar **CHIRPS v3** e confirmar que o calendário termina na última cena detectada;
- testar **ERA5-Land Hourly** e conferir a última cena, a conversão para mm e o aviso de possível dia parcial;
- testar mapas, séries e downloads antes do `git push`.

## Atualizar GitHub

```bash
git status
git add app.py modules pages assets requirements.txt .streamlit/config.toml .gitignore README_ATUALIZACAO.md CATALOGO_PRODUTOS.md
git commit -m "atualiza SIMQA para V5.2"
git push
```

Não envie `.streamlit/secrets.toml` nem chaves JSON ao GitHub.
