import logging
import os
import json
import re
from typing import Dict, Any, List, Optional, Union

import httpx
from google import genai
from google.genai import types
from ..config.settings import settings

logger = logging.getLogger(__name__)


class GeminiMapsService:
    """
    Genera venue locali con Gemini + Google Places API.
    Garantisce place_id reali, foto reali e link Maps corretti.
    """

    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = os.getenv("GEMINI_MAPS_MODEL", "gemini-2.5-flash")

        self.google_maps_api_key = settings.google_maps_api_key
        self.places_base = "https://maps.googleapis.com/maps/api/place"

        self.google_maps_tool = types.Tool(google_maps=types.GoogleMaps())

    # ------------------------------------------------------------------
    # UTIL
    # ------------------------------------------------------------------

    def _extract_city(self, text: Optional[Union[str, List[str]]]) -> Optional[str]:
        if not text:
            return None

        # Se arriva una lista di query, prova a estrarre la città dalla prima stringa valida
        if isinstance(text, list):
            for t in text:
                if isinstance(t, str) and t.strip():
                    extracted = self._extract_city(t)
                    if extracted:
                        return extracted
            return None

        patterns = [
            r"\b(?:a|ad|in|near|vicino a)\s+([A-Za-zÀ-ÿ' \-]+)",
            r"\b([A-Za-zÀ-ÿ' \-]+),\s*Italia"
        ]

        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()

        return None

    def _parse_json(self, text: str) -> Dict[str, Any]:
        if not text:
            return {"results": []}

        match = re.search(r"(\{[\s\S]*\})", text)
        if match:
            text = match.group(1)

        try:
            return json.loads(text)
        except Exception:
            logger.warning("JSON non valido da Gemini")
            return {"results": []}

    # ------------------------------------------------------------------
    # PROMPT
    # ------------------------------------------------------------------

    def _build_prompt(self, query: str, city: Optional[str]) -> str:
        city_line = f'LOCALITÀ: "{city}"' if city else ""

        return f"""
Genera una lista di LUOGHI REALI coerenti con la ricerca.

RICERCA: "{query}"
{city_line}

REGOLE:
- Usa SOLO luoghi realmente esistenti
- Limita alla località indicata
- NON inventare place_id
- Restituisci SOLO JSON

Formato:

{{
  "results": [
    {{
      "name": "...",
      "formatted_address": "...",
      "type": "restaurant|hotel|bar",
      "rating": 4.5,
      "user_ratings_total": 120
    }}
  ]
}}
"""

    # ------------------------------------------------------------------
    # GOOGLE PLACES API
    # ------------------------------------------------------------------

    async def _places_find(self, query: str) -> Optional[Dict[str, Any]]:
        url = f"{self.places_base}/findplacefromtext/json"
        params = {
            "input": query,
            "inputtype": "textquery",
            "fields": "place_id,name,formatted_address,geometry,photos",
            "key": self.google_maps_api_key,
            "language": "it"
        }

        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, params=params)
            r.raise_for_status()
            data = r.json()

        return data["candidates"][0] if data.get("candidates") else None

    async def _place_details(self, place_id: str) -> Dict[str, Any]:
        url = f"{self.places_base}/details/json"
        params = {
            "place_id": place_id,
            "fields": "name,formatted_address,geometry,website,rating,user_ratings_total,opening_hours,reviews,international_phone_number,formatted_phone_number,photos",
            "language": "it",
            "key": self.google_maps_api_key
        }

        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, params=params)
            r.raise_for_status()
            result = r.json().get("result", {})

        photo_url = None
        if result.get("photos"):
            ref = result["photos"][0].get("photo_reference")
            if ref:
                photo_url = self._photo_url(ref)

        return {
            "name": result.get("name"),
            "formatted_address": result.get("formatted_address"),
            "geometry": result.get("geometry"),
            "website": result.get("website"),
            "rating": result.get("rating"),
            "user_ratings_total": result.get("user_ratings_total"),
            "opening_hours": result.get("opening_hours"),
            "reviews": result.get("reviews"),
            "international_phone_number": result.get("international_phone_number"),
            "formatted_phone_number": result.get("formatted_phone_number"),
            "photo_url": photo_url,
            "place_id": place_id,
        }

    async def get_place_details(self, place_id: str) -> Dict[str, Any]:
        """Endpoint backend per /api/place_details/{place_id}. Restituisce dettagli completi.
        Non solleva eccezioni; in caso di ID non valido o errore, ritorna un oggetto con 'error'."""
        try:
            if not place_id or str(place_id).startswith("gemini-"):
                return {"error": "ID non valido per Place Details"}
            return await self._place_details(place_id)
        except Exception as e:
            logger.error(f"Errore nel recupero dettagli per '{place_id}': {e}", exc_info=True)
            return {"error": "Errore nel recupero dei dettagli del luogo"}

    def _photo_url(self, ref: str) -> str:
        return (
            f"{self.places_base}/photo"
            f"?maxwidth=1600"
            f"&photo_reference={ref}"
            f"&key={self.google_maps_api_key}"
        )

    # ------------------------------------------------------------------
    # MAIN
    # ------------------------------------------------------------------

    async def search_places(self, categories: Dict[str, Any], user_message: str) -> Dict[str, Any]:
        results = {}
        categories_count = len(categories) if isinstance(categories, dict) else 0
        findplace_calls = 0
        details_calls = 0
        per_category_results: Dict[str, int] = {}

        for category, query in categories.items():
            try:
                # Gestione liste di query (es. luoghi specifici): cerca direttamente ciascun luogo
                if isinstance(query, list):
                    q_strings = [q for q in query if isinstance(q, str) and q.strip()]
                    city = self._extract_city(q_strings) or self._extract_city(user_message)
                    venues: List[Dict[str, Any]] = []

                    for q in q_strings:
                        findplace_calls += 1
                        place = await self._places_find(q)
                        if not place:
                            continue

                        place_id = place.get("place_id")
                        details_calls += 1
                        details = await self._place_details(place_id)

                        venues.append({
                            "name": place.get("name"),
                            "formatted_address": place.get("formatted_address"),
                            "geometry": details.get("geometry") or place.get("geometry"),
                            "rating": details.get("rating"),
                            "user_ratings_total": details.get("user_ratings_total"),
                            "place_id": place_id,
                            "photo_url": details.get("photo_url"),
                            "website": details.get("website"),
                            "maps_url": f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                        })

                    results[category] = {"results": venues}
                    per_category_results[category] = len(venues)
                    continue

                # Gestione query string (generazione + validazione con Places)
                city = self._extract_city(query) or self._extract_city(user_message)
                query_str = query if isinstance(query, str) else ""

                prompt = self._build_prompt(query_str, city)

                gen_config = types.GenerateContentConfig(
                    tools=[self.google_maps_tool]
                )

                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=gen_config
                )

                parsed = self._parse_json(response.text)
                venues: List[Dict[str, Any]] = []

                for item in parsed.get("results", []):
                    search_query = f"{item.get('name')}, {item.get('formatted_address')}, {city or ''}"

                    findplace_calls += 1
                    place = await self._places_find(search_query)
                    if not place:
                        continue

                    place_id = place.get("place_id")
                    details_calls += 1
                    details = await self._place_details(place_id)

                    venues.append({
                        "name": item.get("name"),
                        "formatted_address": place.get("formatted_address"),
                        # Usa i valori reali dai dettagli
                        "rating": details.get("rating"),
                        "user_ratings_total": details.get("user_ratings_total"),
                        "place_id": place_id,
                        # Includi le coordinate corrette
                        "geometry": details.get("geometry") or place.get("geometry"),
                        "photo_url": details.get("photo_url"),
                        "website": details.get("website"),
                        # Allinea lo schema del link alla versione con ':'
                        "maps_url": f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                    })

                results[category] = {"results": venues}
                per_category_results[category] = len(venues)
            except Exception as e:
                logger.warning(f"Categoria '{category}' fallita: {e}")
                results[category] = {"results": []}
                per_category_results[category] = 0

        total_calls = findplace_calls + details_calls
        logger.info(
            f"[GeminiMaps] Places API calls: categories={categories_count}, "
            f"results_per_category={per_category_results}, "
            f"findplace={findplace_calls}, details={details_calls}, total={total_calls}"
        )

        results["_meta"] = {
            "categories": categories_count,
            "per_category_results": per_category_results,
            "findplace_calls": findplace_calls,
            "details_calls": details_calls,
            "total_calls": total_calls,
        }

        return results