import logging
import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from .search_routes_oop import search_routes_instance
import httpx
import json
import urllib.parse
from .config.settings import settings
import re
from .services.database import get_connection
import hashlib
from .services.city_cache_service import save_city_cache, load_city_cache

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

# Silenzia i logger troppo verbosi
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai.models").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
# Base directory of the sitesense package (for absolute paths)
BASE_DIR = Path(__file__).resolve().parent

class SiteSenseApp:
    """Classe principale per l'applicazione SiteSense"""
    
    def __init__(self):
        self.app = FastAPI(title="SiteSense", description="AI Travel & Food Concierge")
        self.templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
        self._setup_middleware()
        self._setup_static_files()
        self._setup_routes()
        logger.info("SiteSenseApp inizializzata con successo")
    
    def _setup_static_files(self):
        """Configura i file statici"""
        self.app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
        self.app.mount("/assets", StaticFiles(directory=str(BASE_DIR / "assets")), name="assets")
        # Monta gli asset compilati del dashboard (webpack build)
        dashboard_build = BASE_DIR / "dashboard" / "build"
        if dashboard_build.exists():
            self.app.mount("/dashboard", StaticFiles(directory=str(dashboard_build)), name="dashboard")
        # Monta anche i sorgenti (src) per garantire accesso a tutte le risorse referenziate
        dashboard_src = BASE_DIR / "dashboard" / "src"
        if dashboard_src.exists():
            self.app.mount("/dashboard/src", StaticFiles(directory=str(dashboard_src)), name="dashboard_src")
        chi_siamo_dist = BASE_DIR / "Chi Siamo Page Design 1" / "dist"
        chi_siamo_build = BASE_DIR / "Chi Siamo Page Design 1" / "build"
        if chi_siamo_dist.exists():
            self.app.mount("/chi_siamo_design", StaticFiles(directory=str(chi_siamo_dist)), name="chi_siamo_design")
        elif chi_siamo_build.exists():
            self.app.mount("/chi_siamo_design", StaticFiles(directory=str(chi_siamo_build)), name="chi_siamo_design")
        chi_siamo_src = BASE_DIR / "Chi Siamo Page Design 1" / "src"
        if chi_siamo_src.exists():
            self.app.mount("/chi_siamo_design/src", StaticFiles(directory=str(chi_siamo_src)), name="chi_siamo_design_src")
        logger.info("File statici configurati")
    
    def _setup_routes(self):
        """Configura le route dell'applicazione"""
        # Include il router di ricerca
        self.app.include_router(search_routes_instance.get_router())
        
        # Route per le pagine HTML
        self.app.get("/", response_class=HTMLResponse)(self.read_root)
        self.app.get("/place_details", response_class=HTMLResponse)(self.place_details)
        self.app.get("/api/place_details/{place_id}")(self.api_place_details)
        self.app.get("/chi_siamo", response_class=HTMLResponse)(self.chi_siamo_page)
        self.app.get("/contatti", response_class=HTMLResponse)(self.contatti_page)
        self.app.get("/image_search")(self.image_search)
        # Alias esplicito CSE per immagini piatti
        self.app.get("/image_search_cse")(self.image_search)
        self.app.get("/city_image")(self.city_image)
        # Alias esplicito per CSE: utilizza lo stesso handler (CSE-only)
        self.app.get("/city_image_cse")(self.city_image)
        # Nuova endpoint per immagini piatti per citt�
        self.app.get("/city_dish_image")(self.city_dish_image)
        # Nuove endpoint per immagini della pagina intro (associate a città specifica)
        self.app.get("/intro_image/{city}/{item}")(self.intro_page_image)
        self.app.get("/login", response_class=HTMLResponse)(self.login_page)
        self.app.get("/login_super_admin", response_class=HTMLResponse)(self.login_super_admin)
        self.app.post("/login_super_admin", response_class=HTMLResponse)(self.login_super_admin_submit)
        self.app.post("/login")(self.login_submit)
        # API per super admin: elenco utenti con programmi di viaggio
        self.app.get("/api/super_admin/users_programs")(self.api_users_programs)
        # API aggregata: numero di programmi per utente
        self.app.get("/api/super_admin/users_programs_count")(self.api_users_programs_count)
        # Endpoint profilo utente (registrazione esplicita in _setup_routes)
        self.app.post("/api/update_profile")(self.update_profile)

    def _setup_middleware(self):
        """Middleware globale per sanificare percorsi contenenti virgolette codificate/non codificate."""
        @self.app.middleware("http")
        async def _sanitize_path_middleware(request, call_next):
            path = request.url.path
            if path.startswith("/dashboard/api_current_user") or path.startswith("/api/area_riservata/api_current_user"):
                q = request.url.query
                url = "/api_current_user" if not q else f"/api_current_user?{q}"
                return RedirectResponse(url=url, status_code=307)
            # Rimuove qualsiasi occorrenza di %22 o virgolette grezze dal path
            sanitized = path.replace('%22', '').replace('"', '').replace("'", '')
            # Normalizza doppi slash
            sanitized = re.sub(r"/+", "/", sanitized)
            # Rimuove slash finale superfluo dopo .html
            sanitized = re.sub(r"(\.html)/+$", r"\1", sanitized)
            if sanitized != path:
                q = request.url.query
                url = sanitized if not q else f"{sanitized}?{q}"
                return RedirectResponse(url=url, status_code=307)
            return await call_next(request)
        self.app.get("/google_login", name="google_login")(self.google_login)
        self.app.get("/auth/google/callback", name="google_callback")(self.google_callback)
        self.app.get("/area_riservata", response_class=HTMLResponse)(self.area_riservata)
        self.app.get("/profile", response_class=HTMLResponse)(self.profile_page)
        self.app.get("/area_super_admin", response_class=HTMLResponse)(self.area_super_admin)
        self.app.get("/area_super_admin/{page_name}", response_class=HTMLResponse)(self.area_super_admin_page)
        self.app.get("/logout")(self.logout)
        self.app.get("/api/auth_status")(self.api_auth_status)
        self.app.get("/api_current_user")(self.api_current_user)
        self.app.get("/dashboard/api_current_user")(self.api_current_user)
        self.app.get("/api/area_riservata/api_current_user")(self.api_current_user)
        self.app.post("/api/save_itinerary")(self.save_itinerary)
        self.app.post("/api/update_program")(self.update_program)
        self.app.post("/api/delete_program")(self.delete_program)
        self.app.get("/area_riservata", response_class=HTMLResponse)(self.area_riservata)
        self.app.get("/program/{program_id}", response_class=HTMLResponse)(self.view_program) 
        self.app.get("/api/program_details/{program_id}")(self.program_details)
        # Endpoint profilo utente
        self.app.post("/api/update_profile")(self.update_profile)
        # Endpoint stato chiavi Maps (per fallback client)
        self.app.get("/api/maps_status")(self.maps_status)
        # Endpoint cache città: load/save
        self.app.get("/api/load_city_cache")(self.api_load_city_cache)
        self.app.post("/api/save_city_cache")(self.api_save_city_cache)
        # Handler di cortesia per GET sull'endpoint di salvataggio: guida all'uso corretto
        
        
        
        logger.info("Route configurate")

    async def maps_status(self, request: Request):
        """Ritorna lo stato di disponibilità della chiave Google Maps."""
        ok = False
        try:
            key = settings.google_maps_api_key
            # Considera non valida se è DUMMY o placeholder comune
            if key and key not in ("DUMMY_KEY", "YOUR_API_KEY", "your_api_key") and len(key) > 20:
                ok = True
        except Exception:
            ok = False
        return {"maps_key_ok": ok}

    async def api_save_city_cache(self, request: Request):
        """Salva la cache per città (payload inviato dal client)."""
        try:
            data = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Payload JSON non valido")
        city = (data.get("city") or "").strip()
        if not city:
            raise HTTPException(status_code=400, detail="Parametro 'city' mancante")
        try:
            res = save_city_cache(city, data)
            return res
        except Exception as e:
            logger.warning(f"Errore salvataggio cache città: {e}")
            raise HTTPException(status_code=500, detail="Errore salvataggio cache città")

    async def api_save_city_cache_get(self, request: Request):
        """Risponde ai GET su /api/save_city_cache con una guida all'uso (POST richiesto)."""
        # Restituisce 405 per coerenza con il metodo non permesso, ma con messaggio chiaro
        return PlainTextResponse(
            "Usa POST /api/save_city_cache con Content-Type: application/json e payload { city, locals_selection, locals_suggests }",
            status_code=405
        )

    async def api_load_city_cache(self, request: Request):
        """Carica la cache per città, con fallback a other_locals.json."""
        city = (request.query_params.get("city") or "").strip()
        if not city:
            raise HTTPException(status_code=400, detail="Parametro 'city' mancante")
        try:
            data = load_city_cache(city)
            return data
        except Exception as e:
            logger.warning(f"Errore caricamento cache città: {e}")
            raise HTTPException(status_code=500, detail="Errore caricamento cache città")
    
    async def read_root(self, request: Request):
        """Pagina principale"""
        logger.info("Richiesta alla pagina principale")
        # Se l'utente è autenticato, passa i dati utente al template
        user_data = None
        try:
            auth = request.cookies.get("auth")
            user_email = request.cookies.get("user_email")
            if auth == "1" and user_email:
                conn = get_connection()
                if conn:
                    cur = conn.cursor(dictionary=True)
                    try:
                        cur.execute("SELECT * FROM Initalya.users WHERE email = %s", (user_email,))
                        user_data = cur.fetchone()
                    finally:
                        try:
                            conn.close()
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"Impossibile recuperare i dati utente per la home: {e}")
        return self.templates.TemplateResponse("index.html", {"request": request, "user": user_data})

    async def chi_siamo_page(self, request: Request):
        dist_index = BASE_DIR / "Chi Siamo Page Design 1" / "dist" / "index.html"
        if dist_index.exists():
            html = dist_index.read_text(encoding="utf-8")
            if "<base" not in html:
                html = re.sub(r"(<head[^>]*>)", r"\1\n    <base href=\"/chi_siamo_design/\">", html, count=1)
            html = re.sub(r"(src|href)=\"src/", r"\1=\"/chi_siamo_design/src/", html)
            html = re.sub(r"(href|src)=\"/assets/", r"\1=\"/chi_siamo_design/assets/", html)
            html = re.sub(r"(href|src)=\"/vite\.svg", r"\1=\"/chi_siamo_design/vite.svg", html)
            m_head = re.search(r"<head[^>]*>([\s\S]*?)</head>", html, flags=re.IGNORECASE)
            m_body = re.search(r"<body[^>]*>([\s\S]*?)</body>", html, flags=re.IGNORECASE)
            head_inner = (m_head.group(1) if m_head else "")
            body_inner = (m_body.group(1) if m_body else html)
            return self.templates.TemplateResponse("chi_siamo.html", {"request": request, "design_head": head_inner, "design_html": body_inner})
        build_index = BASE_DIR / "Chi Siamo Page Design 1" / "build" / "index.html"
        if build_index.exists():
            html = build_index.read_text(encoding="utf-8")
            if "<base" not in html:
                html = re.sub(r"(<head[^>]*>)", r"\1\n    <base href=\"/chi_siamo_design/\">", html, count=1)
            html = re.sub(r"(src|href)=\"src/", r"\1=\"/chi_siamo_design/src/", html)
            html = re.sub(r"(href|src)=\"/assets/", r"\1=\"/chi_siamo_design/assets/", html)
            html = re.sub(r"(href|src)=\"/vite\.svg", r"\1=\"/chi_siamo_design/vite.svg", html)
            m_head = re.search(r"<head[^>]*>([\s\S]*?)</head>", html, flags=re.IGNORECASE)
            m_body = re.search(r"<body[^>]*>([\s\S]*?)</body>", html, flags=re.IGNORECASE)
            head_inner = (m_head.group(1) if m_head else "")
            body_inner = (m_body.group(1) if m_body else html)
            return self.templates.TemplateResponse("chi_siamo.html", {"request": request, "design_head": head_inner, "design_html": body_inner})
        return self.templates.TemplateResponse("chi_siamo.html", {"request": request})
    
    async def contatti_page(self, request: Request):
        return self.templates.TemplateResponse("contatti.html", {"request": request})

    async def area_super_admin(self, request: Request):
        """Servi la home dell'area super admin identica al dashboard (index.html)."""
        # Consenti accesso solo se autenticato come super admin
        super_auth = request.cookies.get("super_auth") or request.cookies.get("auth")
        role = request.cookies.get("role")
        email = request.cookies.get("superadmin_email") or request.cookies.get("user_email")

        if not ((super_auth == "1" and email) or (super_auth == "1" and role == "super_admin") or (request.cookies.get("auth") == "1" and role == "super_admin")):
            return RedirectResponse(url="/login_super_admin?next=/area_super_admin", status_code=303)

        # Rende la pagina dashboard/build/index.html con base href per asset
        return await self._render_dashboard_page("index.html", request)

    async def area_super_admin_page(self, request: Request, page_name: str):
        """Servi qualsiasi pagina HTML del dashboard sotto /area_super_admin/{page}."""
        # Protezione accesso
        super_auth = request.cookies.get("super_auth") or request.cookies.get("auth")
        role = request.cookies.get("role")
        email = request.cookies.get("superadmin_email") or request.cookies.get("user_email")

        if not ((super_auth == "1" and email) or (super_auth == "1" and role == "super_admin") or (request.cookies.get("auth") == "1" and role == "super_admin")):
            return RedirectResponse(url="/login_super_admin", status_code=303)

        # Garantisci che si richieda solo file .html
        if not page_name.endswith(".html"):
            page_name = f"{page_name}.html"

        return await self._render_dashboard_page(page_name, request)

    async def _render_dashboard_page(self, page_name: str, request: Request) -> HTMLResponse:
        """Legge un file HTML dal build del dashboard e inietta <base href="/dashboard/">."""
        build_dir = BASE_DIR / "dashboard" / "build"
        html_path = build_dir / page_name

        if not html_path.exists():
            raise HTTPException(status_code=404, detail=f"Pagina dashboard non trovata: {page_name}")

        html = html_path.read_text(encoding="utf-8")

        # Inietta il base href se non presente per risolvere asset relativi
        if "<base" not in html:
            html = re.sub(r"(<head[^>]*>)", r"\1\n    <base href=\"/dashboard/\">", html, count=1)

        # Riscrivi percorsi critici (CSS/JS/favicon/src assets) e link HTML
        html = re.sub(r"href=\"style\.css\"", "href=\"/dashboard/style.css\"", html)
        html = re.sub(r"src=\"bundle\.js\"", "src=\"/dashboard/bundle.js\"", html)
        html = re.sub(r"href=\"favicon\.ico\"", "href=\"/dashboard/favicon.ico\"", html)
        # Riscrivi riferimenti a src/ per immagini e altri asset
        html = re.sub(r"(src|href)=\"src/", r"\1=\"/dashboard/src/", html)
        path = request.url.path or ""
        if path.startswith("/area_riservata"):
            html = re.sub(r"href=\"(?!http)(?!/)([A-Za-z0-9._-]+\.html)\"", r"href=\"/area_riservata?dashboard_page=\1\"", html)
            html = re.sub(r"href='(?!http)(?!/)([A-Za-z0-9._-]+\.html)'", r"href='/area_riservata?dashboard_page=\1'", html)
            html = re.sub(r"href=\"/dashboard/([A-Za-z0-9._-]+\.html)\"", r"href=\"/area_riservata?dashboard_page=\1\"", html)
            html = re.sub(r"href='/dashboard/([A-Za-z0-9._-]+\.html)'", r"href='/area_riservata?dashboard_page=\1'", html)
            html = re.sub(r"href=\"\./([A-Za-z0-9._-]+\.html)\"", r"href=\"/area_riservata?dashboard_page=\1\"", html)
            html = re.sub(r"href='\./([A-Za-z0-9._-]+\.html)'", r"href='/area_riservata?dashboard_page=\1'", html)
            html = re.sub(r"href=\"/([A-Za-z0-9._-]+\.html)\"", r"href=\"/area_riservata?dashboard_page=\1\"", html)
            html = re.sub(r"href='/([A-Za-z0-9._-]+\.html)'", r"href='/area_riservata?dashboard_page=\1'", html)
        else:
            html = re.sub(r"href=\"(?!http)(?!/)([A-Za-z0-9_-]+\.html)\"", r"href=\"/area_super_admin/\1\"", html)
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
        if path.startswith("/area_riservata"):
            try:
                auth = request.cookies.get("auth")
                user_email = request.cookies.get("user_email")
                if auth == "1" and user_email:
                    conn = get_connection()
                    u = {}
                    if conn:
                        cur = conn.cursor(dictionary=True)
                        cur.execute("SELECT name, surname, email, profile_image FROM Initalya.users WHERE email = %s", (user_email,))
                        u = cur.fetchone() or {}
                        try:
                            conn.close()
                        except Exception:
                            pass
                    def _esc(v):
                        s = "" if v is None else str(v)
                        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
                        return s
                    name = (u.get("name") or "").strip()
                    surname = (u.get("surname") or "").strip()
                    email_val = (u.get("email") or user_email or "").strip()
                    full_name = (f"{name} {surname}".strip() or email_val)
                    img_src = ((u.get("profile_image") or "").strip() or "/assets/user-variant1.png")
                    img_src = _esc(img_src)
                    # Aggiorna avatar nell'header
                    html = re.sub(r'src="/dashboard/src/images/user/owner\.jpg"', f'src="{img_src}"', html)
                    html = re.sub(r'src="src/images/user/owner\.jpg"', f'src="{img_src}"', html)
                    # Aggiorna nome breve vicino all'avatar
                    if name:
                        html = re.sub(r">\s*Musharof\s*<", f">{_esc(name)}<", html)
                    # Aggiorna nome completo nel dropdown utente
                    html = re.sub(r">\s*Musharof Chowdhury\s*<", f">{_esc(full_name)}<", html)
                    # Aggiorna email nel dropdown utente
                    html = re.sub(r">\s*randomuser@pimjo\.com\s*<", f">{_esc(email_val)}<", html)
                    # Collega il pulsante Sign out al logout sostituendolo con un link
                    # Usa un regex che non attraversi i tag di chiusura button per evitare di catturare bottoni precedenti (es. hamburger)
                 
                    
                    # Aggiorna il bottone hamburger per usare prevent.stop come richiesto
                    html = re.sub(r"@click\.stop=\"sidebarToggle\s*=\s*!sidebarToggle\"", r'@click.prevent.stop="sidebarToggle = !sidebarToggle"', html)

                    # Forza avatar lato client se presenti residui non catturati, inserendo script inline
                    avatar_script = f"<script>try{{var img='{img_src}';var el=document.getElementById('user-avatar-img');if(el){{el.src=img;}}var q=document.querySelector('img[src*=\"owner.jpg\"]');if(q){{q.src=img;}}}}catch(e){{}}</script>"
                    m_body_end = re.search(r"</body>", html, flags=re.IGNORECASE)
                    if m_body_end:
                        pos = m_body_end.start()
                        html = html[:pos] + avatar_script + html[pos:]
            except Exception as _e:
                logger.warning(f"Iniezione header utente fallita: {_e}")



        
      
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
    
    async def _render_chi_siamo_design_page(self, page_name: str, request: Request) -> HTMLResponse:
        build_dir = BASE_DIR / "Chi Siamo Page Design 1" / "dist"
        html_path = build_dir / page_name
        if not html_path.exists():
            raise HTTPException(status_code=404, detail=f"Pagina Chi Siamo non trovata: {page_name}")
        html = html_path.read_text(encoding="utf-8")
        if "<base" not in html:
            html = re.sub(r"(<head[^>]*>)", r"\1\n    <base href=\"/chi_siamo_design/\">", html, count=1)
        html = re.sub(r"(src|href)=\"src/", r"\1=\"/chi_siamo_design/src/", html)
        html = re.sub(r"(href|src)=\"/assets/", r"\1=\"/chi_siamo_design/assets/", html)
        html = re.sub(r"(href|src)=\"/vite\.svg", r"\1=\"/chi_siamo_design/vite.svg", html)
        return HTMLResponse(content=html)
    
    async def api_auth_status(self, request: Request):
     auth = request.cookies.get("auth")
     user_email = request.cookies.get("user_email")

     return {
        "authenticated": auth == "1" and bool(user_email)
     }

    async def api_current_user(self, request: Request):
        """Ritorna i dati dell'utente corrente autenticato (name, surname, email, profile_image)."""
        auth = request.cookies.get("auth")
        user_email = request.cookies.get("user_email")
        if auth != "1" or not user_email:
            return Response(media_type="application/json", content=json.dumps({"ok": False, "error": "Non autenticato"}), status_code=401)
        conn = get_connection()
        if not conn:
            return Response(media_type="application/json", content=json.dumps({"ok": False, "error": "DB non disponibile"}), status_code=503)
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT name, surname, email, profile_image FROM Initalya.users WHERE email = %s", (user_email,))
            u = cur.fetchone() or {}
            prof = (u.get("profile_image") or "").strip()
            if not prof:
                prof = "/assets/user-variant1.png"
            return Response(media_type="application/json", content=json.dumps({
                "ok": True,
                "name": u.get("name"),
                "surname": u.get("surname"),
                "email": u.get("email") or user_email,
                "profile_image": prof,
            }))
        except Exception as e:
            logger.exception("Errore in api_current_user: %s", e)
            return Response(media_type="application/json", content=json.dumps({"ok": False, "error": "Errore server"}), status_code=500)
        finally:
            try:
                conn.close()
            except Exception:
                pass

            
    async def api_users_programs(self, request: Request):
        """Ritorna elenco utenti con i relativi programmi di viaggio (join con citta)."""
        # Allinea la logica di autenticazione all'accesso delle pagine area_super_admin
        super_auth = request.cookies.get("super_auth") or request.cookies.get("auth")
        role = request.cookies.get("role")
        email = request.cookies.get("superadmin_email") or request.cookies.get("user_email")
        if not ((super_auth == "1" and email) or (super_auth == "1" and role == "super_admin") or (request.cookies.get("auth") == "1" and role == "super_admin")):
            return PlainTextResponse("Non autorizzato", status_code=401)

        conn = get_connection()
        if not conn:
            return PlainTextResponse("DB non disponibile", status_code=503)

        try:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT 
                    u.id AS user_id,
                    u.name AS name,
                    u.surname AS surname,
                    u.email AS email,
                    u.profile_image AS profile_image,
                    p.id AS program_id,
                    p.num_locali AS num_locali,
                    p.created_at AS created_at,
                    c.name AS city_name
                FROM Initalya.users u
                LEFT JOIN Initalya.programs p ON p.user_id = u.id
                LEFT JOIN Initalya.cities c ON c.id = p.city_id
                ORDER BY u.id ASC, p.id ASC
                """
            )
            rows = cur.fetchall() or []
            # Prepara output semplice, una riga per ogni programma (o utente senza programma)
            out = []
            for r in rows:
                full_name = (r.get("name") or "")
                if r.get("surname"):
                    full_name = f"{full_name} {r['surname']}".strip()
                out.append({
                    "user_id": r.get("user_id"),
                    "full_name": full_name or r.get("email"),
                    "email": r.get("email"),
                    "profile_image": r.get("profile_image"),
                    "program_id": r.get("program_id"),
                    "city": r.get("city_name"),
                    "num_locali": r.get("num_locali"),
                    "created_at": r.get("created_at").isoformat() if r.get("created_at") else None,
                })
            return Response(media_type="application/json", content=json.dumps({"rows": out}))
        except Exception as e:
            logger.exception("Errore in api_users_programs: %s", e)
            return PlainTextResponse("Errore server", status_code=500)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    async def api_users_programs_count(self, request: Request):
        """Ritorna una riga per utente con il numero totale di programmi."""
        super_auth = request.cookies.get("super_auth") or request.cookies.get("auth")
        role = request.cookies.get("role")
        email = request.cookies.get("superadmin_email") or request.cookies.get("user_email")
        if not ((super_auth == "1" and email) or (super_auth == "1" and role == "super_admin") or (request.cookies.get("auth") == "1" and role == "super_admin")):
            return PlainTextResponse("Non autorizzato", status_code=401)

        conn = get_connection()
        if not conn:
            return PlainTextResponse("DB non disponibile", status_code=503)

        try:
            cur = conn.cursor(dictionary=True)
            # Conta programmi per utente
            cur.execute(
                """
                SELECT 
                    u.id AS user_id,
                    u.name AS name,
                    u.surname AS surname,
                    u.email AS email,
                    u.profile_image AS profile_image,
                    COUNT(p.id) AS programs_count
                FROM Initalya.users u
                LEFT JOIN Initalya.programs p ON p.user_id = u.id
                GROUP BY u.id, u.name, u.surname, u.email, u.profile_image
                ORDER BY u.id ASC
                """
            )
            rows = cur.fetchall() or []
            out = []
            for r in rows:
                full_name = (r.get("name") or "")
                if r.get("surname"):
                    full_name = f"{full_name} {r['surname']}".strip()
                out.append({
                    "user_id": r.get("user_id"),
                    "full_name": full_name or r.get("email"),
                    "email": r.get("email"),
                    "profile_image": r.get("profile_image"),
                    "programs_count": int(r.get("programs_count") or 0),
                })
            return Response(media_type="application/json", content=json.dumps({"rows": out}))
        except Exception as e:
            logger.exception("Errore in api_users_programs_count: %s", e)
            return PlainTextResponse("Errore server", status_code=500)
        finally:
            try:
                conn.close()
            except Exception:
                pass




    async def program_details(self, request: Request, program_id: int):
     auth = request.cookies.get("auth")
     email = request.cookies.get("user_email")

     if auth != "1" or not email:
        return {"success": False, "error": "Non autenticato"}

     conn = get_connection()
     if not conn:
        return {"success": False, "error": "DB non disponibile"}

     try:
        cur = conn.cursor(dictionary=True)

        # Utente
        cur.execute(
            "SELECT id FROM Initalya.users WHERE email = %s",
            (email,)
        )
        user = cur.fetchone()
        if not user:
            return {"success": False, "error": "Utente non trovato"}

        user_id = user["id"]

        # Programma
        cur.execute(
            "SELECT * FROM Initalya.programs WHERE id = %s AND user_id = %s",
            (program_id, user_id)
        )
        program = cur.fetchone()
        if not program:
            return {"success": False, "error": "Programma non trovato"}

        # Citt�
        city_name = ""
        if program.get("city_id"):
            cur.execute(
                "SELECT name FROM Initalya.cities WHERE id = %s",
                (program["city_id"],)
            )
            city = cur.fetchone()
            city_name = city["name"] if city else ""

        # Locali salvati: includi coordinate, immagine e rating se presenti in DB
        cur.execute("""
            SELECT
                l.place_id,
                l.name,
                l.address,
                COALESCE(t.typology, '') AS type,
                l.lat,
                l.lng,
                l.image,
                l.rating
            FROM Initalya.locals l
            LEFT JOIN Initalya.types t ON l.type_id = t.id
            WHERE l.program_id = %s
            ORDER BY l.id ASC
        """, (program_id,))

        locals_rows = cur.fetchall() or []

        return {
            "success": True,
            "program_id": program_id,
            "city_name": city_name,
            "locals": [
                {
                    "place_id": row.get("place_id", ""),
                    "name": row.get("name", ""),
                    "address": row.get("address", ""),
                    "type": row.get("type", ""),
                    "lat": row.get("lat"),
                    "lng": row.get("lng"),
                    "image": row.get("image", ""),
                    "rating": row.get("rating", "")
                }
                for row in locals_rows
            ]
        }

     except Exception as e:
        return {"success": False, "error": str(e)}

     finally:
        conn.close()
   



    async def view_program(self, request: Request, program_id: int):
      auth = request.cookies.get("auth")
      email = request.cookies.get("user_email")

      if auth != "1" or not email:
        return RedirectResponse(
            url=f"/login?next=/program/{program_id}",
            status_code=303
        )

      conn = get_connection()
      if not conn:
         return RedirectResponse(url="/area_riservata", status_code=303)

      try:
        cur = conn.cursor(dictionary=True)

        # Utente
        cur.execute(
            "SELECT id FROM Initalya.users WHERE email = %s",
            (email,)
        )
        user = cur.fetchone()
        if not user:
            return RedirectResponse(url="/area_riservata", status_code=303)

        # Programma
        cur.execute(
            "SELECT id, user_id FROM Initalya.programs WHERE id = %s",
            (program_id,)
        )
        program = cur.fetchone()

        if not program or program["user_id"] != user["id"]:
            return RedirectResponse(url="/area_riservata", status_code=303)

        # ?? Qui � il punto chiave
        return self.templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "restore_program_id": program_id
            }
        )

      finally:
        conn.close()


   




    async def area_riservata(self, request: Request):
        auth = request.cookies.get("auth")
        if auth != "1":
            return RedirectResponse(url="/login?next=/area_riservata", status_code=303)

        user_email = request.cookies.get("user_email")
        user_data = None
        programs = []
        view = request.query_params.get("view") or ""

        ruolo_db = None
        role_num = 3

        if user_email:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            try:
                # Dati utente (Initalya.users per coerenza)
                cursor.execute("SELECT * FROM Initalya.users WHERE email = %s", (user_email,))
                user_data = cursor.fetchone()

                # Determina ruolo SOLO da DB (colonna 'ruolo'), ignorando cookie
                if user_data is not None:
                    ruolo_db = user_data.get("ruolo")
                    if ruolo_db is not None:
                        if isinstance(ruolo_db, int):
                            role_num = ruolo_db
                        else:
                            ruolo_str = str(ruolo_db).strip().lower()
                            mapping = {
                                "utente": 1,
                                "user": 1,
                                "admin": 2,
                                "amministratore": 2,
                                "superadmin": 1,
                                "3": 3,
                                "2": 2,
                                "1": 1,
                            }
                            role_num = mapping.get(ruolo_str, 3)

                # Programmi salvati
                if user_data and user_data.get("id"):
                    cursor.execute(
                        """
                        SELECT p.id as program_id, p.num_locali, c.name as city_name, c.photo as city_photo
                        FROM Initalya.programs p
                        LEFT JOIN Initalya.cities c ON c.id = p.city_id
                        WHERE p.user_id = %s
                        ORDER BY p.id DESC
                        """,
                        (user_data["id"],)
                    )
                    programs = cursor.fetchall()
            finally:
                conn.close()

        template_name = f"area_riservata_{role_num}.html"
        if role_num == 2:
           template_name = "area_riservata_2_full.html"
        
        # Decide il saluto in base al cookie impostato al login
        just_logged_in = (request.cookies.get("just_logged_in") == "1")
        greeting = "Benvenuto" if just_logged_in else "Bentornato"

        resp = self.templates.TemplateResponse(
            template_name,
            {"request": request, "user": user_data, "programs": programs, "view": view, "greeting": greeting}
        )
        # Consuma il flag appena usato
        if just_logged_in:
            try:
                resp.delete_cookie("just_logged_in", path="/")
            except Exception:
                pass
        return resp

    async def profile_page(self, request: Request):
        """Reindirizza alla pagina area_riservata con vista profilo."""
        auth = request.cookies.get("auth")
        if auth != "1":
            return RedirectResponse(url="/login?next=/profile", status_code=303)
        return RedirectResponse(url="/area_riservata?view=profile", status_code=303)

    async def logout(self, request: Request, next: str = "/"):
        resp = RedirectResponse(url=next or "/", status_code=303)
        try:
            resp.delete_cookie("auth")
        except Exception:
            pass
        try:
            resp.delete_cookie("user_email")
        except Exception:
            pass
        try:
            resp.delete_cookie("next")
        except Exception:
            pass
        return resp

    
    async def place_details(self, request: Request, place_id: str):
        """Pagina dettagli luogo"""
        logger.info(f"Richiesta dettagli luogo: {place_id}")
        return self.templates.TemplateResponse(
            "place_details.html", 
            {"request": request, "place_id": place_id}
        )
    
    async def api_place_details(self, place_id: str):
        """API per ottenere i dettagli di un luogo"""
        logger.info(f"API richiesta dettagli luogo: {place_id}")
        return await search_routes_instance.get_controller().get_place_details(place_id)


    async def area_riservata(self, request: Request):
        auth = request.cookies.get("auth")
        if auth != "1":
            return RedirectResponse(url="/login?next=/area_riservata", status_code=303)

        user_email = request.cookies.get("user_email")
        user_data = None
        programs = []
        view = request.query_params.get("view") or ""

        ruolo_db = None
        role_num = 3

        if user_email:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            try:
                # Dati utente (Initalya.users per coerenza)
                cursor.execute("SELECT * FROM Initalya.users WHERE email = %s", (user_email,))
                user_data = cursor.fetchone()

                # Determina ruolo SOLO da DB (colonna 'ruolo'), ignorando cookie
                if user_data is not None:
                    ruolo_db = user_data.get("ruolo")
                    if ruolo_db is not None:
                        if isinstance(ruolo_db, int):
                            role_num = ruolo_db
                        else:
                            ruolo_str = str(ruolo_db).strip().lower()
                            mapping = {
                                "utente": 1,
                                "user": 1,
                                "admin": 2,
                                "amministratore": 2,
                                "superadmin": 1,
                                "3": 3,
                                "2": 2,
                                "1": 1,
                            }
                            role_num = mapping.get(ruolo_str, 3)

                # Programmi salvati
                if user_data and user_data.get("id"):
                    cursor.execute(
                        """
                        SELECT p.id as program_id, p.num_locali, c.name as city_name, c.photo as city_photo
                        FROM Initalya.programs p
                        LEFT JOIN Initalya.cities c ON c.id = p.city_id
                        WHERE p.user_id = %s
                        ORDER BY p.id DESC
                        """,
                        (user_data["id"],)
                    )
                    programs = cursor.fetchall()
            finally:
                conn.close()

        template_name = f"area_riservata_{role_num}.html"
        
        # Decide il saluto in base al cookie impostato al login
        just_logged_in = (request.cookies.get("just_logged_in") == "1")
        greeting = "Benvenuto" if just_logged_in else "Bentornato"

        # Per ruolo 2 (admin), consenti di rendere direttamente una pagina del dashboard usando lo stesso meccanismo dell'area_super_admin
        if role_num == 2:
            dash_page = request.query_params.get("dashboard_page") or "index.html"
            dash_page = re.sub(r"[^A-Za-z0-9._-]", "", dash_page)
            if not dash_page.endswith(".html"):
                dash_page = f"{dash_page}.html"
            return await self._render_dashboard_page(dash_page, request)

        resp = self.templates.TemplateResponse(
            template_name,
            {"request": request, "user": user_data, "programs": programs, "view": view, "greeting": greeting}
        )
        # Consuma il flag appena usato
        if just_logged_in:
            try:
                resp.delete_cookie("just_logged_in", path="/")
            except Exception:
                pass
        return resp


    async def update_profile(self, request: Request):
        """Aggiorna i dati del profilo utente con campi dinamici in base alle colonne disponibili."""
        auth = request.cookies.get("auth")
        current_email = request.cookies.get("user_email")
        if auth != "1" or not current_email:
            return Response(media_type="application/json", content=json.dumps({"ok": False, "error": "Non autenticato"}), status_code=401)

        try:
            data = await request.json()
        except Exception:
            data = {}

        section = (data.get("section") or "").strip()
        # Campi ammessi per ciascuna sezione
        # Normalizza stringhe vuote a None per evitare errori DB (es. DECIMAL '')
        def _norm(v):
            if isinstance(v, str):
                v2 = v.strip()
                return v2 if v2 != "" else None
            return v
        info_fields = {
            "name": _norm(data.get("name")),
            "surname": _norm(data.get("surname")),
            "email": _norm(data.get("email")),
            "phone": _norm(data.get("phone")),
            "city": _norm(data.get("city")),
            "country": _norm(data.get("country")),
            "bio": _norm(data.get("bio")),
        }
        addr_fields = {
            "country": data.get("country"),
            "city": data.get("city"),
            "cap": data.get("cap"),
            "vat_cf": data.get("vat_cf"),
        }

        conn = get_connection()
        if not conn:
            return Response(media_type="application/json", content=json.dumps({"ok": False, "error": "DB non disponibile"}), status_code=503)

        try:
            cur = conn.cursor(dictionary=True)
            # Trova utente corrente
            cur.execute("SELECT id, email FROM Initalya.users WHERE email = %s", (current_email,))
            user = cur.fetchone()
            if not user:
                conn.close()
                return Response(media_type="application/json", content=json.dumps({"ok": False, "error": "Utente non trovato"}), status_code=404)

            user_id = user["id"]

            # Legge colonne tabella per aggiornamento dinamico
            cur.execute("SHOW COLUMNS FROM Initalya.users")
            rows = cur.fetchall()
            # Mappa nome colonna -> tipo (lowercase)
            cols_info = {row["Field"]: (row.get("Type") or "").lower() for row in rows}
            cols = set(cols_info.keys())

            # Seleziona set di campi secondo sezione
            incoming = info_fields if section == "info" else addr_fields if section == "address" else {}
            # Se la colonna "city" esiste ed è numerica, reindirizza a "city_name" per testo libero
            def _is_numeric(t: str) -> bool:
                return bool(re.match(r"^(tinyint|smallint|int|bigint|decimal|float|double|real)", t or ""))
            redirected_incoming = {}
            for k, v in incoming.items():
                if v is None:
                    continue
                if k == "city" and ("city" in cols) and _is_numeric(cols_info.get("city", "")):
                    redirected_incoming["city_name"] = v
                else:
                    redirected_incoming[k] = v
            incoming = redirected_incoming
            # Se alcune colonne richieste non esistono, prova ad aggiungerle dinamicamente
            # Tipi suggeriti per le nuove colonne
            suggested_types = {
                "phone": "VARCHAR(30)",
                "bio": "TEXT",
                "country": "VARCHAR(100)",
                "city": "VARCHAR(100)",
                "city_name": "VARCHAR(100)",
                "cap": "VARCHAR(10)",
                "vat_cf": "VARCHAR(50)",
            }
            missing = [k for k, v in incoming.items() if (v is not None and k not in cols and k in suggested_types)]
            for col in missing:
                try:
                    cur.execute(f"ALTER TABLE Initalya.users ADD COLUMN {col} {suggested_types[col]} NULL")
                    conn.commit()
                    cols.add(col)
                except Exception as e:
                    logger.warning("Impossibile aggiungere colonna %s: %s", col, e)

            update_pairs = [(k, v) for k, v in incoming.items() if (v is not None and k in cols)]

            if not update_pairs:
                return Response(media_type="application/json", content=json.dumps({"ok": False, "error": "Nessun campo aggiornabile"}), status_code=400)

            set_sql = ", ".join([f"{k} = %s" for k, _ in update_pairs])
            values = [v for _, v in update_pairs]
            values.append(user_id)

            cur.execute(f"UPDATE Initalya.users SET {set_sql} WHERE id = %s", tuple(values))
            conn.commit()

            # Gestisce cambio email: aggiorna cookie se necessario
            changed_email = next((v for k, v in update_pairs if k == "email"), None)
            resp = Response(media_type="application/json", content=json.dumps({"ok": True}))
            if changed_email and changed_email != current_email:
                try:
                    resp.set_cookie(key="user_email", value=changed_email, path="/", samesite="lax")
                except Exception:
                    pass
            return resp
        except Exception as e:
            logger.exception("Errore update_profile: %s", e)
            return Response(media_type="application/json", content=json.dumps({"ok": False, "error": "Errore server"}), status_code=500)
        finally:
            try:
                conn.close()
            except Exception:
                pass


    


    def _slugify(self, s: str) -> str:
        t = re.sub(r"\s*\([^)]*\)\s*", " ", s or "")
        t = re.sub(r"[^\w\s-]", "", t, flags=re.UNICODE)
        t = re.sub(r"\s+", " ", t).strip().lower()
        return re.sub(r"[\s-]+", "-", t) or "dish"

    async def google_image_search(self, query: str, cache_folder: str = "assets/images_cache"):
        """Recupera un'immagine tramite Google Custom Search (Image) e la mette in cache.
        Ritorna i bytes dell'immagine o None se non trovata/errore.
        """
        if not query:
            return None
        slug = self._slugify(query)
        cache_dir = Path(cache_folder)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{slug}.jpg"
        if cache_path.exists():
            try:
                return cache_path.read_bytes()
            except Exception:
                pass

        try:
            # Chiavi CSE potrebbero non essere configurate: gestire in modo robusto
            api_key = settings.google_cse_api_key
            cse_id = settings.google_cse_id
        except Exception as e:
            logger.warning(f"Google CSE non configurato: {e}")
            return None

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                params = {
                    "key": api_key,
                    "cx": cse_id,
                    "q": query,
                    "searchType": "image",
                    "num": 5,
                    "safe": "high",
                }
                r = await client.get("https://www.googleapis.com/customsearch/v1", params=params, headers={"Accept": "application/json"})
                if r.status_code == 200:
                    js = r.json()
                    items = js.get("items") or []
                    for it in items:
                        link = it.get("link")
                        if not link:
                            continue
                        try:
                            ir = await client.get(link, headers={"Accept": "image/*"})
                            if ir.status_code == 200 and ir.content:
                                img_bytes = ir.content
                                try:
                                    cache_path.write_bytes(img_bytes)
                                except Exception as e:
                                    logger.warning(f"CSE cache write errore: {e}")
                                return img_bytes
                        except Exception as e:
                            logger.debug(f"CSE image fetch errore: {e}")
                else:
                    logger.warning(f"CSE HTTP {r.status_code}")
        except Exception as e:
            logger.warning(f"Google CSE errore: {e}")
        return None

    async def google_image_search_url(self, query: str, excluded_domains: list[str] | None = None, excluded_keywords: list[str] | None = None, required_keywords: list[str] | None = None) -> str | None:
        """Recupera il primo link immagine tramite Google Custom Search (Image), con possibilità di escludere domini e richiedere keyword obbligatorie."""
        if not query:
            return None
        try:
            api_key = settings.google_cse_api_key
            cse_id = settings.google_cse_id
        except Exception as e:
            logger.warning(f"Google CSE non configurato: {e}")
            return None
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                params = {
                    "key": api_key,
                    "cx": cse_id,
                    "q": query,
                    "searchType": "image",
                    "num": 10,
                    "safe": "high",
                }
                r = await client.get("https://www.googleapis.com/customsearch/v1", params=params, headers={"Accept": "application/json"})
                if r.status_code == 200:
                    js = r.json()
                    items = js.get("items") or []
                    for it in items:
                        link = it.get("link")
                        if link:
                            # Blocca sempre domini sociali noti
                            blocked_social = [
                                "instagram.com",
                                "cdninstagram.com",
                                "instagr.am",
                                "facebook.com",
                                "fbcdn.net",
                                "m.facebook.com",
                                "fbsbx.com",
                                "tiktok.com",
                            ]
                            try:
                                host = urllib.parse.urlparse(link).netloc.lower()
                            except Exception:
                                host = ""
                            if excluded_domains:
                                try:
                                    if any(host == d or host.endswith("." + d) or host.endswith(d) for d in excluded_domains):
                                        continue
                                except Exception:
                                    pass
                            # Esclusione sempre attiva per social
                            try:
                                if any(host == d or host.endswith("." + d) for d in blocked_social):
                                    continue
                            except Exception:
                                pass
                            # Valuta parole chiave su titolo/snippet/link
                            text_blob = " ".join([
                                str(it.get("title") or ""),
                                str(it.get("snippet") or ""),
                                str(link or ""),
                            ]).lower()
                            import unicodedata
                            def _strip_accents(s: str) -> str:
                                try:
                                    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
                                except Exception:
                                    return s
                            text_ascii = _strip_accents(text_blob)
                            # Escludi risultati con keyword indesiderate
                            if excluded_keywords:
                                try:
                                    for kw in excluded_keywords:
                                        kw_l = (kw or '').lower()
                                        kw_a = _strip_accents(kw_l)
                                        if (kw_l and kw_l in text_blob) or (kw_a and kw_a in text_ascii):
                                            raise RuntimeError("skip-item")
                                except RuntimeError:
                                    continue
                            # Richiedi la presenza di keyword obbligatorie (es. città)
                            if required_keywords:
                                try:
                                    ok = False
                                    for kw in required_keywords:
                                        kw_l = (kw or '').lower()
                                        kw_a = _strip_accents(kw_l)
                                        if (kw_l and kw_l in text_blob) or (kw_a and kw_a in text_ascii):
                                            ok = True
                                            break
                                    if not ok:
                                        raise RuntimeError("skip-item")
                                except RuntimeError:
                                    continue
                            return link
                else:
                    logger.warning(f"CSE HTTP {r.status_code}")
        except Exception as e:
            logger.warning(f"Google CSE URL errore: {e}")
        return None

    def _ensure_photo_table(self, conn):
        """Crea la tabella Initalya.photo se non esiste, secondo photo.sql (city_id, url NOT NULL)."""
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS Initalya.photo (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    city_id INT NOT NULL,
                    url VARCHAR(255) NOT NULL,
                    titolo VARCHAR(255) NOT NULL,
                    FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE CASCADE
                )
                """
            )
            conn.commit()
        except Exception as e:
            logger.warning(f"Errore creazione tabella Initalya.photo: {e}")

    async def get_city_dish_image(self, city: str, dish: str):
        """Ottieni immagine piatto per citt�: riusa URL salvato in Initalya.photo o scarica e salva la prima volta.
        
        Questa funzione implementa un sistema di caching per le immagini dei piatti specifici di ogni citt�.
        Alla prima ricerca di un piatto in una citt�, l'immagine viene scaricata e salvata nel database.
        Le ricerche successive riutilizzano l'URL salvato.
        """
        if not city or not dish:
            logger.warning(f"Parametri mancanti: city={city}, dish={dish}")
            return None
        
        city_name = city.strip()
        dish_name = dish.strip()
        logger.info(f"🔍 Ricerca immagine per piatto: '{dish_name}' nella citt�: '{city_name}'")
        
        try:
            conn = get_connection()
            if not conn:
                logger.warning("Connessione DB non disponibile per get_city_dish_image")
                return None
                
            cur = conn.cursor(dictionary=True)
            
            # Trova l'ID della citt�
            cur.execute("SELECT id FROM Initalya.cities WHERE name = %s LIMIT 1", (city_name,))
            city_row = cur.fetchone()
            
            if not city_row:
                # Se la citt� non esiste, la inseriamo
                cur.execute("INSERT INTO Initalya.cities (name) VALUES (%s)", (city_name,))
                city_id = cur.lastrowid
                conn.commit()
                logger.info(f"✅ Creata nuova citt�: {city_name} (id: {city_id})")
            else:
                city_id = city_row['id']
                logger.info(f"✅ Citt� trovata: {city_name} (id: {city_id})")
            
            # Controlla se esiste gi� un'immagine per questo piatto in questa citt�
            # Cerca immagini con titolo che contiene il nome del piatto per questa citt� specifica
            dish_query = f"{dish_name} {city_name}"
            logger.info(f"🔍 Ricerca immagine per piatto '{dish_name}' in citt� '{city_name}' (city_id: {city_id})")
            logger.info(f"🔍 Query di ricerca: titolo LIKE '%{dish_name}%' OR titolo LIKE '%{dish_query}%' OR titolo LIKE '%{city_name}%'")
            
            cur.execute("""
                SELECT url, id, titolo FROM Initalya.photo 
                WHERE city_id = %s AND (
                    titolo LIKE %s OR 
                    titolo LIKE %s OR 
                    titolo LIKE %s
                )
                ORDER BY id DESC 
                LIMIT 1
            """, (city_id, f"%{dish_name}%", f"%{dish_query}%", f"%{city_name}%"))
            photo_row = cur.fetchone()
            
            # Se troviamo un'immagine per questo piatto in questa citt�, la restituiamo (se non social)
            if photo_row and photo_row['url']:
                try:
                    host = urllib.parse.urlparse(photo_row['url']).netloc.lower()
                    if any(host == d or host.endswith("." + d) for d in [
                        "instagram.com", "cdninstagram.com", "instagr.am", "facebook.com", "fbcdn.net", "m.facebook.com", "fbsbx.com", "tiktok.com"
                    ]):
                        logger.info(f"⛔ URL cache su dominio social ignorato: {photo_row['url']}")
                    else:
                        logger.info(f"✅ Immagine trovata in cache per piatto '{dish_name}' in citt� '{city_name}': {photo_row['url']} (titolo: {photo_row['titolo']})")
                        conn.close()
                        return photo_row['url']
                except Exception:
                    logger.info(f"✅ Immagine trovata in cache per piatto '{dish_name}' in citt� '{city_name}': {photo_row['url']} (titolo: {photo_row['titolo']})")
                    conn.close()
                    return photo_row['url']
            else:
                logger.info(f"🔄 Nessuna immagine trovata in cache per piatto '{dish_name}' in citt� '{city_name}'")
            
            # Se non esiste, scarica l'immagine
            url = await self.google_image_search_url(dish_query, excluded_domains=["wikipedia.org", "wikimedia.org"])
            
            if not url:
                logger.warning(f"Impossibile trovare immagine per piatto '{dish_name}' in citt� '{city_name}'")
                conn.close()
                return None
            
            # Salva l'URL nella tabella photo con il nome del piatto come titolo
            logger.info(f"💾 Salvataggio nuova immagine per piatto '{dish_name}' in citt� '{city_name}' (city_id: {city_id}): {url}")
            cur.execute("INSERT INTO Initalya.photo (city_id, url, titolo) VALUES (%s, %s, %s)", (city_id, url, dish_name))
            conn.commit()
            logger.info(f"✅ Immagine salvata con successo per piatto '{dish_name}' in citt� '{city_name}' (city_id: {city_id})")
            
            conn.close()
            return url
            
        except Exception as e:
            logger.error(f"Errore in get_city_dish_image per '{dish_name}' in '{city_name}': {e}")
            return None

    async def image_search(self, request: Request):
        """Reindirizza a un link immagine ottenuto via Google CSE con salvataggio nel database."""
        # Estrai i parametri dalla query string
        query_params = request.query_params
        dish = query_params.get("dish")
        city = query_params.get("city")
        
        if not dish:
            raise HTTPException(status_code=400, detail="Parametro 'dish' mancante")
        
        name = dish.strip()
        query = name
        city_name = None
        
        if city:
            c = city.strip()
            if c:
                query = f"{name} {c}"
                city_name = c
                logger.info(f"🎯 Città '{city_name}' fornita esplicitamente dal parametro city")
        
        # Se nessuna città è specificata (esplicitamente), prova a estrarla dal nome del piatto
        if not city_name:
            # Estrai la città dal nome del piatto se presente (es. "Spaghetti all'Assassina Bari")
            # Questo è utile quando il piatto contiene il nome della città
            words = name.split()
            for word in words:
                # Controlla se questa parola potrebbe essere una città italiana
                if len(word) > 2 and word[0].isupper():
                    # Prova a cercare questa parola come città nel database
                    conn = get_connection()
                    if conn:
                        try:
                            cur = conn.cursor(dictionary=True)
                            # Cerca corrispondenza esatta prima
                            cur.execute("SELECT name FROM Initalya.cities WHERE name = %s LIMIT 1", (word,))
                            city_row = cur.fetchone()
                            if city_row:
                                city_name = city_row['name']
                                logger.info(f"🎯 Città '{city_name}' estratta dal nome del piatto '{name}'")
                                query = f"{name} {city_name}"
                                conn.close()
                                break
                            else:
                                # Prova con corrispondenza parziale
                                cur.execute("SELECT name FROM Initalya.cities WHERE name LIKE %s LIMIT 1", (f"%{word}%",))
                                city_row = cur.fetchone()
                                if city_row:
                                    city_name = city_row['name']
                                    logger.info(f"🎯 Città '{city_name}' estratta (corrispondenza parziale) dal nome del piatto '{name}'")
                                    query = f"{name} {city_name}"
                                    conn.close()
                                    break
                            conn.close()
                        except Exception as e:
                            logger.warning(f"Errore nel tentativo di estrarre città dal piatto: {e}")
                            if conn:
                                conn.close()
        
        if city_name:
            logger.info(f"Richiesta immagine per dish='{name}' con city='{city_name}'")
        else:
            logger.info(f"Richiesta immagine per dish='{name}' senza città specificata")
        
        # Prova a trovare la città nel database
        city_id = None
        if city_name:
            conn = get_connection()
            if conn:
                try:
                    cur = conn.cursor(dictionary=True)
                    cur.execute("SELECT id FROM Initalya.cities WHERE name = %s LIMIT 1", (city_name,))
                    city_row = cur.fetchone()
                    if city_row:
                        city_id = city_row['id']
                        logger.info(f"✅ Città '{city_name}' trovata con ID: {city_id}")
                    else:
                        # Se la città non esiste, la inserisce
                        logger.info(f"Città '{city_name}' non trovata, la inserisco nel database")
                        cur.execute("INSERT INTO Initalya.cities (name) VALUES (%s)", (city_name,))
                        city_id = cur.lastrowid
                        conn.commit()
                        logger.info(f"✅ Inserita nuova città '{city_name}' con ID: {city_id}")
                    conn.close()
                except Exception as e:
                    logger.warning(f"Errore nel recupero/inserimento città '{city_name}': {e}")
                    if conn:
                        conn.close()
        
        # Controlla se l'immagine esiste già nel database (cache) in modo più permissivo
        if city_id is not None:
            conn = get_connection()
            if conn:
                try:
                    cur = conn.cursor(dictionary=True)
                    logger.info(f"🔍 Controllo cache per dish='{name}' e city_id={city_id} (match esatto o parziale)")

                    # Prova prima match esatto, poi parziale sul titolo
                    cur.execute(
                        """
                        SELECT url FROM Initalya.photo
                        WHERE city_id = %s AND (titolo = %s OR titolo LIKE %s)
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        (city_id, name, f"%{name}%")
                    )
                    photo_row = cur.fetchone()

                    if photo_row and photo_row['url']:
                        try:
                            host = urllib.parse.urlparse(photo_row['url']).netloc.lower()
                            if any(host == d or host.endswith("." + d) for d in [
                                "instagram.com", "cdninstagram.com", "instagr.am", "facebook.com", "fbcdn.net", "m.facebook.com", "fbsbx.com", "tiktok.com"
                            ]):
                                logger.info(f"⛔ URL cache su dominio social ignorato: {photo_row['url']}")
                            else:
                                logger.info(f"✅ Immagine trovata in cache per '{name}' nella città {city_id}: {photo_row['url']}")
                                conn.close()
                                return RedirectResponse(photo_row['url'])
                        except Exception:
                            logger.info(f"✅ Immagine trovata in cache per '{name}' nella città {city_id}: {photo_row['url']}")
                            conn.close()
                            return RedirectResponse(photo_row['url'])

                    logger.info("🔄 Immagine non trovata in cache per città specifica, valuterò fallback globale")
                    conn.close()
                except Exception as e:
                    logger.warning(f"Errore nel controllo cache: {e}")
                    try:
                        conn.close()
                    except Exception:
                        pass

        # Fallback: cerca in cache globale per titolo quando la città non è disponibile o non dà risultati
        if city_id is None:
            conn = get_connection()
            if conn:
                try:
                    cur = conn.cursor(dictionary=True)
                    logger.info(f"🔍 Fallback cache globale per dish='{name}' (match esatto o parziale)")
                    cur.execute(
                        """
                        SELECT url, city_id, titolo FROM Initalya.photo
                        WHERE titolo = %s OR titolo LIKE %s
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        (name, f"%{name}%")
                    )
                    photo_row = cur.fetchone()
                    if photo_row and photo_row['url']:
                        try:
                            host = urllib.parse.urlparse(photo_row['url']).netloc.lower()
                            if any(host == d or host.endswith("." + d) for d in [
                                "instagram.com", "cdninstagram.com", "instagr.am", "facebook.com", "fbcdn.net", "tiktok.com"
                            ]):
                                logger.info(f"⛔ URL cache su dominio social ignorato: {photo_row['url']}")
                            else:
                                logger.info(
                                    f"✅ Immagine trovata in cache globale per '{name}': {photo_row['url']} (city_id={photo_row.get('city_id')}, titolo='{photo_row.get('titolo')}')"
                                )
                                conn.close()
                                return RedirectResponse(photo_row['url'])
                        except Exception:
                            logger.info(
                                f"✅ Immagine trovata in cache globale per '{name}': {photo_row['url']} (city_id={photo_row.get('city_id')}, titolo='{photo_row.get('titolo')}')"
                            )
                            conn.close()
                            return RedirectResponse(photo_row['url'])
                    logger.info("🔄 Nessuna immagine trovata in cache globale, procederò con Google CSE")
                    conn.close()
                except Exception as e:
                    logger.warning(f"Errore nel controllo cache globale: {e}")
                    try:
                        conn.close()
                    except Exception:
                        pass
        
        # Scarica l'immagine da Google CSE
        url = await self.google_image_search_url(query, excluded_domains=["wikipedia.org", "wikimedia.org"])
        
        if not url:
            logger.warning(f"❌ Impossibile trovare immagine per '{name}' su Google CSE")
            raise HTTPException(status_code=502, detail="Immagine non disponibile via Google CSE")
        
        logger.info(f"✅ Immagine trovata su Google CSE per '{name}': {url}")

        # Prepara il redirect con status 307
        redirect_response = RedirectResponse(url, status_code=307)

        # Salva l'immagine nel database SOLO se rispondiamo con messaggio 307
        if city_id and redirect_response.status_code == 307:
            conn = get_connection()
            if conn:
                try:
                    cur = conn.cursor()
                    # Evita salvataggi se l'URL appartiene a un dominio social
                    try:
                        host = urllib.parse.urlparse(url).netloc.lower()
                        if any(host == d or host.endswith("." + d) for d in [
                            "instagram.com", "cdninstagram.com", "instagr.am", "facebook.com", "fbcdn.net", "m.facebook.com", "fbsbx.com", "tiktok.com"
                        ]):
                            logger.info(f"⛔ Salvataggio evitato per URL social: {url}")
                        else:
                            logger.info(f"💾 Salvataggio immagine nel database per '{name}' con city_id={city_id} (solo se 307)")
                            cur.execute("INSERT INTO Initalya.photo (city_id, url, titolo) VALUES (%s, %s, %s)", 
                                       (city_id, url, name))
                            conn.commit()
                            logger.info(f"✅ Immagine salvata con successo per '{name}' nella città {city_id}: {url}")
                    except Exception as e:
                        logger.warning(f"Errore nel controllo dominio social per salvataggio: {e}")
                    conn.close()
                except Exception as e:
                    logger.warning(f"Errore nel salvataggio immagine: {e}")
                    if conn:
                        conn.close()

        return redirect_response

    async def city_image(self, city: str):
        """Reindirizza a un'immagine città: riusa URL salvato in Initalya.cities o salva la prima volta."""
        if not city:
            raise HTTPException(status_code=400, detail="Parametro 'city' mancante")
        name = city.strip()

        # Prima: prova a riutilizzare URL già salvato per questa città
        try:
            conn = get_connection()
            if conn:
                self._ensure_photo_table(conn)
                cur = conn.cursor()
                try:
                    cur.execute("SELECT photo FROM Initalya.cities WHERE name = %s LIMIT 1", (name,))
                    row = cur.fetchone()
                    if row and row[0]:
                        saved_url = row[0]
                        logger.info(f"URL foto città già salvato trovato: {name} -> {saved_url}")
                        conn.close()
                        return RedirectResponse(saved_url)
                except Exception as e:
                    logger.warning(f"Errore lettura Initalya.cities per città '{name}': {e}")
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Errore accesso DB per riuso foto città '{name}': {e}")

        # Se non c'è già, ottieni esclusivamente un URL immagine via Google CSE
        url = await self.google_image_search_url(name)
        if not url:
            raise HTTPException(status_code=502, detail="Immagine città non disponibile via Google CSE")

        # Inserisci nuova riga (citta, url) solo se non esiste già
        try:
            conn = get_connection()
            if conn:
                self._ensure_photo_table(conn)
                cur = conn.cursor()
                try:
                    # Inserisce solo se non esiste già una riga per la città
                    cur.execute("SELECT id, photo FROM Initalya.cities WHERE name = %s LIMIT 1", (name,))
                    exists = cur.fetchone()
                    if exists:
                        cur.execute("UPDATE Initalya.cities SET photo = %s WHERE name = %s", (url, name))
                        conn.commit()
                        logger.info(f"Aggiornata foto città (colonna 'photo') in Initalya.cities: {name} -> {url}")
                    else:
                        cur.execute("INSERT INTO Initalya.cities (name, photo) VALUES (%s, %s)", (name, url))
                        conn.commit()
                        logger.info(f"Persistenza foto città (colonna 'photo') in Initalya.cities: {name} -> {url}")
                except Exception as e:
                    logger.warning(f"Errore inserimento/aggiornamento Initalya.cities per città '{name}': {e}")
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Errore nel salvataggio foto città per '{name}': {e}")

        # Reindirizza al link trovato via CSE
        return RedirectResponse(url)

    async def city_dish_image(self, city: str, dish: str):
        """Endpoint per ottenere immagini di piatti specifici per citt� con caching nel database."""
        if not city or not dish:
            raise HTTPException(status_code=400, detail="Parametri 'city' e 'dish' richiesti")
        
        city_name = city.strip()
        dish_name = dish.strip()
        
        # Prova a recuperare l'immagine salvata
        image_url = await self.get_city_dish_image(city_name, dish_name)
        
        if image_url:
            return RedirectResponse(image_url)
        else:
            raise HTTPException(status_code=502, detail="Immagine piatto non disponibile via Google CSE")

    async def get_intro_page_image(self, item_name: str, city_id: int) -> Optional[str]:
        """Ottieni immagine per la pagina intro con caching nel database, associata a una città specifica.
        
        Questa funzione implementa un sistema di caching generico per le immagini della pagina intro.
        Alla prima ricerca di un elemento, l'immagine viene scaricata e salvata nel database.
        Le ricerche successive riutilizzano l'URL salvato.
        """
        if not item_name or not city_id:
            logger.warning(f"Parametri invalidi: item_name={item_name}, city_id={city_id}")
            return None
        
        item_name = item_name.strip()
        logger.info(f"🔍 Ricerca immagine per item='{item_name}' nella città ID={city_id}")
        
        try:
            conn = get_connection()
            if not conn:
                logger.warning("❌ Connessione DB non disponibile per get_intro_page_image")
                return None
                
            cur = conn.cursor(dictionary=True)
            
            # Controlla se esiste già un'immagine per questo elemento nella città specificata
            titolo = item_name  # Usa direttamente item_name come titolo per la tabella photo
            logger.info(f"🔍 Controllo cache per titolo='{titolo}' e city_id={city_id}")
            
            cur.execute("""
                SELECT url, id, titolo FROM Initalya.photo 
                WHERE city_id = %s AND titolo = %s
                ORDER BY id DESC 
                LIMIT 1
            """, (city_id, titolo))
            photo_row = cur.fetchone()
            
            if photo_row and photo_row['url']:
                # Immagine trovata nel cache: ignora se proviene da domini social
                try:
                    host = urllib.parse.urlparse(photo_row['url']).netloc.lower()
                    if any(host == d or host.endswith("." + d) for d in [
                        "instagram.com", "cdninstagram.com", "instagr.am", "facebook.com", "fbcdn.net", "tiktok.com"
                    ]):
                        logger.info(f"⛔ URL cache su dominio social ignorato: {photo_row['url']}")
                    else:
                        logger.info(f"✅ Immagine trovata in cache per '{titolo}' nella città {city_id}: {photo_row['url']}")
                        conn.close()
                        return photo_row['url']
                except Exception:
                    logger.info(f"✅ Immagine trovata in cache per '{titolo}' nella città {city_id}: {photo_row['url']}")
                    conn.close()
                    return photo_row['url']
            
            logger.info(f"🔄 Immagine non trovata in cache, procedo con download da Google CSE")
            
            # Se non esiste, scarica l'immagine da Google CSE
            url = await self.google_image_search_url(titolo, excluded_domains=["wikipedia.org", "wikimedia.org"])
            
            if not url:
                logger.warning(f"❌ Impossibile trovare immagine per '{item_name}' su Google CSE")
                conn.close()
                return None
            
            logger.info(f"✅ Immagine trovata su Google CSE per '{item_name}': {url}")
            
            # Salva l'URL nella tabella photo con il titolo come identificatore (evita domini social)
            try:
                host = urllib.parse.urlparse(url).netloc.lower()
                if any(host == d or host.endswith("." + d) for d in [
                    "instagram.com", "cdninstagram.com", "instagr.am", "facebook.com", "fbcdn.net", "tiktok.com"
                ]):
                    logger.info(f"⛔ Salvataggio evitato per URL social: {url}")
                else:
                    logger.info(f"💾 Salvataggio immagine nel database per '{titolo}' con city_id={city_id}")
                    cur.execute("INSERT INTO Initalya.photo (city_id, url, titolo) VALUES (%s, %s, %s)", 
                               (city_id, url, titolo))
                    conn.commit()
                    logger.info(f"✅ Immagine salvata con successo per '{titolo}' nella città {city_id}: {url}")
            except Exception as e:
                logger.warning(f"Errore controllo dominio social per salvataggio intro: {e}")
            
            conn.close()
            return url
            
        except Exception as e:
            logger.error(f"❌ Errore in get_intro_page_image per '{item_name}' città {city_id}: {e}")
            return None

    async def intro_page_image(self, city: str, item: str):
        """Endpoint per ottenere immagini della pagina intro con caching nel database, associate a una città."""
        if not city or not item:
            logger.error(f"Parametri mancanti: city={city}, item={item}")
            raise HTTPException(status_code=400, detail="Parametri 'city' e 'item' richiesti")
        
        city_name = city.strip()
        item_name = item.strip()
        logger.info(f"Richiesta immagine intro per città='{city_name}', item='{item_name}'")
        
        # Trova o crea la città nel database
        conn = get_connection()
        if not conn:
            logger.error("Database non disponibile per intro_page_image")
            raise HTTPException(status_code=503, detail="Database non disponibile")
        
        try:
            cur = conn.cursor(dictionary=True)
            
            # Verifica se la città esiste
            logger.info(f"Verifico esistenza città '{city_name}' nel database")
            cur.execute("SELECT id FROM Initalya.cities WHERE name = %s LIMIT 1", (city_name,))
            city_row = cur.fetchone()
            
            if not city_row:
                # Se la città non esiste, la inserisce nel database
                logger.info(f"Città '{city_name}' non trovata, la inserisco nel database")
                cur.execute("INSERT INTO Initalya.cities (name) VALUES (%s)", (city_name,))
                city_id = cur.lastrowid
                conn.commit()
                logger.info(f"✅ Inserita nuova città '{city_name}' con ID: {city_id}")
            else:
                city_id = city_row['id']
                logger.info(f"✅ Città '{city_name}' trovata con ID: {city_id}")
            
            conn.close()
            
            # Prova a recuperare l'immagine salvata per questa città
            logger.info(f"Provo a recuperare immagine per item='{item_name}' e città ID={city_id}")
            image_url = await self.get_intro_page_image(item_name, city_id)
            
            if image_url:
                logger.info(f"✅ Immagine trovata e restituita: {image_url}")
                return RedirectResponse(image_url)
            else:
                logger.warning(f"❌ Immagine non trovata per '{item_name}' nella città {city_name}")
                raise HTTPException(status_code=502, detail="Immagine non disponibile via Google CSE")
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Errore nel recupero città per intro_page_image: {e}")
            raise HTTPException(status_code=500, detail="Errore interno del server")

    async def login_page(self, request: Request, next: str = "/"):
        resp = self.templates.TemplateResponse("login.html", {"request": request, "next": next})
        try:
            if next:
                resp.set_cookie("next", next)
        except Exception:
            pass
        return resp

    async def login_super_admin(self, request: Request, next: str = "/"):
        resp = self.templates.TemplateResponse("login_super_admin.html", {"request": request, "next": next})
        try:
            if next:
                resp.set_cookie("next", next)
        except Exception:
            pass
        return resp

    async def login_super_admin_submit(self, request: Request):
        form = await request.form()
        email = (form.get("email") or "").strip()
        password = (form.get("password") or "").strip()
        remember = form.get("remember")
        if not email or not password:
            return self.templates.TemplateResponse(
                "login_super_admin.html",
                {"request": request, "error_message": "Credenziali mancanti."}
            )
        conn = get_connection()
        if not conn:
            return self.templates.TemplateResponse(
                "login_super_admin.html",
                {"request": request, "error_message": "Database non disponibile."}
            )
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM Initalya.superadmins WHERE email = %s", (email,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return self.templates.TemplateResponse(
                    "login_super_admin.html",
                    {"request": request, "error_message": "Email o password non corretti."}
                )
            ok = False
            err_msg = None
            # Verifica password con bcrypt se disponibile
            try:
                import bcrypt  # type: ignore
            except ImportError:
                err_msg = "Modulo 'bcrypt' non installato. Installa con: pip install bcrypt"
                ok = False
            else:
                hashed_str = (row.get("password") or "")
                if not hashed_str:
                    err_msg = "Password non impostata per l'utente."
                    ok = False
                else:
                    try:
                        ok = bcrypt.checkpw(password.encode("utf-8"), hashed_str.encode("utf-8"))
                    except ValueError:
                        # Hash non valido (salt/formato errato)
                        err_msg = "Hash password non valido in archivio."
                        ok = False
                    except Exception as _e:
                        logger.warning(f"Errore verifica bcrypt: {_e}")
                        err_msg = "Errore durante la verifica della password."
                        ok = False
            conn.close()
            if not ok:
                return self.templates.TemplateResponse(
                    "login_super_admin.html",
                    {"request": request, "error_message": err_msg or "Email o password non corretti."}
                )
            # Login OK: imposta cookie e reindirizza all'area super admin
            next_url = form.get("next") or str(request.query_params.get("next") or "/area_super_admin")
            resp = RedirectResponse(url=next_url, status_code=303)
            resp.set_cookie(key="auth", value="1", httponly=True, path="/", samesite="lax")
            resp.set_cookie(key="user_email", value=email, path="/", samesite="lax")
            resp.set_cookie(key="role", value="super_admin", path="/", samesite="lax")
            if remember == "1":
                try:
                    # 30 giorni
                    resp.set_cookie(key="auth", value="1", httponly=True, path="/", samesite="lax", max_age=2592000)
                    resp.set_cookie(key="user_email", value=email, path="/", samesite="lax", max_age=2592000)
                    resp.set_cookie(key="role", value="super_admin", path="/", samesite="lax", max_age=2592000)
                except Exception:
                    pass
            return resp
        except Exception as e:
            try:
                conn.close()
            except Exception:
                pass
            return self.templates.TemplateResponse(
                "login_super_admin.html",
                {"request": request, "error_message": f"Errore imprevisto: {str(e)}"}
            )

    async def login_submit(self, request: Request):
        form = await request.form()
        # Reindirizza sempre all'area riservata dopo login
        resp = RedirectResponse(url="/area_riservata", status_code=303)
        user_email = form.get("email") or "user"
        resp.set_cookie(key="auth",value="1",httponly=True,path="/",samesite="lax")
        resp.set_cookie(key="user_email",value=user_email,path="/",samesite="lax")

        # Imposta cookie con numero ruolo se disponibile nel DB (fallback 3)
        role_num = 3
        conn = get_connection()
        try:
            if conn:
                cur = conn.cursor(dictionary=True)
                try:
                    cur.execute("SELECT * FROM Initalya.users WHERE email = %s", (user_email,))
                    row = cur.fetchone() or {}
                    for key in ("role_number", "role", "user_role"):
                        val = row.get(key)
                        if val is not None:
                            try:
                                role_num = int(val)
                            except Exception:
                                pass
                            break
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            resp.set_cookie(key="role_num", value=str(role_num), path="/", samesite="lax")
        except Exception:
            pass
        return resp

    async def save_itinerary(self, request: Request):
        auth = request.cookies.get("auth")
        email = request.cookies.get("user_email")

        if auth != "1" or not email:
            return {"success": False, "error": "Non autenticato"}

        data = await request.json()
        logger.info(f"DEBUG save_itinerary payload: {data}")
        city = data.get("city")
        # Accetta sia 'locali' (payload frontend) sia 'manualSelection' (fallback)
        locali = data.get("locali") or data.get("manualSelection") or []
        # Usa il campo 'num_locali' se presente, altrimenti calcola dalla lista
        try:
            num_locali = int(data.get("num_locali") or len(locali))
        except Exception:
            num_locali = len(locali)

        conn = get_connection()
        if not conn:
            return {"success": False, "error": "Connessione DB non disponibile"}
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id FROM Initalya.users WHERE email = %s", (email,))
            user = cursor.fetchone()
            if not user:
                return {"success": False, "error": "Utente non trovato"}

            user_id = user["id"]

            has_city = False
            has_city_id = False
            try:
                cursor.execute("SHOW COLUMNS FROM Initalya.programs LIKE 'city'")
                has_city = cursor.fetchone() is not None
                cursor.execute("SHOW COLUMNS FROM Initalya.programs LIKE 'city_id'")
                has_city_id = cursor.fetchone() is not None
            except Exception:
                pass

            if has_city_id:
                def _norm_city(s: str) -> str:
                    t = (s or "").strip()
                    if not t or t.lower() == "none":
                        return ""
                    t = re.sub(r",.*$", "", t)
                    t = re.sub(r"\s+[A-Z]{2}$", "", t)
                    t = re.sub(r"\b(italia|italy)\b", "", t, flags=re.I)
                    t = re.sub(r"\s+", " ", t).strip()
                    return t
                city_name = _norm_city(city) or "Non specificata"
                cursor.execute("SELECT id FROM Initalya.cities WHERE LOWER(name) = LOWER(%s)", (city_name,))
                c = cursor.fetchone()
                if not c:
                    cursor.execute("SELECT id FROM Initalya.cities WHERE name LIKE %s", (f"%{city_name}%",))
                    c = cursor.fetchone()
                if c:
                    city_id = c.get("id") if isinstance(c, dict) else c[0]
                else:
                    cursor.execute("INSERT INTO Initalya.cities (name) VALUES (%s)", (city_name,))
                    city_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO Initalya.programs (user_id, num_locali, city_id) VALUES (%s, %s, %s)",
                    (user_id, num_locali, city_id)
                )
            elif has_city:
                cursor.execute(
                    "INSERT INTO Initalya.programs (user_id, num_locali, city) VALUES (%s, %s, %s)",
                    (user_id, num_locali, (city or ""))
                )
            else:
                cursor.execute(
                    "INSERT INTO Initalya.programs (user_id, num_locali) VALUES (%s, %s)",
                    (user_id, num_locali)
                )
            program_id = cursor.lastrowid

            # Inserimento locali con rilevamento dinamico delle colonne per compatibilit� schema
            try:
                cursor.execute("SHOW COLUMNS FROM Initalya.locals")
                rows = cursor.fetchall() or []
                loc_cols = [ (r.get("Field") if isinstance(r, dict) else r[0]) for r in rows ]
            except Exception:
                loc_cols = []

            prog_candidates = ["program_id", "programma_id", "programId", "program", "id_programma"]
            prog_col = next((c for c in prog_candidates if c in loc_cols), "program_id")
            name_col = "name" if "name" in loc_cols else ("nome" if "nome" in loc_cols else "name")
            addr_col = "address" if "address" in loc_cols else ("indirizzo" if "indirizzo" in loc_cols else "address")
            type_col = "type_id" if "type_id" in loc_cols else ("type" if "type" in loc_cols else None)
            place_col = "place_id" if "place_id" in loc_cols else None
            # Coordinate e immagine (persistenza opzionale se colonne presenti)
            lat_col = "lat" if "lat" in loc_cols else ("latitude" if "latitude" in loc_cols else None)
            lng_col = "lng" if "lng" in loc_cols else ("longitude" if "longitude" in loc_cols else ("long" if "long" in loc_cols else None))
            image_col = (
                "image" if "image" in loc_cols else (
                    "photo" if "photo" in loc_cols else (
                        "photo_url" if "photo_url" in loc_cols else None
                    )
                )
            )
            rating_col = "rating" if "rating" in loc_cols else None

            def _extract_pid_from_url(u: str) -> str:
                try:
                    m = re.search(r"place_id:([^&]+)", u or "")
                    return m.group(1) if m else ""
                except Exception:
                    return ""

            def _fallback_pid(loc: dict) -> str:
                base = f"{loc.get('name','').strip()}|{loc.get('address','').strip()}"
                h = hashlib.md5(base.encode("utf-8")).hexdigest()[:16]
                return f"manual_{h}"

            for loc in locali:
                columns = [prog_col]
                values = [program_id]

                if name_col:
                    columns.append(name_col)
                    values.append((loc.get("name") or ""))
                if addr_col:
                    columns.append(addr_col)
                    values.append((loc.get("address") or ""))

                if type_col:
                    if type_col == "type_id":
                        type_str = (loc.get("type") or "").strip()
                        type_id = None
                        try:
                            cursor.execute("SELECT id FROM Initalya.types WHERE LOWER(typology) = LOWER(%s)", (type_str,))
                            rr = cursor.fetchone()
                            type_id = (rr.get("id") if isinstance(rr, dict) else (rr[0] if rr else None))
                        except Exception:
                            type_id = None
                        if not type_id:
                            # fallback: 3 = Ristoranti se presente, altrimenti 1
                            try:
                                cursor.execute("SELECT id FROM Initalya.types WHERE LOWER(typology) = LOWER(%s)", ("ristoranti",))
                                rr2 = cursor.fetchone()
                                type_id = (rr2.get("id") if isinstance(rr2, dict) else (rr2[0] if rr2 else None)) or 1
                            except Exception:
                                type_id = 1
                        columns.append(type_col)
                        values.append(type_id)
                    else:
                        columns.append(type_col)
                        values.append((loc.get("type") or ""))

                if place_col:
                    pid = (loc.get("place_id") or _extract_pid_from_url(loc.get("url") or "") or "").strip()
                    if not pid:
                        pid = _fallback_pid(loc)
                    columns.append(place_col)
                    values.append(pid)

                # Persisti lat/lng se presenti nello schema
                if lat_col:
                    columns.append(lat_col)
                    try:
                        values.append(loc.get("lat", None))
                    except Exception:
                        values.append(None)
                if lng_col:
                    columns.append(lng_col)
                    try:
                        values.append(loc.get("lng", None))
                    except Exception:
                        values.append(None)

                # Persisti immagine se presente nello schema, tronca dinamicamente alla lunghezza della colonna (default 512)
                if image_col:
                    columns.append(image_col)
                    img = (loc.get("image") or loc.get("photo") or loc.get("photo_url") or "")
                    try:
                        if isinstance(img, str):
                            try:
                                # Prova a leggere la lunghezza della colonna da INFORMATION_SCHEMA
                                cursor.execute(
                                    "SELECT CHARACTER_MAXIMUM_LENGTH, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s",
                                    ("Initalya", "locals", image_col)
                                )
                                row = cursor.fetchone()
                                if row:
                                    max_len, data_type = row
                                    # Se TEXT/xxxTEXT, non troncare; se VARCHAR/CHAR, tronca alla lunghezza
                                    if data_type and str(data_type).lower().endswith("text"):
                                        pass
                                    elif max_len and isinstance(max_len, int) and len(img) > max_len:
                                        img = img[:max_len]
                                else:
                                    # Fallback: tronca a 512
                                    if len(img) > 512:
                                        img = img[:512]
                            except Exception:
                                # Fallback sicuro: tronca a 512
                                if len(img) > 512:
                                    img = img[:512]
                    except Exception:
                        pass
                    values.append(img)

                # Persisti rating se presente nello schema
                if rating_col:
                    columns.append(rating_col)
                    try:
                        values.append(loc.get("rating", None))
                    except Exception:
                        values.append(None)

                placeholders = ", ".join(["%s"] * len(values))
                sql = f"INSERT INTO Initalya.locals ({', '.join(columns)}) VALUES ({placeholders})"
                cursor.execute(sql, tuple(values))

            conn.commit()
            # Salva due file JSON: (1) contenuto pagina 1 (piatti tipici), (2) risultati strutturati pagina 3
            try:
                import os as _os, json as _json
                # Usa BASE_DIR per garantire il percorso assoluto corretto dentro il package sitesense
                save_dir = _os.path.join(str(BASE_DIR), "assets", "saved_itineraries")
                _os.makedirs(save_dir, exist_ok=True)

                # (1) Pagina 1: piatti tipici (HTML)
                page1_html = data.get("page1_html") or ""
                page1_payload = {
                    "program_id": program_id,
                    "city": (city or ""),
                    "page1_html": page1_html,
                }
                page1_path = _os.path.join(save_dir, f"page1_{program_id}.json")
                with open(page1_path, "w", encoding="utf-8") as f:
                    _json.dump(page1_payload, f, ensure_ascii=False)

                # (2) Risultati strutturati pagina 3
                ranked_struct = data.get("page3_ranked") or data.get("ranked") or {}
                page3_payload = {
                    "program_id": program_id,
                    "city": (city or ""),
                    "ranked": ranked_struct,
                }
                page3_path = _os.path.join(save_dir, f"page3_{program_id}.json")
                with open(page3_path, "w", encoding="utf-8") as f:
                    _json.dump(page3_payload, f, ensure_ascii=False)

                logger.info(
                    f"Itinerario salvato su file: page1={page1_path}, page3={page3_path}"
                )
                return {
                    "success": True,
                    "program_id": program_id,
                    "files_saved": {"page1": True, "page3": True},
                    "file_paths": {"page1": page1_path, "page3": page3_path},
                }
            except Exception as _e:
                logger.warning(f"Salvataggio file JSON (page1/page3) fallito: {_e}")
                return {"success": True, "program_id": program_id, "files_saved": {"page1": False, "page3": False}}
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            return {"success": False, "error": str(e)}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    async def update_program(self, request: Request):
        auth = request.cookies.get("auth")
        email = request.cookies.get("user_email")

        if auth != "1" or not email:
            return {"success": False, "error": "Non autenticato"}

        try:
            data = await request.json()
        except Exception:
            data = {}

        program_id = data.get("program_id")
        if not program_id:
            return {"success": False, "error": "program_id mancante"}

        city = data.get("city")
        locali = data.get("locali") or data.get("manualSelection") or []
        try:
            num_locali = int(data.get("num_locali") or len(locali))
        except Exception:
            num_locali = len(locali)

        conn = get_connection()
        if not conn:
            return {"success": False, "error": "Connessione DB non disponibile"}

        try:
            cursor = conn.cursor(dictionary=True)
            # Utente corrente
            cursor.execute("SELECT id FROM Initalya.users WHERE email = %s", (email,))
            user = cursor.fetchone()
            if not user:
                conn.close()
                return {"success": False, "error": "Utente non trovato"}

            user_id = user["id"]

            # Verifica propriet� del programma
            cursor.execute(
                "SELECT * FROM Initalya.programs WHERE id = %s AND user_id = %s",
                (program_id, user_id)
            )
            program = cursor.fetchone()
            if not program:
                conn.close()
                return {"success": False, "error": "Programma non trovato o non autorizzato"}

            # Rileva colonne disponibili su programs
            has_city = False
            has_city_id = False
            try:
                cursor.execute("SHOW COLUMNS FROM Initalya.programs LIKE 'city'")
                has_city = cursor.fetchone() is not None
                cursor.execute("SHOW COLUMNS FROM Initalya.programs LIKE 'city_id'")
                has_city_id = cursor.fetchone() is not None
            except Exception:
                pass

            # Aggiorna programmi: city/city_id e num_locali
            if has_city_id and city is not None:
                def _norm_city(s: str) -> str:
                    import re as _re
                    t = (s or "").strip()
                    if not t:
                        return ""
                    t = _re.sub(r",.*$", "", t)
                    t = _re.sub(r"\s+[A-Z]{2}$", "", t)
                    t = _re.sub(r"\b(italia|italy)\b", "", t, flags=_re.I)
                    t = _re.sub(r"\s+", " ", t).strip()
                    return t
                city_name = _norm_city(city) or "Non specificata"
                cursor.execute("SELECT id FROM Initalya.cities WHERE LOWER(name) = LOWER(%s)", (city_name,))
                c = cursor.fetchone()
                if not c:
                    cursor.execute("SELECT id FROM Initalya.cities WHERE name LIKE %s", (f"%{city_name}%",))
                    c = cursor.fetchone()
                if c:
                    city_id = c.get("id") if isinstance(c, dict) else c[0]
                else:
                    cursor.execute("INSERT INTO Initalya.cities (name) VALUES (%s)", (city_name,))
                    city_id = cursor.lastrowid
                cursor.execute(
                    "UPDATE Initalya.programs SET city_id = %s, num_locali = %s WHERE id = %s AND user_id = %s",
                    (city_id, num_locali, program_id, user_id)
                )
            elif has_city and city is not None:
                cursor.execute(
                    "UPDATE Initalya.programs SET city = %s, num_locali = %s WHERE id = %s AND user_id = %s",
                    (city or "", num_locali, program_id, user_id)
                )
            else:
                cursor.execute(
                    "UPDATE Initalya.programs SET num_locali = %s WHERE id = %s AND user_id = %s",
                    (num_locali, program_id, user_id)
                )

            # Aggiorna i locali: cancella esistenti e reinserisci
            cursor.execute("DELETE FROM Initalya.locals WHERE program_id = %s", (program_id,))

            # Rilevamento dinamico delle colonne in locals
            try:
                cursor.execute("SHOW COLUMNS FROM Initalya.locals")
                rows = cursor.fetchall() or []
                loc_cols = [ (r.get("Field") if isinstance(r, dict) else r[0]) for r in rows ]
            except Exception:
                loc_cols = []

            prog_candidates = ["program_id", "programma_id", "programId", "program", "id_programma"]
            prog_col = next((c for c in prog_candidates if c in loc_cols), "program_id")
            name_col = "name" if "name" in loc_cols else ("nome" if "nome" in loc_cols else "name")
            addr_col = "address" if "address" in loc_cols else ("indirizzo" if "indirizzo" in loc_cols else "address")
            type_col = "type_id" if "type_id" in loc_cols else ("type" if "type" in loc_cols else None)
            place_col = "place_id" if "place_id" in loc_cols else None

            import re as _re
            import hashlib as _hashlib

            def _extract_pid_from_url(u: str) -> str:
                try:
                    m = _re.search(r"place_id:([^&]+)", u or "")
                    return m.group(1) if m else ""
                except Exception:
                    return ""

            def _fallback_pid(loc: dict) -> str:
                base = f"{loc.get('name','').strip()}|{loc.get('address','').strip()}"
                h = _hashlib.md5(base.encode("utf-8")).hexdigest()[:16]
                return f"manual_{h}"

            for loc in locali:
                columns = [prog_col]
                values = [program_id]

                if name_col:
                    columns.append(name_col)
                    values.append((loc.get("name") or ""))
                if addr_col:
                    columns.append(addr_col)
                    values.append((loc.get("address") or ""))

                if type_col:
                    if type_col == "type_id":
                        type_str = (loc.get("type") or "").strip()
                        type_id = None
                        try:
                            cursor.execute("SELECT id FROM Initalya.types WHERE LOWER(typology) = LOWER(%s)", (type_str,))
                            rr = cursor.fetchone()
                            type_id = (rr.get("id") if isinstance(rr, dict) else (rr[0] if rr else None))
                        except Exception:
                            type_id = None
                        if not type_id:
                            try:
                                cursor.execute("SELECT id FROM Initalya.types WHERE LOWER(typology) = LOWER(%s)", ("ristoranti",))
                                rr2 = cursor.fetchone()
                                type_id = (rr2.get("id") if isinstance(rr2, dict) else (rr2[0] if rr2 else None)) or 1
                            except Exception:
                                type_id = 1
                        columns.append(type_col)
                        values.append(type_id)
                    else:
                        columns.append(type_col)
                        values.append((loc.get("type") or ""))

                if place_col:
                    pid = (loc.get("place_id") or _extract_pid_from_url(loc.get("url") or "") or "").strip()
                    if not pid:
                        pid = _fallback_pid(loc)
                    columns.append(place_col)
                    values.append(pid)

                placeholders = ", ".join(["%s"] * len(values))
                sql = f"INSERT INTO Initalya.locals ({', '.join(columns)}) VALUES ({placeholders})"
                cursor.execute(sql, tuple(values))

            conn.commit()
            # Salva due file JSON anche in aggiornamento: page1 (HTML) e page3 (ranked)
            try:
                import os as _os, json as _json
                # Usa BASE_DIR per garantire il percorso assoluto corretto dentro il package sitesense
                save_dir = _os.path.join(str(BASE_DIR), "assets", "saved_itineraries")
                _os.makedirs(save_dir, exist_ok=True)

                page1_html = data.get("page1_html") or ""
                page1_payload = {
                    "program_id": program_id,
                    "city": (city or ""),
                    "page1_html": page1_html,
                }
                page1_path = _os.path.join(save_dir, f"page1_{program_id}.json")
                with open(page1_path, "w", encoding="utf-8") as f:
                    _json.dump(page1_payload, f, ensure_ascii=False)

                ranked_struct = data.get("page3_ranked") or data.get("ranked") or {}
                page3_payload = {
                    "program_id": program_id,
                    "city": (city or ""),
                    "ranked": ranked_struct,
                }
                page3_path = _os.path.join(save_dir, f"page3_{program_id}.json")
                with open(page3_path, "w", encoding="utf-8") as f:
                    _json.dump(page3_payload, f, ensure_ascii=False)

                logger.info(
                    f"Programma aggiornato e salvato su file: page1={page1_path}, page3={page3_path}"
                )
                return {
                    "success": True,
                    "program_id": program_id,
                    "files_saved": {"page1": True, "page3": True},
                    "file_paths": {"page1": page1_path, "page3": page3_path},
                }
            except Exception:
                return {"success": True, "program_id": program_id, "files_saved": {"page1": False, "page3": False}}
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            return {"success": False, "error": str(e)}
        finally:
            try:
                conn.close()
            except Exception:
                pass


    





    async def delete_program(self, request: Request):
        auth = request.cookies.get("auth")
        email = request.cookies.get("user_email")

        if auth != "1" or not email:
            return {"success": False, "error": "Non autenticato"}

        try:
            payload = await request.json()
        except Exception:
            payload = {}

        program_id = payload.get("program_id")
        if not program_id:
            return {"success": False, "error": "program_id mancante"}

        conn = get_connection()
        if not conn:
            return {"success": False, "error": "Connessione DB non disponibile"}

        try:
            cursor = conn.cursor(dictionary=True)
            # Recupera l'utente corrente
            cursor.execute("SELECT id FROM Initalya.users WHERE email = %s", (email,))
            user = cursor.fetchone()
            if not user:
                conn.close()
                return {"success": False, "error": "Utente non trovato"}

            user_id = user["id"]

            # Verifica che il programma appartenga all'utente
            cursor.execute(
                "SELECT id FROM Initalya.programs WHERE id = %s AND user_id = %s",
                (program_id, user_id)
            )
            prog = cursor.fetchone()
            if not prog:
                conn.close()
                return {"success": False, "error": "Programma non trovato o non autorizzato"}

            # Esegue la cancellazione (ON DELETE CASCADE gestisce le relazioni)
            cursor.execute(
                "DELETE FROM Initalya.programs WHERE id = %s AND user_id = %s",
                (program_id, user_id)
            )
            conn.commit()
            conn.close()
            return {"success": True}
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
            return {"success": False, "error": str(e)}
    
    async def google_login(self, request: Request, next: str = "/"):
        # Gestione sicura: se le variabili OAuth non sono configurate, mostra messaggio
        try:
            client_id = settings.google_oauth_client_id
            _secret = settings.google_oauth_client_secret  # verifichiamo anche il secret
            redirect_uri = settings.google_oauth_redirect_uri
            
            # Supporto dinamico per localhost se la richiesta arriva da lì
            host = request.headers.get("host", "")
            if "localhost" in host and "127.0.0.1" in redirect_uri:
                redirect_uri = redirect_uri.replace("127.0.0.1", "localhost")
        except Exception as e:
            logger.warning(f"Google OAuth non configurato: {e}")
            return self.templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "error_message": "Login con Google non configurato. Imposta GOOGLE_OAUTH_CLIENT_ID e GOOGLE_OAUTH_CLIENT_SECRET."
                }
            )
        scope = "openid email profile"
        next_cookie = request.cookies.get("next") or next or "/"
        try:
            parsed = urllib.parse.urlparse(next_cookie)
            q = urllib.parse.parse_qs(parsed.query)
            q["restore"] = ["1"]
            q["retSel"] = ["1"]
            # Preserva il parametro autosalva=1 se presente
            if "autosalva" not in q:
                q["autosalva"] = ["1"]
            new_query = urllib.parse.urlencode({k: v[0] for k, v in q.items()})
            next_cookie = urllib.parse.urlunparse(parsed._replace(query=new_query))
        except Exception:
            pass
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
            "access_type": "offline",
            "prompt": "select_account",
        }
        if next_cookie:
            params["state"] = next_cookie
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
        resp = RedirectResponse(url=auth_url, status_code=303)
        try:
            resp.delete_cookie("next")
        except Exception:
            pass
        return resp

