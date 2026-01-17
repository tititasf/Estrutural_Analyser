import requests
import time

def test_part(num):
    url = f"https://tdxxqechpnqbrpsydvzd.supabase.co/storage/v1/object/public/updates/AgenteCAD-1.0.1.tar.gz.part{num}"
    print(f"\n--- Testing Part {num} ---")
    for i in range(1, 6):
        try:
            print(f"   Attempt {i}...", end="")
            resp = requests.get(url, timeout=20)
            if resp.status_code == 200:
                print(f" SUCCESS! Received {len(resp.content)} bytes")
                return True
            else:
                print(f" FAIL {resp.status_code}")
        except Exception as e:
            print(f" ERROR: {str(e)[:50]}")
        time.sleep(1)
    return False

p14 = test_part(14)
p15 = test_part(15)

if p14 and not p15:
    print("\nCONCLUSION: Part 15 is LIKELY CORRUPTED or BLOCKED on server/network specifically.")
elif not p14 and not p15:
    print("\nCONCLUSION: Systemic SSL failure on machine/network.")
else:
    print("\nCONCLUSION: Intermittent failure.")
