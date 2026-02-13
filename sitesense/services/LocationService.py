
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


class Locator:


    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
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
        return """Sei un assistente virtuale che si occupa di aiutare gli utenti ad ottenere
        informazioni enogastronomiche su una città o una regione. 
        Il tuo compito è quello di analizzare un prompt dell'utente e capire se contiene una località. oppure no

        DEVI rispondere solo con True o False. True se la frase contiene una località, False se non la contiene

        ESEMPI:

        -che vini ci sono a monopoli? -----> True
        -vorrei andare a bari a mangiare del pesce -----> True
        -ci sono sagre a milano ----> True

        -vorrei mangiare la trippa ---> False

        -dimmi di più sui vini ---> False

        -






        
        """ 

    def isCity(self, prompt: str) -> str:
        """Restituisce la risposta dall'analyzer client"""
        response = self.chat.send_message(prompt)
        return response.text
