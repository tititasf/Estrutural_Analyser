# Reconciliação de diagnósticos auto — PIL, FV, LV (03/07/2026)

**Story:** `docs/stories/STORY-EXEC-05-RECONCILIACAO-CONCORDANCIA.md`
**Escopo:** só triagem/logs. Nenhum motor, gerador ou arquivo de UI foi tocado nesta
sessão. Nenhum "aberto real" foi corrigido — todos estão listados abaixo para virarem
story própria depois.

**⚠️ Nota de concorrência:** durante esta reconciliação, outra sessão modificou
`scripts/arete/relatorios/triagem_erros/Obra_TREINO_1_13_PAV_lajes.jsonl` (23 novas
entradas, causa `g1_borda_uniao_tipo_entidade`, todas `status: verificado`) e deixou
`scripts/gerar_lj_dxf_stog.py` com mudanças não commitadas — aparentemente
`STORY-EXEC-04-LAJ-LINHAS-HORIZONTAIS.md` sendo executada em paralelo agora mesmo. Os
números abaixo são o estado observado no momento da medição (estado headless
`gerado_em: 2026-07-03T11:53:14`); LAJ especificamente pode já ter mudado de novo.

## Resumo por classe

| Classe | Alertas auto | Resolvido | Aberto real | Sem par N2/N1 (estrutural) | Fora de escopo |
|---|---|---|---|---|---|
| PIL | 24 | 0 | 13 | 11 | 2 (não-retangulares, já excluídos pelo próprio script) |
| FV | 34 | 0¹ | 22 | 12 | — |
| LV | 20 | 0 | 14 | 6 | — |
| LAJ (referência, feita em sessão anterior) | 4 | — | 2 (L318, L319) confirmados + **2 corroborados por outro diagnóstico concorrente (L312, L315)** | — | — |

¹ Os 6 itens já fechados por `STORY-EXEC-01-FV-SARR5CM.md` (V310, V327, V331, VF202,
VF203, VF301 — causa `g2_config_layer_robo_ausente`) **continuam "aberto real" no
diagnóstico de dimensão N1×N2** — aquele fix resolveu um problema diferente (config do
comparador visual G2, quais layers `SARR_*` entram no score), não a extração de
comprimento/largura que este diagnóstico mede. Não é uma contradição; são dois eixos de
qualidade independentes sobre os mesmos itens.

Nenhum item resgatado nesta rodada tinha sido corrigido por trabalho de motor
específico para PIL/FV/LV desde que os diagnósticos foram criados (02-03/07) — diferente
de LAJ, onde 14/16 alertas humanos de 02/07 já tinham sido resolvidos pelo fix de
`slab_tracer.py` da mesma sessão. Não houve mudança de motor em PIL/FV/LV neste período
(confirmado via `git log`/`git status` dos arquivos de motor de cada classe).

## PIL — 24 alertas, 13 abertos reais, 11 estruturais

**Estrutural (não é bug — 11 itens):** P41-P51 nunca passaram por engenharia reversa
(confirmado: zero linhas em `reverse_eng_fichas` para esses `elemento_id`, embora N1 os
detecte). Numeração consecutiva sugere um bloco/torre ainda não processado. Não é
candidato a story de motor — é candidato a "gerar fichas N2 para P41-P51" se for
prioridade do dono.

**Aberto real — padrão 1 (7 itens: P1, P2, P3, P4, P5, P6, P7):** largura N1 (bbox)
consistentemente **19.0** enquanto N2 declara 24 ou 30 — altura bate certinho em vários
casos (P1: 66=66). Verificado visualmente que o padrão é sistemático, não ruído de
um item isolado.

**Aberto real — padrão 2 (3 itens: P12, P13, P14):** os três compartilham o MESMO
`comprimento_bbox` decimal bizarro (`25.895625999999993`) — forte indício de detecção
geométrica degenerada (sliver/vértices errados), não coincidência.
**Verificado visualmente (P12):** o card N1 mostra um polígono minúsculo destacado onde o
recorte N2 mostra um pilar inteiro 98×19 — confirma que N1 capturou a geometria errada,
não é falso-positivo do comparador.

