# MASTERPLAN — Arquitetura de Fichas F1–F9, Harmonização & Acoplamento Semântico

**Versão:** 2.0
**Data:** 2026-06-20
**Orquestração:** Athena (CEO-Planejamento)
**Origem:** Sessão Gemini `6a039944-751a-43c5-a540-19fdbdb91c05` (fundos de viga + sistema de fichas + botão "Analisar com Eng Reversa") + decisões diretas do dono da obra (2026-06-20).
**Status:** PLANEJAMENTO — taxonomia e fonte semântica TRAVADAS. Execução será feita por modelo menor, por squad, conforme §9.

> **Decisões travadas nesta versão (peso máximo — mais recentes):**
> 1. Taxonomia **F1–F9** confirmada pelo dono (corrige F6/F7/F8 da v1.0 → ver §1).
> 2. **`domain_knowledge`** (LanceDB, 217 chunks, nv-embed-v1 4096-dim) = **fonte de verdade semântica** das fichas.
> 3. Escopo agora = **documentar + harmonizar + ajustes seguros**; sem migração de DB destrutiva.

---

## 0. TL;DR

O pipeline produz **9 fichas** rastreáveis (F1–F9), cada uma ligada a um **nível de dado N1–N4** e a um **`semantic_ref`** no `domain_knowledge`. Hoje elas existem de forma parcial e desalinhada. Esta v2.0 fixa a **nomenclatura canônica**, define a **fonte semântica única**, e separa o que é **ajuste seguro agora** do que entra no **MASTERPLAN do loop de treino** (`MASTERPLAN-LOOP-TREINO-MOTOR.md`).

---

## 0.1 SEQUENCIAMENTO MACRO — 2 Etapas (decisão do dono 2026-06-20)

> A ordem de execução é inequívoca: **fichas & botões primeiro, loops depois.**

```
ETAPA 1 — FICHAS & BOTÕES (fundação / "chão")     ← ESTE masterplan (Fases 1-5 + R1-R7)
  Fazer FUNCIONAR, independente da qualidade do conteúdo:
   • Taxonomia F1-F9 + IDs rastreáveis
   • Schema único de item (F5≡F7≡N1) do campos_json real
   • Os 3 botões com lógica certa (Geral gera F7 · Eng Reversa consulta F5 · Contexto=futuro)
   • Preenchimento dinâmico + persistência segura
   • Ajustes UI seguros (R1-R7)
        │
        ▼  (ponto de transição = S0 do loop: ligar autovalidate_v3 ao botão Eng Reversa)
ETAPA 2 — LOOPS POR CLASSE (refino / qualidade)   ← MASTERPLAN-LOOP-TREINO-MOTOR.md
  Fazer o conteúdo ficar BOM (motor converge ao N2), classe a classe.
```

**Razão:** o botão "Análise Geral" já roda e escreve a ficha **mesmo com interpretação ruim** (Etapa 1). O loop (Etapa 2) usa o N2 como professor para essa interpretação ficar boa. Fichas/botões são o **chão onde o loop pisa** — por isso vêm primeiro.

---

## 1. Modelo Canônico de Fichas (F1–F9) — TRAVADO

> **Regra de ID:** toda ficha carrega ID determinístico e hierárquico. Nenhuma ficha é gerada sem ID + `semantic_ref`.

