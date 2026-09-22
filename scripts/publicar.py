#!/usr/bin/env python3
"""Prepara una carpeta pública por lista permitida. No despliega a Internet."""
import json
import shutil
from pathlib import Path
from actualizar import ROOT


def main():
    target = ROOT / 'sitio-publico'
    if target.exists():
        shutil.rmtree(target)
    (target / 'data').mkdir(parents=True)
    for name in ['index.html', 'data/productos.json']:
        shutil.copy2(ROOT / name, target / name)
    (target / '.nojekyll').write_text('', encoding='utf-8')
    public = json.loads((target / 'data/productos.json').read_text(encoding='utf-8'))
    assert 'margenes' not in public
    assert all('costo' not in p and 'margen' not in p for p in public['productos'])
    assert not (target / 'panel.html').exists()
    print('Listo: sitio-publico/ (catálogo y precios públicos; sin costos ni panel).')


if __name__ == '__main__':
    main()
