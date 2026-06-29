import re

files = [
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\src\ui\modules\diagnostic_hub.py",
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\src\ui\modules\diagnostic_reverse_hub.py"
]

for f in files:
    with open(f, "r", encoding="utf-8") as file:
        content = file.read()
    
    # Increase alphas
    content = content.replace("rgba(180, 120, 0, 38)", "rgba(180, 120, 0, 160)")
    content = content.replace("rgba(180, 120, 0, 71)", "rgba(180, 120, 0, 230)")
    
    content = content.replace("rgba(120, 60, 180, 38)", "rgba(120, 60, 180, 160)")
    content = content.replace("rgba(120, 60, 180, 71)", "rgba(120, 60, 180, 230)")
    
    content = content.replace("rgba(0, 180, 180, 38)", "rgba(0, 180, 180, 160)")
    content = content.replace("rgba(0, 180, 180, 71)", "rgba(0, 180, 180, 230)")
    
    content = content.replace("rgba(0, 200, 120, 31)", "rgba(0, 200, 120, 160)")
    content = content.replace("rgba(0, 200, 120, 71)", "rgba(0, 200, 120, 230)")
    
    content = content.replace("rgba(255, 80, 80, 26)", "rgba(255, 80, 80, 160)")
    content = content.replace("rgba(255, 80, 80, 64)", "rgba(255, 80, 80, 230)")
    content = content.replace("rgba(255, 80, 80, 71)", "rgba(255, 80, 80, 230)")
    
    content = content.replace("rgba(180, 80, 200, 31)", "rgba(180, 80, 200, 160)")
    content = content.replace("rgba(180, 80, 200, 64)", "rgba(180, 80, 200, 230)")
    
    content = content.replace("rgba(220, 50, 50, 31)", "rgba(220, 50, 50, 160)")
    content = content.replace("rgba(220, 50, 50, 64)", "rgba(220, 50, 50, 230)")
    
    content = content.replace("rgba(80, 80, 220, 31)", "rgba(80, 80, 220, 160)")
    content = content.replace("rgba(80, 80, 220, 71)", "rgba(80, 80, 220, 230)")
    
    # We should also ensure the text colors are mostly bright if the background is solid.
    # The text color usually relies on Accent colors like Colors.ACCENT_TEAL, which is bright enough against dark.
    # But since they are somewhat translucent, the white text would look better? 
    # Let's keep the user's specific color variables because he explicitly liked the button styles of Diagnostic Pre, just asked for them to be more solid.
    
    with open(f, "w", encoding="utf-8") as file:
        file.write(content)
