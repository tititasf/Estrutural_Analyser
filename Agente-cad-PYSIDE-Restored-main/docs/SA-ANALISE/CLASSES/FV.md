# FV — manual granular de interpretação, validação e evolução

## 1. Contrato e fronteiras

**Objeto N1:** cada viga possui zero ou mais segmentos físicos de fundo; um segmento
é área interna fechada, não uma parede/linha. O dono semântico é
`FundoVigaInterpreter` em `src/core/beam_interpreters/fundo_viga.py`; a captura de
topologia comum é `BeamTracer`. LV nunca é fallback de campo, dimensão ou apoio FV,
mas é **referência não rígida da cobertura** (D-76, dono 2026-09-29 — espelho de o FV
ser referência da LV): `fundo_viga_lateral_ref.py` usa a cena das laterais para
(1) devolver à dona da faixa o painel que caiu na faixa de outra viga (≥ 70 % lá, < 30 %
na própria; ex.: VF202 com rótulo diagonal levava o fundo da V306), (2) criar painel
onde as duas faces têm parede (células Para) sem fundo — só com as duas paredes como
linha real do DXF, fora de cota, fora de pilar sólido e de **hachura** (seção de pilar
pelo próprio desenho) — e (3) dar à viga diagonal sem fundo o painel da faixa diagonal.
Fundo validado por humano não muda; o gate D-60 audita o resultado depois. Depois da
cobertura, a arbitragem D-79 garante **um único dono por área** nos cruzamentos: fundo
validado vence; entre automáticos vence, por painel, a maior profundidade, depois a
maior largura e depois a continuidade (D-83): fração do maior painel no
desenvolvimento total, só após o gate D-60. Somar vários vãos separados não
prova continuidade. Desenvolvimento total fica como desempate posterior, sem
prioridade por orientação ou nome da viga. O perdedor é recortado por
diferença do polígono real, preservando chanfros e diagonais; conflito entre dois
contornos humanos fica registrado, nunca é resolvido silenciosamente.

**D-83 — costura não é segmento físico:** painéis automáticos consecutivos da
mesma viga, faixa e seção são unidos quando a união é retangular, sem abertura
real e sem campos conflitantes. Tolerância de coordenadas de 0,05 cm não é
comprimento mínimo de fundo. Preservar pilares sólidos, mudanças de seção,
contornos humanos, chanfros e a divisão do L a 90°. Cruzamento deve ter um dono
contínuo e os fundos incidentes terminam nas suas faces; cobertura sem lacunas
nem sobreposição, sozinha, não comprova segmentação correta.
Resíduo criado por diferença de polígonos, com área menor que 0,1 cm² e
espessura até 0,05 cm, é registrado como ruído de coordenadas e não materializado
como painel. Esse saneamento não filtra painéis isolados medidos nem trechos
reais de 1 cm.

Não existe comprimento mínimo semântico para fundo (D-80): intervalo de área
positiva comprovado por duas faces reais gera painel, ainda que isolado e com 1 cm.
Comprimento não pode descartar painel. Uma ocorrência isolada sem vizinho também
é preservada.

**Segmentação do L pelo ângulo (D-82, dono 30/09/2026):** L ortogonal, a 90 graus,
são **dois painéis**. L angulado é **um único painel**, cortado no ângulo, sem divisão
de painel onde nasce o L. O tamanho relativo da perna e do corpo não altera essa
convenção. A hipótese anterior de unir pequenas caudas ortogonais por dominância
relativa foi rejeitada: contorno estrutural de seis vértices não prova peça única.
Robôs, lógica de reprodução N4 e desenhos N2/N4 são referências para compreender
e validar segmentação e corte; não fornecem coordenadas ao motor N1 nem autorizam
alterar geradores sem os gates previstos. Em 29/09 não havia N4 FV finalizado do
14_PAV no corpus consultado; essa disponibilidade deve ser conferida, não presumida.
**Implementação D-82:** removida a união automática `orthogonal_l`; pernas a 90
graus conservam seus painéis próprios, sem mínimo de comprimento. O complemento
de canto angulado se incorpora ao polígono diagonal sem criar slot no nascimento
do L. Testes cobrem dois painéis ortogonais, perna isolada de 1 cm e contorno
angulado único. Isso não equivale a selo completo de reprodução N3/N4.

**D-85/FV — encontro chanfrado não é automaticamente um L.** Nos encontros
angulados de vigas distintas, preferir interfaces retas chanfradas, atravessando
a largura, em vez de degraus/recortes ou uma cauda em L desnecessária. Identidade
da viga e continuidade das duas paredes distinguem mudança de direção do mesmo
elemento, chegada de outra viga e cruzamento passante; ângulo sozinho não decide.
Uma dobra genuína mantém a regra D-82; vigas distintas conservam donos separados.
O chanfro redistribui somente a área já comprovada do encontro, sem mudar seu
contorno externo, apagar peças pequenas ou criar área no vazio/pilar. Não aplica
a cruzamento passante, encontro a 90°, seção/profundidade diferente ou contorno
validado por humano. Se não existir repartição local segura, conserva a geometria
e exige revisão, não força uma interpretação em L. Fonte: apontamentos `fundos`
(30/09/2026 15:12:21) e `fundos2` (15:13:38), esclarecimento do dono no chat.
Implementação: busca cortes entre vértices do contorno real e reduz reentrâncias
e interfaces paralelas às paredes dos braços; restrição de chegada por extremidade
e área externa imutável. Seção medida localmente prevalece sobre dimensão textual
inválida para admitir esse ajuste. Validação sintética inclui rotação, pilar,
profundidade, identidade, validação humana e cruzamento; não é selo N3/N4.

