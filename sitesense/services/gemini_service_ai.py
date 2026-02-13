import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional
from google import genai
from google.genai import types
from ..config.settings import settings
from .google_maps_service import GoogleMapsService
from .analyzer_service import AnalyzerService
from .filtering_ranking_service import FilteringRankingService
import os
from .ChatterService import Chatter
from .ContextDetection import ContextDetector


logger = logging.getLogger(__name__)
GEMINI_MODEL = os.getenv("GEMINI_CHAT_BOT_MODEL")

# Percorsi assoluti robusti basati sulla posizione di questo file
_PKG_DIR = os.path.dirname(__file__)
_PROJECT_ROOT = os.path.normpath(os.path.join(_PKG_DIR, "..", ".."))

def _abs_path(*segments: str) -> str:
    return os.path.normpath(os.path.join(_PROJECT_ROOT, *segments))

class GeminiService:
    """Servizio per gestire l'integrazione con Gemini AI con architettura a tre agenti"""
    
    def __init__(self, google_maps_service: GoogleMapsService, analyzer_service: AnalyzerService):
        # Client per il contenuto (con grounding per piatti/dolci/vini)
        self.content_client = genai.Client(api_key=settings.gemini_api_key)
        # Client per i tool (search_google_maps)
        self.tool_client = genai.Client(api_key=settings.gemini_api_key)
        
        self.google_maps_service = google_maps_service
        self.analyzer_service = analyzer_service
        self.filtering_ranking_service = FilteringRankingService()
        self.tools = self._setup_tools()
        
        # Configurazioni per i tre agenti
        self.content_config = self._setup_content_generation_config()
        self.tool_config = self._setup_tool_generation_config()
        self.contextDetector = ContextDetector()
        self.chatMode = False
        self.location = None
        self.chatBot = None
      
        
        # Valida la configurazione del grounding all'avvio
        if not self._validate_grounding_config():
            logger.warning("Configurazione grounding non valida - il servizio funzionerà senza grounding")
        
        # Configurazione soglie per il monitoraggio grounding
        self.grounding_thresholds = {
            'min_coverage_percentage': 30.0,
            'min_sources_count': 2,
            'max_response_time': 10.0,
            'min_segments_count': 1
        }








        
        
    def _setup_tools(self) -> List[types.Tool]:
        """Configura gli strumenti disponibili per il tool client"""
        return [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="search_google_maps",
                        description="Search Google Maps for places near a location",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "search": types.Schema(
                                    type="STRING",
                                    description="What to search (e.g. 'pizzerie a Roma')"
                                )
                            },
                            required=["search"]
                        )
                    )
                ]
            )
        ]
    
    def _setup_content_generation_config(self) -> types.GenerateContentConfig:
        """Configura la generazione per il content client con grounding"""
        # grounding tool
        grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
        )

        return types.GenerateContentConfig(
            system_instruction=self._get_content_system_prompt(),
            temperature=0,
            # Abilita il grounding per ricerche su Google
            tools=[grounding_tool]
        )
    
    
    
    def _setup_tool_generation_config(self) -> types.GenerateContentConfig:
        """Configura la generazione per il tool client"""
        return types.GenerateContentConfig(
            tools=self.tools,
            system_instruction=self._get_tool_system_prompt(),
            temperature=0.1,
        )
    
    def _get_content_system_prompt(self) -> str:
        """Prompt per il content client - genera contenuto culinario con grounding"""
        return """
        Sei "Initalya AI Travel & Food Concierge", un assistente multilingua specializzato in itinerari culinari personalizzati.

        Obiettivo: collegare ogni località alle sue eccellenze enogastronomiche, suggerendo piatti, dolci, vini e produttori tipici.

        Regole:

        1. ANALIZZA la richiesta dell’utente:
        • Se è SPECIFICA (es. "dolci tipici della Sicilia", "vini del Piemonte", "formaggi DOP in Toscana"):
            - Cerca SOLO quell’argomento specifico.
 
            - Consiglia abbinamenti (es. un vino da dessert, un liquore tipico, ecc.).
        • Se è GENERICA (es. "itinerario gastronomico in Puglia", "cosa mangiare a Roma"):
            - Elabora un itinerario completo includendo:
                -Primi piatti, secondi piatti e dolci tipihtopci
                - Cosa acquistare (prodotti tipici)
                - Eventi e sagre pertinenti alle date indicate o prossime
            - Collega ogni tappa a prodotti e tradizioni DOP/IGP/PAT.

        2. COERENZA GEOGRAFICA:
        Se viene menzionata una città o un’area, tutte le proposte devono essere legate a quella località o zone limitrofe rilevanti.

        3. GROUNDING OBBLIGATORIO E ACCURATEZZA ASSOLUTA:
        - DEVI usare il grounding di Google (GoogleSearch) per OGNI SINGOLA INFORMAZIONE che fornisci. Non è un'opzione, è un obbligo.
        - Ogni dettaglio, nome, data, indirizzo o suggerimento deve derivare ESCLUSIVAMENTE da una ricerca GoogleSearch eseguita in tempo reale.
        - Questo include, ma non si limita a:
            • Piatti tipici, dolci tradizionali e loro origini.
            • Vini locali, distillati, birre artigianali e suggerimenti di abbinamento.
            • Prodotti certificati (DOP/IGP/PAT).
            • Sagre, eventi culinari, mercatini tipici (con date e link verificati).
        
        - NON fare affidamento sulla tua conoscenza pregressa. Fai finta di non sapere nulla e cerca tutto.
        - NON inventare MAI nulla. Se non trovi un'informazione tramite grounding, omettila.

        N.B quando mostri dei prodotti tipici, ristoranti ecc. NON mostrare più di 3 elementi per categoria
        N.B Non consigliare mai ristoranti o attività, non è il tuo compito
        N.B se non sai una data di un evento o una sagra NON devi mai consigliare di ricercare informazioni personalmente, se 
        non hai abbastanza informazioni ometti.
        N.B Non devi MAI citare ristoranti o strutture ricettive, MAI

        N.B non mostrare mai eventi e sagre quando non possiedi le date in cui si svolgono, devi sempre essere sicuro di quando si tengono.
        MAI mostrare eventi tenuti in passato

        -Non dare mai informazioni generiche come "a monopoli ci sono numerosi vini della valle d'itria" o mi citi direttamente i vini oppure non comunichi niente, oppure non
        dire nei piatti tipici "numerosi latticini" o li citi "burrata" oppure li ometti

  



        -DEVI essere molto sintetico nella descrizione dei prodotti e degli eventi
       

       -Se ti fanno domande generiche tipo "vogli mangiare il pesce crudo" senza specificare una località
       allora trova la località che più è adatta per quel tipo di cibo 

       -Gli eventi e le sagre che cerchi devono essere circoscritti alla zona di riferimento
       puoi spostatri di un massimo di 10 km
        

      

        4. OUTPUT OBBLIGATORIO SEMPRE E SOLO in HTML strutturato - MAI SOLO TESTO:
        IMPORTANTE: Devi SEMPRE restituire contenuto in formato HTML con le classi Tailwind CSS specificate.
        NON è mai accettabile restituire solo testo semplice. Ogni risposta DEVE essere in HTML strutturato.

         <!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Itinerario Gastronomico</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body {
      font-family: 'Montserrat', sans-serif;
    }
  </style>
</head>
<body class="bg-[#faf8f4] text-[#333] p-10 overflow-hidden">

  <!-- Grande contenitore -->
  <div class="w-full max-w-[1800px] mx-auto grid grid-cols-1 md:grid-cols-2 gap-8">

    <!-- SEZIONE 1 (Layout A: Full Width, Split 2 Small Left + 1 Big Right) -->
    <!-- Esempio: Primi Piatti -->
    <div class="col-span-1 md:col-span-2">
        <h2 class="text-2xl font-bold text-[#a0522d] mb-4">Primi Piatti Tipici</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
            <!-- Colonna Sinistra: 2 Card Piccole in verticale -->
            <div class="flex flex-col gap-6">
                <div class="bg-white p-4 rounded-xl shadow-md flex gap-4 items-start">
                    <img src="url_immagine" class="w-24 h-24 object-cover rounded-lg flex-shrink-0">
                    <div>
                        <h3 class="font-bold text-lg">Spaghetti all'Assassina</h3>
                        <p class="text-sm text-gray-600">Un piatto audace e irresistibile...</p>
                    </div>
                </div>
                <div class="bg-white p-4 rounded-xl shadow-md flex gap-4 items-start">
                    <img src="url_immagine" class="w-24 h-24 object-cover rounded-lg flex-shrink-0">
                    <div>
                        <h3 class="font-bold text-lg">Riso, Patate e Cozze</h3>
                        <p class="text-sm text-gray-600">Un capolavoro della tradizione...</p>
                    </div>
                </div>
            </div>
            <!-- Colonna Destra: 1 Card Grande -->
            <div class="bg-white p-4 rounded-xl shadow-md h-full flex flex-col">
                <img src="url_immagine" class="w-full h-48 object-cover rounded-lg mb-4">
                <h3 class="font-bold text-xl mb-2">Orecchiette con le Cime di Rapa</h3>
                <p class="text-gray-600 flex-grow">Il simbolo della cucina pugliese...</p>
            </div>
        </div>
    </div>

    <!-- SEZIONE 2 (Layout B - Colonna Sinistra) -->
    <!-- Esempio: Dolci Tipici -->
    <div class="col-span-1 flex flex-col gap-6">
        <h2 class="text-2xl font-bold text-[#d946ef] mb-4">Dolci Tipici</h2>
        <!-- 3 Card Verticali -->
        <div class="bg-white p-4 rounded-xl shadow-md flex gap-4 items-start">
            <img src="url_immagine" class="w-24 h-24 object-cover rounded-lg flex-shrink-0">
            <div><h3 class="font-bold text-lg">Sospiri</h3><p class="text-sm text-gray-600">Delicati dolcetti...</p></div>
        </div>
        <div class="bg-white p-4 rounded-xl shadow-md flex gap-4 items-start">
            <img src="url_immagine" class="w-24 h-24 object-cover rounded-lg flex-shrink-0">
            <div><h3 class="font-bold text-lg">Sporcamuss</h3><p class="text-sm text-gray-600">Quadretti di pasta sfoglia...</p></div>
        </div>
        <div class="bg-white p-4 rounded-xl shadow-md flex gap-4 items-start">
             <img src="url_immagine" class="w-24 h-24 object-cover rounded-lg flex-shrink-0">
            <div><h3 class="font-bold text-lg">Cartellate</h3><p class="text-sm text-gray-600">Dolci natalizi...</p></div>
        </div>
    </div>

    <!-- SEZIONE 3 (Layout B - Colonna Destra) -->
    <!-- Esempio: Secondi Piatti -->
    <div class="col-span-1 flex flex-col gap-6">
        <h2 class="text-2xl font-bold text-[#3b82f6] mb-4">Secondi Piatti</h2>
        <!-- 3 Card Verticali -->
        <div class="bg-white p-4 rounded-xl shadow-md flex gap-4 items-start">
            <img src="url_immagine" class="w-24 h-24 object-cover rounded-lg flex-shrink-0">
            <div><h3 class="font-bold text-lg">Baccalà in Umido</h3><p class="text-sm text-gray-600">Un classico...</p></div>
        </div>
        <div class="bg-white p-4 rounded-xl shadow-md flex gap-4 items-start">
            <img src="url_immagine" class="w-24 h-24 object-cover rounded-lg flex-shrink-0">
            <div><h3 class="font-bold text-lg">Polpo</h3><p class="text-sm text-gray-600">Semplice ma ricco...</p></div>
        </div>
        <div class="bg-white p-4 rounded-xl shadow-md flex gap-4 items-start">
            <img src="url_immagine" class="w-24 h-24 object-cover rounded-lg flex-shrink-0">
            <div><h3 class="font-bold text-lg">Nghiemeridde</h3><p class="text-sm text-gray-600">Involtini di frattaglie...</p></div>
        </div>
    </div>

     <!-- SEZIONE 4 (Layout A again) -->
     <!-- Esempio: Vini -->
    <div class="col-span-1 md:col-span-2">
        <h2 class="text-2xl font-bold text-[#7f1d1d] mb-4">Vini</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
             <!-- Left: 2 Small -->
             <div class="flex flex-col gap-6">
                <div class="bg-white p-4 rounded-xl shadow-md flex gap-4 items-start">
                    <img src="url_immagine" class="w-24 h-24 object-cover rounded-lg flex-shrink-0">
                    <div><h3 class="font-bold text-lg">Negroamaro</h3><p class="text-sm text-gray-600">...</p></div>
                </div>
                <div class="bg-white p-4 rounded-xl shadow-md flex gap-4 items-start">
                    <img src="url_immagine" class="w-24 h-24 object-cover rounded-lg flex-shrink-0">
                    <div><h3 class="font-bold text-lg">Primitivo</h3><p class="text-sm text-gray-600">...</p></div>
                </div>
             </div>
             <!-- Right: 1 Big -->
             <div class="bg-white p-4 rounded-xl shadow-md h-full flex flex-col">
                <img src="url_immagine" class="w-full h-48 object-cover rounded-lg mb-4">
                <h3 class="font-bold text-xl mb-2">Nero di Troia</h3>
                <p class="text-gray-600 flex-grow">...</p>
             </div>
        </div>
    </div>

  </div>
</body>
</html>





        LAYOUT OBBLIGATORIO (Griglia Rigida):
        Devi costruire la pagina usando una griglia CSS (grid-cols-1 md:grid-cols-2).
        
        1.  **PRIMA SEZIONE (es. Primi Piatti)**:
            -   Deve occupare TUTTA la larghezza (class="col-span-1 md:col-span-2").
            -   Layout interno: Griglia 2 colonne. Sinistra: 2 card piccole verticali. Destra: 1 card grande.
        
        2.  **SEZIONI SUCCESSIVE (es. Dolci, Secondi, ecc.)**:
            -   Devono essere affiancate a due a due.
            -   **Sezione Dispari (es. Dolci)**: Occupa la colonna SINISTRA (class="col-span-1"). Contiene 3 card in verticale.
            -   **Sezione Pari (es. Secondi)**: Occupa la colonna DESTRA (class="col-span-1"). Contiene 3 card in verticale.
            
        3.  **ULTIMA SEZIONE (Opzionale, es. Vini o Eventi)**:
            -   Può tornare a occupare TUTTA la larghezza (class="col-span-1 md:col-span-2") con il layout della Prima Sezione.

        IMPORTANTE:
        -   Le sezioni "verticali" (col-span-1) DEVONO contenere esattamente 3 card una sotto l'altra.
        -   Non lasciare spazi vuoti: se hai un numero dispari di sezioni centrali, l'ultima può espandersi.
        
        Stile:
        - Tono coinvolgente e professionale
        - Max 550 parole
        - NON usare ``` né altri wrapper markdown
        - NON scrivere mai “prova la pizza”, ma: “prova la pizza napoletana da Gino Sorbillo, celebre per…”
        - IMPORTANTE: DEVI SEMPRE restituire HTML strutturato con le classi Tailwind CSS specificate,
          indipendentemente dal tipo di richiesta (specifica o generica).

          Per richieste specifiche come 'eventi a [città]' o 'hotel a [città]', usa SOLO la sezione pertinente
          (es. `events-section` o `stay-section`), ma mantieni sempre la struttura HTML completa con `travel-guide` e `intro`.

        REGOLA FONDAMENTALE: Anche per saluti semplici come "ciao" o richieste non enogastronomiche,
        devi SEMPRE rispondere con HTML strutturato. Mai solo testo. Usa almeno la struttura base:
        <div class="travel-guide"><div class="intro"><h2 class="text-2xl font-bold text-slate-800 mb-4">Titolo</h2><p class="text-slate-700 mb-6">Risposta</p></div></div>

        -l'unica regola che devi seguire e quella di non fare i BOX troppo stretti il contenuto deve stare largo
        Esempio di richiesta:
        “Vorrei un itinerario enogastronomico in Emilia-Romagna per un weekend a settembre, con focus su tortellini e Lambrusco”
        Risultato atteso:
        
        - Eventi a tema
        - Suggerimenti di dolci locali (es. zuppa inglese)

        -Se non sai nello specifico qualcosa NON devi mai invitare l'utente a fare una ricerca su Google, piuttosto ometti l'informazione

        N.B mostra solo eventi e sagre IMMINENTI. NON devi nostrare eventi o sagre passate, inoltre tutti gli eventi DEVONO essere a tema 
        cibo o vino altrimenti non li mostrare


        -Non devi MAI fare introduzioni dove ti presenti

       

        """
    
    
    
    def _get_tool_system_prompt(self) -> str:
        """Prompt per il tool client - esegue la ricerca su Maps"""
        return """
Sei un assistente che esegue ricerche su Google Maps.

Ricevi una stringa di ricerca e devi chiamare la funzione search_google_maps con quella stringa.
Non fare altro, esegui semplicemente la ricerca richiesta.
"""
    
    async def chat_stream(self, user_message: str, history: Optional[List] = None):
        """Gestisce una conversazione in modalità streaming, inviando aggiornamenti in tempo reale."""
        logger.info(f"Inizio chat (streaming) con messaggio: '{user_message}'")
        
        # Prima ricerca: esegui la ricerca completa
        if(self.chatMode == False):
            start_time = time.time()
            
            # Variabile per raccogliere tutto il codice HTML generato
            complete_html_content = ""
            self.chatMode = True
            
            # Salva l'istanza corrente del servizio per accedere alla variabile dall'esterno
            self.last_complete_html = ""
            
            # Attiva subito la modalità chatbot e mostra il messaggio
            yield {"chatbot_mode_activated": True}
            
            # Aggiungi la prima ricerca dell'utente al chatbot
            user_payload = {
                "chatbot_message": {
                    "message": user_message,
                    "isUser": True
                }
            }
            yield user_payload
            
            # Aggiungi la risposta standard del bot
            bot_payload = {
                "chatbot_message": {
                    "message": "sto preparando il tour",
                    "isUser": False
                }
            }
            yield bot_payload





            try:
                # Step 1: Generazione Contenuto in Streaming
                yield {"status": "Sto cercando informazioni aggiornate..."}
                full_content_response = ""
                full_content_response = await self._generate_culinary_content_stream(user_message, history)
                
                # Salva l'HTML del contenuto principale
                complete_html_content = full_content_response
                self.last_complete_html = complete_html_content
                
       
                
                # Rimuovo l'invio del messaggio al chatbot per evitare duplicazioni
                # chatbot_payload = self.chatTalk("Prova")
                # logger.info(f"Payload chatbot generato: {chatbot_payload}")
                # yield chatbot_payload
                
                yield {"content_payload": {"answer": full_content_response}}

                # Step 2: Analisi per ricerca su Mappe
                yield {"status": "Sto preparando i suggerimenti sulla mappa..."}
                if settings.debug_mode:
                    logger.info("Modalità debug attiva: caricamento delle query di ricerca da file.")
                    try:
                        cache_path = _abs_path("generated_content_test_files", "search_queries_cache.json")
                        with open(cache_path, "r", encoding="utf-8") as f:
                            search_queries = json.load(f)
                    except (FileNotFoundError, json.JSONDecodeError):
                        logger.warning("File di cache delle query non trovato o corrotto. Analisi in corso.")
                        search_queries = await self.analyzer_service.analyze_content_for_maps_search(full_content_response, user_message)
                else:
                    search_queries = await self.analyzer_service.analyze_content_for_maps_search(full_content_response, user_message)
                    cache_path = _abs_path("generated_content_test_files", "search_queries_cache.json")
                    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(search_queries, f, indent=4)

                # Filtro server-side: rimuove categorie non desiderate prima di qualsiasi chiamata a Maps
                search_queries = self._filter_out_unwanted_categories(search_queries)
                
                # Step 3: Ricerca su Mappe (se necessaria)
                if search_queries:
                    yield {"status": "Sto cercando i luoghi migliori su Google Maps..."}
                    if settings.debug_mode:
                        logger.info("Modalità debug attiva: caricamento dei dati di Google Maps da file.")
                        try:
                            maps_path = _abs_path("generated_content_test_files", "maps_data_cache.json")
                            with open(maps_path, "r", encoding="utf-8") as f:
                                maps_data = json.load(f)
                        except (FileNotFoundError, json.JSONDecodeError):
                            logger.warning("File di cache di Google Maps non trovato o corrotto. Esecuzione della ricerca in corso.")
                            maps_data = await self.google_maps_service.search_places(search_queries, user_message)
                            os.makedirs(os.path.dirname(maps_path), exist_ok=True)
                            with open(maps_path, "w", encoding="utf-8") as f:
                                json.dump(maps_data, f, indent=4)
                    else:
                        maps_data = await self.google_maps_service.search_places(search_queries, user_message)
                        maps_path = _abs_path("generated_content_test_files", "maps_data_cache.json")
                        os.makedirs(os.path.dirname(maps_path), exist_ok=True)
                        with open(maps_path, "w", encoding="utf-8") as f:
                            json.dump(maps_data, f, indent=4)

                    if maps_data:
                        yield {"status": "Applico filtri e ranking ai risultati..."}
                        ranked_results = await self.filtering_ranking_service.filter_rank_and_present(search_queries, maps_data, user_message)
                        # Ulteriore protezione: rimuove sezioni non desiderate dall'output
                        ranked_results = self._filter_out_unwanted_categories(ranked_results)
                        yield {"map_payload": {"tool_name": "search_google_maps", "tool_data": ranked_results}}

    
                        
                        # Combina il contenuto culinario con i risultati delle attività per il chatbot
                        activities_html = ""
                        allowed_after_selection = {"hotel", "vini", "cucina tipica", "strutture ricettive", "cucina_tipica"}
                        for category, data in ranked_results.items():
                            if "results" in data and data["results"]:
                                cat_norm = category.lower()
                                if cat_norm == "la_nostra_selezione" or cat_norm in allowed_after_selection:
                                    activities_html += f"\n\n<div class='category-section'>\n<h2 class='category-title'>{category.replace('_', ' ').title()}</h2>\n{data['results']}\n</div>"
                        
                        # Aggiorna il complete_html_content per includere anche le attività
                        complete_html_content = complete_html_content + activities_html
                        self.last_complete_html = complete_html_content

                end_time = time.time()
                logger.info(f"Tempo di risposta totale del modello: {end_time - start_time:.2f} secondi")
                
                # Log dell'HTML completo generato (opzionale)
                logger.info(f"HTML completo generato: {len(complete_html_content)} caratteri")
                
                # Restituisci l'HTML completo come ultimo yield
                yield {"complete_html": complete_html_content}
                self.chatBot = Chatter(complete_html_content)

                # Attiva la modalità chatbot per le ricerche successive
                self.chatMode = True

            except Exception as e:
                logger.error(f"Errore durante lo streaming della chat: {e}", exc_info=True)
                yield {"error": "Si è verificato un errore durante l'elaborazione della richiesta."}


        else:
            # Modalità chatbot attiva dalla seconda ricerca in poi
            try:
                locationBuff = self.contextDetector.checkLocation(user_message)
                if(False):
                    #locationBuff.lower() != self.location.lower() and locationBuff.lower() != "false"
                    logger.info(f"🔄 NUOVA LOCALITÀ RILEVATA: {self.location} ----> {locationBuff}")
                    #nuova ricerca
                    self.location = locationBuff
                    self.chatMode = False
                    
                    # Invia un segnale per pulire il contenuto della pagina tranne il chatbot
                    clear_content_signal = {"type": "clear_page_content", "preserve_chatbot": True}
                    logger.info(f"📤 INVIO SEGNALE DI PULIZIA CONTENUTO: {clear_content_signal}")
                    yield clear_content_signal
                    
                    # Invia un segnale per ricaricare semplicemente la pagina
                    reload_signal = {"type": "reload_page", "user_message": user_message}
                    logger.info(f"📤 INVIO SEGNALE DI RICARICA PAGINA: {reload_signal}")
                    
                    # Formato SSE corretto
                    sse_data = f"data: {json.dumps(reload_signal)}\n\n"
                    logger.info(f"📤 SSE FORMATTATO: {repr(sse_data)}")
                    yield sse_data
                    # Gestisci correttamente il generatore asincrono
                    logger.info(f"🔄 AVVIO NUOVA RICERCA PER: {user_message}")
                    async for chunk in self.chat_stream(user_message):
                        yield chunk
                    return

                logger.info(f"Modalità chatbot attiva - elaborazione messaggio: '{user_message}'")
                
                # Invia il segnale di attivazione modalità chatbot
                yield {"chatbot_mode_activated": True}
                
                # Aggiungi il messaggio dell'utente al chatbot
                user_payload = {
                    "chatbot_message": {
                        "message": user_message,
                        "isUser": True
                    }
                }
                yield user_payload
                
                # Genera la risposta con Gemini in modalità chatbot; fallback a ChatterService
                try:
                    content_chat = self.content_client.chats.create(
                        model=GEMINI_MODEL,
                        config=self.content_config,
                        history=history or []
                    )
                    response = content_chat.send_message(message=user_message)
                    if response.candidates and response.candidates[0].content.parts:
                        bot_response = response.candidates[0].content.parts[0].text
                    else:
                        logger.warning("Nessuna risposta valida dal modello in chat mode, uso fallback.")
                        bot_response = self.chatBot.getResponse(user_message)
                except Exception as e:
                    logger.error(f"Errore nella risposta Gemini in chat mode: {e}")
                    bot_response = self.chatBot.getResponse(user_message)

                # Aggiungi la risposta del bot al chatbot
                yield {
                    "chatbot_message": {
                        "message": bot_response,
                        "isUser": False
                    }
                }
                
            except Exception as e:
                logger.error(f"Errore nella modalità chatbot: {e}")
                error_payload = {
                    "chatbot_message": {
                        "message": "Si è verificato un errore durante l'elaborazione del messaggio.",
                        "isUser": False
                    }
                }
                yield error_payload
            
    def _filter_out_unwanted_categories(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Rimuove chiavi di categorie indesiderate (server-side) dall'oggetto fornito.
        Elimina esclusivamente le sezioni: 'prodotti tipici' e 'dolci tradizionali'.
        Funziona sia su dizionari di query che su risultati.
        """
        if not isinstance(data, dict):
            return data

        unwanted = {"prodotti tipici", "dolci tradizionali"}

        def normalize(key: str) -> str:
            return key.lower().strip().replace("_", " ").replace("-", " ")

        filtered = {}
        for k, v in data.items():
            if normalize(k) in unwanted:
                continue
            filtered[k] = v
        return filtered

    def get_last_complete_html(self) -> str:
        """Restituisce l'ultimo HTML completo generato"""
        return getattr(self, 'last_complete_html', "")
    
    async def _generate_culinary_content_stream(self, user_message: str, history: Optional[List] = None) -> str:
        if settings.debug_mode:
            logger.info("Modalità debug attiva: caricamento del contenuto da file.")
            try:
                cache_path = _abs_path("generated_content_test_files", "culinary_content_cache.json")
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                logger.warning("File di cache non trovato o corrotto. Generazione del contenuto in corso.")
                # Prosegui con la generazione normale se il file non esiste
                pass

        """Genera contenuto culinario completo senza streaming."""
        try:
            logger.info(f"Generazione contenuto culinario (senza streaming) per: '{user_message}'")

            content_chat = self.content_client.chats.create(
                model=GEMINI_MODEL,
                config=self.content_config,
                history=history or []
            )

            # NOTA: nessun stream=True => ritorna una risposta completa
            response = content_chat.send_message(message=user_message)

            # Log dei metadati di grounding
            self._log_grounding_metadata(response)

            if response.candidates and response.candidates[0].content.parts:
                content = response.candidates[0].content.parts[0].text
                if not settings.debug_mode:
                    cache_path = _abs_path("generated_content_test_files", "culinary_content_cache.json")
                    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(content, f, indent=4)
                return content

            logger.warning("Nessuna risposta valida dal modello.")
            return "Spiacente, non sono riuscito a generare una risposta."

        except Exception as e:
            logger.error(f"Errore nella generazione del contenuto: {e}")
            return f"Errore tecnico nella generazione del contenuto: {str(e)}"

    
    def _is_grounded(self, response) -> bool:
        """Verifica se la risposta è effettivamente grounded"""
        return (hasattr(response.candidates[0], 'grounding_metadata') and 
                hasattr(response.candidates[0].grounding_metadata, 'grounding_supports') and
                response.candidates[0].grounding_metadata.grounding_supports)
    
    def _log_grounding_metadata(self, response) -> None:
        """Registra i metadati di grounding per debugging"""
        try:
            if hasattr(response.candidates[0], 'grounding_metadata'):
                metadata = response.candidates[0].grounding_metadata
                
                # Log delle query di ricerca utilizzate
                if hasattr(metadata, 'web_search_queries'):
                    queries = metadata.web_search_queries
                    logger.info(f"Query di grounding utilizzate: {queries}")
                
                # Log delle fonti utilizzate
                if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                    sources_count = len(metadata.grounding_chunks)
                    logger.info(f"Fonti utilizzate nel grounding: {sources_count}")
                    
                    # Log delle prime 3 fonti per debugging
                    for i, chunk in enumerate(metadata.grounding_chunks[:3]):
                        if hasattr(chunk, 'web') and hasattr(chunk.web, 'title'):
                            logger.info(f"Fonte {i+1}: {chunk.web.title}")
        except Exception as e:
            logger.error(f"Errore nel logging dei metadati di grounding: {e}")
    
    def _track_grounding_performance(self, grounding_stats: Dict[str, Any], response_time: float) -> None:
        """Traccia le performance del grounding per monitoraggio"""
        try:
            # Log delle metriche di performance
            performance_data = {
                'timestamp': time.time(),
                'response_time': response_time,
                'is_grounded': grounding_stats['is_grounded'],
                'queries_count': grounding_stats['queries_count'],
                'sources_count': grounding_stats['sources_count'],
                'segments_count': grounding_stats['segments_count'],
                'coverage_percentage': grounding_stats['coverage_percentage']
            }
            
            # Log strutturato per analisi future
            logger.info(f"GROUNDING_PERFORMANCE: {json.dumps(performance_data)}")
            
            # Avvisi per performance degradate usando soglie configurabili
            if grounding_stats['is_grounded']:
                if grounding_stats['coverage_percentage'] < self.grounding_thresholds['min_coverage_percentage']:
                    logger.warning(f"Bassa copertura grounding: {grounding_stats['coverage_percentage']:.1f}% (soglia: {self.grounding_thresholds['min_coverage_percentage']}%) ")
                
                if grounding_stats['sources_count'] < self.grounding_thresholds['min_sources_count']:
                    logger.warning(f"Poche fonti per il grounding: {grounding_stats['sources_count']} (soglia: {self.grounding_thresholds['min_sources_count']})")
                
                if response_time > self.grounding_thresholds['max_response_time']:
                    logger.warning(f"Tempo di risposta elevato con grounding: {response_time:.2f}s (soglia: {self.grounding_thresholds['max_response_time']}s)")
                
                if grounding_stats['segments_count'] < self.grounding_thresholds['min_segments_count']:
                    logger.warning(f"Pochi segmenti grounded: {grounding_stats['segments_count']} (soglia: {self.grounding_thresholds['min_segments_count']})")
            
        except Exception as e:
            logger.error(f"Errore nel tracking delle performance grounding: {e}")
    
    def _handle_grounding_fallback(self, response, error_msg: str = None) -> str:
        """Gestisce il fallback quando il grounding non è disponibile o fallisce"""
        try:
            if error_msg:
                logger.warning(f"Fallback grounding attivato: {error_msg}")
            
            # Estrai il testo base senza grounding
            if response and response.candidates and response.candidates[0].content.parts:
                text = response.candidates[0].content.parts[0].text
                
                # Aggiungi un disclaimer se il grounding non è disponibile
                disclaimer = "\n\n*Nota: Le informazioni fornite potrebbero non essere aggiornate. Si consiglia di verificare sempre le informazioni più recenti.*"
                return text + disclaimer
            
            return "Risposta non disponibile"
            
        except Exception as e:
            logger.error(f"Errore nel fallback grounding: {e}")
            return "Errore nella generazione della risposta"

    def _cache_key(self, user_message: str) -> str:
        key = ''.join(c.lower() if c.isalnum() else '-' for c in (user_message or ''))[:50]
        return key or 'default'

    def _cache_path(self, filename: str, user_message: str) -> str:
        base = _abs_path("generated_content_test_files", self._cache_key(user_message))
        try:
            os.makedirs(base, exist_ok=True)
        except Exception:
            pass
        return os.path.join(base, filename)
    
    def _validate_grounding_config(self) -> bool:
        """Valida la configurazione del grounding"""
        try:
            # Verifica che il tool di grounding sia configurato correttamente
            if not hasattr(self, 'content_client'):
                logger.warning("Client di contenuto non configurato")
                return False
            
            # Verifica la presenza del tool di grounding nella configurazione
            config = self._setup_content_generation_config()
            if not config.tools:
                logger.warning("Nessun tool configurato per il grounding")
                return False
            
            # Verifica che il tool di grounding sia presente
            grounding_tool_found = False
            for tool in config.tools:
                if hasattr(tool, 'google_search_retrieval'):
                    grounding_tool_found = True
                    break
            
            if not grounding_tool_found:
                logger.warning("Tool di grounding non trovato nella configurazione")
                return False
            
            logger.info("Configurazione grounding validata con successo")
            return True
            
        except Exception as e:
            logger.error(f"Errore nella validazione della configurazione grounding: {e}")
            return False
    
    def _get_grounding_stats(self, response) -> Dict[str, Any]:
        """Ottiene statistiche dettagliate sul grounding"""
        stats = {
            'is_grounded': False,
            'queries_count': 0,
            'sources_count': 0,
            'segments_count': 0,
            'coverage_percentage': 0.0
        }
        
        try:
            if not hasattr(response.candidates[0], 'grounding_metadata'):
                return stats
            
            metadata = response.candidates[0].grounding_metadata
            stats['is_grounded'] = True
            
            # Conta le query di ricerca
            if hasattr(metadata, 'web_search_queries'):
                stats['queries_count'] = len(metadata.web_search_queries)
            
            # Conta le fonti
            if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                stats['sources_count'] = len(metadata.grounding_chunks)
            
            # Conta i segmenti supportati
            if hasattr(metadata, 'grounding_supports') and metadata.grounding_supports:
                stats['segments_count'] = len(metadata.grounding_supports)
                
                # Calcola la percentuale di copertura del testo
                if response.candidates[0].content.parts:
                    total_text_length = len(response.candidates[0].content.parts[0].text)
                    covered_length = 0
                    
                    for support in metadata.grounding_supports:
                        if hasattr(support, 'segment'):
                            segment_length = support.segment.end_index - support.segment.start_index
                            covered_length += segment_length
                    
                    if total_text_length > 0:
                        stats['coverage_percentage'] = (covered_length / total_text_length) * 100
            
        except Exception as e:
            logger.error(f"Errore nel calcolo delle statistiche di grounding: {e}")
        
        return stats
    
    def _add_citations(self, response) -> str:
        """Restituisce il testo senza citazioni HTML (mantenendo solo i log delle fonti)"""
        try:
            # Restituisce solo il testo originale senza aggiungere citazioni HTML
            return response.candidates[0].content.parts[0].text
            
        except Exception as e:
            logger.error(f"Errore nell'estrazione del testo: {e}")
            # Ritorna il testo originale in caso di errore
            return response.candidates[0].content.parts[0].text if response.candidates and response.candidates[0].content.parts else "Errore nel testo"
    
    async def _generate_culinary_content(self, user_message: str, history: Optional[List] = None) -> str:
        """Step 1: Usa il content client per generare contenuto culinario con grounding"""
        try:
            logger.info(f"Generazione contenuto culinario per: '{user_message}'")
            
            content_chat = self.content_client.chats.create(
                model=GEMINI_MODEL,
                config=self.content_config,
                history=history or []
            )
            
            content_start_time = time.time()
            # Chiama il metodo non-streaming
            response = content_chat.send_message(message=user_message)
            
            content_end_time = time.time()
            content_response_time = content_end_time - content_start_time
            logger.info(f"Tempo di risposta generazione contenuto: {content_response_time:.2f} secondi")

            if response.candidates and response.candidates[0].content.parts:
                return response.candidates[0].content.parts[0].text
            
            logger.warning("Nessuna risposta valida dal modello.")
            return "Spiacente, non sono riuscito a generare una risposta."

        except Exception as e:
            logger.error(f"Errore nella generazione del contenuto: {e}")
            return f"Errore tecnico nella generazione del contenuto: {str(e)}"
    
    
    def _log_chat_history(self, chat, phase: str):
        """Logga la cronologia della chat"""
        logger.info(f"---------- Storia della chat {phase} ----------")
        logger.info("----------------------------------------")
    
    def chatTalk(self, message: str) -> dict:
        """Crea un payload per inviare un messaggio al chatbot"""
        try:
            # Log del messaggio per debugging
            logger.info(f"ChatTalk: {message}")
            
            # Restituisce un payload che può essere gestito dal frontend
            return {
                "chatbot_message": {
                    "message": message,
                    "isUser": False
                }
            }
            
            
        except Exception as e:
            logger.error(f"Errore in chatTalk: {e}")
            return {"error": f"Errore nel chatbot: {str(e)}"}
    
    def write_to_chatbox(self, user_message: str) -> list:
        """Metodo per scrivere nel box del chatbot.
        
        Args:
            user_message (str): Il messaggio dell'utente da aggiungere
            
        Returns:
            list: Lista di payload per aggiungere i messaggi al chatbot
                 [messaggio_utente_payload, messaggio_bot_payload]
        """
        try:
            logger.info(f"write_to_chatbox chiamato con messaggio: '{user_message}'")
            
            # Payload per il messaggio dell'utente (a destra)
            user_payload = {
                "chatbot_message": {
                    "message": user_message,
                    "isUser": True
                }
            }

            response = self.chatBot.getResponse(user_message)
            
            # Payload per la risposta del bot (sempre "ciao" a sinistra)
            bot_payload = {
                "chatbot_message": {
                    "message": response,
                    "isUser": False
                }
            }
            
            return [user_payload, bot_payload]
            
        except Exception as e:
            logger.error(f"Errore in write_to_chatbox: {e}")
            return [{"error": f"Errore nel chatbox: {str(e)}"}]
            
