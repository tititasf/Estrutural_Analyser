# FICHA DE COMPREENSÃO — CRANE (Robô de Vigas)

**Sistema:** CAD-ANALYZER v2.0
**Robô:** Crane — Especialista em Vigas Laterais (Beam Robot)
**Responsável:** Fase 5 do Pipeline CAD-ANALYZER
**Versão do Documento:** 1.0 | 2026-03-18

---

## 1. IDENTIDADE DO ROBÔ

| Atributo | Valor |
|----------|-------|
| **Nome** | Crane |
| **Função** | Geração automática de DXF de formas de viga (faces laterais) |
| **Escopo** | Vigas de concreto armado — face A e face B, seção transversal, garfos/grade |
| **Norma** | NBR 14931 (concretagem), NBR 7190 (madeira), NBR 6118 (concreto) |
| **Arquivo de Config** | `_ROBOS_ABAS/Robo_Laterais_de_Vigas/config.json` |

---

## 2. O QUE CRANE PROCESSA

### Entrada (INPUT)

Crane recebe uma **ficha de viga** com os seguintes campos:

```
Viga_name          — Nome da viga (ex: V32b, V1A, V-2)
Viga_dim           — Dimensão da seção (ex: 19/53, 25/58, d=12)
Viga_viga_segs     — Fonte das linhas (Polyline — único valor conhecido)
Viga_viga_a_seg_1_ini_name  — Nome do segmento inicial da face A
Viga_viga_a_seg_1_comprimento_total — Comprimento total do segmento
Viga_id_item       — Identificador interno da viga
```

### Processamento (ENGINE)

Crane processa **faces laterais** — as vistas externas da forma de viga:

1. **Parsing da geometria**: Extrai face_a e face_b do DXF de entrada
2. **Cálculo do comprimento**: Mede o trecho de viga por segmento
3. **Posicionamento de sarrafos**: Calcula sarrafos verticais e horizontais por espessura
4. **Posicionamento de garfos**: Distribui garfos (forcadores) ao longo da viga
5. **Seção transversal**: Gera a seção com largura × altura da viga
6. **Grade de verificação**: Adiciona marcação de cotas e checagem
7. **Exportação**: Combina todas as vistas num DXF unificado por pavimento

### Saída (OUTPUT)

```
laterais_{obra}_{pavimento}.dxf  — DXF com formas laterais de todas as vigas
combined_{obra}_{pavimento}.dxf  — DXF combinado com layout em grid (CELL_W=2900 × CELL_H=1800)
```

---

## 3. LAYERS CAPTURADOS (15 CAMADAS)

| Layer | Conteúdo | Prioridade |
|-------|----------|------------|
| `Painéis` | Face lateral em compensado | CRÍTICA |
| `CONCRETO` | Projeção do concreto da viga | CRÍTICA |
| `Madeira` | Elementos de madeira (sarrafos, berços) | CRÍTICA |
| `SARR_2.2x10`, `SARR_2.2x7` | Sarrafos 2,2cm × 10cm / 7cm | ALTA |
| `SARR_3.5x10`, `SARR_3.5x7` | Sarrafos 3,5cm × 10cm / 7cm | ALTA |
| `SARR_EDITAR` | Sarrafos para edição manual | ALTA |
| `COTA`, `Cotas` | Cotas de dimensão | MÉDIA |
| `GARFOS` | Garfos/forcadores de face | ALTA |
| `TENSOR` | Tirantes de aço (cabos) | ALTA |
| `detalhes` | Linhas de detalhe técnico | MÉDIA |
| `SCO-___-LAJ` | Delimitação de laje adjacente | MÉDIA |
| `0` (default) | Entidades sem layer específica | ALTA (capturar) |
| `barrote` | Barrote de sustentação | MÉDIA |
| `presilha` | Presilhas de fixação | BAIXA |
| `HACHURA MADEIRAS` | Hachuramento de perfis | BAIXA |

