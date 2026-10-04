# Calibração Jev × SA/QA — Fase 1 (G0 + G2 PIL/LAJ)

Implementação do backlog itens 1–2 de [PLANO-CALIBRACAO-JEV-SA-QA.md](PLANO-CALIBRACAO-JEV-SA-QA.md). Não chama a API Jev, não altera N1 e não cria outro loop QA. O helper [jev_sa_second_read.py](../../scripts/arete/jev_sa_second_read.py) e o índice [qa_session_index.py](../../scripts/arete/qa_session_index.py) continuam as interfaces de consulta e de B3.

## CLI

Python 3.12 da `.venv`. Saídas novas apenas em `scripts/arete/relatorios/<stamp>_jev_calibracao_*`.

```powershell
D:\Agente-cad-PYSIDE\.venv\Scripts\python.exe scripts/arete/jev_calibration_cli.py manifest `
  --project-id <ID> --obra Obra_TREINO_1 --pav 13_PAV `
  --dxf <DXF_Fase-1>

D:\Agente-cad-PYSIDE\.venv\Scripts\python.exe scripts/arete/jev_calibration_cli.py dry-run `
  --project-id <ID> --pav 13_PAV --dxf <DXF_Fase-1> `
  --classe PIL,LAJ --items P1,L309

D:\Agente-cad-PYSIDE\.venv\Scripts\python.exe scripts/arete/jev_calibration_cli.py import-known
```

`dry-run` também aceita `--index` (pasta de `qa_session_index.py build`) e `--n1-state-json` (estado SA congelado, como o 14_PAV da paridade VPS). `--manifest` reutiliza o G0 já gravado.

## Artefatos

| Arquivo | Quem vê |
|---|---|
| `run_manifest.json` | hashes DXF/N1/módulos e comparação local × registro VPS 25/09; `parity_claimed` é sempre falso |
| `source_packet.jsonl` | pergunta, evidência CAD, controles, handles; sem SA/QA/gabarito no `evidence` |
| `baseline.jsonl` | valor SA e gatilho; `visible_to_jev=false` |
| `adjudication.jsonl` | nesta fase `PENDENTE_G1` ou `CONVENCAO_INDETERMINADA` (L410) |
| `dry_run_audit.json` | elegíveis, `UNPACKABLE`, motivos de descarte |
| `jev_requests/*.json` | contrato `jev_sa_second_read_request/1` para validação local |

Pacote acima de 16 KB vira `UNPACKABLE` e não gera request. Fonte com `fase-2` / `recortes` / engenharia reversa é recusada.

Nomes de arquivo em `jev_requests/` passam por sanitização Windows (`:` `|` `<>` e nomes reservados). O `case_id` original permanece no JSON. A CLI falha se o número de `.json` visíveis e não vazios for diferente de `packed`.

Contorno PIL no pacote só entra se um loop DXF **fechado contém o rótulo**. Linha próxima sem essa prova vira `NEEDS_SOURCE`/`UNPACKABLE`, não `contour_ref` elegível.

## Próximo passo

Fase 2 LV/FV (catálogo v1, claim/NONE/OWN_STRETCH): `scripts/arete/relatorios/20260929_jev_calibracao_g2_lv_fv_claim/RELATORIO.md`. G3 runner reusa o helper existente só sobre pacotes que passem neste gate. G1 desta pasta G0/G2 não correu. O piloto posterior [`20260929_jev_calibracao_g3_g4_pilot`](../../scripts/arete/relatorios/20260929_jev_calibracao_g3_g4_pilot/RELATORIO.md) tem duas revisões cegas **sem consenso** em V411 nem em ownership N1. O closeout de cobertura não adicionou G1. Experimento v2 (13 `N1_DECISION_RELEVANT` **retirados**): [`20260929_jev_calibracao_catalog_v2_lv_cell/RELATORIO.md`](../../scripts/arete/relatorios/20260929_jev_calibracao_catalog_v2_lv_cell/RELATORIO.md) e correção [`20260929_jev_catalog_v2_lv_independent_audit/RELATORIO.md`](../../scripts/arete/relatorios/20260929_jev_catalog_v2_lv_independent_audit/RELATORIO.md). Stage 1 source-first LV (packed 0): [`20260929_jev_catalog_v3_lv_source_encounter/RELATORIO.md`](../../scripts/arete/relatorios/20260929_jev_catalog_v3_lv_source_encounter/RELATORIO.md).
