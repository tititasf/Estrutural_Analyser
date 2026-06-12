# MASTERPLAN — CAD Analyzer v5.0
**Data:** 2026-06-03 | **Status:** ATIVO
**Escopo:** Robot Quality Loop + Comparison Engine + Gerenciar Projetos + Sincronização Global

---

## VISÃO ESTRATÉGICA — PRIORIDADE REAL

```
TRILHA A — Robot Quality Loop (PRIORIDADE MÁXIMA)
  CE-001 + CE-004  →  Refinamento LV (4 vigas)  →  4× cada classe
      →  Fichas completas  →  Harmonização semântica  →  E2E

TRILHA B — UI/Infraestrutura (paralela ou posterior)
  PM-001 a PM-009  →  Gerenciar Projetos completo

Dependência crítica: CE-001 e CE-004 são pré-requisitos da Trilha A.
Tudo mais em PM pode esperar o quality loop estar maduro.
```

---

## TRILHA A — ROBOT QUALITY LOOP

### QA-001: CE fixes para habilitar o quality loop
**Prioridade:** BLOQUEANTE para Trilha A  
**Stories:** CE-001 (layout), CE-003 (renomear botões), CE-004 (N2 dinâmico)  
**Por que primeiro:** Sem CE-004, o N2 é estático e não rastreia o DXF de eng. reversa por obra/pavimento. O ciclo de comparação N1 vs N2 vs N3 não funciona de forma ágil.

---

### QA-002: Refinamento LV — 4 Vigas de Teste
**Prioridade:** P0 — core do produto  
**Contexto:** 4 vigas (V4, V5, V6, V7) estão sendo testadas. Ainda há erros a refinar.  
**Critério de saída desta etapa:**
- Score comparison N1 vs N2 ≥ 85% em todas as 4 vigas
- N3 (robot gerado) visualmente correto vs N1 (estrutural real)
- Ficha de cada viga no CE com dados coerentes (h, b, laje_sup, laje_inf, seções)
- Zero regressões nas vigas já aprovadas ao corrigir as problemáticas

**Processo de refinamento por viga:**
```
1. Selecionar viga no CE (N1 carrega DXF estrutural, N2 carrega eng. reversa, N3 PNG robot)
2. Identificar delta: o que N3 tem que N1 não tem, e vice-versa
3. Corrigir no gerador (gerar_lv_dxf_stog.py) ou na ficha (fichas_lv_v2)
4. Regenerar N3 → re-comparar
5. Registrar resultado na ficha de validação
```

**Vigas em teste:** V4, V5, V6, V7  
**Arquivos:** `scripts/gerar_lv_dxf_stog.py`, `data/fichas_lv_v2/`, `DADOS-OBRAS/Obra_TREINO_*/`

---

### QA-003: Expansão para todas as classes — 4× cada
**Prioridade:** P1 — após QA-002 aprovado  
**Objetivo:** Ter fichas de validação de 4 amostras de cada classe estrutural no CE.

| Classe | Qtd amostras | Script gerador | Status |
|--------|-------------|----------------|--------|
| LV — Laterais de Viga | 4 (V4/V5/V6/V7) | `gerar_lv_dxf_stog.py` | Em refinamento |
| PL — Pilares | 4 | `gerar_pl_dxf_stog.py` | Pendente após LV |
| LJ — Lajes | 4 | `gerar_lj_dxf_stog.py` | Pendente após LV |
| FV — Fundo de Viga | 4 | `gerar_fv_dxf_stog.py` | Pendente após LV |

**Critério de saída:** CE tem 16 itens de fichas (4 × 4 classes) com N1/N2/N3 carregados e scores ≥ 85%.

---

### QA-004: Harmonização Semântica
**Prioridade:** P1 — após QA-003  
**Objetivo:** Com todas as espécies de fichas no CE, garantir que os campos semânticos (h, b, laje_sup, laje_inf, seções, grades, sarrafos) são extraídos consistentemente entre obras diferentes da mesma classe.

