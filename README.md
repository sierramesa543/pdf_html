# FastAPI + xhtml2pdf Demo

Proyecto minimo que demuestra como generar documentos PDF descargables desde una API
construida con **FastAPI**, usando plantillas **Jinja2** para el HTML y la libreria
**xhtml2pdf** para convertirlo a PDF.

## Que demuestra

- Una Home Page servida con una plantilla Jinja2 (`/`).
- Una **vista previa en HTML** del reporte (`/report`) con un boton para descargarlo,
  de modo que el usuario ve el contenido antes de generar el PDF.
- Una ruta (`/report/pdf`) que consume una lista de diccionarios de ejemplo y devuelve
  el PDF descargable con esa informacion renderizada.
- Una variante del mismo flujo con **logo** (`/report/logo` y `/report/pdf-logo`), que
  enfatiza que para incluir imagenes en `xhtml2pdf` se debe usar una **ruta absoluta**
  en la etiqueta `img`.
- El patron **preview HTML -> descargar PDF** se repite igual en ambos reportes.

Dependencias principales (ver `pyproject.toml`):

- `fastapi[standard]` — framework web y CLI.
- `xhtml2pdf` — conversion de HTML/CSS a PDF.
- `jinja2` — motor de plantillas (incluido con `fastapi[standard]`).

## Estructura del proyecto

```
.
├── main.py               # Aplicacion FastAPI: rutas (preview y PDF)
├── pyproject.toml        # Dependencias y entrypoint de FastAPI
├── assets/
│   └── logo.png          # Logo de ejemplo (servido en web y leido en el PDF)
├── templates/
│   ├── index.html        # Home Page (HTML normal, Jinja2)
│   ├── report.html       # Preview HTML y plantilla del PDF (sin imagenes)
│   └── report_logo.html  # Igual que report.html pero incluye el logo
└── README.md
```

## Rutas

| Metodo | Ruta               | Descripcion                                                       |
| ------ | ------------------ | ----------------------------------------------------------------- |
| `GET`  | `/`                | Home Page en HTML con enlaces a las vistas previas.               |
| `GET`  | `/report`          | Vista previa HTML del reporte, con boton "Descargar PDF".         |
| `GET`  | `/report/pdf`      | Genera y descarga el PDF (puro HTML, sin imagenes).               |
| `GET`  | `/report/logo`     | Vista previa HTML del reporte con logo.                           |
| `GET`  | `/report/pdf-logo` | Genera y descarga el PDF con logo (ruta absoluta en `img`).        |

Todas las descargas de PDF usan `Content-Disposition: attachment` para forzar la
descarga del archivo en lugar de abrirlo en el navegador.

## Flujo: preview HTML y luego descarga

El usuario nunca recibe el PDF de inmediato. El recorrido es:

1. En la Home hace clic en "Ver y descargar PDF" -> `GET /report`.
2. La ruta de preview renderiza la plantilla y devuelve **HTML** (no PDF), con una
   hoja de estilo adicional solo para pantalla (tarjeta tipo hoja A4 y botones de
   accion). El contenido es el mismo que tendra el PDF.
3. En la vista previa, el boton "Descargar PDF" llama a `GET /report/pdf`, que
   renderiza la *misma* plantilla y la convierte con `xhtml2pdf`.

La clave es el flag `preview` que se pasa al contexto:

- `preview=True` -> se incluye la barra de acciones y el CSS de pantalla.
- `preview=False` (al generar el PDF) -> no se incluye nada de eso, por lo que el
  documento solo contiene el reporte.

```jinja
{% if preview %}
<main class="sheet">
{% endif %}

... contenido del reporte ...

{% if preview %}
</main>
<div class="actions">
    <a class="btn" href="/report/pdf">Descargar PDF</a>
    <a class="btn secondary" href="/">Volver al inicio</a>
</div>
{% endif %}
```

### Por que no poner el enlace dentro del PDF

`xhtml2pdf` **descarta los `href` relativos**. En su implementacion
(`xhtml2pdf/tags.py`), el tag `<a>` solo conserva el enlace si coincide con
`^(#|[a-z]+:)`, es decir, anclas (`#seccion`) o URLs absolutas (`http://`, `https://`,
`mailto:`). Un `<a href="/">` no genera ninguna anotacion en el PDF.

