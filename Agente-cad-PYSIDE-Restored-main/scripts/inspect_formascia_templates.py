from pathlib import Path
import ezdxf
from ezdxf import bbox
from collections import Counter
root=Path('D:/Agente-cad-PYSIDE/Exemplos Modos/FORMASCIA')
for name in ['INDICE E MOLDURA ABCD CIMA PILARES.dxf','INDICE GRADES PILARES.dxf','INDICE PRIMEIRA FOLHA PILARES ACBD CIMA.dxf','moldura e indice fundos.dxf','LAJES FORMACIA.dxf']:
 d=ezdxf.readfile(root/name);m=d.modelspace();b=bbox.extents(m,fast=True)
 print(name,'bbox',tuple(b.extmin),tuple(b.extmax),'layers',Counter(e.dxf.layer for e in m))
 for e in m:
  if e.dxftype()=='TEXT' and (e.dxf.layer.lower() in ('carimbo','texto','textos','folhas') or any(v in e.dxf.text.upper() for v in ['ÍND','IND','FOLHA','FORMASC','ESCALA'])):print('TXT',e.dxf.layer,repr(e.dxf.text),tuple(e.dxf.insert),e.dxf.height)
 print('frames')
 for e in m.query('LWPOLYLINE'):
  bb=bbox.extents([e]);
  if bb.size.x>1000 and bb.size.y>500: print(e.dxf.layer,e.closed,tuple(bb.extmin),tuple(bb.size))
