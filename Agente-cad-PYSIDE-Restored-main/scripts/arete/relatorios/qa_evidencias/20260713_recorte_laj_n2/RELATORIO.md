# Recorte N2 LAJ — refinamento por evidência local do STOG

Data: 2026-07-13

## Causa observada

O recortador aceitava o primeiro `bbox` que fechava. Em pranchas com uma linha
estrutural contínua, esse `bbox` podia conter várias lajes da mesma fileira;
em lajes estreitas sem duas bordas longas locais, a única alternativa era a
dimensão vinda da ficha N1.

Isso explica o recorte contaminado de L51 visto no Hub: a janela persistida
antiga tinha aproximadamente `652 x 580`, embora o painel local medisse cerca
de `405 x 71`.

## Alteração universal

`src/core/recorte_motor.py` agora:

1. reduz um candidato estrutural se ele inclui o label de outra laje;
2. lê cadeias horizontal/vertical de cotas do próprio STOG, separadas pela
   célula entre labels vizinhos, para propor um bbox independente de N1;
3. rejeita a proposta se ela ainda capturar outra label;
4. pontua os candidatos por conteúdo local (label próprio, linhas, cotas,
   área e contaminação) e só usa N1 como compatibilidade quando nenhuma prova
   independente atinge 80 de confiança.

Não há regra por item, obra ou pavimento. Recortes com `status=aprovado` não
foram escritos nem sobrescritos.

## Microciclo seco — 2º PAV, Obra_TREINO_1

Fonte: `ALIMONTI - PARAISO - 2° PAV.- LJ - R00.dxf`.

| Medida | Antes | Depois |
|---|---:|---:|
| Itens no lote | 30 | 30 |
| Recortes vazios | 0 | 0 |
| Confiança média | 52,4 | 89,5 |
| Itens abaixo de 70 | 14 | 1 (`L67`, 69,1) |

Leitura visual manual do agente nos PNGs secos:

- `L51`: painel, apoios e cotas locais preservados; sem a faixa vertical
  contaminante mostrada no Hub.
- `L55`: deixou de capturar a fileira inteira L51–L57 e ficou no detalhe local.
- `L75`: a proposta que incluía L76 foi rejeitada; caiu no fallback conservador.
- `L67`: permanece abaixo do limiar e deve continuar para revisão humana, sem
  promoção automática.

PNGs secos: `scripts/arete/tmp/laj_recorte_dryrun_2pav_all_refined_v3/`.
Eles não alteram DB nem dados de obra.

## Regressão

- Testes: `18 passed` (recorte/dimensões e motores LAJ relacionados).
- `arete_runner --classe LAJ --pav 13_PAV`: `31 PASS / 0 FAIL / 0 BLOCKED`,
  Arete numérico 100%.
- O G2-V CLI foi gerado para L318/L319/L326 em
  `scripts/arete/relatorios/g2v/20260713_032018/`; ele não foi usado para novo
  selo porque compara os artefatos 13º já persistidos, não estes DXFs secos.
  A imagem crua ainda mostra a diferença histórica de contexto N2×N4, portanto
  nenhum PASS visual novo foi declarado por este refinamento.

## Próximo passo seguro

No Diagnostic Reverse Hub, processe somente os recortes LAJ **não aprovados**
do 2º PAV e faça revisão visual prioritária de L67. O fluxo existente preserva
os `aprovado`; após a revisão humana, os novos recortes podem virar referência
N2 para os próximos pavimentos.
## Ciclo 2 — rejeição de spans de prancha

Ao varrer os 69 registros LAJ ainda sem aprovação humana, os 25 abaixo de 80
tinham uma assinatura objetiva: bordas estruturais de **prancha**, longas e
finas, eram tomadas por uma laje local. Exemplos: `3146×87`, `3028×2` e
`2400×423` unidades. Isso não é uma laje: é uma cadeia que atravessa vários
painéis ou uma linha de referência.

O seletor agora descarta candidatos estruturais com largura/altura fora de
`45..1250` / `45..850` ou proporção maior que `12:1`; nessas situações ele volta
ao enquadramento local delimitado por labels vizinhos. Sem hardcode de obra ou
ID. Em lote seco, os casos grotescos passaram, por exemplo, de `3146×87` para
`1223×154`, `2403×45` para `609×447`, `1716×61` para `583×658` e `3028×2` para
`663×602`. Nenhum dado humano ou DB foi alterado.

Validação do código: `21 passed` nos testes de recorte/motores LAJ, incluindo
o novo caso de span longo e fino.

## Ciclo 3 — contorno estrutural preservado

O enquadramento menor resolveu a contaminação, mas revelou uma segunda falha:
o clipping aplicava a mesma borda rígida aos painéis e às linhas de contexto.
Assim, marco de contorno, apoio e viga eram truncados exatamente onde definem a
área da laje. A coleta agora mantém os painéis dentro da caixa e concede uma
faixa externa de 18 unidades somente a linhas/polylines fora das layers
`PAINEIS/PAINEL`. É uma regra por papel geométrico, não por obra/item.

No recorte seco de L51 do 2º pavimento, o resultado passou a reter 92 entidades
e estender o contexto estrutural de forma limitada, sem recuperar a antiga faixa
vertical contaminante. Testes: `21 passed`; nenhum dado de produção foi escrito.

## Ciclo 4 — marcos residuais

Os remanescentes de todos os pavimentos mostraram que parte dos marcos é layer
`0`, que antes era filtrado integralmente, e que a margem estrutural de 18
unidades ainda terminava antes das vigas de apoio. O motor agora aceita layer
`0` apenas para linhas/polylines (nunca textos/hatches genéricos) e amplia a
faixa exclusiva de contexto estrutural para 32 unidades; painéis continuam
estritamente limitados ao recorte.

Em lote seco do 14º pavimento, a retenção cresceu sem tocar dados humanos:
`L406` 214→248 entidades, `L409` 97→111 e `L416` 41→48. Os três permanecem
pendentes de veredito humano; este ciclo não declarou selo visual.

## Ciclo 5 — fechamento também para hipóteses estruturais

O fechamento por segmentos de painéis era aplicado apenas quando o motor caía no
fallback Voronoi. Recortes definidos por borda estrutural ou cota local podiam,
portanto, acertar a região central e ainda perder a faixa de marco periférico.
Agora toda hipótese passa por esse fechamento, com os mesmos limites de tamanho
e proteção contra labels vizinhos. Em amostra seca: L67 (2º), L406 (14º) e L503
(cobertura) ampliaram o contorno local sem cruzar outro label. Testes: `21
passed`; regressão LAJ/13º: `31 PASS / 0 FAIL / 0 BLOCKED` (Arete numérico 100%).
