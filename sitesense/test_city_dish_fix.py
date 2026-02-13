#!/usr/bin/env python3
"""
Test script per verificare il funzionamento della funzione get_city_dish_image
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main_oop import SiteSenseApp
from services.database import get_connection

async def test_city_dish_image():
    """Test the get_city_dish_image function"""
    app = SiteSenseApp()
    
    # Test cases
    test_cases = [
        ("Roma", "Carbonara"),
        ("Napoli", "Pizza Margherita"),
        ("Milano", "Risotto alla Milanese"),
        ("Firenze", "Bistecca alla Fiorentina"),
    ]
    
    for city, dish in test_cases:
        print(f"\n{'='*60}")
        print(f"Testing: {dish} in {city}")
        print(f"{'='*60}")
        
        try:
            # Test the function
            result = await app.get_city_dish_image(city, dish)
            
            if result:
                print(f"✅ SUCCESS: Found image for {dish} in {city}")
                print(f"   URL: {result}")
            else:
                print(f"❌ NO IMAGE: No image found for {dish} in {city}")
            
            # Check database
            conn = get_connection()
            if conn:
                cur = conn.cursor(dictionary=True)
                
                # Find city ID
                cur.execute("SELECT id FROM Initalya.cities WHERE name = %s LIMIT 1", (city,))
                city_row = cur.fetchone()
                
                if city_row:
                    city_id = city_row['id']
                    print(f"   City ID: {city_id}")
                    
                    # Check photos for this city and dish
                    cur.execute("""
                        SELECT url, titolo FROM Initalya.photo 
                        WHERE city_id = %s AND titolo LIKE %s
                        ORDER BY id DESC 
                        LIMIT 5
                    """, (city_id, f"%{dish}%"))
                    photos = cur.fetchall()
                    
                    if photos:
                        print(f"   📸 Found {len(photos)} photo(s) in database:")
                        for photo in photos:
                            print(f"      - Title: {photo['titolo']}")
                            print(f"        URL: {photo['url']}")
                    else:
                        print(f"   📸 No photos found in database for this dish")
                        
                    # Check all photos for this city
                    cur.execute("""
                        SELECT titolo, url FROM Initalya.photo 
                        WHERE city_id = %s 
                        ORDER BY id DESC 
                        LIMIT 10
                    """, (city_id,))
                    all_photos = cur.fetchall()
                    
                    if all_photos:
                        print(f"   📚 All photos for {city} ({len(all_photos)} total):")
                        for photo in all_photos:
                            print(f"      - {photo['titolo']}")
                else:
                    print(f"   ❌ City not found in database")
                
                conn.close()
            else:
                print(f"   ❌ Database connection failed")
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("Testing get_city_dish_image function...")
    asyncio.run(test_city_dish_image())
    print("\nTest completed!")