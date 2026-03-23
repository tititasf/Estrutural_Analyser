# MASTERPLAN — RAG & Vectorizacao CAD-ANALYZER

## Protocolo oficial de conhecimento estrutural vetorizado

| Campo         | Valor                                    |
|---------------|------------------------------------------|
| **Data**      | 2026-03-19                               |
| **Status**    | OPERACIONAL ✅ (2026-03-19 13:38)         |
| **Versao**    | 1.0                                      |
| **Autor**     | Claude (Athena/CEO-PLANEJAMENTO)         |
| **Projeto**   | CAD-ANALYZER (D:/Agente-cad-PYSIDE)      |

---

## 1. SITUACAO ATUAL (Diagnostico)

### Dependencias de Vetorizacao

| Componente             | Status | Detalhes                                                        |
|------------------------|--------|-----------------------------------------------------------------|
| **ChromaDB**           | ABANDONADO | Incompativel com Python 3.14 (dependencia pydantic v1 quebrada). Diretorio `data/vectors/chromadb/` existe mas permanece vazio. |
| **FAISS**              | OPERACIONAL | numpy 2.4.3 compativel. FlatIP com normalizacao L2 para cosine similarity. |
| **sentence-transformers** | OPERACIONAL | v5.2.3, modelo `all-MiniLM-L6-v2` (384 dimensoes), execucao 100% local sem API externa. |

### Dados Disponiveis

| Metrica                        | Valor   |
|--------------------------------|---------|
| Obras com ground truth         | 11      |
| Total de pilares catalogados   | 228     |
| Total de vigas catalogadas     | 351     |
| Total de lajes catalogadas     | 220     |
| **Total de elementos**         | **799** |
| **Índices FAISS gerados**      | **4** (estruturais + pilares + vigas + lajes) |

### Decisao Arquitetural

ChromaDB foi definitivamente abandonado apos falhas repetidas de compatibilidade com Python 3.14 (pydantic v1 nao compila). FAISS foi escolhido como substituto por ser:

- Dependencia unica (numpy), sem cadeia de sub-dependencias frageis
- Performance superior para busca em datasets de ate ~100K vetores
- Compatibilidade total com Python 3.12+ e 3.14

---

## 2. ARQUITETURA DO SISTEMA RAG

### Stack Tecnica

```
                        +------------------------+
                        |   sentence-transformers |
                        |   all-MiniLM-L6-v2     |
                        |   384 dims, local      |
                        +----------+-------------+
                                   |
                         texto --> embedding
                                   |
                        +----------v-------------+
                        |       FAISS FlatIP      |
                        |  (cosine via norm L2)   |
                        +----------+-------------+
                                   |
                        +----------v-------------+
                        |   JSON side-car         |
                        |   (metadata estruturada)|
                        +------------------------+
```

| Camada       | Tecnologia                      | Especificacao                                    |
|--------------|----------------------------------|--------------------------------------------------|
| Embedding    | sentence-transformers            | Modelo: `all-MiniLM-L6-v2`, 384 dimensoes, local |
| Vector DB    | FAISS FlatIP                     | Cosine similarity via normalizacao L2 pre-insert  |
| Metadata     | JSON side-car                    | Um `.json` para cada `.index`, pareado por nome   |
| Storage      | Sistema de arquivos local        | `D:/Agente-cad-PYSIDE/data/vectors/faiss/`        |

### Arquivos do Sistema

Todos os arquivos residem em `D:/Agente-cad-PYSIDE/data/vectors/faiss/`:

| Arquivo                  | Tipo        | Descricao                                        |
|--------------------------|-------------|--------------------------------------------------|
| `estruturais.index`      | FAISS index | Indice unificado com todos os elementos           |
| `estruturais_meta.json`  | JSON        | Metadata de cada vetor no indice unificado        |
| `pilares.index`          | FAISS index | Indice segregado — somente pilares                |
| `pilares_meta.json`      | JSON        | Metadata dos vetores de pilares                   |
| `vigas.index`            | FAISS index | Indice segregado — somente vigas                  |
| `vigas_meta.json`        | JSON        | Metadata dos vetores de vigas                     |
| `lajes.index`            | FAISS index | Indice segregado — somente lajes                  |
| `lajes_meta.json`        | JSON        | Metadata dos vetores de lajes                     |
| `REGISTRY.json`          | JSON        | Registro de ingestao: obras, datas, contagens     |

### Relacao entre Index e Metadata

Cada posicao `i` no FAISS index corresponde a posicao `i` no array do JSON side-car. A metadata contem:

