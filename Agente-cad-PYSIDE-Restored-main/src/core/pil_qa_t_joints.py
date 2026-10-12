"""Original T openings explain one missing wall without changing beam identity."""
import math,re

def prove_original_t_joint(scene,left,right,*,axis,positions,tolerance_cm):
    eps=tolerance_cm
    lo,hi=left['hi'],right['lo']
    if hi-lo<=eps:return None
    bottom,top=sorted(positions)
    transverse='y' if axis=='x' else 'x'
    candidates=[]
    for side,edge in enumerate((bottom,top)):
        opposite=1-side
        a,b=left['walls'][opposite],right['walls'][opposite]
        if not set(a['handles']).intersection(b['handles']):continue
        if not (a['lo']<=lo+eps and a['hi']>=hi-eps and b['lo']<=lo+eps and b['hi']>=hi-eps):continue
        # The interrupted edge ends exactly at the two incoming walls.
        if abs(left['walls'][side]['hi']-lo)>eps or abs(right['walls'][side]['lo']-hi)>eps:continue
        pairs=[]
        for p in (lo,hi):
            options=[w for w in scene['walls'] if w['axis']==transverse and abs(w['pos']-p)<=eps
                and ((side==1 and abs(w['lo']-edge)<=eps and w['hi']>edge+10)
                     or (side==0 and abs(w['hi']-edge)<=eps and w['lo']<edge-10))]
            if len(options)!=1:break
            pairs.append(options[0])
        if len(pairs)!=2:continue
        start,end=max(w['lo'] for w in pairs),min(w['hi'] for w in pairs)
        names=[t for t in scene['labels'] if re.fullmatch(r'(?:V|VF)\d+[A-Z]?',t['text'],re.I)
            and lo-t['margin']<=t[axis]<=hi+t['margin'] and start+eps<t[transverse]<end-eps
            and abs(math.sin(math.radians(t['rotation']-(90 if axis=='x' else 0))))<1e-6]
        if len({t['text'] for t in names})!=1:continue
        # A closed original piece still blocks the path; a T never bridges it.
        if any(s['bounds'][0 if axis=='x' else 2]<hi-eps and
               s['bounds'][1 if axis=='x' else 3]>lo+eps and
               s['bounds'][2 if axis=='x' else 0]<top-eps and
               s['bounds'][3 if axis=='x' else 1]>bottom+eps for s in scene['supports']):continue
        candidates.append(dict(kind='original_named_t_opening',span=[lo,hi],edge=edge,
            continuous_wall_handles=sorted(set(a['handles']) & set(b['handles'])),
            incoming_wall_handles=sorted({h for w in pairs for h in w['handles']}),
            incoming_name_handles=sorted({t['handle'] for t in names})))
    return candidates[0] if len(candidates)==1 else None
