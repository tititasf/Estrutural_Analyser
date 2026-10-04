from pathlib import Path
root=Path('_ROBOS_ABAS/Robo_Laterais_de_Vigas')
for filename in ['gerador_script_viga.py','robo_laterais_viga_limpo233.py','SCRIPTS/CENARIOS_VC_HEADLESS/VC-1_V01.scr','CONTEXTUALIZACAO_ROBO_LATERAIS_DE_VIGAS.md']:
    p=root/filename
    raw=p.read_bytes()
    enc='utf-16' if raw[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf8'
    s=raw.decode(enc,errors='replace');lines=s.splitlines()
    print('\nFILE',filename,'bytes',len(raw),'encoding',enc,'lines',len(lines))
    hits=[i for i,l in enumerate(lines) if any(k in l.lower() for k in ['parafus','par_int','par_fundo','par_esq','ancoragem'])]
    shown=set()
    for i in hits[:50]:
        for j in range(max(0,i-6),min(len(lines),i+10)):
            if j not in shown:
                print(f'{j+1}: {lines[j][:220]}');shown.add(j)
