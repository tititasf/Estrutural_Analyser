# MASTERPLAN — RAG: Integração Completa por Todas as Frentes
## CAD-ANALYZER | Athena (CEO-PLANEJAMENTO) | 2026-03-19

---

## SUMÁRIO EXECUTIVO

O sistema RAG FAISS está operacional com **799 vetores** de 11 obras (228 pilares, 351 vigas,
220 lajes). Este masterplan mapeia como esse corpus de conhecimento vetorizado deve ser integrado
em **8 frentes distintas** do pipeline CAD-ANALYZER — da extração DXF até a geração de DXFs
finais — para que o sistema tenha **compreensão semântica real** dos elementos estruturais.

### UPDATE (2026-06-29) - Camada de Event Sourcing MCP
A infraestrutura de RAG descrita abaixo foi recentemente potencializada pela nova camada **MCP (Model Context Protocol)** e banco de dados SQLite (human_event_logs). Foram criados ganchos diretamente na UI (Diagnostic Hubs, Structural Analyzer e Robô de Laterais) usando db_bridge.save_human_edit_event().
Qualquer edição humana pode gerar um evento rastreável, mas o evento nasce
`CAPTURED/T0`: é evidência para investigação, não verdade validada. O daemon produz
uma proposta `PROPOSED/T0` e somente o botão explícito **Aprovar proposta**, com
justificativa humana, permite T1. Os stores MCP são separados do corpus estrutural;
nenhum botão Salvar escreve em `estruturais.index`.

Os loops 1, 2, 7 e 8 possuem ferramentas de leitura/captura úteis. Os loops 3, 4, 5 e
6 ainda possuem ferramentas MCP declarativas com `PENDENTE_INTEGRACAO`; não devem ser
descritos como automação operacional.

### Stack RAG (Confirmado Operacional)
| Componente | Tecnologia | Status |
|---|---|---|
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` 384 dims | ✅ ATIVO |
| Vector DB | FAISS FlatIP + L2 norm (cosine sim) | ✅ ATIVO |
| Ingestor | `scripts/rag_ingestor.py` | ✅ ATIVO |
| Query API | `scripts/rag_query.py` | ✅ ATIVO |
| Índices | estruturais (799) + pilares (228) + vigas (351) + lajes (220) | ✅ ATIVO |
| Registry | `data/vectors/faiss/REGISTRY.json` | ✅ ATIVO |

---

## FRENTES DE INTEGRAÇÃO

```
PIPELINE CAD-ANALYZER — ONDE O RAG ENTRA

DXF Bruto
    ↓
[Fase 1: Intake]          → FRENTE G: Layer Matching Semântico
    ↓
[Fase 2: Purge]           → (sem RAG direto)
    ↓
[Fase 3: Prism]           → FRENTE A: Confidence Boost + FRENTE E: Auto-Complete Dims
    ↓
[Revisão Humana]          → FRENTE D: Anomaly Flag (antes de revisar)
    ↓
[Fase 4: Transform]       → FRENTE B: Validação Cross-Obra
    ↓
[Fase 5/6: Forge+Merge]   → FRENTE H: STOG Validation
    ↓
[Fase 7: Verify]          → FRENTE D: Quality Gate RAG
    ↓
[Fichas PDF]              → FRENTE C: Fichas Enriquecidas
    ↓
[Atlas DXF]               → FRENTE F: Atlas Semântico
    ↓
