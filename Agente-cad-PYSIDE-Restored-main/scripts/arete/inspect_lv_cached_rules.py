"""Inspect cached LV Python code and PyInstaller archives; never execute them."""
from pathlib import Path
import marshal,types,dis,struct,zlib,importlib.util
root=Path(__file__).resolve().parents[2]
out=root/'scripts/arete/relatorios/20261001_lv_cut_fittings/cached_rules.txt'
chunks=[]
def inspect(code,label):
    chunks.append(f'SOURCE {label}')
    def walk(c):
        strings=[s for s in c.co_consts if isinstance(s,str)]
        if any(any(k in s.lower() for k in ('par_int','par_fundo','parafus','ancoragem')) for s in strings) or 'corte' in c.co_name.lower():
            chunks.append(f'FUNCTION {c.co_name} line={c.co_firstlineno} names={c.co_names}')
            chunks.append(dis.Bytecode(c).dis())
        for item in c.co_consts:
            if isinstance(item,types.CodeType):walk(item)
    walk(code)
for base in (root/'_ROBOS_ABAS/Robo_Laterais_de_Vigas',root.parent/'_ROBOS_ABAS/Robo_Laterais_de_Vigas'):
    for p in base.rglob('*gerador*.cpython-312.pyc'):
        inspect(marshal.loads(p.read_bytes()[16:]),str(p))
    for p in base.rglob('*.pyz'):
        raw=p.read_bytes()
        print('PYZ',p,'magic',raw[4:8].hex(),'runtime',importlib.util.MAGIC_NUMBER.hex())
        if raw[4:8]!=importlib.util.MAGIC_NUMBER:continue
        toc=marshal.loads(raw[struct.unpack('!i',raw[8:12])[0]:])
        entries=toc.items() if isinstance(toc,dict) else toc
        for name,(kind,offset,size) in entries:
            if 'gerador' in name.lower() and ('viga' in name.lower() or 'lateral' in name.lower()):
                inspect(marshal.loads(zlib.decompress(raw[offset:offset+size])),f'{p}:{name}')
out.write_text('\n'.join(chunks),encoding='utf8')
print('WROTE',out,'lines',sum(s.count('\n')+1 for s in chunks))