**Processo:**
```
Para cada classe (LV/PL/LJ/FV):
  1. Comparar fichas das 4 amostras entre si
  2. Identificar variações legítimas vs bugs de extração
  3. Documentar regras semânticas canonizadas
  4. Atualizar extratores + geradores
  5. Re-validar as 4 amostras
```

**Output:** `docs/SEMANTICA-CANONICA-{CLASSE}.md` por classe

---

### QA-005: E2E Multi-Obra
**Prioridade:** P2 — após QA-004  
**Objetivo:** Pipeline completo Fase 1→8 funcionando em 3+ obras diferentes sem intervenção manual.

**Critério de saída:**
- Selecionar obra no CE → N1/N2/N3 carregam automaticamente
- Processar pipeline completo (Fases 1-6) em 3 obras distintas
- Score médio ≥ 80% em todas as obras
- Zero regressões nas obras de treino já aprovadas

---

---

## ESTADO ATUAL — SESSÃO 2026-06-03

### Trilha B (UI/Infra) — CONCLUÍDA ✅

| Sprint | Item | Status |
|--------|------|--------|
| 0 | DXFVectorView vetorial N1/N2, OOM caps, viewport culling | ✅ COMMITADO |
| 0 | Fix fundo branco `_resolve_css()`, labels duplicados, gate admin | ✅ COMMITADO |
| 1 | CE-001: layout esquerdo 270px (Fase8+NavSidebar) | ✅ |
| 1 | CE-003: botões → "Gerar Crop N3" | ✅ |
| 1 | PM-001: 3 métodos duplicados removidos | ✅ |
| 1 | PM-003: seletor pavimento Fases 6 e 7 | ✅ |
| 2 | CE-002: botões "Iniciar Análise Geral" + "Fase 4" | ✅ |
| 2 | CE-006: CE→SA via signal em main.py | ✅ |
| 2 | PM-002: scan filesystem Fase 1 + botão "Indexar Tudo" | ✅ |
| 3 | CE-004: N2 dinâmico via dxf_discovery.json | ✅ |
| 3 | PM-006: Fase 2 classe 3 Eng. Reversa (grid + classificação) | ✅ |
| 4 | CE-005 + PM-009: sync global bidirecional CE↔top bar↔Gerenciar Projetos | ✅ |
| 4 | PM-004: Fase 6 grid DXF granular por classe + botão Gerar | ✅ |
| 4 | PM-005: Fase 7 grid consolidação + botão Gerar Consolidado | ✅ |
| 4 | PM-007: Fase 8 dashboard scores/certificação/exportar | ✅ |
| 4 | PM-008: DataPipelineView aba "📊 PIPELINE" | ✅ |

### Trilha A (Robot Quality Loop) — EM ANDAMENTO

| Item | Status |
|------|--------|
| QA-001: pré-requisitos CE (bloqueante) | ✅ via CE-001/CE-004 |
| QA-002: refinamento LV 4 vigas (V4–V7) ≥85% | 🔄 PRÓXIMO |
| QA-003: expansão PL/LJ/FV 4× cada | ⏳ após QA-002 |
| QA-004: harmonização semântica | ⏳ após QA-003 |
| QA-005: E2E multi-obra | ⏳ após QA-004 |

---

## DIAGNÓSTICO COMPLETO

### Gerenciar Projetos (`project_manager.py` — 3375 linhas)
- Sidebar obras, cards de pavimento, fases 1–8 com abas
- Fases 3, 4, 5: seletor ComboBox de pavimento ← **fases 6 e 7 NÃO têm**
- `auto_indexer.py` existe mas **nunca é chamado pela UI** → docs não aparecem na Fase 1
- `DataPipelineView` existe mas estava presa em `AdminDashboard` (admin only) ← gate removido
- Métodos duplicados: `load_projects` stub (L1453), `_convert_to_specific_version` corrompido (L2549), `create_new_project` versão simples (L3248) sobrescrevendo a boa (L2997)