[CLI/Debug]               → FRENTE E (já existe: rag_query.py)
```

---

## FRENTE A — Confidence Boost na Extração (Fase 3: Prism)

### Problema
Quando Prism extrai um elemento com `confidence < 0.80`, ele vai para a fila de revisão
humana. Mas muitas vezes a extração está **correta** e o baixo confidence é apenas ruído
(layer unusual, texto corrompido, etc.). O RAG pode confirmar se o elemento extraído é
plausível vs corpus histórico.

### Solução: RAG Plausibility Check
```python
def rag_plausibility_check(elemento_extraido: dict, modelo_rag) -> dict:
    """
    Consulta RAG para validar se elemento extraído é plausível.
    Retorna: plausibility_score (0.0-1.0) + similar_elements + ação recomendada
    """
    # Formatar texto do elemento extraído igual ao corpus
    texto = fmt_pilar(elemento_extraido['id'], elemento_extraido, obra, pav)

    # Buscar similares no FAISS
    resultados = query(texto, tipo=elemento_extraido['tipo'], k=5)

    if not resultados:
        return {'plausibility': 0.0, 'acao': 'REVISÃO OBRIGATÓRIA', 'similar': []}

    top_score = resultados[0]['score']

    # Se RAG encontra similar com alta similaridade → elemento plausível
    if top_score > 0.85:
        return {'plausibility': 0.95, 'acao': 'ACEITAR', 'similar': resultados[:3]}
    elif top_score > 0.65:
        return {'plausibility': 0.70, 'acao': 'ACEITAR COM AVISO', 'similar': resultados[:3]}
    else:
        return {'plausibility': 0.20, 'acao': 'REVISÃO OBRIGATÓRIA', 'similar': resultados[:1]}
```

### Integração no Agente Estrutural
```python
# Em agente_estrutural.py ou prism.py — após extração de cada elemento:
if elemento.confidence < 0.80:
    rag_check = rag_plausibility_check(elemento, rag_model)

    # Se RAG valida → upgrade confidence
    if rag_check['plausibility'] > 0.90:
        elemento.confidence = max(elemento.confidence + 0.15, 0.80)
        elemento.nota += f" | RAG-VALIDATED: similar a {rag_check['similar'][0]['meta']['obra']}"

    # Se RAG rejeita → manter na fila de revisão com contexto
    else:
        elemento.nota += f" | RAG-ANOMALY: sem similar no corpus (score={rag_check['plausibility']:.2f})"
```

### Impacto Esperado
- Redução de 30-40% na fila de revisão humana desnecessária
- Contexto "similar em obra X" ajuda revisor humano a decidir mais rápido
- Elementos genuinamente anômalos ficam mais visíveis (não há falsos alarmes)

### Arquivo a criar
`scripts/rag_plausibility.py` — módulo importável pelo agente_estrutural

---

## FRENTE B — Validação Cross-Obra (Fase 4: Transform)

### Problema
Na Fase 4 (Transform), os dados são convertidos para objetos CAD. Dimensões
fora do range histórico geram DXFs com geometria absurda (pilar com b=2000cm).

### Solução: RAG Range Validator
```python
LIMITES_RAZOAVEIS = {
    'pilar': {
        'b': (15, 200),    # cm — range histórico real das 11 obras
        'h': (15, 150),
        'altura': (200, 1000),
    },
    'viga': {
        'b': (10, 60),
        'h': (20, 120),
        'comprimento': (50, 2000),
    },
    'laje': {
        'espessura': (7, 40),
        'area_cm2': (5000, 5000000),
    }
}

def rag_range_check(elemento: dict) -> dict:
    """
    Valida dimensões contra dois critérios:
    1. Limites absolutos (LIMITES_RAZOAVEIS)
    2. Distribuição real do corpus RAG (média ± 3σ)
    """
    tipo = elemento['tipo']
    dados = elemento['dados']
    alertas = []

    # Check limites absolutos
    for campo, (min_v, max_v) in LIMITES_RAZOAVEIS.get(tipo, {}).items():
        valor = dados.get(campo)
        if valor and isinstance(valor, (int, float)):
            if not (min_v <= valor <= max_v):
                alertas.append({
                    'campo': campo,
                    'valor': valor,
                    'range': f'{min_v}-{max_v}',
                    'severidade': 'CRÍTICO' if valor > max_v * 3 else 'AVISO'
                })

    return {'alertas': alertas, 'aprovado': len([a for a in alertas if a['severidade'] == 'CRÍTICO']) == 0}
