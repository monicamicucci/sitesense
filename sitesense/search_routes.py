# search_routes.py

import os
import logging
import asyncio
import httpx
from fastapi import APIRouter, FastAPI, Request
from google import genai
from google.genai import types
import json


from pydantic import BaseModel, Field

# ─── CONFIG ────────────────────────────────────────────────────────────────────

# Carica le variabili d'ambiente (se usi un .env)
from dotenv import load_dotenv

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Imposta logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

logger.info("Variabili d'ambiente e logger configurati.")

# ─── DEFINIZIONE TOOLS PER GEMINI ───────────────────────────────────────────────

TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="view_location_google_maps",
                description="View a specific query or geographical location and display it in the embedded maps interface",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Free-form place or address"
                        }
                    },
                    "required": ["query"]
                }
            ),
            types.FunctionDeclaration(
                name="search_google_maps",
                description="Search Google Maps for places near a location",
                parameters={
                    "type": "object",
                    "properties": {
                        "search": {
                            "type": "string",
                            "description": "What to search (e.g. 'pizzerie a Roma')"
                        }
                    },
                    "required": ["search"]
                }
            ),
            types.FunctionDeclaration(
                name="directions_on_google_maps",
                description="Get directions from origin to destination",
                parameters={
                    "type": "object",
                    "properties": {
                        "origin": {
                            "type": "string",
                            "description": "Starting location"
                        },
                        "destination": {
                            "type": "string",
                            "description": "Ending location"
                        }
                    },
                    "required": ["origin", "destination"]
                }
            ),
        ]
    )
]


GROUNDING_PROMPT = """
Sei un assistente di ricerca specializzato in enogastronomia italiana.
Il tuo unico compito è usare lo strumento di ricerca per trovare informazioni dettagliate e specifiche in base alla richiesta dell'utente.
Fornisci un riassunto conciso delle informazioni trovate, concentrandoti su:
- Piatti e prodotti tipici (DOP, IGP, PAT)
- Vini locali (DOC, DOCG)
- Produttori, ristoranti o luoghi di interesse menzionati nelle fonti.
Estrai solo i fatti, senza aggiungere commenti o formattazione.
"""

grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)

