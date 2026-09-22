#!/usr/bin/env python3
"""Sincroniza minorista y calcula comisiones. Python 3.10+, sin dependencias."""
import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
AR = timezone(timedelta(hours=-3))
URL_MINORISTA = 'https://ventas.extranet-elec.com/minorista/'
URL_ESPECIALES = 'https://ventas.extranet-elec.com/especiales/'
GROUPS = {'CELULAR': 'Celulares', 'TABLET': 'Tablets', 'NOTEBOOK': 'Notebooks', 'WATCH': 'Smartwatches', 'ACCESORIO': 'Accesorios'}
PART = re.compile(r'\(([A-Z0-9]{4,10}/[A-Z])\)', re.I)
SIM = re.compile(r'\((?:SIM\s*F[IÍ]SICA\s*[- /]?\s*)?E?SIM\)', re.I)
BULK = re.compile(r'\bX\s*\d+\s*U\$\s*[\d.,]+', re.I)


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFD', str(value)) if unicodedata.category(c) != 'Mn').upper()


def clean_description(value):
    return re.sub(r'\s+', ' ', re.sub(r'\bNUEVO\s*$', '', value, flags=re.I)).strip()


def key(row):
    desc = clean_description(row['descripcion'])
    part = PART.findall(desc)
    if part:
        return part[-1].upper()
    text = BULK.sub(' ', SIM.sub(' ', norm(desc))).replace('-INGLES', ' ')
    base = re.sub(r'[^A-Z0-9]+', ' ', text).strip()
    return base + ('__SIM_FISICA' if 'FISICA' in norm(desc) else '')


def money(value):
    if re.search(r'[-−]', str(value)):
        raise ValueError('El precio no puede ser negativo')
    text = re.sub(r'[^\d.,]', '', str(value))
    if not text:
        raise ValueError('Precio vacío')
    if '.' in text and ',' in text:
        decimal = '.' if text.rfind('.') > text.rfind(',') else ','
        text = text.replace(',' if decimal == '.' else '.', '').replace(decimal, '.')
    elif '.' in text or ',' in text:
        sep = '.' if '.' in text else ','
        parts = text.split(sep)
        if len(parts[-1]) == 3:
            text = ''.join(parts)
        elif len(parts) == 2 and len(parts[-1]) in (1, 2):
            text = '.'.join(parts)
        else:
            raise ValueError(f'Precio ambiguo: {value}')
    number = float(Decimal(text))
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f'Precio inválido: {value}')
    return number