```

### Arquivo a criar
`scripts/rag_validator.py` — usado na Fase 4 antes de Transform

---

## FRENTE C — Fichas PDF Enriquecidas com Contexto RAG

### Problema
As fichas PDF atuais (gerar_fichas_v5.py) mostram apenas os dados extraídos da obra
atual. Falta contexto: "este pilar P20 com b=25 h=50 — é típico ou incomum?"

### Solução: Seção "Similares no Corpus" nas Fichas
Adicionar bloco em cada ficha com:
- Top 3 elementos similares encontrados em outras obras
- Score de similaridade
- Dimensões dos similares (para comparação)
- Flag de anomalia se similarity < 0.5

```python
# Em gerar_fichas_v6.py — bloco adicional por elemento:
def bloco_rag_similares(elemento_id, tipo, dados, obra, model, faiss_index, meta):
    """Retorna Flowable ReportLab com seção RAG."""
    from rag_query import query

    texto_busca = fmt_element(elemento_id, tipo, dados, obra)
    similares = query(texto_busca, tipo=tipo, k=3, threshold=0.30)

    if not similares:
        return Paragraph("Nenhum similar encontrado no corpus.", STYLES['body'])

    rows = [["Elemento", "Obra", "b×h", "Similaridade"]]
    for s in similares:
        m = s['meta']
        d = m.get('dados', {})
        b = d.get('b', '?')
        h = d.get('h', d.get('comprimento', '?'))
        rows.append([
            f"{m.get('tipo','').upper()} {m.get('id','')}",
            m.get('obra', ''),
            f"{b}×{h}cm",
            f"{s['score']:.2f}"
        ])

    return Table(rows, style=TABLE_STYLE_RAG)
```

### Output
`gerar_fichas_v6.py` — versão final das fichas com contexto RAG integrado

---

## FRENTE D — Detecção de Anomalias + Quality Gate

### Problema
A Fase 7 (Verify) não tem critério quantitativo para detectar elementos anômalos
vs o que já foi aprovado em obras anteriores.

### Solução: Anomaly Score via RAG Centroid Distance
```python
def calcular_anomaly_score(elemento: dict, faiss_index, meta) -> float:
    """
    Score de anomalia 0.0-1.0:
    - 0.0 = completamente normal (idêntico a outros no corpus)
    - 1.0 = completamente anômalo (sem similar no corpus)
    """
    texto = fmt_element(elemento)
    similares = query(texto, tipo=elemento['tipo'], k=10, threshold=0.0)

    if not similares:
        return 1.0  # máxima anomalia

    top_sim = similares[0]['score']
    # Score de anomalia = inverso da similaridade máxima
    return 1.0 - top_sim

# No gate da Fase 7:
for elemento in obra_processada.elementos:
    anomaly = calcular_anomaly_score(elemento, ...)

    if anomaly > 0.80:
        gate_results.append({
            'elemento': elemento.id,
            'tipo': 'ANOMALIA_CRÍTICA',
            'anomaly_score': anomaly,
            'acao': 'BLOQUEAR — revisar antes de gerar DXF'
        })
    elif anomaly > 0.60:
        gate_results.append({
            'elemento': elemento.id,
            'tipo': 'ANOMALIA_LEVE',
            'anomaly_score': anomaly,
            'acao': 'ACEITAR COM AVISO'
        })
```

### Arquivo a criar
`scripts/rag_anomaly_detector.py` + integração em `sprint_e_production_gate.py`

---

## FRENTE E — CLI de Diagnóstico e Pesquisa (Já Existe)

### O que já existe
`scripts/rag_query.py` — operacional com:
```bash
python scripts/rag_query.py --stats
python scripts/rag_query.py "pilar 20x50" --tipo pilar --k 5
python scripts/rag_query.py "viga balanco" --tipo viga --obra Obra_TREINO_1
```

### Expansões planejadas

#### E-1: Consulta por ID específico
```bash
python scripts/rag_query.py --find-element P17 --obra Obra_TREINO_1
# → Mostra o elemento e seus 5 mais similares em outras obras
```

#### E-2: Relatório de distribuição de dimensões
```bash
python scripts/rag_query.py --dims-report --tipo pilar
# → Histograma de b, h, altitude para todos os pilares do corpus
# → Percentis: p10, p25, p50, p75, p90
```

#### E-3: Outlier detection global
```bash
python scripts/rag_query.py --anomalies --tipo viga --threshold 0.7
# → Lista todos os elementos com anomaly_score > threshold
```

#### E-4: Cross-obra comparison
```bash
python scripts/rag_query.py --compare-obras Obra_TREINO_1 Obra_TREINO_13
# → Distribuições lado a lado, elementos exclusivos em cada obra
```

### Arquivo a expandir
`scripts/rag_query.py` — adicionar subcomandos `--find-element`, `--dims-report`, `--anomalies`, `--compare-obras`

---

## FRENTE F — Atlas Semântico (Clustering RAG)

### Problema
Os atlases atuais (`gerar_atlas_pilares.py`, etc.) agrupam por dimensão física
(ordena por b×h). Faltam agrupamentos semânticos que capturem padrões mais ricos.

### Solução: Atlas com K-Means sobre embeddings FAISS
```python
from sklearn.cluster import KMeans
import faiss, numpy as np

