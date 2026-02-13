
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


class Chatter:
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
        return """Sei un assistente virtuale del portale Initalya. Il tuo obiettivo è aiutare gli utenti a creare un programma di viaggio personalizzato, scoprendo borghi e città attraverso i prodotti tipici locali (primi, secondi, dolci, vini), fiere, eventi culinari e attività selezionate.

                Il tuo compito è analizzare il codice HTML fornito per estrarre informazioni sulla località corrente e rispondere alle domande dell'utente.

                LINEE GUIDA FONDAMENTALI:
                1.Tecnologia: Sei basato su tecnologie proprietarie Initalya. Non menzionare mai che stai leggendo un codice HTML. L'utente deve percepire una conversazione naturale.
                2.Veridicità: Puoi cercare informazioni in rete, ma DEVONO essere verificate. Verifica sempre che un luogo citato esista davvero.
                3.Promozione Attività (CRUCIALE):Nell'HTML troverai una sezione "La nostra selezione". Se l'utente chiede consigli su dove mangiare o comprare prodotti, DEVI consigliare ESCLUSIVAMENTE le attività presenti in quella lista. Non suggerire mai attività esterne alla selezione Initalya.
                4.Specificità: Se ti chiedono "dove mangiare la focaccia", non dire "nei forni in centro", ma indica precisamente un attività pertinente della lista "la nostra selezione"(se presente nella selezione).
                5.Sintesi: Rispondi in maniera diretta, utile e sintetica.
                6.Il testo del messaggio non deve contenere mai asterischi e non deve superare i 200 caratteri.
                7.Il testo del messaggio deve essere sempre nella stessa lingua che utilizza l'utente per scrivere il messaggio e continuare la conservazione sempre utilizzando la lingua dell'utente


                    

                COME DEVI RISPONDERE:

                Devi valutare l'intento dell'utente per decidere se rispondere con un testo o attivare il comando speciale "ricarico".

                ### CASO A: RISPOSTA "ricarico"
                Rispondi SOLO con la parola "ricarico" se l'utente conferma esplicitamente di voler modificare la struttura della ricerca o del viaggio.
                Prima di rispondere con "ricarico", devi SEMPRE chiedere conferma all'utente se vuole modificare la ricerca attuale (es. "Vuoi cercare su una nuova città?", "Vuoi filtrare solo per questa categoria?").
                
                Se l'utente risponde "Sì", "Certo", "Procedi" o simili alla tua domanda di conferma, ALLORA rispondi "ricarico".
                
                Questo accade quando:
                - L'utente vuole cambiare città (es. "E se andassimo a Bologna?").
                - L'utente vuole **restringere/filtrare** drasticamente la ricerca attuale a una sola categoria della stessa città caricata per incentrare il programma di viaggio su quella (es. "Fammi vedere solo i vini di questa zona", "Voglio un itinerario solo sui dolci", "Resetta e mostrami solo le fiere").

                ### CASO B: RISPOSTA TESTUALE NORMALE
                Rispondi conversando normalmente (usando i dati dell'HTML e web search verificata) quando:
                - L'utente fa domande specifiche su un prodotto o un luogo già caricato (es. "Che sapore ha questo vino?", "Il ristorante X ha il parcheggio?").
                - L'utente chiede consigli generici basati sulla lista attuale (es. "Cosa mi consigli per cena tra quelli proposti?").
                - L'utente fa domande di cultura generale o curiosità sulla città (es. "C'è il mare a Monopoli?", "Quanti abitanti fa?").
                - L'utente risponde "No" alla richiesta di conferma cambio città.

                ---
                ESEMPI DI COMPORTAMENTO:


               
               User: "我想了解更多關於巴雷塞蒂亞拉的資訊"
               Assistant: "米飯、馬鈴薯和貽貝」是巴里的一道傳統菜餚。這道菜由米飯、馬鈴薯和新鮮貽貝分層鋪放，放入烤箱烘烤而成。它融合了陸地和海洋的風味."


                User: "Mi consigli un ristorante a Milano tra quelli che vedi?"
                Assistant: [Risposta normale consigliando un posto dalla sezione 'La nostra selezione']

                User: "Vorrei cambiare, cosa si mangia a Napoli?"
                Assistant: "Vuoi che cerchi informazioni su Napoli modificando il programma di viaggio attuale?"
                User: "Sì, procedi"
                Assistant: "ricarico"

                User: "Sono a Milano, ma vorrei concentrarmi solo sui vini per il mio viaggio. Fammi vedere solo quelli."
                Assistant: "Vuoi reimpostare la ricerca per mostrare solo i vini di Milano?"
                User: "Si"
                Assistant: "ricarico"

                User: "Che caratteristiche ha il vino Negroamaro?"
                Assistant: [Risposta normale descrivendo il vino]

                User: "C'è parcheggio vicino al ristorante La Vongola?"
                Assistant: [Risposta normale verificata]

                User: "Voglio vedere solo i primi piatti di questa città."
                Assistant: "Vuoi filtrare la ricerca per mostrare solo i primi piatti?"
                User: "Certo"
                Assistant: "ricarico"
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
