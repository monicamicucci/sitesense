"""Clasee che serve per rilevare il contesto della località
e in caso di un cambiamento riformulare il tour
la classe avrà due metodi principali

-Uno per rilevare la località di riferimento da una frase
-il secondo per capire se una nuova frase si riferisce ad un nuovo contesto e quindi che ci 
sia la necessita di riformulare il tour"""

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
GEMINI_MODEL = os.getenv("GEMINI_CHAT_BOT_MODEL") or os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"

class ContextDetector:


    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.config = self.generateConfig()
        
        
        

    def generateConfig(self) -> types.GenerateContentConfig:
        """Configura la generazione per l'analyzer client"""
        return types.GenerateContentConfig(
            system_instruction=self.getPrompt(),
            temperature=0.1,
        )

    def getPrompt(self) -> str:
        """Restituisce il prompt per l'analyzer client"""
        return """

        -Il tuo compito è quello di rilevare la località di riferimento da una frase che riceverai in input, la tua
        risposta DEVE essere soltanto il nome della città o paese.
        Puoi ricavare la città da i prodotti tipici locali  
        ATTENZIONE ci potrebbero essere dei casi in cui non si puo rilevare la località di riferimento, in quel caso devi 
        rispondere con soltanto 'False'

        ATTENZIONE i nomi dei ristoranti o piu in generale degli enti commerciali NON sono luoghi,
        i nomi dei prodotti tipici non sono luoghi 

        esempio: dove posso mangiare i taralli a Bari --- la tua risposta --> Bari
        tour di vini nella valle d'itria --- la tua risposta ---> valle d'itria
        al ristorante mollusco c'è il parcheggio? ---la tua risposta ----> False
        quando si tiene il festival? ---la tua risposta ---> False
        dove posso mangiare i pasticciotti --- la tua risposta --> Lecce
        vorrei fare un itinerario sui vini ---la tua risposta ---> False
        
        """ 

    
    def checkLocation(self, prompt):
        response = self.client.models.generate_content(config=self.config, contents=prompt, model=GEMINI_MODEL)
        logger.info("Località rilevata " + str(response.text))
        return response.text
    
