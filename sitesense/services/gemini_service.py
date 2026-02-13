import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional
from google import genai
from google.genai import types
from ..config.settings import settings
from .gemini_maps import GeminiMapsService
from .analyzer_service import AnalyzerService
from .filtering_ranking_service import FilteringRankingService
import os
from .ChatterService import Chatter
from .program_service import ProgramService
from .ContextDetection import ContextDetector


logger = logging.getLogger(__name__)
GEMINI_MODEL = os.getenv("GEMINI_CHAT_BOT_MODEL")

class GeminiService:
    """Servizio per gestire l'integrazione con Gemini AI con architettura a tre agenti"""
    
    def __init__(self, gemini_maps: GeminiMapsService, analyzer_service: AnalyzerService):
        # Client per il contenuto (con grounding per piatti/dolci/vini)
        self.content_client = genai.Client(api_key=settings.gemini_api_key)
        # Client per i tool (search_google_maps)
        self.tool_client = genai.Client(api_key=settings.gemini_api_key)
        
        self.gemini_maps = gemini_maps
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
        self.programMode = False

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

        Obiettivo: collegare ogni località alle sue eccellenze enogastronomiche, suggerendo piatti, dolci, vini locali e produttori tipici.

        Regole:

        1. ANALIZZA la richiesta dell’utente:
        • Se è SPECIFICA (es. "dolci tipici della Sicilia", "vini del Piemonte", "formaggi DOP in Toscana"):
            - Cerca SOLO quell’argomento specifico.
 
            - Consiglia abbinamenti (es. un vino da dessert, un liquore tipico, ecc.).
        • Se è GENERICA (es. "itinerario gastronomico in Puglia", "cosa mangiare a Roma"):
            - Elabora un itinerario completo includendo:
                -Primi piatti, secondi piatti e dolci tipici
                - Vini locali
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
        Regola immagini: usa SEMPRE l'endpoint /image_search_cse con il parametro 'dish='. Non usare mai 'wine', 'product', 'event' o 'city' con /image_search_cse.
        Per foto città usa esclusivamente /city_image_cse?city=NomeCitta.

        
        <!DOCTYPE html>
        <html lang="it">
<head>
  <meta charset="UTF-8">
  <title>Itinerario Gastronomico</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">

  <!-- Tailwind CDN -->
  <script src="https://cdn.tailwindcss.com"></script>

  <!-- Font -->
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">

  <script>
    tailwind.config = {
      theme: {
        extend: {
          fontFamily: {
            sans: ['Montserrat', 'sans-serif'],
          },
        }
      }
    }
  </script>
</head>

