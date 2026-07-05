# LOOPING CANÔNICO — o único loop válido (e a quarentena dos obsoletos)

**Data:** 2026-07-03 | **Status:** CANÔNICO — consolidação pedida pelo dono após
múltiplas transições/refinamentos dos loops. **Se um script/procedimento de loop não
está na seção 1 deste doc, NÃO use sem ordem explícita do dono.**

> Procedimento detalhado: `ARETE-LOOP-PROCEDIMENTO-GERAL.md` (como executar) e
> `ARETE-TRIAGEM-ERROS.md` (ciclo de triagem). Este doc é o MAPA — diz o que é
> canônico e o que é legado, para nenhuma sessão pegar coisa velha por engano.

---

## 1. O loop canônico (dois eixos, um conjunto de ferramentas)

### Eixo A — Qualidade de GERAÇÃO (N2→N4, gates G0/G1/G2/G6)
```bash
python scripts/arete/arete_runner.py --classe {PIL|LV|FV|LAJ} --pav {PAV} [--regressao]
```
Compara N4 (gerado da ficha N2) contra o recorte humano; sela golden em PASS.

### Eixo B — Qualidade de INTERPRETAÇÃO (N1, diagnóstico duplo + triagem)
```bash
# 1. Gerar fichas (ÚNICO headless de fichas; --wait obrigatório em automação)
python scripts/arete/headless_sa_analise.py --obra {OBRA} --pav {PAV} [--secao classe] --wait
#    → fichas HTML N1-N4 (SVG) + 4 diagnósticos automáticos + arete_manifest.json

# 2. Triagem humana (dono marca checkbox nas fichas)
python scripts/arete/qa_error_review.py open --dir .../{secao}
python scripts/arete/qa_error_review.py read --dir ... --json   # Claude interpreta → JSONL

# 3. Concordância auto×humano (métrica de autonomia)
python scripts/arete/triagem_concordancia.py

# 4. Corrigir causa-raiz no motor (1 fix por causa) → regenerar (passo 1) → reverificar
```

### Sempre, ao fim de qualquer rodada
```bash
python scripts/arete/gerar_status.py   # docs/STATUS.md = fonte de verdade de números
```

## 1.5 — HIERARQUIA DE VALIDAÇÃO: G2 sozinho NÃO é Arete (decisão do dono, 03/07)

> **G2 é a validação de MAIS BAIXO NÍVEL.** Ele lê metadados do DXF e confere
> matemática semântica (contagens, valores de cota, tamanhos ±0.5cm). É deliberada e
> estruturalmente CEGO para: cota renderizada em cima de texto, painel torto,
> sobreposições, posição/estética — tudo que um humano vê em 2 segundos.
> **"G2 100% PASS" sem confirmação visual é ILUSÃO de Arete** — consome tokens dando
> voltas sem gerar resultado (palavras do dono). Jamais se apoiar só nele.

```
Nível 0 — G1 round-trip           dados da ficha sobrevivem N2→N4→N2′
Nível 1 — G2 canônico             matemática semântica (contagens/valores)  ← MÍNIMO, nunca suficiente
Nível 2 — G2-V veredito visual    render lado a lado do recorte N2 (humano) × DXF N4 (robô);
                                  playwright_loop: DOM/SVG p/ texto exato + visão p/ geometria,
                                  sobreposição, hachura, gestalt — REGISTRADO no relatório
Nível 3 — Dono (humano)           juiz final; único gabarito onde não há N2 (ex.: GRADES)
```

> **Quem dá o veredito do Nível 2:** a visão do agente CLI (Claude Code / Codex) lendo
> o screenshot — **única fonte de qualidade comprovada e a ÚNICA permitida hoje**
> (`g2v_harness.py --backend cli`). **Ordem do dono (03/07): backends de API
> (claude/gemini/nim) estão DESLIGADOS e bloqueados no código** — só com `--permitir-api`
> + ordem explícita + calibração. NIM reprovado (4/4). Caminhos explorados, becos sem
> saída e o protocolo de calibração: `docs/VISION-VALIDACAO-CAMINHOS.md`. Bug prioritário
> da sentinela x=-9000 em `paridade_visual.py` (distorce os comparacao.png do golden): §5 lá.

**Regras operacionais (valem para TODA classe, TODA rodada):**
1. **Selar golden exige Nível 2 no mínimo:** G2 PASS torna o item *candidato*;
   a selagem só após veredito visual registrado (path dos screenshots/leitura no
   relatório da rodada). Primeira selagem de uma classe/pavimento = varredura visual
   de 100% dos itens; re-selagens pós-fix = 100% dos itens tocados + amostra de 20%
   dos demais (alinha com DA-A4 do masterplan, agora endurecido).
2. **Declarar "Arete atingido" exige Nível 2 + Nível 3** (dono viu e não reclamou —
   silêncio após revisão dele conta; ausência de revisão NÃO conta).
3. **Relatório que diz "100% PASS" sem seção de veredito visual está INCOMPLETO** —
   tratar como candidato, não como resultado.
