# main.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from .search_routes_oop import router as search_router
from fastapi import Form
from pathlib import Path
import re
import importlib
from .services.database import get_connection

# Importa l'app OOP per poter delegare alcune route quando il server viene avviato con main.py
try:
    main_oop = importlib.import_module("sitesense.main_oop")
    sitesense_app = getattr(main_oop, "sitesense_app", None)
except Exception:
    main_oop = None
    sitesense_app = None

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
app.mount("/chi_siamo_design", StaticFiles(directory="Chi Siamo Page Design 1/build"), name="chi_siamo_design")
app.mount("/chi_siamo_design/src", StaticFiles(directory="Chi Siamo Page Design 1/src"), name="chi_siamo_design_src")
# Monta gli asset compilati del dashboard se presenti
app.mount(
    "/dashboard",
    StaticFiles(directory="dashboard/build"),
    name="dashboard",
)
# Monta anche i sorgenti del dashboard (src) per coprire eventuali riferimenti diretti
app.mount(
    "/dashboard/src",
    StaticFiles(directory="dashboard/src"),
    name="dashboard_src",
)
templates = Jinja2Templates(directory="templates")

app.include_router(search_router)

# Middleware globale per sanificare percorsi con virgolette (codificate o grezze)
@app.middleware("http")
async def _sanitize_path_middleware(request, call_next):
    path = request.url.path
    if path.startswith("/dashboard/api_current_user") or path.startswith("/api/area_riservata/api_current_user"):
        q = request.url.query
        url = "/api_current_user" if not q else f"/api_current_user?{q}"
        return RedirectResponse(url=url, status_code=307)
    sanitized = path.replace('%22', '').replace('"', '').replace("'", '')
    sanitized = re.sub(r"/+", "/", sanitized)
    sanitized = re.sub(r"(\.html)/+$", r"\1", sanitized)
    if sanitized != path:
        q = request.url.query
        url = sanitized if not q else f"{sanitized}?{q}"
        return RedirectResponse(url=url, status_code=307)
    return await call_next(request)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/chi_siamo", response_class=HTMLResponse)
async def chi_siamo_page(request: Request):
    base_dir = Path(__file__).resolve().parent
    build_index = base_dir / "Chi Siamo Page Design 1" / "build" / "index.html"
    if build_index.exists():
        html = build_index.read_text(encoding="utf-8")
        html = re.sub(r'(href|src)="/?assets/', r'\1="/chi_siamo_design/assets/', html)
        html = re.sub(r'(href|src)="src/', r'\1="/chi_siamo_design/src/', html)
        html = re.sub(r'(href|src)="/?vite\.svg', r'\1="/chi_siamo_design/vite.svg', html)
        html = re.sub(r"<section[^>]*>[\s\S]*?Vuoi unirti a noi[\s\S]*?</section>", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<section[^>]*>[\s\S]*?Guarda come funziona[\s\S]*?</section>", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<section[^>]*>[\s\S]*?Scegli initalya[\s\S]*?</section>", "", html, flags=re.IGNORECASE)
        m_head = re.search(r"<head[^>]*>([\\s\\S]*?)</head>", html, flags=re.IGNORECASE)
        m_body = re.search(r"<body[^>]*>([\\s\\S]*?)</body>", html, flags=re.IGNORECASE)
        head_inner = (m_head.group(1) if m_head else "")
        body_inner = (m_body.group(1) if m_body else html)
        return templates.TemplateResponse("chi_siamo.html", {"request": request, "design_head": head_inner, "design_html": body_inner})
    return templates.TemplateResponse("chi_siamo.html", {"request": request, "design_head": "", "design_html": ""})

@app.get("/place_details", response_class=HTMLResponse)
async def place_details(request: Request, place_id: str):
    return templates.TemplateResponse("place_details.html", {"request": request, "place_id": place_id})

