import os
import re

path = 'main.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    'Ã£': 'ã',
    'Ã¡': 'á',
    'Ã©': 'é',
    'Ã³': 'ó',
    'Ã­': 'í',
    'Ã§': 'ç',
    'Ãª': 'ê',
    'Ãµ': 'õ',
    'Ãº': 'ú',
    'Ã¢': 'â',
    'Ã€': 'À',
    'Ã‰': 'É',
    'Ã“': 'Ó',
    'Ã ': 'Í',
    'Ãš': 'Ú',
    'Ã‡': 'Ç',
    'Ãƒ': 'Ã',
    'Ã”': 'Ô',
    'ÃŠ': 'Ê',
    'Ã‚': 'Â',
    'ǭ': 'á',
    'ǜ': 'ã',
    'Ǧ': 'é',
    'ǟ': 'Ã',
    'Ǹ': 'ê',
    'M"DULO': 'MÓDULO',
    'Nǜo': 'Não',
    'NǟO': 'NÃO',
    'aǜo': 'ação',
    'Aǜo': 'Ação'
}

for bad, good in replacements.items():
    content = content.replace(bad, good)

# Regex para consertar os ? e o. corrompidos
content = re.sub(r' \?\", \"Validado', ' ❌\", \"Validado', content)
content = re.sub(r' o\.\", \"Validado', ' ✔\", \"Validado', content)

# Regex genérico N?o
content = re.sub(r'N[^\w\s]o validado', 'Não validado', content)
content = re.sub(r'N[^\w\s]O VALIDADO', 'NÃO VALIDADO', content)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Reparo Concluido no main.py!')
