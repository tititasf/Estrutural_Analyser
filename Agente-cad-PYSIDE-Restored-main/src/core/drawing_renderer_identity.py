"""Keep unchanged mode identities only for the exact iNi routing patch.

Any later change to a renderer invalidates its artifacts normally.
"""
from pathlib import Path
from hashlib import sha256
import json

def renderer_bytes(path, mode):
    path=Path(path)
    actual=path.read_bytes()
    folder=Path(__file__).parent/'ini_compat'
    frozen=folder/(path.name+'.snapshot')
    expected=json.loads((folder/'routing_hashes.json').read_text(encoding='utf8'))
    if str(mode).upper() in ('NOVA','MOLDE_1') and frozen.is_file() and sha256(actual).hexdigest()==expected.get(path.name):
        return frozen.read_bytes()
    return actual
