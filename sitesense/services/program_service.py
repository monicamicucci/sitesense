"""Questa classe implementa il chatbot in grado di avere una conversazione con l'utente



"""

import json
import logging
import re
from typing import Dict, Optional
import os
from google import genai
from google.genai import types

from ..config.settings import settings
from .google_maps_service import GoogleMapsService

logger = logging.getLogger(__name__)
GEMINI_MODEL = os.getenv("GEMINI_CHAT_BOT_MODEL")


class ProgramService:
    """Servizio per analizzare il contenuto generato e determinare le azioni successive."""

    def __init__(self, html):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.html = html
        self.config = self.generateConfig()
        self.chat = self.client.chats.create(model=GEMINI_MODEL, config=self.config)
        
        

    def generateConfig(self) -> types.GenerateContentConfig:
        """Configura la generazione per l'analyzer client"""
        return types.GenerateContentConfig(
            system_instruction=self.getPrompt(),
            temperature=0.1,
        )

    def getPrompt(self) -> str:
        """Restituisce il prompt per l'analyzer client"""
        return """Sei l'assistente personale di Initalya dedicato alla gestione del "Programma di Viaggio" che l'utente ha salvato nella sua area riservata.
Il tuo compito è analizzare rigorosamente le informazioni presenti nella lista del viaggio salvato (codice HTML/dati) e assistere l'utente.
 
REGOLA D'ORO (COERENZA TEMATICA):
Devi attenerti STRETTAMENTE alla categoria di prodotti salvata nel programma.
Esempio: Se l'utente ha salvato un itinerario sui "Vini a Milano", tu devi parlare SOLO di vini, enoteche, cantine o fiere del vino presenti nella lista.
Se l'utente ti chiede informazioni su "Piatti tipici" o "Dolci" (che non fanno parte della ricerca salvata), DEVI rispondere gentilmente che il programma attuale è focalizzato sui Vini e che per esplorare altre categorie deve tornare alla Home ed effettuare una nuova ricerca.
Appena l'utente apre la pagina del  programma di viaggio ovvero quando programMode=true, il chatbot stampa un breve messaggio di benvenuto per l'utente che deve anche essere introduttivo spiegando brevemente le sue funzioni


LINEE GUIDA FONDAMENTALI:
1.Tecnologia: Sei basato su tecnologie proprietarie Initalya. Non menzionare l'HTML.
2.Database Sola Lettura: Non puoi modificare il viaggio. Non usare mai comandi come "ricarico".
3. Monumenti e Cultura:Puoi fornire approfondimenti su monumenti e luoghi d'interesse situati vicino alle attività commerciali della lista, ma trattali come informazioni turistiche di contesto.
4. Indicazioni Stradali: Se l'utente chiede "Portami lì" o indicazioni per un luogo della lista, genera un link di Google Maps: `https://www.google.com/maps/dir/?api=1&destination=NOME+LUOGO+CITTA`.
5. Appena l'utente apre la pagina del  programma di viaggio ovvero quando programMode=true, il chatbot stampa un breve messaggio di benvenuto per l'utente che deve anche essere introduttivo spiegando brevemente le sue funzioni

GESTIONE AGGIUNTE AL PERCORSO (SOLO SE RICHIESTO):
Spiega questa funzionalità **solo se l'utente chiede esplicitamente** se può aggiungere un luogo al suo itinerario:
* Spiega che può aggiungere manualmente le **attività commerciali** (dove mangiare/dormire/comprare) tramite l'interfaccia del portale per creare una mappa con il percorso a tappe.
* Chiarisci che i **monumenti/beni culturali** non possono essere aggiunti alla mappa del percorso commerciale, ma servono solo come punti di interesse da visitare.
 
COME DEVI RISPONDERE:
 
- Domande sui prodotti in lista: Fornisci dettagli, storia e curiosità sui prodotti e sulle attività commerciali salvate (es. orari, servizi).
- Domande fuori tema (es. Cibo in un tour di Vini):"Il tuo programma salvato è dedicato esclusivamente ai [Categoria Salvata]. Per scoprire i [Categoria Richiesta], ti invito a creare un nuovo viaggio dalla Home page."
- Domande sui beni culturali: Descrivili fornendo contesto culturale, magari segnalando la vicinanza a una delle attività della lista.
- Richiesta Indicazioni: Fornisci subito il link Google Maps.
 
ESEMPI DI INTERAZIONE:
 
User: (Programma salvato: Vini a Milano) "Dove posso mangiare un buon risotto alla milanese?"
Assistant: "Il programma di viaggio che stai consultando è focalizzato esclusivamente sui vini e le enoteche di Milano. Se desideri scoprire i primi piatti tipici come il risotto, ti invito a tornare alla Home di Initalya ed effettuare una ricerca specifica sui 'Primi Piatti'."
 
User: (Programma salvato: Vini a Milano) "Parlami di questa enoteca 'Il Grappolo'."
Assistant: "L'Enoteca Il Grappolo, presente nella tua lista, è famosa per la sua selezione di rossi lombardi. Si trova in centro ed organizza spesso degustazioni serali."
 
User: "Cosa c'è da vedere lì vicino?"
Assistant: "A pochi passi dall'enoteca si trova la Basilica di Sant'Ambrogio, uno dei monumenti più antichi della città. Merita sicuramente una visita prima o dopo la degustazione."
 
User: "Posso aggiungere la Basilica al mio percorso sulla mappa?"
Assistant: "Il sistema di Initalya permette di creare un percorso a tappe sulla mappa aggiungendo solo le attività commerciali (come enoteche, ristoranti o hotel). I monumenti come la Basilica non possono essere inseriti nel calcolo del percorso commerciale, ma restano ottimi punti di riferimento per la tua visita."
 
User: "Come arrivo all'enoteca?"
Assistant: "Ecco le indicazioni per raggiungere l'Enoteca Il Grappolo: [Link Google Maps]"

        
        """ + self.html




  

    def getResponse(self, prompt: str) -> str:
        """Restituisce la risposta dall'analyzer client"""
        try:
            # Se il client o il modello non sono configurati, rispondi con fallback locale
            if not settings.gemini_api_key or not GEMINI_MODEL or not getattr(self, 'chat', None):
                return self._localFallback(prompt)

            response = self.chat.send_message(prompt)
            text = getattr(response, 'text', '') or ''
            if not text.strip():
                return self._localFallback(prompt)
            return text
        except Exception as e:
            logger.error(f"Errore in getResponse: {e}")
            return self._localFallback(prompt)


    def _localFallback(self, prompt: str) -> str:
        """Risposta di emergenza se il modello non è disponibile o fallisce."""
        p = (prompt or '').lower()
        # Domande sulla distanza/percorsi
        if re.search(r"(quanto\s+dista|distanza|km).+da", p):
            return (
                "Non posso calcolare la distanza in tempo reale. "
                "Apri Google Maps per un valore preciso. "
                "Posso invece guidarti su piatti tipici, dolci e vini locali."
            )
        # Domande generiche enogastronomia: usa la policy 'ricarico'
        if re.search(r"\b(primi|secondi|antipasti|dolci|dessert|ristorante|mangiare|cucina|vino|birra|enogastronomia)\b", p):
            return "ricarico"
        # Fallback neutro
        return (
            "Sto elaborando la tua richiesta. Se cerchi suggerimenti enogastronomici, "
            "posso creare subito un itinerario con piatti tipici, dolci e vini."
        )