### Comparison Engine (`comparison_engine.py` — 2432 linhas)
**Layout atual:**
```
[NavSidebar 215px fixo] | [TriLevelArea flex] | [Fase8Panel direita]
```
**Fase8Panel contém:**
- ComboBox Obra + ComboBox Pavimento (próprios, não sincronizados com global)
- Label "Tipos:" + 4 checkboxes (LV/PL/LJ/FV) — desnecessários por ora
- CheckBox "Só estrutural (sem API)"
- Botão "▶ Validar" — desfuncional por ora
- ProgressBar, scores, botão "Certificar Obra"
- Lista de histórico de validações

**NavSidebar contém:**
- Título "Classes / Itens"
- TreeWidget com itens (LV, PL, etc.)
- Botão "▶ Processar Item"
- Botão "⚡ Processar Todas"

**N2 (Eng. Reversa) — motor não existe ainda**
- DXFVectorView carregado mas o path do DXF de eng. reversa é estático
- Não há rastreamento dinâmico por obra/pavimento
- Não há zoom/crop centrado no item selecionado

### Sincronização Global — Estado Atual
- Cada módulo tem seus próprios ComboBoxes de Obra/Pavimento
- `_tag_robo_obra_combo` existe em main.py mas só para robôs (PL/LV/FV/LJ)
- Structural Analyzer, Comparison Engine e Gerenciar Projetos NÃO sincronizam com top bar

---

## STORIES DO PLANO

---

### CE-001: Comparison Engine — Reestruturação UI (Layout + Limpeza)
**Prioridade:** P1  
**Arquivo:** `src/ui/modules/comparison_engine.py`  
**Critério de aceite:**
- Fase8Panel posicionado JUNTO ao NavSidebar (ambos na esquerda, separados por divisor leve)
- Checkboxes "Tipos:" e label removidos
- Botão "▶ Validar" removido (ou oculto, preservado como `self.btn_validate.hide()`)
- ComboBoxes Obra e Pavimento com `setMinimumHeight(32)` para melhor legibilidade
- Lista (TreeWidget) abaixo dos ComboBoxes na mesma coluna esquerda

**Novo layout:**
```
[Coluna Esquerda: ComboBoxes + Lista + Botões] | [TriLevelArea N1/N2/N3 flex]
```

**Implementação:**
Em `ComparisonEngineModule.__init__`:
```python
layout = QHBoxLayout(self)

# Painel esquerdo unificado
left_panel = QFrame()
left_lay = QVBoxLayout(left_panel)
left_panel.setFixedWidth(260)

# 1. ComboBoxes do Fase8Panel (mover para cá)
# 2. NavSidebar (lista + botões)
# 3. Fase8Panel restante (scores, certificar) — colapsável

layout.addWidget(left_panel)
layout.addWidget(self.tri_level, 1)
```

---

### CE-002: Comparison Engine — Botões "Iniciar Análise Geral" e "Fase 4"
**Prioridade:** P1  
**Arquivo:** `src/ui/modules/comparison_engine.py`  
**Descrição:** Adicionar abaixo da lista os mesmos botões que o Structural Analyzer tem, pois têm ligação direta com o preenchimento das fichas N3 (via Fase 3 e Fase 4).

**Critério de aceite:**
- Botão "▶ Iniciar Análise Geral" — chama a mesma lógica do Structural Analyzer (processa DXF N1, preenche lista de itens)
- Botão "⚙ Fase 4" — dispara `motor_fase4.py` para o pavimento selecionado
- Ao concluir, a lista é recarregada automaticamente

**Implementação:**
```python
btn_analise = QPushButton("▶ Iniciar Análise Geral")
btn_analise.clicked.connect(self._on_iniciar_analise)

btn_fase4 = QPushButton("⚙ Fase 4 — Sync Robôs")
btn_fase4.clicked.connect(self._on_fase4_sync)
```

`_on_iniciar_analise`: emite signal para o módulo pai (main.py) disparar o Structural Analyzer  
`_on_fase4_sync`: subprocess `motor_fase4.py --obra {obra} --pavimento {pav}`

---

