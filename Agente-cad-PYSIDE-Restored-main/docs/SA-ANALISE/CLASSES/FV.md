# FV — manual granular de interpretação, validação e evolução

## 1. Contrato e fronteiras

**Objeto N1:** cada viga possui zero ou mais segmentos físicos de fundo; um segmento
é área interna fechada, não uma parede/linha. O dono semântico é
`FundoVigaInterpreter` em `src/core/beam_interpreters/fundo_viga.py`; a captura de
topologia comum é `BeamTracer`. LV nunca é fallback de campo, dimensão ou apoio FV.

| Camada | Fonte/artefato | Pode decidir |
|---|---|---|
| DXF original | geometria, textos, encontros e convenção de pilar | fonte N1 |
| `BeamTracer` | ocorrências, eixo, intervalos e topologia bruta | somente dado comum |
| `FundoVigaInterpreter` | contorno, segmentação, medida, apoios e exceções FV | semântica FV |
| `beams.data_json` | `fields`, `links`, `viga_segs.seg_bottom` | persistência N1 |
| N2/N4 | ficha/recorte e desenho de referência | comparação, nunca entrada |

O registro arquitetural de sete contratos está em
`docs/ARQUITETURA-INTERPRETADORES-VIGA-N1-ISOLADOS.md`. Só tocar `BeamTracer` se a
captura bruta estiver errada em mais de um contrato; então a regressão inclui PIL,
LAJ, LV e FV.

## 2. Ficha N1: campos, prova e leitura visual

### 2.0 Visão canónica (obrigatória em N1-V / G2-V / G5-V)

Documento mestre: [docs/QA-VISAO-EVIDENCIA-CANONICA.md](../../QA-VISAO-EVIDENCIA-CANONICA.md).

G2-V/G5-V de FV: **agente lê PNG** full-render; **SVG** no HTML com persist/app/portal.
Headless sem persist = imagem dinâmica. Contagem/score sozinho **não** fecha gate.
g2v_harness.py --backend cli + inventário N2×N4. docs/QA-VISAO-EVIDENCIA-CANONICA.md.

Para cada segmento, a ficha em `fundos_viga/<Vxxx>.html` oferece **dois SVGs**:

- **N1 local:** polígono da área, dimensão isolada, extremidades, apoio inicial/final
  locais e furo/recorte que toca o segmento. É a prova que decide o segmento.
- **N1 contextual:** continuidade/eixo da viga, nome/dimensão distante, pilares e
  transições. Explica identidade; não pode criar segmento nem apoio ausente no local.

| Família | Campos N1 esperados | Critério de aceitação | Erro típico |
|---|---|---|---|
| identidade | `fields.nome`, `numero`, `dimensao` | Viga e seção correspondem ao texto/DXF | item de vizinho ou dimensão herdada |
| existência | `viga_fundo_seg_N_exists`, `seg_bottom[N]` | um polígono fechado, área positiva, `source_key` próprio | vínculo de linha/parede, área zero |
| geometria | `points`, `evidence_segments`, `source_segment` | contorno sobreposto à área interna; sem deslocamento | bbox correto, polígono errado |
| comprimento/largura | `length`, `width`, `measure_*` | comprimento é a maior extensão/eixo físico, largura é a outra; tolerância 0,05 | soma de linhas/recortes usada como comprimento |
| ordem/quantidade | `segment_index`, ocorrência, repetição | um segmento por painel físico; multiplicador N2 expande contagem lógica | V306 contado como 2 em vez de 6 |
| apoios locais | `viga_fundo_seg_N_local_ini/fim` e links | contato da extremidade do próprio segmento | usar limite global da viga |
| limites globais | `links.apoios.inicio/fim` com `scope=beam_global` | identidade da viga inteira; não substitui apoio local | início/fim global vendido como apoio do painel |
| exceções | `links.aberturas`, furos, cortes, chanfros | só se intersectam/tocam o polígono local | inventar exceção do contexto |

Pilar com convenção **nasce** não é sólido neste pavimento: não pode cortar, iniciar
ou terminar área FV. Confirmar a convenção PIL antes de classificar o encontro.

## 3. Diagnóstico N1×N2 e barreira S5

Use `scripts/arete/diagnostico_fv_n1_n2.py` como alarme, não como sentença. Ele
compara quantidade física e multiconjunto de comprimentos por segmento em **0,05 cm**;
já expande multiplicadores N2 (`5x`, `_multiplier`, repetições) antes da contagem.