GROUNDING_GEN_CONFIG = types.GenerateContentConfig(
    tools=[grounding_tool],
    # Non è necessario uno `system_instruction` complesso qui
)
PROMPT = (
    """
    <<SYSTEM>>
Sei “Initalya AI Travel & Food Concierge”, un’assistente multilingua
specializzato in itinerari culinari personalizzati.  
Obiettivo: collegare ogni località alle sue eccellenze
enogastronomiche, suggerendo tappe, piatti, dolci, vini e produttori
tipici lungo il percorso richiesto dall’utente.

Regole di ragionamento (nascondi il processo all’utente):
1. Interpreta la richiesta estraendo:
   • DESTINAZIONI (partenza, arrivo, eventuali tappe intermedie)  
   • PREFERENZE_CULINARIE (piatti richiesti, intolleranze, fascia prezzo)  
   • MEZZO_DI_TRASPORTO & TEMPI (auto, treno, durata massima)  
2. Per ogni destinazione individua:
   • Piatti e dolci tipici DOP/IGP o PAT con breve descrizione  
   • Vini/spiriti locali e loro abbinamenti  
   • Eventi, sagre o mercati stagionali se rilevanti  
   • Borghi e luoghi d’interesse gastronomico‐culturale  
3. Per un itinerario *multi-stop* stima km e tempi; distribuisci le  
   tappe in modo logico e progressivo.  
4. Suggerisci **ristoranti, trattorie, cantine, pasticcerie, agriturismi**  
   selezionati in base alle preferenze. Indica: nome, località, breve  
   motivo della scelta, fascia prezzo (€-€€€).  
5. Mantieni tono coinvolgente, autorevole ma colloquiale; lunghezza max  
   ≈ 550 parole (una pagina).  
6. Restituisci sempre output nel linguaggio dell’utente.  
7. Se mancano dati essenziali, chiedi un’unica domanda di chiarimento.

⚠️ Tool usage (nascosto all’utente):
- **Usa `search_google_maps`, `view_location_google_maps` o `directions_on_google_maps` ogni volta che ti serve**:
  • trovare locali/ristoranti/pasticcerie/enoteche in base alla destinazione  
  • visualizzare la zona di interesse sulla mappa  
  • ottenere indicazioni tra le tappe (auto, treno, ecc.)  
  • Se l’utente esprime più preferenze (es. “una pizza e un pasticciotto”), unifica le categorie nella stessa query (es. "pizzerie e pasticcerie a Monopoli") e usa `search_google_maps` una sola volta.
- **Se l’utente menziona anche solo una città, senza ulteriori dettagli, chiama sempre `search_google_maps`** per recuperare i punti di interesse enogastronomici.  
- Dopo ogni chiamata a un tool, integra i dati ottenuti nel tuo ragionamento mantenendo il tono descritto.

Formato di output (HTML formattato):
--------------------------------------------------------------------
Restituisci SEMPRE la risposta in formato HTML ben strutturato, utilizzando i seguenti elementi:

<div class="travel-guide">
  <div class="intro">
    <h2 class="text-2xl font-bold text-slate-800 mb-4">🍷 [Titolo della destinazione]</h2>
    <p class="text-slate-700 mb-6">[3-4 frasi introduttive]</p>
  </div>
  
  <div class="route-section mb-6">
    <h3 class="text-xl font-semibold text-slate-800 mb-3">🗺️ Percorso Consigliato</h3>
    <ul class="list-disc list-inside text-slate-700 space-y-2">
      <li><strong>Partenza → Arrivo</strong> (km, tempo)</li>
      <li>Tappe intermedie con descrizioni</li>
    </ul>
  </div>
  
  <div class="dishes-section mb-6">
    <h3 class="text-xl font-semibold text-slate-800 mb-3">🍝 Piatti Tipici</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div class="bg-amber-50 p-4 rounded-lg">
        <h4 class="font-semibold text-amber-800">[Nome Piatto]</h4>
        <p class="text-sm text-amber-700">[Provenienza]</p>
        <p class="text-slate-600 mt-2">[Descrizione]</p>
      </div>
    </div>
  </div>
  
  <div class="desserts-section mb-6">
    <h3 class="text-xl font-semibold text-slate-800 mb-3">🧁 Dolci Tipici</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div class="bg-pink-50 p-4 rounded-lg">
        <h4 class="font-semibold text-pink-800">[Nome Dolce]</h4>
        <p class="text-sm text-pink-700">[Provenienza]</p>
        <p class="text-slate-600 mt-2">[Descrizione]</p>
      </div>
    </div>
  </div>
  
  <div class="wines-section mb-6">
    <h3 class="text-xl font-semibold text-slate-800 mb-3">🍷 Vini & Bevande</h3>
    <div class="space-y-3">
      <div class="bg-purple-50 p-4 rounded-lg">
        <h4 class="font-semibold text-purple-800">[Denominazione]</h4>
        <p class="text-slate-600">[Zona, vitigno, abbinamenti]</p>
      </div>
    </div>
  </div>
  
  <div class="restaurants-section mb-6">
    <h3 class="text-xl font-semibold text-slate-800 mb-3">🍽️ Dove Mangiare</h3>
    <div class="space-y-3">
      <div class="bg-green-50 p-4 rounded-lg border-l-4 border-green-400">
        <h4 class="font-semibold text-green-800">[Nome Locale]</h4>
        <p class="text-sm text-green-700">[Città] • [Categoria] • [Fascia prezzo]</p>
        <p class="text-slate-600 mt-2">[Piatto distintivo]</p>
      </div>
    </div>
  </div>
  
  <div class="curiosities-section">
    <h3 class="text-xl font-semibold text-slate-800 mb-3">✨ Curiosità Locali</h3>
    <ul class="list-disc list-inside text-slate-700 space-y-2">
      <li>[Aneddoto o tradizione]</li>
      <li>[Sagra o evento]</li>
    </ul>
  </div>
</div>

> Limite: non superare una pagina di output finale.
> IMPORTANTE: Restituisci SOLO il codice HTML, senza wrapper markdown o altri formati.

<<END SYSTEM>>
    """
)


