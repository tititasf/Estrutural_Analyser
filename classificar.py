import os
import re

directories = [
    r"D:\Agente-cad-PYSIDE\minhas_mensagens_agy",
    r"D:\Agente-cad-PYSIDE\minhas_mensagens_codex",
    r"D:\Agente-cad-PYSIDE\minhas_mensagens_claude"
]

classes = {
    "SA": ["sa", "structural", "analyser", "analisador"],
    "N1_N3": ["n1", "n3"],
    "N2_N4": ["n2", "n4"],
    "N5": ["n5"],
    "Visual_Desenho": ["visual", "desenho", "dxf", "layer", "cota", "cor", "hachura", "linha", "texto", "ui", "interface"],
    "Interpretacao_Semantica": ["interpreta", "semantica", "compreens", "logica", "entende"],
    "Design_Comportamento": ["design", "comportamento", "acao", "interacao", "fluxo", "regra"],
    "Robo": ["robo", "robô", "automacao", "agente", "bot"]
}

categorized = {k: [] for k in classes.keys()}
categorized["Outros"] = []

def classify(msg):
    msg_lower = msg.lower()
    assigned = []
    for cls, keywords in classes.items():
        if any(kw in msg_lower for kw in keywords):
            assigned.append(cls)
    
    if not assigned:
        return ["Outros"]
    return assigned

for d in directories:
    if not os.path.exists(d):
        continue
    for f in os.listdir(d):
        if f.endswith(".txt"):
            filepath = os.path.join(d, f)
            with open(filepath, 'r', encoding='utf-8') as file:
                content = file.read()
                # Messages are separated by "\n\n---\n\n"
                msgs = content.split("---\n\n")
                for m in msgs:
                    m = m.strip()
                    if len(m) > 15: # Ignore very short messages like "oi", "sim"
                        cats = classify(m)
                        for c in cats:
                            categorized[c].append(m)

# Write a summarized report
output_file = r"D:\Agente-cad-PYSIDE\analise_classificada.txt"
with open(output_file, 'w', encoding='utf-8') as out:
    for cls, msgs in categorized.items():
        # Remove duplicates
        unique_msgs = list(set(msgs))
        out.write(f"=== CLASSE: {cls} (Total: {len(unique_msgs)}) ===\n")
        # Write up to 20 representative messages to avoid huge file
        for m in unique_msgs[:20]:
            # Replace newlines with space to keep it compact
            m_compact = m.replace("\n", " ")
            out.write(f"- {m_compact}\n")
        out.write("\n")

print(f"Analysis saved to {output_file}")
