# Services package for SiteSense application
import importlib as _importlib
import sys as _sys

# Register absolute-style aliases for internal modules to support legacy imports
def _alias(module_name: str, package_relative: str):
    try:
        mod = _importlib.import_module(package_relative, package=__name__)
        _sys.modules[module_name] = mod
    except Exception:
        pass

_alias("filtering_ranking_service", ".filtering_ranking_service")
_alias("google_maps_service", ".google_maps_service")
_alias("gemini_maps", ".gemini_maps")
_alias("analyzer_service", ".analyzer_service")
_alias("gemini_service", ".gemini_service")
_alias("ChatterService", ".ChatterService")
_alias("ContextDetection", ".ContextDetection")
_alias("LocationService", ".LocationService")

from .google_maps_service import GoogleMapsService
from .gemini_maps import GeminiMapsService
from .gemini_service import GeminiService
from .analyzer_service import AnalyzerService
from .ChatterService import Chatter
from .ContextDetection import ContextDetector
from .LocationService import Locator
 
__all__ = ['GoogleMapsService', 'GeminiMapsService', 'GeminiService', 'AnalyzerService', 'Chatter', 'ContextDetector', 'Locator']
