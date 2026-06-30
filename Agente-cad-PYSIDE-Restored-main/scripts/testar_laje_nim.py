import os
import json
import base64
from openai import OpenAI

api_key = os.environ.get("NVIDIA_API_KEY", "")
if not api_key:
    print("WARNING: NVIDIA_API_KEY not found in environment!")
    # Let's see if there is an alternative API key or just exit
    sys.exit(1)

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=api_key
)

def analyze_laje(image_path, laje_id):
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    prompt = f"""
Compare these two images of a LAJE structural formwork (Lançamento de Laje).
LEFT image = Reference (Engenharia Reversa N2). RIGHT image = Candidate (DXF N4 Gerado).
Laje ID: {laje_id}

Carefully observe:
1. Are there missing horizontal lines (linhas horizontais, sarrafos/paineis) in the RIGHT image compared to the LEFT?
2. Are there missing vertical lines (linhas verticais)?
3. Are the outline dimensions and text annotations (cotas) similar?

Provide a JSON output evaluating each criteria from 0 to 100 (where 100 is identical):
{{"linhas_horizontais_score": 0, "linhas_verticais_score": 0, "outline_score": 0, "cotas_score": 0, "missing_elements": [], "resumo": ""}}
"""

    response = client.chat.completions.create(
        model="meta/llama-3.2-90b-vision-instruct",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
            ]
        }],
        temperature=0.0,
        max_tokens=1024
    )

    print(f"Results for {laje_id}:")
    print(response.choices[0].message.content)

if __name__ == "__main__":
    import sys
    laje = sys.argv[1] if len(sys.argv) > 1 else "L316"
    path = f"D:/Agente-cad-PYSIDE/test_output/arete_lj/visual_audit_13_PAV/items/ARETE_LJ_{laje}_audit.png"
    if os.path.exists(path):
        analyze_laje(path, laje)
    else:
        print(f"File not found: {path}")