```json
{
  "id": "P11_Obra_TREINO_1_1_PAV",
  "tipo": "pilar",
  "nome": "P11",
  "obra": "Obra_TREINO_1",
  "pavimento": "1_PAV",
  "b_cm": 46,
  "h_cm": 56,
  "confidence": 0.9,
  "source": "engenharia-reversa-ezdxf",
  "faces": ["A", "B", "C", "D"],
  "layers": [],
  "nota": "",
  "ingested_at": "2026-03-19T00:00:00Z"
}
```

---

## 3. FORMATO DO DOCUMENTO (o que e embedado)

Para cada elemento estrutural, o texto que alimenta o embedding model segue o template:

```
"{tipo} {id}, Obra: {obra}, Pav: {pav}, b={b}cm h={h}cm, comprimento={comp}cm,
confidence={conf}, source={source}, layers={layers}, faces={faces}, nota={nota}"
```

### Exemplos Reais

**Pilar:**
```
Pilar P11, Obra: Obra_TREINO_1, Pav: 1_PAV, b=46cm h=56cm, confidence=0.9,
source=engenharia-reversa-ezdxf, faces=A B C D
```

**Viga:**
```
Viga V10, Obra: Obra_TREINO_1, Pav: 1_PAV, b=15cm h=40cm, comprimento=520cm,
confidence=0.85, source=engenharia-reversa-ezdxf, faces=A B
```

**Laje:**
```
Laje L1, Obra: Obra_TREINO_1, Pav: 1_PAV, h=12cm, confidence=0.75,
source=engenharia-reversa-ezdxf, nota=laje macica
```

### Campos do Template

| Campo        | Obrigatorio | Descricao                                                     |
|-------------|-------------|---------------------------------------------------------------|
| `tipo`      | Sim         | pilar, viga, laje                                              |
| `id`        | Sim         | Identificador unico (P11, V10, L1...)                         |
| `obra`      | Sim         | Nome da obra (Obra_TREINO_1, Obra_TREINO_21...)               |
| `pav`       | Sim         | Pavimento (1_PAV, 12_PAV, TERREO...)                          |
| `b`         | Se existe   | Largura da secao em cm                                         |
| `h`         | Se existe   | Altura da secao em cm                                          |
| `comprimento` | Se existe | Comprimento do elemento em cm                                 |
| `confidence` | Sim        | Score de confianca da extracao (0.0 a 1.0)                    |
| `source`    | Sim         | Metodo de extracao (engenharia-reversa-ezdxf, ground-truth...) |
| `layers`    | Opcional    | Layers DXF de origem                                           |
| `faces`     | Opcional    | Faces identificadas (A, B, C, D para pilares)                 |
| `nota`      | Opcional    | Observacoes adicionais                                         |

---

## 4. DADOS REGISTRADOS (11 obras com ground truth)

| #  | Obra            | Pilares | Vigas | Lajes | Status Ingestao |
|----|-----------------|---------|-------|-------|-----------------|
| 1  | Obra_TREINO_1   | 40      | 33    | 19    | Pronto          |
| 2  | Obra_TREINO_3   | 18      | 28    | 15    | Pronto          |
| 3  | Obra_TREINO_5   | 22      | 35    | 20    | Pronto          |
| 4  | Obra_TREINO_6   | 15      | 24    | 18    | Pronto          |
| 5  | Obra_TREINO_8   | 25      | 38    | 22    | Pronto          |
| 6  | Obra_TREINO_9   | 20      | 30    | 21    | Pronto          |
| 7  | Obra_TREINO_10  | 19      | 32    | 17    | Pronto          |
| 8  | Obra_TREINO_11  | 24      | 36    | 23    | Pronto          |
| 9  | Obra_TREINO_13  | 16      | 27    | 19    | Pronto          |
| 10 | Obra_TREINO_14  | 12      | 31    | 24    | Pronto          |
| 11 | Obra_TREINO_21  | 17      | 37    | 21    | Pronto          |
|    | **TOTAL**       | **228** | **351** | **219** | **798 elementos** |

### Obras Adicionais (sem ground truth completo — pendentes)

As seguintes obras estao presentes em `DADOS-OBRAS/` mas ainda nao possuem ground truth validado para ingestao RAG:

- Obra_TREINO_12, Obra_TREINO_15, Obra_TREINO_16, Obra_TREINO_17
- Obra_TREINO_18, Obra_TREINO_19, Obra_TREINO_20
- Obra_TREINO_22, Obra_TREINO_23
- OBRA-TESTE1, OBRA_FORMATO_EXEMPLO

---

## 5. COMO USAR O RAG

### 5.1 Ingesta (Popular o FAISS)

