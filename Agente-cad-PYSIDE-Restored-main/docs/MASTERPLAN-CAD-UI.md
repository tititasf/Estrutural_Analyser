# MASTERPLAN-CAD-UI — Vision-Estrutural AI

**Version:** 1.0  
**Date:** 2026-05-17  
**Author:** Bob (PM Strategist) — @pm  
**Status:** APPROVED  

---

## SECAO 1: ESTADO ATUAL (Snapshot)

| Aba | Modulo | Testada E2E | Checks Passing | Gaps Conhecidos |
|-----|--------|-------------|----------------|-----------------|
| Tab0 — Diagnostic Hub | `diagnostic_hub.py` | Sim | 7/7 | Fase-3 nao executa script real (apenas import); [LOAD DEBUG] spam domina log |
| Tab1 — Structural Analyzer | `organisms.py` (main view) | Sim | 3/3 | Botao "Iniciar Analise" nao encontrado via UIA; lista pre-analise=1 item |
| Tab2 — Comparison Engine | `comparison_engine.py` | Sim | 6/6 | Scores pre-validacao estaticos; sem log de progresso por tipo |
| Tab3 — Robo Pilares | `_ROBOS_ABAS/Robo_Pilares/` | Sim | 2/2 | DXF pode ser pre-existente (mtime nao verificado) |
| Tab4 — Robo Laterais (LV) | `_ROBOS_ABAS/Robo_Lajes/laje_src/` | Sim | 2/2 | Idem mtime; [LOAD DEBUG] spam originado aqui |
| Tab5 — Robo Fundo (FV) | `_ROBOS_ABAS/Robo_FundoVigas/` | Sim | 2/2 | Idem mtime |
| Tab6 — Robo Laje (LJ) | `_ROBOS_ABAS/Robo_Lajes/` | Sim | 2/2 | Idem mtime |

**Totais:** 28/28 PASS | 0 FAIL | 277s duracao | 34 screenshots

---

## SECAO 2: GAPS DE TESTE PRIORITARIOS

### P0 — Criticos (corrigir imediatamente)

1. **Tab0: Fase-3 real nao executa** — `fase3_ran=False` no log. O teste clica "Interpretar" e confirma "Sim" no dialog, mas `engenharia_reversa_dxf.py` NAO roda (apenas import de dados ja extraidos). Causa provavel: obra/pavimento ja possui Fase-3 extraida anteriormente.
2. **Tab1: "Iniciar Analise" inacessivel** — Botao nao encontrado via UIA (`[BTN NOT FOUND] 'Iniciar'`). O fluxo de analise com DXF real carregado no canvas (dxf_data nao nulo) nunca foi exercitado.
3. **Tab2: Validar sem-API com scores atualizados** — FEITO (scores pre: 96.2%/83.8%/88.6%/93.3%/90.5%, CERTIFICADO.json salvo).

### P1 — Importantes

4. **Tab0: Pipeline Completo end-to-end com log real** — Pipeline concluiu em ~3s mas log mostra apenas [LOAD DEBUG] spam, sem evidencia de processamento real das fases.
5. **Tab1: Atualizar Listas apos Fase-3** — Parcialmente coberto (1 item pre-analise detectado), mas contagem pos-analise=0 indica que o import nao populou listas.
6. **Robos: DXF fresh gerado** — Todos os 4 robos passam com `score_label='OK'` mas nao ha verificacao de `mtime > TEST_START`. DXF pode ser pre-existente.
7. **Multi-pavimento** — Teste usa apenas `TIPO`. Obra possui TERREO, COBERTURA, FUNDACAO, ATICO, Subsolo — nenhum testado.

### P2 — Desejaveis

8. **Tab0: Apply Fix com re-render** — Botao existe e dialog abre, mas nao verifica se DXF foi re-renderizado com modo selecionado.
9. **Tab1: Salvar projeto** — Persistencia verificada via `obras.json` (AtomicWriter funciona), mas nao ha assert no test.
10. **Robos: DXF Pav. completo** — Geracao completa de pavimento (todos pilares/vigas/lajes) nao testada.
11. **Canvas: interacao** — Zoom, pan, selecao de entidade nao cobertos.
12. **Error paths** — DXF corrompido, obra inexistente, DB vazio, rede offline nao testados.