**Aberto real — outros (3 itens: P9, P15, P17):** P15 mostra formato completamente
diferente (N1 19×100 vs N2 45×45, provável polígono errado); P17 mostra comprimento
exatamente 2x o esperado (120 vs 60 — padrão de "duplicação/merge" parecido com o bug do
L318 de LAJ, mas em pilar). P9 é o mais brando (REGULAR, delta 0.08).

Itens: `P1, P2, P3, P4, P5, P6, P7, P9, P12, P13, P14, P15, P17`

## FV — 34 alertas, 22 abertos reais, 12 estruturais

**Estrutural (12 itens):** mistura de duas situações confirmadas via consulta direta ao
DB — `V309A` tem ficha N2 mas nenhum segmento N1 (viga real, cobertura incompleta);
`V313-318, V323-324, V326, V328` têm segmento N1 mas nenhuma ficha N2 (não passaram por
engenharia reversa); `VF203` genuinamente tem ZERO segmentos em qualquer categoria no
estado N1 (confirmado no log do headless: "Beam VF203 FV segments: 0").

**Aberto real — padrão dominante (a maioria dos 22):** largura bate quase sempre (19≈19,
14≈14); a divergência está quase toda em **comprimento total E contagem de segmentos**
(ex.: V301 tem 2 segmentos no N1 contra 16 no N2). **Verificado visualmente (V301):** o
recorte N2 mostra "V301.C" — uma viga CONTÍNUA real com 16 painéis físicos ao longo de
múltiplos apoios; o N1 só detecta 2. Isso é uma subdetecção real de segmentação do
Structural Analyzer em vigas contínuas longas, não artefato deste comparador. Vale
investigar se há um padrão de "viga com sufixo .C" tratada de forma incompleta pelo SA.

Itens: `V301, V302, V303, V304, V305, V306, V307, V308, V309, V310, V311, V319, V320,
V321, V322, V325, V327, V329, V330, V331, VF202, VF301`

## LV — 20 alertas, 14 abertos reais, 6 estruturais

**Estrutural (6 itens):** `V307, V309, V313, VF202` confirmados sem ficha N2 no DB;
`V13, VF203` — mais interessante — **têm ficha N2 mas ZERO segmentos em QUALQUER
categoria do estado N1** (não só lateral — verificado que não aparecem em nenhuma lista
de `segmentos`), ou seja, o SA não gerou nada pra esses dois, apesar de existir gabarito.
Vale investigar por que o SA falha completamente nesses dois.

**Aberto real (14 itens):** já documentado em detalhe no docstring de
`diagnostico_lv_n1_n2.py` (escrito ao construir o script, 03/07) — o número `120`
(também `60`, `100`, `55` em casos individuais) aparece como altura de segmento no N1
sem corresponder a NENHUM campo numérico da ficha N2 (nem `h_section`/`h_section_all`,
nem alturas de painel `panels_A/B`). Causa gravada como `schema_gap` (confiança 0.6, não
`extractor_bug`) porque a causa raiz real (valor-fallback do SA vs. campo do N2 ainda não
mapeado) não foi determinada — precisa de leitura humana antes de virar fix.

Itens: `V302, V304, V305, V308, V312, V314, V316, V318, V322, V324, V328, V329, V330,
VF301`

## LAJ — achado incidental durante esta reconciliação

Não fazia parte do escopo desta story (LAJ já foi reconciliada em sessão anterior), mas
o rollup abaixo captura o estado atual: `L312`, `L315` (novos, achados pelo diagnóstico
de dimensão desta sessão) coincidem EXATAMENTE com 2 dos itens que a
`STORY-EXEC-04-LAJ-LINHAS-HORIZONTAIS.md` já identificou de forma independente (causa
`g1_borda_uniao_tipo_entidade`, sobre round-trip de bordas de união, um problema
diferente do meu diagnóstico de dimensão bbox). Dois diagnósticos independentes
convergindo nos mesmos itens é sinal forte de que `L312`/`L315` (e `L318`/`L319`, que já
apareciam nos dois lados) são reais. Ver nota de concorrência no topo — aquela story
pode já ter fechado isso quando este documento for lido.

