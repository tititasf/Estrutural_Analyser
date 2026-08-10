# Proposta — Mini-RAG dinâmico de sessão para validação N1 SA

**Status:** proposta de consultoria (2026-07-18), aguardando aprovação do dono antes de
qualquer implementação.
**Escopo:** somente Eixo N1 (campos e vínculos do Structural Analyzer) nas etapas do
looping por classe. Comparação geométrica N2×N4/N3×N4/N3×N2 está **fora** — será
tratada em outra frente como índice estruturado determinístico (não-RAG).
**Contratos que esta proposta respeita e não substitui:**
`CONTRATO-QA-RAG-LOOPINGS.md`, `MASTERPLAN-AGENTE-QA-GLOBAL.md` §7,
`LOOPING-CANONICO.md`, `squads/qa-global-evidencias/references/rag-governance.md`.

## 1. Gap verificado (fatos, 2026-07-18)

1. O "RAG" atual do QA (`semantic_rag_kb`, 117 entradas: FV 43, LV 43, LAJ 21,
   PIL 10) é consultado por `scripts/arete/qa_rag_evidence.py::load_partitioned_rag`
   com **filtro SQL exato** por classe/família/campo/tier/obra/pavimento. Não há
   busca semântica: uma dúvida formulada com vocabulário diferente da regra gravada
   não a recupera.
2. O snapshot N1 de um pavimento não cabe confortável no contexto do agente:
   `beams.data_json` média ~4 KB e máximo ~388 KB por linha; `pillars.links_json`
   até ~32 KB; `slabs.links_json` até ~30 KB (DB real `project_data.vision`).
   Hoje o agente relê fatias sob demanda sem um índice de sessão, o que encarece
   correlação cross-classe (ex.: "quais lajes vinculam este pilar e com que nível").
3. O RAG por-obra (`obra_rag`) indexa apenas metadados de classificação de DXF
   (contagem de entidades + nomes de layers) — nada de campos/vínculos N1.

## 2. Conceito — duas camadas, papéis distintos

O "mini-RAG dinâmico" proposto é um **índice efêmero de sessão**, construído no
início do microciclo para o escopo explícito (project-id + classe + itens) e
descartado/invalidado ao fim. Ele tem duas camadas com naturezas diferentes:

| Camada | Conteúdo | Mecanismo | Papel |
|---|---|---|---|
| **B1 — conhecimento** (semântica) | `semantic_rag_kb` (regras T1/T2/T3), dúvidas estruturadas históricas, achados de triagem, perfis de classe (`class_profiles/*.json`) | embeddings locais + busca por similaridade | recuperar regra/antipadrão/caso parecido mesmo com vocabulário diferente |
| **B2 — snapshot** (estruturada) | campos e vínculos N1 do escopo atual (slabs/pillars/beams do project-id), grafo item↔item cross-classe | índice exato (por chave, campo, relação, faixa de coordenada) — **sem embeddings** | responder consultas determinísticas ("vizinhos de L318", "campos nulos da família X no pavimento") |
| **B3 — fonte CAD** (geométrica) | DXF bruto do pavimento limpo (Fase-1, ex. `TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA.dxf`), entidades via ezdxf: tipo, coordenadas, texto, bbox | índice espacial exato (por faixa de coordenada, proximidade, tipo de entidade) — **sem embeddings, sem semântica de layer** | dar ao QA acesso barato à entidade/coordenada fonte que o contrato exige como prova de campo N1 ("que entidades existem a ≤50cm do ponto X,Y", "que textos numéricos cercam esta laje") |

Racional da separação: conhecimento heurístico se beneficia de recuperação
aproximada; dado do item e geometria exigem resposta exata. Embedar
coordenadas/vínculos em vetores adicionaria aproximação onde o contrato exige
prova — por isso B2/B3 são retrieval estruturado, não RAG. B3 obedece à regra de
independência de layer: consulta por geometria/tipo/conteúdo, nunca por nome de
layer como semântica. Os `TRUE_GEOMETRY.pkl` companheiros são legado — B3 lê o
DXF diretamente via ezdxf.

## 3. Onde entra no looping (etapa nova, sem novo entry point)

Etapa **S-RAG (ingestão de contexto de sessão)**, executada logo após a resolução
de escopo e o snapshot N1, antes da primeira decisão por campo:

```text
escopo explícito → snapshot persistido N1
  → [S-RAG] construir índice de sessão (B1 + B2) com hashes das fontes
  → adaptador da classe decide por campo/vínculo, consultando o índice
  → dossiê cita cada consulta efetivamente usada
  → fix/materialização INVALIDA o índice (igual quadro vivo) → reconstruir
```

Integração concreta (sem criar motor paralelo):

