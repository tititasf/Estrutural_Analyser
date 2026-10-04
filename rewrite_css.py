import os

file_path = 'd:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/consulta-publica-web/app/pavimento/[code]/page.module.css'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Make it look more professional and engineering-focused (CAD analyzer aesthetic)
replacements = {
    'border-radius: 12px;': 'border-radius: 4px;',
    'border-radius: 8px;': 'border-radius: 4px;',
    'border-radius: 6px;': 'border-radius: 4px;',
    'box-shadow: 0 4px 24px rgba(0, 0, 0, 0.04);': 'box-shadow: 0 1px 4px rgba(0,0,0,0.08); border-left: 1px solid var(--border); border-right: 1px solid var(--border);',
    'aspect-ratio: 1;': 'aspect-ratio: 1; min-height: 80px;',
    'grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));': 'grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));',
    'gap: 12px;': 'gap: 8px;',
    'background: rgba(11, 77, 162, 0.08);': 'background: var(--surface-2); border: 1px solid var(--border);',
    'padding: 10px;': 'padding: 8px;',
    'font-size: 15px;': 'font-size: 13px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;',
    'font-weight: 700;': 'font-weight: 600;',
    'box-shadow: 0 2px 6px rgba(0,0,0,0.02);': '',
    'box-shadow: 0 6px 16px rgba(11, 77, 162, 0.1);': 'box-shadow: 0 2px 8px rgba(0,0,0,0.08);',
    'border: 1px dashed var(--border);': 'border: 1px solid var(--border);',
    'border: 1px dashed var(--primary);': 'border: 1px solid var(--border); color: var(--fg);',
    'background-color: var(--surface-1);': 'background-color: var(--surface-0);',
    'padding: 20px 20px 0 20px;': 'padding: 16px 20px 0 20px;'
}

for old, new in replacements.items():
    content = content.replace(old, new)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
