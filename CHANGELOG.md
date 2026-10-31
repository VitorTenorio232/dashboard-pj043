# Histórico de mudanças

## 2026-10-31

### Novidades
- **Barra de escala** em todos os mapas gerados, logo abaixo do mapa e antes dos quadros de informação:
  - na prancha PNG/JPEG (Mapas e Downloads), com a latitude de referência e aviso de que, em áreas
    continentais, a distância varia com a latitude (projeção Web Mercator);
  - na página de mapas interativos, acompanhando o zoom do mapa.

## 2026-10-29

### Correções
- **NDVI travava ao ser escolhido:** a busca da data mais recente varria a coleção inteira do Sentinel-2
  (milhões de cenas) e passava de 10 minutos. Agora procura primeiro nos últimos dias (~3 s), para todos os produtos.
- **NDVI em áreas continentais:** com a América do Sul (padrão da página) eram ~38 mil cenas e vários minutos
  carregando. Agora o site mede área × período antes de processar e, se for pesado demais para 10 m, avisa na hora
  e sugere área menor ou período mais curto (Minas Gerais aceita até ~2 meses).

## 2026-10-26

### Novidades
- **Umidade do solo — NASA SMAP L3 9 km** (`NASA/SMAP/SPL3SMP_E/006`, 2015 em diante): média das passagens
  6h/18h com filtro de qualidade recomendada, em m³/m³.
- **Anomalia de umidade do solo — SMAP (experimental)**: mais úmido (azul) ou mais seco (marrom) que o normal
  da época do ano.

### Correções
- **Rodar localmente:** sem `secrets.toml`, o site dava erro em vez de usar o `earthengine authenticate`.
- **Limites administrativos:** a GAUL 2015 foi descontinuada no Earth Engine e tinha nomes sem acento
  ("Itajuba", "Sao Paulo") e uma opção "Name Unknown" na lista de estados. Agora: países do LSIB e
  estados/municípios da GAUL 2025, com acentos e ordem alfabética correta.
- **Downloads:** clicar num botão de download apagava os outros botões gerados; agora eles ficam.
  GeoTIFF grande demais não derruba mais os outros formatos: o site avisa e sugere a escala que cabe.
- **Prancha PNG/JPEG:** títulos longos (duas linhas) passavam por cima do subtítulo; números da legenda com vírgula.
- **Repositório:** um arquivo com `:` no nome (`…json:Zone.Identifier`) impedia clonar o projeto no Windows.

### Otimizações
- **Séries temporais** calculadas em lote no Earth Engine: ~10× mais rápidas (ex.: 30 dias de SMAP em
  Minas Gerais de ~50 s para ~4 s), com divisão automática do lote quando o GEE recusa por carga.
  Séries diárias agora vão até 1 ano (90 dias nos produtos de alta resolução).
- Gráfico da série liga os dias sem dado; legenda da série mostra a área e quantos intervalos têm dado.
- Botão dos cards da HOME com rótulo curto ("Abrir no mapa →"), que não fica mais cortado.

### Repositório
- README reescrito, `CHANGELOG.md`, `.gitattributes`, `.gitignore` organizado, `requirements-dev.txt`.
- Novo workflow **Testes do site** (lint + pytest + abertura da HOME) a cada push.
- Removido `modules/maps.py.bak`; notas da V5.2 movidas para `docs/historico/`.
