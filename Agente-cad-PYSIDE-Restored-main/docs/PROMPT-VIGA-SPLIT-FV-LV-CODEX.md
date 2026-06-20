# PROMPT — Refactor "Viga Split FV/LV em todos os níveis" para Codex

> Copie tudo abaixo da linha para um chat novo do Codex.

---

## MISSÃO
Separar a **viga** em **dois elementos: Fundo (FV) e Lateral (LV)**, em **todos os níveis** (motor, dados, fichas, comparison, UI), de forma **faseada e NÃO-destrutiva**. Objetivo: alinhar o N1 (Structural Analyzer) com o N2 (Eng. Reversa) e com os robôs FV/LV, que já são separados.

## LEIA ANTES (fonte da verdade)
Em `D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\docs\`:
1. `SPEC-VIGA-SPLIT-FV-LV.md` ← **principal** (regra de domínio + fases)
2. `MASTERPLAN-FICHAS-F1-F9-HARMONIZACAO.md` (taxonomia; F5=N2, F7=N1)
3. `MASTERPLAN-LOOP-TREINO-MOTOR.md` (§6 tem o mismatch FV/LV)

## REGRA DE DOMÍNIO (do dono — não inventar)
Cada **viga tem nome** (ex. `V1`) e gera **exatamente 2 fichas** (não múltiplas), com segmentos **aninhados** dentro:
```
Viga V1
├── Ficha FV (Fundo) — 1 por viga
│     └── sub-fichas: 1 por segmento de fundo (N segmentos)
└── Ficha LV (Lateral) — 1 por viga
      └── sub-fichas: segs lado A + segs lado B + N visões-corte (VC)
```
- **1 ficha FV + 1 ficha LV por viga.** Segmentos vivem DENTRO da ficha (aninhados), nunca como fichas irmãs.
- FV: nº de segmentos de fundo (cada um = 1 sub-ficha).
- LV: segmentos A + B + visões-corte, conforme quantidade/variedade de segmentos e cruzamentos.
- Cada viga é um caso — nº de segmentos diverge.

## REPO / DADOS
- Raiz: `D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main` · Banco: `D:\Agente-cad-PYSIDE\project_data.vision` (1.35 GB)
- Motor da viga: `src/core/beam_tracer.py` (`detect_beams`; fundo em `geometry.classified.merged_bottom_lengths`)
- N1 vigas: tabela `beams` (1 registro/viga, `is_validated`, `validated_fields_json`) — campos fundo `viga_fundo_*`, laterais `viga_a_seg_*`/`viga_b_seg_*`
- N2 gabarito: `reverse_eng_fichas` — FV `campos_json.segments_rich` (lista de segmentos); LV `campos_json.panels_A`/`panels_B`/`section_views`
- Materialização N1/F7: `main.py · process_pillars_action()` → `save_fase3_fichas`
- Card UI: `main.py · _process_with_reverse_engineering()` (n1_report)

## ⚠️ ESTRUTURA EXISTENTE — REAPROVEITAR, NÃO RECRIAR
O N2 **já tem** a estrutura aninhada certa (segments_rich / panels_A/B / section_views). **Bug a consolidar:** N2 atual tem duplicação (FV = 271 fichas para 137 vigas ≈ 2/viga). Alvo = 1 ficha/viga. **Não replicar a duplicação no N1.**

## FASES (não-destrutivo — backup do `.vision` antes de qualquer escrita estrutural)
- **Fase 0 — Modelo.** Tabela aditiva `beam_elements` (`parent_beam_id`, `viga_nome`, `classe`∈{FV,LV}, `campos_json` com segmentos aninhados, `n_segmentos`, `is_validated`). **1 linha por (viga × classe).** Não tocar `beams`.
- **Fase 1 — UI.** Card Fº7 mostra, por viga, fichas FV/LV + **contagem de segmentos** (FV: nº fundo; LV: A+B+VC) lidos do dado da viga.
- **Fase 2 — Fichas.** Materialização do F7 gera 1 ficha FV + 1 ficha LV por viga, com segmentos aninhados (espelhando o schema N2).
- **Fase 3 — Motor.** `beam_tracer` decompõe explicitamente a viga em FV (segmentos de fundo) e LV (segs A/B + VC).
- **Fase 4 — Comparison.** Comparar FV(N1)×FV(N2) e LV(N1)×LV(N2) separadamente. **N2-LV ainda em ajuste → tratar como referência fraca.**

**Gate por fase:** contagem de segmentos bate com inspeção manual de 1 viga conhecida; robôs FV/LV continuam funcionando; sem regressão no Comparison.

## RESTRIÇÕES
NÃO migrar/destruir `beams` · backup do `.vision` antes · abordagem aditiva · N2-LV é referência fraca · branch git separada · commits por fase · edições cirúrgicas.

## ENTREGÁVEL
Fases 0→4 validadas na obra-piloto **Obra_TREINO_1, pavimento 13** (`project_id 4869be2b-f17c-410b-a9c8-98a887ec1c95`). Relatório em `docs/VIGA-SPLIT-RELATORIO.md` (antes/depois: nº fichas FV/LV e nº segmentos por viga). Comece **lendo o SPEC** e inspecionando 1 viga (FV `segments_rich` + LV `panels_A/B`/`section_views`) antes de codar.