Por eso la navegacion (volver al inicio, descargar) se resuelve en la **pagina de
preview HTML**, donde los enlaces si funcionan, y se omite al generar el PDF. Un boton
"Descargar" dentro de un PDF tampoco tendria sentido practico: el documento PDF no es
una aplicacion web.

## Datos de ejemplo

En `main.py` se define la lista `PRODUCTS`, una lista de diccionarios que simula una
fuente de datos:

```python
PRODUCTS: list[dict] = [
    {"id": 1, "name": "Laptop Pro 14", "category": "Computo", "price": 18999.00, "stock": 12},
    {"id": 2, "name": 'Monitor 27" 4K', "category": "Pantallas", "price": 7499.50, "stock": 30},
    # ...
]
```

Cada diccionario expone las claves `id`, `name`, `category`, `price` y `stock`, que la
plantilla `report.html` recorre con un bucle `{% for product in products %}`.

## Como funciona la generacion del PDF

El flujo completo es:

1. **FastAPI** recibe la peticion `GET /report/pdf`.
2. Se obtiene la plantilla Jinja2 con `templates.get_template("report.html")`.
3. Se **renderiza a HTML** pasando los datos y `preview=False`:
   `render(title=..., products=PRODUCTS, preview=False)`.
   El resultado es una cadena de HTML con la tabla ya construida y sin la UI de preview.
4. **xhtml2pdf** convierte ese HTML a PDF con `pisa.CreatePDF(src=html, dest=pdf_buffer)`.
   La conversion escribe los bytes del PDF en un `BytesIO` (buffer en memoria).
5. Se devuelve un `fastapi.Response` con:
   - `media_type="application/pdf"`.
   - Cabecera `Content-Disposition: attachment; filename="report.pdf"` para forzar
     la descarga en el navegador.

Fragmento relevante (`main.py`):

```python
from io import BytesIO
from fastapi.responses import Response
from xhtml2pdf import pisa

@app.get("/report/pdf")
def download_report() -> Response:
    html = templates.get_template("report.html").render(
        title="Catalogo de Productos",
        products=PRODUCTS,
        preview=False,
    )
    pdf_buffer = BytesIO()
    pisa.CreatePDF(src=html, dest=pdf_buffer)
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="report.pdf"'},
    )
```

### Por que una funcion `def` y no `async def`

`xhtml2pdf` (`pisa.CreatePDF`) es una operacion **bloqueante** y sincrona. Por eso la
ruta se declara como `def` (no `async def`): FastAPI la ejecuta en un threadpool y no
bloquea el event loop. Si se marcara como `async def` llamando directamente a `pisa`,
se bloquearia el servidor durante la conversion.

### Por que usar `BytesIO`

`pisa.CreatePDF` acepta un objeto con interfaz de escritura como `dest`. Usar
`BytesIO` mantiene el PDF en memoria y evita escribir archivos temporales en disco.
Para el PDF de este ejemplo (unos pocos KB) es suficiente.

## Uso de xhtml2pdf

### Que es xhtml2pdf

`xhtml2pdf` es una libreria de Python que convierte documentos HTML (con soporte de un
subconjunto de CSS) en PDF. Esta pensada para maquetar documentos usando HTML/CSS en
lugar de programar el PDF a bajo nivel, lo que hace muy comodo generar reportes,
facturas o catalogos a partir de plantillas.

Internamente usa **ReportLab** para dibujar el PDF y un parser HTML/CSS para traducir el
documento. El modulo principal es `pisa`.

### Elementos de API mas usados

| Elemento                        | Descripcion                                                        |
| ------------------------------- | ------------------------------------------------------------------ |
| `pisa.CreatePDF(src, dest)`     | Crea el PDF a partir de `src` (HTML) y escribe en `dest`.          |
| `pisa.CreatePDF(...).err`       | Numero de errores encontrados durante la conversion (0 = OK).      |
| `pisa.pisaDocument(src, dest)`  | Version de mas bajo nivel; `CreatePDF` es un envoltorio.           |
| `pisa.DefaultHTTPClient`        | Cliente HTTP usado para resolver recursos remotos (imagenes, CSS). |
| `link_callback`                 | Callback opcional para resolver rutas de recursos locales/remotos. |

### Limites y consideraciones de CSS

`xhtml2pdf` **no** soporta todo el CSS de un navegador. Es importante tenerlo en cuenta:

