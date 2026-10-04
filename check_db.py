import sqlite3
conn=sqlite3.connect('d:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/consulta-publica-api/public_consulta.db')
print(conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