| Ficha | Nome | Onde nasce (aba/botão) | Nível N | ID canônico | Granularidade | Status |
|-------|------|------------------------|---------|-------------|---------------|--------|
| **F1** | Pré-Obra | Gerenciar Projetos · aba 3 (Fase 1: ingestão + indexação + triagem) | — | `F1-{OBRA}` | Obra (metadados, contagem/classe, classificação triagem) | Parcial |
| **F2** | Pré-Pavimento / Detalhes | Diagnostic Hub Pré · "Iniciar Pré-Análise do Pavimento" | — | `F2-{OBRA}-{PAV}` | Pavimento (compreensão inicial) | Parcial |
| **F3** | Ficha-Obra Global | Diagnostic Hub Pré · "Analisar Todas Fichas / Gerar Ficha da Obra" | — | `F3-{OBRA}` | Obra granular (PIL/LAJ/VL/VF por pavimento) | **EM DESENVOLVIMENTO** — extração granular ainda fraca; insumo da "Análise com Contexto" (futuro) |
| **F4** | Eng. Reversa Pavimento×Classe | Diagnostic Reverse Hub · "Gerar Fichas Obra/Pavimentos/Granulares" | N4 | `F4-{OBRA}-{PAV}-{CLASSE}` | Pavimento×Classe (4/pavimento: PIL, VF, VL, LAJ) — consolida F5 | Quebrado — não popula dinâmico |
| **F5** | Granular do Item (Eng. Reversa) | Diagnostic Reverse Hub · extração dos recortes N2 | N2 | `F5-{OBRA}-{PAV}-{CLASSE}-{ITEM}` | Item (dims, coords, área, vínculos) — **é o item do N2** | Quebrado — não carrega ao selecionar recorte |
| **F6** | Obra Eng. Reversa | Diagnostic Reverse Hub · consolidação da obra | N2 consolidado | `F6-{OBRA}` | Obra (consolida F4 de todos pavimentos) | A implementar (fix `consolidar_obra_er`) |
| **F7** | Ficha Structural Analyzer | Structural Analyzer · Análise Geral / c/ Contexto / c/ Eng Reversa | **N1** | `F7-{OBRA}-{PAV}-{CLASSE}-{ITEM}` | Item — **popula o N1 do Comparison Engine**; mesma profundidade da F5 | A harmonizar |
| **F8** | Ficha N3 (Comparison) | Comparison Engine · N3 (Robô a partir de N1) | **N3** | `F8-{OBRA}-{PAV}` | DXF/Robô gerado do bruto | A formalizar como ficha |
| **F9** | Ficha N4 (Comparison) | Comparison Engine · N4 (Robô granular a partir de F5/N2) | **N4** | `F9-{OBRA}-{PAV}-{CLASSE}` | DXF/Robô gerado do gabarito | A formalizar como ficha |

### 1.1 Correções da v1.0 → v2.0 (decisão do dono)
- **F6** = obra Eng. Reversa (não é mais ambígua).
- **F7** = ficha do Structural Analyzer = **N1 do Comparison** (era "conversão N3" na v1.0).
- **F8** = ficha **N3** do Comparison (era "conversão N4").
- **F9** = ficha **N4** do Comparison (nova).
- **GAP #1 da v1.0 → RESOLVIDO.**

### 1.2 Schema único de item (F5 ≡ F7 ≡ N1)
F5 (granular eng. reversa) e F7 (granular structural) **compartilham o mesmo schema de campos** — derivado do **Comparison Engine (N1)**, o módulo mais maduro em extração. O `VECTOR_SCHEMA.md` v1.0.0 é reconciliado *por baixo* deste schema (ver §6, sem migração destrutiva).

### 1.3 Mapeamento para o BANCO REAL (auditoria 2026-06-20) — NÃO RECRIAR

> ⚠️ **As fichas JÁ EXISTEM no banco.** Harmonizar = popular/indexar/conectar o que está aqui. **Proibido criar tabela nova que duplique estas.** Banco: `D:/Agente-cad-PYSIDE/project_data.vision` (1.35 GB).

