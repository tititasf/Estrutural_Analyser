# RELATORIO DE AUDITORIA TECNICA -- Fichas Instrutivas de Escoramento

**Auditor:** Atlas (Analyst Agent) -- CAD:FormworkEngineering-AIOS
**Data:** 2026-03-19
**Arquivos Auditados:**
- `scripts/gerar_fichas_instrutivas.py` (2794 linhas, 3 PDFs)
- `docs/fichas/bolt-pilar-ficha.md` (Ficha Bolt -- Pilares)
- `docs/fichas/crane-viga-ficha.md` (Ficha Crane -- Vigas)
- `docs/fichas/slab-laje-ficha.md` (Ficha Slab -- Lajes)

**Escopo:** Validacao tecnica das regras de escoramento, terminologia, decision trees, JSON schemas e completude para automacao CAD.

---

## 1. PRECISAO DAS REGRAS DE ESCORAMENTO

### 1.1 Medidas de Sarrafo

| Sarrafo no Script | Dimensao Declarada | Validacao Tecnica | Veredicto |
|---|---|---|---|
| SARR_2.2x7 | 22 x 70 mm | Sarrafo 2,5x10cm e o padrao SINAPI; 2,2cm (22mm) e espessura de compensado, nao de sarrafo serrado. Na pratica, a nomenclatura "2.2x7" indica a espessura do compensado (22mm) x largura (70mm), nao uma peca de madeira serrada. | ATENCAO -- unidade mista |
| SARR_2.2x10 | 22 x 100 mm | Mesma logica: compensado 22mm x 100mm de altura. Usado para PE direito > 3m. | ATENCAO -- nao e sarrafo bruto |
| SARR_2.2x15 | 22 x 150 mm | Listado no layer mas sem regras de uso. | INCOMPLETO |
| SARR_2.2x20 | 22 x 200 mm | Idem, apenas cor ACI definida. | INCOMPLETO |
| SARR_3.5x7 | 35 x 70 mm | Corresponderia a sarrafo bruto 3,5x7cm -- dimensao real de mercado. | CORRETO |
| SARR_7x7 | 70 x 70 mm | Pontalete 7x7cm usado como sarrafo de quina -- compativel com produto real de mercado (pontalete Pinus 7x7cm e padrao encontrado em multiplos fornecedores). | CORRETO |
| SARR_7x10 | 70 x 100 mm | Presente no layer colors, sem regra de uso documentada. | INCOMPLETO |

**Achado CRITICO:** A nomenclatura "SARR_2.2x7" mistura unidades -- o "2.2" refere-se a espessura do compensado (22mm = 2,2cm) e o "7" refere-se a 70mm (7cm). Isto nao corresponde a uma peca de madeira serrada padrao da industria. A documentacao precisa explicitar que "SARR_2.2x7" e uma abreviacao interna que significa "tira de compensado resinado de 22mm de espessura por 70mm de largura", e nao um sarrafo de madeira macica.

### 1.2 Condicoes de Uso (Decision Tree Pg 9 Pilares)

| Condicao | Regra no Script | Analise Tecnica | Veredicto |
|---|---|---|---|
| max(X,Y) < 200mm | SARR_2.2x7 | Para pilares pequenos, tira de compensado de 22x70mm e adequada. | RAZOAVEL |
| max(X,Y) 200-400mm | SARR_3.5x7 | Sarrafo bruto 3,5x7cm para pilares medios -- faz sentido estrutural. | CORRETO |
| max(X,Y) > 400mm | SARR_7x7 | Pontalete 7x7cm como reforco nas quinas de pilares grandes -- pratica comum. | CORRETO |
| PD > 3.0m | SARR_2.2x10 | Aumentar a largura do sarrafo para PE direito elevado compensa o momento fletor. | CORRETO em principio |

**Achado ALTO:** O script define thresholds de 200mm e 400mm na secao do pilar, mas nao documenta a **justificativa estrutural**. A NBR 14931 nao define thresholds especificos para tipo de sarrafo por dimensao de pilar -- estes sao valores empiricos/de fabricante. Devem ser citados como "pratica interna" e nao como norma.

### 1.3 Dimensoes dos Paineis

