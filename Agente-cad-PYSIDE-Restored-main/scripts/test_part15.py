import requests
url = "https://tdxxqechpnqbrpsydvzd.supabase.co/storage/v1/object/public/updates/AgenteCAD-1.0.1.tar.gz.part15"
print(f"Testing isolated download of part 15: {url}")
try:
    resp = requests.get(url, timeout=30)
    print(f"Status: {resp.status_code}")
    print(f"Size: {len(resp.content)} bytes")
    if resp.status_code == 200:
        print("✅ Success!")
    else:
        print(f"❌ Failed: {resp.text}")
except Exception as e:
    print(f"❌ Failed: {e}")
