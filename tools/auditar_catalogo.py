#!/usr/bin/env python3
"""Auditoria do catálogo VIGIA: modo local seguro e modo opcional com GEE.

  python tools/auditar_catalogo.py --project .
  python tools/auditar_catalogo.py --project . --gee

Não lê, imprime nem salva credenciais.
"""
from __future__ import annotations
import argparse
import csv
from datetime import date, datetime, timezone
import importlib
from pathlib import Path
import json
import sys
import types

ap = argparse.ArgumentParser()
ap.add_argument('--project', type=Path, default=Path('.'))
ap.add_argument('--gee', action='store_true', help='Verificar datas reais e bandas com conta Earth Engine já autenticada')
ap.add_argument('--ee-project', default=None, help='GCP project id para ee.Initialize')
args = ap.parse_args()
base = args.project.resolve()
if not (base/'modules'/'products.py').exists():
    raise SystemExit('Arquivo modules/products.py não encontrado')
sys.path.insert(0,str(base))
if not args.gee:
    try:
        import ee
    except ImportError:
        sys.modules['ee'] = types.ModuleType('ee')
import modules.products as cat

warnings=[]; problems=[]; rows=[]
valid_kinds={'fire_modis','fire_viirs','fire_goes','maiac_aod','precip_sum','precip_era5land_sum','lst_modis','ndvi_sentinel2','static_image','static_collection','categorical_last','mean_collection'}
for key,p in cat.PRODUCTS.items():
    local=[]
    if key!=p.key: local.append('Chave do dicionário diferente de key')
    if p.kind not in valid_kinds: local.append(f'kind não implementado: {p.kind}')
    if p.scale<=0: local.append('resolução não positiva')
    if p.vis.get('max',0)<=p.vis.get('min',0): local.append('limites de visualização inválidos')
    palette=p.vis.get('palette',[])
    if not palette or any(len(x.lstrip('#'))!=6 or any(ch not in '0123456789abcdefABCDEF' for ch in x.lstrip('#')) for x in palette):
        local.append('paleta inválida')
    if p.temporal:
        if not p.collection: local.append('produto temporal sem coleção')
        if p.availability_start is None: local.append('data inicial não informada')
        else:
            try: beg=date.fromisoformat(p.availability_start)
            except Exception: local.append('data inicial inválida'); beg=None
        if p.availability_end:
            try:
                fin=date.fromisoformat(p.availability_end)
                if beg is not None and beg > fin: local.append('início posterior ao fim')
            except Exception: local.append('data final inválida')
    elif p.availability_start or p.availability_end: local.append('produto estático com janela temporal artificial')
    if p.kind.startswith('fire_') and 'detecções' not in p.unit and 'varredura' not in p.unit: local.append('unidade de focos ambígua')
    if p.kind in {'precip_sum','precip_era5land_sum'} and p.unit!='mm': local.append('precipitação não convertida em mm')
    if p.kind=='categorical_last' and not p.temporal: local.append('categorical_last requer datas')
    rows.append({
        'produto':key,'fonte':p.source,'colecao_ou_imagem':p.collection or p.image_id,
        'banda':(','.join(p.band) if isinstance(p.band,list) else p.band),
        'tipo':p.kind,'inicio_declarado':p.availability_start or '',
        'fim_declarado':p.availability_end or '', 'temporal':p.temporal,
        'unidade':p.unit,'escala_nominal_m':p.scale,'min_visual':p.vis.get('min'),
        'max_visual':p.vis.get('max'),'categoria':p.group,
        'validacao_local':'OK' if not local else 'ATENÇÃO: '+'; '.join(local),
        'ultima_cena_gee':'NÃO TESTADO', 'bandas_gee':'NÃO TESTADO',
    })
    if local: problems.extend(f'{key}: {x}' for x in local)

# Nota científica: escalas são fixas por produto, não universalmente comparáveis.
if len({(p.vis['min'],p.vis['max']) for p in cat.PRODUCTS.values()}) > 1:
    warnings.append('Escalas definidas por produto, não uma escala universal comum entre sensores e variáveis.')
warnings += [
    'O valor em focos é soma de detecções rasterizadas no recorte, não incêndios independentes.',
    'NDVI Sentinel-2 usa filtro de nebulosidade por cena; o código não aplica máscara pixel a pixel de nuvens.',
    'LST MODIS não aplica no código de origem uma máscara explícita por QA de pixel.',
    'A série temporal estática usa data interna artificial, removida da saída exibida; verificar mensal/diário.',
    'Produtos GEE atualizam com latência; fim = data mais recente da coleção, não necessariamente hoje.',
    'A geometria administrativa GAUL 2015 pode diferir de limites oficiais atuais do IBGE.',
]
if args.gee:
    import ee
    try:
        ee.Initialize(project=args.ee_project or __import__('os').environ.get('EE_PROJECT'))
    except Exception as ex:
        print('Não foi possível autenticar GEE:',type(ex).__name__,str(ex)[:200])
        raise SystemExit(2)
    for row in rows:
        p=cat.PRODUCTS[row['produto']]
        try:
            if p.kind=='static_image': obj=ee.Image(p.image_id)
            else:
                ic=ee.ImageCollection(p.collection)
                if p.temporal:
                    milliseconds=ic.aggregate_max('system:time_start').getInfo()
                    row['ultima_cena_gee']=(datetime.fromtimestamp(milliseconds/1000,tz=timezone.utc).isoformat() if milliseconds is not None else 'SEM CENAS')
                obj=ic.sort('system:time_start',False).first() if p.temporal else ic.first()
            bands=ee.Image(obj).bandNames().getInfo()
            row['bandas_gee']=', '.join(map(str,bands))
            requested=[p.band] if isinstance(p.band,str) else p.band
            if not all(b in bands for b in requested):
                problems.append(f"{p.key}: banda(s) não encontrada(s) na coleção atual: {requested}")
        except Exception as ex:
            row['bandas_gee']='ERRO: '+type(ex).__name__
            warnings.append(f"{p.key}: verificação GEE falhou ({type(ex).__name__})")

out=base/'auditoria_resultados'
out.mkdir(exist_ok=True)
with (out/'matriz_produtos.csv').open('w',newline='',encoding='utf-8-sig') as f:
    writer=csv.DictWriter(f,fieldnames=rows[0].keys(),delimiter=';')
    writer.writeheader();writer.writerows(rows)
report={
    'gerado_utc':datetime.now(timezone.utc).isoformat(),
    'catalogo_produtos':len(rows),
    'gee_validado':args.gee,
    'erros_locais':problems,
    'notas':warnings,
    'resultado':'REVISÃO PENDENTE' if problems else ('VERIFICAÇÕES LOCAIS OK; VALIDAR NO GEE' if not args.gee else 'CONSULTA GEE REALIZADA; REVISAR NOTAS')
}
(out/'auditoria.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Produtos:',len(rows))
print('Problemas:',len(problems))
print('GEE:', 'consultado' if args.gee else 'não consultado')
print('Arquivos:',out)
for p in problems:print('PROBLEMA:',p)
for n in warnings:print('NOTA:',n)
raise SystemExit(1 if problems else 0)
