"""
Sprint-D: Parser de PDFs de PI (Processo Interno) para popular pavimento_pi.

Formato real dos PDFs:
  NOME PAVIMENTO
  P.D.: X,XX          (em metros)
  Delimitacao texto multiplas linhas
  Elemento  Jogos  M2
  Pilar     N      XXX m2
  Vigas     N      XXX m2
  Laje      N      XXX m2
  Tira      N      XXX m2

Grava em: project_data.vision (tabela pavimento_pi)
"""
import os
import re
import sys
import uuid
import sqlite3
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

DB_PATH = Path(__file__).parent.parent / 'project_data.vision'
PDF_DIR = Path(__file__).parent.parent / 'pdfs-obras-aleatorias'

# Mapeamento nome PDF/obra -> work_name no DB
OBRA_MAP = {
    'NIK SUNSET': 'Obra_TREINO_11',
    'LEAF':        'Obra_TREINO_13',
    'LOEFGREN':    'Obra_TREINO_13',
    'INDIANOPOLIS':'Obra_TREINO_1',
    'INDIANÓPOLIS':'Obra_TREINO_1',
    'GWT':         'Obra_TREINO_22',
    'SCHWARTZ':    'Obra_TREINO_22',
    'ARRAIA':      'Obra_TREINO_20',
    'NURBAN':      'Obra_TREINO_9',
}


def _float(s):
    try:
        return float(str(s).replace(',', '.').strip().split()[0])
    except Exception:
        return None


def _detect_obra(pdf_name: str) -> str:
    upper = pdf_name.upper()
    for key, obra in OBRA_MAP.items():
        if key.upper() in upper:
            return obra
    return 'DESCONHECIDO'


def parse_pi_text(full_text: str) -> list:
    """
    Parseia texto completo de PI e retorna lista de dicts, um por pavimento.

    Formato: bloco por pavimento separado por "P.D.:"
    """
    pavimentos = []

    # Dividir por blocos de pavimento (cada bloco começa com linha de nome + PD)
    # Padrao: nome do pav na linha anterior ao PD, depois PD:
    lines = full_text.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Detectar inicio de bloco de pavimento: "P.D.: X"
        pd_m = re.match(r'P\.D\.[:\s]+([\d,\.]+)', line, re.IGNORECASE)
        if pd_m:
            pd_val = _float(pd_m.group(1))
            # Converter metros -> mm (PDFs tem valores como 2.80 = 2800mm)
            if pd_val and pd_val < 20:
                pd_val = round(pd_val * 1000)

            # Nome do pavimento = linha anterior nao vazia
            pav_nome = 'TIPO'
            for back in range(i - 1, max(i - 4, -1), -1):
                candidate = lines[back].strip()
                if candidate and not candidate.startswith('P.D'):
                    pav_nome = candidate
                    break

            # Delimitacao: linhas apos PD ate linha "Elemento"
            delim_lines = []
            j = i + 1
            while j < len(lines) and j < i + 8:
                ln = lines[j].strip()
                if re.match(r'Elemento|Jogos', ln, re.IGNORECASE):
                    break
                if ln and not re.match(r'P\.D\.|Observa', ln, re.IGNORECASE):
                    delim_lines.append(ln)
                j += 1
            delimitacao = ' '.join(delim_lines).replace('Delimitação', '').replace('Delimitacao', '').strip()

            # Tabela de areas: varrer linhas ate "TOTAL" ou proximo bloco
            area_pilar = area_viga = area_laje = area_tira = None
            jogos_pilar = jogos_viga = jogos_laje = 1

            k = j
            while k < len(lines) and k < i + 20:
                ln = lines[k].strip()

                # Pilar: "Pilar  1  644 m²"
                m = re.match(r'Pilar\s+(\d+|-)\s+([\d,\.]+)', ln, re.IGNORECASE)
                if m:
                    jogos_pilar = int(m.group(1)) if m.group(1).isdigit() else 1
                    area_pilar = _float(m.group(2))

                # Viga(s)
                m = re.match(r'Vigas?\s+(\d+|-)\s+([\d,\.]+)', ln, re.IGNORECASE)
                if m:
                    jogos_viga = int(m.group(1)) if m.group(1).isdigit() else 1
                    area_viga = _float(m.group(2))

                # Laje
                m = re.match(r'Laje\s+(\d+|-)\s+([\d,\.]+)', ln, re.IGNORECASE)
                if m:
                    jogos_laje = int(m.group(1)) if m.group(1).isdigit() else 1
                    area_laje = _float(m.group(2))

                # Tira adicional
                m = re.match(r'Tira\s+(?:adicional\s+)?(\d+|-)\s+([\d,\.]+)', ln, re.IGNORECASE)
                if m:
                    area_tira = _float(m.group(2))

                # Parar no TOTAL ou proximo PD
                if re.match(r'TOTAL|P\.D\.', ln, re.IGNORECASE):
                    break
                k += 1

            pav_dict = {
                'pavimento_nome': pav_nome,
                'pe_direito':     pd_val,
                'cota_saida':     None,
                'delimitacao':    delimitacao or None,
                'area_pilar_m2':  area_pilar,
                'area_viga_m2':   area_viga,
                'area_laje_m2':   area_laje,
                'area_tira_reescoramento': area_tira,
                'jogos_formas':   jogos_laje or jogos_pilar or 1,
            }
            pavimentos.append(pav_dict)

        i += 1

    return pavimentos