### CE-003: Comparison Engine — Revisar duplicação "Processar Item / Processar Todas"
**Prioridade:** P1  
**Arquivo:** `src/ui/modules/comparison_engine.py`  
**Diagnóstico:**
- `NavSidebar` tem "▶ Processar Item" e "⚡ Processar Todas"
- Esses processam os **crops do N3** (robot gerado → PNG)
- NÃO são duplicatas dos botões de análise (que processam N1 DXF estrutural)
- São funções distintas — manter ambos mas renomear para clareza

**Critério de aceite:**
- "▶ Processar Item" → renomear para "▶ Gerar Crop N3 (item)"
- "⚡ Processar Todas" → renomear para "⚡ Gerar Crops N3 (todos)"
- Adicionar tooltip explicando o que cada um faz

---

### CE-004: Comparison Engine — Motor N2 (Eng. Reversa) dinâmico
**Prioridade:** P2  
**Arquivo:** `src/ui/modules/comparison_engine.py`  
**Descrição:** Ao selecionar um item na lista, N2 deve auto-localizar o DXF de eng. reversa e fazer zoom centrado na região do item.

**Critério de aceite:**
- Ao selecionar obra/pavimento, sistema rastreia DXFs em `DADOS-OBRAS/{obra}/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa/`
- Ao selecionar item (ex: V4), viewport do N2 centraliza e faz crop na bbox do item
- Se nenhum DXF de eng. reversa encontrado: N2 mostra placeholder "DXF Eng. Reversa não encontrado para esta obra"
- Botão "▶ Processar Eng. Reversa" — indexa e carrega o DXF de eng. reversa

**Implementação:**

```python
def _find_eng_reversa_dxf(self, obra: str, pav: str) -> Path | None:
    base = DADOS_OBRAS_ROOT / obra / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    if not base.exists():
        return None
    # Primeiro tentar match por pavimento no nome do arquivo
    for f in base.glob("*.dxf"):
        if pav.upper() in f.stem.upper():
            return f
    # Fallback: primeiro DXF encontrado
    dxfs = list(base.glob("*.dxf"))
    return dxfs[0] if dxfs else None
```

`TriLevelArea.load_item()` — para N2:
- Buscar bbox do item no DXF de eng. reversa via ezdxf (texto/layer com ID do item)
- Passar bbox para `DXFVectorView.load_dxf(path, bbox)` → zoom centrado automaticamente

---

### CE-005: Sincronização global Obra/Pavimento — Comparison Engine
**Prioridade:** P2  
**Arquivo:** `main.py` + `src/ui/modules/comparison_engine.py`  
**Critério de aceite:**
- ComboBoxes de Obra e Pavimento do Comparison Engine sincronizam com top bar global
- Mudar obra no top bar → Comparison Engine atualiza automaticamente
- Mudar obra no Comparison Engine → top bar atualiza

**Implementação:**
Em `main.py`, após criar `self.comparison_module`:
```python
# Conectar combo global → CE
self.cmb_global_obra.currentTextChanged.connect(
    self.comparison_module.fase8_panel.set_obra_external
)
self.comparison_module.fase8_panel.cmb_obra.currentTextChanged.connect(
    self._on_any_obra_changed  # atualiza top bar + outros módulos
)
```

---

### CE-006: Structural Analyzer — Auto-load DXF ao selecionar obra
**Prioridade:** P2  
**Arquivo:** `main.py`  
**Critério de aceite:**
- Ao selecionar obra no ComboBox do Structural Analyzer, DXF principal é carregado automaticamente no viewer
- Ao selecionar pavimento, carrega o DXF do pavimento correspondente
- Carrega também os estados salvos de análise (pilares/vigas/lajes já extraídos)

**Implementação:**
Em `_on_obra_combo_changed` (Structural Analyzer):
```python
projects = [p for p in self.db.get_projects() if p.get('work_name') == obra]
if projects:
    first = projects[0]
    if first.get('dxf_path') and os.path.exists(first['dxf_path']):
        self._load_dxf(first['dxf_path'])
        self._refresh_lists()
```

---

