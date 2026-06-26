# Padrões de Desenho dos Robos SCR — Sistema NOVA
**Fonte:** config_abcd.json, config_grades.json, config_cima.json, config.json (LV), app_config.json (LJ) — extraído 2026-06-04
**Uso:** RAG compreensão semântica de layers, blocks, comandos SCR e constantes de desenho

---

## 1. Robo Pilares — Vista ABCD (Faces Laterais)

**Config:** `_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/config/config_abcd.json`
**Função:** Gera as 4 faces laterais do pilar (A, B, C, D) com painéis e furação

### Layers
| Layer | Conteúdo |
|-------|----------|
| `Painéis` | Retângulos dos painéis da chapa (h1, h2, h3...) |
| `Nível` | Cota de nível do pavimento |
| `cota` | Dimensões cotadas |
| `SARR_2.2x7` | Sarrafos 2,2×7cm (fixação lateral) |
| `nomenclatura` | Nome do pilar (ex: P-1) |

### Blocos
| Bloco | Uso |
|-------|-----|
| `furacao` | Furos da chapa (onde passa o parafuso) |
| `SLIPTEE` | Conector tipo T (slipform) |
| `SLIPTDD` | Conector duplo D |
| `MULDURA` | Moldura/frame do painel |

### Parâmetros de Parafusos (config parafusos.ab)
| Parâmetro | Valor | Significado |
|-----------|-------|-------------|
| `medida_fundo_primeiro_ab` | 30cm | Distância VERTICAL entre base do pilar e 1º parafuso |
| `medida_1_2_ab` | 50cm | Distância VERTICAL entre parafuso 1 e 2 |
| `medida_2_3_ab` | 55cm | Distância VERTICAL entre parafuso 2 e demais (idem para 3_4, 4_5...) |

**ATENÇÃO:** Estas são distâncias VERTICAIS (ao longo da altura), NÃO as distâncias horizontais dos campos par_1_2.

### Drawing Options
| Opção | Valor |
|-------|-------|
| `espacamento_parafusos` | 50cm |
| `offset_parafuso` | 24cm |
| `offset_moldura` | 38cm |

---

## 2. Robo Pilares — Vista GRADES (Grade Horizontal)

**Config:** `_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/config/config_grades.json`
**Função:** Gera a vista de topo da grade com sarrafos horizontais e verticais

### Layers
| Layer | Conteúdo |
|-------|----------|
| `SARR_2.2x7` | Sarrafos base e laterais (2,2×7cm) |
| `SARR_2.2x10` | Sarrafos de reforço/primeiro_horizontal (2,2×10cm) |
| `SARR_3.5x7` | Sarrafo central (3,5×7cm) |

### Posições Horizontais Padrão
`horizontal_positions = [30, 120, 210, 300, 390, 480, 720, 830, 940]`

Estas posições representam onde são inseridos os sarrafos horizontais na vista de grades.

### Blocos de Triângulo
| Bloco | Posição |
|-------|---------|
| `GRA-E` | Triângulo lado esquerdo (início da grade) |
| `GRA-D` | Triângulo lado direito (fim da grade) |

---

## 3. Robo Pilares — Vista CIMA (Vista Superior)

**Config:** `_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/config/config_cima.json`
**Função:** Gera a vista superior do pilar com as 4 faces e blocos de face

### Layers
| Layer | Conteúdo |
|-------|----------|
| `hachura-chapa` | Hachura do painel de chapa |
| `SARRAFO` | Sarrafos na vista superior |
| `COTA` | Dimensões cotadas |
| `NOMENCLATURA` | Nome e identificador do pilar |
| `GRAVATA` | Elemento de fixação (gravata) |
| `Hachura` | Hachura geral |

### Blocos de Face
| Bloco | Face/Uso |
|-------|----------|
| `B1A.E` | Bloco face A, lado esquerdo, tipo 1 |
| `B1A.D` | Bloco face A, lado direito, tipo 1 |
| `B2A.E` | Bloco face A, lado esquerdo, tipo 2 |
| `B1B.E` | Bloco face B, lado esquerdo, tipo 1 |
| `B1B.D` | Bloco face B, lado direito, tipo 1 |
| `PAR.CIM` | Parafuso superior |
| `PAR.BAI` | Parafuso inferior |
| `TA-TH` | Blocos de face T-A a T-H (conectores especiais) |

