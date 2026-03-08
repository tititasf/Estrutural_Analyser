import urllib.request
import time

url = "https://tdxxqechpnqbrpsydvzd.supabase.co/storage/v1/object/public/updates/AgenteCAD-1.0.1.tar.gz.part1"
print(f"Testing urllib download of {url}")

try:
    with urllib.request.urlopen(url, timeout=30) as response:
        print(f"Status: {response.status}")
        total = 0
        with open("test_urllib.tmp", "wb") as f:
            while True:
                chunk = response.read(1024*1024)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
                print(f"   Downloaded {total / (1024*1024):.2f} MB", end="\r")
    print("\n✅ Success!")
except Exception as e:
    print(f"\n❌ Failed: {e}")
