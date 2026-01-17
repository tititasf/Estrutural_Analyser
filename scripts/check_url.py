
import requests

url = "https://vxkSbNoyzGkYyPsTyhIe.supabase.co/storage/v1/object/public/repository/2.root.json"
print(f"Checking {url}...")
resp = requests.get(url)
print(f"Status Code: {resp.status_code}")
print(f"Content: {resp.text[:100]}")