| Painel | Dimensao (Script) | Validacao | Veredicto |
|---|---|---|---|
| PA-015x050 | 150 x 500 mm (W x H) | Nenhum fabricante vende compensado nesta dimensao como produto padrao. Compensado resinado padrao e 1100x2200mm (1,10x2,20m). "PA-015x050" parece ser um codigo de corte interno, nao um produto de mercado. | ATENCAO -- codificacao interna |
| PA-022x100 | 220 x 1000 mm | Idem -- corte de chapa 2200x1100 em tiras de 220mm. A espessura de 22mm corresponde a compensados de 20mm ou 21mm (nao exatamente 22mm na maioria dos fabricantes; tolerancia +/-1mm). | PARCIALMENTE CORRETO |
| PA-030x150 | 300 x 1500 mm | Corte possivel de chapa standard. | RAZOAVEL |
| Espessura 22mm | Todas as obras | Compensado resinado padrao de mercado brasileiro e tipicamente 6, 9, 12, 14, 17, 20mm. **22mm nao e espessura padrao de catalogo** -- possivelmente compensado "plastificado" ou "plastfilm" que pode chegar a 21-22mm. | ATENCAO -- verificar com fornecedor |

**Achado ALTO:** A espessura de 22mm e usada universalmente no script e nas fichas como constante absoluta, mas nao corresponde exatamente a uma espessura padrao de compensado resinado encontrada em catalogos de fabricantes (6, 9, 12, 14, 17, 20mm sao os padroes). Pode ser compensado plastificado de 21mm com tolerancia, ou uma espessura especifica de um fabricante particular. Deve ser parametrizada, nao hardcoded.

### 1.4 Regra "Sarrafo nas Juntas entre Paineis"

A regra esta presente em multiplas paginas (Pg 2, 4, 5, 21, 22 do PDF de pilares) e e tecnicamente **CORRETA**. Na pratica de escoramento, as juntas entre paineis de compensado sao travadas com ripas/sarrafos para evitar deslocamento lateral durante a concretagem. O script demonstra isso claramente na funcao `draw_pilar_topo()` (linha 599-681), onde os sarrafos sao posicionados nas 4 faces do pilar, nas juntas entre paineis.

**Veredicto: CORRETO e BEM DOCUMENTADO.**

### 1.5 Pontaletes (7x7cm, arco 90 graus)

O pontalete 7x7cm (70x70mm) e um produto real e padrao de mercado, vendido em comprimentos de 3 metros. A funcao `draw_pontalete()` (linha 269-278) o representa como um quadrado com um arco de 90 graus no canto inferior esquerdo -- esta e uma **convencao grafica CAD**, nao uma representacao fisica. O arco indica a direcao de apoio/travamento.

**Achado MEDIO:** O script usa `size=14` como padrao (14mm = 1,4cm na escala do desenho), mas o texto da Pg 7 diz "PONTALETE 7x7mm (escala 2=14x14)". **ERRO DE UNIDADE**: pontalete 7x7**cm** (centimetros), nao 7x7**mm** (milimetros). Um pontalete de 7mm seria do tamanho de um palito de dente. A tabela na Pg 7 tambem lista "PONTALETE W=7 H=7" sem unidade clara. Deve ser 7x7**cm** = 70x70mm.

### 1.6 Chapas de Ancoragem

A funcao `draw_chapa()` (linha 261-266) define `W=4mm` como largura da chapa. A Pg 7 menciona "CHAPA 4x176mm".

| Atributo | Valor no Script | Analise | Veredicto |
|---|---|---|---|
| Largura | 4mm | Chapas metalicas de ancoragem para forma de pilar tipicamente tem 3-5mm de espessura. 4mm esta dentro do range. | RAZOAVEL |
| Altura | 176mm | Este valor parece calculado (22mm painel + 154mm concreto?), nao e um produto padrao. | ATENCAO -- derivado? |
| Material | Aco (vermelho ACI=1) | Correto -- chapa de aco galvanizado. | CORRETO |

**Achado MEDIO:** A altura de 176mm da chapa parece ser um valor derivado de uma configuracao especifica (possivelmente espessura_painel + parcela do pilar), nao um produto padrao de mercado. Deve ser parametrizada.

---

## 2. CONFORMIDADE COM TERMINOLOGIA DE ESCORAMENTO

### 2.1 Termos Tecnicos

