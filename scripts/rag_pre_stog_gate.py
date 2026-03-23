#!/usr/bin/env python3
"""
rag_pre_stog_gate.py — CAD-ANALYZER Sprint 1
=============================================
Gate obrigatório ANTES de qualquer geração DXF pelos robôs Bolt/Crane/Slab.

Carrega elementos da Fase 3 (ground truth JSONs) de uma obra,
valida cada um via AnomalyDetector, e retorna veredicto final:
  - PASS: todos os elementos aprovados (podem prosseguir para os robôs)
  - FAIL: há elementos bloqueados (parar geração até revisão)

Integrar chamada antes de robot_integration.process_pavimento().

Uso:
    from rag_pre_stog_gate import PreStogGate
    gate = PreStogGate()
    result = gate.run('D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1')
    if result.gate == 'FAIL':
        gate.salvar_report(result)
        sys.exit(1)  # bloquear pipeline

    # Ou via CLI:
    python scripts/rag_pre_stog_gate.py --obra Obra_TREINO_1
    python scripts/rag_pre_stog_gate.py --obra Obra_TREINO_1 --force   # prosseguir mesmo com FAIL
    python scripts/rag_pre_stog_gate.py --all                           # todas as obras
"""
import sys, os, json, argparse, datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from rag_anomaly_detector import AnomalyDetector, ObraAnomalyReport

OBRAS_DIR    = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')
REPORTS_DIR  = Path('D:/Agente-cad-PYSIDE/data/rag-gates')
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Carregamento de elementos da Fase 3 ─────────────────────────────────────

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return json.load(f)
    except Exception:
        return {}

def carregar_elementos_fase3(obra_path: Path, obra_nome: str) -> list:
    """
    Carrega pilares, vigas e lajes da Fase 3 de uma obra.
    Mesmo formato do rag_ingestor.py para consistência.
    """
    fase3 = obra_path / 'Fase-3_Interpretacao_Extracao'
    if not fase3.exists():
        return []

    elementos = []

    # Pilares
    for fname in ['pilares_ground_truth.json', 'pilares_bh.json', 'pilares.json']:
        data = _load_json(fase3 / 'Pilares' / fname)
        if data:
            for pid, pdata in data.items():
                if not isinstance(pdata, dict):
                    continue
                elementos.append({'tipo': 'pilar', 'id': pid, 'dados': pdata, 'arquivo': fname})
            break

    # Vigas
    for fname in ['vigas_ground_truth.json', 'vigas.json']:
        data = _load_json(fase3 / 'Vigas' / fname)
        if data:
            for vid, vdata in data.items():
                if not isinstance(vdata, dict):
                    continue
                elementos.append({'tipo': 'viga', 'id': vid, 'dados': vdata, 'arquivo': fname})
            break

    # Lajes
    for fname in ['lajes_ground_truth.json', 'lajes.json', 'lajes_data.json']:
        data = _load_json(fase3 / 'Lajes' / fname)
        if data:
            for lid, ldata in data.items():
                if not isinstance(ldata, dict):
                    continue
                elementos.append({'tipo': 'laje', 'id': lid, 'dados': ldata, 'arquivo': fname})
            break

    return elementos


# ── Gate Result ──────────────────────────────────────────────────────────────

@dataclass
class GateResult:
    obra:        str
    obra_path:   str
    gate:        str       # PASS | FAIL | SKIP (sem elementos)
    timestamp:   str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    n_elementos: int = 0
    n_aprovados: int = 0
    n_avisos:    int = 0
    n_bloqueados: int = 0
    anomaly_report: Optional[ObraAnomalyReport] = None
    motivo_skip: str = ''

    def print_summary(self):
        cor = {
            'PASS':  '\033[32m',  # verde
            'FAIL':  '\033[31m',  # vermelho
            'SKIP':  '\033[33m',  # amarelo
        }
        reset = '\033[0m'
        c = cor.get(self.gate, '')

        print(f"\n{'='*55}")
        print(f"  PRE-STOG GATE — {self.obra}")
        print(f"  Status: {c}{self.gate}{reset}")
        print(f"  Elementos: {self.n_elementos} total")
        print(f"    Aprovados:  {self.n_aprovados}")
        print(f"    Com avisos: {self.n_avisos}")
        print(f"    Bloqueados: {self.n_bloqueados}")
        if self.gate == 'SKIP':
            print(f"  Motivo: {self.motivo_skip}")
        print(f"{'='*55}")

        if self.gate == 'FAIL' and self.anomaly_report:
            print(self.anomaly_report.relatorio(verbose=False))

    def to_dict(self) -> dict:
        d = {
            'obra':        self.obra,
            'obra_path':   self.obra_path,
            'gate':        self.gate,
            'timestamp':   self.timestamp,
            'n_elementos': self.n_elementos,
            'n_aprovados': self.n_aprovados,
            'n_avisos':    self.n_avisos,
            'n_bloqueados': self.n_bloqueados,
        }
        if self.anomaly_report:
            d['anomaly_report'] = self.anomaly_report.to_dict()
        if self.motivo_skip:
            d['motivo_skip'] = self.motivo_skip
        return d


