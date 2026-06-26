import requests
import sys
url = "https://tdxxqechpnqbrpsydvzd.supabase.co/storage/v1/object/public/updates/AgenteCAD-1.0.1.tar.gz.part1"
print(f"Testing download of {url}")
try:
    resp = requests.get(url, stream=True, timeout=30)
    print(f"Status: {resp.status_code}")
    total = 0
    with open("test_part1.tmp", "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024*1024):
            if chunk:
                f.write(chunk)
                total += len(chunk)
                print(f"   Downloaded {total / (1024*1024):.2f} MB", end="\r")
    print("\n✅ Success!")
except Exception as e:
    print(f"\n❌ Failed: {e}")
