# Masterplan — Mini-RAG de sessão + índice CAD para o QA Global N1

**Status:** D0+D1+D2+D3 **CONCLUÍDOS**, MR-0 **PASS**, hit-rate D2 **3/3**,
MR-1 **CONCLUÍDO** (2026-07-18/20, branch `sessao/minirag-d0d1-20260718`).
Evidência D0-D3: `scripts/arete/relatorios/20260718_minirag_d0d1/RELATORIO.md`
— 31/31 lajes, 365/365 labels, B2 113/113 fiel, B1 416 entradas locais/sem
API, D3 provado contra o DB real (248==248 decisões, citações aditivas,
invalidação capturou uma escrita concorrente ao vivo durante o teste), 36/36
testes verdes. Evidência MR-1: `scripts/arete/relatorios/20260718_minirag_d0d1/MR1-RELATORIO.md`
— achado arquitetural prévio (RAG nunca influencia decisão, por desenho;
métrica ajustada com o dono para "cobertura única do B1"), medido no 14_PAV
real (176 decisões, 44 abertas): B1 trouxe 8 citações exclusivas
(`human_event_logs`, invisíveis para B2), 2 delas exatamente sobre as
famílias hoje abertas (`laje_nivel`, `laje_vizinhas_niveis`), corretamente
marcadas `same_origin=false` (0 uso indevido em toda a rodada). Próximo:
decisão do dono sobre institucionalizar (MR-2/MR-3) ou parar aqui.
**Conceito e governança:** `docs/PROPOSTA-MINIRAG-SESSAO-N1.md` (camadas B1/B2/B3,
regras inegociáveis, same-origin). Este masterplan é o plano executável de
desenvolvimento, testes e evolução do QA.
**Contratos superiores:** `CONTRATO-QA-RAG-LOOPINGS.md`,
`MASTERPLAN-AGENTE-QA-GLOBAL.md`, `LOOPING-CANONICO.md`,
`QA-VISAO-EVIDENCIA-CANONICA.md`. Em conflito, eles vencem.

## 1. Objetivo final

Dar ao Agente QA Global uma ferramenta de sessão que ingere dinamicamente o
contexto completo do escopo — conhecimento curado (B1), snapshot N1 (B2) e o
**DXF limpo do pavimento inteiro (B3)** — para que cada decisão de campo/vínculo
SA N1 seja tomada com contexto total, citável e barato, em vez de releituras
artesanais de JSON. O QA fica mais eficiente; a autoridade não muda: prova
continua sendo re-derivação do adaptador + gate visual + veredito humano.

## 2. Fatos do ambiente (verificados 2026-07-18 — não redescobrir)

| Item | Valor |
|---|---|
| Regras curadas | `semantic_rag_kb` = 117 (FV 43, LV 43, LAJ 21, PIL 10), colunas tipadas classe/família/campo/tier/obra/pavimento |
| Consulta atual | `scripts/arete/qa_rag_evidence.py::load_partitioned_rag` — filtro SQL exato, sem similaridade |
| Volume N1 | `beams.data_json` avg ~4 KB / max ~388 KB; `pillars.links_json` max ~32 KB; `slabs.links_json` max ~30 KB |
| DXF 13_PAV (selado) | `DADOS-OBRAS/Obra_TREINO_1/Fase-1_Ingestao/Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF/TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA.dxf` |
| DXF 14_PAV (em ataque) | idem, `TMC-EST-PE-7000-14P-R03_R2018_ASCII_ODA.dxf` |
| `TRUE_GEOMETRY.pkl` | companions existem, são LEGADO — B3 lê DXF direto via ezdxf |
| Python | 3.12 obrigatório (`D:\Agente-cad-PYSIDE\.venv`); ChromaDB compatível |
| Dossiês | `scripts/arete/relatorios/qa_evidencias/` + `rag_consultas.jsonl` por sessão |

## 3. Arquitetura de implementação

Módulo único novo: `scripts/arete/qa_session_index.py` (CLI local; sem MCP).

```text
qa_session_index.py build --project-id <id> --classe LAJ [--pav-dxf <path>]
  → constrói no dossiê da sessão:
     b1/  chroma in-memory ou fallback exato (regras + dúvidas + achados)
     b2/  índice sqlite/json do snapshot N1 (campos, vínculos, grafo cross-classe)
     b3/  índice espacial do DXF (entidades: tipo, coords, bbox, texto; grid/R-tree)
     manifest.json  (hashes de TODAS as fontes + versão do builder)

qa_session_index.py query --kind b1|b2|b3 --json <consulta>
  → resposta + registro append em session_index_consultas.jsonl
```