```bash
# Popular FAISS com todas as 11 obras com ground truth
python scripts/rag_ingestor.py

# Popular apenas uma obra especifica
python scripts/rag_ingestor.py --obra Obra_TREINO_21

# Rebuild completo (apaga indices existentes e repopula)
python scripts/rag_ingestor.py --rebuild
```

**O que o ingestor faz:**
1. Le os arquivos de ground truth de cada obra
2. Gera o texto de embedding por elemento (formato da Secao 3)
3. Codifica com `all-MiniLM-L6-v2` (384 dims)
4. Normaliza L2 para uso com FAISS FlatIP (cosine similarity)
5. Insere no indice unificado (`estruturais.index`) e nos segregados por tipo
6. Atualiza `REGISTRY.json` com contagens e timestamps

### 5.2 Query (Consultar o RAG)

```bash
# Busca semantica generica
python scripts/rag_query.py "como extrair dimensao de pilar cambotado"

# Busca filtrada por tipo com k resultados
python scripts/rag_query.py "viga em balanco sem apoio_fim" --tipo viga --k 5

# Busca com filtro por obra
python scripts/rag_query.py "pilar com secao irregular" --obra Obra_TREINO_1 --k 10

# Estatisticas dos indices
python scripts/rag_query.py --stats
```

**Saida da query:**
```
Query: "pilar com alta confidence sem dimensao"
Top 5 resultados (cosine similarity):

  1. [0.87] Pilar P11, Obra: Obra_TREINO_1, Pav: 1_PAV, b=46cm h=56cm, confidence=0.9
  2. [0.84] Pilar P3, Obra: Obra_TREINO_21, Pav: 12_PAV, b=20cm h=40cm, confidence=0.92
  3. [0.81] Pilar P7, Obra: Obra_TREINO_5, Pav: TERREO, b=30cm h=30cm, confidence=0.88
  4. [0.79] Pilar P22, Obra: Obra_TREINO_8, Pav: 3_PAV, b=null h=null, confidence=0.6
  5. [0.76] Pilar P15, Obra: Obra_TREINO_11, Pav: 2_PAV, b=25cm h=50cm, confidence=0.85
```

### 5.3 API Python (Uso programatico)

```python
from scripts.rag_query import RAGQuery

# Instanciar
rag = RAGQuery()

# Busca semantica simples
results = rag.search("pilar com alta confidence sem dimensao", k=5)

# Busca filtrada por tipo
results = rag.search("viga curta alta resistencia", k=10, tipo="viga")

# Busca filtrada por obra
results = rag.search("laje macica espessa", k=3, obra="Obra_TREINO_1")

# Iterar resultados
for r in results:
    print(f"[{r.score:.2f}] {r.text}")
    print(f"  Metadata: {r.metadata}")
```

### 5.4 Integracao com Pipeline E2E

O RAG pode ser consultado durante qualquer fase do pipeline CAD-ANALYZER:

```python
# Fase 3 - Comparar elemento extraido com ground truth similar
from scripts.rag_query import RAGQuery

rag = RAGQuery()

# Dado um pilar recem-extraido, buscar similares no ground truth
query = f"Pilar {pilar.id}, b={pilar.b}cm h={pilar.h}cm"
similares = rag.search(query, k=3, tipo="pilar")

# Usar resultados para validacao cruzada
for s in similares:
    if s.score > 0.9:
        print(f"Alta similaridade com {s.metadata['nome']} de {s.metadata['obra']}")
```

---

## 6. PROTOCOLO DE MANUTENCAO

### Ingestao Incremental

| Evento                          | Comando                                         | Descricao                                    |
|---------------------------------|--------------------------------------------------|----------------------------------------------|
| Nova obra processada            | `python scripts/rag_ingestor.py --obra {nome}`  | Adiciona obra aos indices existentes          |
| Ground truth atualizado         | `python scripts/rag_ingestor.py --rebuild`       | Reconstroi todos os indices do zero           |
| Verificacao de integridade      | `python scripts/rag_query.py --stats`            | Mostra contagens por indice vs REGISTRY.json  |

### Ciclo de Vida dos Indices

```
Ground Truth atualizado
        |
        v
rag_ingestor.py --rebuild
        |
        v
Indices FAISS recriados
        |
        v
REGISTRY.json atualizado
        |
        v
rag_query.py --stats (verificacao)
```

### Regras de Manutencao

1. **Nunca editar manualmente** os arquivos `.index` — sao binarios FAISS
2. **Sempre manter pareamento** entre `.index` e `_meta.json` — ingestor garante isso
3. **REGISTRY.json** e a fonte da verdade sobre quais obras foram ingeridas e quando
4. **Backup antes de rebuild:** copiar `data/vectors/faiss/` antes de `--rebuild`
5. **Validacao pos-ingestao:** rodar `--stats` e comparar contagens com ground truth conhecido

