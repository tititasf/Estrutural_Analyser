# Contrato — KB global e KB por obra

**Status:** canônico · **Criado:** 2026-09-25 · **Implementação:** `scripts/kb/`

## 1. Duas camadas, um esquema

| | KB global | KB de obra |
|---|---|---|
| Arquivo | `KB-GLOBAL/kb_global.sqlite` | `KB-GLOBAL/obras/<obra>.sqlite` (um por obra) |
| `escopo` | `global` | `obra:<nome>` |
| Conteúdo | o que vale para **toda** obra: regras, decisões, glossário, procedimentos, código | o que é **desta** obra: convenções locais, pendências, respostas do dono sobre ela, notas de QA |
| Autoridade | T1+ (decisões, regras validadas) e docs canônicos | T0 até validação; T1 = validado nesta obra |
| Construção | `kb_build.py` | `kb_build.py --obra <nome> --fontes <pasta>` |
| Consulta | `kb_query.py "..."` | `kb_query.py "..." --obra <nome>` (global + obra, fundidos) |

Arquivos separados por obra garantem a regra **mesma origem**: evidência de uma obra não
contamina outra, e uma obra pode ser refeita ou apagada sem tocar no global.

## 2. Esquema de um trecho (`chunks`)

| Campo | Regra |
|---|---|
| `escopo` | `global` ou `obra:<nome>` — nunca vazio |
| `tipo` | `doc` · `decisao` · `glossario` · `regra_semantica` · `codigo` (novos tipos entram aqui antes do código) |
| `path` | caminho relativo a `D:/Agente-cad-PYSIDE` ou `project_data.vision#tabela/id` |
| `secao` | trilha de títulos — o resultado de busca aponta **arquivo + seção** |
| `status` | status da fonte no inventário; `legado` e `candidato_obsoleto` não são indexados |
| `tier` | T1/T2 para decisões e regras validadas; vazio para docs |
| `classes` | `,PIL,LV,` — detectadas pelo caminho, seção ou texto |
| `sha` | hash do texto indexado — chave do cache de vetores |

## 3. Regras

1. **A KB aponta; não prova.** Todo uso decisório abre a fonte. Em QA, a evidência
   continua sendo a local da obra (dossiê, PNG, inventário).
2. **Nada entra na KB sem estar no texto versionado** (doc no git ou linha no DB com
   tier). A KB é derivada e reconstruível.
3. **Promoção obra → global:** uma regra da KB de obra só vira global com decisão do dono
   (T1) ou validação em ≥2 obras (T2), registrada em `DECISOES-DO-DONO.md` ou em
   `semantic_rag_kb` com tier. Nunca por similaridade.
4. **Revogação:** decisão revogada continua no registro com `revogada por`; regra do DB
   vai a `TX`. O build seguinte já exclui `TX` (só T1/T2 são lidos).
5. **Embedder por arquivo:** cada índice guarda o embedder em `meta`; a consulta usa o
   mesmo. Global e obra podem ter embedders diferentes — a fusão é por posição (RRF), não
   por distância.
6. **N2/N4 não entram na KB de obra como regra.** Podem entrar como nota de QA
   (`tipo=doc`, tier vazio), nunca como fonte de interpretação N1/N3.

## 4. O que alimentará a KB de uma obra (quando a Obra_TREINO_1 fechar)

Candidatos, em ordem de valor — decidir com o dono antes de ligar:

1. Respostas do dono sobre a obra (fichas de dúvida respondidas, `revisoes_humanas.json`).
2. Relatórios `RELATORIO.md` das rodadas Arete da obra (achados, causas, fixes).
3. Convenções locais medidas (níveis, convenção de pilares, pavimentos-tipo).
4. Pendências abertas por item (o que ainda falta validar).
5. Índice espacial do DXF (mini-RAG `qa_session_index.py`) — como camada separada, se
   medir valor (ver `PLANO-HARMONIZACAO.md` §6).

Montagem prevista: um passo que exporta 1–4 para `DADOS-OBRAS/<obra>/kb_fontes/*.md` e
chama `kb_build.py --obra <obra> --fontes DADOS-OBRAS/<obra>/kb_fontes`.
