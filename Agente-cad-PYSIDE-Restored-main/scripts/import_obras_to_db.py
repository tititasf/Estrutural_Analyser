#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
import_obras_to_db.py — Importa obras de D:/Agente-cad-PYSIDE/DADOS-OBRAS para o banco local.

Para cada obra encontrada:
  1. Cria o registro na tabela `works`
  2. Para cada pavimento (via pavimentos_lista.json), cria registro em `projects`
  3. Aponta dxf_path para o DXF de Fase-2 correspondente (se existir)

Uso:
  python scripts/import_obras_to_db.py
  python scripts/import_obras_to_db.py --dry-run
"""
import sys, io, os, json, pathlib, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DADOS_OBRAS = pathlib.Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')
DB_PATH     = ROOT / 'project_data.vision'


def _find_dxf_for_pav(obra_path: pathlib.Path, pav_name: str) -> str:
    """Localiza o DXF estrutural principal da obra.

    Ordem de prioridade:
      1. Fase-1_Ingestao/Estruturais_dos_Pavimentos_*  (DXFs brutos estruturais)
      2. Fase-2_Triagem  (qualquer DXF processado)
      3. Fase-1_Ingestao  (qualquer DXF)
    Em cada pool, tenta casar pelo nome do pavimento antes de usar o primeiro.
    """
    pav_upper = pav_name.upper().replace(' ', '').replace('-', '')

    def _best_from(dxfs):
        if not dxfs:
            return ''
        for d in dxfs:
            stem = d.stem.upper().replace(' ', '').replace('-', '')
            if pav_upper in stem or pav_name.upper() in d.stem.upper():
                return str(d)
        return str(dxfs[0])

    # 1. Estruturais dentro de Fase-1
    f1 = obra_path / 'Fase-1_Ingestao'
    if f1.exists():
        for sub in f1.iterdir():
            if sub.is_dir() and 'estruturai' in sub.name.lower():
                dxfs = list(sub.rglob('*.dxf')) + list(sub.rglob('*.DXF'))
                r = _best_from(dxfs)
                if r:
                    return r

    # 2. Fase-2_Triagem (qualquer DXF)
    f2 = obra_path / 'Fase-2_Triagem'
    if f2.exists():
        dxfs = list(f2.rglob('*.dxf')) + list(f2.rglob('*.DXF'))
        r = _best_from(dxfs)
        if r:
            return r

    # 3. Fase-1_Ingestao restante
    if f1.exists():
        dxfs = list(f1.rglob('*.dxf')) + list(f1.rglob('*.DXF'))
        r = _best_from(dxfs)
        if r:
            return r

    return ''


def main():
    parser = argparse.ArgumentParser(description='Importar obras de DADOS-OBRAS para project_data.vision')
    parser.add_argument('--dry-run', action='store_true', help='Não altera o banco, apenas mostra o que seria feito')
    parser.add_argument('--dados-dir', default=str(DADOS_OBRAS), help='Diretório raiz das obras')
    args = parser.parse_args()

    dados_dir = pathlib.Path(args.dados_dir)
    if not dados_dir.exists():
        print(f'Erro: {dados_dir} nao encontrado')
        sys.exit(1)

    from src.core.database import DatabaseManager
    db = DatabaseManager(str(DB_PATH))

    # Obras já existentes
    existing_works = set(db.get_all_works() or [])
    existing_projects = {(p.get('work_name'), p.get('pavement_name'))
                        for p in (db.get_projects() or [])}

    print(f'\n{"="*60}')
    print(f'  Import DADOS-OBRAS → project_data.vision')
    print(f'{"="*60}')
    print(f'  Fonte: {dados_dir}')
    print(f'  Banco: {DB_PATH}')
    if args.dry_run:
        print('  [DRY-RUN] Nenhuma alteracao real sera feita')
    print(f'  Obras ja no banco: {len(existing_works)}\n')

    obras_criadas = 0
    pavs_criados  = 0
    skipped       = 0

    for obra_dir in sorted(dados_dir.iterdir()):
        if not obra_dir.is_dir():
            continue
        # Ignorar pastas utilitarias
        if obra_dir.name.startswith('.') or obra_dir.name in ('cenarios_fv', 'cenarios_lajes', 'OBRA_FORMATO_EXEMPLO'):
            continue

        obra_nome = obra_dir.name
        f4 = obra_dir / 'Fase-4_Sincronizacao'

        # Tentar ler pavimentos_lista.json
        pav_lista_f = f4 / 'pavimentos_lista.json'
        pavimentos = {}
        if pav_lista_f.exists():
            try:
                raw = json.loads(pav_lista_f.read_text(encoding='utf-8-sig'))
                # Formato: {obra_nome: {pavimentos: [...], pavimentos_data: {...}}}
                for _, v in raw.items():
                    pav_data = v.get('pavimentos_data', {})
                    for pname, pinfo in pav_data.items():
                        pavimentos[pname] = pinfo
                if not pavimentos:
                    # Fallback: lista simples
                    for _, v in raw.items():
                        for pname in v.get('pavimentos', []):
                            pavimentos[pname] = {'nome': pname}
            except Exception as e:
                print(f'  [WARN] {obra_nome}: erro lendo pavimentos_lista.json — {e}')

        # Se nao tem pavimentos_lista, inferir dos JSONs de Fase-4
        if not pavimentos and f4.exists():
            json_pil = f4 / 'JSON_Pilares'
            if json_pil.exists():
                for jf in json_pil.glob('*.json'):
                    try:
                        d = json.loads(jf.read_text(encoding='utf-8-sig'))
                        pav = d.get('pavimento', '')
                        if pav and pav not in pavimentos:
                            pavimentos[pav] = {'nome': pav}
                    except Exception:
                        pass

        # Se ainda nao tem, criar um pavimento padrao
        if not pavimentos:
            pavimentos = {obra_nome: {'nome': obra_nome}}

        # Criar obra no banco
        if obra_nome not in existing_works:
            print(f'  + Obra: {obra_nome} ({len(pavimentos)} pavimentos)')
            if not args.dry_run:
                db.create_work(obra_nome)
            obras_criadas += 1
        else:
            print(f'  = Obra: {obra_nome} (ja existe, verificando pavimentos)')

        # Criar pavimentos (projetos)
        for pav_nome, pinfo in pavimentos.items():
            key = (obra_nome, pav_nome)
            if key in existing_projects:
                skipped += 1
                continue

            dxf_path = _find_dxf_for_pav(obra_dir, pav_nome)
            level_arr = str(pinfo.get('nivel_chegada', '0.0'))
            level_exit = str(pinfo.get('nivel_saida', '280.0'))

            print(f'    + Pav: {pav_nome}  DXF: {pathlib.Path(dxf_path).name if dxf_path else "(nao encontrado)"}')
            if not args.dry_run:
                db.create_project(
                    name=pav_nome,
                    dxf_path=dxf_path,
                    work_name=obra_nome,
                    pavement_name=pav_nome,
                    level_arrival=level_arr,
                    level_exit=level_exit,
                )
            pavs_criados += 1

    print(f'\n{"─"*60}')
    if args.dry_run:
        print(f'  [DRY-RUN] Seriam criados: {obras_criadas} obras, {pavs_criados} pavimentos')
    else:
        print(f'  Criados: {obras_criadas} obras, {pavs_criados} pavimentos')
        print(f'  Ignorados (ja existiam): {skipped}')
        # Verificar resultado
        works_now = db.get_all_works() or []
        print(f'  Total obras no banco agora: {len(works_now)}')
    print()


if __name__ == '__main__':
    main()