### PM-001: project_manager — Remover duplicatas
**Prioridade:** P0  
**Arquivo:** `src/ui/widgets/project_manager.py`  
**Ação:**
- Deletar L1453–1458 (stub `load_projects` com `pass`)
- Deletar L2549–2552 (`_convert_to_specific_version` corrompido)
- Deletar L3248–3263 (`create_new_project` simples — versão L2997 é a correta)

---

### PM-002: Fase 1 — Auto-indexação de arquivos do filesystem
**Prioridade:** P1  
**Arquivo:** `src/ui/widgets/project_manager.py` + `src/utils/auto_indexer.py`  
**Diagnóstico:** Arquivos físicos existem em `DADOS-OBRAS/{obra}/Fase-1_Ingestao/` mas não estão no DB. `auto_indexer.py` existe mas nunca é chamado pela UI.

**Critério de aceite:**
- Fase 1 lista arquivos do filesystem mesmo sem estarem no DB (badge "Não indexado")
- Botão "Indexar Tudo" registra todos no DB via `auto_indexer.scan_and_index(work_name)`
- Ao carregar obra, auto-scan silencioso (sem bloquear UI) via QThread

**Implementação:**
Em `_refresh_phase_tabs` para `phase_num == 1`:
```python
# Além dos docs do DB, escanear filesystem diretamente
fs_files = self._scan_phase1_filesystem(work_name)
for f in fs_files:
    if not any(d.get('file_path') == str(f) for d in docs):
        docs.append({'id': None, 'name': f.name, 'file_path': str(f),
                     'extension': f.suffix, '_not_indexed': True})
```

---

### PM-003: Fases 6 e 7 — Seletor de pavimento
**Prioridade:** P1  
**Arquivo:** `src/ui/widgets/project_manager.py`  
**Critério de aceite:** Fases 6 e 7 têm ComboBox de pavimento idêntico ao das fases 3, 4, 5.

**Implementação:**
```python
# Em _create_phase_tab:
if phase_num in [4, 5, 6, 7]:
    self.setup_pavement_selector_combo(layout, phase_num=phase_num)

# Em setup_pavement_selector_combo — adicionar ao phase_map:
6: 'CONVERSÃO DXF GRANULAR',
7: 'UNIFICAÇÃO DXF PAVIMENTO',

# No bloco elif no final do método:
elif phase_num == 6:
    self.cmb_pavements_dxf_gen = cmb
elif phase_num == 7:
    self.cmb_pavements_dxf_merge = cmb

# Em load_projects — adicionar combos:
'cmb_pavements_dxf_gen', 'cmb_pavements_dxf_merge'
```

---

### PM-004: Fase 6 — Listagem granular de itens DXF por pavimento
**Prioridade:** P1  
**Arquivo:** `src/ui/widgets/project_manager.py`  
**Descrição:** Após selecionar pavimento, listar itens geráveis (de Fase 4) com botões "Gerar DXF" e "Abrir no CAD".  
**Classes:** DXF Pilares, DXF Vigas Laterais, DXF Vigas Fundo, DXF Lajes  
**Fonte de dados:** JSONs da Fase 4 (`Fase-4_Sincronizacao/`)  
**Geração:** subprocess `gerar_{tipo}_dxf_stog.py --pavimento {pav} --item {id}`

---

### PM-005: Fase 7 — Consolidação DXF por pavimento
**Prioridade:** P1  
**Descrição:** Lista classes com status de consolidação. Botão "Gerar Consolidado" unifica DXFs granulares da Fase 6.

---

### PM-006: Fase 2 — Classe 3: Eng. Reversa por Pavimento (classificação)
**Prioridade:** P2  
**Arquivo:** `src/ui/widgets/project_manager.py` + `src/core/storage/project_storage.py`  
**Descrição:** Grid de cards de DXFs de eng. reversa por obra/pavimento com campos de classificação (PIL/VIG/LAJ/FV) e status visual.

**Fonte de dados:** `DADOS-OBRAS/{obra}/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa/`

```python
PHASE_CLASSES[2] = [
    "Estruturais Pavimentos Limpos",
    "Detalhamentos Específicos",
    "Projetos Finalizados para Engenharia Reversa"  # NOVA
]
```

---

