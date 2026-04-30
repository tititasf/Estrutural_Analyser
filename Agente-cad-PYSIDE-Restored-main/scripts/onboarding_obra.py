#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
onboarding_obra.py — Integração de nova obra ao pipeline CAD-ANALYZER (CAD-12.4)
==================================================================================
Automatiza os passos de onboarding:
  1. Cria estrutura de pastas padrão (Fase-1 a Fase-8)
  2. Copia/move DXFs para Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa/
  3. Executa descoberta de DXFs (descobrir_obras.py)
  4. Valida que DXFs mínimos existem (PL, LV, FV, LJ)
  5. Gera checklist de validação manual

CLI:
  python scripts/onboarding_obra.py --nome "Nome da Obra" [--dir /path/to/dxfs] [--data-dir DADOS-OBRAS]
  python scripts/onboarding_obra.py --nome "Obra Teste" --dir D:/dxfs/minha-obra --dry-run
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DATA_DIR_DEFAULT = SCRIPT_DIR.parent.parent / "DADOS-OBRAS"

# Estrutura obrigatória de uma obra
ESTRUTURA_FASES = [
    "Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa",
    "Fase-1_Ingestao/DXF_Bruto",
    "Fase-2_Triagem",
    "Fase-3_Interpretacao_Extracao/Pilares",
    "Fase-3_Interpretacao_Extracao/Vigas",
    "Fase-3_Interpretacao_Extracao/Lajes",
    "Fase-3_Interpretacao_Extracao/Garfos",
    "Fase-3_Interpretacao_Extracao/Fichas_Completas",
    "Fase-3_Interpretacao_Extracao/Estruturais_Pavimentos_Limpos",
    "Fase-4_Sincronizacao/JSON_Pilares",
    "Fase-4_Sincronizacao/JSON_Vigas_Laterais",
    "Fase-4_Sincronizacao/JSON_Vigas_Fundo",
    "Fase-4_Sincronizacao/JSON_Lajes",
    "Fase-5_Geracao_Scripts/DXF_Pilares",
    "Fase-5_Geracao_Scripts/DXF_Vigas",
    "Fase-5_Geracao_Scripts/DXF_Lajes",
    "Fase-6_Execucao_CAD/DXF_Pilares",
    "Fase-6_Execucao_CAD/DXF_Vigas_Laterais",
    "Fase-6_Execucao_CAD/DXF_Vigas_Fundo",
    "Fase-6_Execucao_CAD/DXF_Lajes",
    "Fase-7_Consolidacao/DXF_Consolidado_por_Pavimento",
    "Fase-7_Consolidacao/DXF_Consolidado_por_Tipo",
    "Fase-8_Revisao_Entrega/DXF_Final_Validado",
]

# Tipos de DXF necessários e sufixos que os identificam
DXF_TIPOS = {
    "PL": ["PL", "PILAR", "PILARES", "pilar"],
    "LV": ["LV", "LATERAL", "VIGA", "VIGAS"],
    "FV": ["FV", "FD", "FUNDO"],
    "LJ": ["LJ", "LAJE", "LAJES"],
    "EVG": ["EVG", "ESF", "ESFORCO"],  # opcional
}


def _identificar_tipo_dxf(filename: str) -> str | None:
    """Identifica o tipo (PL, LV, FV, LJ, EVG) pelo nome do arquivo."""
    upper = filename.upper()
    for tipo, keywords in DXF_TIPOS.items():
        if any(k in upper for k in keywords):
            return tipo
    return None


def _criar_estrutura(obra_path: Path, dry_run: bool) -> list[str]:
    """Cria estrutura de pastas. Retorna lista do que foi criado."""
    criados = []
    for fase_rel in ESTRUTURA_FASES:
        p = obra_path / fase_rel
        if not p.exists():
            if dry_run:
                criados.append(f"[DRY] mkdir {p.relative_to(obra_path)}")
            else:
                p.mkdir(parents=True, exist_ok=True)
                criados.append(str(p.relative_to(obra_path)))
    return criados


def _copiar_dxfs(src_dir: Path, obra_path: Path, dry_run: bool) -> dict:
    """Copia DXFs do diretório fonte para Fase-1_Ingestao/Projetos_Finalizados/."""
    destino = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    dxfs_src = sorted(src_dir.glob("*.dxf")) + sorted(src_dir.glob("*.DXF"))
    if not dxfs_src:
        # Tentar subdiretórios 1 nível
        dxfs_src = sorted(src_dir.glob("**/*.dxf"))[:50]

    resultado = {"copiados": [], "ignorados": [], "tipos_encontrados": set()}
    for dxf in dxfs_src:
        tipo = _identificar_tipo_dxf(dxf.name)
        dest_path = destino / dxf.name
        if not dry_run:
            shutil.copy2(dxf, dest_path)
        resultado["copiados"].append({"arquivo": dxf.name, "tipo": tipo or "?", "destino": str(dest_path)})
        if tipo:
            resultado["tipos_encontrados"].add(tipo)

    resultado["tipos_encontrados"] = sorted(resultado["tipos_encontrados"])
    return resultado


