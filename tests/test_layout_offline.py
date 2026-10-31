"""Smoke tests sem credenciais GEE, executável também no laboratório.
python -m unittest discover -s tests -p 'test_layout_offline.py'
"""
from __future__ import annotations
from io import BytesIO
import unittest
from PIL import Image
from modules.export_image import render_board, png_to_jpeg, _fit_view
from modules.products import PRODUCTS, LANDCOVER_VALUES, LANDCOVER_PALETTE


class TestVigiaVisual(unittest.TestCase):
    def test_enquadramento_cidade(self):
        zoom,bbox=_fit_view(-47.45,-18.63,-47.35,-18.52,1450,720)
        self.assertGreaterEqual(zoom,8)
        self.assertLess(bbox[0],-47.4)
        self.assertGreater(bbox[2],-47.4)
        self.assertLess(bbox[1],-18.57)
        self.assertGreater(bbox[3],-18.57)

    def test_enquadramento_continental(self):
        zoom,bbox=_fit_view(-83,-56,-35,13,1450,720)
        self.assertGreaterEqual(zoom,0)
        self.assertLessEqual(zoom,7)
        self.assertLess(bbox[0],-60)
        self.assertGreater(bbox[2],-60)

    def test_scalas_fixadas_no_catalogo(self):
        self.assertEqual(len(PRODUCTS),25)
        for p in PRODUCTS.values():
            self.assertLess(p.vis['min'],p.vis['max'])
            self.assertTrue(p.vis['palette'])
        self.assertEqual(len(LANDCOVER_VALUES),len(LANDCOVER_PALETTE))

    def test_export_png_jpeg(self):
        map_image=Image.new('RGB',(1450,720),'#dae9df')
        src=PRODUCTS['Focos FIRMS MODIS']
        png=render_board(map_image,src.key,'Abadia dos Dourados - MG','2026-10-05','2026-10-11',
            src.source,['Região selecionada'],src.vis,
            {'short':'0 detecções rasterizadas','headline':'0 detecções rasterizadas'},'Claro',10)
        with Image.open(BytesIO(png)) as img:
            self.assertEqual(img.format,'PNG')
            self.assertEqual(img.size,(1600,1456))
        jpg=png_to_jpeg(png)
        with Image.open(BytesIO(jpg)) as img:
            self.assertEqual(img.format,'JPEG')
            self.assertEqual(img.size,(1600,1456))

    def test_export_categorico(self):
        map_image=Image.new('RGB',(1450,720),'#cee5d2')
        src=PRODUCTS['Cobertura do Solo']
        png=render_board(map_image,src.key,'Minas Gerais',None,None,src.source,
            [],src.vis,{'short':'7 classes','headline':'7 classes'},'Satélite',6)
        with Image.open(BytesIO(png)) as img:
            self.assertEqual(img.size,(1600,1566))


if __name__ == '__main__':unittest.main()
