# Changelog

## 1.9.2 — 2026-07-16

- Ganchos automáticos de `cycle_phase` no `qa_loop_executor`: review/coverage→validate,
  visual/fix/test records, teach/question→train, advance pós-fix→regen.
- Rubrica evita dupla contagem (prefere eventos `cycle_phase`).
- Testes de auto-phase + `cycle_efficiency` no RESUME/session_metrics.

## 1.9.1 — 2026-07-16

- Doc `docs/QA-CICLO-EFICIENCIA-E-AUTORIDADE.md`: loop treino×validação×visual, **🟠 juiz `qa_agente`**, permitido vs proibido.
- Rubrica `arete.qa_cycle_efficiency/v1` (`qa_cycle_efficiency.py`) em `session_metrics` + RESUME.
- CLI `qa_loop_executor.py record-cycle --phase train|validate|visual|fix|regen`.
- Checklist `checklists/permitido-vs-proibido-ciclo.md`.

## 1.9.0 — 2026-07-16

- Stage-2 residual (exceto #2 cross-obra e #6 MCP, adiados pós-obra completa 4 classes).
- `qa_g2v_record_verdict.py` + template de veredito G2-V padronizado (pack dossiê, anti-super-selo).
- `session_metrics.llm_usage` + CLI `qa_loop_executor.py record-llm` (tokens/custo).
- FV: furos/cortes/aberturas com polígono, centróide e near_fundo no adaptador CAD.
- PIL: `_geometry_class` (ret/L-U/circular/especial), `_edge_lengths`, `_audit_dim` nonrect (bbox não prova L/U), faces A–H.
- Handoff: `qa_handoff_assets` (KPIs treino×validação + quadro) no `write_reports` e RESUME.
- Reaudit CEO-AUDIT Stage-2 **89/A** + `DEFERRED-OPEN-ITEMS-POS-OBRA-COMPLETA.md`.

## 1.8.0 — 2026-07-16

- Paridade multi-classe: `qa_class_golden_regression.py` (PIL/LAJ/FV/LV, paralelo).
- `qa_g2v_visual_gate.py` v2 para as 4 classes em paralelo.
- Mapa de capacidade: `data/class_capability_matrix.json` + `qa_class_capability.py` + `docs/QA-CAPACIDADE-POR-CLASSE.md`.
- `qa_fv_lv_golden_regression.py` vira wrapper de compatibilidade.

## 1.7.0 — 2026-07-16

- Aba UI **QA Global de Evidências** (MainWindow tab 9) + disclaimer nas prefichas N1/PIL.
- Handoff com paths absolutos (resumo + RESUME) e `duration_seconds` em session_metrics.
- `qa_error_memory` (recorrência por família) + ingest automático de achados no dossiê.
- `qa_g2v_visual_gate` (prontidão visual FV/LV) + checklist anti-super-selo.
- Dossiê template com SHA por decisão; reaudit operacional **87/A**.
- Doc `docs/INTEGRACAO-APP-AGENTE.md` + scaffold golden cross-obra.

## 1.6.0 — 2026-07-16

- FV: auditoria de `cortes`/`aberturas` (N/A sem geometria; CONFIRMAR com entidade existente).
- LV: aberturas `viga_*_abert_pilar_*` com dist/larg + label de identidade.
- Dim FV: aceita match de espessura (menor cota × menor aresta do contorno).
- Golden multi-item: `scripts/arete/qa_fv_lv_golden_regression.py` + baseline.
- Apply/snapshot de `beams` sem exigir `extra_data_json`.

## 1.5.0 — 2026-07-16

- Adaptadores CAD `FvEvidenceAuditor` / `LvEvidenceAuditor` (`scripts/arete/qa_fv_lv_adapters.py`).
- CLASS_REGISTRY + authority_matrix: FV/LV `validation_ready` (limites por família).
- Migração RAG: colunas nativas `tier`/`field_id`/`familia`/`pavimento` em `semantic_rag_kb`
  (`scripts/arete/migrate_semantic_rag_tier_columns.py`); promote grava colunas quando existem.

## 1.4.0 — 2026-07-16

- Harmonização pós meta-auditoria CEO-AUDIT (`AUDIT-QA-GLOBAL-EVIDENCIAS-2026-07-16`).
- `data/authority_matrix.json` + `scripts/arete/qa_authority_matrix.py` (CI anti-drift).
- Autoridade PIL alinhada a `validation_ready` (código/PROVENIENCIA); skill/squad/masterplan/perfil sincronizados.
- Tasks com aceite negativo; command AIOS cobre `*probe-profile`/`*smoke-n3`/`*teach`.
- `validate_squad.py` dual score (structural + operational do CEO-AUDIT).
- `session_metrics.v1` no `qa_loop_executor` a cada persist.
- RAG: filtro de tier via JSON embutido + `require_tier` fail-closed.
- Apresentação ≠ prova: banner em `ficha_motor_item` + `qa_presentation_notice` + painel UI mínimo de dossiê.
- CLI `qa_open_latest_dossier.py` para abrir última prova.

## 1.3.0 — 2026-07-13

- Executor persistente `qa_loop_executor.py` com budget, retomada, ledger e ensino humano estruturado.
- Adaptador PIL `qa_pil_coverage.py` para identidade, faces, PARA, PASSA e montagem.
- Promoção QG7, visão e RAG permanecem checkpoints humanos; nenhum apply PIL foi liberado.

## 1.2.0 — 2026-07-13

- Adicionados perfis executáveis e premissas N1/N3 específicas para PIL, LAJ, FV e LV.
- Adicionado `qa_n3_smoke.py` para identidade/camadas por contrato e variante.
- Escopo de projeto e resultados `PENDENTE` passaram a falhar fechado no CLI.
- Separadas semanticamente as famílias FV/LV na tabela compartilhada `beams`.
- Paridade vazia deixou de produzir PASS; ficha registra hashes DXF, SVG e HTML.
- Validados exemplares reais de cada classe no 13_PAV sem ampliar a autoridade.
- Corrigida a leitura de proveniência LV: origem/slot são por segmento e
  `behavior_isolated`/`fv_dimension_fallback` pertencem a `_sa_meta`.

## 1.1.0 — 2026-07-13

- Adicionado probe N1 ultragranular, com campos/checks declarados e cross-classe consultivo.
- Adicionadas paridade de artefatos e ficha individual com hashes de contrato.
- Cache por conteúdo passou a invalidar por versão e entradas relevantes.
- Adicionados benchmark reproduzível e consulta RAG tipada/fail-closed.
- Autoridade do PASS explicitamente limitada à hipótese testada.

## 1.0.0 — 2026-07-13

- Criada squad task-first do QA Global de Evidências.
- Adicionado roteamento dinâmico N1/N3/N4/RAG por escopo e variante.
- Formalizados gates anti-leakage, visual CLI, perguntas estruturadas e cache por hash.
- Registrada autoridade atual: LAJ `validation_ready`; PIL/FV/LV `diagnostic_only`.
- MCP e hooks automáticos adiados até promoção segura dos adaptadores.