---

## 7. GAPS REMANESCENTES

### Gap 1 — Dimensoes de Vigas (CRITICO)

| Item            | Estado                                                        |
|-----------------|---------------------------------------------------------------|
| **Problema**    | Maioria das vigas no ground truth tem `b=null` e `h=null`     |
| **Impacto**     | Busca semantica por dimensoes de vigas retorna poucos matches |
| **Causa raiz**  | Extracao dimensional de vigas e mais complexa que pilares     |
| **Solucao**     | Script de extracao semi-automatica de vigas dos DXFs STOG gerados |
| **Prioridade**  | ALTA                                                          |

### Gap 2 — Coordenadas de Lajes (MEDIO)

| Item            | Estado                                                        |
|-----------------|---------------------------------------------------------------|
| **Problema**    | Muitas lajes tem `coordenadas=[]` (array vazio)               |
| **Impacto**     | Impossivel reconstruir contorno geometrico via RAG             |
| **Causa raiz**  | Contornos de lajes sao inferidos, nao explicitamente extraidos |
| **Solucao**     | Script de extracao de contornos de lajes dos DXFs STOG        |
| **Prioridade**  | MEDIA                                                         |

### Gap 3 — Obras sem Ground Truth (BAIXO)

| Item            | Estado                                                        |
|-----------------|---------------------------------------------------------------|
| **Problema**    | 11 obras adicionais em DADOS-OBRAS sem ground truth validado  |
| **Impacto**     | Dataset limitado para treinamento e validacao cruzada          |
| **Causa raiz**  | Ground truth requer validacao manual por engenheiro            |
| **Solucao**     | Pipeline semi-automatico: extrair + revisar + validar          |
| **Prioridade**  | BAIXA (dataset atual de 798 elementos e suficiente para MVP)  |

### Plano de Resolucao

```
Gap 1 (Vigas dims)    → Sprint 6, Story CAD-RAG-1
Gap 2 (Lajes coords)  → Sprint 6, Story CAD-RAG-2
Gap 3 (Mais obras)     → Sprint 7+ (conforme demanda)
```

---

## 8. HISTORICO

| Data       | Evento                                                                 |
|------------|------------------------------------------------------------------------|
| 2026-01-21 | Diretorios `data/vectors/chromadb/` e `data/vectors/faiss/` criados    |
| 2026-02-07 | Tentativa ChromaDB — falha pydantic v1 vs Python 3.14                  |
| 2026-03-08 | MASTERPLAN v4.0 consolida pipeline E2E (Epics 5-7 concluidos)          |
| 2026-03-19 | Decisao DEFINITIVA: ChromaDB ABANDONADO, FAISS como unico vector store |
| 2026-03-19 | Sistema RAG implementado por Claude (Athena/CEO-PLANEJAMENTO)          |
| 2026-03-19 | Ingestor (`dxf_ingestor.py`) integrado ao pipeline de vetorizacao      |
| 2026-03-19 | Este MASTERPLAN criado como protocolo oficial                          |

### Motivacao

ChromaDB nunca foi efetivamente populado apesar de multiplas solicitacoes ao longo de semanas.
A causa raiz era a incompatibilidade fundamental entre pydantic v1 (requerido pelo ChromaDB) e
Python 3.14 (runtime do projeto). Em vez de fazer downgrade do Python ou manter workarounds
frageis, a decisao estrategica foi migrar para FAISS — uma biblioteca mais simples, mais rapida,
e com dependencia minima (apenas numpy).

**Esta e a implementacao DEFINITIVA e PROTOCOLADA.**

---

## 9. REFERENCIA CRUZADA

| Documento                        | Relacao                                            |
|----------------------------------|----------------------------------------------------|
| `MASTERPLAN-CAD-ANALYZER-v4.0.md` | Pipeline E2E que alimenta o RAG                   |
| `src/core/vectorization/dxf_ingestor.py` | Modulo de ingestao DXF do pipeline         |
| `tests/core/phase3/ground_truth.json` | Exemplo de ground truth unitario              |
| `DADOS-OBRAS/`                   | Diretorio raiz com todas as obras de treinamento   |
| `Output_E2E_AllObras/`           | Saida do pipeline E2E (DXFs gerados)               |
| `data/vectors/faiss/`            | Diretorio dos indices FAISS                        |

---

*Documento protocolado em 2026-03-19 por Morgan (PM/Strategist) com dados consolidados pela equipe CAD-ANALYZER.*