# Consenti avvio con uvicorn: l'istanza globale dell'app è definita in coda al file

    async def google_callback(self, request: Request):
        code = str(request.query_params.get("code") or "")
        state = str(request.query_params.get("state") or "/area_riservata")
        # Mantieni intatto l'URL di stato per tornare esattamente alla pagina richiesta
        # (inclusi i parametri come ?autosalva=1).
        logger.info(f"DEBUG Google callback: code={code[:10]}..., state={state}")
        try:
            s = urllib.parse.unquote(state)
            parsed = urllib.parse.urlparse(s)
            # Non alterare porta/host: evita riscritture forzate che possono
            # rompere il flusso su ambienti che usano porte diverse (es. 8001).
            state = urllib.parse.urlunparse(parsed)
            logger.info(f"DEBUG Google callback: parsed state={state}")
        except Exception as e:
            logger.warning(f"DEBUG Google callback: error parsing state={e}")
            pass
        if not code:
            return RedirectResponse(url="/login?next=/area_riservata", status_code=303)
        token_url = "https://oauth2.googleapis.com/token"
        try:
            cid = settings.google_oauth_client_id
            csec = settings.google_oauth_client_secret
            redir = settings.google_oauth_redirect_uri
            
            # Supporto dinamico per localhost anche nella callback
            host = request.headers.get("host", "")
            if "localhost" in host and "127.0.0.1" in redir:
                redir = redir.replace("127.0.0.1", "localhost")
        except Exception as e:
            logger.warning(f"Google OAuth non configurato in callback: {e}")
            return self.templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "error_message": "Login con Google non configurato. Imposta GOOGLE_OAUTH_CLIENT_ID e GOOGLE_OAUTH_CLIENT_SECRET."
                }
            )
        data = {
            "code": code,
            "client_id": cid,
            "client_secret": csec,
            "redirect_uri": redir,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            tr = await client.post(token_url, data=data)
            if tr.status_code != 200:
                return RedirectResponse(url="/login?next=/area_riservata", status_code=303)
            tokens = tr.json()
            access_token = tokens.get("access_token")
            user_email = "user"
            if access_token:
                ur = await client.get(
                    "https://openidconnect.googleapis.com/v1/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if ur.status_code == 200:
                    info = ur.json()
                    user_email = info.get("email") or user_email
                    google_id = info.get("sub")      # ID Google univoco
                    name = info.get("given_name")
                    surname = info.get("family_name")
                    profile_image = info.get("picture")
                    user = get_user_by_google_id(google_id)
                    logger.info(f"DEBUG Google callback: user found by google_id={google_id}: {user is not None}")
                    if not user:
                      # Controlla se esiste già un utente con la stessa email
                      existing_user = get_user_by_email(user_email)
                      if existing_user:
                        logger.info(f"DEBUG Google callback: found existing user with email={user_email}, updating google_id")
                        # Aggiorna l'utente esistente con il google_id
                        conn = get_connection()
                        if conn:
                          cursor = conn.cursor()
                          cursor.execute(
                            "UPDATE Initalya.users SET google_id = %s WHERE email = %s",
                            (google_id, user_email)
                          )
                          conn.commit()
                          conn.close()
                        user = get_user_by_google_id(google_id)
                      else:
                        logger.info(f"DEBUG Google callback: creating new user with google_id={google_id}, email={user_email}")
                        create_user(
                             google_id=google_id,
                             email=user_email,
                             name=name,
                             surname=surname,
                             profile_image=profile_image
                       )
                        logger.info(f"DEBUG Google callback: user created successfully")
                   
        target_url = state or "/area_riservata"# Sanifica l'URL di redirect rimuovendo parametri come restore e retSel
        
        logger.info(f"DEBUG Google callback: redirecting to target_url={target_url}")
        resp = RedirectResponse(url=target_url, status_code=303)
        resp.set_cookie(key="auth", value="1", httponly=True, path="/", samesite="lax")
        resp.set_cookie(key="user_email", value=user_email, path="/", samesite="lax")
        # Flag per mostrare "Benvenuto" solo subito dopo il login
        resp.set_cookie(key="just_logged_in", value="1", path="/", samesite="lax")
        return resp
    
    def get_app(self) -> FastAPI:
        """Restituisce l'istanza FastAPI"""
        return self.app

def get_user_by_google_id(google_id: str):
    conn = get_connection()
    if not conn:
        return None

    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM Initalya.users WHERE google_id = %s",
        (google_id,)
    )
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_email(email: str):
    conn = get_connection()
    if not conn:
        return None

    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM Initalya.users WHERE email = %s",
        (email,)
    )
    user = cursor.fetchone()
    conn.close()
    return user


