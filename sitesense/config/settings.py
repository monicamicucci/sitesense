import os
import logging
from dotenv import load_dotenv
from typing import Optional
from pathlib import Path

class Settings:
    """Classe per gestire le configurazioni dell'applicazione"""
    
    def __init__(self):
        # Carica prima eventuale .env nella root di avvio
        load_dotenv()
        # Carica esplicitamente il .env del pacchetto sitesense (cartella padre di config), se esiste
        package_env = Path(__file__).resolve().parents[1] / ".env"
        if package_env.exists():
            # Non sovrascrivere variabili già presenti nell'ambiente
            load_dotenv(dotenv_path=package_env, override=False)
        # Logger
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        logger = logging.getLogger(__name__)
        self._google_maps_api_key: Optional[str] = os.getenv("GOOGLE_MAPS_API_KEY")
        self._gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
        self._google_oauth_client_id: Optional[str] = (
            os.getenv("GOOGLE_OAUTH_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID")
        )
        self._google_oauth_client_secret: Optional[str] = (
            os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET")
        )
        self._google_oauth_redirect_uri: Optional[str] = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://127.0.0.1:8001/auth/google/callback")
        self._enable_food_validation: bool = os.getenv("ENABLE_FOOD_VALIDATION", "true").lower() == "true"
        self._enable_filtering_and_ranking: bool = os.getenv("ENABLE_FILTERING_AND_RANKING", "true").lower() == "true"
        env_debug = os.getenv("DEBUG_MODE")
        self._debug_mode: bool = (env_debug.lower() == "true") if env_debug is not None else (not self._google_maps_api_key or not self._gemini_api_key)
        self._gemini_model: Optional[str] = os.getenv("GEMINI_MODEL")
        self._google_cse_api_key: Optional[str] = os.getenv("GOOGLE_CSE_API_KEY")
        self._google_cse_id: Optional[str] = os.getenv("GOOGLE_CSE_ID")
        self._unsplash_access_key: Optional[str] = os.getenv("UNSPLASH_ACCESS_KEY")
        self._pexels_api_key: Optional[str] = os.getenv("PEXELS_API_KEY")
        self._pixabay_api_key: Optional[str] = os.getenv("PIXABAY_API_KEY")
        # Log non sensibili per diagnosi
        try:
            logger.info(f"Settings: GOOGLE_CLIENT_ID presente={bool(self._google_oauth_client_id)}; GOOGLE_CLIENT_SECRET presente={bool(self._google_oauth_client_secret)}")
        except Exception:
            pass
        
    @property
    def google_maps_api_key(self) -> str:
        if not self._google_maps_api_key:
            if self._debug_mode:
                return "DUMMY_KEY"
            raise ValueError("GOOGLE_MAPS_API_KEY non configurata")
        return self._google_maps_api_key
    
    @property
    def gemini_api_key(self) -> str:
        if not self._gemini_api_key:
            if self._debug_mode:
                return "DUMMY_KEY"
            raise ValueError("GEMINI_API_KEY non configurata")
        return self._gemini_api_key

    @property
    def google_oauth_client_id(self) -> str:
        if not self._google_oauth_client_id:
            raise ValueError("GOOGLE_OAUTH_CLIENT_ID non configurata")
        return self._google_oauth_client_id

    @property
    def google_oauth_client_secret(self) -> str:
        if not self._google_oauth_client_secret:
            raise ValueError("GOOGLE_OAUTH_CLIENT_SECRET non configurata")
        return self._google_oauth_client_secret

    @property
    def google_oauth_redirect_uri(self) -> str:
        return self._google_oauth_redirect_uri

    @property
    def unsplash_access_key(self) -> str:
        if not self._unsplash_access_key:
            if self._debug_mode:
                return "DUMMY_KEY"
            raise ValueError("UNSPLASH_ACCESS_KEY non configurata")
        return self._unsplash_access_key

    @property
    def pexels_api_key(self) -> Optional[str]:
        return self._pexels_api_key

    @property
    def pixabay_api_key(self) -> Optional[str]:
        return self._pixabay_api_key



    @property
    def enable_food_validation(self) -> bool:
        return self._enable_food_validation

    @property
    def enable_ranking(self) -> bool:
        return self._enable_filtering_and_ranking

    @property
    def debug_mode(self) -> bool:
        return self._debug_mode

    @property
    def gemini_model(self) -> Optional[str]:
        return self._gemini_model

    @property
    def google_cse_api_key(self) -> str:
        if not self._google_cse_api_key:
            raise ValueError("GOOGLE_CSE_API_KEY non configurata")
        return self._google_cse_api_key

    @property
    def google_cse_id(self) -> str:
        if not self._google_cse_id:
            raise ValueError("GOOGLE_CSE_ID non configurata")
        return self._google_cse_id

# Istanza singleton delle configurazioni
settings = Settings()
