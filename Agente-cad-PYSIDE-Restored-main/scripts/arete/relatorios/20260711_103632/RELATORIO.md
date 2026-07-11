# RELATÓRIO — Validação técnica PIL N3 PARA/PASSA (P1–P3 / 13_PAV)

**Gerado:** 2026-07-11T10:36:32
**Escopo:** Obra_TREINO_1 · 13_PAV · P1, P2, P3
**Não é G2-V / Arete visual:** validação humana no Comparison Engine ainda pendente.

## Checklist automatizado

| Critério | Resultado |
|----------|-----------|
| Artefatos n3_variants para/passa (json+ABCD+GRADES) P1–P3 | PASS |
| CIMA canônico presente por item | PASS |
| ABCD PARA ≠ ABCD PASSA (hash) | PASS |
| GRADES PARA ≠ GRADES PASSA (hash) | PASS |
| CE resolve P{n}_Para / P{n}_Passa (CIMA+ABCD+GRADES+payload) | PASS |
| Contrato pil.n3_mode_contract.v1 embutido no JSON | PASS |
| payload aberturas == aberturas ativas do contrato | PASS |
| DXF PARA contém segmentos Painéis h≈124/59 e w≈11/29/34 | PASS (sinais geométricos) |
| DXF PASSA sem aberturas (só malha 160/120/158) | PASS |
| HTML fichas pack 20260711_102044 com seções PARA/PASSA | PASS |
| G2-V / aprovação humana visual | PENDENTE |

## Hashes (sha256[:12])

| Item | CIMA | ABCD_para | ABCD_passa | GRADES_para | GRADES_passa |
|------|------|-----------|------------|-------------|--------------|
| P1 | a1a5a2929cb7 | dca16c68d73b | 172d8eca6428 | fee500bc8ba7 | 0f353c641bc2 |
| P2 | 938ea20f461d | a3154a6c464a | 132512696afa | 9c33b0b372f3 | 573fe9a81a55 |
| P3 | 5d58951fca2e | 593ed5f97751 | fb3817b0ee94 | a0d555433414 | d242f1e2846e |

## Contratos semânticos (resumo)

### P1
- **PARA** modo=PARA ariant=PARA
  - Face A: topo=0.0(nulo); PARA AD:V309 h=124.0
  - Face B: topo=14.0(laje_espessura_mais_2); PARA BD:V309 h=124.0; CHEGA BC:VF301 h=124.0
  - Face C: topo=120.0(viga_que_passa)
  - Face D: topo=120.0(dentro_do_interior)
- **PASSA** modo=PASSA ariant=PASSA
  - Face A: topo=120.0(viga_que_passa)
  - Face B: topo=120.0(viga_que_passa); NEUT BC:VF301
  - Face C: topo=120.0(viga_que_passa)
  - Face D: topo=120.0(dentro_do_interior)

### P2
- **PARA** modo=PARA ariant=PARA
  - Face A: topo=14.0(laje_espessura_mais_2); PARA AD:V312 h=124.0; CHEGA AC:V301 h=124.0
  - Face B: topo=14.0(laje_espessura_mais_2); PARA BD:V312 h=124.0; CHEGA BC:V301 h=59.0
  - Face C: topo=120.0(viga_que_passa)
  - Face D: topo=120.0(dentro_do_interior)
- **PASSA** modo=PASSA ariant=PASSA
  - Face A: topo=120.0(viga_que_passa); NEUT AC:V301
  - Face B: topo=120.0(viga_que_passa); NEUT BC:V301
  - Face C: topo=120.0(viga_que_passa)
  - Face D: topo=120.0(dentro_do_interior)

### P3
- **PARA** modo=PARA ariant=PARA
  - Face A: topo=14.0(laje_espessura_mais_2); PARA AD:V314 h=124.0; CHEGA AC:V301 h=59.0; CHEGA AC:V320 h=59.0
  - Face B: topo=14.0(laje_espessura_mais_2); PARA BD:V314 h=124.0; CHEGA BC:V301 h=124.0
  - Face C: topo=120.0(viga_que_passa)
  - Face D: topo=120.0(dentro_do_interior)
- **PASSA** modo=PASSA ariant=PASSA
  - Face A: topo=120.0(viga_que_passa); NEUT AC:V301; NEUT AC:V320
  - Face B: topo=120.0(viga_que_passa); NEUT BC:V301
  - Face C: topo=120.0(viga_que_passa)
  - Face D: topo=120.0(dentro_do_interior)

## Achados para olhar humano (não bloqueiam pipeline técnico)

1. **P1 PARA Face A** tem azio_topo=0 (nulo) enquanto Face B usa laje+2=14. Assimetria pode ser correta se A sem laje no N1 — confirmar visualmente na ficha HTML e no N1.
2. **P3 PARA Face A** materializa **duas chegadas no mesmo slot AC** (V301 e V320) com a **mesma** geometria (w=34 h=59 y_rel=205). No DXF as linhas coincidem (duplicata geométrica). Avaliar se a regra geral deve colapsar chegadas iguais no mesmo slot.
3. **PASSA** em P1–P3: zero aberturas no payload (todas as chegadas neutralizadas por profundidade ≤ passante 120). Visual esperado: painel “cheio” com vazio de topo 120, sem recortes laterais de chegada.
4. **Não hardcodar P1/P2/P3** se houver correção — qualquer fix deve nascer de regra geral (dedupe de slot, prioridade de laje, etc.).

## Como validar no Comparison Engine (humano)

1. Reiniciar a app se já estava aberta antes do headless de 2026-07-11 10:20.
2. Comparison Engine → Obra_TREINO_1 → 13_PAV → classe PIL.
3. Para cada item virtual:
   - P1_Para / P1_Passa
   - P2_Para / P2_Passa
   - P3_Para / P3_Passa
4. Em N3 conferir: CIMA comum; ABCD/GRADES distintos por modo; ficha com _sa_mode_variant correto; aberturas coerentes com SA.
5. Só então marcar feedback; correções depois, uma causa por vez.

## Artefatos

- Variantes: D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-6_Execucao_CAD\n3_variants
- Pack HTML: scripts\arete\html_fichas\Obra_TREINO_1\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260711_102044
- Fichas: pilares/MORRE/P1.html, P2.html, P3.html
