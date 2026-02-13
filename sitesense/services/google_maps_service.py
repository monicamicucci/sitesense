import asyncio
import logging
import httpx
import math
from typing import Dict, List, Any, Optional
from ..config.settings import settings
from .filtering_ranking_service import FilteringRankingService

logger = logging.getLogger(__name__)

class GoogleMapsService:
    """Servizio per gestire le chiamate alle API di Google Maps"""
    
    def __init__(self):
        self.api_key = settings.google_maps_api_key
        self.base_url = "https://maps.googleapis.com/maps/api"
        self.filtering_ranking_service = FilteringRankingService()
        if self.api_key == "DUMMY_KEY":
            logger.warning(
                "GOOGLE_MAPS_API_KEY mancante o DEBUG_MODE attivo: uso DUMMY_KEY. "
                "Le chiamate alle API di Google restituiranno errori e i risultati (place_id) potrebbero essere vuoti."
            )

        
    async def _search_single_category(self, category: str, query: Any, language: str) -> Dict[str, Any]:
        """Esegue una o più ricerche per una categoria specifica."""
        logger.info(f"Ricerca luoghi per categoria '{category}' con query: '{query}'")

        if isinstance(query, list):

            
            # Se la query è una lista, esegui una ricerca "Find Place" per ogni elemento
            tasks = [self._find_exact_place(sub_query, language) for sub_query in query]
            search_results = await asyncio.gather(*tasks)
            
            # Filtra i risultati nulli (luoghi non trovati)
            results = [res for res in search_results if res]
            
            # Usa la prima query per l'URL dell'iframe rappresentativo
            iframe_url = self._build_search_iframe_url(query[0]) if query else None
        else:
            # Se la query è una stringa, esegui una singola ricerca
            results = await self._perform_text_search(query, language)
            iframe_url = self._build_search_iframe_url(query)

        logger.info(f"Trovati {len(results)} risultati per la categoria '{category}'")
        return {category: {"results": results, "iframe_url": iframe_url}}

    async def _perform_text_search(self, query: str, language: str) -> List[Dict[str, Any]]:
        """Esegue una singola ricerca textsearch e restituisce i risultati filtrati geograficamente."""
        url = f"{self.base_url}/place/textsearch/json"
        fields = ["name", "formatted_address", "rating", "geometry", "types", "photos", "place_id", "user_ratings_total", "price_level", "website", "editorial_summary", "url"]
        params = {
            "query": query,
            "key": self.api_key,
            "language": language,
            "fields": ",".join(fields)
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()
        status = data.get("status")
        error_message = data.get("error_message")
        if status != "OK":
            logger.warning(
                f"TextSearch fallita o non OK (status={status}, error={error_message}) per query='{query}'."
            )
        
        results = data.get("results", [])
        
        # Applica filtro geografico se possibile
        filtered_results = await self._apply_geographic_filter(results, query)
        
        return filtered_results

    async def _find_exact_place(self, query: str, language: str) -> Optional[Dict[str, Any]]:
        """Esegue una ricerca 'Find Place' per trovare il candidato più probabile."""
        url = f"{self.base_url}/place/findplacefromtext/json"
        fields = ["place_id", "name", "formatted_address", "geometry", "rating", "types", "photos", "user_ratings_total", "price_level"]
        params = {
            "input": query,
            "inputtype": "textquery",
            "key": self.api_key,
            "language": language,
            "fields": ",".join(fields)
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()
        status = data.get("status")
        error_message = data.get("error_message")
        if status != "OK":
            logger.warning(
                f"FindPlace non OK (status={status}, error={error_message}) per input='{query}'."
            )

        # "Find Place" restituisce una lista "candidates"
        candidates = data.get("candidates", [])
        if candidates:
            # Applica filtro geografico anche ai candidati
            filtered_candidates = await self._apply_geographic_filter(candidates, query)
            if filtered_candidates:
                return filtered_candidates[0]  # Restituisce il primo candidato filtrato
        return None

    async def search_places(self, search_queries: Dict[str, Any], user_query: str, language: str = "it") -> Dict[str, Any]:
        """Cerca luoghi in parallelo e applica le regole di ranking se abilitato."""
        if not search_queries:
            return {}

        tasks = []
        for category, query in search_queries.items():
            tasks.append(self._search_single_category(category, query, language))
        
        results_list = await asyncio.gather(*tasks)
        
        raw_results = {}
        for result in results_list:
            for category, data in result.items():
                num_results = len(data.get("results", []))
                logger.info(f"Categoria '{category}': {num_results} risultati ricevuti da Google Maps.")
            raw_results.update(result)
            
        return raw_results
    
    async def get_place_details(self, place_id: str, language: str = "it") -> Dict[str, Any]:
        """Ottiene i dettagli di un luogo specifico"""
        logger.info(f"Recupero dettagli per place_id: '{place_id}'")
        
        url = f"{self.base_url}/place/details/json"
        params = {
            "place_id": place_id,
            "key": self.api_key,
            "language": language
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()
        
        result = data.get("result", {})
        result["photo_url"] = self._get_photo_url(result.get("photos"))
        
        return result
    
    def _process_places_results(self, places: List[Dict]) -> List[Dict[str, Any]]:
        """Processa i risultati della ricerca luoghi, limitando a 20 risultati."""
        results = []
        for place in places[:20]:  # Limita ai primi 20 risultati
            photo_url = self._get_photo_url(place.get("photos"))
            
            results.append({
                "nome": place.get("name"),
                "indirizzo": place.get("formatted_address"),
                "valutazione": place.get("rating", "N/A"),
                "coordinate": place.get("geometry", {}).get("location"),
                "tipologie": place.get("types", []),
                "foto_url": photo_url,
                "place_id": place.get("place_id")
            })
        
        return results
    
    def _process_directions_steps(self, routes: List[Dict]) -> List[Dict[str, str]]:
        """Processa le indicazioni stradali"""
        if not routes:
            return []
        
        all_steps = []
        for route in routes:
            for leg in route.get("legs", []):
                for step in leg.get("steps", []):
                    instruction = self._clean_html_instruction(step.get("html_instructions", ""))
                    distance = step.get("distance", {}).get("text", "")
                    duration = step.get("duration", {}).get("text", "")
                    
                    all_steps.append({
                        "istruzione": instruction,
                        "distanza": distance,
                        "durata": duration
                    })
        
        return all_steps
    
    def _clean_html_instruction(self, instruction: str) -> str:
        """Pulisce le istruzioni HTML"""
        return (instruction
                .replace("<div style=\"font-size:0.9em\">", " ")
                .replace("</div>", "")
                .replace("<b>", "")
                .replace("</b>", ""))
    
    def _get_photo_url(self, photos: Optional[List[Dict]]) -> Optional[str]:
        """Costruisce l'URL della foto se disponibile"""
        if not photos:
            return None
        
        photo_reference = photos[0].get("photo_reference")
        if not photo_reference:
            return None
        
        return (f"{self.base_url}/place/photo"
                f"?maxwidth=400&photoreference={photo_reference}&key={self.api_key}")
    
    def _build_search_iframe_url(self, query: str) -> str:
        """Costruisce l'URL iframe per la ricerca"""
        encoded_query = query.replace(' ', '+')
        return f"https://www.google.com/maps/embed/v1/search?key={self.api_key}&q={encoded_query}"
    
    def _build_place_iframe_url(self, query: str) -> str:
        """Costruisce l'URL iframe per visualizzare un luogo"""
        encoded_query = query.replace(' ', '+')
        return f"https://www.google.com/maps/embed/v1/place?key={self.api_key}&q={encoded_query}"
    
    def _build_directions_iframe_url(self, origin: str, destination: str) -> str:
        """Costruisce l'URL iframe per le indicazioni"""
        encoded_origin = origin.replace(' ', '+')
        encoded_destination = destination.replace(' ', '+')
        return (f"https://www.google.com/maps/embed/v1/directions?key={self.api_key}"
                f"&origin={encoded_origin}&destination={encoded_destination}")
    
    async def _apply_geographic_filter(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Applica un filtro geografico ai risultati basato sulla località nella query."""
        try:
            # Estrai la località dalla query
            location = self._extract_location_from_query(query)
            if not location:
                return results  # Se non riusciamo a estrarre la località, restituiamo tutti i risultati
            
            # Ottieni le coordinate della località di riferimento
            reference_coords = await self._get_location_coordinates(location)
            if not reference_coords:
                return results  # Se non riusciamo a ottenere le coordinate, restituiamo tutti i risultati
            
            # Filtra i risultati in base alla distanza (max 50km)
            filtered_results = []
            for result in results:
                geometry = result.get('geometry', {})
                location_coords = geometry.get('location', {})
                
                if location_coords.get('lat') and location_coords.get('lng'):
                    distance = self._calculate_distance(
                        reference_coords['lat'], reference_coords['lng'],
                        location_coords['lat'], location_coords['lng']
                    )
                    
                    # Mantieni solo i risultati entro 50km
                    if distance <= 35:
                        filtered_results.append(result)
                    else:
                        logger.info(f"Filtrato risultato '{result.get('name')}' - distanza: {distance:.1f}km")
                else:
                    # Se non abbiamo coordinate, manteniamo il risultato
                    filtered_results.append(result)
            
            logger.info(f"Filtro geografico: {len(results)} -> {len(filtered_results)} risultati")
            return filtered_results
            
        except Exception as e:
            logger.warning(f"Errore nel filtro geografico: {e}")
            return results  # In caso di errore, restituiamo tutti i risultati
    
    def _extract_location_from_query(self, query: str) -> Optional[str]:
        """Estrae la località dalla query di ricerca."""
        import re
        
        # Pattern per estrarre località dopo "a", "in", "di", "vicino a"
        patterns = [
            r'\b(?:a|in|di)\s+([A-Z][a-zA-Z\s]+?)(?:\s|$)',
            r'vicino\s+a\s+([A-Z][a-zA-Z\s]+?)(?:\s|$)',
            r'\b([A-Z][a-zA-Z\s]+?)\s+ristorante',
            r'ristorante\s+([A-Z][a-zA-Z\s]+?)(?:\s|$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                # Filtra parole comuni che non sono località
                if location.lower() not in ['me', 'centro', 'buono', 'migliore', 'tipico']:
                    return location
        
        return None
    
    async def _get_location_coordinates(self, location: str) -> Optional[Dict[str, float]]:
        """Ottiene le coordinate di una località usando l'API Geocoding."""
        try:
            url = f"{self.base_url}/geocode/json"
            params = {
                'address': location,
                'key': self.api_key
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                data = response.json()
            
            results = data.get('results', [])
            if results:
                geometry = results[0].get('geometry', {})
                location_coords = geometry.get('location', {})
                
                if location_coords.get('lat') and location_coords.get('lng'):
                    return {
                        'lat': location_coords['lat'],
                        'lng': location_coords['lng']
                    }
            
            return None
            
        except Exception as e:
            logger.warning(f"Errore nel recupero coordinate per '{location}': {e}")
            return None
    
    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calcola la distanza in km tra due punti usando la formula dell'emisenoverso."""
        # Raggio della Terra in km
        R = 6371.0
        
        # Converti gradi in radianti
        lat1_rad = math.radians(lat1)
        lng1_rad = math.radians(lng1)
        lat2_rad = math.radians(lat2)
        lng2_rad = math.radians(lng2)
        
        # Differenze
        dlat = lat2_rad - lat1_rad
        dlng = lng2_rad - lng1_rad
        
        # Formula dell'emisenoverso
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        # Distanza in km
        distance = R * c
        
        return distance
