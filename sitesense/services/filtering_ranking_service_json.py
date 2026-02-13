import logging
import math
import json
import os
from typing import List, Dict, Any, Optional
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

    def _format_to_html(
        self,
        activities: List[Dict[str, Any]],
        warning: Optional[str],
        category: Optional[str] = None,
    ) -> str:
        """
        Genera l'output HTML IDENTICO al layout richiesto, ma usando SOLO JSON locali.
        Ignora i risultati Maps e carica i suggerimenti da assets/cities_cache/other_locals.json.
        """
        # Carica i suggerimenti locali da percorsi candidati
        pkg_dir = os.path.dirname(__file__)
        candidate_paths = [
            os.path.normpath(os.path.join(pkg_dir, "..", "assets", "cities_cache", "other_locals.json")),
            os.path.normpath(os.path.join(os.getcwd(), "assets", "cities_cache", "other_locals.json")),
            os.path.normpath(os.path.join(pkg_dir, "..", "generated_content_test_files", "other_locals.json")),
            os.path.normpath(os.path.join(os.getcwd(), "generated_content_test_files", "other_locals.json")),
        ]

        other_items: List[Dict[str, Any]] = []
        for json_path in candidate_paths:
            try:
                if not os.path.exists(json_path):
                    continue
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list) and data:
                    other_items = data
                    logger.info(
                        f"Caricato other_locals da: {json_path} ({len(data)} elementi)"
                    )
                    break
                else:
                    logger.info(
                        f"JSON other_locals vuoto o non valido: {json_path}"
                    )
            except Exception as e:
                logger.info(f"Errore nel caricamento di {json_path}: {e}")

        # Se ho una categoria specifica (hotel, vini, cucina_tipica, ristoranti, ...),
        # filtro i suggerimenti locali in base al campo "category" del JSON.
        # Obiettivo principale: gli hotel devono comparire solo nella sezione hotel
        # e non mescolarsi nelle altre sezioni.
        if other_items and category:
            cat_lower = str(category).lower()
            canonical_category: Optional[str] = None

            if "hotel" in cat_lower or "strutture" in cat_lower:
                canonical_category = "hotel"
            elif "vin" in cat_lower:  # "vini", "vino", ...
                canonical_category = "vini"
            elif "cucina" in cat_lower or "ristorant" in cat_lower:
                # Trattiamo ristoranti/cucina tipica come stessa macro-categoria
                canonical_category = "cucina_tipica"
            elif "dolci" in cat_lower:
                canonical_category = "dolci tipici"

            if canonical_category:
                filtered = [
                    it
                    for it in other_items
                    if str(it.get("category", "")).lower() == canonical_category
                ]
                if filtered:
                    other_items = filtered
                else:
                    # Se non trovo nulla per quella categoria, almeno evito
                    # che gli hotel finiscano in sezioni non-hotel.
                    if canonical_category != "hotel":
                        other_items = [
                            it
                            for it in other_items
                            if str(it.get("category", "")).lower() != "hotel"
                        ]

        # Se non troviamo elementi e non c'è alcun warning, restituiamo il messaggio identico
        if not other_items and not warning:
            return "<p>Mi dispiace, non ho trovato attività pertinenti secondo i criteri forniti.</p>"

        html_parts: List[str] = []

        # Eventuale warning in alto
        if warning:
            html_parts.append('''
            <div class="warning" style="background-color: #fffbe6; border: 1px solid #fde047; padding: 12px; border-radius: 8px; margin-bottom: 16px;">
                ''' + warning + '''
            </div>
            ''')

        # Container identico al layout richiesto
        html_parts.append('<div class="activities-grid" style="display: grid; grid-template-columns: repeat(4, 230px); gap: 22px 12px; align-items: stretch; justify-content: start;">')

        # Generazione card dal JSON locale (adattamento dei campi mancanti)
        for item in other_items:
            name = item.get('name', 'Nome non disponibile')
            price_level = item.get('price_level')
            price = '€' * price_level if price_level else ''
            rating = item.get('rating', 'N/A')
            reviews = item.get('reviews_count') or item.get('user_ratings_total', 'N/A')
            description = item.get('editorial_summary', {}).get('overview', 'Nessuna descrizione disponibile.')
            services = item.get('servizi', [])
            place_id = item.get('place_id', '')
            # Usa query_place_id solo se l'ID non è un pseudo (prefisso 'gemini-')
            if isinstance(place_id, str) and place_id and not place_id.startswith('gemini-'):
                maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}".strip()
            else:
                # Fallback: usa URL diretto se fornito, altrimenti ricerca generica su Maps
                name_addr = (item.get('name','') + ' ' + (item.get('formatted_address') or item.get('vicinity') or '')).strip()
                if item.get('url'):
                    maps_url = item.get('url').strip()
                elif name_addr:
                    from urllib.parse import quote_plus
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(name_addr)}"
                else:
                    maps_url = "https://www.google.com/maps"
            address = item.get('formatted_address') or item.get('vicinity') or ''

            # Tronca descrizione se troppo lunga
            if isinstance(description, str) and len(description) > 100:
                description = description[:100] + '...'

            # Link identico con apertura modale, adattato al JSON
            links_html = (
                f"<div class=\"links\" style=\"margin-top: 0px;\">"
                f" <a href=\"{maps_url}\" target=\"_blank\" class=\"selection-card-link\" onclick=\"openActivityModal('{place_id}', '{name.replace("'", "&#39;")}'); return false;\" style=\"display: inline-flex; align-items: center; gap: 6px; text-decoration: none;font-size: 0.875rem; font-weight: 600; color: #0f3e34;\">"
                f"Visualizza la scheda<span class=\"material-icons\" style=\"font-size: 16px; line-height: 1; color: #0f3e34;\">arrow_forward</span></a></div>"
            )

            # Immagine: usa esclusivamente Google Custom Search (CSE) tramite endpoint backend
            # Deriva city_hint dall'indirizzo per migliorare la pertinenza
            photo_url = None
            try:
                address = item.get('formatted_address') or item.get('vicinity') or ''
                city_hint = None
                if isinstance(address, str) and "," in address:
                    parts = [p.strip() for p in address.split(",") if p.strip()]
                    if len(parts) >= 2:
                        last = parts[-1].lower()
                        possible_country = any(c in last for c in ["italia", "italy"])
                        city_hint = parts[-2] if possible_country else parts[-1]
                from urllib.parse import quote_plus
                if city_hint:
                    photo_url = f"/image_search_cse?dish={quote_plus(name)}&city={quote_plus(city_hint)}"
                else:
                    photo_url = f"/image_search_cse?dish={quote_plus(name)}"
            except Exception:
                from urllib.parse import quote_plus
                photo_url = f"/image_search_cse?dish={quote_plus(name)}"
            if photo_url:
                image_core = f'<div class="activity-image" style="width: 250px; height: 200px; background-image: url({photo_url}); background-size: cover; background-position: center; border-radius: 8px 8px 0 0; margin: -16px -16px 12px -16px;"></div>'
            else:
                image_core = '<div class="activity-image" style="width: 100%; height: 150px; background: #eaeaea; border-radius: 8px 8px 0 0; margin: -16px -16px 12px -16px;"></div>'
            image_html = f'<div style="position: relative;">{image_core}<button type="button" class="add-to-trip-btn" title="Aggiungi" style="position: absolute; top: 10px; right: 10px; background: #b8f36d; border-radius: 9999px; padding: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.08); border: none; cursor: pointer;"><span class="material-icons" style="color: #0f3e34; font-size: 16px; font-weight: 700;">add</span></button></div>'

            escaped_name = name.replace("'", "&#39;")
            lat = item.get('geometry', {}).get('location', {}).get('lat', '')
            lng = item.get('geometry', {}).get('location', {}).get('lng', '')

            # Card completa con layout orizzontale identico
            html_parts.append(f'''
            <div class="activity-card" 
                data-place-id="{place_id}" 
                data-lat="{lat}" 
                data-lng="{lng}" 
                data-address="{address}"
                data-rating="{rating}"
                data-reviews="{reviews}"
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
                cursor: pointer; 
            " onmouseover="this.style.transform='translateY(-4px)'; this.style.boxShadow='0 4px 16px rgba(0,0,0,0.15)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.1)'" > 
                {image_html} 
                <div style="padding-top: 4px;"> 
                    <h3 style="font-size: 0.95rem; font-weight: 700; margin-bottom: 2px; line-height: 1.25; color: #0f172a;"> 
                        {escaped_name} 
                        {f'<span style="color: #64748b; font-size: 0.875rem;">{price}</span>' if price else ''} 
                    </h3> 
                    <p class="rating" style="margin-bottom: 0px; font-size: 0.875rem; color: #334155;"><b>⭐ {rating}</b> · {reviews} recensioni</p> 
                </div> 
                <div style="padding-top: 0px;">{links_html}</div> 
            </div> 
            ''')

        html_parts.append('</div>')

        # Bottone "Carica altri suggerimenti" identico
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

    async def filter_rank_and_present(self, search_queries: Dict[str, Any], maps_data: Dict[str, Any], user_query: str) -> Dict[str, Any]:
        """
        Metodo principale che orchestra il processo di filtering, ranking e presentazione.
        """
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

                ranked_html = self._format_to_html(ranked_selection, None, category)
                ranked_results[category] = {
                    "results": ranked_html,
                    "iframe_url": data.get("iframe_url")
                }
            else:
                # Nessun risultato da Maps: mostra comunque i suggerimenti locali
                ranked_html = self._format_to_html([], None, category)
                ranked_results[category] = {
                    "results": ranked_html,
                    "iframe_url": data.get("iframe_url")
                }
        
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
            if act.get('rating') >= 3.8:
                logger.info(f"L'attività '{act.get('name')}' con rating {act.get('rating')} corrisponde al filtro.")
                filtered_list.append(act)
            else:
                logger.info(f"L'attività '{act.get('name')}' con rating {act.get('rating')} non corrisponde al filtro.")
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
            rating = activity.get('rating', 0)
            reviews = activity.get('user_ratings_total', 0)
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
            num_to_select = min(24, num_activities)
            top_activities = sorted_activities[:num_to_select]
            logger.info(f"Selezionate le prime {num_to_select} attività su {num_activities}.")

        return top_activities

    




    def _create_our_selection(self, all_activities: dict) -> Optional[str]:
        """Crea la sezione 'La nostra selezione' mixando JSON locale e risultati Maps.

        - Prova a caricare un JSON di override (our_selection_override.json).
        - Se non esiste o non è valido, seleziona attività da ``all_activities``
          usando ``target_categories`` e un fallback fino a 8 card.
        - Genera l'HTML completo delle card.
        """

        selected_items: List[Dict[str, Any]] = []

        # 1) Prova a usare il JSON di override se presente
        try:
            pkg_dir = os.path.dirname(__file__)
            candidate_paths = [
                os.path.normpath(os.path.join(pkg_dir, "..", "assets", "cities_cache", "our_selection_override.json")),
                os.path.normpath(os.path.join(os.getcwd(), "assets", "cities_cache", "our_selection_override.json")),
                os.path.normpath(os.path.join(pkg_dir, "..", "generated_content_test_files", "our_selection_override.json")),
                os.path.normpath(os.path.join(os.getcwd(), "generated_content_test_files", "our_selection_override.json")),
            ]

            override_items = None
            for json_path in candidate_paths:
                if not os.path.exists(json_path):
                    continue
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list) and data:
                    override_items = data
                    logger.info(f"Caricato override da: {json_path} ({len(data)} elementi)")
                    break
                else:
                    logger.info(f"JSON vuoto o non valido: {json_path}")

            if override_items:
                for it in override_items:
                    pid = it.get("place_id")
                    url = it.get("url")
                    if not pid and not url:
                        continue
                    # Estrai coordinate e numero recensioni dall'override, con vari fallback
                    # Le chiavi supportate nell'override: lat/lng, latitude/longitude, geometry.location
                    lat = None
                    lng = None
                    if isinstance(it.get("geometry"), dict):
                        lat = (it.get("geometry") or {}).get("location", {}).get("lat")
                        lng = (it.get("geometry") or {}).get("location", {}).get("lng")
                    if lat is None:
                        lat = it.get("lat") or it.get("latitude")
                    if lng is None:
                        lng = it.get("lng") or it.get("longitude")

                    reviews_count = it.get("reviews_count") or it.get("user_ratings_total")

                    selected_items.append({
                        "place_id": pid or "",
                        "url": url or "",
                        "name": it.get("name", "Nome non disponibile"),
                        "formatted_address": it.get("formatted_address", "Indirizzo non disponibile"),
                        "display_category": it.get("category", ""),
                        "image": it.get("image", ""),
                        "rating": it.get("rating"),
                        # Normalizziamo il conteggio recensioni in user_ratings_total per compatibilità
                        "user_ratings_total": reviews_count,
                        "reviews_count": reviews_count,
                        "price_level": it.get("price_level"),
                        "editorial_summary": it.get("editorial_summary", {}),
                        "lat": lat,
                        "lng": lng,
                    })

        except Exception as e:
            logger.info(f"Errore caricamento JSON 'La nostra selezione': {e}")

        # 2) Se non ho nulla dall'override, uso le categorie target su all_activities
        if not selected_items:
            target_categories = {
                "strutture ricettive": {
                    "keywords": ["hotel", "alloggi", "accommodation"],
                    "limit": 2,
                },
                "vini": {
                    "keywords": ["vini", "wine", "enoteca", "cantina"],
                    "limit": 2,
                },
                "cucina_tipica": {
                    "keywords": [
                        "cucina_tipica",
                        "ristoranti",
                        "restaurant",
                        "food",
                        "dining",
                        "trattoria",
                    ],
                    "limit": 2,
                },
            }

            for target_key, cfg in target_categories.items():
                keywords = cfg["keywords"]
                limit = cfg["limit"]
                count_added = 0
                for category, activities in all_activities.items():
                    if count_added >= limit:
                        break
                    if activities and any(keyword in category.lower() for keyword in keywords):
                        for act in activities:
                            if count_added >= limit:
                                break
                            item = dict(act)
                            item["display_category"] = target_key
                            selected_items.append(item)
                            count_added += 1
                            logger.info(
                                f"Selezionata attività '{item.get('name')}' per la categoria target '{target_key}' dalla categoria '{category}'"
                            )

            # Se non abbiamo trovato nulla, restituisci None
            if not selected_items:
                logger.info("Nessuna attività disponibile per 'La nostra selezione' nelle categorie specificate")
                return None

            # Fallback: riempi fino a 8 card totali prendendo ulteriori elementi da altre categorie
            try:
                seen_ids = {
                    it.get("place_id")
                    for it in selected_items
                    if it.get("place_id")
                }
                if len(selected_items) < 8:
                    for cat, activities in all_activities.items():
                        for act in activities:
                            pid = act.get("place_id")
                            if pid and pid not in seen_ids:
                                extra = dict(act)
                                extra["display_category"] = extra.get(
                                    "display_category"
                                ) or cat
                                selected_items.append(extra)
                                seen_ids.add(pid)
                                if len(selected_items) >= 8:
                                    break
                        if len(selected_items) >= 8:
                            break
            except Exception:
                # meglio non bloccare tutta la sezione per un errore nel fallback
                pass

        # A questo punto selected_items contiene la lista finale da mostrare
        if not selected_items:
            return None

        try:
            logger.info(
                f"OUR_SELECTION: totale elementi selezionati = {len(selected_items)}"
            )
            for it in selected_items:
                logger.info(
                    f"Place_id \"{it.get('place_id','')}\", nome \"{it.get('name','')}\""
                )
        except Exception as e:
            logger.info(
                f"Errore nella stampa dei luoghi 'La nostra selezione': {e}"
            )

        # 3) Generazione HTML delle card
        html_parts: List[str] = []
        html_parts.append(
            '''
        <div class="our-selection" style="margin: 16px 16px 16px 48px; padding: 28px 28px 32px 32px; background-color: #0f3e34; border-radius: 1px; color: #ffffff; max-width: 1400px;">
            <h2 style="margin: 0 0 8px 0; font-size: 1.5rem; font-weight: 800; text-align: left; color:#b7f056;">La nostra selezione</h2>
            <div class="selection-grid" style="display: grid; grid-template-columns: repeat(4, 230px); gap: 24px 16px; align-items: stretch; justify-content: start;">
        '''
        )

        category_display = {
            "hotel": {"svg": "hotel.svg", "name": "Hotel", "color": ""},
            "strutture ricettive": {
                "svg": "hotel.svg",
                "name": "Hotel",
                "color": "",
            },
            "ristoranti": {
                "svg": "ristorante.svg",
                "name": "Ristoranti",
                "color": "",
            },
            "dolci tipici": {
                "svg": "dolci.svg",
                "name": "Dolci Tipici",
                "color": "",
            },
            "cucina_tipica": {
                "svg": "ristorante.svg",
                "name": "Cucina Tipica",
                "color": "",
            },
            "vini": {"svg": "vini.svg", "name": "Vini", "color": ""},
        }

        for item in selected_items:
            name = item.get("name", "Nome non disponibile")
            price = (
                "€" * item.get("price_level", 0)
                if item.get("price_level")
                else ""
            )
            rating = item.get("rating", "N/A")
            reviews = item.get("reviews_count") or item.get("user_ratings_total", "N/A")
            # Nessuna descrizione di default "Esperienza unica e indimenticabile":
            # se non c'è overview, non mostriamo il paragrafo
            description = item.get("editorial_summary", {}).get("overview") or ""
            place_id = item.get("place_id", "")
            # Usa query_place_id solo se l'ID non è un pseudo (prefisso 'gemini-')
            if isinstance(place_id, str) and place_id and not place_id.startswith('gemini-'):
                maps_url = f"https://www.google.com/maps/search/?api=1&query_place_id={str(place_id)}".strip()
            else:
                # Fallback: URL diretto o ricerca generica
                name_addr = (item.get('name','') + ' ' + (item.get('formatted_address') or item.get('vicinity') or '')).strip()
                if item.get("url"):
                    maps_url = item.get("url").strip()
                elif name_addr:
                    from urllib.parse import quote_plus
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(name_addr)}"
                else:
                    maps_url = "https://www.google.com/maps"
            address = (
                item.get("formatted_address")
                or item.get("vicinity")
                or ""
            )

            # Coordinate: supporta sia struttura geometry.location che campi lat/lng top-level
            lat = (
                (item.get("geometry", {}) or {}).get("location", {}).get("lat")
                if isinstance(item.get("geometry"), dict)
                else None
            )
            if lat is None:
                lat = item.get("lat") or item.get("latitude")
            lng = (
                (item.get("geometry", {}) or {}).get("location", {}).get("lng")
                if isinstance(item.get("geometry"), dict)
                else None
            )
            if lng is None:
                lng = item.get("lng") or item.get("longitude")
            lat = lat if lat is not None else ""
            lng = lng if lng is not None else ""

            # URL immagine (se presente)
            photo_url = item.get("image") or self._get_photo_url(item.get("photos"))

            # Tronca descrizione
            if description and len(description) > 80:
                description = description[:80] + "..."

            # Determina categoria visuale
            category = str(item.get("display_category", "")).lower()
            if category in category_display:
                svg_icon = category_display[category]["svg"]
                display_name = category_display[category]["name"]
                cat_color = category_display[category]["color"]
            else:
                svg_icon = "ristorante.svg"
                display_name = category.replace("_", " ").title()
                cat_color = ""

            # Escape del nome per JavaScript
            escaped_name = name.replace("'", "\\'")

            image_html = ""
            if photo_url:
                image_html = f'''
                <div class="activity-image" style="width: 250px; height: 200px; background-image: url({photo_url}); background-size: cover; background-position: center; border-radius: 8px 8px 0 0; margin: -16px -16px 12px -16px;"></div>
                '''

            html_parts.append(
                f'''
             <div class="activity-card selection-card"
                data-place-id="{place_id}"
                data-lat="{lat}"
                data-lng="{lng}"
                data-rating="{rating}"
                data-reviews="{reviews}"
                data-address="{address}"
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
    cursor: pointer;
                " onmouseenter="this.style.transform='translateY(-4px)'; this.style.boxShadow='0 4px 16px rgba(0,0,0,0.15)'; try{{this.querySelector('.minus-btn').style.opacity='1';}}catch(e){{}}" 
  onmouseleave="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.1)'; try{{this.querySelector('.minus-btn').style.opacity='0';}}catch(e){{}}">
                
                <button type="button" class="minus-btn" title="Rimuovi"
                    data-place-id="{place_id}"
                    style="position: absolute; top: 48px; right: 10px; width: 28px; height: 28px; border-radius: 9999px; border: 2px solid #0f3e34; color:#0f3e34; background: #ffffff; display: inline-flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 700; cursor: pointer; opacity: 0; transition: opacity 0.2s; z-index: 2;"
                    onmouseover="this.style.background='#b7f056'"
                    onmouseout="this.style.background='#ffffff'"
                    >-</button>
                {image_html}
               <div style="padding: 14px 12px 12px 12px; display: flex; flex-direction: column; height: auto;">
                    <div style="display: inline-flex; align-items: center; gap: 12px; font-size: 0.95rem; margin: 12px 0 8px; color: #374151; text-transform: uppercase; font-weight: 700; height: 36px;">
                        <span style="width: 32px; height: 32px; border-radius: 9999px; display: inline-flex; align-items: center; justify-content: center; background:{cat_color};">
                            <img src="/assets/{svg_icon}" alt="" style="width: 24px; height: 24px;" />
                        </span>
                        <span style="font-weight: 700; letter-spacing: 0.02em;">{display_name}</span>
                    </div>
                    <h3 style="font-size: 0.95rem; font-weight: 700; margin-bottom: 6px; line-height: 1.3; color: #0f172a;">
                        {name} <span aria-hidden="true" style="color: #22c55e; font-weight: 800; font-size: 18px; margin-left: 8px;">✓</span>
                        {f'<span style="color: #64748b; font-size: 0.875rem; margin-left: 4px;">{price}</span>'}
                    </h3>
                    <p style="margin-bottom: 4px; font-size: 0.875rem; color: #334155;"><b>⭐ {rating}</b> · {reviews} recensioni</p>
                    {f'<p style="margin-bottom: 8px; font-size: 0.875rem; color: #334155;">{description}</p>' if description else ''}
                    <!-- Indirizzo rimosso dalla card; viene mostrato solo nella scheda pop-up -->
                    <div style="margin-top: 4px;"></div>
                    <div style="padding-top: 2px;">
                        <a href="{maps_url}" target="_blank" class="selection-card-link" onclick="openActivityModal('{place_id}', '{escaped_name}'); return false;" style="
                            display: inline-flex; align-items: center; gap: 6px; text-decoration: none;
                            font-size: 0.875rem; font-weight: 600; color: #0f3e34;">
                            Visualizza la scheda
                            <span class="material-icons" style="font-size: 16px; line-height: 1; color: #0f3e34;">arrow_forward</span>
                        </a>
                    </div>
                </div>
            </div>
            '''
            )

        html_parts.append("</div></div>")
        return "\n".join(html_parts)
    


    

    

    

    
