import logging
import json
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from ..services import GeminiMapsService, GeminiService, AnalyzerService
from ..services.filtering_ranking_service import FilteringRankingService

logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    """Modello per le richieste di chat"""
    query: str = Field(..., description="Il prompt da inviare a Gemini")
    history: list = Field(default_factory=list, description="Cronologia dei messaggi")
    skip_echo: bool = Field(default=False, description="Se True, evita di inviare l'echo del messaggio utente")

class ChatResponse(BaseModel):
    """Modello per le risposte di chat"""
    answer: str
    tool_name: str | None = None
    tool_data: list[dict] | dict | None = None

class SearchController:
    """Controller per gestire le operazioni di ricerca e chat"""
    
    def __init__(self):
        self.maps_service = GeminiMapsService()
        self.analyzer_service = AnalyzerService(self.maps_service)
        self.gemini_service = GeminiService(self.maps_service, self.analyzer_service)
        logger.info("SearchController inizializzato con successo")
    
    async def handle_chat_request_stream(self, chat_request: ChatRequest):
        """Gestisce una richiesta di chat in modalità streaming."""
        try:
            logger.info(f"Elaborazione richiesta chat (streaming): {chat_request.query}")
            
            # LOG PENULTIMO MESSAGGIO UTENTE (DEBUG)
            user_msgs = [m for m in chat_request.history if isinstance(m, dict) and m.get('role') == 'user']
           

            # In Programma di viaggio, chatMode deve essere sempre True
            if getattr(self.gemini_service, "programMode", True):
                self.gemini_service.chatMode = True
                logger.info("ProgramMode attivo: chatMode forzato a True")
            else:
                # Reset della modalità chatbot per ogni nuova sessione
                # Questo assicura che ogni prima richiesta esegua sempre la ricerca completa
                if not chat_request.history or len(chat_request.history) == 0:
                    self.gemini_service.chatMode = False
                    logger.info("Reset chatMode a False per nuova sessione")
                # Reset aggiuntivo: se la history contiene solo un messaggio utente, è una nuova sessione
                elif len(chat_request.history) == 1 and chat_request.history[0].get('role') == 'user':
                    self.gemini_service.chatMode = False
                    logger.info("Reset chatMode a False - rilevata nuova sessione con un solo messaggio utente")
            
            # Usa il metodo di streaming del servizio Gemini
            async for chunk in self.gemini_service.chat_stream(
                chat_request.query, 
                chat_request.history,
                skip_echo=chat_request.skip_echo
            ):
                yield chunk
            
        except Exception as e:
            logger.error(f"Errore durante lo streaming della richiesta: {e}", exc_info=True)
            # Fallback: genera "La nostra selezione" e "Altri suggerimenti" senza Gemini
            try:
                yield {"status": "Modalità fallback: suggerimenti locali senza AI."}
                frs = FilteringRankingService()
                # Categorie di default per la terza pagina (Hotel/Vini/Cucina tipica)
                default_queries = {
                    "hotel": "hotel",
                    "vini": "enoteca vini",
                    "cucina tipica": "cucina tipica"
                }
                ranked_results = await frs.filter_rank_and_present(default_queries, {}, chat_request.query)
                # Stream dei suggerimenti per compatibilità frontend
                yield {"map_payload": {"tool_name": "search_google_maps", "tool_data": ranked_results}}
                # Messaggio informativo minimale per la parte contenuti
                info_html = (
                    "<div class='travel-guide'><div class='intro'>"
                    "<h2 class='text-2xl font-bold text-slate-800 mb-2'>Suggerimenti locali</h2>"
                    "<p class='text-slate-700'>Contenuti AI non disponibili: mostra suggerimenti curati e selezione locale.</p>"
                    "</div></div>"
                )
                yield {"complete_html": info_html}
            except Exception as e2:
                logger.error(f"Errore nel fallback locale: {e2}", exc_info=True)
                error_message = {
                    "answer": (
                        "<div class=\"travel-guide\"><div class=\"intro\">"
                        "<h2 class=\"text-2xl font-bold text-slate-800 mb-4\">Errore</h2>"
                        "<p class=\"text-slate-700 mb-6\">Si è verificato un errore interno durante l'elaborazione della tua richiesta. Ci scusiamo per l'inconveniente.</p>"
                        "</div></div>"
                    ),
                    "tool_name": None,
                    "tool_data": None
                }
                yield error_message
    
    async def get_place_details(self, place_id: str) -> Dict[str, Any]:
        """Ottiene i dettagli di un luogo specifico"""
        try:
            logger.info(f"Recupero dettagli per place_id: {place_id}")
            return await self.maps_service.get_place_details(place_id)
        except Exception as e:
            logger.error(f"Errore nel recupero dettagli luogo: {e}", exc_info=True)
            return {"error": "Errore nel recupero dei dettagli del luogo"}