
import requests
import hashlib
import platform
import uuid
import json

GAS_URL = "https://script.google.com/macros/s/AKfycbxHlT39nnCR7GEMUWr4y7sacwTcIIwZhlxoP4VABIJTPaglsHMPH-sNZy2x4elclmoL8Q/exec"

def get_hwid():
    combined = f"{platform.node()}_{uuid.getnode()}_{platform.processor()}"
    return hashlib.sha256(combined.encode()).hexdigest()[:12]

def test_login(email, password):
    hwid = get_hwid()
    payload = {
        "action": "login",
        "email": email,
        "password": password,
        "hwid": hwid
    }
    print(f"Testando login para {email} com HWID {hwid}...")
    try:
        response = requests.post(GAS_URL, json=payload, allow_redirects=True, timeout=15)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Resposta: {json.dumps(data, indent=2)}")
            return data.get("success")
        else:
            print(f"Erro: {response.text}")
    except Exception as e:
        print(f"Erro de conexão: {e}")
    return False

if __name__ == "__main__":
    test_login("admin@vigas.com", "123456")