- Soporta un subconjunto basado en CSS 2.1: colores, fuentes, margenes, paddings,
  bordes, selectores por etiqueta/clase/id, etc.
- **No** soporta Flexbox ni CSS Grid. Para maquetar se recomienda usar **tablas**.
- Reglas `@page` (tamano de hoja y margenes) si estan soportadas:

  ```css
  @page {
      size: letter;  /* carta, A4, etc */
      margin: 2cm;
  }
  ```

- Es mejor usar fuentes basicas (Helvetica, Arial, Times) o registrar fuentes TTF
  explicitamente, porque las fuentes del sistema no siempre estan disponibles.
- Propiedades no implementadas (por ejemplo `border-collapse`, `float`, `box-shadow`)
  se ignoran y `xhtml2pdf` emite en consola un warning del tipo:

  ```
  Ignoring CSS properties xhtml2pdf does not implement: border-collapse
  ```

  No es un error: el PDF se genera igual. Como `border-collapse: collapse` si es util
  para que la tabla se vea bien en el preview web, en este proyecto esa declaracion
  vive **solo dentro del bloque `<style>` de `{% if preview %}`**, de modo que el
  navegador la aplica pero `xhtml2pdf` nunca la ve al generar el PDF y no genera el
  warning.

### Recursos e imagenes

Si el HTML referencia imagenes o CSS externos, `xhtml2pdf` necesita poder resolver esas
rutas. La forma mas simple (la usada en este proyecto) es pasar una **ruta absoluta en
disco** al `src` de la imagen: `xhtml2pdf` la lee directamente del sistema de archivos.

Opcionalmente se puede pasar un `link_callback` para mapear rutas relativas a archivos
locales o a URLs, util cuando hay muchos recursos o rutas dinamicas:

```python
def link_callback(uri, rel):
    # uri: ruta tal como aparece en el HTML
    # devolver la ruta absoluta en disco o la URL final
    return uri

pisa.CreatePDF(src=html, dest=pdf_buffer, link_callback=link_callback)
```

## Ejemplo 2: PDF con logo

Este ejemplo enfatiza que **para incluir imagenes en el PDF hay que usar una ruta
absoluta en la etiqueta `img`**. La ruta es la misma que la del ejemplo 1 pero con la
variante de logo (`/report/logo` para preview y `/report/pdf-logo` para descarga).

Se compone de:

- La imagen `assets/logo.png` (un PNG con transparencia).
- La plantilla `templates/report_logo.html`, que agrega una tabla de encabezado con el
  logo a la izquierda y el titulo a la derecha.
- La ruta absoluta al logo en `main.py`, calculada con `BASE_DIR` para no depender del
  directorio de trabajo.

El logo se resuelve de dos formas segun el destino, porque **un navegador y
`xhtml2pdf` necesitan cosas distintas**:

| Destino | Valor de `logo_src` | Por que |
| ------- | ------------------- | ------- |
| Preview HTML (`/report/logo`) | `http://host/assets/logo.png` | El navegador carga imagenes por URL. Se sirve con `StaticFiles`. |
| PDF (`/report/pdf-logo`) | `/ruta/absoluta/assets/logo.png` | `xhtml2pdf` lee el archivo directamente del disco. |

La plantilla no decide nada: siempre usa una unica variable, `logo_src`.

```html
<img class="logo" src="{{ logo_src }}" alt="Logo" />
```

Es la **ruta la que elige el valor** segun sea preview o PDF, y las dos se renderizan de
forma identica:

```python
BASE_DIR = Path(__file__).resolve().parent

app.mount("/assets", StaticFiles(directory=BASE_DIR / "assets"), name="assets")

@app.get("/report/logo")
async def preview_report_with_logo(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="report_logo.html",
        context={
            "title": "Catalogo de Productos",
            "products": PRODUCTS,
            "preview": True,
            # En el navegador el src debe ser una URL.
            "logo_src": str(request.url_for("assets", path="logo.png")),
            # Solo para mostrar en el preview la ruta absoluta que usara el PDF.
            "logo_pdf_path": str(BASE_DIR / "assets" / "logo.png"),
        },
    )

@app.get("/report/pdf-logo")
def download_report_with_logo() -> Response:
    html = templates.get_template("report_logo.html").render(
        title="Catalogo de Productos",
        products=PRODUCTS,
        preview=False,
        # Para xhtml2pdf el logo se pasa como ruta absoluta de disco.
        logo_src=str(BASE_DIR / "assets" / "logo.png"),
    )
    pdf_buffer = BytesIO()
    result = pisa.CreatePDF(src=html, dest=pdf_buffer)
    return _pdf_response(pdf_buffer, result, "report_con_logo.pdf")
```

