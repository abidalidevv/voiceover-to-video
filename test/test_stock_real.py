import asyncio
import sqlite3
import json
from backend.main import PexelsProvider, PixabayProvider

async def test_stock():
    conn = sqlite3.connect("data/videogen.db")
    pexels_key = conn.execute("SELECT value FROM settings WHERE key='pexels_api_key'").fetchone()[0]
    pixabay_key = conn.execute("SELECT value FROM settings WHERE key='pixabay_api_key'").fetchone()[0]
    
    print("Testing Pexels with real API call...")
    pexels = PexelsProvider(pexels_key)
    p_results = await pexels.search("brain scan glowing digital", orientation="landscape", per_page=3)
    print(f"Pexels results count: {len(p_results)}")
    if p_results and "error" not in p_results[0]:
        print(f"Sample Pexels asset: ID={p_results[0]['id']}, provider_id={p_results[0]['provider_id']}, res={p_results[0]['width']}x{p_results[0]['height']}, duration={p_results[0]['duration']}s, license={p_results[0]['license_info']}")
        print(f"URL: {p_results[0]['url'][:80]}...")
    else:
        print("Pexels error/empty:", p_results)

    print("\nTesting Pixabay with real API call...")
    pixabay = PixabayProvider(pixabay_key)
    pix_results = await pixabay.search("laboratory research", orientation="landscape", per_page=3)
    print(f"Pixabay results count: {len(pix_results)}")
    if pix_results and "error" not in pix_results[0]:
        print(f"Sample Pixabay asset: ID={pix_results[0]['id']}, provider_id={pix_results[0]['provider_id']}, res={pix_results[0]['width']}x{pix_results[0]['height']}, duration={pix_results[0]['duration']}s, license={pix_results[0]['license_info']}")
        print(f"URL: {pix_results[0]['url'][:80]}...")
    else:
        print("Pixabay error/empty:", pix_results)

asyncio.run(test_stock())
