import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import requests
from src import config

urls = [
    config.UPDATE_METADATA_URL + "/root.json",
    config.UPDATE_METADATA_URL + "/2.root.json",
    config.UPDATE_TARGETS_URL + "/AgenteCAD-1.0.1.tar.gz.part1",
    config.UPDATE_TARGETS_URL + "/AgenteCAD-1.0.1.tar.gz.part2",
    config.UPDATE_TARGETS_URL + "/AgenteCAD-1.0.1.tar.gz.part3",
    config.UPDATE_TARGETS_URL + "/AgenteCAD-1.0.1.tar.gz.part4",
    config.UPDATE_TARGETS_URL + "/AgenteCAD-1.0.1.tar.gz.part5",
]

for url in urls:
    print(f"\nChecking {url}...")
    try:
        resp = requests.head(url)
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            size_mb = int(resp.headers.get('Content-Length', 0)) / (1024*1024)
            print(f"Size: {size_mb:.2f} MB")
        else:
            # Try GET to see error message
            resp_get = requests.get(url)
            print(f"GET Error: {resp_get.text}")
    except Exception as e:
        print(f"Request failed: {e}")