Regras de construção:

- **B1**: embeddings locais (sentence-transformers, modelo pequeno, CPU). Se o
  modelo não carregar, degrada para o filtro exato atual — nunca bloqueia sessão.
  Cada entrada carrega tier + flag `same_origin` calculada contra o escopo.
- **B2**: projeção read-only das linhas slabs/pillars/beams do project-id;
  fronteiras de classe aplicadas na consulta (FV↮LV em `beams.data_json`).
- **B3**: ezdxf sobre o DXF de Fase-1; indexa entidade→(tipo, coords, bbox,
  conteúdo de texto). Nome de layer é armazenado apenas como metadado descritivo,
  **nunca** como filtro semântico (regra de independência de layer). N2/recortes
  reversos ficam FORA.
- Invalidação: `manifest.json` guarda hash do snapshot e do DXF; qualquer
  materialização headless no escopo torna o índice stale → rebuild obrigatório
  antes de nova consulta (mesma disciplina do quadro vivo).

## 4. Fases de desenvolvimento

### D0 — Esqueleto e B2 (o mais barato e certo)
- `qa_session_index.py` com build/query, manifest com hashes, log de consultas.
- B2 completo para LAJ: campos, vínculos, grafo laje↔pilar/viga do pavimento.
- Teste: no 13_PAV selado, respostas de B2 batem 100% com o snapshot (é projeção;
  divergência = bug).
- Saída: CLI funcional read-only + testes unitários do builder.

### D1 — B3 (ingestão do DXF limpo do pavimento)
- Ingestor ezdxf → índice espacial (grid simples primeiro; R-tree se necessário).
- Consultas mínimas: `entities_near(x, y, raio)`, `texts_in_bbox(...)`,
  `entities_of_type(tipo, bbox)`.
- Teste de mecânica (13_PAV): para 5 lajes seladas, as entidades-fonte que o
  selo LAJ já provou devem ser recuperáveis por consulta espacial a partir das
  coordenadas do N1. Falha = bug do índice, não da interpretação.
- Teste de performance: build do 13_PAV completo < 30 s; consulta < 100 ms.

### D2 — B1 (camada semântica)
- Embedding local das 117 regras + dúvidas estruturadas + achados de triagem.
- Consulta híbrida: filtro exato de partição (classe/família/tier) E similaridade
  dentro da partição — nunca similaridade global sem partição.
- Flag `same_origin` em toda resposta.
- Teste: 10 dúvidas reais reformuladas com vocabulário diferente; a regra
  correta deve aparecer no top-3 da partição. Registro de hit-rate.

### D3 — Integração consultiva no looping
- `qa_evidence_auditor.py review --rag-evidence auto` consulta B1 via
  `qa_session_index` quando o índice existe (fallback: caminho atual intacto).
- `qa_n1_field_probe.py` ganha `--session-index <dossiê>` opcional para montar
  contexto cross-classe/B3 nos checks declarados.
- Nada de `apply` novo; autoridade progressiva do contrato §5 inalterada.

### D4 — Medição e veredito (ver §5)
- Relatório A/B, decisão do dono sobre institucionalizar, matar B1 ou só B2/B3.

## 5. Plano de testes — 13_PAV prova mecânica, 14_PAV prova valor

**Por quê a divisão:** o 13_PAV está selado (respostas conhecidas ⇒ oráculo grátis
para bugs de índice), mas as regras LAJ do `semantic_rag_kb` nasceram dele —
medir "valor da memória" ali é treinar e testar no mesmo dado. Transferência
13→14 é o teste honesto (espírito QG5).

### MR-0 (13_PAV, mecânica) — bloqueia D2→D3
1. Build completo B1+B2+B3 do 13_PAV LAJ.
2. Replay: para cada laje selada, consultar B2/B3 e conferir que o contexto
   recuperado é consistente com a evidência do selo.
3. Auditar `session_index_consultas.jsonl`: toda consulta registrada com hash.
4. Invalidação: simular materialização → índice marca stale → rebuild.
5. PASS = zero divergência mecânica + citações completas. Divergência de
   conteúdo aqui é bug do builder, por definição.

### MR-1 (14_PAV, valor) — dentro do ataque em curso
1. Selecionar as pendências LAJ reais do 14_PAV (fila do ataque atual).
2. Para cada decisão: rodar o caminho atual (sem índice) e o caminho com índice,
   registrando ambas as saídas e as consultas citadas.
