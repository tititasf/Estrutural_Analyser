import urllib.request
url = "https://tdxxqechpnqbrpsydvzd.supabase.co/storage/v1/object/public/updates/AgenteCAD-1.0.0.tar.gz.part1"
print(f"Testing 1.0.0 part1: {url}")
try:
    with urllib.request.urlopen(url, timeout=30) as response:
        print(f"Status: {response.status}")
        total = 0
        while True:
            chunk = response.read(1024*1024)
            if not chunk: break
            total += len(chunk)
            print(f"   {total / (1024*1024):.2f} MB", end="\r")
    print("\n✅ Success!")
except Exception as e:
    print(f"\n❌ Failed: {e}")
