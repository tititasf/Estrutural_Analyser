import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_setup_doc_declares_every_custom_linetype_used_by_pil():
    code = """
import sys
sys.path.insert(0, 'scripts')
import gerar_pl_dxf_stog as generator
doc = generator.setup_doc()
assert 'DASHED' in doc.linetypes
assert 'HIDDEN' in doc.linetypes
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
