import math

lines = [[(1198, 2991), (1603, 2991)]]
label_pos = (1212.8825, 3013.788)
center = label_pos

for line in lines:
    dx = line[-1][0] - line[0][0]
    dy = line[-1][1] - line[0][1]
    length = math.hypot(dx, dy)
    lc = (sum(p[0] for p in line)/2, sum(p[1] for p in line)/2)
    is_horizontal = True
    is_perpendicular = False
    is_closed = False
    
    is_valid_bottom = False
    if not is_closed and is_perpendicular and length <= 80:
        is_valid_bottom = True
    elif is_closed and not is_perpendicular:
        pass
    elif not is_closed and not is_perpendicular and length > 30:
        label_ref = label_pos or center
        print(f"Eval: dx={dx}, dy={dy}, length={length}")
        if dx > dy and dy < 5:
            dist_to_label = abs(lc[1] - label_ref[1])
            print(f"dist_to_label: {dist_to_label} (lc[1]={lc[1]}, label_ref={label_ref[1]})")
            if dist_to_label < 25.0:
                is_valid_bottom = True
                
    print(f"is_valid_bottom: {is_valid_bottom}")