@app.get("/api/place_details/{place_id}")
async def api_place_details(place_id: str):
    from search_routes_oop import get_place_details
    details = await get_place_details(place_id)
    return details

# Alias per compatibilità: /image_search e /image_search_cse
# Delegano all'handler OOP se disponibile, evitando 404 quando si avvia con main.py
@app.get("/image_search")
async def image_search_alias(request: Request):
    if sitesense_app and hasattr(sitesense_app, "image_search"):
        return await sitesense_app.image_search(request)
    return RedirectResponse(url="/", status_code=307)

@app.get("/image_search_cse")
async def image_search_cse_alias(request: Request):
    if sitesense_app and hasattr(sitesense_app, "image_search"):
        return await sitesense_app.image_search(request)
    return RedirectResponse(url="/", status_code=307)

# Alias per compatibilità: /city_image e /city_image_cse
# Delegano all'handler OOP se disponibile, evitando 404 quando si avvia con main.py
@app.get("/city_image")
async def city_image_alias(city: str):
    if sitesense_app and hasattr(sitesense_app, "city_image"):
        return await sitesense_app.city_image(city=city)
    return RedirectResponse(url="/", status_code=307)

@app.get("/city_image_cse")
async def city_image_cse_alias(city: str):
    if sitesense_app and hasattr(sitesense_app, "city_image"):
        return await sitesense_app.city_image(city=city)
    return RedirectResponse(url="/", status_code=307)

# Pagina di login Super Admin
@app.get("/login_super_admin", response_class=HTMLResponse)
async def login_super_admin_get(request: Request):
    return templates.TemplateResponse("login_super_admin.html", {"request": request})

# Endpoint di submit del login (mock; sostituire con logica reale)
@app.post("/login_super_admin", response_class=HTMLResponse)
async def login_super_admin_post(request: Request, email: str = Form(...), password: str = Form(...), remember: str | None = Form(None)):
    # TODO: sostituire con verifica reale delle credenziali super admin
    if not (email and password):
        return templates.TemplateResponse("login_super_admin.html", {"request": request, "error_message": "Credenziali mancanti."})
    # Mock semplice: consenti solo email con dominio initialya.it
    if not email.endswith("@initialya.it"):
        return templates.TemplateResponse("login_super_admin.html", {"request": request, "error_message": "Accesso riservato ai super admin Initialya."})
    # Imposta cookie semplice e reindirizza all'area super admin (dashboard)
    resp = RedirectResponse(url="/area_super_admin", status_code=303)
    resp.set_cookie(key="super_auth", value="1", samesite="lax", path="/")
    resp.set_cookie(key="superadmin_email", value=email, samesite="lax", path="/")
    return resp

# Helper per rendere gli HTML del dashboard build con base href
BASE_DIR = Path(__file__).resolve().parent