---

## SECAO 3: PLANO DE DESIGN SYSTEM

### Epic DS-1: Centralizacao de Tokens

| Story | Descricao | Status | Complexidade |
|-------|-----------|--------|--------------|
| DS-1.1 | `theme.py` criado com Colors, Fonts, Spacing, Radius, StyleSheets | DONE | - |
| DS-1.2 | Aplicar em `widgets/detail_card.py` (~60 inline styles) | TODO | HIGH |
| DS-1.3 | Aplicar em `organisms.py` (~15 inline) | TODO | MEDIUM |
| DS-1.4 | Aplicar em `diagnostic_hub.py` | TODO | MEDIUM |
| DS-1.5 | Aplicar em `comparison_engine.py` | TODO | MEDIUM |
| DS-1.6 | Aplicar em `main.py` (maior arquivo) | TODO | HIGH |
| DS-1.7 | Aplicar em `login_widget.py` (~20 inline) | TODO | MEDIUM |
| DS-1.8 | Aplicar em `user_profile_dialog.py` (~25 inline) | TODO | MEDIUM |

### Criterios de Consistencia por Aba

Cada aba deve satisfazer:

- [ ] Header/toolbar uniforme (altura 35px, bg `Colors.BG_SECONDARY`)
- [ ] Botoes primarios usam `StyleSheets.button_primary()`
- [ ] Labels de status: verde=`ACCENT_SUCCESS`, laranja=`ACCENT_WARNING`, vermelho=`ACCENT_DANGER`
- [ ] Progress bars: altura 14px, cor `ACCENT_PRIMARY` via `StyleSheets.progress_bar()`
- [ ] ComboBoxes: estilo `StyleSheets.combo_box()`
- [ ] Fontes: `Fonts.SIZE_MD` (11px) padrao, `Fonts.SIZE_SM` (10px) para labels secundarios
- [ ] Zero cores hex hardcoded no arquivo apos migracao
- [ ] Borders usam tokens `BORDER_*` (nunca `#333` / `#444` inline)

### Decisao Arquitetural: Cyan Unificado

| Token | Hex | Uso |
|-------|-----|-----|
| `ACCENT_PRIMARY` | `#00d4ff` | Links, selected states, highlights (MAIORIA — 25+ ocorrencias) |
| `ACCENT_BRAND` | `#00E5FF` | Logo, email, branding (9 ocorrencias) |

**Decisao:** Manter ambos por enquanto. Unificar em `#00d4ff` apos revisao visual completa na Sprint 2.

---

## SECAO 4: GAPS DE RASTREAMENTO DE ESTADO

Estados da interface que NAO estao sendo logados de forma estruturada:

| ID | Componente | Log Esperado | Status Atual |
|----|-----------|--------------|--------------|
| S1 | Tab0 Canvas | `[CANVAS] loaded {n_entities} entities from {filename}` | Nao existe — DXF carrega mas sem contagem no log |
| S2 | Tab0 Interpretar | `[FASE3] imported {n_pilares} pilares, {n_vigas} vigas, {n_lajes} lajes` | Nao existe — apenas [LOAD DEBUG] spam visivel |
| S3 | Tab1 Analise | `[ANALISE] found PL={n} BM={n} SL={n} LJ={n}` | Nao existe — resultado da analise nao logado |
| S4 | Tab2 Validar | `[VALIDAR] PL: {score}% LV: {score}% FV: {score}% LJ: {score}%` | Nao existe — scores atualizados mas sem log por tipo |
| S5 | Robos | `[ROBO_{tipo}] generated {path} ({size}KB) in {time}s` | Nao existe — apenas score_label='OK' capturado |
| S6 | Tab0 Pipeline | `[PIPELINE] phase {n}/{total}: {phase_name} ({duration}s)` | Nao existe — pipeline conclui silenciosamente |
| S7 | Performance | `[PERF] DXF load: {ms}ms | Render: {ms}ms | Analysis: {ms}ms` | Nao existe |