3. Métricas:
   - decisões alteradas (`PENDENTE`→`CONFIRMAR/CORRIGIR` com evidência local, ou
     achado novo aberto);
   - tempo/leituras por decisão (eficiência);
   - citações same-origin usadas indevidamente como reforço (deve ser ZERO);
   - falsos ganhos (decisão mudou mas o gate visual/humano reprovou) — cada um
     é regressão grave do piloto.
4. Veredito por evidência, não por impressão: relatório em
   `scripts/arete/relatorios/qa_evidencias/minirag_mr1/` com antes/depois por item.

### Critérios de encerramento
- **Sucesso B1**: ≥1 decisão real melhorada por recuperação semântica que o
  filtro exato não encontraria, sem nenhum falso ganho.
- **Sucesso B2/B3**: redução mensurável de releituras/tempo por decisão no
  mesmo conjunto de itens.
- **Fracasso honesto B1**: zero decisão alterada ⇒ manter só B2/B3, arquivar B1.
- Qualquer confirmação circular same-origin detectada ⇒ parada e correção antes
  de continuar.

## 6. Evolução do QA com a ferramenta (o que muda em cada rota)

| Rota do looping | Sem índice (hoje) | Com índice de sessão |
|---|---|---|
| `review` por campo | relê fatias de JSON por item; RAG só por filtro exato | contexto cross-classe pronto (B2) + regra por similaridade citada (B1) |
| `qa_n1_field_probe` | fontes declaradas manualmente por request | request pode referenciar consultas B3 ("entidade fonte a ≤50cm") como check |
| dúvida estruturada | formulada sem saber se já foi respondida parecida | busca semântica em dúvidas históricas antes de perguntar ao dono |
| triagem de achado | recorrência detectada de memória do agente | recorrência consultável ("achados parecidos em outras classes/pavs") |
| prova de campo (contrato §5.2 "evidência local independente") | localizar entidade fonte é investigação manual no DXF | B3 devolve candidatos por coordenada em ms; adaptador re-deriva como sempre |

O ganho-alvo agregado: menos `PENDENTE` por ignorância de contexto, ensino
humano reutilizado entre sessões, e o custo de contextualizar uma decisão caindo
de minutos para segundos — mantendo cada consulta auditável no dossiê.

## 7. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Confirmação circular (regra nascida do item "confirma" o item) | flag same-origin obrigatória; MR-1 mede uso indevido (meta: zero) |
| Falso ganho (decisão muda, visual reprova) | todo `CONFIRMAR/CORRIGIR` novo do piloto passa pelo gate visual antes de contar como sucesso |
| Layer como semântica no B3 | consulta só por geometria/tipo/texto; layer é metadado descritivo; teste de regressão específico |
| Contaminação N2/N4 no índice N1 | builder recusa paths de recortes/Fase-2; teste anti-leakage no CI do módulo |
| Índice stale após fix | hash no manifest + rebuild forçado; consulta em índice stale falha fechado |
| Peso de dependência (modelo de embedding) | modelo pequeno CPU-only; fallback degrada para filtro exato sem quebrar sessão |
| Scope creep para N2×N4 | fora de escopo declarado; diff geométrico é outra frente (não-RAG) |

## 8. Sequência recomendada de execução

1. **D0+D1 juntos** (B2+B3 são determinísticos e de valor certo) → MR-0 no 13_PAV.
2. **D2** (B1) → repetir MR-0 só para mecânica de citação/same-origin.
3. **D3** integração consultiva → **MR-1 no 14_PAV dentro do ataque LAJ real**.
4. **D4** relatório A/B → decisão do dono (institucionalizar / só B2/B3 / arquivar).
5. Extensão PIL/FV/LV (MR-3) somente após veredito, com regressão das classes
   verdes do 13_PAV.

Toda rodada termina com relatório em `scripts/arete/relatorios/` (protocolo
padrão) e este masterplan atualizado com o estado real — números escritos à mão
envelhecem; o estado vivo é o dossiê.

## 9. Uso recomendado a partir de 2026-07-20 (pós-MR-1)

Decisão do dono (2026-07-20): ligar para uso real em vez de acumular mais
teste sintético — a mecânica já está provada (36/36 testes + duas validações
reais MR-0/MR-1); o que faltava era qualidade de texto (fix em §10).
Governança inalterada: RAG continua consultivo, nunca confirmatório.

**Prática recomendada** (não é gate, não bloqueia se pulado; `--classe` aceita
`LAJ|PIL|FV|LV|ALL` — o mecanismo é classe-agnóstico em código. **Mas o ganho real
varia por classe** — ver §11 antes de tratar isso como recomendação uniforme):

