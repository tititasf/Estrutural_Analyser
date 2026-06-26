
import sys
import logging
from pathlib import Path
from tufup.client import Client

import requests
import time
import os
import logging

# --- SUPABASE 400->404 & CHUNK REASSEMBLY PATCH ---
_orig_request = requests.Session.request
def patched_request(self, method, url, *args, **kwargs):
    resp = _orig_request(self, method, url, *args, **kwargs)
    
    # Handle Supabase 400 -> 404
    if resp.status_code == 400 and "not_found" in resp.text:
        resp.status_code = 404
    
    # Handle Chunk Reassembly for .tar.gz
    if resp.status_code == 404 and url.endswith(".tar.gz") and method.upper() == "GET":
        part1_url = f"{url}.part1"
        print(f"DEBUG PATCH: 404 for {url}. Checking for chunks: {part1_url}")
        
        with requests.Session() as s:
            p1_resp = s.head(part1_url, timeout=10)
            if p1_resp.status_code != 200:
                return resp

        print(f"DEBUG PATCH: Chunked archive detected. Starting ultra-robust reassembly...")
        temp_dir = Path("dist_v1/downloads")
        temp_dir.mkdir(parents=True, exist_ok=True)
        tmp_archive = temp_dir / "reassembled_archive.tmp"
        
        total_size = 0
        part_num = 1
        
        try:
            with open(tmp_archive, 'wb') as outfile:
                while True:
                    part_url = f"{url}.part{part_num}"
                    print(f"   Fetching part {part_num}: {part_url}")
                    
                    success = False
                    for attempt in range(1, 11): # 10 retries
                        try:
                            with requests.Session() as s_part:
                                s_part.headers.update({"Connection": "close"})
                                p_resp = s_part.get(part_url, stream=True, timeout=30)
                                if p_resp.status_code != 200:
                                    break
                                
                                p_size = 0
                                for chunk in p_resp.iter_content(chunk_size=128*1024):
                                    if chunk:
                                        outfile.write(chunk)
                                        p_size += len(chunk)
                            
                            print(f"   Downloaded {p_size} bytes for part {part_num}")
                            total_size += p_size
                            success = True
                            break
                        except Exception as e:
                            print(f"   Attempt {attempt} failed for part {part_num}: {e}")
                            time.sleep(1 * attempt)
                    
                    if not success:
                        break
                    part_num += 1
            
            if total_size > 0:
                print(f"DEBUG PATCH: Successfully reassembled {total_size} bytes total into {tmp_archive}")
                with open(tmp_archive, 'rb') as f:
                    content = f.read()
                
                mock_resp = requests.Response()
                mock_resp.status_code = 200
                mock_resp._content = content
                mock_resp.url = url
                mock_resp.headers['Content-Length'] = str(total_size)
                return mock_resp
        except Exception as ef:
            print(f"DEBUG PATCH: Reassembly failed: {ef}")
            
    return resp
requests.Session.request = patched_request
# -------------------------------

# Import local config
sys.path.append(str(Path.cwd()))
from src import config

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# Paths
ROOT_DIR = Path.cwd()
DIST_V1_DIR = ROOT_DIR / "dist_v1"
METADATA_DIR = DIST_V1_DIR / "metadata"
TARGET_DIR = DIST_V1_DIR / "downloads"
KEYS_DIR = DIST_V1_DIR / "keys"

def test_client():
    current_ver = "1.0.0" # Mocking the old version
    print(f"Testing Client with version {current_ver}")
    print(f"Update URL: {config.UPDATE_METADATA_URL}")
    
    # Ensure metadata dir exists
    if not METADATA_DIR.exists():
        print("Metadata dir missing!")
        return

    public_key = KEYS_DIR / "timestamp.pub"
    
    try:
        client = Client(
            app_name=config.APP_NAME,
            current_version=current_ver,
            metadata_dir=str(METADATA_DIR),
            metadata_base_url=config.UPDATE_METADATA_URL,
            target_dir=str(TARGET_DIR),
            target_base_url=config.UPDATE_TARGETS_URL,
            app_install_dir=str(DIST_V1_DIR)
        )
        
        print("Client initialized.")
        print("Checking for updates...")
        update = client.check_for_updates()
        if update:
            print(f"✅ Update found: {update}")
            print(f"Version: {update.version}")
            print("🚀 Downloading update...")
            # We use download_and_apply_update but we expect it to fail at the 
            # 'apply' step because we are running as a script, not an exe.
            # But it will still download the parts!
            try:
                client.download_and_apply_update()
                print("✅ Download/Apply process completed.")
            except Exception as e:
                print(f"Apply failed (expected for script): {e}")
        else:
            print("❌ No updates found.")
            
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_client()
