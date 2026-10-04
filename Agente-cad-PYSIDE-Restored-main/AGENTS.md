# AGENTS.md — Codex / Antigravity / qualquer agente que não leia CLAUDE.md

> # ⭐ FONTE ÚNICA DE VERDADE DO PROJETO: **`CLAUDE.md`** (neste mesmo diretório).
> **LEIA O `CLAUDE.md` INTEGRALMENTE ANTES DE QUALQUER AÇÃO.** Este arquivo apenas
> resume os invariantes para o caso de você não seguir referências; em qualquer
> conflito, o `CLAUDE.md` vence. Regras comportamentais adicionais que valem para
> TODOS os agentes (proibição de restore de backup, proibição de simulação falsa):
> `.agents/AGENTS.md`.

## Invariantes inegociáveis (resumo — detalhes no CLAUDE.md)

1. **Python 3.12 OBRIGATÓRIO**: `C:\Users\Thierry\AppData\Local\Programs\Python\Python312\python.exe`
   (3.13/3.14 crasham QThread e quebram ChromaDB).
2. **DB real** = `D:/Agente-cad-PYSIDE/project_data.vision` (o de dentro do repo é stale).
   NUNCA deletar/sobrescrever DXFs de obras nem JSONs Fase-4.
3. **Status real** = relatório mais recente em `scripts/arete/relatorios/` + golden.
   `docs/STATUS.md`/`gerar_status.py` estão desconectados do fluxo atual; não usar como verdade.
4. **Loop de qualidade**: usar SOMENTE o canônico — `docs/LOOPING-CANONICO.md` seção 1.
   Headless de fichas é UM só: `scripts/arete/headless_sa_analise.py` sempre com
   `--wait`. Rodadas read-only de uma `--secao` (com ou sem `--item`), inclusive
   persistência parcial quando usa `--secao + --item`, têm filas isoladas por classe;
   PIL/FV/LV reservam também o snapshot compartilhado de `beams`, e só o commit SQLite
   é serializado. Rodada completa ou multiclasse espera todas as classes.
   **NUNCA finalize o processo detentor.** Scripts fora dessa lista = legado em quarentena.
   **Vision dual-mode** (`docs/QA-VISAO-EVIDENCIA-CANONICA.md`): agente julga em **PNG**;
   HTML com `--persist-db` / app / **portal web** → **SVG**; headless sem persist = imagem
   dinâmica (sem SVG obrigatório).
   **SVG pan/zoom web:** somente **viewBox** (padrão FV V302) — proibido CSS scale.
   Ver `docs/PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md` + `fv_hifi_n1_render.initPanZoom` /
   `pil_qa_notes_chrome.initPilPanZoom`. Todo CLI de ficha HTML N1 herda isso.
   **Tags PIL:** aplicar integralmente `docs/PADRAO-TAGS-DESTAQUE-AGENTICO-PIL.md`;
   chega no centro da viga, passa no vértice exato e todos os gates (geometria,
   semântica, vínculo, conteúdo, ponto, legibilidade e PNG) têm o mesmo peso.
   Sidecar PASS isolado não aprova.
5. **Motor universal (Regra de Ouro)**: zero hardcode por item/pavimento/obra — fix é
   fórmula geral a partir da ficha. Golden set: PROIBIDO selar com gate FAIL;
   regressão Arete obrigatória após qualquer toque em `gerar_*`/`motor_*`.
6. **Coordenação**: não editar geradores/motores sem causa provada por gate G1/G2;
   não editar arquivos de UI compartilhados (`pre_validation_dialog.py`,
   `diagnostic_reverse_hub.py`) sem confirmar que nenhuma outra sessão está neles.
7. **Git**: sem push para main; commits na branch de sessão.
8. **Missões ativas e leituras obrigatórias**: seção "MISSÃO ATUAL" do `CLAUDE.md`
   (masterplans `MASTERPLAN-ARETE-QUALITY-GATES.md` e `MASTERPLAN-PRODUCAO-SOBERANIA.md`).
9. **Conhecimento**: entrada = `docs/CONHECIMENTO/MAPA-DO-CONHECIMENTO.md`; busca =
   `python scripts/kb/kb_query.py "pergunta"`; decisões do dono = `DECISOES-DO-DONO.md`.
   Conhecimento novo vai para o doc canônico do tema (seção "Conhecimento" do `CLAUDE.md`).
