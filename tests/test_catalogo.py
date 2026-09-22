"""Pruebas de regresión: importación, stock y cálculo de comisiones."""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import actualizar as app
from embeber import literal


def table(rows, headers=('Rubro', 'Descripción', 'Stock', 'USD')):
    return '<table><thead>'+''.join('<th>'+h+'</th>' for h in headers)+'</thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(c)+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table>'


def row(name='IPHONE 18 PRO 256GB. SILVER (eSIM)', price=1617, stock='Medio'):
    return {'descripcion': name, 'usd': price, 'stock': stock, 'rubro': 'CELULAR - APPLE', 'nuevo': False}


class CatalogTests(unittest.TestCase):
    def test_supplier_html_and_new_badge(self):
        source=table([('CELULAR - APPLE', '<a>IPHONE 18 PRO 256GB. SILVER (eSIM) <span>Nuevo</span></a>', '<span>Medio</span>', '<div><span>1617</span><i></i></div>')])
        parsed=app.parse_html(source)
        self.assertEqual(len(parsed),1)
        p=app.product(parsed[0])
        self.assertEqual((p['modelo'],p['capacidad'],p['color'],p['stock'],p['usd']),('iPhone 18 Pro','256 GB','Silver','Medio',1617))
        self.assertTrue(p['nuevo'])
        self.assertNotIn('NUEVO',p['id'])
        self.assertEqual(p['id'],app.key(row()))

    def test_reordered_visible_columns_and_inference(self):
        source=table([('Alto','816','IPHONE 16 128GB. TEAL (SIM FISICA-eSIM)')],('Stock','USD','Descripción'))
        p=app.product(app.parse_html(source)[0])
        self.assertEqual(p['marca'],'Apple')
        self.assertEqual(p['sim'],'SIM física + eSIM')

    def test_sim_options_do_not_collide(self):
        esim=row('IPHONE 16 128GB. TEAL (eSIM)')
        physical=row('IPHONE 16 128GB. TEAL (SIM FISICA-eSIM)')
        self.assertNotEqual(app.key(esim),app.key(physical))
        self.assertNotEqual(app.product(esim)['grupo_id'],app.product(physical)['grupo_id'])

    def test_decimal_prices(self):
        for text, expected in [('1617',1617),('1.617',1617),('1,617',1617),('1.617,50',1617.5),('1,617.50',1617.5),('1617.50',1617.5),('1617,50',1617.5)]:
            with self.subTest(text=text): self.assertEqual(app.money(text),expected)
        for invalid in ['0','-5','sin precio','12,3,4']:
            with self.subTest(invalid=invalid), self.assertRaises(Exception): app.money(invalid)

    def test_invalid_source_never_silently_skips_rows(self):
        for bad in ['<html>Acceso</html>',table([]),table([('CELULAR - APPLE','iPhone','Bajo','-1')]),table([('Apple','iPhone')])]:
            with self.subTest(source=bad), self.assertRaises(ValueError): app.parse_html(bad)
        r=('CELULAR - APPLE','IPHONE 18 PRO 256GB. SILVER (eSIM)','Bajo','1617')
        with self.assertRaises(ValueError): app.parse_html(table([r,r]))

    def test_unknown_stock_not_claimed_available(self):
        raw=table([('CELULAR - APPLE','IPHONE 18 PRO 256GB. SILVER (eSIM)','Consultar','1617')])
        p=app.product(app.parse_html(raw)[0])
        self.assertEqual(p['estado'],'consultar')
        self.assertEqual(p['stock'],'Consultar')

    def test_commission_matches_public_price_and_markup(self):
        public,private=app.build([row()],[row(price=1550)],markup=5)
        self.assertEqual(public['productos'][0]['usd'],1697.85)
        self.assertEqual(private['margenes'][0]['venta'],1697.85)
        self.assertEqual(private['margenes'][0]['margen'],147.85)
        self.assertEqual(private['margenes'][0]['pct'],8.71)
        self.assertNotIn('costo',public['productos'][0])

    def test_missing_cost_is_pending_and_not_zero(self):
        public,private=app.build([row()],None)
        self.assertEqual(len(public['productos']),1)
        self.assertIsNone(private['margenes'][0]['costo'])
        self.assertIsNone(private['margenes'][0]['margen'])
        self.assertFalse(private['costos_verificados'])

    def test_wholesale_only_does_not_expand_public_catalog(self):
        public,private=app.build([row()],[row(price=1550),row('IPHONE 99 1TB BLACK',price=2000)])
        self.assertEqual(len(public['productos']),1)
        self.assertEqual(len(private['solo_especiales']),1)

    def test_disappeared_variant_removed_and_stock_changed(self):
        first,_=app.build([row(stock='Alto'),row('IPHONE 17 256GB. BLACK (eSIM)',price=1045)],None)
        public,private=app.build([row(stock='Bajo',price=1600)],None,first)
        self.assertEqual(len(public['productos']),1)
        self.assertEqual(len(private['cambios']['bajas']),1)
        self.assertEqual(len(private['cambios']['stock']),1)
        self.assertEqual(len(private['cambios']['precios']),1)

    def test_script_embedding_cannot_close_script(self):
        text=literal({'nombre':'</script><script>alert(1)</script>'})
        self.assertNotIn('<',text)
        self.assertEqual(json.loads(text)['nombre'],'</script><script>alert(1)</script>')

    def test_failed_update_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir()
            (root/'data/config.json').write_text('{"recargo":0}')
            (root/'data/productos.json').write_text('{"productos":[]}')
            (root/'data/margenes.json').write_text('COSTOS ORIGINALES')
            bad=root/'broken.html';bad.write_text('<html>No hay lista</html>')
            with patch.object(app,'ROOT',root),patch.object(sys,'argv',['actualizar','--minorista-html',str(bad),'--sin-costos']),contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(app.main(),1)
            self.assertEqual((root/'data/productos.json').read_text(),'{"productos":[]}')
            self.assertEqual((root/'data/margenes.json').read_text(),'COSTOS ORIGINALES')

    def test_massive_drop_keeps_last_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir()
            (root/'data/config.json').write_text('{"recargo":0}')
            original=json.dumps({'productos':[{'id':str(i)} for i in range(30)]})
            (root/'data/productos.json').write_text(original)
            small=root/'small.html';small.write_text(table([('CELULAR - APPLE','IPHONE 18 PRO 256GB. SILVER (eSIM)','Medio','1617')]))
            with patch.object(app,'ROOT',root),patch.object(sys,'argv',['actualizar','--minorista-html',str(small),'--sin-costos']),contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(app.main(),1)
            self.assertEqual((root/'data/productos.json').read_text(),original)


if __name__ == '__main__': unittest.main()