def _executar_discovery(data_dir: Path, dry_run: bool) -> bool:
    """Executa descobrir_obras.py para atualizar dxf_discovery.json."""
    script = SCRIPT_DIR / "descobrir_obras.py"
    if not script.exists():
        print("  [WARN] descobrir_obras.py não encontrado — skip discovery")
        return False
    if dry_run:
        print(f"  [DRY-RUN] descobrir_obras.py --data-dir {data_dir}")
        return True
    cmd = [sys.executable, str(script), "--data-dir", str(data_dir)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def _validar_dxfs(obra_path: Path) -> dict:
    """Verifica quais tipos de DXF estão presentes em Fase-1."""
    fase1 = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    dxfs  = list(fase1.glob("*.dxf")) + list(fase1.glob("*.DXF"))

    presentes = {}
    for dxf in dxfs:
        tipo = _identificar_tipo_dxf(dxf.name)
        if tipo and tipo not in presentes:
            presentes[tipo] = dxf.name

    obrigatorios = {"PL", "LV", "FV", "LJ"}
    ausentes     = obrigatorios - set(presentes.keys())

    return {
        "presentes":    presentes,
        "ausentes":     sorted(ausentes),
        "total_dxfs":   len(dxfs),
        "completo":     len(ausentes) == 0,
    }


def _gerar_checklist(obra_path: Path, nome: str, validacao: dict) -> str:
    """Gera arquivo de checklist de validação manual."""
    checklist = [
        f"# Checklist de Onboarding — {nome}",
        f"",
        f"**Criado em:** {datetime.now(timezone.utc).isoformat()}",
        f"**Obra path:** {obra_path}",
        f"",
        f"## 1. DXFs (verificação automática)",
        f"",
        f"| Tipo | Arquivo | Status |",
        f"|------|---------|--------|",
    ]
    for tipo in ["PL", "LV", "FV", "LJ", "EVG"]:
        arquivo = validacao["presentes"].get(tipo, "—")
        status  = "✅" if tipo in validacao["presentes"] else ("❌ AUSENTE" if tipo in {"PL","LV","FV","LJ"} else "⏭️ opcional")
        checklist.append(f"| {tipo} | {arquivo} | {status} |")

    checklist += [
        f"",
        f"## 2. Verificação Manual (obrigatória antes de processar)",
        f"",
        f"- [ ] DXFs abrem no AutoCAD/DXF viewer sem erros",
        f"- [ ] Layer 'Texto Seção' ou 'NOMENCLATURA' contém IDs P{{n}}/V{{n}}/L{{n}}",
        f"- [ ] Layer 'Cota Seção (2x)' ou 'COTA' contém dimensões B/H",
        f"- [ ] Pavimento(s) claramente identificáveis pelo nome do DXF",
        f"- [ ] Sem DXFs corrompidos ou com encoding incompatível",
        f"",
        f"## 3. Próximos Passos",
        f"",
        f"```bash",
        f"# Processar obra completa",
        f"python scripts/cad_pipeline_cli.py run --obra DADOS-OBRAS/{nome}",
        f"",
        f"# Verificar status após processamento",
        f"python scripts/cad_pipeline_cli.py status",
        f"```",
        f"",
        f"## 4. Gaps Conhecidos a Verificar",
        f"",
        f"- Pilares com IDs em layer '0' ou compound (P1-P2-P3): ok — suportado",
        f"- Vigas compostas tipo '(VA2+V16).A': ok — suportado",
        f"- Lajes tipo 'L-N' (só espessura h=10): extraídas como GT=0, skip no score",
        f"- P2-P8 (pilares especiais): podem estar no PAV TIPO DXF, não no pavimento principal",
        f"",
    ]

    content = "\n".join(checklist)
    out_path = obra_path / "ONBOARDING_CHECKLIST.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return str(out_path)


def main():
    parser = argparse.ArgumentParser(description="Onboarding de nova obra — CAD-ANALYZER (CAD-12.4)")
    parser.add_argument("--nome",      required=True,  help="Nome da obra (será o nome da pasta)")
    parser.add_argument("--dir",       default=None,   help="Diretório com DXFs para copiar")
    parser.add_argument("--data-dir",  default=str(DATA_DIR_DEFAULT), help="Diretório raiz de obras")
    parser.add_argument("--dry-run",   action="store_true", help="Mostra o que seria feito")
    args = parser.parse_args()

    data_dir  = Path(args.data_dir).resolve()
    obra_path = data_dir / args.nome

    print(f"\n{'═'*65}")
    print(f"  CAD-ANALYZER  onboarding  — {args.nome}")
    print(f"{'═'*65}")
    print(f"\n  Destino: {obra_path}")
    if args.dry_run:
        print(f"  [DRY-RUN] Nenhuma alteração real será feita.\n")

    # 1. Verificar se obra já existe
    if obra_path.exists() and not args.dry_run:
        fase1 = obra_path / "Fase-1_Ingestao"
        if fase1.exists():
            print(f"[WARN] Obra '{args.nome}' já existe. Estrutura será complementada (não sobrescrita).")

    # 2. Criar estrutura
    print("\n[1/4] Criando estrutura de pastas ...")
    criados = _criar_estrutura(obra_path, args.dry_run)
    if criados:
        print(f"  {len(criados)} pastas criadas:")
        for p in criados[:8]:
            print(f"    + {p}")
        if len(criados) > 8:
            print(f"    ... e mais {len(criados)-8}")
    else:
        print("  [SKIP] Estrutura já existe")

    # 3. Copiar DXFs (se --dir fornecido)
    copy_result = {"copiados": [], "tipos_encontrados": [], "ausentes": []}
    if args.dir:
        src_dir = Path(args.dir).resolve()
        if not src_dir.exists():
            print(f"[ERRO] Diretório fonte não encontrado: {src_dir}")
            sys.exit(1)
        print(f"\n[2/4] Copiando DXFs de {src_dir} ...")
        copy_result = _copiar_dxfs(src_dir, obra_path, args.dry_run)
        print(f"  {len(copy_result['copiados'])} DXFs copiados")
        print(f"  Tipos identificados: {copy_result['tipos_encontrados']}")
        for item in copy_result["copiados"][:5]:
            prefix = "[DRY-RUN] " if args.dry_run else ""
            print(f"    {prefix}{item['arquivo']} → tipo={item['tipo']}")
    else:
        print(f"\n[2/4] Nenhum --dir fornecido — copie os DXFs manualmente para:")
        print(f"  {obra_path / 'Fase-1_Ingestao' / 'Projetos_Finalizados_para_Engenharia_Reversa'}")

    # 4. Discovery
    print(f"\n[3/4] Executando discovery de DXFs ...")
    disc_ok = _executar_discovery(data_dir, args.dry_run)
    print(f"  Discovery: {'OK' if disc_ok else 'FALHOU — executar manualmente'}")

    # 5. Validar
    print(f"\n[4/4] Validando DXFs encontrados ...")
    if not args.dry_run:
        validacao = _validar_dxfs(obra_path)
    else:
        validacao = {
            "presentes": {t: "(simulado)" for t in copy_result.get("tipos_encontrados", [])},
            "ausentes": [],
            "total_dxfs": len(copy_result.get("copiados", [])),
            "completo": True,
        }

    print(f"  DXFs encontrados: {validacao['total_dxfs']}")
    for tipo, arquivo in validacao["presentes"].items():
        print(f"  ✅ {tipo}: {arquivo}")
    for tipo in validacao["ausentes"]:
        print(f"  ❌ {tipo}: AUSENTE (obrigatório)")

    # 6. Gerar checklist
    if not args.dry_run:
        checklist_path = _gerar_checklist(obra_path, args.nome, validacao)
        print(f"\n  Checklist manual: {checklist_path}")

    # Resultado
    print(f"\n{'─'*65}")
    if validacao["completo"] or args.dry_run:
        print(f"  ✅ Onboarding concluído — {args.nome} pronto para processamento")
        print(f"\n  Próximo passo:")
        print(f"    python scripts/cad_pipeline_cli.py run --obra DADOS-OBRAS/{args.nome}")
        sys.exit(0)
    else:
        print(f"  ⚠️  Onboarding parcial — DXFs ausentes: {validacao['ausentes']}")
        print(f"  Copie os DXFs faltantes e execute:")
        print(f"    python scripts/cad_pipeline_cli.py run --obra DADOS-OBRAS/{args.nome}")
        sys.exit(1)


if __name__ == "__main__":
    main()
