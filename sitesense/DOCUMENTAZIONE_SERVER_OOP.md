# Documentazione Dettagliata del Server Python SiteSense (Versione OOP)

## Panoramica Generale

SiteSense è un'applicazione web sviluppata in Python utilizzando FastAPI con un'architettura orientata agli oggetti. L'applicazione funziona come un "AI Travel & Food Concierge" che integra le API di Google Maps e Gemini AI per fornire consigli di viaggio personalizzati e informazioni enogastronomiche.

## Architettura del Sistema

### Struttura del Progetto

```
/opt/sitesense/
├── main_oop.py              # Entry point principale dell'applicazione
├── search_routes_oop.py     # Gestione delle route di ricerca
├── config/
│   └── settings.py          # Configurazioni dell'applicazione
├── controllers/
│   └── search_controller.py # Controller per la logica di business
├── services/
│   ├── google_maps_service.py # Servizio per Google Maps API
│   └── gemini_service.py      # Servizio per Gemini AI
├── templates/               # Template HTML
├── static/                  # File statici (CSS, JS)
└── assets/                  # Risorse (immagini, logo)
```

## Componenti Principali

### 1. Classe SiteSenseApp (main_oop.py)

La classe principale che orchestra l'intera applicazione:

```python
class SiteSenseApp:
    def __init__(self):
        self.app = FastAPI(title="SiteSense", description="AI Travel & Food Concierge")
        self.templates = Jinja2Templates(directory="templates")
        self._setup_static_files()
        self._setup_routes()
```

**Responsabilità:**
- Inizializzazione dell'applicazione FastAPI
- Configurazione dei file statici e template
- Setup delle route principali
- Gestione delle pagine HTML (homepage, dettagli luoghi)

**Metodi principali:**
- `_setup_static_files()`: Configura i percorsi per file statici e assets
- `_setup_routes()`: Registra tutte le route dell'applicazione
- `read_root()`: Gestisce la homepage
- `place_details()`: Gestisce la pagina dei dettagli di un luogo
- `api_place_details()`: API endpoint per i dettagli dei luoghi

### 2. Classe SearchRoutes (search_routes_oop.py)

Gestisce le route specifiche per le funzionalità di ricerca:

```python
class SearchRoutes:
    def __init__(self):
        self.router = APIRouter()
        self.controller = SearchController()
        self._setup_routes()
```

**Responsabilità:**
- Configurazione del router per le API di ricerca
- Integrazione con il SearchController
- Gestione dell'endpoint `/search`

### 3. Classe SearchController (controllers/search_controller.py)

Controller che implementa la logica di business:

```python
class SearchController:
    def __init__(self):
        self.google_maps_service = GoogleMapsService()
        self.gemini_service = GeminiService(self.google_maps_service)
```

**Responsabilità:**
- Coordinamento tra i servizi Google Maps e Gemini
- Gestione delle richieste di chat
- Elaborazione delle richieste di dettagli luoghi
- Gestione degli errori e logging

**Modelli Pydantic:**
- `ChatRequest`: Modello per le richieste di chat (query, history)
- `ChatResponse`: Modello per le risposte (answer, tool_name, tool_data)

### 4. Classe GoogleMapsService (services/google_maps_service.py)

Servizio per l'integrazione con le API di Google Maps:

```python
class GoogleMapsService:
    def __init__(self):
        self.api_key = settings.google_maps_api_key
        self.base_url = "https://maps.googleapis.com/maps/api"
```

**Funzionalità principali:**
- `search_places()`: Ricerca luoghi tramite Text Search API
- `get_place_details()`: Dettagli specifici di un luogo
- `get_directions()`: Calcolo indicazioni stradali
- Processamento e formattazione dei risultati
- Generazione di URL per iframe di Google Maps

**Metodi di supporto:**
- `_process_places_results()`: Elabora i risultati della ricerca
- `_process_directions_steps()`: Elabora le indicazioni stradali
- `_get_photo_url()`: Genera URL per le foto dei luoghi

### 5. Classe GeminiService (services/gemini_service.py)

Servizio per l'integrazione con Gemini AI:

```python
class GeminiService:
    def __init__(self, google_maps_service: GoogleMapsService):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.google_maps_service = google_maps_service
        self.tools = self._setup_tools()
```

**Caratteristiche avanzate:**
- **Function Calling**: Integrazione di strumenti personalizzati
- **System Prompt specializzato**: Prompt ottimizzato per consigli enogastronomici
- **Gestione conversazioni**: Mantenimento della cronologia chat
- **Output HTML strutturato**: Risposte formattate con HTML e Tailwind CSS

**Strumenti disponibili:**
- `search_google_maps`: Ricerca luoghi su Google Maps
- `view_location_google_maps`: Visualizzazione località specifica
- `directions_on_google_maps`: Calcolo indicazioni stradali

### 6. Classe Settings (config/settings.py)

Gestione centralizzata delle configurazioni:

```python
class Settings:
    def __init__(self):
        load_dotenv()
        self._google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self._gemini_api_key = os.getenv("GEMINI_API_KEY")
```

**Caratteristiche:**
- Caricamento automatico delle variabili d'ambiente
- Validazione delle chiavi API richieste
- Pattern Singleton per accesso globale

## Flusso di Elaborazione

