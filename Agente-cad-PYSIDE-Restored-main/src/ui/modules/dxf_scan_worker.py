"""
dxf_scan_worker.py — subprocess helper para escanear labels do DXF estrutural.
Executado como: python dxf_scan_worker.py <dxf_path>
Retorna: JSON { "labels": {txt: [x,y]}, "ents": [[type,x,y,layer], ...] }

NÃO importa PySide6.
"""
import sys, json
from pathlib import Path


def scan(dxf_path: Path):
    import ezdxf
    labels = {}
    ents = []
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        for e in msp:
            t   = e.dxftype()
            lyr = e.dxf.layer if hasattr(e.dxf, 'layer') else ''
            ex = ey = None
            try:
                if hasattr(e.dxf, 'insert'):
                    ex, ey = e.dxf.insert.x, e.dxf.insert.y
                elif hasattr(e.dxf, 'start'):
                    ex = (e.dxf.start.x + e.dxf.end.x) / 2
                    ey = (e.dxf.start.y + e.dxf.end.y) / 2
            except Exception:
                pass
            if ex is not None:
                ents.append([t, ex, ey, lyr])
            if t in ('MTEXT', 'TEXT') and ex is not None:
                try:
                    txt = (e.plain_text() if hasattr(e, 'plain_text')
                           else e.dxf.text).strip()
                    if txt and txt not in labels:
                        labels[txt] = [ex, ey]
                except Exception:
                    pass
        del doc, msp
    except Exception:
        pass
    return {'labels': labels, 'ents': ents}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.stderr.write('Usage: dxf_scan_worker.py <dxf_path>\n')
        sys.exit(1)
    result = scan(Path(sys.argv[1]))
    # Output as JSON (compact)
    out = json.dumps(result, separators=(',', ':'))
    sys.stdout.write(out)
    sys.stdout.flush()
