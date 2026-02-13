import logging
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from .controllers.search_controller import SearchController, ChatRequest
from .services.ChatterService import Chatter

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

class SearchRoutes:
    """Classe per gestire le route di ricerca in modo orientato agli oggetti"""
    
    def __init__(self):
        self.router = APIRouter()
        self.controller = None
        self._setup_routes()
        logger.info("SearchRoutes inizializzato con successo")
    
    def _setup_routes(self):
        """Configura le route dell'API"""
        self.router.post("/search")(self.search_endpoint)
        logger.info("Route configurate")
    
    def get_controller(self) -> SearchController:
        if self.controller is None:
            self.controller = SearchController()
        return self.controller

    async def search_endpoint(self, request: Request, chat_request: ChatRequest):
        """Endpoint per le richieste di ricerca e chat in streaming."""
        referer = request.headers.get("referer", "") or ""
        is_program_page = ("/program/" in referer)
        logger.info(f"Richiesta streaming ricevuta su /search: {chat_request.query} | referer='{referer}' program_mode={is_program_page}")
        try:
            controller = self.get_controller()
            controller.gemini_service.programMode = bool(is_program_page)
            if is_program_page:
                controller.gemini_service.chatMode = True
            
            # --- LOGICA SOSTITUZIONE QUERY SU 'RICARICO' ---
            # Recuperiamo l'istanza del bot attiva dal servizio Gemini
            chat_bot = getattr(controller.gemini_service, 'chatBot', None)
            
          
            # -----------------------------------------------

            logger.info(f"ProgramMode={controller.gemini_service.programMode} chatMode={controller.gemini_service.chatMode} referer='{referer}'")
        except Exception as e:
            logger.warning(f"Impostazione programMode/chatMode fallita: {e}")
        
        async def stream_generator():
            try:
                # Usa il metodo di streaming del controller
                # Verifichiamo se esiste ed è un'istanza di Chatter
                if chat_bot and isinstance(chat_bot, Chatter):
                    try:
                        logger.info(f"Verifica preventiva 'ricarico' per query: {chat_request.query}")
                        # Chiamiamo il metodo sull'istanza, passando la query dell'utente
                        bot_response = chat_bot.getResponse(chat_request.query)
                        logger.info(f"Risposta preventiva ChatterService: '{bot_response}'")
                        
                        if bot_response and "ricarico" in bot_response.lower().strip():
                            logger.info("ChatterService ha risposto 'ricarico'. Procedo alla sostituzione del messaggio.")
                            
                            # Helper per gestire sia dict che oggetti Pydantic
                            def get_role(m): return m.get('role') if isinstance(m, dict) else getattr(m, 'role', None)
                            def get_parts(m): return m.get('parts') if isinstance(m, dict) else getattr(m, 'parts', [])
                            
                            # Recupera i messaggi dell'utente dalla history
                            user_msgs = [m for m in chat_request.history if get_role(m) == 'user']
                            logger.info(f"Messaggi utente trovati: {len(user_msgs)}")
                            
                            # Se abbiamo almeno 2 messaggi (l'attuale + uno precedente)
                            if len(user_msgs) >= 2:
                                # Prende il penultimo messaggio (quello prima del reload/conferma)
                                penultimate = user_msgs[-2]
                                try:
                                    # Estrae il testo in modo sicuro
                                    parts = get_parts(penultimate)
                                    penultimate_text = ""
                                    
                                    if isinstance(parts, list) and len(parts) > 0:
                                        p0 = parts[0]
                                        penultimate_text = p0.get('text') if isinstance(p0, dict) else getattr(p0, 'text', str(p0))
                                    else:
                                        penultimate_text = str(parts)
                                        
                                    penultimate_text = str(penultimate_text or "").strip()
                                    
                                  
                                    logger.info(f"Sostituzione query: '{chat_request.query}' -> '{penultimate_text}'")
                                    chat_request.query = penultimate_text
                                    # Imposta flag per evitare echo duplicato del messaggio utente
                                    #
                                        
                                        # Forza reset chatMode a False per eseguire una nuova ricerca completa
                                        # invece di trattare la query sostituita come un messaggio di chat
                                        
                                   
                                    chat_request.skip_echo = True  
                                  
                                    logger.info("ChatMode forzato a False dopo sostituzione 'ricarico' per rigenerare il contenuto.")
                                    controller.gemini_service.chatMode = False
                                        # Flag per evitare duplicazione messaggio utente e risposta incoerente
                                except Exception as e:
                                    logger.error(f"Errore estrazione testo penultimo messaggio: {e}")
                            else:
                                logger.warning("Ricarico richiesto ma non ci sono abbastanza messaggi nella history.")
                                
                    except Exception as e:
                        logger.warning(f"Errore durante verifica ChatterService: {e}")

                async for chunk in self.get_controller().handle_chat_request_stream(chat_request):
                    yield json.dumps(chunk) + "\n"
            except Exception as e:
                logger.error(f"Errore nello stream generator: {e}", exc_info=True)
                error_payload = {
                    "detail": "Errore interno del server durante lo streaming"
                }
                yield json.dumps(error_payload) + "\n"

        return StreamingResponse(stream_generator(), media_type="text/plain")
    
    def get_router(self) -> APIRouter:
        """Restituisce il router configurato"""
        return self.router

# Istanza globale per compatibilità con il codice esistente
search_routes_instance = SearchRoutes()
router = search_routes_instance.get_router()

# Funzione per compatibilità con main.py
async def get_place_details(place_id: str):
    """Funzione di compatibilità per ottenere i dettagli di un luogo"""
    return await search_routes_instance.get_controller().get_place_details(place_id)

logger.info("Modulo search_routes_oop caricato con successo")