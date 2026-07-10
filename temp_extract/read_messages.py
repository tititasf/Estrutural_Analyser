import json

path = r'D:\Agente-cad-PYSIDE\temp_extract\58794338-fb03-4a6b-909f-8f32189aa0b4.jsonl'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

user_messages = []
for line in lines:
    try:
        data = json.loads(line)
        if data.get('type') == 'user':
            msg = data.get('message', {})
            content = msg.get('content', [])
            
            is_tool_result = all(isinstance(c, dict) and c.get('type') == 'tool_result' for c in content)
            if not is_tool_result:
                user_messages.append(data)
    except Exception as e:
        pass

for i, m in enumerate(user_messages[-5:]):
    print(f"\n--- USER MESSAGE {i+1} ---")
    content = m.get('message', {}).get('content', [])
    if isinstance(content, str):
        print(f"TEXT: {content}")
        continue
    for c in content:
        if isinstance(c, dict):
            if c.get('type') == 'text':
                print(f"TEXT: {c.get('text')}")
            elif c.get('type') == 'image':
                img_source = c.get('source', {})
                print(f"IMAGE: format={img_source.get('media_type')}, size={len(img_source.get('data', ''))}")
                if img_source.get('data'):
                    import base64
                    ext = img_source.get("media_type", "image/png").split("/")[-1]
                    img_path = f'D:\\Agente-cad-PYSIDE\\temp_extract\\image_{i}.{ext}'
                    with open(img_path, 'wb') as img_f:
                        img_f.write(base64.b64decode(img_source.get('data')))
                    print(f"Saved image to {img_path}")
            else:
                pass
        elif isinstance(c, str):
            print(f"TEXT: {c}")
