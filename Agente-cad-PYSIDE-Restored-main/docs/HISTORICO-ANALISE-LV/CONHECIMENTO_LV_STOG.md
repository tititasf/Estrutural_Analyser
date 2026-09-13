# Conhecimento Extraído: Laterais de Vigas STOG
## 142 amostras | 5 obras | 13 DXFs | 2026-03-10

---

## 1. Anatomia de uma LV STOG

Cada viga lateral STOG contém:

```
┌─────────────────────────────────────────────────────────────┐
│  TÍTULO (INSERT titulo1)                                     │
│  - Attribs: TITULO=V1, SEÇÃO=(19x60), REAPROVEITAMENTO=     │
│                                                              │
│  ┌──────────────────────────────────┐  ┌────────────────┐    │
│  │  FACE A (superior)               │  │ SEÇÃO TRANSV.  │    │
│  │  - Painéis (Painéis layer)       │  │ - Concreto     │    │
│  │  - Sarrafos (SARR_* layers)      │  │ - Escoras      │    │
│  │  - Hachura reaprov. (Reaprov.)   │  │ - Tensores     │    │
│  │  - Cotas (COTA layer)            │  │ - Presilhas    │    │
│  │  - Números painéis (P1, P2...)   │  └────────────────┘    │
│  └──────────────────────────────────┘                        │
│  ┌──────────────────────────────────┐  ┌────────────────┐    │
│  │  FACE B (inferior)               │  │ TABELA ALTURAS │    │
│  │  - Layout similar à Face A       │  │ - Alt. laje    │    │
│  │  - h_B = h_A - 10 (típico)      │  │ - Espaçamento  │    │
│  │  - Pode ter hachuras diferentes  │  │   barrotes     │    │
│  └──────────────────────────────────┘  └────────────────┘    │
│                                                              │
│  ┌──────────────────────────────────┐                        │
│  │  SARR (arranj. sarrafo-detalhes) │ ← opcional             │
│  └──────────────────────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## 2. Layers STOG (por frequência nas 142 amostras)

| Layer | Freq | Função | Cor/Estilo |
|-------|------|--------|------------|
| Painéis | 98 | Contorno dos painéis de fôrma | Cyan (#00FFFF) |
| Madeira | 91 | Peças de madeira (barrotes, compensado) | ANSI31 hatch |
| Texto Seção | 91 | Texto/labels do detalhe de seção | Branco |
| CONCRETO | 89 | Contorno da seção de concreto | Preto/Cinza |
| SARR_2.2x7 | 83 | Sarrafos 2.2x7cm | Magenta |
| COTA | 81 | Dimensões + hachura concreto (AR-CONC) | Amarelo/Bylayer |
| SARR_3.5x7 | 80 | Sarrafos 3.5x7cm | Magenta |
| 5 | 72 | Números dos painéis | Layer 5 |
| detalhes | 72 | Detalhes construtivos | Variável |
| 0 | 70 | Layer default | Branco |
| SCO-___-LAJ | 60 | Contorno da laje | Verde/Cyan |
| barrote | 60 | Barrotes (reforço) | Bylayer |
| presilha | 60 | Presilhas metálicas (blocks) | Purple |
| TENSOR | 53 | Tensores de amarração | Vermelho |
| Hachura | 47 | Hachuras genéricas | Bylayer |
| SARR_EDITAR | 47 | Sarrafos editáveis | Magenta |
| texto | 47 | Texto dimensões dos painéis | Branco |
| CARIMBO | 45 | Grid/carimbo da folha | Laranja |
| Sarr 2.2x7 | 44 | Sarrafos (variante de nome) | Magenta |
| NOMENCLATURA | 39 | Labels de identificação | Branco |
| Reaproveitamento | 23 | Hachura de reaproveitamento | ANSI31/Bylayer |
| Demarcação 2 | 10 | Marcação de zonas | Bylayer |
| Perfil Metálico | 10 | Perfis metálicos | Bylayer |

## 3. Hatch Patterns

| Pattern | Freq | Layer | Uso |
|---------|------|-------|-----|
| AR-CONC | 69 | COTA | Seção concreto (denso, granulado) |
| ANSI31 | 52 | Reaproveitamento, Madeira | Linhas diagonais 45° (reuso/madeira) |
| SOLID | 29 | Hachura | Preenchimento sólido (peças pequenas) |
| ANSI32 | 10 | Hachura | Cross-hatching (X pattern) |
| ANSI37 | 3 | Hachura | Diagonal fina |
| ANSI36 | 3 | Hachura | Padrão especial |
| DOTS | 3 | Hachura | Pontos (raro) |

## 4. Medidas Padrão de Painéis

Larguras mais comuns (em cm):
- **244** — Painel padrão (mais frequente)
- **122** — Meio painel
- **160** — Intermediário
- **220/224** — Painel largo
- **99/100** — Painel curto
- **155/156** — Intermediário
- **130/131** — Intermediário

Alturas típicas:
- Face A: h_section + 4 (ex: 60+4=64)
- Face B: h_section - 10 (ex: 60-10=50, mínimo 10)

## 5. Diversidade de Tipos

| Tipo | Qtd | % | Características |
|------|-----|---|----------------|
| Simples (sem hatch, curta) | 58 | 41% | Apenas painéis e seção |
| Complexa com laje (longa) | 39 | 27% | Hachuras de reaproveitamento + laje |
| Com abertura/pilar | 16 | 11% | Linhas tracejadas + reforços |
| Hachura simples | 15 | 11% | 1-3 hachuras (laje ou seção) |
| Hachura média | 12 | 8% | 4-8 hachuras |
| Muito complexa (laje+aber.) | 9 | 6% | Maior diversidade visual |

## 6. Entity Counts por Viga

| Tipo | Min | Max | Média |
|------|-----|-----|-------|
| Hatches | 0 | 66 | 12.6 |
| Lines | 0 | 827 | 224 |
| LWPolylines | 0 | 221 | 51 |
| Text | 0 | 148 | 34 |
| MText | 0 | 46 | 9 |

## 7. Padrões para Reprodução

### 7.1 Face A e Face B
- Face A: altura = h/2 + 4 (face superior, mais alta)
- Face B: altura = max(h/2 - 10, 10) (face inferior)
- Painéis subdivididos em módulos (244, 122, etc.)
- Sarrafos passam horizontalmente por todos os painéis
- Cotas em linha abaixo dos painéis

### 7.2 Seção Transversal
- Retângulo b_alma x h com hachura AR-CONC (escala ~0.4-0.5)
- Escoras abaixo (diagonal, amarelo)
- Presilhas metálicas (blocks roxos)
- Tensores (vermelho)
- Barrotes (layers barrote/Madeira)

### 7.3 Laje (quando presente)
- Contorno no layer SCO-___-LAJ
- Hachura ANSI31 no layer COTA ou Reaproveitamento
- Posição: superior, inferior, ou central
- Altura típica: 7-10cm

### 7.4 Reaproveitamento
- Painéis hachurados com ANSI31 no layer Reaproveitamento
- Indica painéis reutilizados de outros pavimentos
- Cor 256 (bylayer)
- Escala da hachura: ~1.0

### 7.5 Numeração
- Painéis numerados: P1, P2, P3... (layer 5 ou NOMENCLATURA)
- Face A e Face B podem ter numerações diferentes
- Número posicionado centrado abaixo de cada painel

---

## 8. Diferenças Entre Obras

| Obra | Estilo | Complexidade |
|------|--------|-------------|
| TREINO_3 (Diamond) | Isométrica 3D + table | Alta (886 ents/viga max) |
| TREINO_9 (Citta) | Isométrica 3D + escoras | Alta (891 ents) |
| TREINO_10 (Hospital) | Faces claras + seção | Média-alta (953 ents) |
| TREINO_21 (Nik Sunset) | Limpo, faces + seção | Média (825 ents) |
| TREINO_22 (Paraiso) | Multi-viga combinada | Média (475 ents) |

---

*Gerado automaticamente a partir de 142 amostras STOG — 2026-03-10*