GEN_CONFIG = types.GenerateContentConfig(
    tools=TOOLS,
    system_instruction=PROMPT,
    temperature=0.3,
)
logger.info(f"Tools per Gemini definiti: {len(TOOLS[0].function_declarations)} funzioni.")

# ─── HANDLER PER CHIAMATE A GOOGLE MAPS ────────────────────────────────────────

async def places_search(search: str):
    logger.info(f"Inizio places_search con query: '{search}'")
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": search,
        "key": GOOGLE_MAPS_API_KEY,
        "language": "it"
    }
    logger.info(f"Chiamata API Google Maps Places: URL='{url}', Params='{params}'")
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        data = r.json()
    #logger.info(f"Risposta API Google Maps Places: Status={r.status_code}, Data='{data}'")

    results = []
    for p in data.get("results", []):
        # Prepara URL per la foto, se disponibile
        photo_url = None
        photos = p.get("photos")
        if photos:
            # Usa il primo riferimento foto per costruire l'URL
            ref = photos[0].get("photo_reference")
            if ref:
                photo_url = (
                    f"https://maps.googleapis.com/maps/api/place/photo"
                    f"?maxwidth=400&photoreference={ref}&key={GOOGLE_MAPS_API_KEY}"
                )

        results.append({
            "nome": p.get("name"),
            "indirizzo": p.get("formatted_address"),
            "valutazione": p.get("rating", "N/A"),
            "coordinate": p.get("geometry", {}).get("location"),
            "tipologie": p.get("types", []),
            "foto_url": photo_url,
            "place_id": p.get("place_id")
        })

    # Costruisci l'URL dell'iframe per la query di ricerca originale
    iframe_url_search = f"https://www.google.com/maps/embed/v1/search?key={GOOGLE_MAPS_API_KEY}&q={search.replace(' ', '+')}"
    logger.info(f"URL iframe per la ricerca '{search}': {iframe_url_search}")

    logger.info(f"Fine places_search. Trovati {len(results)} risultati.")
    # Restituisci sia i risultati che l'URL dell'iframe per la mappa generale della ricerca
    return {"results": results, "iframe_url": iframe_url_search}

async def get_place_details(place_id: str):
    logger.info(f"Inizio get_place_details per place_id: '{place_id}'")
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "key": GOOGLE_MAPS_API_KEY,
        "language": "it"
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        data = r.json()
    #logger.info(f"Risposta API Google Maps Place Details: Status={r.status_code}")
    result = data.get("result", {})
    # Aggiungi l'URL della foto se disponibile
    photo_url = None
    photos = result.get("photos")
    if photos:
        ref = photos[0].get("photo_reference")
        if ref:
            photo_url = (
                f"https://maps.googleapis.com/maps/api/place/photo"
                f"?maxwidth=800&photoreference={ref}&key={GOOGLE_MAPS_API_KEY}"
            )
    result["photo_url"] = photo_url
    return result


