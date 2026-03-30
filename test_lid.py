import asyncio
import httpx

API_URL = "http://147.15.19.110:8080"
API_KEY = "65DRSa9v0Vzqp@Tp^!Vjc%"
INSTANCE = "iassis_bot"
LID = "141588042883143@lid"

HEADERS = {
    "apikey": API_KEY,
    "Content-Type": "application/json"
}

async def main():
    async with httpx.AsyncClient() as client:
        # Test findChats
        print("Testing findChats...")
        r = await client.post(
            f"{API_URL}/chat/findChats/{INSTANCE}",
            json={"where": {"remoteJid": LID}},
            headers=HEADERS
        )
        print("findChats Status:", r.status_code)
        print("findChats Response:", r.json())
        
        # Test findContacts
        print("\nTesting findContacts...")
        r = await client.post(
            f"{API_URL}/chat/findContacts/{INSTANCE}",
            json={"where": {"id": LID}},
            headers=HEADERS
        )
        print("findContacts Status:", r.status_code)
        contacts = r.json()
        print("findContacts Response length:", len(contacts) if isinstance(contacts, list) else type(contacts))
        if isinstance(contacts, list) and len(contacts) > 0:
            print("Looking for Fatimas...")
            for c in contacts:
                if 'Tabosa' in str(c) or 'tabosa' in str(c).lower() or 'tima' in str(c):
                    print("Found Fatima:", str(c)[:300])
                    
asyncio.run(main())
