
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
GEMINI_MODEL = os.getenv("GEMINI_MODEL")


class HtmlGenerator:
    """Servizio per analizzare il contenuto generato e determinare una interfaccia html"""

    
       

        

   