def gerar_atlas_semantico(tipo='pilar', n_clusters=5):
    """
    1. Carrega vetores FAISS do tipo
    2. Aplica K-Means sobre embeddings
    3. Identifica cluster semântico de cada elemento
    4. Gera atlas agrupado por cluster (não por dimensão)
    """
    index = faiss.read_index(f'data/vectors/faiss/{tipo}s.index')

    # Extrair vetores
    vecs = np.zeros((index.ntotal, 384), dtype=np.float32)
    faiss.extract_index_vectors(index, vecs)  # ou via reconstruct_n

    # Clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    labels = kmeans.fit_predict(vecs)

    # Nomear clusters automaticamente (elemento mais central de cada)
    for cluster_id in range(n_clusters):
        idxs = np.where(labels == cluster_id)[0]
        center = kmeans.cluster_centers_[cluster_id]
        # Elemento mais próximo do centroide = "representante" do cluster
        ...

    # Gerar PDF por cluster
    # Cluster 0: "Pilares pequenos (b<20, h<40)"
    # Cluster 1: "Pilares médios (b=20-40)"
    # Cluster 2: "Pilares grandes/especiais"
```

### Arquivo a criar
`scripts/gerar_atlas_semantico.py` — atlas por cluster RAG

---

## FRENTE G — Layer Matching Semântico (Fase 1: Intake)

### Problema
Quando uma obra de firma desconhecida chega, os layers têm nomes diferentes dos
mapeados em CONFIG-LAYERS.yaml. Hoje a Fase 1 usa regex simples — mas o contexto
semântico do nome do layer não é explorado.

### Solução: Vetorizar nomes de layers + match semântico
```python
# Corpus de layers canônicos já mapeados (do CONFIG-LAYERS.yaml):
CANONICAL_LAYERS = {
    'PAINEIS': 'PANEL_GEOMETRY',
    'NOMENCLATURA': 'ELEMENT_LABEL',
    'fundo': 'BEAM_BOTTOM',
    'SARRAFO': 'WOOD_BATTEN',
    # ... 85 layers mapeados
}

def semantic_layer_match(layer_desconhecido: str, model, threshold=0.70) -> dict:
    """
    Para layer desconhecido de firma nova, encontrar equivalente canônico.
    Exemplo: 'PILLAR-BORDER-LINE' → 'PANEL_GEOMETRY' (similarity=0.78)
    """
    vec = model.encode([layer_desconhecido])
    vec = normalize(vec)

    # Buscar nos canônicos pré-embedados
    scores, ids = canonical_index.search(vec, k=3)

    best_match = canonical_layers_list[ids[0][0]]
    best_score = scores[0][0]

    if best_score >= threshold:
        return {
            'canonical': best_match,
            'confidence': best_score,
            'acao': 'AUTO-MAP',
            'nota': f"Layer '{layer_desconhecido}' → '{best_match}' (sim={best_score:.2f})"
        }
    else:
        return {
            'canonical': None,
            'confidence': best_score,
            'acao': 'REVISÃO HUMANA',
            'nota': f"Layer '{layer_desconhecido}' sem match claro (melhor: '{best_match}'={best_score:.2f})"
        }