# ── Gate Principal ───────────────────────────────────────────────────────────

class PreStogGate:
    """
    Gate de validação RAG pré-geração DXF.

    Instanciar uma vez e reutilizar para múltiplas obras
    (o detector mantém modelo em cache).

    Exemplo:
        gate = PreStogGate()

        # Obra específica
        result = gate.run('Obra_TREINO_1')
        result.print_summary()

        # Programático — integrar em robot_integration
        if not gate.approve(obra_path, obra_nome):
            raise ValueError(f"Gate FAIL para {obra_nome}")
    """

    def __init__(self):
        self.detector = AnomalyDetector()

    def run(self, obra: str, obras_dir: Path = OBRAS_DIR) -> GateResult:
        """
        Executa gate para uma obra.

        Args:
            obra:      nome da obra (pasta) ou path completo
            obras_dir: diretório base das obras

        Returns:
            GateResult com veredicto final
        """
        # Resolver path
        if Path(obra).exists():
            obra_path = Path(obra)
            obra_nome = obra_path.name
        else:
            obra_path = obras_dir / obra
            obra_nome = obra

        if not obra_path.exists():
            return GateResult(
                obra=obra_nome,
                obra_path=str(obra_path),
                gate='SKIP',
                motivo_skip=f'Caminho não encontrado: {obra_path}',
            )

        # Carregar elementos
        elementos = carregar_elementos_fase3(obra_path, obra_nome)
        if not elementos:
            return GateResult(
                obra=obra_nome,
                obra_path=str(obra_path),
                gate='SKIP',
                motivo_skip='Nenhum elemento encontrado na Fase 3',
            )

        # Executar anomaly detection
        report = self.detector.report_obra(obra_nome, elementos)

        # Contar por categoria
        n_avisos    = len(report.incomuns) + len(report.suspeitos)
        n_bloqueados = len(report.bloqueados)
        n_aprovados  = len(report.normais)

        gate_status = 'PASS' if n_bloqueados == 0 else 'FAIL'

        return GateResult(
            obra=obra_nome,
            obra_path=str(obra_path),
            gate=gate_status,
            n_elementos=len(elementos),
            n_aprovados=n_aprovados,
            n_avisos=n_avisos,
            n_bloqueados=n_bloqueados,
            anomaly_report=report,
        )

    def approve(self, obra: str, obras_dir: Path = OBRAS_DIR) -> bool:
        """
        Versão booleana para integração em pipelines.
        True = PASS (pode prosseguir), False = FAIL (bloquear).
        """
        result = self.run(obra, obras_dir)
        return result.gate in ('PASS', 'SKIP')

    def run_all(self, obras_dir: Path = OBRAS_DIR) -> list:
        """Executa gate para todas as obras no diretório."""
        results = []
        for obra_dir in sorted(obras_dir.iterdir()):
            if obra_dir.is_dir():
                r = self.run(obra_dir.name, obras_dir)
                results.append(r)
        return results

    def salvar_report(self, result: GateResult) -> Path:
        """Salva relatório JSON em data/rag-gates/."""
        fname = f"gate-{result.obra}-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        path  = REPORTS_DIR / fname
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        return path


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RAG Pre-STOG Gate — CAD-ANALYZER')
    parser.add_argument('--obra',    help='Nome da obra a validar')
    parser.add_argument('--all',     action='store_true', help='Validar todas as obras')
    parser.add_argument('--force',   action='store_true', help='Não sair com código 1 em FAIL')
    parser.add_argument('--save',    action='store_true', help='Salvar report JSON')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    gate = PreStogGate()

    if args.all:
        results = gate.run_all()
        print(f"\n{'='*60}")
        print(f"PRE-STOG GATE — Todas as Obras ({len(results)} processadas)")
        print(f"{'='*60}")
        for r in results:
            cor = '\033[32m' if r.gate == 'PASS' else ('\033[33m' if r.gate == 'SKIP' else '\033[31m')
            print(f"  {cor}{r.gate}\033[0m  {r.obra:<30}  elem={r.n_elementos}  bloqued={r.n_bloqueados}")
            if args.save and r.gate != 'SKIP':
                p = gate.salvar_report(r)
                print(f"        → {p}")

        n_fail = sum(1 for r in results if r.gate == 'FAIL')
        n_pass = sum(1 for r in results if r.gate == 'PASS')
        n_skip = sum(1 for r in results if r.gate == 'SKIP')
        print(f"\nResumo: PASS={n_pass} FAIL={n_fail} SKIP={n_skip}")

        if n_fail > 0 and not args.force:
            sys.exit(1)

    elif args.obra:
        result = gate.run(args.obra)
        result.print_summary()
        if args.save:
            p = gate.salvar_report(result)
            print(f"\nReport salvo: {p}")
        if result.gate == 'FAIL' and not args.force:
            sys.exit(1)
    else:
        parser.print_help()
        print('\nExemplos:')
        print('  python scripts/rag_pre_stog_gate.py --obra Obra_TREINO_1')
        print('  python scripts/rag_pre_stog_gate.py --all')
        print('  python scripts/rag_pre_stog_gate.py --obra Obra_TREINO_1 --save')
