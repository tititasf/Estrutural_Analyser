import math

data = {
    "V302": {"len_h": 3490, "dist_h": 3.2, "len_v": 1159, "dist_v": 2.8, "true": "H"},
    "V332": {"len_h": 3490, "dist_h": 10.0, "len_v": 546, "dist_v": 21.5, "true": "H"},
    "V330": {"len_h": 3490, "dist_h": 2.8, "len_v": 1337, "dist_v": 5.7, "true": "H"},
    "V325": {"len_h": 3490, "dist_h": 14.7, "len_v": 1244, "dist_v": 0.9, "true": "H"},
    "V322": {"len_h": 3490, "dist_h": 15.0, "len_v": 1244, "dist_v": 3.8, "true": "V"},
    "V320": {"len_h": 3490, "dist_h": 15.0, "len_v": 1244, "dist_v": 3.8, "true": "V"},
    "V312": {"len_h": 3490, "dist_h": 26.4, "len_v": 1244, "dist_v": 3.8, "true": "V"},
    "V303": {"len_h": 3344, "dist_h": 3.8, "len_v": 757, "dist_v": 15.0, "true": "H"},
    "V301": {"len_h": 3374, "dist_h": 3.8, "len_v": 1194, "dist_v": 15.0, "true": "H"},
}

cap = 10.0
power = 2.6

correct = 0
for name, d in data.items():
    sh = d["len_h"] / (max(cap, d["dist_h"]) ** power)
    sv = d["len_v"] / (max(cap, d["dist_v"]) ** power)
    pred = "H" if sh >= sv else "V"
    if pred == d["true"]:
        correct += 1
    print(f"{name:5s}: true={d['true']} pred={pred} | sh={sh:.1f} sv={sv:.1f}")

print(f"\nAccuracy: {correct}/{len(data)}")
