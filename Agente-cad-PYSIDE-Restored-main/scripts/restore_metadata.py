import requests
import os
from pathlib import Path

# Config
BASE_URL = "https://tdxxqechpnqbrpsydvzd.supabase.co/storage/v1/object/public/updates"
FILES = ["root.json", "timestamp.json", "snapshot.json", "targets.json"]
DEST = Path("dist_v1/metadata")
DEST.mkdir(parents=True, exist_ok=True)

for f in FILES:
    url = f"{BASE_URL}/{f}"
    print(f"Downloading {f}...")
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            with open(DEST / f, "wb") as out:
                out.write(resp.content)
            print(f"   Success")
        else:
            print(f"   Failed: {resp.status_code}")
    except Exception as e:
        print(f"   Error: {e}")
