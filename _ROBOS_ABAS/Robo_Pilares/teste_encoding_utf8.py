"""
Teste rápido de encoding UTF-8
"""

import os
import sys
import io

# Configurar encoding UTF-8 para Windows
if sys.platform == 'win32':
    try:
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        elif hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        elif hasattr(sys.stderr, 'buffer') and not isinstance(sys.stderr, io.TextIOWrapper):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception as e:
        print(f"Erro ao configurar encoding: {e}")

# Testar prints com acentos e emojis
print("Teste de encoding UTF-8")
print("Acentos: painéis, nível, coração")
print("Emojis: ✅ ❌ ⚠️ 🔍")
print("Teste concluído com sucesso!")