| Ficha | Tabela real | Rows | Observação crítica |
|-------|-------------|------|--------------------|
| **F5** | `reverse_eng_fichas` | **902** (FV 271, LAJ 177, LV 229, PIL 225) | `campos_json` já rico; **`rag_indexed=0` em 100%** → acoplamento semântico PENDENTE; status: 765 draft + 137 extracted |
| **F6** | `reverse_eng_obra_ficha` | 2 | consolida totais por classe + `confianca_media`; `rag_indexed` |
| **F7** | `fase3_fichas` | 405 (laje 80, pilar 162, viga 160, garfo 3) | **0 revisados**; possui `dna_vector` |
| N2 recortes | `reverse_eng_recortes` | 775 | bbox + entity_count por elemento |
| Elementos validados | `pillars` 7216 · `beams` 7356 · `slabs` 4709 | — | `validated_fields_json`/`na_fields_json` = **estado de persistência** (FASE 4) |
| Cache de ficha | `cache_fichas` | 0 | vazio — `entidade_hash` + `ficha_json` (anti-regeneração) |

**Schema de item já existente** (`reverse_eng_fichas.campos_json`, ex. FV): `number, name, floor, total_width, total_height, panels, segments_rich, holes, pillar_left/right, label_left/right, sarrafo_left/right_id, _n_linhas_folha, _er_meta, _fase4_ref`. → A FASE 1 (schema canônico) **parte deste JSON real**, não do zero.

**Semântica:** `domain_knowledge` (217 chunks; `field_semantics`=66) é a fonte. A tabela `semantic_rag_kb` (SQLite, **0 rows**, cols `classe/regra_semantica/obra_contexto/confianca`) é o **bridge vazio** a popular — é onde o `semantic_ref` por-classe deve materializar, espelhando o `domain_knowledge`.

---

## 2. Camada Semântica — `domain_knowledge` como fonte de verdade

**QUATRO** stores coexistem no CAD (auditoria 2026-06-20); cada um com papel **fixo**:

| Store | Papel TRAVADO | Real | Estado |
|-------|---------------|------|--------|
| **`domain_knowledge`** (LanceDB) | **Fonte das REGRAS/significado** — `grade_1`, `h3`, fórmulas. Origem do `semantic_ref`. | `DADOS-OBRAS/stog_rag_db` | **217 chunks**, 9 doc_types (`field_semantics`=66) ✅ |
| **`stog_kbs`** (LanceDB) | **Ground truth de inventário** por-DXF. | mesma instância | **2179 rows** (header/inventory/semantics/nomenclaturas) ✅ |
| **Chroma** (`vector_memory/`) | **Aprendizado adaptativo** + elementos + amostras de treino. | `Restored-main/vector_memory/chroma.sqlite3` | **2282 embeddings** — collections `adaptive_learning`, `structural_elements`, `training_samples` ✅ |
| **`semantic_rag_kb`** (SQLite) | **Bridge por-classe** — `regra_semantica` por classe/obra (espelho operacional do domain_knowledge). | `project_data.vision` | **0 rows** ⚠️ vazio — a popular |
| RAG por-obra (`obra_rag_pipeline.py`) | KB por obra — alvo do "Analisar com Eng Reversa". | scripts | EPIC 1 (P0 pendente) |

**Acoplamento (ação real):** (1) rodar a indexação das 902 fichas (`reverse_eng_fichas.rag_indexed 0→1`); (2) preencher `semantic_rag_kb` a partir do `domain_knowledge`; (3) cada campo de ficha ganha `semantic_ref` = id do chunk. Consulta: `python scripts/domain_knowledge_ingestor.py --query "..."`. **Nenhum store é recriado** — só populado/conectado.

---

## 3. Fluxo Dual + Fichas + Camada Semântica

```
PRÉ (bruto / motor dinâmico):
 F1 Pré-Obra → F2 Pré-Pav → F3 Obra-Global → [Structural Analyzer]
                                              └► F7 (N1) ──► F8 (N3, Robô)

REVERSO (STOG humano = GABARITO):
 Recortes N2 → F5 (N2, item) → F4 (pav×classe) → F6 (obra-reversa)
                                              └► F9 (N4, Robô granular)

COMPARISON ENGINE:  N1(F7) vs N2(F5) → score cruzado → loop de treino do motor

SEMÂNTICA (transversal): cada campo de F1..F9 → semantic_ref → domain_knowledge
```