4. **A regra vale para TODO gate visual, não só o G2.** Todo número que compara desenhos
   tem um par visual obrigatório, sempre via `g2v_harness.py` (mesmo prompt, mesmo
   schema, backend cli):

   | Gate numérico (cego) | Veredito visual obrigatório | Comando |
   |---|---|---|
   | G2 paridade (N2×N4) | **G2-V** | `g2v_harness.py --par n2xn4 --backend cli` |
   | diagnostico_*_n1_n2 (N1×N2) | **N1-V** | `g2v_harness.py --par n1xn2 --backend cli` |
   | paridade N3×N4 (G5) | **G5-V** | `g2v_harness.py --par n3xn4 --backend cli` |
   | GRADES do PIL — onde HÁ recorte de grades (1º/2º/14º/TÉRREO/TIPO) | **GRADES-V** | `g2v_harness.py --classe PIL --par grades --backend cli` |
   | GRADES do PIL — onde NÃO há recorte (ex. 13_PAV) | **dono (Nível 3)** | ele olha o N4 grades, não há comparador |

   Aprovar/avançar qualquer um desses só com o número = alucinação de aprovação. NUNCA.
   > Nota GRADES: o recorte de grades é por SHEET do pavimento (todos os pilares numa
   > folha), não por pilar (masterplan AR-1'.E). O `--par grades` hoje entrega a leitura
   > visual do N4 grades via ficha HTML (para o agente/dono); o comparador NUMÉRICO
   > per-sheet recorte×N4 é a story AR-1'.E, ainda pendente. Onde não há recorte
   > (13_PAV), é só o dono — não force comparação.

> **Nota de estado (03/07):** os goldens selados hoje (FV 26/26, LAJ 31/31, PIL
> 35/35 do 13_PAV) foram selados no Nível 1 apenas — são CANDIDATOS aguardando a
> varredura visual das sessões de looping em andamento. Não re-anunciar como Arete
> concluído até o veredito visual passar.

### Scripts canônicos (a lista completa — nada além disto)

| Script (`scripts/arete/`) | Papel |
|---|---|
| `headless_sa_analise.py` | ÚNICO entry point de fichas (4 classes, `--secao`, `--wait`, trava anti-OOM) |
| `arete_runner.py` (+ `roundtrip_ficha`, `paridade_visual`, `ficha_adapter`, `gerar_n4_item`) | Gates N2→N4 + golden |
| `diagnostico_{pil,fv,lv,laj}_n1_n2.py` + `diagnostico_common.py` | Diagnóstico NUMÉRICO N1×N2 (já rodam DENTRO do headless; CLI avulso só p/ debug) — **cego, exige N1-V** |
| `g2v_harness.py` | **VEREDITO VISUAL obrigatório** de todo gate visual: `--par n2xn4`(G2-V) / `n1xn2`(N1-V) / `n3xn4`(G5-V), `--backend cli` (agente lê a imagem). Ver §1.5 e `VISION-VALIDACAO-CAMINHOS.md` |
| `qa_error_review.py` | Triagem humana (abrir/ler checkboxes) |
| `playwright_loop.py` | Leitura QA das fichas (screenshots/DOM p/ visão do Claude) |
| `triagem_concordancia.py` | Rollup de concordância auto×humano |
| `gerar_status.py` | STATUS.md gerado (nunca escrever número à mão) |
| `single_instance.py` | Trava anti-OOM (biblioteca) |

---

## 2. QUARENTENA — gerações anteriores do loop (NÃO usar como entry point)

Inventário verificado no disco + grep de referências em 2026-07-03:

### 2a. Bibliotecas da app (o código importa; NUNCA rodar como loop)
| Script | Quem usa | Nota |
|---|---|---|
| `scripts/engrev_laj_recorte_loop.py` | `src/ui/modules/comparison_engine.py` | função interna da UI |
| `scripts/fv_loop_runner.py` | `src/ui/widgets/project_manager.py`, `analise_geral_headless` | idem |
| `scripts/laje_loop_runner.py` | `src/ui/widgets/project_manager.py` | idem |
| `scripts/fv_render_loop.py` | `analise_geral_headless` (→ `main.py`) | idem |
| `scripts/analise_geral_headless.py`, `laje_analise_geral_headless.py` | `main.py` / `laje_loop_runner` | bibliotecas apesar do nome "headless" |
| `scripts/arete/gerar_html_preficha_headless.py` | `playwright_loop` | CLI DESCONTINUADO (aborta sem `--legacy`); só biblioteca |

### 2b. Órfãos (zero referências — presumidos obsoletos, geração "vision loop" de 30/06)
`lj_vision_loop.py` · `lj_refinamento_loop_vision.py` · `lv_ab_prod_pav_loop_runner.py`
— superados pela decisão SVG/DOM (visão só para gestalt). Candidatos a mover para
`scripts/_loops_legado/` numa story futura, com ordem do dono.

### 2c. Cluster LV legado (25/06 — só se referenciam entre si + 1 masterplan antigo)
`lv_n2_vision_loop_runner.py` · `lv_n4_unit_loop_runner.py` ·
`lv_section_prod_pav_loop_runner.py` · `lv_section_visual_loop_runner.py`
— presumidos superados pelo harness LV novo (03/07: `preficha_lateral_html` +
`diagnostico_lv_n1_n2`). **Confirmar com a sessão LV antes de qualquer remoção.**
`docs/MASTERPLAN-LOOP-LV-N2-VISION-N4.md` referencia este cluster → marcar como
histórico quando o cluster for aposentado.

### 2d. Docs de loop superseded (história, não procedimento)
`LOOPING-EVOLUCAO-N2-VISAO-FICHA.md` · `MASTERPLAN-LOOP-TREINO-MOTOR.md` ·
`MASTERPLAN-LOOP-LV-N2-VISION-N4.md` — não seguir como execução.

---

## 3. Regra de contaminação zero

1. Sessão nova SÓ usa o que está na seção 1. Dúvida = perguntar ao dono, não improvisar.
2. Script legado que ainda for útil vira FUNÇÃO importada pelo caminho canônico —
   nunca um segundo entry point.
3. Todo refinamento futuro do loop ATUALIZA este mapa na mesma entrega (o refinamento
   que não atualiza o mapa é a origem exata da contaminação que este doc mata).
