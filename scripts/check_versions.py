import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import requests
from src import config
from tufup.client import Client

# --- SUPABASE 400->404 PATCH ---
_orig_request = requests.Session.request
def patched_request(self, method, url, *args, **kwargs):
    resp = _orig_request(self, method, url, *args, **kwargs)
    if resp.status_code == 400 and "not_found" in resp.text:
        resp.status_code = 404
    return resp
requests.Session.request = patched_request
# -------------------------------

META_DIR = Path("dist_v1/metadata")
TARGET_DIR = Path("dist_v1/downloads")
INSTALL_DIR = Path("dist_v1")

print(f"Checking versions in {META_DIR}...")
client = Client(
    app_name=config.APP_NAME,
    current_version="1.0.0", # Force 1.0.0 for comparison
    metadata_dir=str(META_DIR),
    metadata_base_url=config.UPDATE_METADATA_URL,
    target_dir=str(TARGET_DIR),
    target_base_url=config.UPDATE_TARGETS_URL,
    app_install_dir=str(INSTALL_DIR)
)

print("Checking for updates via TUF...")
info = client.check_for_updates()
if info:
    print(f"Update Found: {info.name} (v{info.version})")
else:
    print("No update found.")

# List local targets
targets_path = Path(config.METADATA_DIR) / "targets.json"
if targets_path.exists():
    print(f"Local targets.json exists. Content version: ...")
    with open(targets_path, 'r') as f:
        print(f.read())
else:
    print("Local targets.json NOT found.")
