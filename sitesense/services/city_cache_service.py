import json
import re
from pathlib import Path
from typing import Dict, Any, List

BASE_DIR = Path(__file__).resolve().parents[1]
CACHE_DIR = BASE_DIR / "assets" / "cities_cache"


def _slugify_city(city: str) -> str:
    s = (city or "").strip().lower()
    # Remove country suffixes and province abbreviations
    s = re.sub(r",.*$", "", s)
    s = re.sub(r"\s+[A-Z]{2}$", "", s)
    # Replace spaces and non-word chars
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "unknown_city"


def ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def save_city_cache(city: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Save per-city cache JSON under assets/cities_cache, writing split files only.

    Scrive SOLO due file:
    - <slug>_selection.json: array dei locali della seconda pagina (La nostra selezione)
    - <slug>_suggests.json: array dei locali degli altri suggerimenti

    Ogni voce ha la forma (senza HTML):
    [
      {
        "place_id": str,
        "name": str,
        "formatted_address": str,
        "image": str,
        "category": str,
        "lat": float,
        "lng": float,
        "rating": float,
        "reviews_count": int
      },
      ...
    ]

    Il payload può contenere:
    - locals_selection / locals_suggests: liste già pronte da salvare; OPPURE
    - manualSelection / suggests: sorgenti da cui costruire le liste.
    """
    ensure_cache_dir()
    slug = _slugify_city(city)
    # Percorso del vecchio file combinato (non più usato): lo cancelliamo se presente
    old_combined_path = CACHE_DIR / f"{slug}.json"
    try:
        if old_combined_path.exists():
            old_combined_path.unlink()
    except Exception:
        # Ignora errori di cancellazione; l'obiettivo è non mantenere il file combinato
        pass

    # Build a flat list of places (locals)
    locals_list: List[Dict[str, Any]] = []

    def _clean_text(v: Any) -> str:
        s = str(v or "").strip()
        # Rimuove backtick e virgolette ai bordi, normalizza spazi
        s = s.strip("`\"'")
        s = re.sub(r"\s+", " ", s)
        return s

    def _to_float(v: Any):
        try:
            return float(v)
        except Exception:
            try:
                return float(str(v).replace(",", "."))
            except Exception:
                return 0.0

    def _to_int(v: Any):
        try:
            return int(v)
        except Exception:
            try:
                return int(float(v))
            except Exception:
                return 0

    def _push_place(place: Dict[str, Any], category_hint: str = ""):
        if not place:
            return
        item = {
            "place_id": _clean_text(place.get("place_id") or place.get("id") or ""),
            "name": _clean_text(place.get("name") or place.get("nome") or ""),
            "formatted_address": _clean_text(place.get("formatted_address") or place.get("indirizzo") or ""),
            "image": _clean_text(place.get("image") or place.get("photo") or place.get("foto_url") or ""),
            "category": _clean_text(place.get("category") or category_hint or ""),
            "lat": _to_float((place.get("lat") if place.get("lat") is not None else (place.get("location", {}) or {}).get("lat"))),
            "lng": _to_float((place.get("lng") if place.get("lng") is not None else (place.get("location", {}) or {}).get("lng"))),
            "rating": _to_float(place.get("rating") or place.get("valutazione")),
            "reviews_count": _to_int(place.get("reviews_count") or place.get("reviews") or place.get("user_ratings_total")),
        }
        locals_list.append(item)

    # Prefer 'locals' supplied by client
    given_locals = payload.get("locals")
    if isinstance(given_locals, list) and given_locals:
        # Normalize minimally to ensure keys exist
        for p in given_locals:
            _push_place(p)
    else:
        ranked = payload.get("ranked") or payload.get("page3_ranked") or {}
        for cat, obj in ranked.items():
            results = obj.get("results") if isinstance(obj, dict) else None
            if isinstance(results, list):
                for p in results:
                    _push_place(p, category_hint=cat)

        for p in (payload.get("manualSelection") or []):
            _push_place(p, category_hint="la_nostra_selezione")

        for p in (payload.get("suggests") or []):
            _push_place(p)

    # Non scriviamo il file combinato <slug>.json (rimosso)

    # Build and write split arrays: selection and suggests
    selection_list: List[Dict[str, Any]] = []
    suggests_list: List[Dict[str, Any]] = []

    given_selection = payload.get("locals_selection")
    if isinstance(given_selection, list) and given_selection:
        for p in given_selection:
            _push_place(p)
            selection_list.append(locals_list[-1])  # last pushed
    else:
        for p in (payload.get("manualSelection") or []):
            _push_place(p, category_hint="la_nostra_selezione")
            selection_list.append(locals_list[-1])

    given_suggests = payload.get("locals_suggests")
    if isinstance(given_suggests, list) and given_suggests:
        for p in given_suggests:
            _push_place(p)
            suggests_list.append(locals_list[-1])
    else:
        for p in (payload.get("suggests") or []):
            _push_place(p)
            suggests_list.append(locals_list[-1])

    sel_path = CACHE_DIR / f"{slug}_selection.json"
    sug_path = CACHE_DIR / f"{slug}_suggests.json"

    # Scrivi i file solo se le liste hanno contenuto; altrimenti rimuovi eventuali file vuoti
    # Fallback: se entrambe sono vuote ma abbiamo 'locals_list', usa quelli come 'suggests'
    if not selection_list and not suggests_list and locals_list:
        suggests_list = list(locals_list)

    if selection_list:
        sel_path.write_text(json.dumps(selection_list, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        try:
            if sel_path.exists():
                sel_path.unlink()
        except Exception:
            pass

    if suggests_list:
        sug_path.write_text(json.dumps(suggests_list, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        try:
            if sug_path.exists():
                sug_path.unlink()
        except Exception:
            pass

    # Salvaguardia: se qualche altro codice ha scritto il file combinato legacy,
    # rimuovilo comunque al termine.
    legacy_path = CACHE_DIR / f"{slug}.json"
    try:
        if legacy_path.exists():
            legacy_path.unlink()
    except Exception:
        pass

    return {"success": True, "selection_path": str(sel_path), "suggests_path": str(sug_path)}


def load_city_cache(city: str) -> Dict[str, Any]:
    """Load per-city cache combinando i file _selection e _suggests se presenti.

    - Legge <slug>_selection.json e <slug>_suggests.json, li unisce in 'locals'.
    - Se assenti, fallback a other_locals.json.
    """
    ensure_cache_dir()
    slug = _slugify_city(city)
    sel_path = CACHE_DIR / f"{slug}_selection.json"
    sug_path = CACHE_DIR / f"{slug}_suggests.json"
    locals_list: List[Dict[str, Any]] = []

    try:
        if sel_path.exists():
            sel = json.loads(sel_path.read_text(encoding="utf-8"))
            if isinstance(sel, list):
                locals_list.extend(sel)
        if sug_path.exists():
            sug = json.loads(sug_path.read_text(encoding="utf-8"))
            if isinstance(sug, list):
                locals_list.extend(sug)
    except Exception:
        locals_list = []

    if locals_list:
        return {"city": city, "locals": locals_list}

    # Fallback: generic local suggestions
    other_path = CACHE_DIR / "other_locals.json"
    if other_path.exists():
        try:
            data = json.loads(other_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return {"city": city, "locals": data}
            if isinstance(data, dict) and isinstance(data.get("locals"), list):
                return {"city": city, "locals": data.get("locals", [])}
        except Exception:
            pass

    return {"city": city, "locals": []}