| Termo | Uso no Script/Fichas | Corretude | Observacao |
|---|---|---|---|
| SARRAFO DE PRESSAO | Layer, linhas tracejadas, topo/base | CORRETO | Elemento perimetral de travamento; standard na industria |
| HT20CT | Escora em U, 3 polylines | PARCIALMENTE | "HT20" e nomenclatura de viga de escoramento (ex: H20 da Doka/PERI); "CT" pode ser variante local. Nome nao encontrado em catalogos padrao -- possivelmente "H20 Corte Transversal" como abreviacao interna |
| PRESILHA | Metalica, forma de C | CORRETO | Presilha metalica e o termo padrao para grampo de fixacao de forma |
| GARFO | Bloco C, ancoragem | CORRETO | "Garfo" ou "forcador" e o termo correto para ancoragem transversal |
| TENSOR | Tirante vertical | CORRETO | Tensor/tirante de aco para manter as laterais paralelas |
| FV | Fundo de Viga | CORRETO | Abreviacao padrao da industria |
| BARRA ANCORAGEM | Barra horizontal | CORRETO | Barra de ancoragem e o termo padrao |
| PONTALETE | Escora vertical 7x7cm | CORRETO | Termo padrao |
| MEIO PONTALETE | 3.5x7cm | CORRETO | Metade de um pontalete cortado longitudinalmente |
| PA-022 | Codigo de painel | INTERNO | Nao e nomenclatura padrao da industria -- e codificacao interna do sistema |

**Achado MEDIO:** "HT20CT" nao e um termo padrao encontravel em catalogos da SH, Doka, PERI ou Mills. A viga H20 (ou HT20) e um produto real, mas "CT" parece ser uma adenda interna. Recomendacao: documentar a origem do termo ou usar "Viga H20 (escora em U)".

### 2.2 Nomenclatura de Faces

O script usa a convencao `V1.A`, `V1.B`, `P1.A`, `P1.B`, etc.

| Convencao | Uso | Padrao Industria | Veredicto |
|---|---|---|---|
| P{n}.A/B/C/D | Faces de pilar (A=maior dim) | Nao ha padrao ABNT oficial para nomear faces de formas. Fabricantes como SH usam "lado 1, lado 2" ou "frente/verso". A convencao ABCD e razoavel e consistente. | ACEITAVEL -- convencao interna |
| V{n}.A/B | Laterais de viga | Idem. A/B para laterais e pratica comum em escritorios de projetos de formas. | ACEITAVEL |
| CMT | Comprimento lateral | Abreviacao interna nao padrao. | INTERNO |

---

## 3. COMPLETUDE DO CONTEUDO

### 3.1 O que esta FALTANDO para um Robo CAD

| Item Ausente | Criticidade | Descricao |
|---|---|---|
| **Tolerancias dimensionais** | CRITICO | O robo precisa saber: tolerancia de corte do compensado (+/-1mm?), folga entre pilar e forma (tipicamente 5-10mm), tolerancia de posicionamento de sarrafos. Nenhuma tolerancia esta documentada. |
| **Regras de sobreposicao de paineis** | CRITICO | Quando dois paineis se encontram numa quina, qual sobrepoe qual? O script desenha (draw_pilar_topo linhas 614-621), mas as regras de prioridade nao estao explicitadas. |
| **Sentido de montagem** | ALTO | Em que ordem as 4 faces do pilar sao montadas? Tipicamente: faces opostas primeiro, depois as adjacentes. Nao documentado. |
| **Calculo de quantidade de paineis por face** | ALTO | A formula n_paineis = ceil(comprimento_face / largura_painel) esta implicita mas nao explicita em nenhuma ficha. |
| **Offset de juntas entre faces opostas** | ALTO | A Pg 22 menciona "offset minimo 10cm", mas nao fornece a formula de calculo do offset. |
| **Regras para parafusos/fixacao** | ALTO | Os templates ABCD (Bolt ficha, secao 3) mencionam 8 variantes de parafusos (PAR_ESQ, PAR_DIRV, INI_PAR, etc.) mas as fichas instrutivas nao documentam NENHUM detalhe de fixacao por parafusos. |
| **Espessura minima de concreto por norma** | MEDIO | A NBR 6118 define cobrimentos minimos que afetam a dimensao da forma. Nao mencionado. |
| **Contra-flecha** | MEDIO | Para vigas longas (>6m), a NBR 14931 exige contra-flecha. Nenhuma regra de contra-flecha esta documentada. |
| **Pressao do concreto fresco** | MEDIO | Para pilares altos, a pressao lateral do concreto fresco e critica para dimensionamento da forma. Nao calculada. |
| **Desmoldante** | BAIXO | Tipo de desmoldante afeta o acabamento. Nao mencionado. |