**Princípio operacional:** "Analisar com Eng Reversa" = **consulta** (gabarito N2), não gera DXF. "Análise Geral" reproduz **dinamicamente sem `teacher_coords` direto**. A diferença = sinal de treino (detalhado em `MASTERPLAN-LOOP-TREINO-MOTOR.md`).

---

## 3.5 Os 3 Botões do Structural Analyzer (intenção — decisão do dono 2026-06-20)

| Botão | O que é | Usa | Estado / Prioridade |
|-------|---------|-----|---------------------|
| **Iniciar Análise Geral** | Motor dinâmico puro, do zero, **sem teacher**. Baseline que deve aprender a interpretar sozinho. | regras aprendidas (`transformation_rules`) + Chroma | **FOCO ATUAL** — é o que o loop de treino refina até atingir o nível do N2 |
| **Análise com Eng Reversa** | **Consulta** o N2/gabarito (não gera DXF). Serve de gold para treinar e comparar. | `reverse_eng_fichas` (F5/N2) | **EM IMPLEMENTAÇÃO** — alvo deste alinhamento; é o chão do loop |
| **Análise com Contexto** | **Refinamento FINAL** (objetivo de longo prazo). Usa **F1/F2/F3** para compreender **reaproveitamento de grades e painéis entre pavimentos** e comportamentos de itens ao longo da obra. | F1/F2/F3 + memória global | **FUTURO** — só deixar preparado e documentado. Hoje não há extração/explicação suficiente nem loop de auto-healing para essa distinção. NÃO implementar agora. |

> **Ordem estratégica (dono):** primeiro **Eng. Reversa + loop de treino** elevam a **Análise Geral** até Arete → isso vira a **base/chão** para, no futuro, construir a **Análise com Contexto** (reaproveitamento entre pavimentos). O nível atual das fichas ainda não sustenta o "Contexto"; ele será otimizado depois com um loop de auto-healing de compreensão.

## 3.6 Produto Final (modos de operação)

Quando a interpretação atingir **Arete** (qualidade + confiança), a app opera em **dois modos**:
1. **Human-in-the-loop** — operador valida/corrige cada classe antes de gerar (modo atual e sempre disponível).
2. **End-to-end (zero-touch)** — DXF bruto entra, DXF STOG final sai, sem intervenção — **liberado apenas quando a confiança da classe/obra justificar**.

**Status da geração:** robôs SCR são bons; o **DXF final (N4)** ainda está em refino — resultados parcialmente bons. Mais obras refinam o motor e o N4. A interpretação atingir Arete é **pré-condição** do modo end-to-end.

---

## 4. Estado Atual (resumo)

**Funciona:** geradores STOG certificados (20 obras); Comparison Engine maduro em extração; triagem classifica pavimentos; botão Eng Reversa já faz relatório N2 + confirmação; popup de auditoria ampliado (1100×700).

**Quebrado:** F3/F4/F5 não populam dinâmico (passo 4147); motor Structural ruim → F7 quase vazia; estado de fundos não persiste (3186); ComboBox Structural sem classificação por pavimento (4328); Diagnostic Hub Pré mostra tudo como "Outros" (3601); F6 sem `consolidar_obra_er` (4231).

---

## 5. Harmonização Desejada (alvo)
1. Nomenclatura única F1–F9 + IDs em 100% das fichas (§1 = fonte da verdade).
2. Schema único de item F5≡F7≡N1 (Comparison Engine).
3. `semantic_ref` → `domain_knowledge` em todo campo.
4. Preenchimento dinâmico ao selecionar recorte/documento.
5. Persistência segura (validado nunca sobreposto).
6. Design System coerente em todas as abas de ficha.

---

## 6. AJUSTES SEGUROS (execução prévia — sem risco de DB/aprendizagem)

Mudanças de UI/rotulagem/leitura. PRs pequenos, reversíveis, **sem migração**:

