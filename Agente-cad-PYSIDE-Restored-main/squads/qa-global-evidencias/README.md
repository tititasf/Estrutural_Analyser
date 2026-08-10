# QA Global de Evidências

Squad AIOS do QA Arete. O orquestrador escolhe o microciclo por nível e delega a
semântica a adaptadores de classe. A implementação operacional continua nos scripts
canônicos do repo; esta squad formaliza roteamento, gates, dossiês e autoridade.

Ativação: `/CAD:QAGlobalEvidencias-AIOS *loop --project-id ... --classe ... --item ... --nivel ...`

Autoridade por classe: `data/authority_matrix.json` (validar com
`python scripts/arete/qa_authority_matrix.py`).

Abrir último dossiê (prova, não HTML genérico):

```powershell
python scripts/arete/qa_open_latest_dossier.py --project-id <id> --open
```

Painel UI mínimo: `src/ui/widgets/qa_global_dossier_panel.py` (`QaGlobalDossierPanel`).

Golden multi-item FV/LV:

```powershell
python scripts/arete/qa_fv_lv_golden_regression.py --project-id <id> --write-baseline
python scripts/arete/qa_fv_lv_golden_regression.py --project-id <id>
```

Baseline: `scripts/arete/qa_requests/golden/fv_lv_13pav_baseline.json`.

Integração app↔agente: `docs/INTEGRACAO-APP-AGENTE.md`  
Capacidade por classe (paridade): `docs/QA-CAPACIDADE-POR-CLASSE.md` + `data/class_capability_matrix.json`  
Anti-super-selo: `checklists/operational-anti-superselo-checklist.md`  
Aba UI: **QA Global de Evidências** (module tab 9).

```powershell
python scripts/arete/qa_class_capability.py
python scripts/arete/qa_class_golden_regression.py --project-id <id> --write-baseline
python scripts/arete/qa_class_golden_regression.py --project-id <id>
python scripts/arete/qa_g2v_visual_gate.py --pav 13_PAV
```

Arquitetura: uma squad, um orquestrador, tasks determinísticas e zero entry point
alternativo para headless, geração ou visão.

Fast paths v1.2: perfis executáveis por classe, probe N1 limitado a campos/checks,
allowlists semânticas FV/LV, smoke N3 por contrato/variante,
paridade declarativa contrato→payload→DXF→HTML, render cacheado por conteúdo e
RAG particionado com degradação explícita. Esses caminhos aceleram diagnóstico;
não aprovam ficha/item nem substituem gate visual.

Retomada operacional: `scripts/arete/qa_loop_executor.py`. Para PIL, cobertura por
famílias e probes cross-classe: `scripts/arete/qa_pil_coverage.py`. O executor avança
passos seguros, persiste a próxima ação e pede ensino humano somente para regra
ambígua, visão, QG7 ou promoção RAG.

Premissa detalhada por classe: `docs/QA-PERFIS-CLASSES-SA-N1-N3.md`.