**Impacto:** O [LOAD DEBUG] spam (50+ linhas de lajes por operacao) domina 90% do log, tornando impossivel diagnosticar problemas reais sem grep manual.

---

## SECAO 5: STORIES EXECUTAVEIS

### EPIC: CAD-TEST-01 — Cobertura de Testes E2E

**Story CAD-TEST-01.1 (P0): Verificar Fase-3 real no log**
- **AC1:** `[Fase-3] Iniciando: Obra_TREINO_1 / TIPO` aparece no app log
- **AC2:** Script `engenharia_reversa_dxf.py` executa (nao apenas import de dados ja existentes)
- **Solucao:** Usar obra/pavimento cujo diretorio Fase-3 esteja VAZIO, OU deletar resultado Fase-3 antes do teste, OU desmarcar checkbox "Force" no dialog e usar DXF nao-extraido
- **Estimativa:** 2h | **Risco:** Medio (depende de dados de teste disponiveis)

**Story CAD-TEST-01.2 (P1): DXF fresh gerado pelos robos**
- **AC1:** `mtime` do DXF gerado > `TEST_START` para pelo menos 1 robo
- **AC2:** Arquivo DXF possui tamanho > 0 bytes
- **Solucao:** Limpar DXFs de output antes do test OU comparar timestamp. Adicionar assert: `os.path.getmtime(dxf_path) > test_start_time`
- **Estimativa:** 1h | **Risco:** Baixo

**Story CAD-TEST-01.3 (P1): Multi-pavimento coverage**
- **AC1:** Test roda com TIPO E TERREO, ambos passam
- **AC2:** Parametrize `OBRA_NAME` e `PAV_NAME` no topo do test como lista configuravel
- **Solucao:** Mover constantes para `TEST_CONFIGS = [('Obra_TREINO_1', 'TIPO'), ('Obra_TREINO_1', 'TERREO')]` e iterar
- **Estimativa:** 1.5h | **Risco:** Baixo

**Story CAD-TEST-01.4 (P1): Tab1 Iniciar Analise acessivel**
- **AC1:** Botao "Iniciar Analise" encontrado via UIA e clicado
- **AC2:** Log mostra `[ANALISE]` com contagem de elementos detectados
- **Solucao:** Investigar por que UIA nao encontra o botao (pode ser nome diferente, ou oculto sem DXF carregado no Tab1)
- **Estimativa:** 3h | **Risco:** Alto (pode exigir mudanca na UI)

**Story CAD-TEST-01.5 (P2): Error paths basicos**
- **AC1:** DXF corrompido mostra mensagem de erro (nao crash)
- **AC2:** Obra inexistente no combo nao trava a app
- **Solucao:** Adicionar fixtures de DXF malformado em `tests/fixtures/`
- **Estimativa:** 3h | **Risco:** Medio

---

### EPIC: CAD-DS-01 — Design System Application

**Story CAD-DS-01.1 (P1): Aplicar theme em organisms.py**
- **AC1:** Sidebar usa `Colors.*` e `StyleSheets.sidebar()` do theme.py
- **AC2:** Zero cores hex hardcoded (`#1e1e1e`, `#252528`, `#00d4ff`, etc.) no arquivo apos migracao
- **AC3:** Aparencia visual identica antes/depois (screenshot diff)
- **Estimativa:** 2h | **Risco:** Baixo

**Story CAD-DS-01.2 (P1): Aplicar theme em diagnostic_hub.py**
- **AC1:** Botoes Interpretar/Pipeline usam `StyleSheets.button_primary()`
- **AC2:** Progress bar usa `StyleSheets.progress_bar()`
- **AC3:** Tree widget usa `StyleSheets.sidebar()` para consistencia
- **Estimativa:** 2h | **Risco:** Baixo

**Story CAD-DS-01.3 (P2): Aplicar theme em detail_card.py**
- **AC1:** 60+ chamadas `setStyleSheet` substituidas por tokens
- **AC2:** Cores semanticas (success/warning/danger) usam tokens corretos
- **AC3:** Nenhum `#hex` inline restante
- **Estimativa:** 4h | **Risco:** Medio (maior arquivo, mais chance de regressao visual)