```powershell
$py = 'D:\Agente-cad-PYSIDE\.venv\Scripts\python.exe'

# 1. Construir/atualizar o índice de sessão do pavimento em foco (uma vez por
#    sessão de trabalho, ou quando N1/regras mudarem — falha fechado se stale).
& $py -X utf8 scripts/arete/qa_session_index.py build `
  --project-id <id> --out scripts/arete/relatorios/qa_session_index/<obra>_<pav> `
  --pav-dxf <DXF limpo de Fase-1_Ingestao>

# 2. Passar --session-index nas revisões reais da sessão (qualquer classe).
& $py -X utf8 scripts/arete/qa_evidence_auditor.py review `
  --project-id <id> --classe FV --include-sealed `
  --session-index scripts/arete/relatorios/qa_session_index/<obra>_<pav>
```

Ponteiro cruzado registrado em `CONTRATO-QA-RAG-LOOPINGS.md` §3.

## 10. Fix de qualidade pós-MR-1 (2026-07-20)

MR-1 achou o resumo de aprovações em lote (`human_event_logs`, status
`APPROVED`) fino demais: dizia "existe aprovação" sem dar ao leitor como
localizar o pacote completo. Corrigido em `_b1_row_text_human_event_logs`
(`qa_session_index.py`): extrai `candidate_id` do `log_id` (padrão
`qa-rag-approval-<candidate_id>`) e inclui `approved_by`/`approved_at`,
virando um ponteiro buscável em `semantic_rag_kb.regra_semantica` em vez de
uma afirmação vaga. Testado contra fixture
(`test_b1_aprovacao_humana_traz_candidate_id_navegavel`,
`test_b1_aprovacao_sem_padrao_de_log_id_nao_quebra`) e confirmado contra os
dois índices reais (13_PAV, 14_PAV) — texto real:

```
[LAJ] item MULTI — Aprovação humana do pacote QA ground truth
(campos alterados: laje_dim; status APPROVED; aprovado por dono em
2026-07-13T01:18:51+00:00; candidate_id=qa-rag-19bcc9bb72e5e6bb
(buscar em semantic_rag_kb.regra_semantica))
```

## 11. MR-3 — extensão validada a PIL/FV/LV (2026-07-20)

Pedido do dono: estender o mecanismo às outras 3 classes e atualizar os
procedimentos onde isso soma valor. Relatório completo:
`scripts/arete/relatorios/20260718_minirag_d0d1/MR3-RELATORIO.md`.

**Achado que mudou o escopo:** `qa_session_index.py`/`qa_evidence_auditor.py`
já eram classe-agnósticos em código antes desta rodada — `B2_COLUMNS` sempre
indexou `slabs`/`pillars`/`beams` juntos, e `load_session_index_b1_context`
já iterava por classe sem hardcode de LAJ. MR-3 não escreveu mecanismo novo;
mediu, com o mesmo rigor do MR-0/MR-1, se ele funciona e ajuda nas outras 3
classes.

**Regressão (13_PAV, `--include-sealed`):** decisões idênticas com/sem
`--session-index` — PIL 560/560, FV 526/526, LV 394/394. Zero divergência.

**Cobertura única medida** (B1 vs baseline `semantic_rag_kb`, `--rag-limit 50`):

| Classe | Ganho único do B1 | Fonte |
|---|---|---|
| FV | +7 | `human_event_logs` status `CAPTURED` |
| LV | +4 | `human_event_logs` status `CAPTURED` |
| PIL | **0** | `human_event_logs` classe PIL está vazio hoje |

**Veredito por classe (não uniforme, de propósito):** FV e LV — institucionalizar
`--session-index` como prática recomendada, mesmo padrão de LAJ (MR-1). PIL —
mecanismo disponível e testado, mas **sem recomendar uso obrigatório ainda**: não
há ganho real até `human_event_logs` acumular decisões humanas para essa classe.
Forçar a prática ali seria ritual sem função. Diários atualizados de acordo:
`docs/SA-ANALISE/HISTORICO/FV.md`, `LV.md` (recomendam), `PIL.md` (documenta
disponibilidade sem recomendar).

Achado colateral fora de escopo, registrado para não se perder: `human_event_logs`
tem 231 linhas sob `classe="LJ"` (não `"LAJ"`) — mesma inconsistência de nome já
documentada e deliberadamente não corrigida em `ARETE-LOOP-PROCEDIMENTO-GERAL.md`
§6.1 item 1. Não afeta o resultado de LAJ (que já tinha cobertura B1 provada via
linhas `classe="LAJ"` reais no MR-1), mas deixa esse corpus sob `"LJ"` invisível
para consulta B1 até uma decisão explícita de normalizar.