def parse_pi_pdf(pdf_path: Path) -> dict:
    result = {
        'pdf': pdf_path.name,
        'obra': _detect_obra(pdf_path.name),
        'pavimentos': [],
    }
    if not HAS_PDF:
        return result
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            full_text = '\n'.join(
                (page.extract_text() or '') for page in pdf.pages
            )
    except Exception as ex:
        print(f"  [ERRO] {pdf_path.name}: {ex}")
        return result

    result['pavimentos'] = parse_pi_text(full_text)
    return result


def salvar_pavimento_pi(conn, obra_name: str, pav: dict) -> bool:
    projs = conn.execute(
        "SELECT id FROM projects WHERE work_name=? LIMIT 1", (obra_name,)
    ).fetchall()
    if not projs:
        return False
    proj_id = projs[0][0]
    rec_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT OR REPLACE INTO pavimento_pi
          (id, project_id, pavimento_nome, pe_direito, cota_saida,
           delimitacao, area_pilar_m2, area_viga_m2, area_laje_m2,
           jogos_formas, tiras_reescoramento, validated, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, datetime('now'))
        """,
        (
            rec_id, proj_id,
            pav.get('pavimento_nome', 'TIPO'),
            pav.get('pe_direito'),
            pav.get('cota_saida'),
            pav.get('delimitacao'),
            pav.get('area_pilar_m2'),
            pav.get('area_viga_m2'),
            pav.get('area_laje_m2'),
            pav.get('jogos_formas', 1),
            pav.get('area_tira_reescoramento', 0),
        ),
    )
    return True


def main():
    if not PDF_DIR.exists():
        print(f"ERRO: Pasta PDFs nao encontrada: {PDF_DIR}")
        sys.exit(1)

    if not HAS_PDF:
        print("Instalando pdfplumber...")
        os.system("pip install pdfplumber -q")
        try:
            import pdfplumber as _p
            globals()['HAS_PDF'] = True
        except ImportError:
            print("FALHA pdfplumber. Instalar manualmente: pip install pdfplumber")
            sys.exit(1)

    pi_pdfs = sorted(set(
        list(PDF_DIR.glob('PI*.pdf')) + list(PDF_DIR.glob('PI *.pdf'))
    ))
    print(f"Sprint-D: Parser PI PDFs -- {len(pi_pdfs)} PDFs encontrados")
    print("=" * 60)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    total_inseridos = 0

    for pdf_path in pi_pdfs:
        print(f"\n[PDF] {pdf_path.name}")
        parsed = parse_pi_pdf(pdf_path)
        obra = parsed.get('obra', 'DESCONHECIDO')
        pavs = parsed.get('pavimentos', [])

        if obra == 'DESCONHECIDO':
            print(f"  [SKIP] Obra nao mapeada")
            continue

        print(f"  Obra: {obra} | {len(pavs)} pavimentos extraidos")
        ok_count = 0
        for pav in pavs:
            pd = pav.get('pe_direito')
            al = pav.get('area_laje_m2')
            nome = pav.get('pavimento_nome', '')
            delim = (pav.get('delimitacao') or '')[:50]
            print(f"  [{nome[:25]:25}] PD={pd}mm  laje={al}m2  delim={delim}...")
            if salvar_pavimento_pi(conn, obra, pav):
                ok_count += 1

        print(f"  Inseridos: {ok_count}/{len(pavs)}")
        total_inseridos += ok_count

    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print(f"[RESULTADO] {total_inseridos} registros inseridos em pavimento_pi")
    # Verificar
    conn2 = sqlite3.connect(str(DB_PATH))
    n = conn2.execute("SELECT COUNT(*) FROM pavimento_pi").fetchone()[0]
    conn2.close()
    print(f"  Total na tabela agora: {n}")


if __name__ == '__main__':
    main()
