# Hold the Line · Versión 2.0

Catálogo de equipos y panel de comisiones, continuado a partir del proyecto original.

Los celulares se presentan en secciones separadas por marca (Apple, Samsung, Xiaomi y las nuevas marcas que incorpore el proveedor). Dentro de cada marca, el orden inicial es de menor a mayor precio. Los otros criterios de orden también se aplican dentro de cada grupo.

## Para verlo ahora

1. Descomprimí todo el ZIP.
2. Abrí `index.html` con Chrome, Edge o Firefox. Funciona con doble clic, incluso sin servidor.
3. Abrí `panel.html` para revisar costos, comisiones y simular una venta.

El catálogo tiene los datos verificados en la fecha que figura arriba. No es una conexión en vivo con el proveedor al abrir el HTML.

## Qué incluye esta versión

- Modelos agrupados por capacidad, RAM y conectividad, con selector de color.
- Stock alto, medio o bajo de cada variante; nunca se inventan cantidades.
- Búsqueda por modelo, color o código; filtros combinables y orden por precio.
- Vista en tarjetas o lista, adaptación a pantallas pequeñas y lista descargable en CSV.
- Consulta con cantidades, total y texto preparado para WhatsApp. La selección se conserva en ese navegador cuando permite almacenamiento local.
- Fecha y hora de la lista, en Argentina, en formato de 24 horas. Aviso cuando tiene más de 14 horas.
- Panel con costos verificados, simulador con cantidades y descuento total, exportación y comparación de cambios.
- Actualizador que incorpora altas y retira los productos que desaparecen de la lista minorista.
- Carpeta `sitio-publico`, que contiene únicamente el catálogo y los precios públicos.

Se mantuvieron el WhatsApp **5491137832111**, Instagram **holdtheline.phones**, recargo **0%** y las condiciones comerciales del archivo original.

## Actualizar precios y stock en tu PC

Necesitás Python 3.10 o posterior. No requiere instalar otras librerías.

**Windows:** ejecutá `ACTUALIZAR.bat`. Cuando termine, volvé a abrir el catálogo y el panel.

**Mac / Linux:** ejecutá `sh actualizar.sh` desde la carpeta del proyecto.

También se pueden ejecutar los pasos por separado:

```bash
python scripts/actualizar.py
python scripts/embeber.py
python scripts/publicar.py
```

El primer paso consulta las dos listas del proveedor, el segundo inserta los datos dentro del HTML para abrirlo solo y el tercero prepara la carpeta publicable. Ningún paso local publica a Internet.

El botón **Revisar catálogo** de la web vuelve a leer la última lista publicada en tu sitio. No hace una consulta directa al proveedor. En un HTML abierto con doble clic informa que estás viendo una copia guardada; ejecutá el actualizador para obtener una nueva lista.

## Fuentes y reglas