class Tables(HTMLParser):
    """Admite encabezados th fuera de tr, como en la página del proveedor."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table = self.row = self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'table':
            self.table = {'headers': [], 'rows': []}
            self.tables.append(self.table)
        elif self.table is not None:
            if tag == 'tr':
                self.row = []
            elif tag in ('th', 'td'):
                self.cell = {'text': [], 'href': None, 'tag': tag}
            elif self.cell is not None:
                if tag == 'a':
                    self.cell['href'] = attrs.get('href')
                elif tag == 'br':
                    self.cell['text'].append(' ')

    def handle_data(self, data):
        if self.cell is not None:
            self.cell['text'].append(data)

    def handle_endtag(self, tag):
        if tag in ('th', 'td') and self.cell is not None:
            self.cell['text'] = ' '.join(' '.join(self.cell['text']).split())
            if self.cell['tag'] == 'th':
                self.table['headers'].append(self.cell['text'])
            elif self.row is not None:
                self.row.append(self.cell)
            self.cell = None
        elif tag == 'tr' and self.table is not None:
            if self.row:
                self.table['rows'].append(self.row)
            self.row = None
        elif tag == 'table':
            self.table = self.cell = self.row = None


def infer_category(desc):
    text = norm(desc)
    if text.startswith(('IPHONE', 'GALAXY', 'POCO', 'REDMI', 'XIAOMI')):
        return 'CELULAR - ' + ('APPLE' if text.startswith('IPHONE') else 'SAMSUNG' if text.startswith('GALAXY') else 'XIAOMI')
    if text.startswith('IPAD'):
        return 'TABLET - APPLE'
    if text.startswith('MACBOOK'):
        return 'NOTEBOOK - APPLE'
    if text.startswith('WATCH'):
        return 'WATCH - APPLE'
    return 'ACCESORIO - APPLE' if text.startswith(('AIRPODS', 'PENCIL')) else 'ACCESORIO - OTRA'


def parse_html(html):
    parser = Tables()
    parser.feed(html)
    for table in parser.tables:
        headers = [norm(h) for h in table['headers']]
        def col(*names):
            return next((i for i, h in enumerate(headers) if any(n in h for n in names)), None)
        desc, stock, price, category = col('DESCRIPCION'), col('STOCK'), col('USD', 'PRECIO'), col('RUBRO')
        if None in (desc, stock, price):
            continue
        rows = []
        for cells in table['rows']:
            if len(cells) <= max(desc, stock, price):
                raise ValueError('La tabla contiene una fila incompleta')
            raw = cells[desc]['text']
            if not raw:
                raise ValueError('Producto sin descripción')
            level = norm(cells[stock]['text'])
            level = {'ALTO':'Alto', 'MEDIO':'Medio', 'BAJO':'Bajo', 'SIN STOCK':'Sin stock', 'AGOTADO':'Sin stock', '0':'Sin stock'}.get(level, 'Consultar')
            rows.append({'rubro': cells[category]['text'] if category is not None and category < len(cells) else infer_category(raw),
                         'descripcion': clean_description(raw), 'stock': level, 'usd': money(cells[price]['text']),
                         'nuevo': bool(re.search(r'\bNUEVO\s*$', raw, re.I)), 'url': cells[desc]['href']})
        if not rows:
            raise ValueError('La lista está vacía')
        seen = set()
        for row in rows:
            ident = key(row)
            if ident in seen:
                raise ValueError(f"Producto duplicado: {row['descripcion']}")
            seen.add(ident)
        return rows
    raise ValueError('No se encontró la tabla con Descripción, Stock y USD')


def download(url):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (HoldTheLine catalog sync)', 'Accept': 'text/html'})
    with urlopen(req, timeout=35) as response:
        raw = response.read(5_000_001)
        if len(raw) > 5_000_000:
            raise ValueError('La respuesta excede el tamaño esperado')
        return parse_html(raw.decode(response.headers.get_content_charset() or 'utf-8', 'replace'))


WORDS = {'IPHONE':'iPhone', 'IPAD':'iPad', 'MACBOOK':'MacBook', 'AIRPODS':'AirPods', 'WIFI':'WiFi', 'ESIM':'eSIM', 'USB-C':'USB-C', 'GPS':'GPS', 'CPU':'CPU', 'GPU':'GPU', 'SSD':'SSD', 'POCO':'POCO', 'C/CANCELACION':'con cancelación', 'DE':'de', 'S/M':'S/M', 'M/L':'M/L', 'SE':'SE'}


def pretty(text):
    return ' '.join(WORDS.get(w.upper(), w if any(c.isdigit() for c in w) else w.capitalize()) for w in text.split()).strip(' .-')


def product(row):
    desc = clean_description(row['descripcion'])
    raw = PART.sub('', BULK.sub('', SIM.sub('', desc))).replace('-INGLES', '').strip(' .-')
    raw = re.sub(r'(\d+(?:GB|TB))\.', r'\1', raw)
    tipo, _, marca = norm(row['rubro']).partition(' - ')
    tipo, marca = tipo.strip(), marca.strip().capitalize() or 'Otra'
    storage, ram, color, model, details = '', '', '', pretty(raw), []
    if tipo == 'CELULAR':
        match = re.search(r'(?:(\d+)\s*/\s*)?(\d+\s*(?:GB|TB))\.?', raw, re.I)
        if match:
            ram = (match[1] + ' GB') if match[1] else ''
            storage = re.sub(r'(\d+)\s*(GB|TB)', r'\1 \2', match[2])
            model = pretty(re.sub(r'\b[A-Z]\d{3}[A-Z]\b', '', raw[:match.start()])).replace('5G.', '5G').strip()
            color = pretty(re.sub(r'^\s*(?:5G\s+)?', '', raw[match.end():])).strip(' .-')
        if 'ESIM' in norm(desc):
            details.append('SIM física + eSIM' if 'FISICA' in norm(desc) else 'eSIM')
    elif tipo == 'TABLET':
        match = re.search(r'(\d+)(GB|TB)\.?', raw, re.I)
        if match:
            storage = match[1] + ' ' + match[2].upper()
            model = pretty(raw[:match.start()]).strip()
            color = pretty(raw[match.end():]).strip(' .-')
    elif tipo == 'NOTEBOOK':
        match = re.search(r'MACBOOK\s+(AIR|PRO|NEO)\s+([A-Z0-9]+(?:\s+PRO)?)', raw, re.I)
        model = pretty(match[0]) if match else 'MacBook'
        mram = re.search(r'(\d+)\s*GB', raw, re.I)
        mssd = re.search(r'(\d+)\s*(SSD|TB)', raw, re.I)
        ram = mram[1] + ' GB' if mram else ''
        storage = mssd[1] + (' TB' if mssd[2].upper() == 'TB' else ' GB') if mssd else ''
        screen = re.search(r'(\d+(?:\.\d+)?)"', raw)
        if screen:
            model += ' · ' + screen[1] + '″'
        colors = re.findall(r'\(([^)]+)\)', raw)
        color = pretty(colors[-1]) if colors else ''
        details.append('Teclado en inglés')
    elif tipo == 'WATCH':
        match = re.match(r'WATCH\s+(.*?)\s+(?:(GPS)\s+)?(\d+mm)\s*(GPS)?\s*(.*)', raw, re.I)
        if match:
            model = 'Apple Watch ' + pretty(match[1])
            storage = match[3].lower().replace('mm', ' mm')
            tail = match[5]
            color = pretty(re.split(r'ALUMINIUM CASE', tail, flags=re.I)[0]).strip(' -')
            details.append(pretty(tail))
    else:
        model = pretty(raw)
        if model.startswith('Pencil'):
            model = 'Apple ' + model
    parts = PART.findall(desc)
    group_source = '|'.join([tipo, marca, model, storage, ram, details[0] if tipo == 'CELULAR' and details else ''])
    if tipo not in ('CELULAR', 'TABLET', 'NOTEBOOK', 'WATCH'):
        group_source = key(row)
    return {'id': key(row), 'grupo_id': hashlib.sha256(group_source.encode()).hexdigest()[:16],
            'tipo': tipo, 'grupo': GROUPS.get(tipo, pretty(tipo)), 'marca': marca,
            'nombre': pretty(raw), 'modelo': model, 'capacidad': storage, 'ram': ram,
            'color': color, 'detalles': details, 'sku': parts[-1] if parts else None,
            'stock': row['stock'], 'usd': row['usd'], 'nuevo': row.get('nuevo', False),
            'esim': bool(SIM.search(desc)), 'sim': details[0] if tipo == 'CELULAR' and details else None,
            'estado': 'disponible' if row['stock'] in ('Alto', 'Medio', 'Bajo') else 'consultar',
            'descripcion_original': desc}


def round_price(value):
    return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def build(retail, costs, previous=None, markup=0):
    stamp = datetime.now(AR).isoformat(timespec='seconds')
    costmap = {key(r): r for r in (costs or [])}
    products, margins, alerts = [], [], []
    for row in retail:
        p = product(row)
        p['usd'] = round_price(Decimal(str(row['usd'])) * (1 + Decimal(str(markup)) / 100))
        products.append(p)
        cost = costmap.get(p['id'])
        value = cost['usd'] if cost else None
        margin = round_price(p['usd'] - value) if value is not None else None
        margins.append({'id': p['id'], 'nombre': p['nombre'], 'stock': p['stock'], 'marca': p['marca'], 'nuevo': p['nuevo'],
                        'precio_lista': row['usd'], 'venta': p['usd'], 'costo': value, 'margen': margin,
                        'pct': round(margin / p['usd'] * 100, 2) if margin is not None else None})
        if value is None:
            alerts.append({'tipo': 'sin_costo', 'nombre': p['nombre'], 'detalle': 'No hay costo verificado en esta actualización.'})
        elif margin <= 0:
            alerts.append({'tipo': 'margen_negativo', 'nombre': p['nombre'], 'detalle': f"Venta USD {p['usd']:g} / costo USD {value:g}."})
    old = {p['id']: p for p in (previous or {}).get('productos', [])}
    current = {p['id']: p for p in products}
    changes = {'altas': [], 'bajas': [], 'precios': [], 'stock': []}
    if old:
        changes['altas'] = [{'id': p['id'], 'nombre': p['nombre']} for p in products if p['id'] not in old]
        changes['bajas'] = [{'id': p['id'], 'nombre': p['nombre']} for p in old.values() if p['id'] not in current]
        for p in products:
            before = old.get(p['id'])
            if not before:
                continue
            if before.get('usd') != p['usd']:
                changes['precios'].append({'id': p['id'], 'nombre': p['nombre'], 'antes': before.get('usd'), 'ahora': p['usd']})
            if before.get('stock') != p['stock']:
                changes['stock'].append({'id': p['id'], 'nombre': p['nombre'], 'antes': before.get('stock'), 'ahora': p['stock']})
    order = {name: i for i, name in enumerate(GROUPS)}
    products.sort(key=lambda p: (order.get(p['tipo'], 99), not p['nuevo'], p['marca'], -p['usd'], p['nombre']))
    public = {'schema': 2, 'generado': stamp, 'fuente': URL_MINORISTA, 'stock_tipo': 'nivel', 'recargo_pct': markup,
              'total_variantes': len(products), 'total_modelos_capacidades': len({p['grupo_id'] for p in products}), 'productos': products}
    private = {'schema': 2, 'generado': stamp, 'costos_verificados': costs is not None,
               'comparado_con': (previous or {}).get('generado'), 'recargo_pct': markup, 'margenes': margins,
               'alertas': alerts, 'total_productos': len(products), 'cambios': changes,
               'solo_especiales': [{'id': key(r), 'nombre': pretty(r['descripcion'])} for r in (costs or []) if key(r) not in current]}
    return public, private


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=path.parent, prefix='.tmp-')
    try:
        with os.fdopen(handle, 'w', encoding='utf-8', newline='\n') as file:
            file.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minorista-html', type=Path, help='Importar una página guardada del proveedor')
    parser.add_argument('--especiales-html', type=Path)
    parser.add_argument('--sin-costos', action='store_true')
    parser.add_argument('--permitir-reduccion-masiva', action='store_true', help='Aceptar una reducción verificada mayor al 50%%')
    args = parser.parse_args()
    try:
        config = json.loads((ROOT / 'data/config.json').read_text(encoding='utf-8'))
        markup = float(config.get('recargo', 0))
        if not math.isfinite(markup) or not 0 <= markup <= 1000:
            raise ValueError('El recargo debe estar entre 0 y 1000%')
        retail = parse_html(args.minorista_html.read_text(encoding='utf-8')) if args.minorista_html else download(URL_MINORISTA)
        previous_path = ROOT / 'data/productos.json'
        previous = json.loads(previous_path.read_text(encoding='utf-8')) if previous_path.exists() else None
        previous_count = len((previous or {}).get('productos', []))
        if previous_count >= 20 and len(retail) < previous_count * .5 and not args.permitir_reduccion_masiva:
            raise ValueError(f'La lista pasó de {previous_count} a {len(retail)} filas. Revisá el proveedor antes de aceptar la reducción')
    except Exception as error:
        print(f'ERROR: {error}. No se modificaron los datos.', file=sys.stderr)
        return 1
    costs = None
    if not args.sin_costos:
        try:
            costs = parse_html(args.especiales_html.read_text(encoding='utf-8')) if args.especiales_html else download(URL_ESPECIALES)
        except Exception as error:
            print(f'AVISO: no se pudieron verificar los costos ({error}); el catálogo se actualizará y el panel mostrará costos pendientes.', file=sys.stderr)
    public, private = build(retail, costs, previous, markup)
    for name, data in (('productos', public), ('margenes', private)):
        atomic_text(ROOT / f'data/{name}.json', json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(f"Actualizado: {public['total_variantes']} variantes / {public['total_modelos_capacidades']} modelos y capacidades.")
    print('Stock: niveles del proveedor, sin cantidades exactas. Fecha:', public['generado'])
    print('Cambios:', ', '.join(f'{len(rows)} {name}' for name, rows in private['cambios'].items()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
