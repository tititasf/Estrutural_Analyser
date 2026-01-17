from PIL import Image
import os

def convert_to_ico():
    source_path = r"assets/image copy 3.png"
    dest_path = r"assets/icon.ico"
    
    if not os.path.exists(source_path):
        print(f"❌ Source file not found: {source_path}")
        return

    try:
        img = Image.open(source_path)
        # Resize to standard icon sizes for Windows
        icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
        
        img.save(dest_path, format='ICO', sizes=icon_sizes)
        print(f"✅ Converted '{source_path}' to '{dest_path}'")
    except Exception as e:
        print(f"❌ Error converting image: {e}")

if __name__ == "__main__":
    convert_to_ico()
