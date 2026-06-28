# LOOPING-EVOLUCAO-N2 — Visão × Ficha Motor × Iteração Humana

Versao: 1.0  
Data: 2026-06-28  
Autor: Thierry + Agente CLI  
Escopo: procedimento GENÉRICO aplicável a qualquer classe estrutural (LV, FV, PIL, LAJ, …).

## 0. Propósito

Este documento descreve o looping de evolução da interpretação N2 que deve ser aplicado
classe a classe para garantir que o motor reverso consegue extrair da imagem N2 TUDO que
é necessário para o gerador N4 reproduzir fielmente o recorte.

O processo combina três fontes de verdade:

| Fonte | O que é |
|-------|---------|
| **Imagem N2** (vision) | O que existe no desenho STOG humano real |
| **Ficha Motor** (extração geométrica) | O que o motor reverso consegue extrair do DXF |
| **Iteração Humana** | O que o dono corrige/confirma quando os dois anteriores divergem |

O resultado de cada ciclo é:
- Um motor mais preciso (código)
- Um doc de aprendizado atualizado (por classe)
- Um schema de ficha mais rico (novos campos quando necessário)

## 1. Quando Iniciar um Looping Para Uma Classe

Pré-condições:
- A classe tem pelo menos 1 recorte N2 disponível em `DADOS-OBRAS/`.
- O motor reverso da classe existe (`scripts/motor_reverso_{classe}.py`).
- O gerador N4 da classe existe (`scripts/gerar_{classe}_dxf_stog.py`).

Gatilho para iniciar:
- A comparação visual N2 vs N4 ainda mostra divergência semântica relevante
  (elemento faltando, dimensão errada, estrutura não reproduzida).

## 2. Protocolo Por Item (Ciclo Unitário)

Para cada item alvo (ex.: V301):

### Passo 1 — Ler N2 por Vision

1. Renderizar o recorte N2 em PNG (usar `comparar_ficha_lv_vision.py` ou equivalente).
2. Ler a imagem com vision e descrever no formato estruturado da classe:
   - Quantidade de elementos de topo (segmentos, painéis, seções, etc.)
   - Dimensões de cada elemento (largura, altura, espessuras)
   - Detalhes especiais: aberturas, degraus, reaproveitamento, grades, pilares
   - Textos de referência: vizinhos, continuidade, labels
3. Registrar em `vision_ficha.json` dentro da pasta da rodada.

### Passo 2 — Ler N2 pelo Motor

1. Executar `extrair_ficha_{classe}(recorte_path, elem_id)`.
2. Registrar em `extractor_ficha.json`.

### Passo 3 — Comparar e Diagnosticar

Comparar campo a campo:

| Campo | Vision diz | Motor diz | Diagnóstico |
|-------|-----------|-----------|-------------|
| contagem elementos | N | M | `extractor_bug` / `schema_gap` / `render_bug` |
| dimensões | X cm | Y cm | `extractor_bug` / `vision_prompt_bug` |
| detalhe especial | presente | ausente | `schema_gap` se campo não existe no schema |

Categorias de diagnóstico:
- `extractor_bug`: dado visível na imagem, motor erra a geometria.
- `vision_prompt_bug`: dado existe no DXF, vision não leu certo.
- `render_bug`: PNG não exibe o dado (crop ruim, resolução baixa).
- `schema_gap`: campo não existe no schema atual — precisa criar.
- `ambiguous_stog`: convenção STOG ambígua — perguntar ao dono.

### Passo 4 — Iteração Humana (quando necessário)

O dono intervém quando:
- Vision e motor discordam sobre algo visualmente claro.
- Uma convenção STOG desconhecida aparece.
- Um campo novo é identificado mas não está no schema.

O dono confirma:
- O valor correto do campo divergente.
- A regra geométrica que explica a divergência.
- Se o campo deve ser adicionado ao schema ou se é artefato.

### Passo 5 — Refinar o Motor

Para cada `extractor_bug` confirmado:
- Adicionar/corrigir função de extração geométrica.
- Regra deve ser genérica (não hardcode por item).
- Validar que a correção não regride outros itens do lote.

Para cada `schema_gap` confirmado:
- Adicionar campo ao schema da ficha da classe.
- Atualizar motor para extrair o campo.
- Atualizar gerador N4 para usar o campo.
- Documentar no doc de aprendizado da classe.

### Passo 6 — Documentar o Aprendizado

Cada achado vira uma entrada no doc de aprendizado da classe (`{CLASSE}-COMPREENDER-*.md`):

