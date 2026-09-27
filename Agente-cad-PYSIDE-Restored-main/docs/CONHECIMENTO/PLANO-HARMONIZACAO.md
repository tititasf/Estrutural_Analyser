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
        ├── kb_grafo.py  ──►  grafo.json  ──►  portal, aba "Base Global" (só o dono; lacunas + cobertura)
        ▼
kb_build.py  ──►  KB-GLOBAL/kb_global.sqlite     (FTS5 + vetores + metadados)
      ▲                 ▲
semantic_rag_kb T1+     KB-GLOBAL/obras/<obra>.sqlite   (futuro, mesmo esquema)
                        │
kb_query.py  ◄──────────┘   busca híbrida; kb_eval.py mede a qualidade
```

Tudo abaixo de `KB-GLOBAL/` é **derivado**: apagar e rodar `kb_build.py` reproduz.
A fonte de verdade continua sendo o texto versionado no git.

**Escolha do embedder por medição (2026-09-26, 262 fontes → 5.719 trechos, 25 perguntas):**

| Embedder | Modo | hit@1 | hit@5 | MRR | Consulta CLI (processo novo) | Build completo |
|---|---|---:|---:|---:|---:|---:|
| — (só texto, FTS5) | texto | 76% | 92% | 0,83 | — | — |
| local `paraphrase-multilingual-mpnet` | híbrido | 80% | 92% | 0,85 | 13,6 s | ~9 min |
| **NIM `nemotron-3-embed-1b` (padrão)** | híbrido | **80%** | **96%** | **0,88** | **2,1 s** | **3 min** |

Critério do dono: "o mais eficiente e disponível" (D-22). NIM venceu em qualidade, tempo de
consulta e de build. Riscos aceitos e mitigados: exige rede e chave; o catálogo NIM tira
modelos do ar sem aviso (o `nv-embed-v1` da DP-6 e mais 3 embedders respondem 410 em
2026-09-26). Se o NIM cair, a busca continua só por texto (92% hit@5 medido); trocar de
modelo = `KB_NIM_MODELO=<modelo> kb_build.py`; offline = `kb_build.py --embedder local`.
Rever a escolha rodando `kb_eval.py --db <índice>` para cada candidato.

## 4. Rotina de manutenção

| Quando | O quê |
|---|---|
| doc novo / renomeado / descontinuado | `kb_inventario.py` e revisar a seção `candidato_obsoleto`; curadoria em `fontes_override.yaml` |
| decisão nova do dono | linha em `DECISOES-DO-DONO.md` + texto completo no doc do tema |
| módulo novo | docstring de uma frase no topo; `kb_mapa_codigo.py` |
| qualquer um dos acima | `kb_build.py` (incremental: só recalcula trechos alterados) e `kb_eval.py` |
| qualquer um dos acima | `kb_grafo.py` (regrava `grafo.json`; o deploy leva à aba "Base Global" do portal) |
| queda de hit@5 no `kb_eval.py` | investigar antes de seguir: a busca piorou |

## 5. Limpeza — isolar e arquivar, nada apagado

Executado em 2026-09-26 (ordem do dono: "não precisa apagar, isolar em legado e arquivar").
Tudo com `git mv` — histórico preservado, reversível.

| Fase | Ação | Estado |
|---|---|---|
| L0 — marcar | status de cada fonte no inventário | ✅ feito |
| L1 — avisar | banner LEGADO no topo do que fica no lugar: `README.md` (raiz e repo), `STATUS.md` do repo; bloco ByteRover do `AGENTS.md` | ✅ feito |
| L2 — desligar | skill ByteRover saiu de `.claude/skills` e `.agents/skills` → `_arquivo/skills/` | ✅ feito |
| L3 — arquivar | 25 docs do programa RAG de junho + rascunho → `docs/_arquivo/`; 8 masterplans/docs antigos da raiz → `D:/Agente-cad-PYSIDE/_arquivo/` (cada arquivo com README) | ✅ feito |
| L4 — congelar stores | `CONGELADO.md` em `data/vectors/faiss/` e `.brv/`; `DADOS-OBRAS/stog_rag_db/` marcado no `CLAUDE.md` da raiz (não se escreve em `DADOS-OBRAS`) | ✅ feito |
| L5 — remover | apagar stores mortos e o arquivo | ⛔ não fazer sem ordem explícita do dono |

O inventário trata qualquer caminho em `_arquivo/` como `legado` (fora do índice). Os
scripts `rag_*` da raiz e o `obra_rag_pipeline` continuam onde estão: a app PySide ainda
os importa.

## 6. Lacunas abertas

1. Invariante de face → D-35. Nível de laje: bug cm×m **corrigido** no código (com portões) e nos dados do 13_PAV (D-37, D-38, `scripts/arete/relatorios/20260926_correcao_nivel_laje/`); desenho da regra por soma de evidências aguarda o dono (`docs/PROPOSTA-NIVEL-LAJE-POR-EVIDENCIAS.md`).
2. `CLAUDE.md` do repo traz status datado de 03/07 ("LV 21/32") — número escrito à mão, contra a própria regra; trocar por ponteiro para `docs/STATUS.md`.
3. ~~`docs/SA-ANALISE/CLASSES/LV.md` linha 72 "SVG-only"~~ — resolvido 2026-09-26.
4. `scripts/obra_rag_utils.py` (RAG por obra da app PySide) ainda chama `nv-embed-v1`, que está fora do ar: cai em silêncio para o modelo local de 768 dimensões, mas as tabelas LanceDB das obras foram criadas com 4096 → nova ingestão na app falha ou mistura vetores. Mesmo problema em `domain_knowledge_ingestor.py`/`stog_rag_ingestor.py` (legados).
5. 136 módulos sem docstring (ver `MAPA-CODIGO.md`): a busca de código não os enxerga pelo papel.
6. Mini-RAG de sessão (`qa_session_index.py`): decidir se vira a camada espacial da KB de obra ou fica como ferramenta de QA separada.