### ⚠️ Layers Críticos Frequentemente Perdidos

Os layers **`0`** (default), **`TENSOR`** e **`barrote`** frequentemente contém
elementos visuais importantes que não são capturados pelo extrator principal.
O **patch_extra_layers.py** foi criado especificamente para recuperar esses elementos.

---

## 4. ANATOMIA DE UMA VIGA NO DXF

```
┌─────────────────────────────────────────────────────────────────────┐
│  UMA VIGA (ex: V32b, 19/53) NO DXF APARECE COMO:                   │
│                                                                     │
│  FACE_A (vista lateral esquerda):                                   │
│  ┌──────────────────────────────────────────────┐                  │
│  │ LWPOLYLINE (layer=Painéis) — face frontal    │                  │
│  │ LINE entities (layer=Madeira) — sarrafos      │                  │
│  │ LINE entities (layer=GARFOS) — garfos         │                  │
│  │ LINE entities (layer=TENSOR) — tirantes       │                  │
│  │ LINE entities (layer=0) — linhas extras        │                  │
│  └──────────────────────────────────────────────┘                  │
│                                                                     │
│  SEÇÃO TRANSVERSAL:                                                 │
│  ┌──────┐ ← largura (19cm)                                          │
│  │      │   altura (53cm)                                           │
│  │      │ ← LWPOLYLINE fechada (layer=CONCRETO)                     │
│  └──────┘                                                           │
│                                                                     │
│  FACE_B (vista lateral direita):                                    │
│  Mesmos elementos que face_A, espelhados                            │
│                                                                     │
│  GRADE/GARFOS:                                                      │
│  Distribuição dos pontos de fixação ao longo do comprimento         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. GRID DE COMBINAÇÃO (combined_vXX.dxf)

O arquivo `combined_vXX.dxf` organiza TODAS as vigas em um grid fixo:

```
CELL_W = 2900  (largura de cada célula em unidades DXF)
CELL_H = 1800  (altura de cada célula)
MARGIN = 80    (margem interna)
COLS   = 12    (colunas por linha)
ROWS   = ceil(n_vigas / COLS)

Layout de cada célula:
  ┌─────────────────────────────────────┐
  │ [LABEL: V32b]                       │  ← LABEL_ID layer
  │ ┌───────────────────────┐           │
  │ │      FACE_A           │           │  ← face principal
  │ └───────────────────────┘           │
  │ [SEÇÃO]  [FACE_B]  [GARFOS]        │  ← elementos secundários
  └─────────────────────────────────────┘
```

**Problema frequente:** Elementos "soltos" no AutoCAD — ocorre quando ox/oy
calculado pelo `compute_content_bbox()` posiciona face_A corretamente mas
outros elementos usam coordenadas absolutas do DXF original.

**Solução aplicada (v51+):** Detecção de clusters via Union-Find com EPS=350u
e validação de Y-overlap >= 30%.

---

## 6. MODELO DE DADOS (SQLITE)

### Tabela `beams` em `project_data.vision`

```sql
id               TEXT  PRIMARY KEY
project_id       TEXT  — FK para projects
name             TEXT  — Nome da viga (V32b, V1A...)
data_json        TEXT  — Dados completos da viga (geometria + params)
sides_data_json  TEXT  — Dados de cada face (face_a, face_b, secao)
links_json       TEXT  — Conexões com pilares/lajes adjacentes
validated_fields_json  TEXT  — Campos validados pelo usuário
na_fields_json   TEXT  — Campos N/A
issues_json      TEXT  — Problemas detectados
is_validated     BOOLEAN
pkl_path         TEXT  — Cache serializado
```

**Total de vigas no banco:** 7.005

---

## 7. REGRAS DE TRANSFORMAÇÃO (Crane)

| Campo | Acurácia Global | Status | Observação |
|-------|-----------------|--------|------------|
| Viga_viga_segs | **100%** | ✅ PRODUÇÃO | Sempre "Polyline" — trivial |
| Viga_dim | 46.4% | ⚠️ BAIXA | 6 valores únicos: 19/53, d=12, d=15, 19/58, 25/58, 19/50 |
| Viga_name | 32.3% | ⚠️ BAIXA | 9 valores únicos — projeto-específico |
| Viga_viga_a_seg_1_ini_name | 50.0% | ⚠️ MÉDIA | Apenas 4 eventos de treino |

### Análise de Acurácia por Campo

**Viga_viga_segs (100%):** O tipo de segmento é SEMPRE "Polyline".
Esta regra funciona como classificador binário trivial.

**Viga_dim (46.4%):** 19/53 é a dimensão mais comum (13/28 eventos = 46.4%).
A distribuição real é: 19/53 (46%), 19/58 (11%), 25/58 (11%), 19/50 (7%), d=12 (18%), d=15 (7%).
O global_default "19/53" está correto para ~46% dos casos.

**Viga_name (32.3%):** Os nomes dependem totalmente do projeto.
O global_default "V1a" só é correto em 32% dos casos.
→ **Este campo SEMPRE requer validação humana.**

---

## 8. PIPELINE DE EXECUÇÃO DO CRANE

```
DXF de Entrada (por pavimento)
    ↓