```
N. `{CLASSE}/AB/nome_da_regra`: [descrição da regra]
   - Sintoma visual: [o que se vê na imagem]
   - Regra de interpretação: [como extrair/interpretar]
   - Campos afetados: [lista de campos]
   - Exemplos positivos: [vigas/itens que confirmam]
   - Exemplos negativos: [falsos positivos conhecidos]
```

### Passo 7 — Expandir o Lote

Após validar 1 item:
- Repetir para 3-5 itens do mesmo pavimento.
- Verificar se a regra nova é estável no lote.
- Se sim, marcar a regra como `consolidada`.
- Se não, refinar e re-testar.

## 3. Formato de Leitura Vision Por Classe

Cada classe tem um formato canônico de leitura vision. O agente CLI deve usar
esse formato ao descrever o que vê, para facilitar a comparação com a ficha motor.

### LV (Lateral de Viga)

```
Quantidade de Segmentos Face A: N
Quantidade de Segmentos Face B: N
Quantidade de Painéis: N (N_A Face A + N_B Face B)
Visões de Corte: N

Segmento A1 "label":
  P1: LarguraxAltura  sarrafos H 7×(L-7), V 7×H  [flags: is_first, laje_sup=X]
  P2: LarguraxAltura  sarrafos H 7×(L-7), V 7×H
      abertura CORNER: WxH  [sarrafe V 7 ao lado]
  laje topo: X  |  texto inic: REF_ESQ  texto fim: REF_DIR

Segmento A2 (espelho de A1): [descrever simetricamente]
...

Visão de Corte 1 "label":
  b=Xcm  h_section=Xcm  h_total=Xcm  laje_sup=Xcm  laje_inf=Xcm
  [fechamento NX se repete]
```

### FV (Fundo de Viga)

```
[a definir na primeira sessão de looping FV]
```

### PIL (Pilar)

```
[a definir na primeira sessão de looping PIL]
```

### LAJ (Laje)

```
[a definir na primeira sessão de looping LAJ]
```

## 4. Campos-Alvo Por Prioridade (LV como referência)

A ordem de ataque recomendada em cada looping:

| Prioridade | Campo | Status LV |
|-----------|-------|----------|
| P1 | Contagem de segmentos A/B | ✓ estável |
| P1 | Contagem de visões de corte | ✓ estável |
| P1 | `largura_cm` por segmento | ✓ estável (sub-widths corretos) |
| P2 | `height1` por segmento (degrau) | ✓ refinado 2026-06-28 |
| P2 | `laje_sup/inf` global | parcial (laje=7 vs 15 em V301) |
| P2 | `raw_holes` / aberturas de canto | ✓ adicionado 2026-06-28 |
| P3 | Espelho por face_unit (2 instâncias) | documentado, N4 a implementar |
| P3 | `laje_sup_local` por segmento | ✓ já extraído |
| P3 | `reuse` e `reuse_regions` | ✓ já extraído |
| P4 | Sub-widths → agrupamento em painéis visuais | gap conhec., não refin. ainda |
| P4 | Textos de referência (text_left/right) | ✓ já extraído |

## 5. Rastreamento de Progresso

Registrar em cada sessão de looping:

```markdown
## Sessão YYYY-MM-DD — Classe {CLASSE} — Item {ID}

### O que vision leu que o motor não capturava:
- [campo 1]
- [campo 2]

### Refinamentos implementados:
- [mudança 1 no código / função]
- [mudança 2]

### Campos pendentes (próxima sessão):
- [campo A]

### Perguntas ao dono:
- [pergunta 1] → resposta: [resposta]
```

## 6. Aplicando a Outras Classes

Para iniciar o looping em uma nova classe:

1. Escolher 1 item representativo (de preferência com variedade: degraus, aberturas, reaproveitamento).
2. Renderizar o recorte N2 em alta resolução.
3. Ler com vision no formato canônico da classe (definir o formato se não existir).
4. Pedir ao dono confirmação/correção.
5. Comparar com extrator atual.
6. Diagnosticar gaps.
7. Refinar motor.
8. Documentar em `{CLASSE}-COMPREENDER-*.md`.
9. Expandir lote.

Classe seguinte sugerida após LV: **Visão Corte LV** (seções transversais), depois FV.

## 7. Referências

- LV aprendizado: `docs/LV-COMPREENDER-INTERPRETACAO-FICHAS-N2-N4.md`
- LV loop masterplan: `docs/MASTERPLAN-LOOP-LV-N2-VISION-N4.md`
- Schema ficha granular: `docs/SCHEMA-FICHA-GRANULAR.md`
- Motor LV: `scripts/motor_reverso_lv.py`
- Gerador LV N4: `scripts/gerar_lv_dxf_stog.py`