async def get_directions(origin: str, destination: str):
    logger.info(f"Inizio get_directions da '{origin}' a '{destination}'")
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin,
        "destination": destination,
        "key": GOOGLE_MAPS_API_KEY,
        "language": "it"
    }
    logger.info(f"Chiamata API Google Maps Directions: URL='{url}', Params='{params}'")
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        data = r.json()
    #logger.info(f"Risposta API Google Maps Directions: Status={r.status_code}, Data='{data}'")
    # semplifica: prendi primo percorso e primo step
    routes = data.get("routes", [])
    if not routes:
        logger.info("Nessuna indicazione trovata.")
        return []

    all_steps = []
    for route in routes:
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                instruction = step.get("html_instructions", "").replace("<div style=\"font-size:0.9em\">", " ").replace("</div>", "").replace("<b>", "").replace("</b>", "")
                distance = step.get("distance", {}).get("text", "")
                duration = step.get("duration", {}).get("text", "")
                all_steps.append({
                    "istruzione": instruction,
                    "distanza": distance,
                    "durata": duration
                })
    logger.info(f"Trovate {len(all_steps)} indicazioni.")
    # Costruisci l'URL dell'iframe per le indicazioni
    iframe_url = f"https://www.google.com/maps/embed/v1/directions?key={GOOGLE_MAPS_API_KEY}&origin={origin.replace(' ', '+')}&destination={destination.replace(' ', '+')}"
    logger.info(f"URL iframe per le indicazioni: {iframe_url}")

    return {"steps": all_steps, "iframe_url": iframe_url}

# ─── ORCHESTRAZIONE DEL FUNCTION CALL ─────────────────────────────────────────

async def handle_function_call(call):
    logger.info(f"Inizio handle_function_call con chiamata: {call}")
    name = call["name"]
    args = call["arguments"]
    if name == "search_google_maps":
        logger.info(f"Esecuzione tool 'search_google_maps' con argomenti: {args}")
        search_result_data = await places_search(args["search"])
        resp = search_result_data
        
        # Crea una stringa testuale descrittiva per il modello
        results = resp.get("results", [])
        iframe_url = resp.get("iframe_url", "")
        
        # Costruisci il testo descrittivo
        if results:
            descrizione_risultati = "Le attività sono:\n"
            for result in results:
                nome = result.get("nome", "N/D")
                valutazione = result.get("valutazione", "N/A")
                descrizione_risultati += f"- {nome} con valutazione {valutazione}\n"
            
            if iframe_url:
                descrizione_risultati += f"\nPuoi visualizzare la mappa qui: {iframe_url}"
        else:
            descrizione_risultati = "Nessuna attività trovata."
        
        # Restituisci sia la risposta completa che la versione descrittiva
        return {
            "name": name,
            "response": resp,
            "response_to_model": descrizione_risultati  # 👈 Ora è una stringa testuale
        }
    elif name == "view_location_google_maps":
        logger.info(f"Esecuzione tool 'view_location_google_maps' con argomenti: {args}")
        query = args["query"]
        # Costruisci l'URL dell'iframe direttamente nel backend
        iframe_url = f"https://www.google.com/maps/embed/v1/place?key={GOOGLE_MAPS_API_KEY}&q={query.replace(' ', '+')}" 
        resp = {"iframe_url": iframe_url, "location": query} # Includi anche la location originale per riferimento, se necessario
    elif name == "directions_on_google_maps":
        logger.info(f"Esecuzione tool 'directions_on_google_maps' con argomenti: {args}")
        resp = await get_directions(args["origin"], args["destination"])
    else:
        logger.warning(f"Tool sconosciuto '{name}' chiamato con argomenti: {args}")
        resp = {"error": f"Tool sconosciuto {name}"}
    logger.info(f"Fine handle_function_call per '{name}'")
    
    return {"name": name, "response": resp}


