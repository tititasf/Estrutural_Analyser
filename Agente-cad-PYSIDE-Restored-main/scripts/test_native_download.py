import ctypes
from ctypes import wintypes
import os

# Windows WinInet constants
INTERNET_OPEN_TYPE_DIRECT = 1
INTERNET_SERVICE_HTTP = 3
INTERNET_FLAG_RELOAD = 0x80000000
INTERNET_FLAG_SECURE = 0x00800000
INTERNET_FLAG_IGNORE_CERT_CN_INVALID = 0x00001000
INTERNET_FLAG_IGNORE_CERT_DATE_INVALID = 0x00002000

wininet = ctypes.windll.wininet

def download_file_wininet(url, output_path):
    print(f"Trying Native WinInet download: {url}")
    h_internet = wininet.InternetOpenW("AgenteCAD-Updater", INTERNET_OPEN_TYPE_DIRECT, None, None, 0)
    if not h_internet:
        print("Failed to open Internet session")
        return False
    
    # Simple URL open
    h_url = wininet.InternetOpenUrlW(h_internet, url, None, 0, 
                                     INTERNET_FLAG_RELOAD | INTERNET_FLAG_SECURE | 
                                     INTERNET_FLAG_IGNORE_CERT_CN_INVALID | INTERNET_FLAG_IGNORE_CERT_DATE_INVALID, 0)
    
    if not h_url:
        err = ctypes.GetLastError()
        print(f"Failed to open URL. Error: {err}")
        wininet.InternetCloseHandle(h_internet)
        return False
    
    success = False
    try:
        with open(output_path, "wb") as f:
            buffer_size = 64 * 1024
            buffer = ctypes.create_string_buffer(buffer_size)
            bytes_read = wintypes.DWORD()
            total = 0
            
            while wininet.InternetReadFile(h_url, buffer, buffer_size, ctypes.byref(bytes_read)):
                if bytes_read.value == 0:
                    success = True
                    break
                f.write(buffer.raw[:bytes_read.value])
                total += bytes_read.value
                print(f"   Downloaded {total / (1024*1024):.2f} MB", end="\r")
        print(f"\n✅ Native Download Complete: {total} bytes")
    except Exception as e:
        print(f"\n❌ Native Download Failed: {e}")
    finally:
        wininet.InternetCloseHandle(h_url)
        wininet.InternetCloseHandle(h_internet)
    
    return success

if __name__ == "__main__":
    url = "https://tdxxqechpnqbrpsydvzd.supabase.co/storage/v1/object/public/updates/AgenteCAD-1.0.1.tar.gz.part1"
    download_file_wininet(url, "test_wininet.tmp")
