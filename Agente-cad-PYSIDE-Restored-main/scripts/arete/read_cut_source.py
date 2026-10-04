from pathlib import Path
import sys
p=Path(sys.argv[1]); lines=p.read_text(encoding='utf8').splitlines()
a=int(sys.argv[2]) if len(sys.argv)>2 else 1
b=int(sys.argv[3]) if len(sys.argv)>3 else len(lines)
print('\n'.join(f'{i+1}: {line}' for i,line in enumerate(lines) if a<=i+1<=b))
