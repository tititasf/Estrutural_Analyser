import re

with open(r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\pipeline_runner.py', 'r', encoding='utf-8') as f:
    txt = f.read()

new_func = '''def _garantir_project_registrado(settings: Settings, obra: dict, pavimento: str) -> None:
    from src.core.database import DatabaseManager
    import sqlite3

    obra_dir = _obra_dir(settings, obra)
    work_name = str(obra_dir)
    database = DatabaseManager(db_path=str(settings.sa_db_path))

    dxf_path = None
    try:
        conn = sqlite3.connect(str(settings.db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT arquivo_nome FROM portal_documentos WHERE obra_id = ? AND pavimento_alvo = ? ORDER BY arquivo_nome ASC",
            (obra.get("id"), pavimento)
        ).fetchall()
        for doc in rows:
            if doc and doc["arquivo_nome"]:
                nome = doc["arquivo_nome"]
                if nome.lower().endswith(".dwg") or nome.lower().endswith(".dxf"):
                    candidato = obra_dir / "entrada" / nome
                    dxf_path = candidato.with_suffix(".dxf")
                    if not dxf_path.is_file() and "_R2018_ASCII_ODA" in nome:
                        dxf_path = candidato
                    break
    except Exception as e:
        print("Erro ao buscar documento para registrar project:", e)
    finally:
        if 'conn' in locals():
            conn.close()

    if not dxf_path:
        entrada = _arquivo_entrada(obra_dir, obra)
        if not entrada:
            return
        dxf_path = entrada.with_suffix(".dxf")

    if not dxf_path or not dxf_path.is_file():
        return

    try:
        database.cursor.execute(
            "UPDATE projects SET dxf_path = ? WHERE work_name = ? AND name = ?",
            (str(dxf_path), work_name, pavimento)
        )
        if database.cursor.rowcount == 0:
            database.create_project(
                name=pavimento, dxf_path=str(dxf_path),
                work_name=work_name, pavement_name=pavimento,
            )
        database.conn.commit()
    except Exception as e:
        print("Erro ao atualizar project.vision:", e)
'''

txt = re.sub(r'def _garantir_project_registrado.*?def _tail', new_func + '\n\ndef _tail', txt, flags=re.DOTALL)
with open(r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\pipeline_runner.py', 'w', encoding='utf-8') as f:
    f.write(txt)
print('Patched!')
