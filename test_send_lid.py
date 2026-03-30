import asyncio
import httpx
import json

API_URL = "http://147.15.19.110:8080"
API_KEY = "65DRSa9v0Vzqp@Tp^!Vjc%"
INSTANCE = "iassis_bot"
LID = "45032899928207@lid"
MSG_ID = "3A100537F3815ADF475F"

HEADERS = {
    "apikey": API_KEY,
    "Content-Type": "application/json"
}

async def send_msg(path, payload):
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{API_URL}/message/{path}/{INSTANCE}", json=payload, headers=HEADERS)
        print(f"[{path}] Status:", r.status_code)
        print(f"[{path}] Response:", r.text)

async def main():
    print("Testing checkNumber inside options")
    await send_msg("sendText", {
        "number": LID,
        "text": "Test 1",
        "options": {"delay": 0, "checkNumber": False},
    })
    
    print("\nTesting checkNumber outside options")
    await send_msg("sendText", {
        "number": LID,
        "text": "Test 2",
        "checkNumber": False,
        "options": {"delay": 0},
    })

    print("\nTesting quoted with checkNumber inside options")
    await send_msg("sendText", {
        "number": LID,
        "text": "Test Quoted",
        "options": {
            "delay": 0,
            "checkNumber": False,
            "quoted": {
                "key": {
                    "remoteJid": LID,
                    "fromMe": False,
                    "id": MSG_ID
                }
            }
        }
    })

asyncio.run(main())