### 3.2 Regras Criticas de Montagem Ausentes

1. **Sequencia de concretagem**: O robo nao sabe se o pilar sera concretado de uma vez ou em etapas (janela de concretagem).
2. **Lastro de concreto**: Nem todas as vigas tem fundo apoiado -- vigas em balanco tem apoio diferente.
3. **Escoramento de laje sob viga**: A ficha da laje nao explica como o escoramento da laje interage com o escoramento da viga que cruza a laje.
4. **Janela de inspecao**: Pilares altos precisam de janela na base para limpeza. Nao documentado.
5. **Fixacao no piso**: Como os pontaletes sao fixados ao piso/laje inferior (sarrafo guia, chapuz). Nao documentado.

### 3.3 Casos Especiais Ausentes

| Caso Especial | Status | Impacto |
|---|---|---|
| Pilar circular | MENCIONADO na Pg 6 ("grade para pilares circulares") mas sem regras detalhadas | ALTO -- pilares circulares precisam de grade curvada, nao retangular |
| Pilar em L | PRESENTE na Pg 3 (codigo especial com cw=0) mas regras de sarrafo/chapa para quinas internas e externas nao documentadas | ALTO |
| Pilar em T ou U | AUSENTE | MEDIO -- raro mas existe |
| Viga em balanco | AUSENTE | ALTO -- escoramento e radicalmente diferente |
| Viga inclinada/rampa | AUSENTE | MEDIO |
| Viga alta (h > 1m) | AUSENTE | ALTO -- precisa de travamento intermediario |
| Laje em balanco | AUSENTE | ALTO |
| Laje com recorte curviline | AUSENTE | MEDIO |
| Pilar de borda (2 faces livres) | AUSENTE | ALTO -- travamento diferente |
| Pilar de canto (1 face livre) | PRESENTE implicitamente no pilar L | MEDIO |

---

## 4. QUALIDADE DAS DECISION TREES

### 4.1 Decision Tree de Pilares (Pg 9)

A Pg 9 implementa 4 fluxos de decisao:

**FLUXO 1 -- Tipo de Painel:**
- Condicao: presenca de SARR_2.2x7 no layer
- SIM -> SARRAFEADO / NAO -> GRADE
- **Analise:** Logica correta para deteccao, mas INCOMPLETA. Pode haver paineis sarrafeados sem a layer SARR_2.2x7 (outros tipos de sarrafo). Deveria verificar ANY layer SARR_*.

**FLUXO 2 -- Tipo de Sarrafo por Secao:**
- max(X,Y) < 200mm -> SARR_2.2x7
- max(X,Y) < 400mm -> SARR_3.5x7
- else -> SARR_7x7
- **Analise:** Thresholds 200mm e 400mm sao EMPIRICOS. Pilares de 19x229mm (caso real no DXF) tem max=229mm -> SARR_3.5x7, o que parece excessivo para um pilar estreito. A regra deveria considerar AMBAS as dimensoes, nao apenas max.

**FLUXO 3 -- Sarrafo por PD:**
- PD > 3.0m -> SARR_2.2x10
- else -> SARR_2.2x7
- **Analise:** O threshold de 3.0m e razoavel -- PE direito > 3m gera maior pressao lateral. CORRETO.

**FLUXO 4 -- Tipo de Pilar:**
- max(X,Y) < 200mm -> PEQUENO
- max(X,Y) < 400mm -> MEDIO
- else -> GRANDE
- **Analise:** Classificacao razoavel, mas nao afeta diretamente o output do robo. Precisa de acao vinculada a cada classe.

**Achado CRITICO:** Falta um fluxo para decidir a QUANTIDADE de paineis por face. Falta um fluxo para decidir se a face usa 1, 2, 3 ou mais paineis empilhados. Falta um fluxo para secao nao-retangular.

### 4.2 Decision Trees de Vigas (Pg 27-30)

