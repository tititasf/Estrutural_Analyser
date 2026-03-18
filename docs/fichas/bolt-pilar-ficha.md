# FICHA DE COMPREENSÃO — BOLT (Robô de Pilares)

**Sistema:** CAD-ANALYZER v2.0
**Robô:** Bolt — Especialista em Pilares (Pilar Robot)
**Responsável:** Fase 5 do Pipeline CAD-ANALYZER
**Versão do Documento:** 1.0 | 2026-03-18

---

## 1. IDENTIDADE DO ROBÔ

| Atributo | Valor |
|----------|-------|
| **Nome** | Bolt |
| **Função** | Geração automatica de DXF de formas de pilar |
| **Escopo** | Pilares de concreto armado — seção quadrada/retangular |
| **Norma** | NBR 7190 (madeira), NBR 14931 (concretagem), NBR 6118 (concreto) |
| **Arquivo de Config** | `_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/config/config_abcd.json` |

---

## 2. O QUE BOLT PROCESSA

### Entrada (INPUT)

Bolt recebe uma **ficha de pilar** com os seguintes campos obrigatórios:

```
Pilar_name        — Nome do pilar (ex: P1, P32A)
Pilar_dim         — Dimensão da seção (ex: (19x229), (30x188))
Pilar_pilar_segs  — Fonte das linhas (Entidade CAD | Geometria Automática)
Pilar_p_sA_l1_n   — Nome da laje lado A, nível 1 (ex: L26)
Pilar_p_sA_l1_h   — Altura da laje lado A, nível 1 (ex: 15cm)
Pilar_p_sA_l2_n   — Nome da laje lado A, nível 2 (ex: L31)
Pilar_p_sA_l2_h   — Altura da laje lado A, nível 2
Pilar_p_sB_l1_n   — Nome da laje lado B, nível 1 (ex: L30)
Pilar_p_sB_l1_h   — Altura da laje lado B, nível 1
```

### Processamento (ENGINE)

Bolt usa o **StructuralVectorizer** + **TransformationEngine** para:

1. **Leitura de geometria**: Extrai contornos do pilar do DXF de entrada (layer CONCRETO ou 0)
2. **Detecção de template**: Verifica qual template ABCD usar (Padrão, ROCONTEC, PATRIARCA, UNI5, NOVA, INIFORMAS, INIFORMAS2, INI)
3. **Cálculo de painéis**: Determina quantos painéis (compensado resinado) envolvem o pilar
4. **Posicionamento de sarrafos**: Calcula espaçamento de sarrafos (AB e CDEFGH) por dimensão
5. **Geração de DXF**: Desenha a forma completa com todas as views (frontal, seção transversal, corte)

### Saída (OUTPUT)

```
pilares_{obra}_{pavimento}.dxf  — DXF com todas as formas de pilar do pavimento
```

Camadas geradas no DXF de saída:
- `Painéis` — Faces de compensado (vermelho/branco por reaproveitamento)
- `CONCRETO` — Projeção do concreto do pilar
- `COTA` / `COTA_H` — Cotas de dimensão
- `Madeira` — Elementos de madeira (berços, cunhas)
- `HACHURA MADEIRAS` — Hachuramento dos perfis de madeira
- `NOMENCLATURA` — Identificação do pilar e número da forma

---

## 3. TEMPLATES ABCD (8 VARIANTES)

| Template | Parafuso | Linha | Usado Por |
|----------|----------|-------|-----------|
| **Padrão (2)** | PAR_ESQ | PLINE | Maioria das obras |
| **ROCONTEC** | PAR_DIRV | MLINE | Obras Rocontec |
| **PATRIARCA** | PAR_ESQ | PLINE | Obras Patriarca |
| **UNI5** | PAR_ESQ | PLINE | Sistema UNI5 |
| **NOVA** | PAR_ESQ (parafuso-only) | PLINE | Novo formato |
| **INIFORMAS** | INI_PAR | MLINE | Sistema Iniformas |
| **INIFORMAS2** | INI_PAR2 | MLINE | Variante Iniformas |
| **INI** | INI_PAR (parafuso-only) | PLINE | Formato INI |

### Dimensões Padrão por Template

```
altura_h1:      Altura total da forma (cm)
max_altura_ab:  Altura máxima do painel AB
max_altura_cd:  Altura máxima do painel CD
max_largura_ab: Largura máxima do painel AB
max_largura_cd: Largura máxima do painel CD
min_abertura_normal:   Abertura mínima normal
min_abertura_pequena:  Abertura mínima para pilares pequenos
```

---

## 4. MODELO DE DADOS (SQLITE)

### Tabela `pillars` em `project_data.vision`

```sql
id               TEXT  PRIMARY KEY
project_id       TEXT  — FK para projects
name             TEXT  — Nome do pilar (P1, P32A...)
type             TEXT  — Tipo de seção
area             REAL  — Área da seção (mm²)
points_json      TEXT  — Vértices do polígono de seção
sides_data_json  TEXT  — Dados de cada face (AB, CD)
links_json       TEXT  — Conexões com vigas/lajes adjacentes
conf_map_json    TEXT  — Mapa de confiança por campo
validated_fields_json  TEXT  — Campos validados pelo usuário
na_fields_json   TEXT  — Campos marcados como N/A
issues_json      TEXT  — Problemas detectados
is_validated     BOOLEAN
pkl_path         TEXT  — Cache serializado
```