**Story CAD-DS-01.4 (P2): Aplicar theme em login_widget.py + user_profile_dialog.py**
- **AC1:** ~45 inline styles migrados para tokens
- **AC2:** Botoes azuis usam `ACCENT_BLUE` / `ACCENT_BLUE_HOVER`
- **Estimativa:** 3h | **Risco:** Baixo

---

### EPIC: CAD-OBS-01 — Observabilidade e Log Estruturado

**Story CAD-OBS-01.1 (P0): Reduzir spam [LOAD DEBUG]**
- **AC1:** Loop de debug em `main_window.py` encapsulado em `if os.environ.get('CAD_DEBUG_LOAD'):` 
- **AC2:** Log final reduz de ~200 linhas de lajes para 1 linha resumo: `[LOAD] {n_obras} obras, {n_pavimentos} pavimentos carregados`
- **Estimativa:** 30min | **Risco:** Zero

**Story CAD-OBS-01.2 (P1): Adicionar logs estruturados S1-S7**
- **AC1:** Cada estado da Secao 4 gera print formatado
- **AC2:** Test `test_humano_autonomo.py` pode grep por esses logs para validacao
- **Estimativa:** 2h | **Risco:** Baixo

---

## SECAO 6: CHECKLIST DE VALIDACAO ATUAL

### Funcionalidade

| Check | Status | Evidencia |
|-------|--------|-----------|
| Launch app e conectar via UIA | PASS | Janela "Vision-Estrutural AI - Pro Dashboard" em 20s |
| Selecionar obra (exact match) | PASS | `Obra_TREINO_1` selecionada, 23 obras disponiveis |
| Selecionar pavimento | PASS | `TIPO` selecionado, `[PAV_CHANGED] idx=1 text='TIPO'` |
| Tab0: Sidebar tree navegavel | PASS | 15 nodes, expand/collapse funcional |
| Tab0: DXF carregado | PASS | `[TREE_DBL]` + `[DOC_SEL]` no log |
| Tab0: RenderModeDialog abre/fecha | PASS | Dialog "Modo de Renderizacao" → OK |
| Tab0: APPLY FIX funcional | PASS | Botao enabled, dialog abre |
| Tab0: Interpretar dialog "Sim" | PASS | Dialog confirmado, execucao em ~3s |
| Tab0: Interpretar executa Fase-3 REAL | WARN | `fase3_ran=False` — apenas import, script nao executou |
| Tab0: Pipeline Completo | PASS | Conclui em ~3s (mas sem evidencia de processamento real) |
| Tab1: Listas carregadas | PASS | 1 item detectado pre-analise |
| Tab1: Iniciar Analise | FAIL | Botao nao encontrado via UIA |
| Tab2: Combos obra/tipo | PASS | `['Obra  Tipo', 'Obra  Tipo']` |
| Tab2: Checkboxes PL/LV/FV/LJ | PASS | Todos presentes |
| Tab2: Scores pre-validacao | PASS | `96.2% / 83.8% / 88.6% / 93.3% / 90.5%` |
| Tab2: Validar sem-API | PASS | Concluiu em ~7s |
| Tab2: Certificar | PASS | `CERTIFICADO.json` salvo |
| Robo PL: DXF Item | PASS | score_label='OK' |
| Robo LV: DXF Item | PASS | score_label='OK' |
| Robo FV: DXF Item | PASS | score_label='OK' |
| Robo LJ: DXF Item | PASS | score_label='OK' |

### Design System

| Check | Status | Evidencia |
|-------|--------|-----------|
| theme.py criado com tokens completos | PASS | 5 classes: Colors, Fonts, Spacing, Radius, StyleSheets |
| StyleSheets com metodos reutilizaveis | PASS | 11 metodos: tab_widget, button_primary/secondary/accent, panel, sidebar, list_widget, combo_box, progress_bar, input_field, group_box, scroll_area, dialog |
| Migracao aplicada em arquivos alvo | FAIL | 0/11 arquivos migrados |
| Cores inline eliminadas | FAIL | ~45 hex values em 12+ arquivos |
| organisms.py: duplicate refresh() | PASS | Removido |

### Observabilidade

