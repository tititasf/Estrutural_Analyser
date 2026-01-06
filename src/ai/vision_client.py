import google.generativeai as genai
import os
import logging

class VisionClient:
    """
    Cliente para integração com Google Gemini (Vision/Text).
    """
    def __init__(self, api_key: str = None):
        if not api_key:
            api_key = os.getenv('GOOGLE_API_KEY')
            
        if not api_key:
            logging.warning("GOOGLE_API_KEY não encontrada. Funcionalidades de IA estarão limitadas.")
            self.model = None
        else:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')

    def analyze_geometry_text(self, geometry_desc: str) -> str:
        """Envia descrição da geometria para análise do Gemini."""
        if not self.model:
            return "IA não configurada."
            
        prompt = f"""
        Você é um engenheiro estrutural assistente.
        Analise a seguinte geometria de um elemento estrutural (Pilar/Viga) extraída de um DXF:
        
        {geometry_desc}
        
        Classifique o formato geométrico provável (Retangular, L, T, U, Z) e sugira melhorias na identificação.
        Responda em JSON.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logging.error(f"Erro na Gemini API: {e}")
            return "Erro na análise."
