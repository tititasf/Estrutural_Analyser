"""Explicit paper scales for the initial coherent iNi slab plan."""
from ezdxf import bbox

def windows(doc,width,height):
 box=bbox.extents(doc.modelspace())
 # Drawing cm at 1x means 1:50. Select only declared paper scales, keep
 # every entity and the complete SA arrangement, and expose the choice.
 for scale in (1.,.5,.25):
  if box.size.x*scale<=width and box.size.y*scale<=height:
   yield doc,dict(bounds=[box.extmin.x,box.extmin.y,box.extmax.x,box.extmax.y],scale=scale,paper_scale=f'1:{50/scale:g}')
   return
 raise ValueError('Planta coerente iNi excede os formatos declarados 1:50/1:100/1:200')
