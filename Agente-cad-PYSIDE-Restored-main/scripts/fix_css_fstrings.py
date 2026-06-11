#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix broken f-string CSS braces: Colors.TOKEN}}; rest }  -> Colors.TOKEN}; rest }}"""
import re
import pathlib

files = [
    'src/ui/widgets/detail_card.py',
    'src/ui/widgets/project_manager.py',
]

# Pattern: {Colors.TOKEN}}; ... }" at end of stylesheet call
# The broken pattern results in Colors.TOKEN}} where }} closes the Python expr AND adds one }
# Correct: Colors.TOKEN}; ... }}  (single } closes Python, double }} is CSS close)
PATTERN = re.compile(r'\{(Colors\.[A-Z_]+)\}\}(;[^"]*)\}"')

def fix_match(m):
    return '{' + m.group(1) + '}' + m.group(2) + '}}"'

for fname in files:
    p = pathlib.Path(fname)
    text = p.read_text(encoding='utf-8')
    original = text

    # Fix pattern 1: Colors.TOKEN}}; rest_css }"  ->  Colors.TOKEN}; rest_css }}"
    text = PATTERN.sub(fix_match, text)

    # Fix pattern 2: Colors.TOKEN}}; }"  ->  Colors.TOKEN}; }}"  (no rest)
    text = re.sub(r'\{(Colors\.[A-Z_]+)\}\}; \}"', r'{\1}; }}"', text)

    if text != original:
        p.write_text(text, encoding='utf-8')
        print(f'Fixed: {fname}')
    else:
        print(f'No change: {fname}')

print('Done.')
