from google import genai 
from google.genai import types
from typing import Optional, Dict, Any
import logging
import os
import json
from ..config.settings import settings

logger = logging.getLogger(__name__)
GEMINI_MODEL = os.getenv("GEMINI_CHAT_BOT_MODEL") or os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"

class PreferencesCheckerService:
    """
    Servizio per verificare se l'utente ha prefereze, e nel caso, le recupera e le restituisce.
    """
    def __init__(self):
        logger.info("PreferencesCheckerService initialized.")
        self.preferences_checker_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.preferences_checker_config = self._setup_preferences_checker_config()
        self.debug_mode = settings.debug_mode

    def _setup_preferences_checker_config(self) -> types.GenerateContentConfig:
        """
        Configura le impostazioni per la verifica delle preferenze.
        """
        return types.GenerateContentConfig(
            system_instruction=self._get_preferences_checker_system_instruction(),
            temperature=0.5,
        )


        


    

    def _get_preferences_checker_system_instruction(self) -> str:
        """
        Restituisce l'istruzione del sistema per la verifica delle preferenze.
        """
        return """Sei un assistente AI specializzato nell'analisi delle query degli utenti per identificare le loro preferenze riguardo a luoghi come ristoranti, hotel o attrazioni turistiche. Il tuo compito è estrarre in modo accurato e strutturato SOLO i seguenti due tipi di preferenze:

1.  **budget**: Analizza la richiesta per determinare la fascia di prezzo desiderata. I valori possibili sono STRETTAMENTE limitati a: `economico`, `medio`, `lusso`.
2.  **servizi**: Estrai qualsiasi servizio o caratteristica specifica richiesta (es. 'pet-friendly', 'accessibilità', 'piscina', 'parcheggio gratuito').

Il tuo output DEVE essere un oggetto JSON. Ecco le regole:

-   Se identifichi una preferenza di budget, includi la chiave `"budget"` con uno dei tre valori consentiti.
-   Se identifichi uno o più servizi, includi la chiave `"servizi"` con una lista di stringhe.
-   Se non trovi NESSUNA preferenza esplicita (né budget, né servizi), DEVI restituire: `{"preferences_found": false}`.
-   Se trovi solo una delle due categorie, includi solo quella nel JSON.

Esempi:

Query: 'Cerco un ristorante economico che sia anche pet-friendly.'
Output JSON atteso:
{
  "budget": "economico",
  "servizi": ["pet-friendly"]
}

Query: 'Hotel di lusso con piscina.'
Output JSON atteso:
{
  "budget": "lusso",
  "servizi": ["piscina"]
}

Query: 'Un posto accessibile in sedia a rotelle.'
Output JSON atteso:
{
  "servizi": ["accessibilità"]
}

Query: 'Mostrami dei ristoranti a Roma.'
Output JSON atteso:
{
  "preferences_found": false
}

Analizza attentamente la richiesta e fornisci solo l'output JSON."""

    def _fallback_preferences(self, user_query: str) -> str:
        """Restituisce un JSON di fallback coerente con l'orchestratore quando l'API non è disponibile."""
        # Heuristica semplice: individua budget e alcuni servizi dal testo.
        text = (user_query or "").lower()
        budget = None
        if "economico" in text:
            budget = "economico"
        elif "lusso" in text:
            budget = "lusso"
        elif "medio" in text:
            budget = "medio"

        services = []
        for kw in ["pet-friendly", "accessibilita", "accessibilità", "piscina", "parcheggio", "family", "famiglia"]:
            if kw in text:
                services.append(kw)

        payload: Dict[str, Any] = {}
        if budget:
            payload["budget"] = budget
        if services:
            payload["servizi"] = services
        if not payload:
            payload["preferences_found"] = False
        return json.dumps(payload)

    async def check_preferences(self, user_query: str) -> Optional[str]:
        """
        Verifica se l'utente ha delle preferenze specifiche.
        """
        logger.info("Verifica delle preferenze dell'utente...")
        try:
            preferences_chat = self.preferences_checker_client.chats.create(
                model=GEMINI_MODEL,
                config=self.preferences_checker_config
            )
            response = preferences_chat.send_message(user_query)
            return response.text
        except Exception as e:
            # Non bloccare la pipeline: usa fallback coerente
            logger.warning(f"Preferenze: errore durante la chiamata al modello ({type(e).__name__}): {e}. Uso fallback.")
            # In debug possiamo anche loggare più dettagli o leggere da cache locale in futuro
            return self._fallback_preferences(user_query)




