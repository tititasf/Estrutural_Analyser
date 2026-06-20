# PROMPT — ETAPA 1 (Fichas & Botões) para Codex executar

> Copie tudo abaixo da linha para um chat novo do Codex.

---

## MISSÃO
Você vai implementar a **ETAPA 1 — Fichas & Botões (fundação)** do app CAD PySide. O objetivo desta etapa é fazer o **sistema de fichas F1–F9 e os 3 botões FUNCIONAREM** (plumbing: IDs rastreáveis, preenchimento dinâmico, persistência, lógica clara dos botões) — **independente da qualidade da interpretação**. A qualidade vem numa ETAPA 2 (loops de treino) que NÃO é seu escopo agora.

## ANTES DE TOCAR EM QUALQUER CÓDIGO — LEIA ESTES DOCS (fonte da verdade)
Na pasta `D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\docs\`:
1. `MASTERPLAN-FICHAS-F1-F9-HARMONIZACAO.md` ← **principal desta etapa** (taxonomia, §0.1 ordem macro, §1.3 mapeamento DB real, §3.5 os 3 botões, §6 ajustes seguros R1-R7, §7 protocolo)
2. `MASTERPLAN-LOOP-TREINO-MOTOR.md` (contexto da Etapa 2 — só para entender o destino, NÃO implementar)
3. `QUALITY-GATE-MASTERPLANS-FICHAS-LOOP.md` (gaps a fechar)
4. Apoio: `STATUS-ATUAL-JUNHO-2026.md`, `VECTOR_SCHEMA.md`, `SEMANTICA-PILAR-NOVA.md`, `SEMANTICA-VIGA-NOVA.md`, `SEMANTICA-LAJE-NOVA.md`, `REVERSE_ENGINEERING.md`

## REPOSITÓRIO E PASTAS
- Raiz do projeto: `D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main`
- App principal (PySide6/Qt6): `main.py` (~8.700 linhas)
- Banco SQLite REAL: `D:\Agente-cad-PYSIDE\project_data.vision` (1.35 GB) — **NÃO** use `data/*.db` (vazios)
- Vetores: LanceDB `D:\Agente-cad-PYSIDE\DADOS-OBRAS\stog_rag_db` (`domain_knowledge`, `stog_kbs`) + Chroma `vector_memory/chroma.sqlite3`
- Gabarito N2 por pavimento: `projects_repo/<project_id>/laje_data/obras.json`

## ARQUIVOS-CHAVE (use grep para localizar funções; linhas podem ter mudado)
- `main.py`:
  - `process_pillars_action()` → botão **Iniciar Análise Geral** (gera N1/F7)
  - `_process_with_reverse_engineering()` → botão **Analisar com Eng Reversa** (consulta N2/F5)
- `src/ui/modules/diagnostic_hub.py` → Diagnostic Hub Pré (F2/F3)
- `src/ui/modules/diagnostic_reverse_hub.py` → Diagnostic Reverse Hub (F4/F5/F6); função `_on_gerar_ficha`
- `src/ui/widgets/project_manager.py` → Gerenciar Projetos, aba 3 (F1)
- `src/core/slab_tracer.py` → motor (NÃO alterar lógica de interpretação nesta etapa)
- `scripts/motor_reverso_obra.py` → consolidação obra-reversa (F6) — corrigir export ausente `consolidar_obra_er`

## TAXONOMIA DE FICHAS F1–F9 (TRAVADA — não renumerar)
| Ficha | O que é | Tabela REAL no `project_data.vision` | ID |
|-------|---------|--------------------------------------|----|
| F1 | Pré-Obra (Gerenciar Projetos, aba 3) | — | `F1-{OBRA}` |
| F2 | Pré-Pavimento (Diagnostic Hub Pré) | — | `F2-{OBRA}-{PAV}` |
| F3 | Ficha-Obra Global (Hub Pré) — EM DESENVOLVIMENTO | — | `F3-{OBRA}` |
| F4 | Eng. Reversa Pavimento×Classe (Reverse Hub) | (deriva de reverse_eng_fichas) | `F4-{OBRA}-{PAV}-{CLASSE}` |
| F5 | Granular do item (Reverse Hub, N2) | **`reverse_eng_fichas`** (902 rows; FV271/LAJ177/LV229/PIL225) | `F5-{OBRA}-{PAV}-{CLASSE}-{ITEM}` |
| F6 | Obra Eng. Reversa (Reverse Hub) | **`reverse_eng_obra_ficha`** (2) | `F6-{OBRA}` |
| F7 | Ficha Structural Analyzer = N1 Comparison | **`fase3_fichas`** (405) | `F7-{OBRA}-{PAV}-{CLASSE}-{ITEM}` |
| F8 | Ficha N3 Comparison (Robô de N1) | (Comparison Engine) | `F8-{OBRA}-{PAV}` |
| F9 | Ficha N4 Comparison (Robô de N2) | (Comparison Engine) | `F9-{OBRA}-{PAV}-{CLASSE}` |

Outras tabelas relevantes: `reverse_eng_recortes` (775, N2), `pillars`/`beams`/`slabs` (com `validated_fields_json`/`na_fields_json` = estado de persistência), `transformation_rules` (23, motor dinâmico — NÃO alterar), `training_events` (901), `cache_fichas` (0), `semantic_rag_kb` (0, bridge vazio), `obra_triagem` (129, classificação por pavimento).

Schema de item já existente em `reverse_eng_fichas.campos_json` (ex. FV): `number, name, floor, total_width, total_height, panels, segments_rich, holes, pillar_left/right, label_left/right, sarrafo_left/right_id, _er_meta, _fase4_ref`. **Use este JSON real como base do schema canônico — não invente do zero.**

## OS 3 BOTÕES (lógica a implementar/clarificar)
1. **Iniciar Análise Geral** — motor dinâmico puro, sem teacher. Gera a ficha **F7/N1** (grava em `fase3_fichas`) e popula o N1 do Comparison Engine. Pode produzir conteúdo ruim — tudo bem nesta etapa.
2. **Analisar com Eng Reversa** — **CONSULTA** as fichas N2/F5 (`reverse_eng_fichas`), **não gera DXF**. Fluxo: (Etapa 1) busca fichas N2 do projeto/pavimento → relatório de granularidade (quantos PIL/VF/VL/LAJ, com dims/coords) → confirmação do usuário → segue. (já parcialmente implementado; corrigir bugs)
3. **Análise com Contexto** — **FUTURO**. Apenas deixar o botão/aba presente e documentar a intenção (refino final usando F1/F2/F3 para compreender reaproveitamento de grades/painéis entre pavimentos). **NÃO implementar lógica** — hoje não há extração suficiente.

## TAREFAS DA ETAPA 1 (com critério de aceite)
**T1 — IDs rastreáveis (F1–F9).** Gerar e persistir ID determinístico (padrão da tabela acima) em todo ponto de criação de ficha. *Aceite:* toda ficha gravada tem ID; buscar por ID retorna a ficha.

**T2 — Schema canônico de item.** Documentar `docs/SCHEMA-FICHA-GRANULAR.md` a partir do `reverse_eng_fichas.campos_json` real (por classe PIL/VF/VL/LAJ). Aplicar o mesmo schema à F7 (`fase3_fichas`). *Aceite:* F5 e F7 compartilham os mesmos campos por classe.

**T3 — Os 3 botões com lógica/rotulagem certa.** Implementar conforme spec acima. Corrigir: `_process_with_reverse_engineering` (erro `cmb_obras`→`cmb_works`; relatório N2 deve encontrar os recortes validados do pavimento). *Aceite:* cada botão faz o descrito; rótulos claros (incluir o nº da ficha gerada).

**T4 — Preenchimento dinâmico.** Ao selecionar um recorte/documento de uma classe, carregar e exibir a ficha correspondente (F4/F5 no Reverse Hub; F2/F3 no Hub Pré por documento selecionado). *Aceite:* selecionar recorte popula a aba SEM reprocessar.

**T5 — Persistência segura.** Campos **validados nunca são sobrepostos nem apagados**; fechar e reabrir o app recarrega o estado do pavimento (usar `validated_fields_json`/`na_fields_json` em `pillars`/`beams`/`slabs`). *Aceite:* reabrir mantém os fundos/itens validados.

**T6 — Fix F6 (consolidação obra-reversa).** Corrigir export ausente `consolidar_obra_er` em `scripts/motor_reverso_obra.py`; F6 (`reverse_eng_obra_ficha`) gera/exibe sem erro. *Aceite:* botão de ficha-obra reversa funciona.

**T7 — Ajustes seguros de UI (R1–R7, sem migração de DB):**
- R2: ComboBox do Structural Analyzer lista por pavimento/classe da triagem (`obra_triagem`), como já fazem Hub Pré e Reverse Hub.
- R3: Diagnostic Hub Pré exibe a classe real da triagem (hoje mostra tudo como "Outros").
- R6: Diagnostic Reverse Hub com 3 abas de ficha (Obra / Pavimentos / Granulares) + renomear botão para "Ficha Obra, Pavimentos e Granulares".
- R1/R5: rótulos com nº de ficha (F1–F9) + harmonizar design system das abas de ficha.
- R7: reconciliar `VECTOR_SCHEMA.md` ao schema de T2 (apenas doc, sem migrar dados).
*Aceite:* itens visíveis e coerentes; nenhuma migração de banco.

## RESTRIÇÕES (NÃO-NEGOCIÁVEIS)
- **NÃO recriar** tabelas/estruturas existentes — popular/conectar o que já existe.
- **NÃO** rodar operação destrutiva de DB (sem `DROP`, sem `DELETE` em massa, sem recriar `.vision`). Faça backup do `.vision` antes de qualquer escrita estrutural.
- **ZERO hardcode** de regras de interpretação — a interpretação é da Etapa 2; aqui é só plumbing.
- **NÃO** alterar `transformation_rules` nem `slab_tracer.py` (lógica do motor).
- Trabalhe numa branch git separada se o projeto for versionado; commits pequenos por tarefa.
- Edições cirúrgicas (Edit pontual), nada de reescrever arquivos inteiros.

## ENTREGÁVEL
Etapa 1 concluída quando T1–T7 passam os critérios de aceite na obra-piloto **Obra_TREINO_1, pavimento 13** (`project_id 4869be2b-f17c-410b-a9c8-98a887ec1c95`). Ao final, escreva um relatório curto do que mudou (arquivos, funções, antes/depois) em `docs/ETAPA-1-RELATORIO.md`.

Comece **lendo os 4 docs** e fazendo um inventário (grep) das funções dos botões antes de propor o plano de execução.
