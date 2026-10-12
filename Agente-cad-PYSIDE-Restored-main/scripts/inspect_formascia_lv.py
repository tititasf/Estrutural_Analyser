import ezdxf

for filename in [
    "LATERAIS DE VIGA PAINEIS A B FORMASCIA.dxf",
    "LATERAIS DE VIGA GRADES SOLTAS FORMASCIA.dxf",
    "LATERAIS DE VIGA VISAO CORTE FORMASCIA.dxf",
]:
    path = f"d:/Agente-cad-PYSIDE/Exemplos Modos/FORMASCIA/{filename}"
    doc = ezdxf.readfile(path)
    print(f"=== {filename} ===")
    print("Layers:")
    for l in doc.layers:
        print(f"  {l.dxf.name}: color={l.dxf.color}, linetype={l.dxf.linetype}")
    print("Blocks:", [b.name for b in doc.blocks if not b.name.startswith("*")][:10])
    print("Dimstyles:")
    for ds in doc.dimstyles:
        print(f"  {ds.dxf.name}: dimtxt={ds.dxf.get('dimtxt', None)}, dimclrd={ds.dxf.get('dimclrd', None)}, dimclrt={ds.dxf.get('dimclrt', None)}")