**Pg 27 -- Tipo Lateral:**
- SARR_2.2x7 presente? SIM -> sarr / NAO -> grade
- Comprimento < 3.0m? SIM -> HT20CT esp=400mm / NAO -> esp=600mm
- **Analise:** A segunda arvore e INVERTIDA em relacao a intuicao: vigas MAIS LONGAS deveriam ter MAIS escoras (menor espacamento). O script diz comp < 3m -> esp=400mm (mais denso) e comp >= 3m -> esp=600mm (menos denso). Isto parece **ERRADO** -- vigas mais longas precisam de mais apoio, nao menos.

**Pg 28 -- Tipo Fundo:**
- largura > 600mm? SIM -> grade / NAO -> sarrafeado
- n_paineis = floor(comp / larg_painel)
- sobra < 50mm? SIM -> ajustar ultimo painel
- **Analise:** Threshold de 600mm para grade no fundo e razoavel. Regra de sobra minima e correta.

**Pg 29 -- Sistema de Ancoragem:**
- altura > 400mm? SIM -> garfo / NAO -> opcional
- PD > 2.5m? SIM -> PRESILHA 2+3 / NAO -> apenas PRESILHA 1
- **Analise:** Threshold de 400mm para garfos e razoavel (vigas de 40cm+ de altura geram pressao significativa). PD > 2.5m para presilhas extras e correto.

**Achado ALTO:** A logica de espacamento HT20CT na Pg 27 parece invertida. Precisa revisao tecnica com engenheiro de escoramento.

### 4.3 Thresholds

| Threshold | Valor | Padrao Industria | Veredicto |
|---|---|---|---|
| 200mm (pilar pequeno) | max(X,Y) < 200 | Nao ha padrao ABNT. Fabricantes como SH classificam pilares < 30cm como "pequenos". 200mm (20cm) e conservador. | ACEITAVEL |
| 400mm (pilar medio) | max(X,Y) < 400 | Razoavel. | ACEITAVEL |
| 600mm (fundo grade) | largura_viga > 600 | Grade para FV de viga larga e pratica comum. | CORRETO |
| 3.0m (PD sarrafo) | PD > 3.0m | PE direito > 3m gera maior pressao lateral. Coerente. | CORRETO |
| 400mm (garfo) | altura_viga > 400 | Vigas de 40cm+ tipicamente tem garfos. | CORRETO |
| 2.5m (presilha) | PD > 2.5m | Razoavel para presilhas extras. | CORRETO |

---

## 5. JSON SCHEMAS

### 5.1 Schema de Pilares (Pg 10)

```json
{
  "pilar_id": "str",
  "secao_x": "int (mm)",
  "secao_y": "int (mm)",
  "altura_pd": "float (m)",
  "nivel_saida": "float",
  "nivel_chegada": "float",
  "tipo_painel": "\"sarr\"|\"grade\"",
  "esp_painel": "int (mm)",
  "sarrafo_tipo": "str",
  "com_grade": "bool",
  "chapa_aci": "int",
  "layer_concreto": "str"
}
```

**Campos Faltantes:**

| Campo | Tipo | Motivo |
|---|---|---|
| `n_paineis_face_a` | int | Robo precisa saber quantos paineis por face |
| `n_paineis_face_b` | int | Idem |
| `orientacao_paineis` | str | Horizontal ou vertical |
| `laje_adjacente_a` | str | Nome da laje de cada lado (dado existente no Bolt) |
| `laje_adjacente_b` | str | Idem |
| `template_abcd` | str | Qual template ABCD usar (Padrao, ROCONTEC, etc.) |
| `secao_tipo` | str | "retangular", "L", "circular" |
| `parafuso_tipo` | str | PAR_ESQ, PAR_DIRV, INI_PAR |
| `folga_forma` | float (mm) | Folga entre concreto e painel interno |
| `projeto_id` | str | FK para projeto |
| `pavimento` | str | Identificacao do pavimento |
| `coordenadas_xy` | [float, float] | Posicao no plano do pavimento |

**Tipo de dados incorretos:**
- `tipo_painel` deveria ser `enum`, nao `str` livre
- `sarrafo_tipo` deveria ser `enum` com valores validos
- `nivel_saida` e `nivel_chegada` deveriam ter unidade explicita (mm ou m)

### 5.2 Schema de Vigas (Pg 30)