### Drawing Options
| Opção | Valor |
|-------|-------|
| `scale_factor` | 2 |
| `dimstyle` | `cotax2` |

---

## 4. Robo Laterais de Vigas (LV)

**Config:** `_ROBOS_ABAS/Robo_Laterais_de_Vigas/config.json`
**Função:** Gera as faces laterais A e B das vigas com segmentação e recortes

### Layers
| Layer | Conteúdo |
|-------|----------|
| `Painéis` | Painéis da face lateral (segmentos de 122cm) |
| `SARR_2.2x7` | Sarrafos verticais 2,2×7cm |
| `SARR_2.2x7 (horiz)` | Sarrafos horizontais 2,2×7cm |
| `SARR_2.2x5` | Sarrafos pequenos 2,2×5cm (cantos) |
| `NOMENCLATURA` | Identificação da viga |
| `COTA` | Dimensões cotadas |
| `BARRA_ANCORAGEM` | Barra de ancoragem lateral |

### Comandos LISP Especializados
| Comando | Função |
|---------|--------|
| `ex2` | Extensor tipo 1 (extensor1) |
| `Bextend` | Extensão de bloco |
| `APP` | Append/adicionar elemento |
| `appdel` | Remover elemento appended |
| `ABVET` | Abertura vertical (passagem em viga) |
| `ABVEF` | Abertura viga, face esquerda |
| `ABFDT` | Abertura fundo topo |
| `ABVDT` | Abertura viga direita topo |
| `ABVDTV` | Abertura viga direita topo vertical |
| `ABVDF` | Abertura viga direita fundo |
| `ABFDF` | Abertura fundo fundo |

---

## 5. Robo Lajes (LJ)

**Config:** `_ROBOS_ABAS/Robo_Lajes/laje_src/config/app_config.json`
**Função:** Gera o grid de painéis da laje com linhas verticais e horizontais

### Layers
| Layer | Conteúdo |
|-------|----------|
| `nomenclatura` | Label do painel (A1, A2, B1...) |
| `painéis` | Retângulos dos painéis |
| `concreto` | Região de concreto/enchimento |
| `cota` | Dimensões cotadas |

### Comandos de Hatch
| Comando | Função |
|---------|--------|
| `HLAZ` | Hatch união (unir painéis adjacentes sem linha divisória) |
| `HH` | Hatch reaproveitamento inteiro (painel reutilizável inteiro) |
| `HHH` | Hatch reaproveitamento com corte |

### Algoritmo Modo 1 — Distribuição de Linhas Verticais
Ciclo principal: `122 + 60 + união` (= 182cm + união)
- Linha 122cm: painel principal
- Linha 60cm: painel intermediário
- União: espaçamento de emenda, 20–30cm (preferir 20cm)
- Ciclos seguintes: `122 + união`
- Meta: soma exata = largura_total (sobra = 0)

### Nomenclatura do Grid de Painéis
- Coluna = letra (A, B, C, D...)
- Linha = número (1, 2, 3...)
- Exemplo: A1 (coluna A, linha 1), B2 (coluna B, linha 2)
- Linhas horizontais são INVERTIDAS antes do cálculo (reversed antes de calcular posições absolutas)

---

## 6. Robo Fundos de Vigas (FV)

**Arquivos:** `_ROBOS_ABAS/Robo_Fundos_de_Vigas/compactador-producao/`
**Função:** Gera o fundo (base) da viga com sarrafos transversais

### Conceitos Chave
- O fundo é a face INFERIOR da viga (plano horizontal)
- Dimensões: largura (14cm, 19cm, etc.) × comprimento total da viga
- Sarrafos transversais: perpendiculares ao eixo da viga

### Templates FV (de docs existentes)
| Template | Uso |
|----------|-----|
| `ex2` | Template extensor tipo 2 |
| `nf1`–`nf10` | Templates numerados para diferentes configurações de fundo |
| 5 layers distintos | Layers específicos do fundo |

