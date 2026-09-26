# Plano de harmonização do conhecimento

**Status:** canônico · **Criado:** 2026-09-25 · **Dono da execução:** quem mantiver a KB

## 1. Diagnóstico (medido em 2026-09-25)

O conhecimento da empresa não faltava — estava **espalhado em seis lugares**, dois deles
parados e sem aviso de que estavam parados:

| Onde | Estado medido |
|---|---|
| ~300 arquivos `.md` (repo, raiz do workspace, squads, skills) | vivo, mas sem mapa; 33 legados e 14 candidatos a obsoleto misturados com os vigentes |
| `semantic_rag_kb` (DB) | vivo: 117 regras, 8 T1; o QA consome |
| Programa "Cérebro RAG" de junho (masterplan + 21 stories RAG-* + 15 scripts `rag_*`) | parado; princípios bons, execução abandonada quando o Arete assumiu |
| FAISS `data/vectors/faiss` | morto: 213 vetores de maio, todos T0 |
| LanceDB `DADOS-OBRAS/stog_rag_db` | morto: última escrita 2026-06-04 |
| ByteRover `.brv/context-tree` | parado desde 2026-08-01 |

Risco concreto: um agente que consulte um store parado recebe regra de junho como se
fosse atual, e decisões do dono que só vivem na memória de sessões de agente se perdem.

## 2. O que foi herdado do Cérebro RAG de junho (e não reinventado)

| Princípio de junho | Onde vive agora |
|---|---|
| Tiers T0/T1/T2/TX, consulta global só T1+ | `POLITICA-CONFIANCA-RAG.md` (canônico); decisões = T1; regras T1+ entram na KB |
| Revogação humana sem apagar histórico | `DECISOES-DO-DONO.md`: coluna Estado (`revogada por D-xx`) |
| Regra × instância | KB global guarda regras e decisões; instâncias ficam na KB de cada obra |
| RAG global + RAG por obra | [CONTRATO-KB-MULTIOBRA.md](CONTRATO-KB-MULTIOBRA.md) |
| 8 dimensões por classe | eixo `classes` de cada trecho; manuais de classe como fonte |
| Anti-contaminação (N2/N4 não alimentam N1/N3) | KB só **aponta** fontes; nunca vira prova nem entra no motor |

O que **não** foi herdado: FAISS/LanceDB como armazenamento, indexação de fichas em bulk,
a aba Curadoria redesenhada (continua como ideia no masterplan de junho, histórico).

## 3. Arquitetura resultante

```
docs canônicos (git)  ──►  kb_inventario.py  ──►  FONTES-E-STATUS.md   (o que vale)
        │                                         _inventario.json
        ├── GLOSSARIO / DECISOES-DO-DONO (curados, com fonte)
        ├── kb_mapa_codigo.py  ──►  MAPA-CODIGO.md  (gerado das docstrings)
        ▼
kb_build.py  ──►  KB-GLOBAL/kb_global.sqlite     (FTS5 + vetores + metadados)
      ▲                 ▲
semantic_rag_kb T1+     KB-GLOBAL/obras/<obra>.sqlite   (futuro, mesmo esquema)
                        │
kb_query.py  ◄──────────┘   busca híbrida; kb_eval.py mede a qualidade
```

Tudo abaixo de `KB-GLOBAL/` é **derivado**: apagar e rodar `kb_build.py` reproduz.
A fonte de verdade continua sendo o texto versionado no git.

**Linha de base (2026-09-25, embedder local mpnet, 262 fontes → 5.713 trechos, 25 perguntas):**

| Modo | hit@1 | hit@5 | MRR |
|---|---:|---:|---:|
| texto (FTS5) | 76% | 92% | 0,83 |
| vetor | 56% | 88% | 0,68 |
| **híbrido (padrão)** | **80%** | **92%** | **0,85** |

Build completo ≈ 9 min em CPU (6 núcleos); incremental ≈ 20 s. Falhas conhecidas:
sinônimo sem palavra em comum ("não podem ser alterados" × "intocáveis") — candidato a
melhorar com o embedder NIM (DP-6).

## 4. Rotina de manutenção

| Quando | O quê |
|---|---|
| doc novo / renomeado / descontinuado | `kb_inventario.py` e revisar a seção `candidato_obsoleto`; curadoria em `fontes_override.yaml` |
| decisão nova do dono | linha em `DECISOES-DO-DONO.md` + texto completo no doc do tema |
| módulo novo | docstring de uma frase no topo; `kb_mapa_codigo.py` |
| qualquer um dos acima | `kb_build.py` (incremental: só recalcula trechos alterados) e `kb_eval.py` |
| queda de hit@5 no `kb_eval.py` | investigar antes de seguir: a busca piorou |

## 5. Limpeza — só depois de harmonizar, em fases, nada destrutivo sem ordem

A limpeza **não foi executada**. Cada fase é reversível até a última, e a última exige
ordem explícita do dono.

| Fase | Ação | Alvo | Reversível? |
|---|---|---|---|
| L0 — marcar | status no inventário (feito) | todos | sim |
| L1 — avisar | banner "LEGADO — ver MAPA-DO-CONHECIMENTO" no topo dos docs `legado` | 33 docs | sim |
| L2 — desligar | skill ByteRover sai de `.claude/skills` e `.agents/skills` (arquivar, não apagar) | 2 skills | sim |
| L3 — arquivar | mover docs `legado` para `docs/_arquivo/` (e `../docs/_arquivo/`), mantendo o histórico git | 33 docs + 14 revisados | sim (git mv) |
| L4 — congelar stores | README "CONGELADO" em `data/vectors/faiss/`, `DADOS-OBRAS/stog_rag_db/`, `.brv/` | 3 stores | sim |
| L5 — remover | apagar stores mortos e docs arquivados há 30+ dias sem consulta | FAISS, `stog_rag_db`, `.brv` | **não** — exige ordem do dono |

Antes de L3/L5 em código: conferir que nada importa o alvo
(`grep -r "<modulo>" src portal scripts`). Os scripts `rag_*` da raiz e o
`obra_rag_pipeline` ainda são importados pela app PySide — ficam fora da limpeza até a
app deixar de usá-los.

## 6. Lacunas abertas

1. Decisões PIL que só existem na memória de agente (ver fim de `DECISOES-DO-DONO.md`) → escrever no manual da classe.
2. `CLAUDE.md` do repo traz status datado de 03/07 ("LV 21/32") — número escrito à mão, contra a própria regra; trocar por ponteiro para `docs/STATUS.md`.
3. `docs/SA-ANALISE/CLASSES/LV.md` linha 72 ainda diz "SVG-only" (alteração de outro agente em andamento na hora da harmonização).
4. DP-6 (embeddings NIM) × índice local: a KB suporta os dois; o build inicial foi local porque NIM envia o conteúdo dos docs à NVIDIA — decisão do dono pendente.
5. 136 módulos sem docstring (ver `MAPA-CODIGO.md`): a busca de código não os enxerga pelo papel.
6. Mini-RAG de sessão (`qa_session_index.py`): decidir se vira a camada espacial da KB de obra ou fica como ferramenta de QA separada.