```json
{
  "viga_id": "str",
  "largura_viga": "int (mm)",
  "altura_viga": "int (mm)",
  "comprimento": "float (m)",
  "tipo_lateral": "\"sarr\"|\"grade\"",
  "tipo_fundo": "\"sarr\"|\"grade\"",
  "tem_garfo": "bool",
  "esp_garfo": "int (mm)",
  "qtd_ht20ct": "int",
  "nivel_saida": "float",
  "nivel_chegada": "float"
}
```

**Campos Faltantes:**

| Campo | Tipo | Motivo |
|---|---|---|
| `n_segmentos` | int | Vigas podem ter segmentos (tramos) |
| `pilares_apoio` | list[str] | Pilares de apoio em cada extremidade |
| `lajes_adjacentes` | list[str] | Lajes que a viga suporta |
| `label_a` | str | Presente no script mas ausente no schema |
| `label_b` | str | Idem |
| `cmt_a` | float | Comprimento da lateral A |
| `cmt_b` | float | Comprimento da lateral B |
| `esp_presilha` | int (mm) | Espacamento das presilhas |
| `tipo_presilha` | str | MET1, MET2 |
| `contra_flecha` | float (mm) | Para vigas longas |
| `balanco` | bool | Se a viga e em balanco |

### 5.3 Schema de Lajes (Pg 10)

```json
{
  "laje_id": "str",
  "largura_laje": "int (mm)",
  "comprimento_laje": "int (mm)",
  "tipo_painel": "str",
  "esp_painel": "int (mm)",
  "sarrafo_tipo": "str",
  "pilares_recorte": "list",
  "nivel_laje": "float",
  "orientacao": "\"h\"|\"v\""
}
```

**Campos Faltantes:**

| Campo | Tipo | Motivo |
|---|---|---|
| `espessura_laje` | int (mm) | d=12, d=15, d=20 -- essencial para calculo de carga |
| `area_m2` | float | Presente no parametros mas ausente no JSON schema |
| `ilhas` | list[polygon] | Aberturas/shafts |
| `vigas_borda` | list[str] | Vigas que delimitam a laje |
| `pontaletes_grade` | object | Grid de posicionamento dos pontaletes |
| `tipo_escoramento` | str | "pontalete_madeira", "escora_metalica", "torre" |
| `reaproveitamento` | list[polygon] | Regioes marcadas para reuso |
| `contorno` | polygon | Contorno completo da laje (nao retangular) |
| `nivel` | float | Duplicado com nivel_laje -- consolidar |
| `com_reaprov` | bool | Presente nos parametros mas ausente no schema |

---

## 6. SCORE DE QUALIDADE TECNICA

### 6.1 Precisao das Medidas: 13/20

- (+) Pontalete 7x7cm, SARR_3.5x7, SARR_7x7 sao dimensoes reais
- (+) Espessura de 22mm e consistente em todo o sistema
- (-) 22mm nao e espessura padrao de compensado resinado (padrao = 20mm)
- (-) SARR_2.2x7 mistura nomenclatura compensado/sarrafo
- (-) Chapa 4x176mm e valor derivado, nao padrao de mercado
- (-) Pontalete descrito como 7x7mm (milimetros!) ao inves de 7x7cm
- (-) Variantes SARR_2.2x15, SARR_2.2x20, SARR_7x10 sem regras de uso

### 6.2 Completude das Regras: 12/20

- (+) 4 fluxos de decisao para pilares
- (+) 4 decision trees para vigas (pg 27-30)
- (+) Regras de juntas, pontaletes, sarrafos bem definidas
- (-) Zero tolerancias dimensionais
- (-) Sequencia de montagem ausente
- (-) Calculo de quantidade de paineis por face ausente
- (-) Regra de sobreposicao de quinas ausente
- (-) Pressao do concreto fresco nao calculada
- (-) Contra-flecha para vigas longas ausente
- (-) Logica HT20CT possivelmente invertida (vigas longas = menos escoras?)

### 6.3 Terminologia: 12/15

- (+) SARRAFO DE PRESSAO, PRESILHA, GARFO, TENSOR -- corretos
- (+) FV (fundo de viga) -- padrao
- (+) PONTALETE, BARRA ANCORAGEM -- corretos
- (-) HT20CT -- nao encontrado como termo padrao na industria
- (-) PA-022x100 -- codificacao interna, nao padrao
- (-) CMT -- abreviacao nao padrao

