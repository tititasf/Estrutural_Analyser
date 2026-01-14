import requests
import json
import hashlib
import platform
import uuid
import os

class LicensingService:
    # URL do Web App gerado após o Deploy do Google Apps Script
    # O usuário deve colar aqui o URL fornecido pelo Google
    GAS_URL = "https://script.google.com/macros/s/AKfycbxHlT39nnCR7GEMUWr4y7sacwTcIIwZhlxoP4VABIJTPaglsHMPH-sNZy2x4elclmoL8Q/exec"

    def __init__(self):
        self.user_data = None
        self.hwid = self._get_hwid()

    def _get_hwid(self):
        try:
            combined = f"{platform.node()}_{uuid.getnode()}_{platform.processor()}"
            return hashlib.sha256(combined.encode()).hexdigest()[:12]
        except:
            return "unknown_hwid"

    def login(self, email, password):
        payload = {
            "action": "login",
            "email": email,
            "password": password,
            "hwid": self.hwid
        }
        try:
            # allow_redirects=True é essencial para GAS
            response = requests.post(self.GAS_URL, json=payload, allow_redirects=True, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.user_data = data.get("userData")
                    return True, "Login realizado com sucesso!"
                return False, data.get("message", "Erro desconhecido")
            return False, f"Servidor retornou erro {response.status_code}"
        except Exception as e:
            return False, f"Falha na conexão: {str(e)}"

    def consume_credits(self, m2_amount):
        if not self.user_data:
            return False, "Usuário não logado."
        
        payload = {
            "action": "consume",
            "email": self.user_data['email'],
            "amount": m2_amount
        }
        try:
            response = requests.post(self.GAS_URL, json=payload, allow_redirects=True, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.user_data['creditos'] = data.get("remaining")
                    return True, f"Créditos consumidos. Restante: {data.get('remaining'):.2f} m²"
                return False, data.get("message", "Saldo insuficiente ou erro.")
            return False, "Erro na comunicação com servidor."
        except Exception as e:
            return False, f"Falha na conexão: {str(e)}"

    def save_session(self):
        if self.user_data:
            with open(".session_v2", "w") as f:
                json.dump(self.user_data, f)

    def load_session(self):
        if os.path.exists(".session_v2"):
            try:
                with open(".session_v2", "r") as f:
                    self.user_data = json.load(f)
                return True
            except:
                return False
        return False

    def logout(self):
        self.user_data = None
        if os.path.exists(".session_v2"):
            os.remove(".session_v2")