- `qa_evidence_auditor.py review --rag-evidence auto|required` passa a consultar
  B1 via similaridade além do filtro exato atual (fallback: se o modelo de
  embedding não estiver disponível, degrada para o filtro exato de hoje — nunca
  falha por causa da camada semântica).
- `qa_n1_field_probe.py` e `qa_profile_probe.py` ganham acesso opcional a B2 para
  montar contexto cross-classe permitido pela classe (fronteiras FV/LV mantidas).
- Novo módulo único `scripts/arete/qa_session_index.py` (nome sugerido) constrói e
  serve as duas camadas; CLI local, sem MCP (governança: MCP continua adiado).

## 4. Governança (inegociável)

1. **Consultivo, nunca confirmatório.** B1 herda o contrato atual: tier anexado,
   conflito com CAD/ficha ⇒ item `PENDENTE`. B2 é projeção do DB N1 (fonte
   primária com hash) — serve como evidência local, mas não substitui a
   re-derivação do adaptador.
2. **Citação total.** Toda consulta usada vai ao dossiê:
   `rag_consultas.jsonl` (B1) + `session_index_consultas.jsonl` (B2), com hash do
   snapshot que gerou o índice.
3. **Anti-leakage.** N2/N4 **nunca** entram no índice de sessão N1. Fronteiras
   semânticas por classe (FV↮LV em `beams.data_json`) aplicadas na construção.
4. **Efêmero e invalidável.** Índice vive em memória/arquivo temporário do dossiê;
   qualquer materialização headless no escopo o invalida. Nada é promovido a
   `semantic_rag_kb` por esta via — promoção continua exclusivamente pela
   curadoria humana (`qa_rag_curation.py materialize`).
5. **Sem API externa.** Embeddings locais (ex.: sentence-transformers em
   Python 3.12; ChromaDB in-memory já é dependência compatível). Alinha com
   soberania (DP-1..9) e com a proibição de API visual.
6. **Flag same-origin obrigatória (anti-circularidade).** Toda citação B1 deve
   marcar se a entrada tem origem no mesmo escopo (mesma obra/pavimento/item) da
   decisão atual. Entrada same-origin é contexto, nunca reforço confirmatório —
   sem isso, uma regra nascida da L318 "confirmaria" a própria L318. Os campos
   `obra_contexto`/`pavimento` já existem em `semantic_rag_kb`; a flag é
   propagada no dossiê de consultas.

## 5. Custo estimado

Corpus B1 é minúsculo (117 regras + achados/dúvidas históricas): embedding total
em segundos, uma vez por sessão. B2 é leitura já feita pelo snapshot atual —
apenas reorganizada em índice consultável. Sem GPU, sem serviço residente.

## 6. Gates de adoção (piloto antes de institucionalizar)

Decisão de desenho (2026-07-18, confirmada pelo dono): **mecânica se prova no
13_PAV, valor se prova no 14_PAV.** O 13_PAV está selado — respostas conhecidas
separam bug de índice de erro de interpretação de graça. Mas medir "a memória
ajuda?" no 13_PAV seria treinar e testar no mesmo dado: boa parte das regras LAJ
do `semantic_rag_kb` nasceu do próprio 13_PAV. O teste de valor real é
transferência 13→14, no espírito do QG5.

| Gate | Pavimento | Critério |
|---|---|---|
| MR-0 | **13_PAV** (selado) | Protótipo read-only em LAJ: índice constrói, consulta, cita e invalida corretamente; divergência contra o selo = bug de mecânica |
| MR-1 | **14_PAV** (em ataque) | Medição A/B nas pendências reais do ataque em curso: consultas B1/B2/B3 mudam decisão? (menos `PENDENTE` indevido, achado novo com evidência) — relatório com citações e flags same-origin |
| MR-2 | 14_PAV | Integração no `review --rag-evidence` com fallback exato + dossiê estendido |
| MR-3 | ambos | Extensão a PIL/FV/LV respeitando fronteiras; regressão das classes verdes do 13_PAV |
| MR-4 | — | Só então discutir persistência/embedding incremental (fora desta proposta) |

Critério de fracasso honesto: se em MR-1 a camada semântica não alterar nenhuma
decisão em relação ao filtro exato atual, a B1 semântica não se justifica e apenas
B2/B3 (índices estruturados de sessão) seguem adiante.

Plano executável de desenvolvimento e testes:
`docs/MASTERPLAN-MINIRAG-QA-N1.md`.

## 7. Fora de escopo desta proposta

- Diff geométrico N2×N4/N3×N4/N3×N2 (índice estruturado determinístico — outra
  frente, outro chat).
- Embeddings visuais (PNG→vetor) do `MASTERPLAN-CEREBRO-RAG-MULTIMODAL-v1.0.md`.
- Qualquer escrita em N1, `semantic_rag_kb` ou promoção de tier.