### 1. Richiesta Utente
1. L'utente inserisce una query nell'interfaccia web
2. Il frontend invia una richiesta POST a `/search`
3. `SearchRoutes` riceve la richiesta e la inoltra al `SearchController`

### 2. Elaborazione AI
1. `SearchController` passa la query a `GeminiService`
2. Gemini analizza la richiesta e determina se servono strumenti esterni
3. Se necessario, vengono chiamate le funzioni di Google Maps
4. Gemini elabora i dati e genera una risposta HTML strutturata

### 3. Risposta
1. La risposta viene formattata come `ChatResponse`
2. Il frontend riceve i dati e aggiorna l'interfaccia
3. Vengono mostrati risultati, mappe e informazioni dettagliate

## Caratteristiche Tecniche

### Logging
- Sistema di logging configurato a livello INFO
- Tracciamento dettagliato delle operazioni
- Logging delle conversazioni con Gemini

### Gestione Errori
- Try-catch centralizzato nei controller
- Risposte di errore user-friendly
- Logging dettagliato degli errori per debugging

### Sicurezza
- Gestione sicura delle API key tramite variabili d'ambiente
- Validazione degli input tramite Pydantic
- Gestione degli errori senza esposizione di informazioni sensibili

### Performance
- Client HTTP asincrono (httpx) per le chiamate API
- Architettura asincrona con FastAPI
- Caching implicito delle configurazioni

## Interfaccia Utente

### Frontend
- **Framework**: HTML5 + Tailwind CSS + JavaScript vanilla
- **Responsive Design**: Ottimizzato per desktop e mobile
- **Animazioni**: Animate.css per transizioni fluide
- **Icone**: Material Icons di Google

### Funzionalità UI
- Barra di ricerca con autocompletamento
- Visualizzazione risultati in card responsive
- Integrazione mappe Google tramite iframe
- Cronologia conversazioni mantenuta lato client

## Configurazione e Deployment

### Variabili d'Ambiente Richieste
```bash
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
GEMINI_API_KEY=your_gemini_api_key
```

### Dipendenze Principali
- FastAPI: Framework web asincrono
- Google Generative AI: Client per Gemini
- httpx: Client HTTP asincrono
- Pydantic: Validazione e serializzazione dati
- Jinja2: Template engine
- python-dotenv: Gestione variabili d'ambiente

### Avvio dell'Applicazione
```bash
uvicorn main_oop:app --reload
```

L'applicazione sarà disponibile su `http://localhost:8000`

## Vantaggi dell'Architettura OOP

1. **Modularità**: Ogni componente ha responsabilità ben definite
2. **Manutenibilità**: Codice organizzato e facilmente modificabile
3. **Testabilità**: Componenti isolati facilmente testabili
4. **Scalabilità**: Facile aggiunta di nuovi servizi e funzionalità
5. **Riusabilità**: Servizi riutilizzabili in diversi contesti
6. **Separation of Concerns**: Logica di business separata dalla presentazione

## Diagrammi di Architettura

### Diagramma dei Componenti
```
┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   SiteSenseApp  │
│   (HTML/JS)     │◄──►│   (main_oop.py) │
└─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  SearchRoutes   │
                       │(search_routes_  │
                       │     oop.py)     │
                       └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │SearchController │
                       │  (controllers/) │
                       └─────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
           ┌─────────────────┐    ┌─────────────────┐
           │GoogleMapsService│    │  GeminiService  │
           │   (services/)   │    │   (services/)   │
           └─────────────────┘    └─────────────────┘
```

### Flusso di Dati
```
Utente → Frontend → SiteSenseApp → SearchRoutes → SearchController
                                                        │
                                                        ▼
                                                  GeminiService
                                                        │
                                                        ▼
                                              GoogleMapsService
                                                        │
                                                        ▼
                                                 Google Maps API
```

## Testing

### Struttura dei Test
- Directory `tests/` contiene i test unitari
- Test per i servizi principali
- Utilizzo di pytest come framework di testing

### Esecuzione dei Test
```bash
python -m pytest tests/
```

## Monitoraggio e Debugging

### Log Files
- Tutti i componenti utilizzano il modulo `logging` di Python
- Log strutturati con timestamp e livelli di severità
- Tracciamento delle chiamate API e delle conversazioni

### Debug Mode
```bash
uvicorn main_oop:app --reload --log-level debug
```

## Estensibilità

### Aggiunta di Nuovi Servizi
1. Creare una nuova classe nel package `services/`
2. Implementare l'interfaccia comune
3. Registrare il servizio nel `SearchController`
4. Aggiornare i tool di Gemini se necessario

### Aggiunta di Nuove Route
1. Estendere la classe `SearchRoutes`
2. Implementare i nuovi endpoint
3. Aggiornare il frontend se necessario

## Sicurezza e Best Practices

### Gestione delle API Key
- Mai hardcodare le chiavi nel codice
- Utilizzare sempre variabili d'ambiente
- Validazione delle chiavi all'avvio

### Validazione Input
- Utilizzo di Pydantic per la validazione
- Sanitizzazione degli input utente
- Gestione degli errori di validazione

### Rate Limiting
- Implementare rate limiting per le API esterne
- Gestione delle quote delle API
- Retry logic per le chiamate fallite

---

*Documentazione generata per SiteSense v1.0 - Architettura OOP*