### 6.4 Decision Trees: 12/20

- (+) 4 fluxos de pilar com logica clara
- (+) 4 fluxos de viga com decisoes vinculadas
- (+) Thresholds razoaveis e consistentes
- (-) Logica HT20CT possivelmente invertida
- (-) Fluxo 2 (sarrafo por secao) usa apenas max(X,Y), nao ambas dimensoes
- (-) Sem fluxo para secoes nao-retangulares
- (-) Sem fluxo para quantidade de paineis
- (-) Sem fluxo para LAJES (nenhuma decision tree para lajes!)
- (-) Sem fallback ou tratamento de erro nos fluxos

### 6.5 JSON Schemas: 8/15

- (+) Campos obrigatorios vs opcionais diferenciados
- (+) Tipos de dados basicamente corretos
- (+) Exemplos de valores incluidos
- (-) 11 campos faltantes no schema de pilares
- (-) 11 campos faltantes no schema de vigas
- (-) 9 campos faltantes no schema de lajes
- (-) Sem validacao (min/max, ranges)
- (-) Sem referencia cruzada entre schemas (pilar<->viga<->laje)
- (-) Unidades inconsistentes (mm vs m vs sem unidade)

### 6.6 Casos Especiais Cobertos: 4/10

- (+) Pilar em L presente (Pg 3, Pg 16-17)
- (+) Grade vs sarrafeado diferenciado
- (+) Viga com/sem garfo (4 variantes corte, Pg 7)
- (+) Reaproveitamento de paineis de laje
- (-) Pilar circular -- mencionado sem regras
- (-) Pilar T/U ausente
- (-) Viga em balanco ausente
- (-) Viga alta (>1m) ausente
- (-) Laje em balanco ausente
- (-) Pilar de borda/canto ausente

---

## TOTAL: 61/100

| Dimensao | Score | Peso |
|---|---|---|
| Precisao das medidas | 13/20 | |
| Completude das regras | 12/20 | |
| Terminologia | 12/15 | |
| Decision trees | 12/20 | |
| JSON schemas | 8/15 | |
| Casos especiais | 4/10 | |
| **TOTAL** | **61/100** | |

**Classificacao: C+ (Adequado para MVP, insuficiente para producao)**

---

## 7. LISTA PRIORIZADA DE CORRECOES

### CRITICO (Impede geracao correta de DXF)

| # | Item | Descricao | Acao |
|---|---|---|---|
| C1 | Unidade pontalete | Descrito como 7x7mm quando deveria ser 7x7cm (70x70mm). Afeta todos os calculos se usado como entrada para o robo. | Corrigir todas as referencias para "7x7cm" ou "70x70mm" |
| C2 | Tolerancias ausentes | Zero tolerancias documentadas. Robo nao sabe a folga entre concreto e forma. | Adicionar campo `folga_forma` (tipico: 5-10mm) em todos os schemas |
| C3 | Quantidade de paineis | Nenhuma formula para calcular quantos paineis por face do pilar. | Adicionar fluxo: n = ceil(dim_face / largura_painel) + regra de sobra minima |
| C4 | Sobreposicao de quinas | Quando 2 paineis se encontram na quina, qual sobrepoe qual? | Documentar regra: paineis AB sobrepoe paineis CD (ou vice-versa) |

### ALTO (Causa erros em subconjuntos de casos)

| # | Item | Descricao | Acao |
|---|---|---|---|
| A1 | HT20CT inversao | Vigas longas recebem espacamento MAIOR (600mm) quando deveriam receber MENOR. | Revisar com engenheiro: provavel inversao da logica na Pg 27 |
| A2 | Sarrafo por secao | Fluxo 2 usa apenas max(X,Y). Pilar 19x229mm teria sarrafo de pilar medio quando e estreito. | Considerar min(X,Y) tambem, ou area total |
| A3 | Decision tree lajes | Lajes nao tem NENHUMA decision tree. O robo nao sabe quando usar pontalete vs escora metalica. | Criar decision tree completa para lajes |
| A4 | Templates ABCD | 8 templates mencionados na ficha Bolt mas ZERO detalhes nas fichas instrutivas. | Documentar criterios de selecao de cada template |
| A5 | Parafusos/fixacao | Sistema de parafusos completamente ausente das fichas instrutivas. | Adicionar pagina(s) sobre tipos de parafusos e posicionamento |
| A6 | Esp. 22mm hardcoded | Espessura de 22mm nao e padrao de mercado e esta hardcoded em todo o script. | Parametrizar e validar com fornecedor (20mm ou 21mm?) |
| A7 | Sequencia montagem | Ordem de instalacao das faces nao documentada. | Adicionar fluxo: faces opostas primeiro -> adjacentes -> sarrafos -> chapas -> pontaletes |

