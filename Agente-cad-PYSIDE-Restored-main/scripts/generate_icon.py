from PIL import Image, ImageDraw
import math

def draw_icon():
    size = (256, 256)
    # Background: Dark Gray/Black
    bg_color = (30, 30, 30)
    # Line Color: Cyan/Electric Blue
    line_color = (0, 229, 255)
    
    img = Image.new('RGB', size, bg_color)
    draw = ImageDraw.Draw(img)
    
    center = (128, 128)
    radius = 100
    
    # Sacred Geometry: Simplified Flower of Life / Hexagonal Structure
    
    # 1. Outer Circle
    draw.ellipse([center[0]-radius, center[1]-radius, center[0]+radius, center[1]+radius], outline=line_color, width=3)
    
    # 2. Hexagon
    vertices = []
    for i in range(6):
        angle_deg = 60 * i - 30
        angle_rad = math.radians(angle_deg)
        x = center[0] + radius * math.cos(angle_rad)
        y = center[1] + radius * math.sin(angle_rad)
        vertices.append((x, y))
    
    draw.polygon(vertices, outline=line_color, width=3)
    
    # 3. Inner Connections (Merkaba-ish)
    # Connect every vertex to the one 2 steps away (Star of David)
    star1 = [vertices[0], vertices[2], vertices[4]]
    star2 = [vertices[1], vertices[3], vertices[5]]
    
    draw.polygon(star1, outline=line_color, width=2)
    draw.polygon(star2, outline=line_color, width=2)
    
    # 4. Center Point
    r_inner = 10
    draw.ellipse([center[0]-r_inner, center[1]-r_inner, center[0]+r_inner, center[1]+r_inner], fill=line_color)
    
    # Save as ICO
    # Ensure assets dir exists
    import os
    if not os.path.exists('assets'):
        os.makedirs('assets')
        
    img.save('assets/icon.ico', format='ICO', sizes=[(256, 256)])
    print("✅ Icon generated: assets/icon.ico")

if __name__ == "__main__":
    draw_icon()
