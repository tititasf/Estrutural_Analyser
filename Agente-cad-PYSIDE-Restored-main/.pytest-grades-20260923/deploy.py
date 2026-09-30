from hashlib import sha256
from pathlib import Path
from shutil import copy2
from os import replace

root = Path('/opt/cad-analyzer')
stage = root / 'ui-releases/20260923-pilares-grades-detail'
files = {
    'n1_routes.py': ('portal/app/routers/n1_routes.py', '05f2fb3f2ff9caceadad8d1e3fb09d3790deb9ee80018f339b495d1829ca098b', 'bec9702da9bd789adfc552431df4496943465a90681a7737e61c52d416995823'),
    'pillar_ficha.js': ('portal/app/static/pillar_ficha.js', 'a426fc19bba56427c5c3dc4685bd2cca003a6cf7c9e5e80bd55b2fd1a921d22c', '863acee7db1238c9025c9148a1608bee5727b8ca6a217e2c1dee932b1a72d3e1'),
    'pillar_ficha.css': ('portal/app/static/pillar_ficha.css', '92721da53e70b24d96dee76eb11431d71ff9014bff516ba30b91c68da8546727', 'c28d209e24c68c416f3114ba559580e11eeb43452dde2fd644197b60f30c9259'),
    'obra_detalhe.html': ('portal/app/templates/obra_detalhe.html', 'aab1eabfc69a71dea8ba99f868ee0d700f774a1bb7c0030d61b76815d344e02f', 'a3b3c4c9bd66e3d6de1e6837f8e9e94b9429eea7a975ab0677b7eaee4a9bd9a5'),
}

def digest(path):
    return sha256(path.read_bytes()).hexdigest()

for name, (relative, old, new) in files.items():
    assert digest(root / relative) == old, f'Live file changed: {relative}'
    assert digest(stage / name) == new, f'Staged file mismatch: {name}'

for name, (relative, _old, new) in files.items():
    destination = root / relative
    temporary = destination.with_name(destination.name + '.grades-new')
    copy2(stage / name, temporary)
    assert digest(temporary) == new
    replace(temporary, destination)
    print(f'Published {relative}: {new}')