<body class="font-sans bg-[#f3fdf9] text-[#333] overflow-x-hidden">




  <style>
 @media (max-width: 558px) {

      /* ===== GENERALE (SOLO per le sezioni interne, NO Hero) ===== */
      .mb-12 h2, .pb-12 h2 { font-size: 1.15rem; }
      .mb-12 h3, .pb-12 h3 { font-size: 0.95rem; }
      .mb-12 p, .pb-12 p { font-size: 0.82rem; line-height: 1.4; }

      .mb-12, .pb-12 { margin-bottom: 2.2rem; }

      /* Riduzione padding card per immagini più aderenti */
      .mb-12 .bg-white, .pb-12 .bg-white {
        padding: 0.5rem !important;
      }
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        
      /* ===== PRIMI PIATTI & VINI ===== */
      section.mb-12 > .lg\:grid-cols-2,
      section.pb-12 > .lg\:grid-cols-2 { grid-template-columns: 1fr !important; }

      section.mb-12 > .lg\:grid-cols-2 > div:first-child,
      section.pb-12 > .lg\:grid-cols-2 > div:first-child {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 0.6rem;
      }

      section.mb-12 > .lg\:grid-cols-2 > div:first-child img,
      section.pb-12 > .lg\:grid-cols-2 > div:first-child img {
        height: 120px !important;
        width: 100% !important;
        min-width: 100% !important;
      }

      section.mb-12 > .lg\:grid-cols-2 > div:last-child,
      section.pb-12 > .lg\:grid-cols-2 > div:last-child {
        margin-top: 0.7rem;
      }

      section.mb-12 > .lg\:grid-cols-2 > div:last-child img,
      section.pb-12 > .lg\:grid-cols-2 > div:last-child img {
        height: 210px !important;
      }

      /* ===== DOLCI + SECONDI (FIX DEFINITIVO) ===== */
      section.grid.grid-cols-1.lg\:grid-cols-2 {
        display: grid !important;
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 0.8rem;
        align-items: start;
      }

      /* colonne */
      section.grid.grid-cols-1.lg\:grid-cols-2 > div {
        display: flex;
        flex-direction: column;
        gap: 0.8rem;
      }

      /* card verticali */
      section.grid.grid-cols-1.lg\:grid-cols-2 .bg-white {
        display: flex;
        flex-direction: column !important;
        padding: 0.5rem !important;
      }

      /* immagini card */
      section.grid.grid-cols-1.lg\:grid-cols-2 img {
        width: 100% !important;
        min-width: 100% !important;
        height: 120px !important;
        object-fit: cover;
        border-radius: 12px;
      }

      /* testo limitato */
      section.grid.grid-cols-1.lg\:grid-cols-2 p {
        font-size: 0.8rem;
        line-height: 1.35;
        display: -webkit-box;
        -webkit-line-clamp: 4;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }
      
      section.grid.grid-cols-1.lg\:grid-cols-2 > div {
        margin-top: 0 !important;
        padding-top: 0 !important;
      }

      /* ===== FIX FLEX ===== */
      .flex.sm\:flex-row {
        flex-direction: column;
      }
    }
</style>










