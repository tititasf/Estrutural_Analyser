import tarfile
from pathlib import Path

tar_path = Path("repository/targets/AgenteCAD-1.0.0.tar.gz")

def inspect():
    if not tar_path.exists():
        print(f"❌ File not found: {tar_path}")
        return

    print(f"📦 Inspecting {tar_path}...")
    try:
        with tarfile.open(tar_path, "r:gz") as tar:
            members = tar.getmembers()
            print(f"   Contains {len(members)} files.")
            print("   Top 10 files by size:")
            sorted_members = sorted(members, key=lambda m: m.size, reverse=True)
            for m in sorted_members[:10]:
                print(f"   - {m.name}: {m.size/1024/1024:.2f} MB")
                
            # Check for main.exe
            exe_found = any(m.name.endswith("main.exe") for m in members)
            print(f"\n   Found main.exe? {'✅ YES' if exe_found else '❌ NO'}")
            
    except Exception as e:
        print(f"❌ Error opening tar: {e}")

if __name__ == "__main__":
    inspect()
