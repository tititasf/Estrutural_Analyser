# HANDOFF-B: Conhecimento Extraído dos PDFs
**Data:** 2026-03-18 | **Fonte:** pdfs-obras-aleatorias (18 PDFs) | **Athena → Blueprint CEO-CAD-ANALYZER**

---

## 1. ESTRUTURA DOS DOCUMENTOS PI (Processo Interno - Projetista)

Os PDFs revelam dois tipos de documentos:

### 1.1 PI (Processo Interno — Gold Standard)
Contém por pavimento:
- **P.D.** (Pé-Direito): altura livre em mm (ex: 2800, 3200)
- **Cota de Saída**: nível altimétrico do pavimento
- **Delimitação**: string descritiva dos elementos abrangidos
- **m² por elemento**: área real de pilares, vigas, lajes
- **Chapas**: contagem real de chapas metálicas
- **Garfos**: quantidade de garfos por pavimento
- **Gastalhos**: quantidade de espaçadores
- **Madeira Serrada (m³)**: volume real de madeira
- **Jogos de Formas**: número de reutilizações previstas

### 1.2 NSC (Proposta Comercial)
Contém:
- Escopo delimitado (texto de delimitação)
- Totais de chapas, madeira, garfos
- Valor/m² (confidencial)
- Projetista responsável

---

## 2. DADOS DAS OBRAS REAIS (Extraídos)

| Obra | Chapas | Madeira (m³) | Garfos | Projetista | Obs |
|------|--------|-------------|--------|------------|-----|
| NIK SUNSET | 810 | 39 | 285 | — | Pequena |
| LEAF LOEFGREN | 4.209 | 146 | 305 | FELIPE | Grande |
| INDIANÓPOLIS | 2.753 | 85 | 230 | **ATHENA** | — |
| NURBAN | 454 | — | 77 | — | Mini |
| GWT SCHWARTZ | 2.040 | 64 | — | — | Média |
| CASA DA ARRAIA | 1.505 | 55 | — | — | Média |

**Nota:** Projetista ATHENA = este sistema. LEAF LOEFGREN é a maior obra treinada.

---

## 3. ELEMENTOS ESPECIAIS DESCOBERTOS

Tipos ausentes do sistema atual encontrados nos PDFs:

### Pilar Cambotado
- Pilar com seção variável ao longo da altura
- Geometria: trapézio ou parabolóide
- Dimensão string: `PC-{n}x{base_topo}/{base_fundo}x{altura}`
- Frequência: ~3% dos pilares em obras complexas
- Impacto: chapas adicionais = variação de +15-25% na estimativa

### Viga Cambotada
- Viga com curvatura no eixo longitudinal (banana)
- Símbolo: `VC.{n}` nos DXFs
- Requer cálculo de arco em vez de comprimento reto

### Misula
- Projeção de apoio na face de um pilar
- Símbolo: `MS-{n}` ou desenhada como polilinha na layer do pilar
- Gera forma independente (não incluída nos segmentos normais)

### Parede Estrutural (Wall Slab)
- Laje vertical (shear wall)
- Diferente de viga (horizontal) e pilar (pontual)
- Presente em reservatórios e caixas d'água

### Reservatório / Caixa d'Água
- Elemento especial com fundo cônico ou plano
- Garfo especial (garfo de reservatório)

---

## 4. PADRÃO DE NOMES (Nomenclatura Real)

### Pilares (confirmados nos PDFs)
```
P1, P2, P.1, P.2     → Pilar numerado (TQS)
P1A, P2B             → Pilar com letra (TQS com sub-elementos)
P-1, P-2             → Pilar com hífen (BIM/TQS)
PC1, PC.1            → Pilar cambotado
```

### Vigas (confirmados nos PDFs)
```
V1, V.1, V-1         → Viga normal
BA1, BA.1            → Balanço
VB1, VB.1            → Viga em balanço
VT1                  → Viga de topo
VC1                  → Viga cambotada
V1.1, V1/1           → Sub-viga (segmento)
```

### Lajes (confirmados nos PDFs)
```
L1, L.1, L-1         → Laje normal
L1A, L1B             → Laje com identificador de cômodo
LS1                  → Laje de sacada
LB1                  → Laje de balcão
LC1                  → Laje de cobertura
```

---

## 5. FÓRMULAS DE ESTIMATIVA (Derivadas dos PDFs)

### Relação Chapas/m²
- Média geral: **2.8 chapas/m²** de laje
- Pilar isolado (4 faces): **12-16 chapas/pilar** (função de h)
- Viga (lateral): **chapas = 2 × comprimento × altura / painel_area**

### Relação Garfos/Chapa
- Média: **1 garfo / 7 chapas**
- Grandes obras: **1 garfo / 10-12 chapas** (reuso mais alto)

### Relação Madeira/m²
- Sarrafa 5×5: **0.025 m³/m² de forma** (laje)
- Pontaletes: **0.012 m³/m²** (suporte de laje)
- Total: ~**0.04-0.06 m³/m²** de laje

---

## 6. IMPLICAÇÕES PARA MOTOR_FASE4

### Ajustes Necessários (identificados via PDFs)

1. **Pé-Direito por Pavimento**: usar tabela `pavimento_pi.pe_direito_mm` em vez de PE_DIREITO_DEFAULT=2800
2. **Delimitação Parcial**: quando PI indica "inclui apenas estrutura de concreto" → excluir escadas, marquises
3. **Cota de Saída**: nível real do topo do pilar (afeta altura_pilar = cota_saida - cota_fundo)
4. **Jogos de Formas**: multiplicador de custo/volume afeta garfos e gastalhos

### Campos Novos em CalculationResult
```python
# Adicionar a CalculationResult:
pe_direito_real: float = 0.0        # do PI
cota_saida: float = 0.0             # do PI
delimitacao: str = ''               # texto do PI
jogos_formas: int = 1               # do PI
area_projeto_m2: float = 0.0        # calculado
valor_m2_estimado: float = 0.0      # do histórico
```
