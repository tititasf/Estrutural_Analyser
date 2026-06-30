import sqlite3, json
conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
cur = conn.cursor()
cur.execute("SELECT campos_json FROM reverse_eng_fichas WHERE classe='LAJ' AND elemento_id='L315' ORDER BY created_at DESC")
row = cur.fetchone()
if row:
    fc = json.loads(row[0])
    ficha_clean = {
        k: v for k, v in fc.items()
        if not k.startswith('_') or k in {"_hlaz", "_stog_pose"}
    }
    with open('test_ficha.json', 'w', encoding='utf-8') as f:
        json.dump(ficha_clean, f, indent=2, ensure_ascii=False)
    print("Saved test_ficha.json")
else:
    print("Not found in DB")