### Regras de Transformação Ativas (Bolt)

| Campo | Acurácia | Status | Tipo |
|-------|----------|--------|------|
| Pilar_pilar_segs | 85.4% | ✅ PRODUÇÃO | Classificação (Entidade CAD vs Geometria) |
| Pilar_name | 32.8% | ⚠️ BAIXA | Nome (projeto-específico, difícil generalizar) |
| Pilar_dim | 29.1% | ⚠️ BAIXA | Dimensão (muitas variantes por projeto) |
| Pilar_p_sA_l1_n | 100% | ✅ PRODUÇÃO | Nome da laje (único valor no dataset) |
| Pilar_p_sA_l1_h | 100% | ✅ PRODUÇÃO | Altura da laje (único valor) |
| Pilar_p_sA_l2_n | 100% | ✅ PRODUÇÃO | Nome da laje (único valor) |
| Pilar_p_sA_l2_h | 100% | ✅ PRODUÇÃO | Altura da laje (único valor) |
| Pilar_p_sB_l1_n | 100% | ✅ PRODUÇÃO | Nome da laje (único valor) |
| Pilar_p_sB_l1_h | 100% | ✅ PRODUÇÃO | Altura da laje (único valor) |

**Nota sobre Pilar_name e Pilar_dim:** A acurácia baixa se deve ao fato de que os nomes de pilares são
específicos de cada projeto. Bolt depende da validação humana (Serra + Mestre) para esses campos.

---

## 5. SEMÂNTICA — O QUE É UM PILAR NO DXF

```
┌─────────────────────────────────────────────────────┐
│  O pilar no DXF aparece como:                       │
│                                                     │
│  1. POLILINHA FECHADA no layer CONCRETO ou '0'      │
│     → Contorno da seção transversal                 │
│     → Normalmente retangular (30x188mm, 19x229mm)   │
│                                                     │
│  2. TEXTO próximo com nome "P{N}" e dimensão        │
│     → P1 ou P1(19x229) ou P32A                      │
│     → Layer: NOMENCLATURA, TEXTO ou '0'             │
│                                                     │
│  3. HACHURA ou SOLID no interior                    │
│     → Indica área de concreto (família TQS)         │
│                                                     │
│  IDENTIFICAÇÃO AUTOMÁTICA:                          │
│    - bbox quadrada ou levemente retangular           │
│    - área ~500 a 5000 mm²                           │
│    - aspect_ratio < 3.0                             │
│    - texto próximo começa com "P"                   │
└─────────────────────────────────────────────────────┘
```

---

## 6. PIPELINE DE EXECUÇÃO DO BOLT

```
DXF de Entrada
    ↓
[1] DXFIngestor
    → Detecta familia (TQS/BIM)
    → Extrai RawEntity (polylines, textos)
    ↓
[2] StructuralVectorizer
    → Classifica: Pilar (aspect_ratio < 3, bbox fechada)
    → Gera FeatureVector 8-dim
    → DNA key: "area,0,n_verts,1.0,layer_hash,0,0,1"
    ↓
[3] TransformationEngine (transformation_rules lookup)
    → Prediz: name, dim, pilar_segs
    → Se DNA match: usa dna_frequency_map (alta precisão)
    → Se sem match: usa global_default (fallback)
    ↓
[4] REVISÃO HUMANA (Serra + Mestre)
    → Valida nome, dimensão, lajes adjacentes
    → Registra em training_events (melhora futuras regras)
    ↓
[5] Bolt gera DXF de forma
    → Seleciona template ABCD correto
    → Calcula painéis, sarrafos, cotas
    → Exporta DXF final
```

---

## 7. PROBLEMAS CONHECIDOS E LIMITAÇÕES

| Problema | Causa | Mitigação |
|----------|-------|-----------|
| Pilar_name acurácia 32.8% | Nomes são projeto-específicos | Validação humana obrigatória |
| Pilar_dim acurácia 29.1% | Muitas dimensões diferentes | TransformationEngine DNA por obra |
| Pilares sobrepostos no DXF | Projetos com pilares-parede | Merge de contornos adjacentes |
| Layer '0' vs CONCRETO | Arquivos TQS usam layer '0' | FamilyDetector identifica automaticamente |

---

## 8. MÉTRICAS DE PERFORMANCE (2026-03-18)

```
Total de pilares no banco:  6.524
Pilares validados:          ~3.800 (~58%)
training_events (Pilar):    189 eventos de validação
Regras de transformação:    9 regras (7 em produção)
Acurácia média das regras:  71.4%
Cobertura média:            3.8%
```

---

*Ficha técnica Bolt v1.0 | CAD-ANALYZER | Diana Corporação Senciente*
*Gerada automaticamente em 2026-03-18 | Revisar a cada evolução de versão*