- **R1** — Rótulos de abas/botões com nomenclatura F1–F9 + ID visível.
- **R2** — ComboBox Structural: listar por pavimento/classe da triagem (igual Hub Pré/Reverse) — passo 4328.
- **R3** — Diagnostic Hub Pré: exibir classe real da triagem (não "Outros") — passo 3601.
- **R4** — Relatório Eng. Reversa: janela em colunas (feito) listando todas as fichas com ID.
- **R5** — Harmonizar Design System das abas de ficha — passo 3838.
- **R6** — 3ª aba de fichas no Diagnostic Reverse Hub (Obra/Pavimentos/Granulares) + renomear botão.
- **R7** — Reconciliar `VECTOR_SCHEMA.md` v1.0.0 sob o schema do Comparison (apenas doc + mapeamento, sem migrar dados).

---

## 7. PROTOCOLO do Analista — Harmonização & Acoplamento Semântico

**FASE 0 — Decisões.** TRAVADAS (taxonomia F1–F9 + domain_knowledge). *DoD:* §1 sem ⚠️ ✅.
**FASE 1 — Schema canônico.** Extrair do Comparison Engine os campos por classe → `docs/SCHEMA-FICHA-GRANULAR.md`. Aplicar a F5/F7. *DoD:* schema único versionado.
**FASE 2 — IDs rastreáveis.** Gerador determinístico (§1) em todo ponto de criação. *DoD:* busca por ID retorna ficha.
**FASE 3 — Preenchimento dinâmico.** Seleção de recorte/documento → carrega F4/F5 e F2/F3. *DoD:* passo 4147 resolvido.
**FASE 4 — Persistência segura.** "validado nunca sobreposto"; reabrir recarrega estado. *DoD:* passo 3186 resolvido.
**FASE 5 — Acoplamento semântico.** `semantic_ref` por campo → `domain_knowledge`. *DoD:* ≥90% das classes explicáveis por consulta.
**FASE 6 — Auditoria de coerência.** Obra_TREINO_1 pav 13 ponta-a-ponta (Hub/Reverse/Comparison). *DoD:* 0 divergências de ID, 0 erros (passo 3562).

---

## 8. GAPS abertos (decisão futura, não bloqueiam o loop de treino)
- F3 Obra-Global depende do motor de compreensão global (ainda inexistente) — manter placeholder versionado.
- F8/F9 como ficha persistida vs só artefato DXF — formalizar na FASE 1.

---

## 9. Divisão por Squad (para execução em modelo menor)

| Bloco | Squad responsável | Entregável |
|-------|-------------------|-----------|
| Schema canônico + reconciliação VECTOR_SCHEMA | `Dados:STOGIntelligence-AIOS` | `SCHEMA-FICHA-GRANULAR.md` |
| Acoplamento semântico (`semantic_ref` + queries) | `Dados:RagForge-AIOS` | mapeamento campo→chunk |
| Preenchimento dinâmico + persistência (UI) | `CAD:CadVisualInterpreter-AIOS` / `Desenvolvimento:Dev-AIOS` | F3/F4/F5 dinâmicos |
| Loop de treino do motor | ver `MASTERPLAN-LOOP-TREINO-MOTOR.md` | motor convergente |
| Orquestração/governança | `Dados:CeoData-AIOS` + `CEOs:CEO-CAD-ANALYZER` | quality gates |

---

## 10. Referências
- Sessão Gemini: `…\6a039944-…\.system_generated\logs\transcript.jsonl`
- `docs/MASTERPLAN-LOOP-TREINO-MOTOR.md` (loop de treino — companion deste)
- `docs/MASTERPLAN-ENGENHARIA-REVERSA.md` (dual-flow N1–N4)
- `docs/VECTOR_SCHEMA.md`, `docs/SEMANTICA-{PILAR,VIGA,LAJE}-NOVA.md`
- `scripts/domain_knowledge_ingestor.py`, `scripts/obra_rag_pipeline.py`
