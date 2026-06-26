import requests
url = "https://tdxxqechpnqbrpsydvzd.supabase.co/storage/v1/object/public/updates/AgenteCAD-1.0.1.tar.gz.part1"
print(f"Testing 100KB Range Request on: {url}")
headers = {"Range": "bytes=0-102399"} 
try:
    resp = requests.get(url, headers=headers, timeout=10, verify=False)
    print(f"Status: {resp.status_code}")
    print(f"Size received: {len(resp.content)} bytes")
    if resp.status_code == 206:
        print("✅ 100KB success!")
    else:
        print(f"❌ Failed with status {resp.status_code}")
except Exception as e:
    print(f"❌ 100KB failed: {e}")
