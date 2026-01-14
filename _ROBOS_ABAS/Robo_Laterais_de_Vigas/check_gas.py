import requests
import json
import uuid
import platform

# Cole sua URL aqui para testar
GAS_URL = "https://script.google.com/macros/s/AKfycbxHlT39nnCR7GEMUWr4y7sacwTcIIwZhlxoP4VABIJTPaglsHMPH-sNZy2x4elclmoL8Q/exec"

def test_connection():
    if "SUA_URL" in GAS_URL:
        print("Erro: Você precisa colar a URL gerada no Google Sheets no topo deste script.")
        return

    print(f"Testando conexão com: {GAS_URL}")
    
    # Mock Data
    payload = {
        "action": "login",
        "email": "admin@vigas.com",
        "password": "123", # Password from GAS default population
        "hwid": "TEST_HWID_" + str(uuid.getnode())
    }

    try:
        response = requests.post(GAS_URL, json=payload, timeout=10)
        print(f"Status Code: {response.status_code}")
        print("Resposta do Servidor:")
        print(json.dumps(response.json(), indent=4, ensure_ascii=False))
        
        if response.json().get('success'):
            print("\n✅ SUCESSO! A comunicação com o Google Sheets está funcionando.")
        else:
            print(f"\n❌ ERRO NO SCRIPT: {response.json().get('message')}")
            
    except Exception as e:
        print(f"\n❌ ERRO DE CONEXÃO: {e}")
        print("\nDicas:")
        print("1. Verifique se você publicou o script como 'Qualquer pessoa' (Anyone).")
        print("2. Verifique se a URL termina com /exec")
        print("3. Verifique sua conexão com a internet.")

if __name__ == "__main__":
    test_connection()