def create_user(google_id, email, name, surname, profile_image, phone=None, bio=None, country=None, city=None):
    """Crea un utente inserendo anche phone, bio, country, city se le colonne esistono.

    La funzione rileva dinamicamente la presenza delle colonne nel DB e le
    include nell'INSERT solo se presenti, mantenendo compatibilità con schemi
    precedenti.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Colonne base sempre presenti
        columns = ["google_id", "email", "name", "surname", "profile_image"]
        values = [google_id, email, name, surname, profile_image]

        # Verifica dinamica delle nuove colonne
        optional_fields = [
            ("phone", phone),
            ("bio", bio),
            ("country", country),
            ("city", city),
        ]
        for col_name, col_value in optional_fields:
            try:
                cursor.execute("SHOW COLUMNS FROM Initalya.users LIKE %s", (col_name,))
                if cursor.fetchone() is not None:
                    columns.append(col_name)
                    values.append(col_value)
            except Exception:
                # Se SHOW COLUMNS fallisce, ignora ed evita di inserire la colonna
                pass

        placeholders = ", ".join(["%s"] * len(values))
        col_list = ", ".join(columns)
        sql = f"INSERT INTO Initalya.users ({col_list}) VALUES ({placeholders})"
        cursor.execute(sql, tuple(values))
        conn.commit()
    finally:
        conn.close()



async def login_super_admin_submit(request: Request):
    form = await request.form()
    email = form.get("email")
    password = form.get("password")

    conn = get_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB non disponibile")

    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM Initalya.superadmins WHERE email = %s",
        (email,)
    )
    superadmin = cursor.fetchone()
    conn.close()

    if not superadmin:
        return RedirectResponse("/login_super_admin?error=1", status_code=303)

    # ?? Qui puoi aggiungere hash password se vuoi
    if superadmin["password"] != password:
        return RedirectResponse("/login_super_admin?error=1", status_code=303)

    # LOGIN OK
    resp = RedirectResponse(url="/area_super_admin", status_code=303)
    resp.set_cookie(
        key="super_auth",
        value="1",
        httponly=True,
        samesite="lax",
        path="/"
    )
    resp.set_cookie(
        key="superadmin_email",
        value=email,
        samesite="lax",
        path="/"
    )
    return resp

# (definizione duplicata rimossa: area_super_admin con parametro self fuori dalla classe)


async def logout_super_admin():
    resp = RedirectResponse("/login_super_admin", status_code=303)
    resp.delete_cookie("super_auth")
    resp.delete_cookie("superadmin_email")
    return resp













# Crea l'istanza dell'applicazione
sitesense_app = SiteSenseApp()
app = sitesense_app.get_app()

# Configura la porta dall'ambiente
port = int(os.environ.get("PORT", 5000))

logger.info(f"Applicazione SiteSense avviata con successo sulla porta {port}")

@app.get("/@vite/client")
async def vite_client_stub():
    return PlainTextResponse("/* vite client stub */", media_type="text/javascript")

# Avvia il server solo se eseguito direttamente
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("main_oop:app", host="0.0.0.0", port=port, reload=True)