async def gemini_chat(user_message: str, history: list = None) -> dict:
    # logger.info(f"Inizio gemini_chat con messaggio utente: '{user_message}' e cronologia: {history}")
    chat = client.chats.create(
        model=GEMINI_MODEL,
        config=GEN_CONFIG,
        history=history or []
    )

    logger.info("----------------------------------------------Storia della chat before:")
    for entry in chat.get_history():
        logger.info("----------------------------------------")
        logger.info(f"Ruolo: {entry.role}")
        for part in entry.parts:
            if part.text:
                logger.info(f"Testo: {part.text}")
            if hasattr(part, 'function_call') and part.function_call:
                logger.info(f"Function Call: {part.function_call.name}")
                logger.info(f"Arguments: {part.function_call.args}")
    logger.info("----------------------------------------")

    logger.info("Chat con Gemini avviata.")
    resp = chat.send_message(message=user_message)
    #logger.info(f"Risposta iniziale da Gemini: {resp}")
    part = resp.candidates[0].content.parts[0]
    # logger.info(f"-------------------------------------------------------part: {part}")
    if hasattr(part, "function_call"):
        call = part.function_call
        logger.info(f"Gemini ha richiesto una function call: Name='{call.name}', Args='{call.args}'")
        tool_resp = await handle_function_call({"name": call.name, "arguments": call.args})
        logger.info(f"Risposta dal tool '{call.name}'")
        
        # Prepara il messaggio da inviare al modello
        message_to_model = tool_resp
        
        # Se abbiamo una versione specifica per il modello, usiamo quella
        if "response_to_model" in tool_resp and call.name == "search_google_maps":
            # Crea una copia del tool_resp ma sostituisci la risposta con quella filtrata
            message_to_model = {"name": tool_resp["name"], "response": tool_resp["response_to_model"]}
        
        # Se il tool ha generato un iframe_url, informa Gemini che la mappa è stata mostrata
        if "iframe_url" in tool_resp.get("response", {}):
            # Se vuoi dare più contesto, manda una lista di stringhe/parti
            follow_up = chat.send_message(
                message=[
                    json.dumps(message_to_model),
                    f"La mappa è stata mostrata all'utente con l'URL: {tool_resp['response']['iframe_url']}"
                ]
            )
        else:
            follow_up = chat.send_message(
                message=json.dumps(message_to_model)
            )
        
        #logger.info(f"Risposta di follow-up da Gemini dopo function call: {follow_up}")
        # logger.info(f"Tool response: {tool_resp}") # Rimosso perché loggato sopra
        final_response = {
            "answer": follow_up.text,
            "tool_name": call.name,
            "tool_data": tool_resp.get("response", {})
        }
    else:
        logger.info("Nessuna function call richiesta da Gemini.")
        final_response = {
            "answer": part.text,
            "tool_name": None,
            "tool_data": None
        }
    #logger.info(f"Fine gemini_chat. Risposta finale: {final_response}")

    logger.info("----------------------------------------------Storia della chat after:")
    for entry in chat.get_history():
        logger.info("----------------------------------------")
        logger.info(f"Ruolo: {entry.role}")
        for part in entry.parts:
            if part.text:
                logger.info(f"Testo: {part.text}")
            if hasattr(part, 'function_call') and part.function_call:
                logger.info(f"Function Call: {part.function_call.name}")
                logger.info(f"Arguments: {part.function_call.args}")
    logger.info("----------------------------------------")

    return final_response


# ─── FASTAPI ROUTER ───────────────────────────────────────────────────────────

router = APIRouter()
logger.info("Router FastAPI creato.")

class ChatRequest(BaseModel):
    query: str = Field(..., description="Il prompt da inviare a Gemini")
    history: list = Field(default_factory=list, description="Cronologia dei messaggi")

class ChatResponse(BaseModel):
    answer: str
    tool_name: str | None = None
    tool_data: list[dict] | dict | None = None

@router.post("/search", response_model=ChatResponse)
async def search_endpoint(request: Request, chat_request: ChatRequest):
    logger.info(f"Richiesta ricevuta su endpoint /search: {chat_request.query}")
    try:
        response_data = await gemini_chat(chat_request.query, chat_request.history)
        #logger.info(f"Risposta inviata da endpoint /search:")
        #logger.info(json.dumps(response_data, indent=2, ensure_ascii=False))
        return response_data
    except Exception as e:
        logger.error(f"Errore durante l'elaborazione della richiesta /search: {e}", exc_info=True)
        return {"answer": "Si è verificato un errore interno.", "tool_name": None, "tool_data": None} # Considera di ritornare un HTTPException