- [Lista minorista](https://ventas.extranet-elec.com/minorista/): productos, niveles de stock y precios de venta.
- [Lista especiales](https://ventas.extranet-elec.com/especiales/): costo para calcular la comisión, como en el proyecto original.
- El stock proviene exclusivamente de minorista. El nivel no implica unidades exactas ni garantiza disponibilidad al momento de la compra.
- Un producto que solo figura en especiales queda registrado en el JSON interno y no se incorpora al catálogo público.
- Los códigos de parte identifican las variantes que los tienen. En los demás casos se normaliza la descripción y se diferencia SIM física de eSIM.
- La etiqueta “Nuevo” no forma parte del identificador, para que el producto no cambie de identidad cuando desaparezca esa etiqueta.
- Si falla minorista, cambia la tabla, aparece un precio inválido o queda vacía, se conserva la lista anterior y se interrumpe la actualización.
- Una caída superior al 50% en una lista de al menos 20 variantes requiere revisar la fuente y ejecutar explícitamente `--permitir-reduccion-masiva` si la reducción es real.
- Si falla especiales, minorista se actualiza. Todos los costos y las comisiones quedan pendientes: no se reutilizan costos antiguos como actuales.
- Comisión = precio de venta menos costo. El margen porcentual se calcula sobre la venta. No incluye otros gastos o impuestos.
- Los cambios del panel se comparan con el archivo local anterior. La primera entrega compara contra el catálogo original del 7/9/2026. Si cambia la nomenclatura del proveedor, puede registrarse una baja y un alta de una variante equivalente.

## WhatsApp, Instagram y recargo

Editá `data/config.json` y volvé a ejecutar los tres pasos de actualización.

```json
{
  "whatsapp": "5491137832111",
  "instagram": "holdtheline.phones",
  "recargo": 0
}
```

`recargo` es un porcentaje agregado al precio minorista, aplicado por el actualizador. El catálogo y las comisiones usan el mismo precio final, redondeado a dos decimales.

Para cambiar textos o diseño, editá `index.html`. Para cambiar el panel, editá `templates/panel.html`: `panel.html` se vuelve a generar desde esa plantilla.

## Publicación

Para una publicación manual en un hosting estático, subí **solo el contenido de `sitio-publico`**. El proyecto completo incluye costos y comisiones y se conserva para uso interno.

Ocultar el enlace al panel o poner `noindex` no restringe el acceso. Un repositorio privado tampoco vuelve privada una página de GitHub Pages. Por eso el paquete público se construye con una lista explícita de archivos: `index.html`, `data/productos.json` y `.nojekyll`.

### Actualización programada con GitHub Pages

Se incluye `.github/workflows/actualizar.yml`, preparado para la rama `main`:

1. Subí el código al repositorio. Si el repositorio es público, **no subas `panel.html` ni `data/margenes.json`**. El `.gitignore` los excluye al usar Git, pero no protege una carga manual desde la web ni archivos ya subidos anteriormente. La plantilla `templates/panel.html`, sin datos, sí se puede subir.
2. En Settings → Pages → Build and deployment → Source, seleccioná **GitHub Actions**.
3. En Actions, ejecutá **Actualizar catálogo y publicar**.
4. Revisá que la ejecución finalice correctamente y abrí la dirección que entregue GitHub.

La tarea consulta minorista **cada hora, de 8:17 a 19:17**, hora argentina, de lunes a viernes. GitHub puede demorar o suspender las ejecuciones; revisá su estado en Actions. Al cargar código en `main` o ejecutar manualmente también actualiza. Si falla la importación, no reemplaza la publicación existente.

El workflow procesa únicamente información pública y publica `sitio-publico`. El panel con costos se actualiza en tu PC con `ACTUALIZAR.bat`; no se publica ni queda en el artefacto de Pages.

**Esta entrega no creó un repositorio, no activó GitHub Actions y no publicó un sitio.** La programación queda preparada en los archivos y comienza cuando configures el repositorio y Pages.

Referencia: [documentación de GitHub sobre workflows de Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Estructura

| Archivo o carpeta | Uso |
| --- | --- |
| `index.html` | Catálogo autónomo, con datos embebidos |
| `panel.html` | Panel interno autónomo, con costos |
| `data/productos.json` | Última lista pública |
| `data/margenes.json` | Costos, comisiones y cambios; interno |
| `data/config.json` | Contactos y recargo |
| `templates/panel.html` | Plantilla del panel, sin costos embebidos |
| `scripts/actualizar.py` | Importación, validación y cálculo |
| `scripts/embeber.py` | Generación de respaldos en los HTML |
| `scripts/publicar.py` | Preparación de la carpeta pública; no despliega |
| `sitio-publico/` | Archivos listos para subir al hosting |
| `ACTUALIZAR.bat` / `actualizar.sh` | Actualización local |
| `tests/` | Regresiones del importador y cálculo |

## Validación

```bash
python -m unittest discover -s tests -v
```

Se verificaron 13 casos del importador: encabezados reordenados, precios con separadores, variantes SIM, identidad sin la etiqueta Nuevo, stock desconocido, retiro de equipos, comisión con recargo, costos ausentes y conservación de la lista ante errores. Además, se realizaron comprobaciones de interacción sobre el DOM para búsqueda, filtros, selección por color, cantidades, persistencia, resumen de WhatsApp, actualización y simulador.

La revisión visual en un navegador completo quedó pendiente porque el navegador de pruebas no permitió abrir archivos locales. No se ejecutó el workflow en una cuenta de GitHub.
