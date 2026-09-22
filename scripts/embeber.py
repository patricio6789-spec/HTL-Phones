#!/usr/bin/env python3
"""Inserta datos verificados para que catálogo y panel funcionen con doble clic."""
import json
import re
from actualizar import ROOT, atomic_text


def literal(data):
    # Evitar que texto del proveedor cierre el elemento script del documento.
    return json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def replace(html, name, value):
    pattern = re.compile(r'(const ' + re.escape(name) + r' = ).*?(;\n)', re.S)
    output, count = pattern.subn(lambda m: m[1] + literal(value) + m[2], html, count=1)
    if count != 1:
        raise ValueError(f'No se encontró el marcador {name}')
    return output


def main():
    config = json.loads((ROOT / 'data/config.json').read_text(encoding='utf-8'))
    outputs = []
    for name, source in [('index.html', 'productos'), ('panel.html', 'margenes')]:
        path = ROOT / name
        data = json.loads((ROOT / f'data/{source}.json').read_text(encoding='utf-8'))
        template = ROOT / 'templates/panel.html' if name == 'panel.html' else path
        html = replace(template.read_text(encoding='utf-8'), 'DATOS_EMBEBIDOS', data)
        if name == 'index.html':
            html = replace(html, 'CONFIG', config)
        outputs.append((path, html))
    for path, html in outputs:
        atomic_text(path, html)
        print('Actualizado:', path.name)


if __name__ == '__main__':
    main()
