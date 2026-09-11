# Rodada de revisão granular — LV 13_PAV

## Objetivo

Levar o motor de desenho LV a **Arete em todas as vigas do 13_PAV**, não só na
V301 (item de calibração). Para isso o revisor precisa, em cada viga, da mesma
superfície que foi construída na V301:

- cada **segmento N2 recortado** ao lado do seu **segmento N4 correspondente**;
- marcação de ponto e nota **por cartão**, com coordenadas DXF reais na
  referência copiada (sobrevive à troca de handles entre gerações);
- as **visões de corte** logo abaixo dos segmentos, uma por instância real.

O ciclo é: revisar → apontar → corrigir o motor → **regerar só aquela viga** →
reabrir a página. Repete até a viga ficar Arete; depois passa para a próxima.

## Procedimento

```bash
# 1. Gerar os N4 da rodada (NÃO escreve na produção)
python scripts/arete/gerar_lv_n4_fichas.py <vigas...> \
    --out scripts/arete/relatorios/g2v/lv_13pav_rodada_20260911/n4
```

`--refresh-from-recorte` é o padrão e a fonte da ficha é impressa
(`[FICHA] fonte = ...`).

```bash
# 2. Rodar a rodada: gate de geometria + página por viga
python scripts/arete/rodada_lv_13pav.py

# 3. Revisar
#    abrir <rodada>/INDEX_VIGAS.html e clicar na viga

# 4. Após corrigir o motor, regerar SÓ a viga afetada
python scripts/arete/gerar_lv_n4_fichas.py V314 --out <rodada>/n4
python scripts/arete/rodada_lv_13pav.py --item V314
```

## Onde a rodada escreve

Só dentro de `scripts/arete/relatorios/g2v/` (gitignored):

| caminho | conteúdo |
|---|---|
| `lv_13pav_rodada_20260911/n4/` | N4 da rodada (A, VIEW_A, VIEW_B, CORTE) |
| `lv_13pav_rodada_20260911/INDEX_VIGAS.html` | lista simples → clica e abre a viga |
| `lv_13pav_rodada_20260911/INDEX.html` | panorama com previews e índice N2 |
| `{viga}_geometry_gate/{VIGA}_SEGMENTS_E2E.html` | página granular da viga |

**A produção não é tocada.** Os N4 selados em
`DADOS-OBRAS/*/Fase-6_Execucao_CAD/n4/` estão **somente-leitura** de propósito
(artefato protegido, data de 16/07) — tentar publicar por cima falha com
`Permission denied`, e isso é o guarda funcionando. A rodada lê e escreve N4
apenas na pasta própria, via a variável de ambiente **`LV_N4_DIR`**, respeitada
por `run_geometry_gate_lv.py` e `_build_segments_html_v301.py`.

Para publicar em produção (quando houver decisão explícita): comparar contagem
de entidades contra o arquivo existente antes de escrever. Queda grande =
ficha stale → abortar.

## Estado desta rodada (2026-09-11)

- **29/32 vigas** com N4 e página granular: **130 cartões** (100 segmentos + 30 cortes).
- **3 falham o contrato N4** e por isso não têm página:
  - `V305`, `V308` — `face_units: lado(s) ausente(s): B` (extração só achou um lado);
  - `V330` — `face_units[0].segments[0].height1: deve ser maior que zero`.
- **28 dos 29 cortes** já saem da geometria real do N2. Só a `V13` cai no
  template procedural (a seção dela não tem `visual_primitives`).

### Achados do índice N2 (antes de olhar desenho)

- **Nenhuma das 32 vigas tem `face_units` no `fichas_lv_v2.json`.** Toda a
  produção antiga foi desenhada pela rota legada `draw_viga_lateral`, não pelo
  motor de `face_units`. Por isso os arquivos antigos têm mais entidades: são
  **outro desenho**, não um desenho melhor.
- **14 vigas com faces A×B de comprimentos muito diferentes** (limiar 1.35×):
  V302, V303, V306, V314, V316, V318, V320, V321, V322, V323, V328, V332,
  VF203, VF301. Ex.: V314 e V318 com 174.9 vs 568.0; VF203 com 732 vs 156.
  Ou a extração está errada, ou a viga realmente tem faces de comprimentos
  diferentes — é o primeiro lote a revisar.

### Sobre `--refresh-from-recorte`

Foi tornado padrão após o incidente de 10/09 (rodar sem a flag sobrescreveu N4
já validados da V301: 935 → 314 entidades). Medindo as 32, porém, **não há
vencedor universal**: refresh entrega mais em 14, a ficha em 10, empatam em 5 —
e é o refresh que faz V305/V308/V330 falharem o contrato. O invariante real
não é o default da flag, é o **procedimento**: comparar contra o que já existe
antes de publicar.

## Limitações conhecidas

- O recorte do Corte 1 ainda deixa entrar um pedaço do topo do Corte 2 (as
  cotas em escala 2× de uma seção alcançam a vizinha).
- `_build_segments_html_v301.py` mantém o nome histórico, mas já aceita
  `<item>` como argumento posicional.
- `SyntaxWarning: invalid escape sequence '\d'` na linha que injeta o JS
  (pré-existente, não bloqueia; `node --check` passa).