### MEDIO (Melhoria de qualidade)

| # | Item | Descricao | Acao |
|---|---|---|---|
| M1 | HT20CT nomenclatura | Termo nao encontrado na industria. | Documentar origem ou usar "Viga H20" |
| M2 | Chapa 176mm | Valor derivado, nao produto padrao. | Documentar formula de calculo: chapa_h = f(pilar_dim, painel_esp) |
| M3 | SARR_2.2x15/x20/7x10 | Layers definidos sem regra de uso. | Adicionar condicoes de uso ou remover do catalogo |
| M4 | Contra-flecha | Vigas >6m precisam (NBR 14931). | Adicionar campo `contra_flecha` e regra PD >6m |
| M5 | JSON schema validacao | Sem min/max, sem enum explicito. | Adicionar constraints: secao_x in [100..1200], tipo_painel in [sarr, grade] |
| M6 | Referencia cruzada | Schemas de pilar/viga/laje nao se referenciam. | Adicionar FKs: viga.pilares_apoio -> pilar.pilar_id |
| M7 | Pilar circular | Mencionado mas sem regras. | Criar secao "Pilares Circulares" com calculo de numero de segmentos de grade |
| M8 | Pressao concreto | Nao calculada, afeta dimensionamento. | Adicionar formula: P = gamma_c * h * Kf (NBR 14931 secao 8) |

---

## FONTES

- [NBR 14931:2004 - Execucao de Estruturas de Concreto](https://docente.ifrn.edu.br/valtencirgomes/disciplinas/construcao-de-edificios/nbr-14931-2004-execucao-de-estruturas-de-concreto-procedimento)
- [SH Catalogo Formas, Andaimes e Escoramentos](https://sh.com.br/pt/catalogos/)
- [Compensado Resinado - Tudo Certo Madeiras](https://tudocertomadeiras.com.br/compensado-resinado/)
- [Pontalete de Madeira Pinus 7x7cm - Comadam Madeiras](https://comadam.com.br/produtos/pontalete-de-madeira-pinus-7x7-cm/)
- [Barra de Ancoragem - IW8 Forma para Pilar](https://www.barradeancoragem.com.br/forma-para-pilar-de-concreto/)
- [Compensados Dourados - Resinado/Plastificado/Naval](https://www.compensadosdourados.com/compensados/)
- [HT20plus - AEC Web](https://www.aecweb.com.br/produto/sistema-de-escoramento-viga-de-sustentacao-ht-20plus/36982)
- [SINAPI Catalogo de Insumos - Sarrafo](https://orcamentor.com/insumo/4509/)
- [IW8 - Tipos de Forma e Escoramento](https://www.iw8.com.br/pdf/tipos-de-forma-execucao-de-formas-escoramentos-de-formas-prazos-para-desforma-30072012121054.pdf)

---

## NOTA DE CONFIANCA

Este relatorio foi elaborado cruzando:
1. Analise estatica do codigo Python (2794 linhas)
2. Analise de conteudo das 3 fichas Markdown (Bolt, Crane, Slab)
3. Pesquisa em catalogos de fabricantes brasileiros (SH, IW8, Comadam)
4. Pesquisa em normas brasileiras (NBR 14931, NBR 6118, NBR 7190)
5. Pesquisa de produtos em fornecedores (compensado resinado, pontaletes, chapas)

**Nivel de confianca:** 75% (MEDIO-ALTO)
- Alta confianca nas validacoes de produtos de mercado (pontaletes, compensados)
- Media confianca nos thresholds de decision trees (empiricos, dependem de fabricante)
- Baixa confianca na validacao de HT20CT (termo nao encontrado em catalogo publico)

---

*Atlas -- Analyst Agent | CAD:FormworkEngineering-AIOS | 2026-03-19*
