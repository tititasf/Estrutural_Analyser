from pathlib import Path
import difflib
root=Path('scripts/arete/relatorios/20261001_lv_n3_cortes')
for local,remote in [('portal/app/lv_ficha.py','remote_lv_ficha.txt'),('portal/app/static/lv_ficha.js','remote_lv_ficha_js.txt'),('portal/app/pipeline_runner.py','remote_pipeline.txt')]:
    diff=list(difflib.unified_diff((root/remote).read_text(encoding='utf8').splitlines(),Path(local).read_text(encoding='utf8').splitlines(),fromfile='remote',tofile=local))
    print(local,'\n'.join(diff)[:15000])
