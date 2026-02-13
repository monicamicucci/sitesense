import json
import logging
import re
from typing import Dict, Optional, Any
import os

from google import genai
from google.genai import types

from ..config.settings import settings
from .google_maps_service import GoogleMapsService

logger = logging.getLogger(__name__)
GEMINI_MODEL = os.getenv("GEMINI_CHAT_BOT_MODEL")


class AnalyzerService:
    """Analizza contenuti e genera ricerche Google Maps con località dedotta da Gemini."""

    def __init__(self, google_maps_service: GoogleMapsService):
        self.analyzer_client = genai.Client(api_key=settings.gemini_api_key)
        self.analyzer_config = self._setup_analyzer_generation_config()
        self.google_maps_service = google_maps_service

    def _setup_analyzer_generation_config(self) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=self._get_analyzer_system_prompt(),
            temperature=0.1,
        )

    def _get_analyzer_system_prompt(self) -> str:
        return """
Sei un assistente specializzato nell'analisi di contenuti turistici ed enogastronomici italiani.

OBIETTIVO:
- Analizzare la query dell’utente
- Analizzare il contenuto generato
- DEDURRE o CONFERMARE la località geografica di riferimento
- Generare query Google Maps coerenti

CONTESTO:
- Ti viene fornita, quando disponibile, una LOCALITÀ CORRENTE (es. la città già scelta in conversazione).
- DEVI mantenere coerenza tra i turni: non cambiare città se l’utente non lo chiede esplicitamente.

REGOLE LOCALITÀ:
- Se la località è presente nella query utente, usala.
- Se NON è presente, deducila da piatti tipici, prodotti, vini, tradizioni.
- Usa come località solo città o paesi italiani (no regioni se è nota una città).
- Se è presente la LOCALITÀ CORRENTE, NON cambiarla in presenza di richieste di filtro come:
  "questa città", "qui", "in zona", "dintorni", "solo i vini", "solo i dolci",
  "filtra", "restringi", "mostrami solo".
- Cambia città SOLO se l’utente lo chiede esplicitamente, con frasi come:
  "ora spostiamoci a <Città>", "andiamo a <Città>", "a <Città>", "in <Città>".

CATEGORIE E QUERY:
- Ogni query DEVE includere la località.
- Categorie consentite: "Cucina Tipica", "Vini", "Dolci Tipici", "Hotel" (sinonimo: "Strutture Ricettive"), .
- NON includere eventi o sagre.

ESEMPI MULTI-TURNO:
Utente: "Cosa visitare a Firenze?"
→ località: Firenze
Utente: "Mostrami solo i vini di questa città"
→ località: Firenze (non cambiare)
Utente: "E i dolci?"
→ località: Firenze (non cambiare)
Utente: "Ora spostiamoci a Siena"
→ località: Siena (cambia esplicitamente)

FORMATO DI OUTPUT:
Restituisci SOLO un JSON valido, senza markdown e senza intestazioni:
{
  "localita": "<località>",
  "queries": {
    "<categoria>": "<query>" | ["<query1>", "<query2>"]
  }
}

 -DEVI sempre aggiungere una sezione hotel
 -DEVI sempre aggiungere una sezione vini
 -DEVI sempre aggiungere una sezione dolci tipici
"""

    async def analyze_content_for_maps_search(
        self,
        content_response: str,
        original_query: str,
        current_location: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:

        try:
            logger.info("Analisi contenuto per Google Maps (località dedotta da Gemini)")

            analyzer_chat = self.analyzer_client.chats.create(
                model=GEMINI_MODEL,
                config=self.analyzer_config
            )

            prompt = f"""
QUERY UTENTE:
{original_query}

CONTENUTO GENERATO:
{content_response}

LOCALITÀ CORRENTE (se presente): {current_location or ''}

Genera il JSON delle ricerche Google Maps.
"""

            response = analyzer_chat.send_message(prompt)
            raw_text = response.candidates[0].content.parts[0].text.strip()

            match = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
            if match:
                raw_text = match.group(1)

            result = json.loads(raw_text)

            if "localita" not in result or "queries" not in result:
                logger.error("JSON non valido: manca localita o queries")
                return None

            self._validate_queries(result["queries"], result["localita"]) 

            try:
                if current_location:
                    ql = original_query.lower()
                    if re.search(r"(questa città|qui|in zona|dintorni|solo i vini|solo i dolci|mostrami solo|restringi|filtra)", ql):
                        result["localita"] = current_location
            except Exception:
                pass

            logger.info("Località dedotta correttamente: %s", result["localita"])            
            return result

        except Exception as e:
            logger.exception("Errore AnalyzerService")
            return None

    def _validate_queries(self, queries: Dict[str, Any], location: str) -> None:
        for category, value in queries.items():
            if isinstance(value, str):
                if location.lower() not in value.lower():
                    logger.warning(
                        f"Query '{value}' non contiene la località '{location}'"
                    )
            elif isinstance(value, list):
                for q in value:
                    if location.lower() not in q.lower():
                        logger.warning(
                            f"Query '{q}' non contiene la località '{location}'"
                        )