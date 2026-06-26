import requests
url = "https://tdxxqechpnqbrpsydvzd.supabase.co/storage/v1/object/public/updates/AgenteCAD-1.0.1.tar.gz.part1"
print(f"Testing Range Request on: {url}")
headers = {"Range": "bytes=0-1048575"} # First 1MB
try:
    resp = requests.get(url, headers=headers, timeout=30)
    print(f"Status: {resp.status_code}") # Should be 206 Partial Content
    print(f"Size received: {len(resp.content)} bytes")
    print(f"Content-Range header: {resp.headers.get('Content-Range')}")
    if resp.status_code == 206:
        print("✅ Supabase supports Range requests!")
    else:
        print("❌ Supabase does not support Range requests (or returned different code).")
except Exception as e:
    print(f"❌ Test failed: {e}")
