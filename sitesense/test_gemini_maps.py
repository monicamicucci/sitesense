#!/usr/bin/env python3
"""
Test script per verificare il funzionamento del servizio Gemini Maps
"""

import asyncio
import os
import sys
sys.path.append('.')

from services.gemini_maps import GeminiMapsService

async def test_gemini_maps():
    """Testa il servizio Gemini Maps per cercare locali"""
    try:
        print("🚀 Inizializzazione GeminiMapsService...")
        service = GeminiMapsService()
        print("✅ GeminiMapsService inizializzato con successo")
        
        # Test ricerca locali a Roma
        categories = {
            'ristoranti': 'pizzerie a Roma',
            'hotel': 'hotel a Roma'
        }
        
        print("🔍 Ricerca locali a Roma...")
        results = await service.search_places(categories, 'Roma')
        
        print(f"📊 Risultati:")
        print(f"   - Categorie trovate: {len(results)}")
        
        if "_meta" in results:
            meta = results["_meta"]
            print(f"   - Totale chiamate API: {meta.get('total_calls', 0)}")
            print(f"   - Chiamate FindPlace: {meta.get('findplace_calls', 0)}")
            print(f"   - Chiamate Details: {meta.get('details_calls', 0)}")
            print(f"   - Risultati per categoria: {meta.get('per_category_results', {})}")
        
        # Mostra alcuni risultati
        for category, data in results.items():
            if category != '_meta' and data.get('results'):
                print(f"\n   📍 {category.upper()}: {len(data['results'])} locali trovati")
                for i, place in enumerate(data['results'][:3]):
                    name = place.get('name', 'N/A')
                    rating = place.get('rating', 'N/A')
                    address = place.get('formatted_address', 'N/A')
                    print(f"     {i+1}. {name} (⭐ {rating}) - {address}")
        
        # Test se ci sono errori
        if not results or len(results) <= 1:  # Solo _meta
            print("\n⚠️  Nessun locale trovato! Possibili problemi:")
            print("   - API key non valida")
            print("   - Limite API raggiunto")
            print("   - Nessun risultato per la ricerca")
            
    except Exception as e:
        print(f"❌ Errore: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_gemini_maps())