Antes de S6/N3, montar matriz por segmento: identidade, ordem, polígono local,
comprimento, largura, apoios locais, apoio global, chanfro, furo/recorte. Registrar
score, match/mismatch/N/A e fonte. N2 ajuda a detectar a fronteira que N1 perdeu,
mas não preenche N1. Segmentação, forma, contato e chanfro exigem SVG; bbox PASS não
fecha a matriz.

```powershell
# consulta já persistida, sem headless
python scripts/arete/qa_evidence_auditor.py review --project-id <ID> --classe FV --include-sealed
python scripts/arete/qa_profile_probe.py --classe FV --probe first_segment_support_and_dimension `
  --item V301 --project-id <ID>

# apenas se a hipótese atingir a interpretação N1
python scripts/arete/headless_sa_analise.py --obra <OBRA> --pav <PAV> `
  --secao fundos_viga --item V301 --wait
python scripts/arete/g2v_harness.py --classe FV --pav <PAV> --par n1xn2 `
  --item V301 --backend cli
```

O N1-V (interpretação N1×N2) usa somente SVGs-fonte e manifesto do harness; o
modelo/agente CLI dá o veredito. API visual é proibida.

## 4. Taxonomia de casos e decisão de motor

| Caso visual | Regra geral | Dono provável | Teste negativo |
|---|---|---|---|
| encontro comum | fronteira física abre novo painel | `fundo_viga` | não unir por proximidade |
| alturas diferentes | mudança de seção/altura quebra segmento | `fundo_viga` | não fundir áreas coplanares aparentes |
| chanfro diagonal | polígono segue borda real; medida pelo eixo/extensão física | `fundo_viga` | não retangularizar nem somar linhas |
| obstáculo interno | preservar área e recorte identificado | `fundo_viga` | não tratar texto/objeto visual como vazio |
| objeto só visual | ignorar sem excluir área estrutural | `fundo_viga` | não gerar furo por proximidade |
| pilar nasce | ignorar como sólido no pavimento | contexto PIL + FV | não dividir/encurtar fundo |
| eixo/intervalo bruto errado em várias classes | corrigir captura comum | `BeamTracer` | regressão das 4 classes |

O guia manual protegido é `interpretacao_fundos.html`; ler, nunca editar. V301 é
prova de segmentação contínua; V306 é prova de multiplicador e chanfro; V307 é caso
especial angular/manual até existir fórmula geral comprovada.

## 5. N3, regressão e persistência

N3 é variante `FUNDO_C`, gerada pelo contrato em `src/core/fv_generation_contract.py`.
Antes de desenho, provar nome `Vxxx.C`, ordem/quantidade dos painéis, dimensão de cada
segmento, apoios e exceções. Smoke não prova área ou chanfro: abrir ficha do motor e
rodar G5-V (paridade final N3×N4) via CLI/SVG.

No G5-V de FV, `apoios_segmento` é obrigatório no checklist CLI: comparar o apoio
inicial/final do **painel local**, não só textos globais da viga. PASS geométrico com
apoio divergente retorna a S5 para reconciliar N1×N2/DXF; não autoriza alterar o N3
com dados N4 nem culpar a conversão enquanto ela reproduz fielmente o N1.

Geometria validada de um segmento FV congela o conjunto validado: reanálise não
adiciona/remove segmentos nem substitui o polígono validado; campos internos ainda não
validados podem evoluir. Um contorno automático aberto, de área zero ou linha aborta
o commit. Regra completa: `docs/PERSISTENCIA-HEADLESS-SA.md`.

Após mudança em `fundo_viga`: teste unitário + microciclo de família + diagnóstico FV
e N1-V. Após mudança em `BeamTracer`: headless completo, quatro diagnósticos,
comparação de alertas e gates visuais proporcionais. Registrar no diário `HISTORICO/FV.md`.

## 6. Autoevolução e candidato RAG FV

Cada BLUE/laranja ou exceção FV deve acrescentar ao diário e a este manual: tipo de
encontro, contorno local/contextual, medida, multiplicador, apoio local/global,
convenção de pilar, contraexemplo e regressão. O HTML/SVG validado vira candidato RAG
multimodal **segmento a segmento**, com hashes e decisão humana; não é promovido
automaticamente. Ao fechar todos os laranjas FV do pavimento, consolidar a taxonomia
e pedir ao humano validação para futura curadoria RAG FV.