def render_dashboard_page(page_name: str) -> HTMLResponse:
    build_dir = BASE_DIR / "dashboard" / "build"
    html_path = build_dir / page_name
    if not html_path.exists():
        return HTMLResponse(status_code=404, content=f"Pagina non trovata: {page_name}")
    html = html_path.read_text(encoding="utf-8")
    if "<base" not in html:
        html = re.sub(r"(<head[^>]*>)", r"\1\n    <base href=\"/dashboard/\">", html, count=1)
    # Riscrivi percorsi critici (CSS/JS/favicon/src assets) e link HTML per l'area_super_admin
    html = re.sub(r"href=\"style\.css\"", "href=\"/dashboard/style.css\"", html)
    html = re.sub(r"src=\"bundle\.js\"", "src=\"/dashboard/bundle.js\"", html)
    html = re.sub(r"href=\"favicon\.ico\"", "href=\"/dashboard/favicon.ico\"", html)
    html = re.sub(r"(src|href)=\"src/", r"\1=\"/dashboard/src/", html)
    html = re.sub(r"href=\"(?!http)(?!/)([A-Za-z0-9_-]+\.html)\"", r"href=\"/area_super_admin/\1\"", html)
    # Supporto anche per href con apici singoli
    html = re.sub(r"href='(?!http)(?!/)([A-Za-z0-9_-]+\.html)'", r"href='/area_super_admin/\1'", html)
    # Pulisci virgolette codificate %22 eventualmente presenti nei valori href/src
    # Inizio valore attributo
    html = re.sub(r"(href|src)=(\"|')%22/", r"\1=\2/", html)
    # Fine valore attributo
    html = re.sub(r"%22(\"|')", r"\1", html)
    # Gestisci anche il caso con slash finale prima della chiusura
    html = re.sub(r"/%22(\"|')", r"\1", html)
    # Rimuovi qualsiasi occorrenza di %22 all'interno dei valori href/src
    html = re.sub(r"(href|src)=(\"|')([^\"']*?)%22([^\"']*?)(\"|')", r"\1=\2\3\4\5", html)
    # Nota: rimozione di normalizzazioni con backreference errate che potevano
    # introdurre virgolette spurie nel path (es. /"/area_super_admin/...).
    # Rimuovi slash finale dopo .html
    html = re.sub(r"href=(\"|')(/area_super_admin/[A-Za-z0-9_-]+\.html)/+(\"|')", r"href=\1\2\3", html)

    # Sanitizza sistematicamente i valori href/src per rimuovere virgolette interne e slash superflui
    def _sanitize_attr_double(m):
        val = m.group(2)
        val = val.replace('%22', '')
        val = val.replace('"', '')
        val = val.replace("'", '')
        val = re.sub(r"(\.html)/+$", r"\1", val)
        return f"{m.group(1)}=\"{val}\""

    def _sanitize_attr_single(m):
        val = m.group(2)
        val = val.replace('%22', '')
        val = val.replace('"', '')
        val = val.replace("'", '')
        val = re.sub(r"(\.html)/+$", r"\1", val)
        return f"{m.group(1)}='{val}'"

    html = re.sub(r"(href|src)=\"([^\"]*)\"", _sanitize_attr_double, html)
    html = re.sub(r"(href|src)='([^']*)'", _sanitize_attr_single, html)
    return HTMLResponse(content=html)

@app.get("/area_super_admin", response_class=HTMLResponse)
async def area_super_admin(request: Request):
    super_auth = request.cookies.get("super_auth")
    email = request.cookies.get("superadmin_email")
    if super_auth != "1" or not email:
        return RedirectResponse("/login_super_admin", status_code=303)
    return render_dashboard_page("index.html")

@app.get("/area_super_admin/{page_name}", response_class=HTMLResponse)
async def area_super_admin_page(request: Request, page_name: str):
    super_auth = request.cookies.get("super_auth")
    email = request.cookies.get("superadmin_email")
    if super_auth != "1" or not email:
        return RedirectResponse("/login_super_admin", status_code=303)
    if not page_name.endswith(".html"):
        page_name = f"{page_name}.html"
    return render_dashboard_page(page_name)

@app.get("/api_current_user")
async def api_current_user(request: Request):
    auth = request.cookies.get("auth")
    user_email = request.cookies.get("user_email")
    if auth != "1" or not user_email:
        return JSONResponse({"ok": False, "error": "Non autenticato"}, status_code=401)
    conn = get_connection()
    if not conn:
        return JSONResponse({"ok": False, "error": "DB non disponibile"}, status_code=503)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT name, surname, email, profile_image FROM Initalya.users WHERE email = %s", (user_email,))
        u = cur.fetchone() or {}
        return JSONResponse({
            "ok": True,
            "name": u.get("name"),
            "surname": u.get("surname"),
            "email": u.get("email") or user_email,
            "profile_image": u.get("profile_image") or "/assets/user-variant1.png",
        })
    except Exception as e:
        return JSONResponse({"ok": False, "error": "Errore server"}, status_code=500)
    finally:
        try:
            conn.close()
        except Exception:
            pass