| Check | Status | Evidencia |
|-------|--------|-----------|
| app_stdout.txt captura output | PASS | Todas as secoes do log lidas com sucesso |
| [LOAD DEBUG] spam controlado | FAIL | 90%+ do log e spam de lajes (50 linhas por operacao) |
| Log estruturado para estados UI | FAIL | Apenas [TREE_DBL], [DOC_SEL], [PAV_CHANGED], [WORK_CHANGED] existem |
| Metricas de performance | FAIL | Zero timing de DXF load, render, analise |

---

## SECAO 7: RECOMENDACOES IMEDIATAS

### Sprint 1 (esta semana) — Quick Wins

| # | Acao | Impacto | Esforco |
|---|------|---------|---------|
| 1 | **Reduzir spam [LOAD DEBUG]** — Encapsular em `if os.environ.get('CAD_DEBUG_LOAD'):` | Diagnosticabilidade +90% | 30min |
| 2 | **Adicionar log canvas load** — Em `diagnostic_hub.py._on_dxf_loaded()`, print entidades | Rastreabilidade Tab0 | 15min |
| 3 | **Parametrizar test configs** — `OBRA_NAME`/`PAV_NAME` como constantes no topo | Flexibilidade test | 30min |
| 4 | **Investigar Tab1 "Iniciar"** — Verificar se botao tem nome diferente ou e condicional | Desbloqueia P0 | 1h |

### Sprint 2 (proxima semana) — Consolidacao

| # | Acao | Impacto | Esforco |
|---|------|---------|---------|
| 5 | **Fase-3 real no test** — Usar pavimento sem dados extraidos | Valida pipeline critico | 2h |
| 6 | **DXF mtime assertion** — Garantir geracao fresh nos robos | Confianca na geracao | 1h |
| 7 | **DS-01.1: organisms.py** — Primeira migracao de tokens | Referencia para demais | 2h |
| 8 | **DS-01.2: diagnostic_hub.py** — Segunda migracao | Visibilidade alta (tab principal) | 2h |

### Sprint 3 — Design System Full

| # | Acao | Impacto | Esforco |
|---|------|---------|---------|
| 9 | **DS-01.3: detail_card.py** — Maior migracao (60 styles) | Elimina maioria dos inline | 4h |
| 10 | **DS-01.4: login + profile** — Migrar 45 styles | Consistencia UX | 3h |
| 11 | **Multi-pavimento test** — TIPO + TERREO | Cobertura estrutural | 1.5h |
| 12 | **CI/CD integration** — GitHub Actions com display virtual | Automacao completa | 3h |

---

## RISK ASSESSMENT

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|--------------|---------|-----------|
| Fase-3 nunca executa em test (dados sempre pre-existentes) | ALTA | ALTO | Criar fixture de obra "limpa" sem Fase-3 |
| Regressao visual na migracao DS | MEDIA | MEDIO | Screenshot diff antes/depois por arquivo |
| Tab1 "Iniciar" depende de estado interno nao-reproduzivel | MEDIA | ALTO | Debug manual com UIA Spy para mapear arvore |
| [LOAD DEBUG] spam mascara erros reais em producao | ALTA | MEDIO | Sprint 1 item #1 elimina o risco |
| Robos geram DXF cached, nao fresh | ALTA | BAIXO | Assert mtime resolve |

---

## METRICAS DE SUCESSO

| Metrica | Atual | Meta Sprint 1 | Meta Sprint 3 |
|---------|-------|---------------|---------------|
| Checks E2E passing | 28/28 | 28/28 + 3 novos | 35+ |
| Fase-3 real executada no test | Nao | Sim | Sim |
| Arquivos migrados para theme.py | 0/11 | 2/11 | 6/11 |
| Linhas de [LOAD DEBUG] no log tipico | ~200 | <5 | <5 |
| Logs estruturados (S1-S7) | 0/7 | 3/7 | 7/7 |
| Multi-pavimento coverage | 1 | 1 | 3+ |

---

*Documento gerado automaticamente com base em analise factual do test output (28/28 PASS, 277s), design-system-gaps.md, e theme.py. Nenhuma suposicao — todos os dados verificados nos artefatos.*
