import re
path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\obra_detalhe.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# The code in obra_detalhe.html looks like this:
# {% if not eh_obra_rapida %}
# ... (lots of code for miller column)
# {% else %}
# ... (processamento rapido code)
# {% endif %}

# We will use regex to capture the parts.
match = re.search(r'\{%\s*if not eh_obra_rapida\s*%\}\s*(.*?)\s*\{%\s*else\s*%\}\s*<section aria-labelledby="et1".*?\{%\s*endif\s*%\}', content, re.DOTALL)
if match:
    miller_column_code = match.group(1)
    new_content = content[:match.start()] + miller_column_code + content[match.end():]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Successfully removed the if/else block and kept only the Miller column code.")
else:
    print("Could not find the eh_obra_rapida if/else block!")
