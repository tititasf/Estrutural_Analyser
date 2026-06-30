import os
import json
import base64
import time
from openai import OpenAI

def main():
    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        print("WARNING: NVIDIA_API_KEY not found in environment!")
        sys.exit(1)

    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key
    )

    report_path = "D:/Agente-cad-PYSIDE/validacao_visual/engrev_laj_recorte_loop/engrev_laj_recorte_loop_report.json"
    if not os.path.exists(report_path):
        print(f"Report not found: {report_path}")
        return

    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    items = data.get("items", data)
    targets = [x for x in items if x.get("status") in ["FAIL", "NEAR"]]
    
    print(f"Found {len(targets)} lajes with attention points (FAIL/NEAR).")

    results = []

    for item in targets:
        laje_id = item["id"]
        print(f"\nProcessing Laje: {laje_id}")
        image_path = f"D:/Agente-cad-PYSIDE/test_output/arete_lj/visual_audit_13_PAV/items/ARETE_LJ_{laje_id}_audit.png"
        
        if not os.path.exists(image_path):
            print(f"  -> Image not found: {image_path}")
            continue

        with open(image_path, "rb") as img_f:
            img_b64 = base64.b64encode(img_f.read()).decode()

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

        try:
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
            
            content = response.choices[0].message.content
            print(f"  -> Vision Result: {content.strip()}")
            results.append({
                "id": laje_id,
                "status": item["status"],
                "gaps": item["gaps"],
                "vision_analysis": content
            })
            
            # rate limit
            time.sleep(2)
        except Exception as e:
            print(f"  -> API Error: {e}")

    out_file = "D:/Agente-cad-PYSIDE/validacao_visual/engrev_laj_recorte_loop/laje_vision_loop_results.json"
    with open(out_file, "w", encoding="utf-8") as out:
        json.dump(results, out, indent=2)
    print(f"\nSaved vision loop results to {out_file}")

if __name__ == "__main__":
    import sys
    main()