## Saída do rollup (`scripts/arete/triagem_concordancia.py`)

```
=== FV ===
  extractor_bug: 22 auto | 5 c/ par humano | concordância 0% | 22 aberto(s) real(is)
  g2_config_layer_robo_ausente: 0 auto | 0 c/ par humano | concordância sem dado | 0 aberto(s)
  schema_gap: 12 auto | 1 c/ par humano | concordância 0% | 12 aberto(s) real(is)

=== LAJ ===
  extractor_bug: 4 auto | 4 c/ par humano | concordância 0% | 4 aberto(s) real(is)
  g1_borda_uniao_tipo_entidade: 0 auto | 0 c/ par humano | concordância sem dado | 0 aberto(s)
  n1_overlap_viga: 0 auto | 0 c/ par humano | concordância sem dado | 0 aberto(s)
  n3_geometria_complexa_e_cotagem_n4: 0 auto | 0 c/ par humano | concordância sem dado | 0 aberto(s)

=== LV ===
  schema_gap: 20 auto | 0 c/ par humano | concordância sem dado | 20 aberto(s) real(is)

=== PIL ===
  extractor_bug: 13 auto | 0 c/ par humano | concordância sem dado | 13 aberto(s) real(is)
  schema_gap: 11 auto | 0 c/ par humano | concordância sem dado | 11 aberto(s) real(is)
```

**Leitura do rollup:** a "concordância 0%" de FV/LAJ não significa que o diagnóstico
automático está errado — significa que, nos itens onde existe marcação humana/de outra
sessão no MESMO item, a `causa_raiz` textual não bate literalmente (porque medem eixos
diferentes: G2 visual vs. dimensão N1×N2; G1 round-trip vs. dimensão N1×N2). PIL e LV não
têm par humano nenhum ainda — "concordância sem dado" é o estado honesto, não um zero.

## Itens abertos reais — candidatos a story própria (NÃO corrigidos aqui)

| Item(ns) | Classe | Causa observada | Evidência |
|---|---|---|---|
| P1,P2,P3,P4,P5,P6,P7 | PIL | largura N1 sistematicamente ~19 | padrão consistente, ver seção PIL |
| P12,P13,P14 | PIL | comprimento_bbox idêntico degenerado (25.8956...) | verificado visualmente (P12) |
| P9,P15,P17 | PIL | P15 formato trocado; P17 comprimento 2x | ver seção PIL |
| V301...VF301 (22 itens) | FV | vigas contínuas (.C) subdetectadas em segmentos | verificado visualmente (V301) |
| V302,V304,...VF301 (14 itens) | LV | altura de segmento sem campo N2 correspondente | ver docstring `diagnostico_lv_n1_n2.py` |
| L318, L319 | LAJ | overlap laje×viga (já conhecido) | ver §7 `ARETE-LOOP-PROCEDIMENTO-GERAL.md` |
| L312, L315 | LAJ | corroborado por 2 diagnósticos independentes | ver seção LAJ acima |

## Itens estruturais (cobertura incompleta, NÃO é bug de motor)

| Classe | Itens | Situação |
|---|---|---|
| PIL | P41-P51 (11) | sem ficha N2, nunca passou por engenharia reversa |
| FV | V309A, V313-318, V323-324, V326, V328, VF203 (12) | mistura de sem-N1 e sem-N2; VF203 tem zero segmentos em qualquer categoria |
| LV | V307,V309,V313,VF202 (4) sem N2; V13,VF203 (2) sem N1 nenhum | V13/VF203: SA não gerou nada, apesar de haver gabarito |