### Por que una ruta absoluta y no un `file://` directo

Aunque se podria pensar en poner una URI `file:///ruta/al/logo.png` en el `src`, en la
practica `xhtml2pdf` no siempre logra leerla (el esquema `file` pasa por la clase
`LocalProtocolURI`, que espera un `basepath` y puede fallar silenciosamente). Por eso se
pasa directamente una **ruta absoluta de disco** (`/ruta/al/logo.png`), que `xhtml2pdf`
resuelve con `LocalFileURI`.

### Diferencia entre preview web y PDF

- En el **preview** el `src` es una URL (`http://host/assets/logo.png`) y la carga el
  navegador.
- En el **PDF** el `src` es una ruta absoluta de disco y la lee `xhtml2pdf`.

Es la misma plantilla y la misma variable (`logo_src`); lo unico que cambia es el valor
que la ruta inyecta en el contexto. Si intentaras usar la URL web dentro del PDF,
`xhtml2pdf` tendria que descargar la imagen por HTTP de si mismo, algo fragil detras de
proxies y en plataformas como Vercel.

### Por que calcular la ruta con `BASE_DIR`

Usar `Path(__file__).resolve().parent` en lugar de `os.path.abspath("assets/logo.png")`
evita depender del **directorio de trabajo (CWD)** del proceso. Si la app arranca desde
otra carpeta (systemd, Docker, otro `WorkingDirectory`), una ruta relativa al CWD
apuntaria al lugar equivocado y el logo desapareceria silenciosamente del PDF.

La verificacion es simple: el PDF con logo pesa mas que el PDF sin logo porque incluye
los bytes de la imagen.

Como alternativa a la ruta absoluta, `link_callback` permite resolver varias imagenes
(recibe cada `uri`) cuando hay muchos recursos o rutas dinamicas; en este demo no hace
falta porque la imagen es una sola y conocida.

### Manejo de errores

`pisa.CreatePDF` no lanza excepciones por HTML/CSS invalido: acumula errores y los
reporta. Conviene revisar el resultado:

```python
result = pisa.CreatePDF(src=html, dest=pdf_buffer)
if result.err:
    # registrar o devolver un error
    ...
```

## Personalizacion

- **Cambiar los datos**: edita la lista `PRODUCTS` en `main.py`.
- **Cambiar el diseno del PDF**: edita `templates/report.html` (recuerda las
  limitaciones de CSS indicadas arriba).
- **Cambiar el logo**: reemplaza `assets/logo.png` por tu imagen. El nombre se resuelve
  en `main.py` con `BASE_DIR / "assets" / "logo.png"`.
- **Cambiar el nombre del archivo**: modifica el valor de `filename` en la cabecera
  `Content-Disposition`.
- **Cambiar la Home Page**: edita `templates/index.html`.

## Verificacion rapida

Con el servidor en ejecucion:

```bash
curl -s -o preview.html        http://127.0.0.1:8000/report
curl -s -o preview_logo.html   http://127.0.0.1:8000/report/logo
curl -s -o report.pdf          http://127.0.0.1:8000/report/pdf
curl -s -o report_logo.pdf     http://127.0.0.1:8000/report/pdf-logo
file report.pdf report_logo.pdf                         # -> PDF document ...
```

La cabecera de las descargas debe indicar `attachment`:

```bash
curl -sI http://127.0.0.1:8000/report/pdf | grep -i content-disposition
# content-disposition: attachment; filename="report.pdf"
```

Para comprobar que el logo quedo embebido en el segundo PDF:

```bash
pdfimages -list report_logo.pdf   # debe listar una imagen de 480x160
```

## Enlaces de interes

- FastAPI: https://fastapi.tiangolo.com/
- Plantillas en FastAPI: https://fastapi.tiangolo.com/advanced/templates/
- Jinja2: https://jinja.palletsprojects.com/
- xhtml2pdf: https://xhtml2pdf.readthedocs.io/
