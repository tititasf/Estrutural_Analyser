"""Corrige somente diretórios derivados criados por auditorias antigas como root."""
from pathlib import Path
import os
import pwd

root = Path('/opt/cad-analyzer/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/n3_cut_inventory').resolve()
user = pwd.getpwnam('cadapp')
count = 0
for path in [root, *root.rglob('*')]:
    assert path.resolve().is_relative_to(root)
    if path.is_dir() and path.stat().st_uid == 0:
        os.chown(path, user.pw_uid, user.pw_gid)
        count += 1
print('Derived directories corrected', count)