### PM-007: Fase 8 — Dashboard de Revisão e Entrega
**Prioridade:** P2  
**Descrição:** Grid por pavimento com score de completude, status do DXF final, botão "Exportar Pacote".

---

### PM-008: Janela "Dados" — DataPipelineView na navegação principal
**Prioridade:** P2  
**Arquivo:** `main.py`  
**Diagnóstico:** Estava em `AdminDashboard` (admin only). Gate removido nesta sessão — agora aparece em CURADORIA. Avaliar se merece aba própria no `module_tabs`.

---

### PM-009: Sincronização global Obra/Pavimento — todos os módulos
**Prioridade:** P2  
**Arquivo:** `main.py`  
**Critério de aceite:** Top bar ComboBoxes → propagam para Gerenciar Projetos, Structural Analyzer, Comparison Engine e todos os Robôs bidirecionalmente.

---

## ORDEM DE EXECUÇÃO RECOMENDADA

```
Sprint 1 — Correções e base (P0/P1 rápidos):
  PM-001 (duplicatas)
  PM-003 (seletor fases 6/7)
  CE-001 (layout CE)
  CE-003 (renomear botões)

Sprint 2 — Dados e Engine:
  PM-002 (auto-indexação fase 1)
  CE-002 (botões Análise Geral + Fase 4)
  CE-006 (auto-load DXF structural analyzer)

Sprint 3 — N2 e Eng. Reversa:
  CE-004 (motor N2 dinâmico)
  PM-006 (fase 2 classe 3 eng. reversa)

Sprint 4 — Sync + Fases 6/7/8:
  CE-005 (sync global CE)
  PM-009 (sync global todos)
  PM-004 (fase 6 listagem)
  PM-005 (fase 7 consolidação)
  PM-007 (fase 8 dashboard)
  PM-008 (dados pipeline)
```

---

## ARQUITETURA PIPELINE END-TO-END

```
Gerenciar Projetos (fases) ←→ Módulos do module_stack
                               ↕ sync via signals (obra/pav)
Top Bar ComboBoxes ────────→ todos os módulos

DADOS-OBRAS/{obra}/
  Fase-1_Ingestao/
    Estruturais_dos_Pavimentos.../   ← DWG/DXF brutos (PM-002 indexa)
    Projetos_Finalizados_para_Eng_Reversa/  ← input CE-004 N2
  Fase-2_Triagem/                   ← PM-006 classifica aqui
  Fase-3_Interpretacao/             ← CE-002 btn Análise Geral
  Fase-4_Sincronizacao/             ← CE-002 btn Fase4, PM-004 fonte
  Fase-5_Geracao_Scripts/
  Fase-6_Execucao_CAD/              ← PM-004 gera aqui
  Fase-7_Consolidacao/              ← PM-005
  Fase-8_Revisao_Entrega/           ← PM-007

module_stack (main.py):
  [0] Diagnostic Hub
  [1] Structural Analyzer  ← CE-006 auto-load
  [2] Comparison Engine    ← CE-001..005
  [3] Robo Pilares
  [4] Robo LV
  [5] Robo FV
  [6] Robo Lajes
  [7] DataPipelineView    ← PM-008 (a adicionar)
```

---

## ARQUIVOS CHAVE

| Arquivo | Linhas | Responsabilidade |
|---------|--------|-----------------|
| `src/ui/modules/comparison_engine.py` | 2432 | Motor 3-níveis N1/N2/N3 |
| `src/ui/widgets/project_manager.py` | 3375 | Gerenciar Projetos fases 1–8 |
| `src/core/storage/project_storage.py` | ~100 | PHASE_CLASSES, estrutura de pastas |
| `src/core/database.py` | — | get/save documents |
| `src/utils/auto_indexer.py` | — | Scanner filesystem → DB |
| `src/ui/widgets/data_pipeline.py` | — | DataPipelineView |
| `main.py` | ~7500 | module_stack, sync global, top bar |
| `scripts/gerar_*_dxf_stog.py` | — | Geradores DXF por tipo |
| `scripts/motor_fase4.py` | — | Sync Fase 4 |