### Integração COM AutoCAD
O Robo FV usa COM (pythoncom, win32com.client) para interação com AutoCAD:
- `pythoncom.CoInitialize()` — inicialização COM
- `win32com.client.Dispatch("AutoCAD.Application")` — conexão
- Operações via Selection Sets no documento ativo

---

## 7. Relação entre Robos e JSON de Pilar/Viga

### Campos JSON → Vista Robo PL
| Campo JSON | Vista | Uso no Desenho |
|------------|-------|----------------|
| `larg1_A`..`larg1_H` | ABCD | Largura do retângulo de cada face |
| `h1_A`..`h4_H` | ABCD | Alturas dos painéis empilhados |
| `grade_1`, `grade_2`, `grade_3` | GRADES | Comprimento das barras horizontais |
| `distancia_1`, `distancia_2` | GRADES | Espaçamento entre grades paralelas |
| `par_1_2`..`par_8_9` | GRADES | Posições dos parafusos na grade |
| `laje_A`..`laje_H` | ABCD | Espessura da laje na face (furação especial) |
| `posicao_laje_A`..`H` | ABCD | Qual painel tem recorte de laje |

### Campos JSON → Vista Robo LV
| Campo JSON | Vista | Uso no Desenho |
|------------|-------|----------------|
| `grade_h1`, `grade_h2` | LV | Altura dos sarrafos horizontais (bug: sempre 0 atualmente) |
| `pillar_left`, `pillar_right` | LV | Pilares nas extremidades (cruzamento) |
| `segmentos` | LV | Lista de segmentos com comprimento e laje |
| Segmento: `comp_com_fv` | LV | Comprimento incluindo fundo de viga |

### Campos JSON → Vista Robo LJ
| Campo JSON | Vista | Uso no Desenho |
|------------|-------|----------------|
| `linhas_verticais` | LJ | Divisões de colunas (122, 60, união...) |
| `linhas_horizontais` | LJ | Divisões de linhas (normalmente iguais) |
| `coordenadas` | LJ | Polígono do contorno da laje |
| `modo_calculo` | LJ | 1=Modo1 (automático), 2=Manual |

---

## 8. Nomenclatura Canônica de Blocos AutoCAD

Blocos são inseridos via comando `_INSERT` ou `INSIRA` no SCR:
```
_INSERT bloco_name pto_x,pto_y escala rot
```

| Prefixo | Família de Blocos |
|---------|------------------|
| `GRA-E`, `GRA-D` | Grade (triangulo esquerdo/direito) |
| `B1A`, `B2A`, `B1B` | Face do pilar (tipo1/2, face A/B) |
| `PAR.CIM`, `PAR.BAI` | Parafuso CIMA/BAIXO |
| `TA-TH` | Conectores especiais T-A até T-H |
| `MULDURA` | Moldura do painel |
| `furacao` | Furos de chapa |
| `SLIPTEE`, `SLIPTDD` | Conectores slip |
| `PONTALETE` | Bloco pontalete da laje |

---

## 9. Constantes de Dimensão NOVA

| Constante | Valor | Fonte |
|-----------|-------|-------|
| Chapa inteira — altura | 244cm | Sistema NOVA padrão |
| Chapa inteira — largura | 122cm | Sistema NOVA padrão |
| Meia chapa — altura | 122cm | Sistema NOVA |
| Cinta inferior (h1) | 2cm | config/semantica validada |
| Grade extension per side | 11cm | grade_1 = comp + 22 (2×11) |
| Grade internal adj | 12cm | grade_calc: comp + 24 (2×12) |
| Dist parafuso fundo | 30cm | config_abcd.parafusos.ab |
| Dist parafuso 1-2 | 50cm | config_abcd.parafusos.ab |
| Dist parafuso 2+ | 55cm | config_abcd.parafusos.ab |
| Tamanho max de grade | 106cm | grade_calculator.calcular_grades |
| Distância entre grades | 1–15cm | grade_calculator.calcular_grades |
| Detail max (detalhe_grade) | 33cm | calculate_details_legacy |
| Union laje | 20–30cm | calculo_modo1 |
