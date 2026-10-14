from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from xhtml2pdf import pisa

BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=BASE_DIR / "templates")

app = FastAPI(title="xhtml2pdf Demo")

app.mount("/assets", StaticFiles(directory=BASE_DIR / "assets"), name="assets")

PRODUCTS: list[dict] = [
    {
        "id": 1,
        "name": "Laptop Pro 14",
        "category": "Computo",
        "price": 18999.00,
        "stock": 12,
    },
    {
        "id": 2,
        "name": 'Monitor 27" 4K',
        "category": "Pantallas",
        "price": 7499.50,
        "stock": 30,
    },
    {
        "id": 3,
        "name": "Teclado Mecanico",
        "category": "Accesorios",
        "price": 1299.99,
        "stock": 85,
    },
    {
        "id": 4,
        "name": "Mouse Inalambrico",
        "category": "Accesorios",
        "price": 499.00,
        "stock": 120,
    },
    {
        "id": 5,
        "name": "Webcam Full HD",
        "category": "Video",
        "price": 899.00,
        "stock": 45,
    },
]


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": "xhtml2pdf Demo", "products_count": len(PRODUCTS)},
    )


@app.get("/report", response_class=HTMLResponse)
async def preview_report(request: Request) -> HTMLResponse:
    """Muestra el reporte en HTML antes de descargarlo como PDF."""
    return templates.TemplateResponse(
        request=request,
        name="report.html",
        context={
            "title": "Catalogo de Productos",
            "products": PRODUCTS,
            "preview": True,
        },
    )


@app.get("/report/logo", response_class=HTMLResponse)
async def preview_report_with_logo(request: Request) -> HTMLResponse:
    """Preview del reporte con logo (el logo se sirve por URL en la web)."""
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


@app.get("/report/pdf")
def download_report() -> Response:
    """Genera el PDF a partir de puro HTML (sin imagenes)."""
    html = templates.get_template("report.html").render(
        title="Catalogo de Productos",
        products=PRODUCTS,
        preview=False,
    )
    pdf_buffer = BytesIO()
    result = pisa.CreatePDF(src=html, dest=pdf_buffer)
    return _pdf_response(pdf_buffer, result, "report.pdf")


@app.get("/report/pdf-logo")
def download_report_with_logo() -> Response:
    """Genera el PDF con logo usando una ruta absoluta en la etiqueta img."""
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


def _pdf_response(pdf_buffer: BytesIO, result, filename: str) -> Response:
    if result.err:
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar el PDF ({result.err} errores)",
        )
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