**Busca alternativa de faixa FV:** quando a cota próxima não permite encontrar
a faixa, ou não há cota, o fundo pode reconhecer a largura pelas duas paredes
estruturais. Nessa busca alternativa, ambas devem existir na região longitudinal
do próprio rótulo; uma linha distante não pode formar faixa fictícia só por
envolver o texto transversalmente. Linhas de cota continuam excluídas e a
extensão final respeita sólidos/hachuras. Opção exclusiva do fluxo FV: a captura
de LV mantém seu comportamento padrão. Causa comprovada: VF404 do 14_PAV.

**Seção sólida prevalece sobre símbolo NASCE vizinho (D-81).** Continuidade das
paredes da viga e sobreposição com a caixa de um pilar que nasce não provam ausência
de outro pilar. Não se elimina a exclusão sólida, mesmo com classificação incerta.
O dono confirmou em 30/09 que P13 do 13_PAV é sólido até a região apontada: os dois
segmentos de fundo separados nessa região são corretos e não devem ser unidos.

**Jev opcional:** perguntar por segmento quando abertura, apoio ou seção tiver
evidência local conflitante; uma contagem global da viga não prova abertura em
cada fundo. Ver [segunda leitura do SA](../JEV-SEGUNDA-LEITURA-OPCIONAL.md).

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

**Como não errar (caso V301 S2 × P42, 2026-09-28 — D-65):**

1. **Reconhecer o NASCE pela convenção do pavimento, não pelo desenho solto.** O recorte
   `convencao_pilares_*.dxf` diz qual símbolo é NASCE/SEGUE/MORRE (no 13_PAV: **X** =
   NASCE). Pilar desenhado com esse símbolo não existe como sólido aqui.
2. **Linha interrompida pelo X não é limite do fundo.** As paredes do fundo costumam ser
   desenhadas cortadas onde passa o pilar que nasce; o fundo **ignora o pilar e segue até
   topar a viga** (ou o apoio sólido) seguinte. Nunca encurtar o contorno até a ponta da
   linha nem até a face do X.
3. **Cruzamento com viga mais funda corta nas PAREDES dela, nunca no rótulo.** O rótulo
   fica ao lado da viga: V312 rotulada em x=1599,6 tem paredes em 1603,4/1622,4. Zona de
   corte = par de linhas de fundo da viga que cruza (vão = largura da seção), só na falta
   desse par usa rótulo ± meia largura (`_crossing_walls`). Cortar pelo rótulo deslocou
   V301 S2 para 1590,1 e V302 S5–S9 em ~13 cm.
4. **Conferir contra a vizinha colinear.** Vigas paralelas cortadas pelas mesmas vigas
   (V301/V302) têm as mesmas coordenadas de corte; divergência de poucos cm = corte
   pelo rótulo ou por linha interrompida.
5. **Vão canônico manda; a linha só ancora a faixa.** Ao reancorar um contorno nas faces
   (`build_area_contour`), o comprimento vem sempre do vão canônico, mesmo quando a
   parede termina antes. Usar a extensão da linha fez a V301 S6 da VPS virar 2059–2462,
   sobreposta ao S5, e o gate não vê (o contorno fica sobre a linha). Segmentos da mesma
   viga nunca se sobrepõem: confira isso junto com o gate.

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
modelo/agente CLI dá o veredito (agente lê o PNG rasterizado desse SVG (+ `--zoom` vetorial em região densa)). API visual é proibida.

## 4. Taxonomia de casos e decisão de motor

| Caso visual | Regra geral | Dono provável | Teste negativo |
|---|---|---|---|
| encontro comum | fronteira física abre novo painel | `fundo_viga` | não unir por proximidade |
| alturas diferentes | mudança de seção/altura quebra segmento | `fundo_viga` | não fundir áreas coplanares aparentes |
| chanfro diagonal | polígono segue borda real; medida pelo eixo/extensão física | `fundo_viga` | não retangularizar nem somar linhas |
| obstáculo interno | preservar área e recorte identificado | `fundo_viga` | não tratar texto/objeto visual como vazio |
| objeto só visual | ignorar sem excluir área estrutural | `fundo_viga` | não gerar furo por proximidade |
| pilar nasce | ignorar como sólido no pavimento | contexto PIL + FV | não dividir/encurtar fundo |
| viga mais funda cruza | cortar nas paredes da viga que cruza | `fundo_viga` | não cortar por rótulo ± meia largura |
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