[1] DXFIngestor
    → Detecta familia DXF (TQS tem layers numéricos)
    → Extrai: Painéis, CONCRETO, Madeira, SARR_*, GARFOS, TENSOR, '0', barrote
    → patch_extra_layers.py: recupera layers '0', TENSOR, barrote não capturados
    ↓
[2] StructuralVectorizer
    → Classifica vigas por aspect_ratio > 2.5 (horizontal)
    → Agrupa face_a + face_b + seção + grade por proximidade
    → Gera FeatureVector + DNA key
    ↓
[3] TransformationEngine
    → Prediz: name, dim, viga_segs, segmentos
    → global_default como fallback
    ↓
[4] REVISÃO HUMANA (Serra + Mestre)
    → Confirma nome, dimensão, segmentos
    → training_events registrados → melhora regras futuras
    ↓
[5] Crane gera DXF de formas
    → Sarrafos verticais/horizontais por espessura de painel
    → Garfos distribuídos por comprimento
    → Cotas automáticas
    ↓
[6] combinar_vigas_dxf.py
    → Layout em grid CELL_W×CELL_H
    → clip de linhas na borda da célula
    → combined_v{N}.dxf exportado
```

---

## 9. PROBLEMAS CONHECIDOS

| Problema | Causa | Solução |
|----------|-------|---------|
| Elementos soltos no AutoCAD | ox/oy não alinha todos os layers | Union-Find clustering (EPS=350) |
| Layer '0' não capturado | Extrator principal usava whitelist | Abordagem BLACKLIST em patch_extra_layers.py |
| TENSOR ausente em vigas protendidas | Layer TENSOR não estava na lista | Adicionado à captura extra_layers |
| MemoryError em DXF grande (STOG-NURBAN) | 12 vigas + DXF grande | try/except MemoryError + skip com aviso |
| Matplotlib mostra 0 problemas, AutoCAD mostra soltos | Centroid-based não detecta grupos dispersos | detect_clusters_real.py com Union-Find |

---

## 10. MÉTRICAS DE PERFORMANCE (2026-03-18)

```
Total de vigas no banco:    7.005
Vigas em combined_v51.dxf:  248 (grid 21×12)
training_events (Viga):     141 eventos
Regras de transformação:    4 regras (1 em produção)
Acurácia média das regras:  57.2%
Layers capturados:          15 camadas
Vigas com extra_entities:   217 de 248 (87.5%)
```

---

*Ficha técnica Crane v1.0 | CAD-ANALYZER | Diana Corporação Senciente*
*Gerada automaticamente em 2026-03-18 | Revisar a cada evolução de versão*
