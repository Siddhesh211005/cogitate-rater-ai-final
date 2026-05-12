import asyncio
import sys
import logging

sys.path.insert(0, r"c:\Users\Siddhesh\cogitate-rater-ai-final\backend")

# Need to set up dotenv first just like main.py
from dotenv import load_dotenv
load_dotenv(r"c:\Users\Siddhesh\cogitate-rater-ai-final\.env")

from services.nim_enrichment import enrich_fields

logging.basicConfig(level=logging.INFO)

async def test_nim():
    fields = [
        {"field": "issue_age", "type": "number", "group": "Rating Inputs"},
        {"field": "sum_assured_input", "type": "number", "group": "Rating Inputs"}
    ]
    
    print("Sending fields to NIM enrichment...")
    enriched = await enrich_fields(fields)
    print("\nResults:")
    for f in enriched:
        print(f"  {f['field']} -> label: '{f.get('label')}', description: '{f.get('description')}'")

if __name__ == "__main__":
    asyncio.run(test_nim())