<div class="max-w-[1800px] mx-auto pr-4 pl-8">

  <!-- ================= HERO ================= -->
  <section class="py-6">
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">

      <div class="-mt-8">
        <h1 class="text-3xl lg:text-4xl font-bold mb-4">
          Scopri i Sapori<br>Autentici di Bari
        </h1>
        <p class="text-base text-[#4b5a56] max-w-xl leading-relaxed">
          Affacciata sul blu dell’Adriatico, Bari è un vero scrigno di tradizioni
          culinarie. Qui ogni piatto racconta una storia fatta di passione,
          ingredienti genuini e gesti tramandati da generazioni.
        </p>
      </div>

      <div class="w-full h-[260px] lg:h-[320px] rounded-[20px] overflow-hidden shadow-md">
        <img src="/city_image_cse?city=Bari" alt="Panorama di Bari" class="w-full h-full object-cover">
      </div>

    </div>
  </section>

  <!-- ================= PRIMI PIATTI ================= -->
  <section class="mb-12">
    <h2 class="text-[1.4rem] font-bold mb-4 text-yellow-500">
      Primi Piatti Tipici
    </h2>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

      <!-- LEFT -->
      <div class="flex flex-col gap-6">

        <!-- CARD -->
        <div class="bg-white rounded-[18px] shadow-md p-4
                    flex flex-col sm:flex-row gap-4">

           <img src="/image_search_cse?dish=Spaghetti%20all%27Assassina&city=Bari"
               class="w-[260px] min-w-[260px] h-[220px] object-cover rounded-[14px] flex-shrink-0">

          <div class="flex flex-col justify-center w-full">
            <h3 class="text-lg font-bold mb-2">Spaghetti all'Assassina</h3>
            <p class="text-[0.95rem] text-[#4b5a56]">
              Un piatto audace e irresistibile. Gli spaghetti vengono cotti direttamente in padella....(testo di 180 caratteri)
            </p>
          </div>
        </div>

        <!-- CARD -->
        <div class="bg-white rounded-[18px] shadow-md p-4
                    flex flex-col sm:flex-row gap-4">

           <img src="/image_search_cse?dish=Spaghetti%20all%27Assassina&city=Bari"
               class="w-[260px] min-w-[260px] h-[220px] object-cover rounded-[14px] flex-shrink-0">

          <div class="flex flex-col justify-center w-full">
            <h3 class="text-lg font-bold mb-2">Riso, Patate e Cozze</h3>
            <p class="text-[0.95rem] text-[#4b5a56]">
              Un capolavoro della tradizione barese, ricco di profumi e sapori....(testo di 180 caratteri)
            </p>
          </div>
        </div>

      </div>

      <!-- RIGHT BIG -->
      <div class="bg-white rounded-[18px] shadow-md p-4 flex flex-col">
         <img src="/image_search_cse?dish=Spaghetti%20all%27Assassina&city=Bari"
             class="w-full h-[260px] sm:h-[320px] object-cover rounded-[14px] mb-4">
        <h3 class="text-lg font-bold mb-2">Orecchiette con le Cime di Rapa</h3>
        <p class="text-[0.95rem] text-[#4b5a56]">
          Il simbolo della cucina pugliese: pasta fresca fatta a mano con cime di rapa........(testo di circa 350 caratteri)
        </p>
      </div>

    </div>
  </section>

  <!-- ================= DOLCI & SECONDI ================= -->
  <section class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-12">

    <!-- DOLCI -->
    <div class="flex flex-col gap-6">
      <h2 class="text-[1.4rem] font-bold text-red-500">Dolci Tipici</h2>

      <!-- CARD -->
      <div class="bg-white rounded-[18px] shadow-md p-4
                  flex flex-col sm:flex-row gap-4">
         <img src="/image_search_cse?dish=Spaghetti%20all%27Assassina&city=Bari"
             class="w-[260px] min-w-[260px] h-[220px] object-cover rounded-[14px] flex-shrink-0">
        <div class="flex flex-col justify-center w-full">
          <h3 class="text-lg font-bold">Sospiri</h3>
          <p class="text-[0.95rem] text-[#4b5a56]">Delicati dolcetti tipici della provincia di Bari.......(testo di 180 caratteri)</p>
        </div>
      </div>

      <div class="bg-white rounded-[18px] shadow-md p-4
                  flex flex-col sm:flex-row gap-4">
         <img src="/image_search_cse?dish=Spaghetti%20all%27Assassina&city=Bari"
             class="w-[260px] min-w-[260px] h-[220px] object-cover rounded-[14px] flex-shrink-0">
        <div class="flex flex-col justify-center w-full">
          <h3 class="text-lg font-bold">Sporcamuss</h3>
          <p class="text-[0.95rem] text-[#4b5a56]">Pasta sfoglia calda ripiena di crema........(testo di 180 caratteri)</p>
        </div>
      </div>
    </div>

    <!-- SECONDI -->
    <div class="flex flex-col gap-6">
      <h2 class="text-[1.4rem] font-bold text-blue-500">Secondi Piatti</h2>

      <div class="bg-white rounded-[18px] shadow-md p-4
                  flex flex-col sm:flex-row gap-4">
         <img src="/image_search_cse?dish=Spaghetti%20all%27Assassina&city=Bari"
             class="w-[260px] min-w-[260px] h-[220px] object-cover rounded-[14px] flex-shrink-0">
        <div class="flex flex-col justify-center w-full">
          <h3 class="text-lg font-bold">Baccalà in Umido</h3>
          <p class="text-[0.95rem] text-[#4b5a56]">Un classico della cucina di pesce barese.......(testo di 180 caratteri)</p>
        </div>
      </div>

      <div class="bg-white rounded-[18px] shadow-md p-4
                  flex flex-col sm:flex-row gap-4">
         <img src="/image_search_cse?dish=Spaghetti%20all%27Assassina&city=Bari"
             class="w-[260px] min-w-[260px] h-[220px] object-cover rounded-[14px] flex-shrink-0">
        <div class="flex flex-col justify-center w-full">
          <h3 class="text-lg font-bold">Polpo</h3>
          <p class="text-[0.95rem] text-[#4b5a56]">Semplice ma ricco di gusto.......(testo di 180 caratteri)</p>
        </div>
      </div>
    </div>

  </section>

  <!-- ================= VINI LOCALI================= -->
  <section class="pb-12">
    <h2 class="text-[1.4rem] font-bold mb-4">Vini Locali</h2>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

      <div class="flex flex-col gap-6">

        <div class="bg-white rounded-[18px] shadow-md p-4
                    flex flex-col sm:flex-row gap-4">
           <img src="/image_search_cse?dish=Spaghetti%20all%27Assassina&city=Bari"
               class="w-[260px] min-w-[260px] h-[220px] object-cover rounded-[14px] flex-shrink-0">
          <div class="flex flex-col justify-center w-full">
            <h3 class="text-lg font-bold">Negroamaro</h3>
            <p class="text-[0.95rem] text-[#4b5a56]">Vino rosso corposo e intenso.......(testo di 180 caratteri)</p>
          </div>
        </div>

        <div class="bg-white rounded-[18px] shadow-md p-4
                    flex flex-col sm:flex-row gap-4">
           <img src="/image_search_cse?dish=Spaghetti%20all%27Assassina&city=Bari"
               class="w-[260px] min-w-[260px] h-[220px] object-cover rounded-[14px] flex-shrink-0">
          <div class="flex flex-col justify-center w-full">
            <h3 class="text-lg font-bold">Primitivo</h3>
            <p class="text-[0.95rem] text-[#4b5a56]">Ricco e potente, con note di frutta rossa.......(testo di 180 caratteri)</p>
          </div>
        </div>

      </div>

      <div class="bg-white rounded-[18px] shadow-md p-4 flex flex-col">
         <img src="/image_search_cse?dish=Spaghetti%20all%27Assassina&city=Bari"
             class="w-full h-[260px] sm:h-[320px] object-cover rounded-[14px] mb-4">
        <h3 class="text-lg font-bold mb-2">Nero di Troia</h3>
        <p class="text-[0.95rem] text-[#4b5a56]">
          Uno dei vini più eleganti e strutturati della Puglia.......(testo di 350 caratteri)
        </p>
      </div>

    </div>
  </section>

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
            
        3.  **ULTIMA SEZIONE (Vini Locali)**:
            -   Può tornare a occupare TUTTA la larghezza (class="col-span-1 md:col-span-2") con il layout della Prima Sezione.

       

        4. **IMMAGINE PRINCIPALE DELLA CITTÀ (HERO)**:
            - L'immagine grande nella sezione HERO deve SEMPRE usare come src un endpoint nel formato `/city_image_cse?city=<NOME_CITTÀ>`.
           

        IMPORTANTE:
        -   Le sezioni "verticali" (col-span-1) DEVONO contenere esattamente 3 card una sotto l'altra.
        -   Non lasciare spazi vuoti: se hai un numero dispari di sezioni centrali, l'ultima può espandersi.
        
        Stile:
        - Tono coinvolgente e professionale
        - Max 1050 parole
        - NON usare ``` né altri wrapper markdown
        - NON scrivere mai “prova la pizza”, ma: “prova la pizza napoletana da Gino Sorbillo, celebre per…”
        - IMPORTANTE: DEVI SEMPRE restituire HTML strutturato con le classi Tailwind CSS specificate,
          indipendentemente dal tipo di richiesta (specifica o generica).
        - Tutte le immagini delle card laterali DEVONO usare esattamente: class="w-[260px] min-w-[260px] h-[220px] object-cover rounded-[14px] flex-shrink-0" per garantire allineamento uniforme.
        - I testi di descrizione dei piatti che si trovano nella card grandi devono essere di 80 parole
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
    
    async def chat_stream(self, user_message: str, history: Optional[List] = None, skip_echo: bool = False):
        """Gestisce una conversazione in modalità streaming, inviando aggiornamenti in tempo reale."""
        logger.info(f"Inizio chat (streaming) con messaggio: '{user_message}' skip_echo={skip_echo}")
        if history and isinstance(history, list):
                # Filtra solo i messaggi dell'utente
                user_msgs = [m for m in history if isinstance(m, dict) and m.get('role') == 'user']
                if len(user_msgs) >= 2:
                    # Prendi il penultimo (indice -2)
                    penultimate = user_msgs[-2]
                    logger.info(f"--- PENULTIMO MESSAGGIO UTENTE ---\n{json.dumps(penultimate, indent=2)}\n------------------------------")
                    penultimate = user_msgs[-2]    
                    logger.info(penultimate['parts'][0]['text'])
                else:
                    logger.info(f"--- PENULTIMO MESSAGGIO UTENTE: Non presente (Totale msg utente: {len(user_msgs)}) ---")
                   
        else:
                logger.info("History vuota o non valida.")
      
        # Forza chat mode in pagina Programma di viaggio
        if getattr(self, "programMode", True):
            self.chatMode = True
        
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
            if not skip_echo:
                user_payload = {
                    "chatbot_message": {
                        "message": user_message,
                        "isUser": True
                    }
                }
                
                yield user_payload
            else:
                logger.info("Skip user echo attivo: il messaggio utente non viene inviato al frontend.")

            # Rileva la località dalla query e inviala al frontend
            try:
                    original_query = user_message
            except Exception as e:
                    logger.warning(f"Preparazione query fallita: {e}")
                
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
                msg_for_content = user_message
                
                #


                full_content_response = await self._generate_culinary_content_stream(msg_for_content, history)
                
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
                        with open("generated_content_test_files/search_queries_cache.json", "r") as f:
                            cached = json.load(f)
                        if isinstance(cached, dict) and "queries" in cached:
                            loc = cached.get("localita")
                            if loc:
                                self.location = loc
                                yield {"detected_location": self.location}
                            search_queries = cached.get("queries", {})
                        else:
                            search_queries = cached
                    except (FileNotFoundError, json.JSONDecodeError):
                        logger.warning("File di cache delle query non trovato o corrotto. Analisi in corso.")
                        res = await self.analyzer_service.analyze_content_for_maps_search(full_content_response, user_message, current_location=self.location)
                        if isinstance(res, dict) and "queries" in res:
                            loc = res.get("localita")
                            if loc:
                                self.location = loc
                                yield {"detected_location": self.location}
                            search_queries = res.get("queries", {})
                        else:
                            search_queries = res
                else:
                    # Produzione: se l'analisi fallisce (es. 429), usa fallback deterministici
                    try:
                        res = await self.analyzer_service.analyze_content_for_maps_search(full_content_response, user_message, current_location=self.location)
                        if isinstance(res, dict) and "queries" in res:
                            loc = res.get("localita")
                            if loc:
                                self.location = loc
                                yield {"detected_location": self.location}
                            search_queries = res.get("queries", {})
                            try:
                                with open("generated_content_test_files/search_queries_cache.json", "w") as f:
                                    json.dump(res, f, indent=4)
                            except Exception as _e:
                                logger.warning(f"Scrittura cache query fallita: {_e}")
                        else:
                            search_queries = res
                    except Exception as e:
                        logger.warning(f"Analisi query fallita: {e}. Applico fallback locale per proseguire col ranking.")
                        location_hint = (self.location or user_message or "località").strip()
                        search_queries = {
                            "strutture ricettive": f"hotel a {location_hint}",
                            "vini": f"enoteche e cantine a {location_hint}",
                            "cucina_tipica": f"ristoranti tipici a {location_hint}",
                            "dolci tipici": f"pasticcerie a {location_hint}",
                        }

                # Filtro server-side: rimuove categorie non desiderate prima di qualsiasi chiamata a Maps
                search_queries = self._filter_out_unwanted_categories(search_queries)
                # Se dopo il filtro non resta nulla, crea un fallback deterministico
                if not search_queries:
                    logger.warning("Nessuna categoria valida dopo filtro; uso fallback di base per proseguire.")
                    location_hint = (self.location or user_message or "località").strip()
                    search_queries = {
                        "strutture ricettive": f"hotel a {location_hint}",
                        "vini": f"enoteche e cantine a {location_hint}",
                        "cucina_tipica": f"ristoranti tipici a {location_hint}",
                        "dolci tipici": f"pasticcerie a {location_hint}",
                    }
                
                # Step 3: Ricerca su Mappe (se necessaria)
                if search_queries:
                    yield {"status": "Sto cercando i luoghi migliori su Google Maps..."}
                    if settings.debug_mode:
                        logger.info("Modalità debug attiva: caricamento dei dati di Google Maps da file (assets/generata).")
                        candidate_paths = [
                            os.path.join("assets", "cities_cache", "maps_data_cache.json"),
                            os.path.join("generated_content_test_files", "maps_data_cache.json"),
                        ]
                        maps_data = None
                        for p in candidate_paths:
                            try:
                                if os.path.exists(p):
                                    with open(p, "r", encoding="utf-8") as f:
                                        maps_data = json.load(f)
                                    logger.info(f"Caricati dati Maps da: {p}")
                                    break
                            except Exception as e:
                                logger.warning(f"Errore nel caricamento file Maps '{p}': {e}")

                        if not maps_data:
                            logger.warning("Cache Maps non trovata/valida. Uso struttura vuota per consentire suggerimenti locali.")
                            maps_data = {cat: {"results": [], "iframe_url": None} for cat in search_queries.keys()}
                    else:
                        # Produzione: se la ricerca Maps fallisce (es. API error), crea struttura vuota
                        try:
                            logger.info(f"Chiamo gemini_maps.search_places con categorie: {list(search_queries.keys())}")
                            print(f"[GeminiService] CALL gemini_maps.search_places -> categories={list(search_queries.keys())}")
                            maps_data = await self.gemini_maps.search_places(search_queries, user_message)
                            logger.info("gemini_maps.search_places completata senza eccezioni")
                            print("[GeminiService] gemini_maps.search_places DONE")
                            with open("generated_content_test_files/maps_data_cache.json", "w") as f:
                                json.dump(maps_data, f, indent=4)
                        except Exception as e:
                            logger.warning(f"Ricerca Maps fallita: {e}. Uso struttura vuota per consentire suggerimenti locali.")
                            print(f"[GeminiService] gemini_maps.search_places FAILED: {e}")
                            maps_data = {cat: {"results": [], "iframe_url": None} for cat in search_queries.keys()}

                    if maps_data:
                        yield {"status": "Applico filtri e ranking ai risultati..."}
                        
                        augmented_user_message = (f"{user_message} a {self.location}" if isinstance(user_message, str) and self.location else user_message)
                        ranked_results = await self.filtering_ranking_service.filter_rank_and_present(search_queries, maps_data, augmented_user_message)
                        # Ulteriore protezione: rimuove sezioni non desiderate dall'output
                        ranked_results = self._filter_out_unwanted_categories(ranked_results)
                        yield {"map_payload": {"tool_name": "search_google_maps", "tool_data": ranked_results}}

    
                        
                        # Combina il contenuto culinario con i risultati delle attività per il chatbot
                        activities_html = ""
                        allowed_after_selection = {"hotel", "vini", "cucina tipica", "strutture ricettive", "cucina_tipica", "dolci tipici"}
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
                self.chatBot = ProgramService(complete_html_content) if getattr(self, "programMode", False) else Chatter(complete_html_content)

                # Attiva la modalità chatbot per le ricerche successive
                self.chatMode = True

            except Exception as e:
                logger.error(f"Errore durante lo streaming della chat: {e}", exc_info=True)
                yield {"error": "Si è verificato un errore durante l'elaborazione della richiesta."}


        else:
            # Modalità chatbot attiva dalla seconda ricerca in poi
            try:
                # Inizializzazione di sicurezza del chatbot nel caso non sia stato creato
                if self.chatBot is None:
                    logger.info("ChatBot non inizializzato: creo istanza chatbot in base alla modalità")
                    self.chatBot = ProgramService(self.get_last_complete_html()) if getattr(self, "programMode", False) else Chatter(self.get_last_complete_html())
                locationBuff = self.contextDetector.checkLocation(user_message)
                try:
                    loc = (locationBuff or "").strip()
                    if loc and loc.lower() != "false":
                        self.location = loc
                        logger.info(f"📍 Località impostata per chat mode: {self.location}")
                        # Invia al frontend la località rilevata
                        yield {"detected_location": self.location}
                except Exception as _e:
                    logger.warning(f"Impostazione località fallita: {_e}")

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
                
                # Usa il ChatterService per generare la risposta appropriata
                bot_response = self.chatBot.getResponse(user_message)
                logger.info(f"Risposta del chatbot: {bot_response}")
                # Aggiungi la risposta del bot al chatbot
                bot_payload = {
                    "chatbot_message": {
                        "message": bot_response,
                        "isUser": False
                    }
                }
                yield bot_payload
                
                # Popola comunque i suggerimenti (LFW/Selezione) anche in chat mode
               
                
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
        """Filtra le categorie lato server lasciando SOLO quelle supportate in UI.
        Ammesse: 'cucina_tipica', 'vini', 'hotel' (sinonimo: 'strutture ricettive').
        Rimuove tutto il resto (es. 'eventi'). Funziona sia su dizionari di query che su risultati.
        """
        if not isinstance(data, dict):
            return data

        # Consenti le categorie supportate in UI e la sezione "La nostra selezione"
        # Nota: le chiavi vengono normalizzate (underscore e trattini → spazio, lowercase)
        allowed = {
            "cucina tipica",
            "dolci tipici",
            "vini",
            "hotel",
            "strutture ricettive",
            "la nostra selezione",
         
        }

        def normalize(key: str) -> str:
            return key.lower().strip().replace("_", " ").replace("-", " ")

        filtered = {}
        for k, v in data.items():
            nk = normalize(k)
            if nk in allowed:
                filtered[k] = v
        return filtered

    def get_last_complete_html(self) -> str:
        """Restituisce l'ultimo HTML completo generato"""
        return getattr(self, 'last_complete_html', "")
    
    async def _generate_culinary_content_stream(self, user_message: str, history: Optional[List] = None) -> str:
        if settings.debug_mode:
            logger.info("Modalità debug attiva: caricamento del contenuto da file.")
            try:
                with open("generated_content_test_files/culinary_content_cache.json", "r") as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                logger.warning("File di cache non trovato o corrotto. Generazione del contenuto in corso.")
                # Prosegui con la generazione normale se il file non esiste
                pass

        """Genera contenuto culinario completo senza streaming."""
        try:
            logger.info(f"Generazione contenuto culinario (senza streaming) per: '{user_message}'")

            content_config = self.content_config
            try:
                if self.chatMode and self.location:
                    grounding_tool = types.Tool(google_search=types.GoogleSearch())
                    content_config = types.GenerateContentConfig(
                        system_instruction=self._get_content_system_prompt() + f"\nCITTÀ CORRENTE: {self.location}\n",
                        temperature=0,
                        tools=[grounding_tool]
                    )
            except Exception:
                content_config = self.content_config
            content_chat = self.content_client.chats.create(
                model=GEMINI_MODEL,
                config=content_config,
                history=history or []
            )

            # NOTA: nessun stream=True => ritorna una risposta completa
            response = content_chat.send_message(message=user_message)

            # Log dei metadati di grounding
            self._log_grounding_metadata(response)

            if response.candidates and response.candidates[0].content.parts:
                content = response.candidates[0].content.parts[0].text
                if not settings.debug_mode:
                    with open("generated_content_test_files/culinary_content_cache.json", "w") as f:
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
        base = os.path.join("generated_content_test_files", self._cache_key(user_message))
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
            # Inizializzazione di sicurezza del chatbot
            if self.chatBot is None:
                logger.info("ChatBot non inizializzato in write_to_chatbox: creo istanza in base alla modalità")
                self.chatBot = ProgramService(self.get_last_complete_html()) if getattr(self, "programMode", False) else Chatter(self.get_last_complete_html())

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

