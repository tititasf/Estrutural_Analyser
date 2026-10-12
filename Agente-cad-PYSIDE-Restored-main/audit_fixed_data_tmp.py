from pathlib import Path
s=Path('audit_all_tag_candidates.py').read_text(encoding='utf-8-sig').split('for p in pillars:\n path=')[0]
s=s.replace('tag_candidate_audit','tag_fixed_audit')
exec(s)
for name in ('P3','P8','P17'):
 p=report[name];print(name,p['face_beams'])
