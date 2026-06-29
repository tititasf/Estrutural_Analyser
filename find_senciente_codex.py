import os
import json
import glob

sessions_dir = r"C:\Users\Thierry\.codex\sessions"
history_file = r"C:\Users\Thierry\.codex\history.jsonl"
target_keyword = "corporacao-senciente"

matched_sessions = set()

# Find all rollout files containing the keyword
for root, dirs, files in os.walk(sessions_dir):
    for file in files:
        if file.startswith("rollout-") and file.endswith(".jsonl"):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(4000)
                    if target_keyword in content.lower():
                        base = file[:-6] 
                        if len(base) >= 36:
                            session_id = base[-36:]
                            matched_sessions.add(session_id)
            except Exception as e:
                pass

conversations = {}

if os.path.exists(history_file):
    with open(history_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                session_id = data.get("session_id")
                text = data.get("text", "")
                ts = data.get("ts", 0)
                
                if session_id in matched_sessions and text:
                    if session_id not in conversations:
                        conversations[session_id] = []
                    conversations[session_id].append({"ts": ts, "text": text})
            except Exception as e:
                pass

if not conversations:
    print("No conversations found for corporacao-senciente.")
else:
    # Find the latest conversation by checking the maximum timestamp in each conversation
    latest_session = None
    max_ts = 0
    
    for session_id, msgs in conversations.items():
        session_max_ts = max(m["ts"] for m in msgs)
        if session_max_ts > max_ts:
            max_ts = session_max_ts
            latest_session = session_id
            
    print(f"Latest Session ID: {latest_session}")
    
    # Print the conversation of the latest session
    latest_msgs = conversations[latest_session]
    latest_msgs.sort(key=lambda x: x["ts"])
    
    output_file = r"D:\Agente-cad-PYSIDE\ultima_conversa_senciente.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        for m in latest_msgs:
            f.write(f"--- MSG ---\n{m['text']}\n\n")
            
    print(f"Conversation saved to {output_file}")
