import logging
import math
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
from .preferences_checker_service import PreferencesCheckerService

logger = logging.getLogger(__name__)

class FilteringRankingService:
    """
    Servizio per filtrare, ordinare e presentare attività (ristoranti, hotel, etc.)
    in base a un set di regole definite e alle preferenze dell'utente.
    """
    def __init__(self):
        logger.info("FilteringRankingService initialized.")
        self.preferences_checker_service = PreferencesCheckerService()
        # Importa le impostazioni per l'API key di Google Maps
        from ..config.settings import settings
        self.api_key = settings.google_maps_api_key
        self.base_url = "https://maps.googleapis.com/maps/api"

    def _is_maps_key_active(self) -> bool:
        try:
            key = str(self.api_key or "").strip()
            if not key:
                return False
            # Chiavi dummy o troppo corte non sono valide
            if key.upper() == "DUMMY_KEY":
                return False
            if len(key) <= 20:
                return False
            return True
        except Exception:
            return False

    def _extract_city_hint(self, search_queries: Dict[str, Any], user_query: str) -> str:
        """
        Estrae un hint di città dalla query utente o dalle search_queries.
        Heuristics semplici su preposizioni italiane ("a", "in") e fallback al testo finale.
        """
        candidates: List[str] = []

        # Prova dalle search_queries stringhe (es. "ristoranti tipici a Bari")
        for q in search_queries.values():
            if isinstance(q, str):
                m = re.search(r"\b(?:a|in)\s+([A-Za-zÀ-ÖØ-öø-ÿ\-'\s]+)$", q.strip())
                if m:
                    candidates.append(m.group(1).strip())

        # Prova anche dall'user_query
        if isinstance(user_query, str) and user_query.strip():
            m2 = re.search(r"\b(?:a|in)\s+([A-Za-zÀ-ÖØ-öø-ÿ\-'\s]+)$", user_query.strip())
            if m2:
                candidates.append(m2.group(1).strip())

        # Scegli la prima candidata non vuota; normalizza spazi/punteggiatura finale
        for c in candidates:
            c2 = re.sub(r"[\s,.;:]+$", "", c)
            if c2:
                return c2
        return (user_query or "").strip()

    def _load_city_cache_split(self, city_hint: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Carica i due file split (selection/suggests) se presenti, altrimenti other_locals.
        Ritorna un dict con chiavi: 'selection' e 'suggests'.
        """
        try:
            from .city_cache_service import _slugify_city, CACHE_DIR
        except Exception:
            _slugify_city = lambda s: re.sub(r"[^a-z0-9]+", "_", (s or "").strip().lower()).strip("_") or "unknown_city"
            CACHE_DIR = Path(__file__).resolve().parents[1] / "assets" / "cities_cache"

        slug = _slugify_city(city_hint or "")
        sel_path = CACHE_DIR / f"{slug}_selection.json"
        sug_path = CACHE_DIR / f"{slug}_suggests.json"
        selection: List[Dict[str, Any]] = []
        suggests: List[Dict[str, Any]] = []

        try:
            if sel_path.exists():
                selection = json.loads(sel_path.read_text(encoding="utf-8")) or []
            if sug_path.exists():
                suggests = json.loads(sug_path.read_text(encoding="utf-8")) or []
        except Exception:
            selection, suggests = [], []

        # Fallback other_locals.json
        if not selection and not suggests:
            other_path = CACHE_DIR / "other_locals.json"
            try:
                if other_path.exists():
                    data = json.loads(other_path.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        suggests = data
                    elif isinstance(data, dict) and isinstance(data.get("locals"), list):
                        suggests = data.get("locals", [])
            except Exception:
                pass

        return {"selection": selection, "suggests": suggests}

    def _build_activity_link(self, activity: Dict[str, Any]) -> str:
        """
        Costruisce un link utilizzabile per aprire la sede su Maps o sito web
        quando il dato non contiene un `place_id` (output locale da Gemini).

        Priorità:
        1) `website` se presente
        2) Google Maps con `place_id` se disponibile
        3) Ricerca su Google Maps usando nome + indirizzo
        4) Coordinate se disponibili
        """
        try:
            website = activity.get('website')
            if website:
                return website

            place_id = activity.get('place_id')
            # Usa place_id reale per aprire direttamente la scheda del luogo
            if place_id and not str(place_id).startswith('gemini-'):
                # Usa l'URL della scheda del luogo
                return f"https://www.google.com/maps/place/?q=place_id:{str(place_id)}"

            name = activity.get('name') or ''
            address = activity.get('formatted_address') or activity.get('vicinity') or ''

            # Preferisci la ricerca per nome+indirizzo rispetto alle coordinate
            geometry = activity.get('geometry', {})
            location = geometry.get('location', {})
            lat = location.get('lat')
            lng = location.get('lng')
            query = (name + ' ' + address).strip() or name or address
            if query:
                return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"

            # Solo se mancano nome/indirizzo, usa le coordinate come fallback
            if lat is not None and lng is not None:
                return f"https://www.google.com/maps/search/?api=1&query={quote_plus(str(lat))}%2C{quote_plus(str(lng))}"

            # Fallback finale: homepage di Google Maps
            return "https://www.google.com/maps"
        except Exception:
            return "https://www.google.com/maps"

    def _format_to_html(self, activities: List[Dict[str, Any]], warning: Optional[str]) -> str:
        """
        Genera l'output HTML per le attività selezionate, includendo nome, prezzo, rating, recensioni,
        descrizione, servizi, link a Google Maps e indirizzo (se disponibile).
        Le attività vengono mostrate come card disposte orizzontalmente.
        """
        if not activities and not warning:
            return "<p>Mi dispiace, non ho trovato attività pertinenti secondo i criteri forniti.</p>"

        html_parts = []

        html_parts.append("""
    <style>
      @media (max-width: 558px) {

   .activities-grid { grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    gap: 14px !important;
    justify-items: stretch !important;
    width: 100% !important;
         margin-right: -20px !important;
          margin-left: 0 !important;
          padding-left: 0 !important;
          padding-right: 0 !important;
  }

        .activity-card {
          min-height: auto !important;
          padding-left: 0px !important;
          padding-right: 0px !important;
          text-align: center;
          width: 100% !important;
        }

        .activity-card .activity-image {
          height: 120px !important;
          margin-bottom: 8px !important;
        }

        .activity-card h3 {
          font-size: 0.8rem !important;
          line-height: 1.2 !important;
          margin-bottom: 4px !important;
        }

        .activity-card p {
          font-size: 0.75rem !important;
        }

        .activity-card a {
          font-size: 0.7rem !important;
          justify-content: center;
        }

        .add-to-trip-btn {
          width: 28px !important;
          height: 28px !important;
          padding: 4px !important;
        }

        .load-more-btn {
          font-size: 0.8rem !important;
          padding: 8px 20px !important;
        }
      }
    </style>
    """)





        if warning:
            html_parts.append(f'''
            <div class="warning" style="background-color: #fffbe6; border: 1px solid #fde047; padding: 12px; border-radius: 8px; margin-bottom: 16px;">
                {warning}
            </div>
            ''')

        
        # Container griglia 4 colonne con spaziatura uniforme e larghezza card ridotta
        html_parts.append('<div class="activities-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 24px 16px; align-items: stretch; justify-content: start;">')

        for activity in activities:
            name = activity.get('name', 'Nome non disponibile')
            price = '€' * activity.get('price_level', 0) if activity.get('price_level') else ''
            rating = activity.get('rating', 'N/A')
            reviews = activity.get('user_ratings_total', 'N/A')
            description = activity.get('editorial_summary', {}).get('overview', 'Nessuna descrizione disponibile.')
            services = activity.get('servizi', [])
            maps_url = self._build_activity_link(activity)
            address = activity.get('formatted_address') or activity.get('vicinity') or 'Indirizzo non disponibile'
            # Ottieni l'URL dell'immagine e includilo nel log
            photo_url = self._resolve_photo_url(activity)
            try:
                logger.info(f"Attività: {name} | {address} | place_id={activity.get('place_id','')} | rating={rating} | image_url={photo_url or ''}")
            except Exception:
                pass

            # Tronca la descrizione se troppo lunga
            if len(description) > 100:
                description = description[:100] + '...'

            services_html = ''

            # Costruisci i link in modo resiliente: se manca place_id, non usare onclick
            # L'onclick apre il modal solo quando abbiamo un place_id valido
            place_id_for_link = activity.get('place_id')
            escaped_name_for_link = name.replace("'", "&#39;")
            if place_id_for_link:
                links_html = (
                    f'<div class="links" style="margin-top: 0px;">'
                    f' <a href="{maps_url}" target="_blank" class="selection-card-link" '
                    f'onclick="openActivityModal(\'{place_id_for_link}\', \'{escaped_name_for_link}\'); return false;" '
                    f'style="display: inline-flex; align-items: center; gap: 6px; text-decoration: none;font-size: 0.875rem; font-weight: 600; color: #0f3e34;">'
                    f'Visualizza la scheda<span class="material-icons" style="font-size: 16px; line-height: 1; color: #0f3e34;">arrow_forward</span></a></div>'
                )
            else:
                links_html = (
                    f'<div class="links" style="margin-top: 0px;">'
                    f' <a href="{maps_url}" target="_blank" class="selection-card-link" '
                    f'style="display: inline-flex; align-items: center; gap: 6px; text-decoration: none;font-size: 0.875rem; font-weight: 600; color: #0f3e34;">'
                    f'Visualizza la scheda<span class="material-icons" style="font-size: 16px; line-height: 1; color: #0f3e34;">arrow_forward</span></a></div>'
                )

            # Genera l'HTML per l'immagine in un contenitore relativo con overlay "+"
            if photo_url:
                image_core = f'<div class="activity-image" style="display:block; width: calc(100% + 20px); height: 200px; background-image: url({photo_url}); background-size: cover; background-position: center; border-top-left-radius: 12px; border-top-right-radius: 12px; margin: -10px -10px 12px -10px;"></div>'
            else:
                image_core = '<div class="activity-image" style="display:block; width: calc(100% + 20px); height: 200px; background: #eaeaea; border-top-left-radius: 12px; border-top-right-radius: 12px; margin: -10px -10px 12px -10px;"></div>'
            image_html = f'<div style="position: relative;">{image_core}<button type="button" class="add-to-trip-btn" title="Aggiungi" style="position: absolute; top: 10px; right: 10px; background: #ffffff; border-radius: 9999px; padding: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.08); border: none; cursor: pointer;"><span class="material-icons" style="color: #0f3e34; font-size: 16px; font-weight: 700;">add</span></button></div>'
            
            # Card completa con layout ottimizzato per disposizione orizzontale e funzionalità di espansione
            place_id = activity.get('place_id', '')
            escaped_name = name.replace("'", "&#39;")
            
            # Estrai coordinate
            geometry = activity.get('geometry', {})
            location = geometry.get('location', {})
            lat = location.get('lat', '')
            lng = location.get('lng', '')
            
            html_parts.append(f'''
            <div class="activity-card" 
                data-place-id="{place_id}"
                data-lat="{lat}" 
                data-lng="{lng}"
                style="
                border: 1px solid #e2e8f0; 
                border-radius: 12px; 
                padding: 10px; 
                background: white;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                transition: transform 0.2s, box-shadow 0.2s;
                min-height: 380px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                overflow: hidden;
                position: relative;
                cursor: pointer;
            " onmouseover="this.style.transform='translateY(-4px)'; this.style.boxShadow='0 4px 16px rgba(0,0,0,0.15)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.1)'" >
                {image_html}
                <div style="padding: 14px 12px 12px 12px; display: flex; flex-direction: column; height: auto;">
<h3 style="font-size: 0.95rem; font-weight: 700; margin-bottom: 2px; line-height: 1.25; color: #0f172a;">
                        {name} 
                        {f'<span style="color: #64748b; font-size: 0.875rem;">{price}</span>' if price else ''}
                    </h3>
                    <p class="rating" style="margin-bottom: 0px; font-size: 0.875rem; color: #334155;"><b>⭐ {rating}</b> · {reviews} recensioni</p>
                </div>
                <div style="padding-top: 0px;">{links_html}</div>
            </div>
            ''')

        html_parts.append('</div>')  # Chiude il container delle card

        html_parts.append("""
        <div style="width:100%; display:flex; justify-content:center; margin-top:32px;">
        <button class="load-more-btn" style="
        background:#e6fdf4;
        border:2px solid #0f766e;
        color:#0f766e;
        padding:10px 24px;
        font-size:0.95rem;
        font-weight:700;
        border-radius:9999px;
        cursor:pointer;">
        Carica altri suggerimenti
        </button>
        </div>
        """)


        return "\n".join(html_parts)

    def _get_photo_url(self, photos: Optional[List[Dict]]) -> Optional[str]:
        """Costruisce l'URL della foto se disponibile"""
        if not photos:
            return None
        
        photo_reference = photos[0].get("photo_reference")
        if not photo_reference:
            return None
        
        return (f"{self.base_url}/place/photo"
                f"?maxwidth=400&photoreference={photo_reference}&key={self.api_key}")

    def _resolve_photo_url(self, item: Dict[str, Any]) -> Optional[str]:
        """Risolvi l'URL dell'immagine da diversi possibili campi (photo_url, foto_url, image, photos)."""
        try:
            if not item:
                return None
            # Campi diretti
            for key in ("photo_url", "foto_url", "image", "image_url"):
                val = item.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip().replace("http://", "https://")
            # Dal primo elemento di photos
            photos = item.get("photos")
            if isinstance(photos, list) and photos:
                first = photos[0] or {}
                for key in ("url", "photo_url", "image"):
                    val = first.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip().replace("http://", "https://")
                ref = first.get("photo_reference")
                if isinstance(ref, str) and ref.strip():
                    return (f"{self.base_url}/place/photo"
                            f"?maxwidth=400&photoreference={ref}&key={self.api_key}")
            return None
        except Exception:
            return None

    async def filter_rank_and_present(self, search_queries: Dict[str, Any], maps_data: Dict[str, Any], user_query: str) -> Dict[str, Any]:
        """
        Metodo principale che orchestra il processo di filtering, ranking e presentazione.
        """
        # Se la chiave Maps NON è attiva, carica dai JSON salvati e presenta i risultati.
        if not self._is_maps_key_active():
            city_hint = self._extract_city_hint(search_queries, user_query)
            cache = self._load_city_cache_split(city_hint)
            selection = cache.get("selection", [])
            suggests = cache.get("suggests", [])

            ranked_results: Dict[str, Any] = {}

            # Sezione "La nostra selezione" (usa il renderer generico delle card)
            if selection:
                sel_html = self._format_selection_to_html(selection)
                if sel_html:
                    ranked_results["la_nostra_selezione"] = {
                        "results": sel_html,
                        "iframe_url": None,
                    }

            # Raggruppa i suggests per categoria se disponibile
            groups: Dict[str, List[Dict[str, Any]]] = {}
            for item in suggests:
                cat = str(item.get("category") or "altri_suggerimenti").strip().lower()
                groups.setdefault(cat, []).append(item)

            for cat, items in groups.items():
                ranked_results[cat] = {
                    "results": self._format_to_html(items, None),
                    "iframe_url": None,
                }

            return ranked_results

        preferences = await self.preferences_checker_service.check_preferences(user_query)
        logger.info(f"Preferenze dell'utente: {preferences}")
        
        # ogni ciclo contiene le attività per una determinata categoria
        ranked_results = {}
        all_activities = {}  # Raccoglie tutte le attività per categoria per la selezione
        
        for category, query in search_queries.items():
            cat_lower = str(category).lower()
            if ('prodotti' in cat_lower) or ('eventi' in cat_lower):
                logger.info(f"Salto categoria '{category}' (prodotti/eventi non caricati lato server)")
                continue
            data = maps_data.get(category, {})
            activities = data.get("results", [])
            if activities:
                # Se la query è una lista, si tratta di luoghi specifici e non vengono filtrati
                if isinstance(query, list):
                    logger.info(f"----------------------Query per '{category}' è una lista. Salto i filtri e il ranking.")
                    final_selection = activities
                else:
                    logger.info(f"----------------------Query per '{category}' non è una lista, quindi sono delle ricerche generiche.")
                    final_selection = self.orchestrate_preferences_filtering(activities, preferences)

                # Dopo aver filtrato, ordino le attività
                ranked_selection = self._rank_activities(final_selection)
                all_activities[category] = ranked_selection  # Salva per la selezione

                ranked_html = self._format_to_html(ranked_selection, None)
                ranked_results[category] = {
                    "results": ranked_html,
                    "iframe_url": data.get("iframe_url")
                }
            else:
                ranked_results[category] = data
        
        # Crea la sezione "La nostra selezione" e la inserisce all'inizio
        our_selection = self._create_our_selection(all_activities)
        if our_selection:
            # Crea un nuovo dizionario con "La nostra selezione" come primo elemento
            new_ranked_results = {
                "la_nostra_selezione": {
                    "results": our_selection,
                    "iframe_url": None
                }
            }
            # Aggiungi tutti gli altri risultati dopo
            new_ranked_results.update(ranked_results)
            ranked_results = new_ranked_results
        
        return ranked_results




        

    def orchestrate_preferences_filtering(self, activities: List[Dict[str, Any]], preferences: str) -> List[Dict[str, Any]]:
        """
        Orchestra il processo di filtraggio dei risultati in base alle preferenze dell'utente.

        Args:
            activities: La lista di attività da filtrare.
            preferences: Una stringa JSON contenente le preferenze dell'utente.

        Returns:
            La lista di attività filtrate.
        """
        # Pulisce la stringa JSON da eventuali marcatori di codice
        if preferences.strip().startswith('```json'):
            preferences = preferences.strip()[7:-3].strip()

        try:
            preferences_data = json.loads(preferences)
            if preferences_data.get("preferences_found") is False:
                logger.info("Nessuna preferenza utente specificata, restituisco i risultati non filtrati.")
                return activities
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Impossibile decodificare le preferenze JSON: {preferences}. Restituisco i risultati non filtrati.")
            return activities

        logger.info(f"Applicazione dei filtri basati sulle preferenze: {preferences_data}")

        filtered_activities = activities

        # 1. Filtro per budget
        budget_preference = preferences_data.get('budget')
        if budget_preference:
            filtered_activities = self._filter_by_budget(filtered_activities, budget_preference)

        # 2. Filtro per servizi
        services_preference = preferences_data.get('servizi')
        if services_preference:
            filtered_activities = self._filter_by_services(filtered_activities, services_preference)

        # 3. Filtro per rating minore 3.8 (salvo unica opzione) 
        filtered_activities = self._filter_by_rating(filtered_activities)

        return filtered_activities

    def _filter_by_budget(self, activities: List[Dict[str, Any]], budget: str) -> List[Dict[str, Any]]:
        """
        Filtra le attività in base al budget specificato.
        """
        logger.info(f"Filtraggio per budget: {budget}")
        price_map = {'economico': 1, 'medio': 2, 'lusso': 3}
        target_price_level = price_map.get(budget.lower())
        if not target_price_level:
            logger.warning(f"Budget non valido: {budget}. Nessun filtro applicato.")
            return activities
        
        filtered_list = []
        for act in activities:
            price_level = act.get('price_level')
            # price level non è sempre definito
            logger.info(f"price_level è presente ------------> {price_level}")
            if price_level and price_level <= target_price_level:
                logger.info(f"L'attività '{act.get('name')}' con price_level {price_level} corrisponde al budget.")
                filtered_list.append(act)
            else:
                logger.info(f"L'attività '{act.get('name')}' con price_level {price_level} non corrisponde al budget.")
        
        logger.info(f"Trovate {len(filtered_list)} attività che corrispondono al budget.")
        return filtered_list


    

    def _filter_by_services(self, activities: List[Dict[str, Any]], services: List[str]) -> List[Dict[str, Any]]:
        """
        Filtra le attività in base ai servizi richiesti.
        """
        logger.info(f"Filtraggio per servizi: {services}")
        
        filtered_list = []
        for act in activities:
            # logger.info(f"attività: {json.dumps(act, indent=2, ensure_ascii=False)}")
            # Controlla se almeno uno dei servizi richiesti è presente nell'attività
            if any(service.lower() in act.get('name', '').lower() or \
                   service.lower() in act.get('editorial_summary', {}).get('overview', '').lower() or \
                   any(service.lower() in t.lower() for t in act.get('types', [])) for service in services):
                logger.info(f"L'attività '{act.get('name')}' corrisponde ai servizi richiesti.")
                filtered_list.append(act)
            else:
                logger.info(f"L'attività '{act.get('name')}' non corrisponde ai servizi richiesti.")

        logger.info(f"Trovate {len(filtered_list)} attività che corrispondono ai servizi.")
        return filtered_list
        
    def _filter_by_rating(self, activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filtra le attività in base al rating.
        """
        logger.info(f"Filtraggio per rating.")
        
        filtered_list = []
        for act in activities:
            logger.info(f"attività: {json.dumps(act, indent=2, ensure_ascii=False)}")
            # Controlla se almeno uno dei servizi richiesti è presente nell'attività
            rating_raw = act.get('rating')
            try:
                rating_val = float(rating_raw)
            except (TypeError, ValueError):
                rating_val = 0.0
            if rating_val >= 3.8:
                logger.info(f"L'attività '{act.get('name')}' con rating {rating_val} corrisponde al filtro.")
                filtered_list.append(act)
            else:
                logger.info(f"L'attività '{act.get('name')}' con rating {rating_val} non corrisponde al filtro.")
        return filtered_list
        
    def _rank_activities(self, activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ordina le attività.
        Ordinamento Multi-Criterio
        1. Punteggio qualita (rating x log10(recensioni + 1))
        2. Rapporto qualita-prezzo
        3. Numero recensioni
        4. Distanza
        5. Seleziona 24 attività scegliendo di mostarne inizialmente fino a 8, cliccando il tasto "Carica altri suggerimenti" si mostrano altre 8 attività
        """
        # Calcolo del punteggio di qualità per ogni attività
        for activity in activities:
            rating_raw = activity.get('rating')
            reviews_raw = activity.get('user_ratings_total')

            # Normalizza rating a float; valori mancanti o non numerici diventano 0.0
            try:
                rating = float(rating_raw)
            except (TypeError, ValueError):
                rating = 0.0

            # Normalizza reviews a int; valori None/str non numerici diventano 0
            try:
                reviews = int(reviews_raw)
            except (TypeError, ValueError):
                reviews = 0
            if reviews < 0:
                reviews = 0
            # Usiamo log10(reviews + 1) per evitare log(0) e per dare peso alle recensioni
            quality_score = rating * math.log10(reviews + 1)
            activity['quality_score'] = quality_score
            logger.info(f"Attività: {activity.get('name')}, Rating: {rating}, Recensioni: {reviews}, Punteggio Qualità: {quality_score}")

        # Ordinamento delle attività in base al punteggio di qualità (decrescente)
        sorted_activities = sorted(activities, key=lambda x: x.get('quality_score', 0), reverse=True)

        logger.info("Attività ordinate per punteggio di qualità:")
        for activity in sorted_activities:
            logger.info(f"  - {activity.get('name')}: {activity.get('quality_score')}")

        # 5. Seleziona le migliori attività
        num_activities = len(sorted_activities)
        if num_activities <= 3:
            top_activities = sorted_activities
            logger.info(f"Selezionate tutte le {num_activities} attività disponibili.")
        else:
            # Seleziona un numero di attività compreso tra 3 e 5
            # In questo caso, ne selezioniamo 5 se ce ne sono abbastanza
            num_to_select = min(5, num_activities)
            top_activities = sorted_activities[:num_to_select]
            logger.info(f"Selezionate le prime {num_to_select} attività su {num_activities}.")

        return top_activities

    def _format_selection_to_html(self, items: List[Dict[str, Any]]) -> Optional[str]:
        """
        Genera HTML per "La nostra selezione" partendo da una lista di attività già selezionate.
        Usa le stesse card con classe `selection-card` dentro il contenitore `#page-selection`.
        """
        if not items:
            return None

        html_parts = []
        html_parts.append('''
           <style>
      @media (max-width: 558px) {
        #page-selection {
         
          
          transform: translateX(2px);
          
        }

        .selection-grid {
          grid-template-columns: repeat(2, 1fr) !important;
          gap: 12px 10px !important;
          
       
        }

        .selection-card {
          min-height: auto !important;
         
       
        }

        .selection-card .activity-image {
          height: 120px !important;
          margin-bottom: 8px !important;
        }

        .selection-card h3 {
          font-size: 0.8rem !important;
          line-height: 1.2 !important;
        }

        .selection-card p {
          font-size: 0.75rem !important;
          margin-bottom: 6px !important;
        }

        .selection-card a {
          font-size: 0.7rem !important;
        }

        .selection-card img {
          width: 18px !important;
          height: 18px !important;
        }

        .selection-card .minus-btn {
          width: 22px !important;
          height: 22px !important;
          font-size: 14px !important;
          top: 8px !important;
          right: 8px !important;
        }
      }
    </style>
        <div id="page-selection" class="our-selection" style="margin: -12px auto 0 auto; padding: 0px 0px 28px 32px; background-color: #0f3e34; border-radius: 1px; color: #ffffff; max-width: 2000px; width: 100%;">
            <h2 style="margin: 0 0 8px 0; font-size: 1.5rem; font-weight: 800; text-align: left; color:#b7f056;">La nostra selezione</h2>
            <p style="margin: 0 0 16px 0; font-size: 0.8rem; text-align: left; color: #c7d2d9;">Esperienze consigliate dalla redazione basate sulla qualità.</p>
          <div class="selection-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 24px 16px; align-items: stretch;">
        ''')

        for item in items:
            name = item.get('name', 'Nome non disponibile')
            price = '€' * item.get('price_level', 0) if item.get('price_level') else ''
            rating = item.get('rating', 'N/A')
            reviews = item.get('reviews_count') or item.get('user_ratings_total', 'N/A')
            maps_url = self._build_activity_link(item)
            address = item.get('formatted_address') or item.get('vicinity') or 'Indirizzo non disponibile'
            photo_url = self._resolve_photo_url(item)

            category = str(item.get('display_category') or item.get('category') or '').lower()
            category_display = {
                'hotel': {'svg': 'hotel.svg', 'name': 'Hotel', 'color': ''},
                'strutture ricettive': {'svg': 'hotel.svg', 'name': 'Hotel', 'color': ''},
                'ristoranti': {'svg': 'ristorante.svg', 'name': 'Ristoranti', 'color': ''},
                'dolci_tipici': {'svg': 'dolci.svg', 'name': 'Dolci Tipici', 'color': ''},
                'cucina_tipica': {'svg': 'ristorante.svg', 'name': 'Cucina Tipica', 'color': ''},
                'vini': {'svg': 'vini.svg', 'name': 'Vini', 'color': ''}
            }
            if category in category_display:
                svg_icon = category_display[category]['svg']
                display_name = category_display[category]['name']
                cat_color = category_display[category]['color']
            else:
                svg_icon = 'ristorante.svg'
                display_name = category.replace('_', ' ').title() or 'Selezione'
                cat_color = ''

            image_html = ''
            if photo_url:
                image_html = f'''<div class="activity-image" style="display:block; width: calc(100% + 20px); height: 200px; background-image: url({photo_url}); background-size: cover; background-position: center; border-top-left-radius: 12px; border-top-right-radius: 12px; margin: -10px -10px 12px -10px;"></div>'''

            geometry = item.get('geometry', {})
            location = geometry.get('location', {})
            reviews = item.get('reviews_count') or item.get('user_ratings_total', 'N/A')
            lat = item.get('lat', '')
            lng = item.get('lng', '')
            safe_address = (address or '').replace('"', '&quot;')
            safe_place_id = item.get('place_id', '')

            html_parts.append(f'''
           <div class="activity-card selection-card" 
                data-place-id="{safe_place_id}"
                data-address="{safe_address}"
                data-category="{category}"
                data-rating="{rating}"
                data-reviews="{reviews}"
                data-lat="{lat}" 
                data-lng="{lng}"
                style="
    border: 1px solid #e2e8f0; 
    border-radius: 12px; 
    padding: 10px; 
    background: white;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    transition: transform 0.2s, box-shadow 0.2s;
    min-height: 380px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow: hidden;
    position: relative;
    cursor: pointer;
                " onmouseenter=\"this.style.transform='translateY(-4px)'; this.style.boxShadow='0 4px 16px rgba(0,0,0,0.15)'; try{{this.querySelector('.minus-btn').style.opacity='1';}}catch(e){{}}\" 
  onmouseleave=\"this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.1)'; try{{this.querySelector('.minus-btn').style.opacity='0';}}catch(e){{}}\">
                {image_html}
                <button type="button" class="minus-btn" title="Rimuovi"
                    data-place-id="{item.get('place_id','')}"
                    style="position: absolute; top: 48px; right: 10px; width: 28px; height: 28px; border-radius: 9999px; border: 2px solid #0f3e34; color:#0f3e34; background: #ffffff; display: inline-flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 700; cursor: pointer; opacity: 0; transition: opacity 0.2s; z-index: 2;"
                    onmouseover="this.style.background='#b7f056'"
                    onmouseout="this.style.background='#ffffff'"
                    >-</button>
                <span aria-hidden="true" style="position: absolute; top: 20px; right: 10px; width: 20px; height: 20px; border-radius: 9999px; background: #facc15; color: #22c55e; display: inline-flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 800; box-shadow: 0 0 0 2px #ffffff; z-index: 10000; pointer-events: none;">✓</span>
               <div style="padding: 14px 12px 12px 12px; display: flex; flex-direction: column; height: auto;">
                    <div style="display: inline-flex; align-items: center; gap: 12px; font-size: 0.95rem; margin: 12px 0 8px; color: #374151; text-transform: uppercase; font-weight: 700; height: 36px;">
                        <span style="width: 32px; height: 32px; border-radius: 9999px; display: inline-flex; align-items: center; justify-content: center; background: {cat_color};">
                            <img src="/assets/{svg_icon}" alt="{display_name}" style="width: 24px; height: 24px;" />
                        </span>
                        <span style="font-weight: 700; letter-spacing: 0.02em;">{display_name.upper()}</span>
                    </div>
                    <h3 style="font-size: 0.95rem; font-weight: 700; margin-bottom: 6px; line-height: 1.3; color: #0f172a;">
                        {name} <span aria-hidden="true" style="color: #22c55e; font-weight: 800; font-size: 18px; margin-left: 8px;"></span>
                        {f'<span style="color: #64748b; font-size: 0.875rem; margin-left: 4px;">{price}</span>' if price else ''}
                    </h3>
                    <p style="margin-bottom: 8px; font-size: 0.875rem; color: #334155;"><b>⭐ {rating}</b> · {reviews} recensioni</p>
                    <div style="margin-top: 4px;"></div>
                    <div style="padding-top: 2px;">
                        <a href="{maps_url}" target="_blank" class="selection-card-link" onclick="openActivityModal('{item.get('place_id','')}', '{name.replace("'", "&#39;")}'); return false;" style="
                            display: inline-flex; align-items: center; gap: 6px; text-decoration: none;
                            font-size: 0.875rem; font-weight: 600; color: #0f3e34;">
                            Visualizza la scheda
                            <span class="material-icons" style="font-size: 16px; line-height: 1; color: #0f3e34;">arrow_forward</span>
                        </a>
                    </div>
                </div>
            </div>
            ''')

        html_parts.append('</div></div>')
        return "\n".join(html_parts)

    def _create_our_selection(self, all_activities: Dict[str, List[Dict[str, Any]]]) -> Optional[str]:
        """
        Crea la sezione "La nostra selezione" selezionando automaticamente
        la migliore attività solo per le categorie specifiche: Hotel, Vini, Dolci, Cucina tipica.
        """
        selected_items = []
        
        # Categorie specifiche da includere nella selezione (con limiti per arrivare a 8 card)
        target_categories = {
            'hotel': ['hotel', 'alloggi', 'accommodation'],
            'vini': ['vini', 'wine', 'enoteca', 'cantina'],
            'dolci_tipici': ['dolci', 'pasticceria', 'gelateria', 'dessert', 'bakery'],
            'cucina_tipica': ['cucina', 'ristoranti', 'restaurant', 'food', 'dining', 'trattoria', 'osteria', 'pizzeria', 'mangiare', 'gastronomia', 'bistrot', 'pranzo', 'cena']
        }

        # Seleziona più attività per ciascuna categoria target fino a raggiungere 8 card complessive
        for target_key, keywords in target_categories.items():
            found_activity = None
            
            # Cerca nelle categorie disponibili
            for category, activities in all_activities.items():
                if activities and any(keyword in category.lower() for keyword in keywords):
                    # Prendi la prima attività (già ordinata per qualità)
                    found_activity = activities[0]
                    # Aggiungi informazioni sulla categoria per il display
                    found_activity['display_category'] = target_key
                    selected_items.append(found_activity)
                    logger.info(f"Selezionata attività '{found_activity.get('name')}' per la categoria target '{target_key}' dalla categoria '{category}'")
                    break
            
            if not found_activity:
                logger.info(f"Nessuna attività trovata per la categoria target '{target_key}'")
        
        # Se non ci sono attività selezionate, restituisci None
        if not selected_items:
            logger.info("Nessuna attività disponibile per 'La nostra selezione' nelle categorie specificate")
            return None
        
        if not selected_items:
            return None
        
        # Genera l'HTML per la selezione
        html_parts = []
        html_parts.append('''
           <style>
      @media (max-width: 558px) {
        #page-selection {
         
          
          transform: translateX(2px);
          
        }

        .selection-grid {
          grid-template-columns: repeat(2, 1fr) !important;
          gap: 12px 10px !important;
          
       
        }

        .selection-card {
          min-height: auto !important;
         
       
        }

        .selection-card .activity-image {
          height: 120px !important;
          margin-bottom: 8px !important;
        }

        .selection-card h3 {
          font-size: 0.8rem !important;
          line-height: 1.2 !important;
        }

        .selection-card p {
          font-size: 0.75rem !important;
          margin-bottom: 6px !important;
        }

        .selection-card a {
          font-size: 0.7rem !important;
        }

        .selection-card img {
          width: 18px !important;
          height: 18px !important;
        }

        .selection-card .minus-btn {
          width: 22px !important;
          height: 22px !important;
          font-size: 14px !important;
          top: 8px !important;
          right: 8px !important;
        }
      }
    </style>
        <div id="page-selection" class="our-selection" style="margin: -12px auto 0 auto; padding: 0px 0px 28px 32px; background-color: #0f3e34; border-radius: 1px; color: #ffffff; max-width: 2000px; width: 100%;">
            <h2 style="margin: 0 0 8px 0; font-size: 1.5rem; font-weight: 800; text-align: left; color:#b7f056;">La nostra selezione</h2>
            <p style="margin: 0 0 16px 0; font-size: 0.8rem; text-align: left; color: #c7d2d9;">Esperienze consigliate dalla redazione basate sulla qualità.</p>
          <div class="selection-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 24px 16px; align-items: stretch;">
        ''')

        for item in selected_items:
            name = item.get('name', 'Nome non disponibile')
            price = '€' * item.get('price_level', 0) if item.get('price_level') else ''
            rating = item.get('rating', 'N/A')
            reviews = item.get('user_ratings_total', 'N/A')
            description = item.get('editorial_summary', {}).get('overview', 'Esperienza unica e indimenticabile.')
            maps_url = self._build_activity_link(item)
            address = item.get('formatted_address') or item.get('vicinity') or 'Indirizzo non disponibile'
            # Ottieni l'URL dell'immagine e includila nel log
            photo_url = self._resolve_photo_url(item)
            try:
                logger.info(f"Selezione: {name} | {address} | place_id={item.get('place_id','')} | rating={rating} | image_url={photo_url or ''}")
            except Exception:
                pass
            
            # Tronca la descrizione
            if len(description) > 80:
                description = description[:80] + '...'
            
            # Determina il tipo di attività basato sulla categoria
            category = item.get('display_category', '').lower()
            
            category_display = {
                'hotel': {'svg': 'hotel.svg', 'name': 'Hotel', 'color': ''},
                'strutture ricettive': {'svg': 'hotel.svg', 'name': 'Hotel', 'color': ''},
                'ristoranti': {'svg': 'ristorante.svg', 'name': 'Ristoranti', 'color': ''},
                'dolci_tipici': {'svg': 'dolci.svg', 'name': 'Dolci Tipici', 'color': ''},
                'cucina_tipica': {'svg': 'ristorante.svg', 'name': 'Cucina Tipica', 'color': ''},
                'vini': {'svg': 'vini.svg', 'name': 'Vini', 'color': ''}
            }
            
            if category in category_display:
                svg_icon = category_display[category]['svg']
                display_name = category_display[category]['name']
                cat_color = category_display[category]['color']
            else:
                svg_icon = 'ristorante.svg'
                display_name = category.replace('_', ' ').title()
                cat_color = ''
            
            # Genera l'HTML per l'immagine se disponibile
           
            image_html = ''
            if photo_url:
                image_html = f'''<div class="activity-image" style="display:block; width: calc(100% + 20px); height: 200px; background-image: url({photo_url}); background-size: cover; background-position: center; border-top-left-radius: 12px; border-top-right-radius: 12px; margin: -10px -10px 12px -10px;"></div>'''
            
            # Escape del nome per JavaScript
            escaped_name = name.replace("'", "\\'")
            
            # Estrai coordinate
            geometry = item.get('geometry', {})
            location = geometry.get('location', {})
            lat = location.get('lat', '')
            lng = location.get('lng', '')

            # Attributi sicuri per il frontend
            safe_address = (address or '').replace('"', '&quot;')
            safe_place_id = item.get('place_id', '')

            html_parts.append(f'''
           <div class="activity-card selection-card" 
                data-place-id="{safe_place_id}"
                data-address="{safe_address}"
                data-category="{category}"
                data-rating="{rating}"
                data-reviews="{reviews}"
                data-lat="{lat}" 
                data-lng="{lng}"
               style="
    border: 1px solid #e2e8f0; 
    border-radius: 12px; 
    padding: 10px; 
    background: white;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    transition: transform 0.2s, box-shadow 0.2s;
    min-height: 380px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow: hidden;
    position: relative;
    cursor: pointer;
                " onmouseenter=\"this.style.transform='translateY(-4px)'; this.style.boxShadow='0 4px 16px rgba(0,0,0,0.15)'; try{{this.querySelector('.minus-btn').style.opacity='1';}}catch(e){{}}\" 
  onmouseleave=\"this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.1)'; try{{this.querySelector('.minus-btn').style.opacity='0';}}catch(e){{}}\">
                {image_html}
                <button type="button" class="minus-btn" title="Rimuovi"
                    data-place-id="{item.get('place_id','')}"
                    style="position: absolute; top: 48px; right: 10px; width: 28px; height: 28px; border-radius: 9999px; border: 2px solid #0f3e34; color:#0f3e34; background: #ffffff; display: inline-flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 700; cursor: pointer; opacity: 0; transition: opacity 0.2s; z-index: 2;"
                    onmouseover="this.style.background='#b7f056'"
                    onmouseout="this.style.background='#ffffff'"
                    >-</button>
                <span aria-hidden="true" style="position: absolute; top: 20px; right: 10px; width: 20px; height: 20px; border-radius: 9999px; background: #facc15; color: #22c55e; display: inline-flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 800; box-shadow: 0 0 0 2px #ffffff; z-index: 10000; pointer-events: none;">✓</span>
               <div style="padding: 14px 12px 12px 12px; display: flex; flex-direction: column; height: auto;">
                    <div style="display: inline-flex; align-items: center; gap: 12px; font-size: 0.95rem; margin: 12px 0 8px; color: #374151; text-transform: uppercase; font-weight: 700; height: 36px;">
                        <span style="width: 32px; height: 32px; border-radius: 9999px; display: inline-flex; align-items: center; justify-content: center; background: {cat_color};">
                            <img src="/assets/{svg_icon}" alt="{display_name}" style="width: 24px; height: 24px;" />
                        </span>
                        <span style="font-weight: 700; letter-spacing: 0.02em;">{display_name.upper()}</span>
                    </div>
                    <h3 style="font-size: 0.95rem; font-weight: 700; margin-bottom: 6px; line-height: 1.3; color: #0f172a;">
                        {name} <span aria-hidden="true" style="color: #22c55e; font-weight: 800; font-size: 18px; margin-left: 8px;"></span>
                        {f'<span style="color: #64748b; font-size: 0.875rem; margin-left: 4px;">{price}</span>' if price else ''}
                    </h3>
                    <p style="margin-bottom: 8px; font-size: 0.875rem; color: #334155;"><b>⭐ {rating}</b> · {reviews} recensioni</p>
                    <div style="margin-top: 4px;"></div>
                    <div style="padding-top: 2px;">
                        <a href="{maps_url}" target="_blank" class="selection-card-link" onclick="openActivityModal('{item.get('place_id','')}', '{name.replace("'", "&#39;")}'); return false;" style="
                            display: inline-flex; align-items: center; gap: 6px; text-decoration: none;
                            font-size: 0.875rem; font-weight: 600; color: #0f3e34;">
                            Visualizza la scheda
                            <span class="material-icons" style="font-size: 16px; line-height: 1; color: #0f3e34;">arrow_forward</span>
                        </a>
                    </div>
                </div>
            </div>
            ''')

        html_parts.append('</div></div>')
        return "\n".join(html_parts)
    

    

    