```

### Arquivo a criar
`scripts/rag_layer_matcher.py` + índice `data/vectors/faiss/layers_canonicos.index`

---

## FRENTE H — Validação STOG/DXF antes de Gerar

### Problema
O STOG (LV DXF extractor + reconstructor) gera 249 vigas mas não verifica se
as dims reconstituídas fazem sentido vs o corpus histórico.

### Solução: Gate pré-STOG com RAG validation
```python
def pre_stog_validation_gate(obra_path: str) -> dict:
    """
    GATE obrigatório antes de gerar DXFs:
    1. Carrega elementos extraídos (JSON do Fase 3)
    2. Verifica cada elemento vs corpus RAG
    3. Retorna lista de elementos que BLOQUEIAM a geração
    4. Lista de elementos que passam com aviso
    5. Métricas gerais da obra
    """
    elementos = carregar_elementos_obra(obra_path)

    bloqueados = []
    avisos = []
    aprovados = []

    for elem in elementos:
        anomaly = calcular_anomaly_score(elem, ...)
        rag_plaus = rag_plausibility_check(elem, ...)
        range_ok = rag_range_check(elem)

        if anomaly > 0.85 or not range_ok['aprovado']:
            bloqueados.append({**elem, 'anomaly': anomaly, 'range_check': range_ok})
        elif anomaly > 0.60:
            avisos.append({**elem, 'anomaly': anomaly})
        else:
            aprovados.append(elem)

    return {
        'obra': obra_path,
        'total': len(elementos),
        'aprovados': len(aprovados),
        'avisos': len(avisos),
        'bloqueados': len(bloqueados),
        'gate_status': 'PASS' if len(bloqueados) == 0 else 'FAIL',
        'elementos_bloqueados': bloqueados,
    }
```

### Arquivo a criar
`scripts/rag_pre_stog_gate.py` — executado antes de qualquer geração DXF

---

## ROADMAP DE IMPLEMENTAÇÃO

### Sprint 1 — Fundação de Módulos (1-2 dias)
| # | Arquivo | Frente | Prioridade |
|---|---|---|---|
| S1-1 | `scripts/rag_plausibility.py` | A | CRÍTICO |
| S1-2 | `scripts/rag_validator.py` | B, D | CRÍTICO |
| S1-3 | `scripts/rag_anomaly_detector.py` | D | CRÍTICO |
| S1-4 | `scripts/rag_pre_stog_gate.py` | H | ALTO |

### Sprint 2 — Integração no Pipeline (2-3 dias)
| # | Ação | Frente | Prioridade |
|---|---|---|---|
| S2-1 | Integrar `rag_plausibility` no agente_estrutural.py | A | CRÍTICO |
| S2-2 | Integrar `rag_validator` na Fase 4 Transform | B | ALTO |
| S2-3 | Integrar `rag_pre_stog_gate` antes do STOG | H | ALTO |
| S2-4 | Integrar `rag_anomaly_detector` em sprint_e_production_gate.py | D | MÉDIO |

### Sprint 3 — Fichas e Atlas (1-2 dias)
| # | Arquivo | Frente | Prioridade |
|---|---|---|---|
| S3-1 | `scripts/gerar_fichas_v6.py` (+ seção RAG) | C | ALTO |
| S3-2 | `scripts/gerar_atlas_semantico.py` | F | MÉDIO |
| S3-3 | `scripts/rag_layer_matcher.py` + índice canônico | G | MÉDIO |

### Sprint 4 — CLI Avançado (1 dia)
| # | Expansão | Frente |
|---|---|---|
| S4-1 | `rag_query.py --find-element {id} --obra {obra}` | E |
| S4-2 | `rag_query.py --dims-report --tipo {tipo}` | E |
| S4-3 | `rag_query.py --anomalies --threshold {t}` | E, D |
| S4-4 | `rag_query.py --compare-obras {o1} {o2}` | E |

---

## ARQUITETURA DE MÓDULOS RAG

```
D:/Agente-cad-PYSIDE/
├── scripts/
│   ├── rag_ingestor.py         ✅ OPERACIONAL — popula FAISS
│   ├── rag_query.py            ✅ OPERACIONAL — CLI semântica
│   ├── rag_plausibility.py     📋 SPRINT 1 — confidence boost
│   ├── rag_validator.py        📋 SPRINT 1 — range validation
│   ├── rag_anomaly_detector.py 📋 SPRINT 1 — anomaly score
│   ├── rag_pre_stog_gate.py    📋 SPRINT 1 — gate pré-DXF
│   ├── rag_layer_matcher.py    📋 SPRINT 3 — layer semântico
│   └── gerar_fichas_v6.py      📋 SPRINT 3 — fichas + RAG
│
├── data/vectors/faiss/
│   ├── estruturais.index       ✅ 799 vetores
│   ├── pilares.index           ✅ 228 vetores
│   ├── vigas.index             ✅ 351 vetores
│   ├── lajes.index             ✅ 220 vetores
│   ├── layers_canonicos.index  📋 SPRINT 3 — 85 layers mapeados
│   ├── REGISTRY.json           ✅ metadata de ingestão
│   └── *_meta.json             ✅ side-cars por tipo
│
└── docs/
    ├── MASTERPLAN-RAG-VECTORIZACAO.md       ✅ stack técnica
    └── MASTERPLAN-RAG-INTEGRACAO-COMPLETA.md ✅ este documento
```

---

## INTERFACE PÚBLICA DO RAG (API Python)

Todos os módulos acima compartilham esta interface consistente:

```python
# rag_commons.py — módulo base importado por todos
from rag_commons import (
    load_model,          # → SentenceTransformer
    load_index,          # (tipo) → (faiss.Index, list[dict])
    normalize,           # (np.array) → np.array
    query,               # (text, tipo, obra, k, threshold) → list[Result]
    fmt_pilar,           # (id, data, obra, pav) → str
    fmt_viga,            # (id, data, obra, pav) → str
    fmt_laje,            # (id, data, obra, pav) → str
)

# Resultado padrão de query()
Result = {
    'score': float,      # 0.0-1.0 (cosine similarity)
    'meta': {
        'tipo': str,     # pilar | viga | laje
        'id': str,       # P17 | V5 | L3
        'obra': str,     # Obra_TREINO_1
        'pavimento': str,
        'arquivo_fonte': str,
        'dados': dict,   # dados originais do JSON
        'faiss_id': int,
    }
}
```

### Arquivo a criar
`scripts/rag_commons.py` — extrair funções compartilhadas de `rag_ingestor.py` + `rag_query.py`

---

## MÉTRICAS DE SUCESSO

| Métrica | Baseline Atual | Meta Sprint 1 | Meta Sprint 4 |
|---|---|---|---|
| % elementos validados pelo RAG | 0% | 100% | 100% |
| % revisão humana reduzida | 0% | 30% | 50% |
| Obras com anomalias detectadas | 0 | 11 (retroativo) | Toda obra nova |
| Fichas com contexto RAG | 0/798 | 0/798 | 798/798 |
| Layer aliases auto-mapeados | ~85 | ~85 | +N (firmas novas) |
| Tempo pré-gate STOG | ~0s | ~5s por obra | ~5s por obra |

---

## CRITÉRIOS DE DONE (por Frente)

| Frente | Done When |
|---|---|
| A — Confidence Boost | `rag_plausibility.py` importável + testes unitários passando |
| B — Range Validation | `rag_validator.py` com limites calibrados nas 11 obras |
| C — Fichas v6 | PDF gerado com seção "similares" para pelo menos 1 obra |
| D — Anomaly Detection | `sprint_e_production_gate.py` rejeitando elemento com anomaly > 0.85 |
| E — CLI Avançado | 4 subcomandos novos operacionais em `rag_query.py` |
| F — Atlas Semântico | Atlas com 5 clusters para pilares gerado e legível |
| G — Layer Matcher | `rag_layer_matcher.py` testado com layer desconhecido real |
| H — STOG Gate | `rag_pre_stog_gate.py` executado em Obra_TREINO_1 sem erros |

---

## PRÓXIMO PASSO IMEDIATO

**Sprint 1, Story 1:** Criar `scripts/rag_commons.py` — refactor dos módulos existentes
para base compartilhada, eliminando duplicação entre `rag_ingestor.py` e `rag_query.py`.

```bash
# Verificar estado atual
python scripts/rag_query.py --stats

# Após rag_commons.py criado, testar:
python -c "from rag_commons import load_model, query; print('OK')"
```

---

*MASTERPLAN-RAG-INTEGRACAO-COMPLETA v1.0*
*Athena (CEO-PLANEJAMENTO) | 2026-03-19*
*8 Frentes | 4 Sprints | 799 vetores base | 11 obras corpus*
