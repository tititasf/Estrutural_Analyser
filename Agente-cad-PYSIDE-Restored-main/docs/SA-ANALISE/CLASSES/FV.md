# FV — manual granular de interpretação, validação e evolução

## 1. Contrato e fronteiras

**Seção numérica em eixo oblíquo (10/10/2026).** A largura física de um fundo
oblíquo não é o lado menor da bbox global. Vincular o nome e a seção numérica
alinhados a duas paredes do DXF original, no eixo local, com largura concordante
e cobertura da borda real no intervalo comum. Essa prova permite derivar o fundo
a partir do nível e da altura numérica; não aprova pontas, apoios ou o contorno
completo. Preservar os handles de nome, seção e paredes na evidência. Se houver
alturas distintas, parede ausente ou vínculo ambíguo, manter a pendência.
O contexto derivado conserva o N1 e o polígono original. Referência de prova:
`20261010_encontros_niveis_14pav/desenvolvimento_rapido/integracao_v408_identidade/v406_original_section_proof.json`.

**Fundo normal abaixo de uma invertida (04/10/2026, V301 SEG 16 × V330).**
O corte em planta por uma viga mais alta não prova bloqueio: comparar níveis
absolutos locais. Quando o fundo normal está estritamente abaixo da base da
invertida confirmada, e ambas as paredes estruturais do DXF chegam à face
afastada, conservar essa chegada. No caso aprovado, V301 SEG 16 vai à face B
da V330: 247,52 → 266,517 cm; fundo 851,64 m, base da invertida 852,06 m.
O contorno de P49 em planta termina nessa mesma face B; essa chegada expressa
nas duas paredes foi aprovada pelo dono. Não extrapolar uma face de pilar
que ultrapasse o destino, nem ocupar outro segmento da mesma viga.
Exigir cobertura completa e concordante da invertida, sem pendências de nível.
Geometrias humanas têm precedência. O ajuste é derivado na leitura/conversão
SA → N3, conserva IDs e contagem; não reescreve N1 original, DXF nem Fase-4.
Implementação: `fv_inverted_crossings.py`; evidência em
`scripts/arete/relatorios/20261003_v330_inverted_plan/verify_v301_crossing.py`.

**SA → N3: preservar a dobra angular (03/10/2026, V307 do 13_PAV).**
O adaptador deve ler a geometria efetiva do SA, incluindo o sidecar humano do
pavimento, antes de construir a ficha de geração. Um contorno côncavo com dobra
não ortogonal vira um contorno explícito com todos os vértices, transformado
rigidamente para um eixo local estável; guardar origem e eixo permite voltar ao
estrutural sem deslocamento. A envoltória de corte não substitui a medida física
do SA. Retângulos e chanfros convexos conservam a modulação comum; L a 90° conserva
a regra de dois painéis. Painéis explícitos existentes têm precedência.

**Modulação de fabricação independente da dobra (03/10/2026).** A chapa normal
tem comprimento máximo de 244 cm. O contorno angular gerado a partir do SA também
deve ser modulado: a dobra não causa divisão, mas não dispensa o limite da chapa.
Colocar as emendas na região reta comum às duas paredes, preservando a dobra
inteira no painel terminal. Recortar os polígonos conservando exatamente a área,
sem sobreposição, e transladar a origem local de cada painel para manter seu
vínculo com o estrutural. A divisão de fabricação não cria outro segmento SA.
Uma sobra pequena é redistribuída entre chapas, nunca descartada nem anexada a
uma chapa de 244 cm tornando-a maior que o limite. Todo comprimento positivo
continua válido, inclusive 1 cm. Se a geometria não admitir emendas retas dentro
do limite, exigir revisão; não cortar automaticamente na dobra. Detalhar as
projeções internas/externas da dobra, altura total, corpo reto e chanfro terminal
pelos vértices efetivos, usando N2/N4 apenas como referência QA. Referência de
validação: `scripts/arete/relatorios/20261003_v307_modulacao/`.
Para esse painel angular, um apoio em pilar pode ser identificado pela face
sólida compartilhada integralmente com a aresta terminal, sem invasão do sólido.
Proximidade, contato pontual, NASCE e contato ambíguo não autorizam substituir
apoio. Tolerância de 0,0001 cm serve apenas ao arredondamento de coordenadas.
Geometria humana não muda; N4 é comparação QA, nunca entrada dessa conversão.
Regenerar N3 sem editar seus campos não deve gravar uma substituição retangular
a partir do formulário resumido. A conclusão `done` do acompanhamento equivale
a concluído e deve atualizar a ficha. Evidência e limites da validação em
`scripts/arete/relatorios/20261003_v307_n3/RELATORIO.md`.

**Proteção persistente contra pilares sólidos (03/10/2026, P18/P19 no 13_PAV).**
A exclusão do polígono físico sólido vale também para fundos automáticos já
existentes, reconstruídos e prolongados; não basta excluir os vazios novos.
Aplicar diferença geométrica antes da recuperação e novamente depois das
reancoragens/ajustes de cruzamento, sincronizando slots e comprimentos. Não usar
rótulo ou largura de outra viga como substituto da seção sólida. NASCE, ignorados
e inválidos seguem o contrato canônico de não bloqueio. Preservar fragmentos
positivos, inclusive 1 cm; contorno com furo requer divisão conservando a área,
nunca preencher o furo. Geometria humana é preservada e seu conflito é reportado,
não recortado silenciosamente. Correção geral: `clip_automatic_bottoms_to_solid_pillars`.
Referência: apontamentos V303×P19 e V330×P18; não é certificação Arete global.

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

**Referência manual do dono, 02/10/2026 — validar a repartição, não só o número de chanfros.**
**Refinamento geométrico de 02/10/2026:** se duas chegadas colineares têm
larguras diferentes e encontram um terceiro braço angulado da largura da maior,
com mesma profundidade local, a continuação estreita termina na parede do braço.
Entre o braço e a continuação larga, uma única corda conecta as interseções das
duas paredes medidas de cada um. Essas interseções podem estar no interior de
uma aresta da união, não necessariamente em um vértice. Não repartir a ponta
50/50 nesse caso. Redistribuir somente dentro da célula local, conservando a
união, os três donos, as outras extremidades e a ausência de sobreposição.
Pilares sólidos, cruzamentos passantes e contornos humanos continuam protegidos.
Implementação: `_stepped_collinear_junctions`; referência manual é só QA, nunca
entrada do motor. Replay 13: 91 painéis, VF203 inalterada; replay 14: 84 painéis
e nenhuma alteração pela regra. Isso não certifica Arete global nem N3/N4.

**Contatos arredondados na primeira passagem (02/10/2026):** bandas medidas
independentemente podem gerar microfendas entre vértices e arestas. O preenchimento
do encontro já comprovado deve admitir contato numérico inferior a 0,05 cm,
somente dentro da célula testemunhada pelas paredes, sem erodir contornos nem
mover os braços externos. Esse valor é tolerância de contato, não comprimento
mínimo de painel: fundos de 1 cm continuam permitidos. Separação real, pilar
sólido, cruzamento passante e geometria humana não podem ser unidos por isso.
Conferir o resultado desde a primeira passagem sem cache; uma segunda execução
ou replay de um estado já reparado pode mascarar a falha de preenchimento.

O contorno manual de V307/V306/VF202/VF203 no 13_PAV é referência protegida
para comparar a interpretação de encontros complexos. O replay isolado da
primeira passagem, após o refinamento, reproduz as interfaces do nó triplo;
restam diferenças de área por coordenadas medidas: V307 10,295 cm², V306
1,285 cm², VF202 6,043 cm²; VF203 coincide. Esses valores são comparação local,
não aprovação integral. Um corte único não prova sozinho que a distribuição entre vigas está
correta. Comparar interfaces, cobertura da união e exclusividade por dono,
preservando os desenhos humanos. Não generalizar coordenadas ou nomes de vigas.
Evidência local: `scripts/arete/relatorios/20261002_fv_stepped_junction/manual_junction_comparison.json`.

**D-85/FV, adendo 01/10/2026 — um corte completo no encontro triplo.** Quando
uma chegada de três vigas distintas deixa uma ponta com dois chanfros no fundo
de uma delas, preferir uma única reta entre suas duas paredes reais. A ponta
não é apagada: sua área é redistribuída entre os dois fundos vizinhos, que
encontram essa mesma reta; continuam três painéis com donos separados. O dono
aprovou explicitamente essa solução para V307/V306/VF202, preservando o encontro
VF202/VF203 já aprovado. A regra é geométrica, sem depender desses nomes ou do
pavimento. Exige contato com os dois vizinhos, chegada pelas extremidades,
profundidade local igual, ausência de pilar sólido e de validação humana;
conserva união externa e ausência de sobreposição. Não transforma cruzamento
passante ou dobra da mesma viga em encontro triplo. Tolerâncias numéricas não
são limite mínimo de comprimento de painel: pedaços físicos pequenos permanecem.

**Entrega FV no portal:** `--production-web` em chamada headless direta produz
snapshot isolado de classe/PID. Isso não prova que o viewer mudou: ele consome
`estado_<pav>.json`. A publicação precisa concluir pelo runner do portal, com
`promover_snapshot_sa(..., secao='fundos_viga')`, preservando segmentos de outras
classes; depois conferir a camada SVG efetivamente exibida nos encontros.
Captura `after_final.json` ou PNG desse snapshot, sozinha, não fecha a entrega.
Evidência: retorno do dono aos dois apontamentos D-85/FV em 30/09/2026.

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

### Apresentação decimal e ponta chanfrada — 2026-10-03

Comprimentos na ficha FV, inclusive campos de painéis, e cotas do N3 usam uma
casa decimal com vírgula: 417,98 → 418,0; 417,88 → 417,9. É apresentação,
não arredondamento do contorno SA, da medida persistida ou dos pontos DXF.
Salvar um campo que não foi editado conserva o valor preciso original.

O contrato SA→N3 reconhece a ponta chanfrada de um quadrilátero com duas
paredes paralelas no referencial local, independentemente da rotação ou ordem
dos vértices. Preserva o contorno efetivo (inclusive edição humana), deriva os
chanfros por painel após modulação e não repete o chanfro no painel reto.
Não confundir essa ponta convexa com dobra angular em L. Não é prova de
reconhecimento de todo polígono convexo nem autorização para retangularizar
contornos não suportados. As regras independentes de L e chapa de 244 cm
permanecem vigentes. Evidência: `tests/test_fv_decimal_chamfer.py` e relatório
`scripts/arete/relatorios/20261003_fv_decimal_chamfer/RELATORIO.md`.

Cada BLUE/laranja ou exceção FV deve acrescentar ao diário e a este manual: tipo de
encontro, contorno local/contextual, medida, multiplicador, apoio local/global,
convenção de pilar, contraexemplo e regressão. O HTML/SVG validado vira candidato RAG
multimodal **segmento a segmento**, com hashes e decisão humana; não é promovido
automaticamente. Ao fechar todos os laranjas FV do pavimento, consolidar a taxonomia
e pedir ao humano validação para futura curadoria RAG FV.
# Preferência de garfos por pavimento — 01/10/2026

Decisão do dono: garfos Sim/Não em seleção única antes do N3 de fundos e
também no painel Motores. Não é o padrão; não há Não informado. A seleção
fica separada do N1, com snapshot por job. A geometria de garfos ainda aguarda
a regra funcional do dono; Sim é registrado, mas a geração de FV com Sim
é rejeitada explicitamente até implementar essa regra. Não inventar geometria.
Ver `docs/CONFIGURACAO-MODOS-N3.md`, seção Seleção antes de gerar.


### Consolidação de níveis — 2026-10-01

Regra integrada: `docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md` (canônico). Um nível por segmento FV, com fonte, confiança e altura; fundo físico = nível superior menos altura/100. Corte geométrico válido tem precedência sobre associação textual. FV pode receber suporte LV independente quando faltar fonte própria; depois LV lê FV resolvido, sem ciclos. Não usar cota escalar de laje com degrau como prova de contato em toda a laje. D-61 permanece estimativa rastreável.


### Referência padrão e treino de exceções — NIV-PADRAO-EXCECAO-20261003

Aplicar o contrato global em `docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md`, seção Referência padrão e exceções explícitas. O padrão confirmado é topo da viga no nível principal da laje ou base de saída do pavimento quando não há laje, salvo indicação explícita diferente. Ausência de corte não torna esse padrão uma estimativa por si só. Preservar regiões de laje, datum da viga, contato por face do pilar e fontes independentes. QA distingue convenção de medida e verifica qualidade/cobertura da leitura antes de confirmar; não elevar score apenas renomeando status. Interpretação de vigas em níveis diferentes por hatch/corte está pendente de treino com exemplos reais futuros; não foi certificada neste caso.

**Trava QA, corte de planta (04/10/2026, regra derivada).** A marca na planta não basta. A trava lê a elevação (título, topo, espessura e um nível escrito). Plano no datum: a marca deixa de bloquear o padrão. Degrau desenhado ou nível diferente do datum: não certifica, e o valor lido não vira o nível da laje. No 13_PAV o corte B-B é plano em 852,19 e não resolve os 3 cm dos degraus 852,16. Detalhe e evidência: `docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md`, seção Leitura do corte de planta na trava QA.

**Pilar que nasce na trava QA (04/10/2026, D-65 aplicado).** Só um contorno fechado com o símbolo da convenção do pavimento (13_PAV: X) é pilar que nasce e não limita o fundo. Polilinha aberta não é pilar. Sem convenção lida, o encontro fica não certificado. Evidência: `scripts/arete/relatorios/20261004_qa_jev_fv_f0_f2/RELATORIO.md`, 4ª passada.

**Visão corte desenhada na planta (04/10/2026, dono).** O T preenchido de haste 12 cm e conjunto 55 cm, com o texto 55 ao lado (V301, V302, V303 e V306 do 13_PAV), é visão corte, não uma viga. Não abre o fundo e não cria outra viga; o fundo segue contínuo por baixo. O mesmo vale para os outros desenhos da ficha `DUVIDAS-ABERTURAS-FV.html`: T de 120, T de um lado só, números 7, 48, 52 ou 55, e o preenchimento largo à esquerda do T na V330. A cota e o lado da haste não decidem. A forma é a já usada nas outras classes (alma e braços). Evidência: `docs/CONHECIMENTO/DECISOES-DO-DONO.md`, seção FV-VISAO-CORTE-T-20261004.

### Fundo normal contínuo sob invertida — 04/10/2026

Uma invertida não divide o fundo normal que passa abaixo dela quando os níveis
confirmam ausência de interferência e as duas paredes estruturais atravessam
integralmente o encontro. Se há trechos opostos da mesma viga, unir incluindo a
largura atravessada. Não unir através de pilar, mudança de largura/altura, níveis
explicitamente diferentes ou edição humana protegida. A geometria derivada mantém
os IDs e polígonos de origem em `merged_source_segments`, sem reescrever N1.

Caso conferido: VF301 fundos 8 e 9, 289,0175 + 19 + 97,4825 = 405,5 cm,
sob a V330 invertida. Portal e conversão N3 recebem um único fundo. Níveis
herdados de lajes diferentes não provam degrau da viga: conservar as referências
e deixar o nível da união pendente, sem arbitrar um valor. A geometria contínua
não certifica o datum. Evidência e contraexemplos: `test_fv_inverted_crossings.py`;
relatório `scripts/arete/relatorios/20261004_vf301_join/RELATORIO.md`.


### Fechamento de cortes e invertidas (05/10/2026)

Consolidação das regras finais, evidências e pendências: `docs/CONHECIMENTO/CONSOLIDACAO-CORTES-INVERTIDAS-20261005.md`. Compressão tem orçamento de 50 cm, mantendo região das lajes, medidas físicas e fonte original; sinal distinto da inversão. Cobertura SA por segmento de fundo inclui repetições e dispensa interpretado quando o original cobre o trecho. A rodada final confirmou continuidade VF301, mas não regenerou N3 publicado: revisão independente do perfil de 124 cm e certificação por unidade permanecem abertas.


### Cortes locais por perfil e datum medido — revisão 05/10/2026

Cobrir cada perfil físico de cada fundo, incluindo altura diferente e degrau, mesmo quando outro original já cobre um perfil do fundo. Desenhar localmente sem setinhas, comprimir somente cauda e conservar cotas físicas. Confiança: azul claro confirmado, laranja revisar, vermelho invertida. Em viga normal, topo medido da viga e nível regional da laje são referências distintas; referência original única pode ancorar o datum sem alterar N1. Ausência ou conflito de evidência não autoriza assumir datum de viga vizinha. Regras, casos e limites: `docs/CONHECIMENTO/CONSOLIDACAO-CORTES-INVERTIDAS-20261005.md`, seção Revisão final dos destaques.


## Apresentação N3/N5 por modo — 07/10/2026

INI, NOVA e Formascia têm padrões de desenho distintos sobre o mesmo contrato estrutural. Consultar a [matriz canônica de desenho](../../PADROES-DESENHO-N3-N5.md) e o [padrão INI aprovado](../../PADRAO-INI-APROVADO.md). A aprovação visual não altera os dados SA nem certifica automaticamente todos os itens. LAJ INI compartilha o N3/perfil NOVA; os compositores N5 continuam separados.


### 08/10/2026 — fundos: paredes, apoios, cortes e cruzamentos sem divisória

Pedido do dono: corrigir VF3, VF4/VF1, V513, cauda de V514/P18, V524/V526 sobre cortes, V525/V508 e V504/V506/V507/P8; regra universal, sem nomes ou coordenadas no motor.

A faixa pertence ao intervalo axial das duas paredes junto ao rótulo; um par remoto não vence pela proximidade transversal. Fundos automáticos retangulares deslocados são reconstruídos nas paredes medidas. Apoio automático pode ser reassociado somente com identificação e dimensão independentes do DXF; manter decisões humanas. A cauda além de apoio exige duas paredes e chamada de seção compatível entrando nela, conservando o pilar.

Correção da interpretação após esclarecimento do dono: visão de corte é anotação, não obstáculo físico. Mesmo com contorno confirmado no DXF, não exclui área nem segmenta fundos; o fundo segue contínuo por baixo. Sua informação de perfil/nível continua disponível para as análises. Cruzamento ortogonal sem divisória pode trocar a ocupação para reduzir painéis, preservando área, alturas locais, apoios e geometrias humanas. Risco físico na divisória atual ou proposta veta a troca. Uma divisória física real ou mudança de seção/nível continua limitando a união; o desenho da visão de corte por si só não cria essa divisória.

Validação e recibos: `scripts/arete/relatorios/20261008_fv_missing_crossings/`. Aprovação global G2-V e N3/N5 não são inferidas dos testes do SA.

Seções medidas pertencem ao próprio segmento: a reconciliação entre classes não
homogeneíza alturas diferentes usando uma dimensão global da viga. Chamadas
mais afastadas só podem ser associadas com orientação/largura compatíveis e sem
parede interveniente. Uma rodada granular LV preserva integralmente os dados FV
não solicitados, inclusive espelhos e geometria classificada. Visões de corte não entram na máscara de sólidos nem vetam preenchimento de
cruzamentos; a regeneração recupera os trechos automáticos anteriormente
fragmentados, comprovando paredes contínuas. A fonte DXF não é alterada.
Ver recibo atualizado `RELATORIO-CONTINUIDADE.md` no diretório acima.

### Costura automática sem transição física — 08/10/2026

Uma costura dentro de uma faixa contínua e fora das transições locais medidas
não cria um painel físico por haver dimensões textuais diferentes. Unir apenas
retângulos contíguos com paredes comprovadas, sem divisória real, abertura,
diferença de nível ou geometria humana. Preservar as chamadas de seção locais
em `fv_source_section_references`; a divergência não certifica altura uniforme.
`fv_section_transition_unlocated` impede a reconciliação de substituir a seção
local pela seção global ou de uma cauda além do apoio. Caso V514: antigos
segmentos 1 e 2 unidos; cauda além de P18 preservada. Recibo `RELATORIO-V514.md`.

### Vão sem repetição do nome além de apoio — 08/10/2026

O término de um trecho na face do apoio não elimina um vão do outro lado.
Recuperar no inventário compartilhado FV/LV somente com par de paredes do
DXF, chamada local de seção, apoio sólido e um único trecho adjacente identificado
de mesma largura/altura. Nome concorrente, seção diferente ou decisão protegida
vetam associação; não atribuir por simples distância. O apoio conserva sua área.
Caso V517 acima de P16: `RELATORIO-V517.md` no diretório de recibos desta rodada.

### Mudança de largura através do apoio — 10/10/2026

Uma seção local de largura diferente pode continuar a mesma viga através de
apoio sólido quando há uma parede longitudinal comum, altura declarada igual,
duas paredes fonte saindo da face oposta e um único dono adjacente. O apoio
deve cobrir ambas as faixas. Recortar o novo trecho na face oposta antes de
conferir sobreposições: a extensão bruta pode incluir bordas do apoio e parte
da faixa estreita. A chamada de seção precisa ficar no trecho recuperado.
Parede ausente, apoio incompleto, altura diferente, nome concorrente ou
decisão protegida vetam a recuperação. Não unir os painéis nem homogeneizar
suas larguras. O gate de linhas usa os mesmos apoios reais que o inventário
FV/LV; falta de apoio não é suprida por uma etiqueta de proveniência.

O recorte que supera o veto inicial de sobreposição é exclusivo de uma
transição física de largura. Para a mesma largura e seção, conservar o veto
de sobreposição da extensão bruta com trechos conhecidos e exigir que a
extensão já termine na face do apoio. Não recortar fundos existentes nem
eliminar cantos ao recuperar um vão. A validação compara a união geométrica
completa por viga, independentemente da numeração ou partição dos painéis.

Contraprova local: V408 passa de14/55 para19/55 através de P33 e alcança P34.
Valores e nomes são evidência desse desenho, não constantes da regra.
Replays, controles e recibos: `scripts/arete/relatorios/20261010_encontros_niveis_14pav/vf402_fechamento/`.

### Canto diagonal com retorno retangular já reconhecido — 10/10/2026

Quando o gate de linhas recebe os apoios reais, um retorno retangular de
`trecho_de_canto_em_L` pode sobreviver como painel separado. Esse retângulo
não recebe o fechamento do corpo diagonal: um painel inteiramente coberto
pela faixa medida do retorno deve ser ignorado na escolha do corpo a
prolongar. A ordem dos índices não pode impedir a recomposição da cunha
entre as duas pontas oblíquas e a face do apoio. Preservar os vetos de apoio,
proteção e contato; a existência do retorno não autoriza acrescentar área
fora da célula comprovada.

Contraprova V406: com o retorno examinado primeiro, o fechamento informava
área adicionada zero e faltavam 77,893844 cm². Selecionar o corpo diagonal
restituiu a união fonte de 4891,605153 cm² no ensaio local. Comparar a união
completa antes/depois e repetir com o retorno antes e depois do corpo; a
partição de painéis não substitui conservação geométrica. Esse recibo local
não confirma publicação; consultar o replay canônico e seu recibo final.

## ESTILO-INTEGRADO-20261008 — harmonização entre classes

### Anotação de pilar na faixa FV — 10/10/2026

Uma seção B/H próxima ao fundo pode pertencer ao pilar. O QA só exclui essa
anotação como PIL quando há nome original de pilar, agrupamento de legenda
alinhado e um único contorno retangular fechado original com as duas dimensões
escritas. Proximidade isolada ou largura semelhante não basta; ambiguidades
permanecem para revisão. Contraprova do 13_PAV: E39=P8, E3A=19/66 e contorno
253=19×66. Essa seção não prova largura 19 da VF301, cuja própria anotação é
14/55. Excluir a seção errada não aprova automaticamente a seção da viga quando
ela está fora do corredor medido. Preservar a incerteza e a geometria N1.

### Rótulos repetidos e identidade de parcelas — 10/10/2026

Um nome repetido não autoriza atribuir todas as parcelas ao primeiro texto nem
transferir níveis a outro texto só porque escreve o mesmo nome. A ligação de
uma parcela ao rótulo exige que seu handle original esteja na prova de seção
numérica alinhada e do par de paredes observadas no contorno da parcela. Se
mais de um rótulo original puder ocupar esse vínculo, manter a ambiguidade.
Preservar a proveniência e o estado dos níveis, inclusive estimados e inferidos.
Essa prova de identidade/seção não aprova extremos, inventário ou contorno inteiro.

Contraprova 14_PAV: D73=VF402 liga à parcela oblíqua pelas paredes 2A3/2A4
e seção DB6=14/55; D78=VF406 liga à sua parcela pelas paredes 2EC/2F0 e
seção DF6=14/55. O replay local separou essas parcelas do primeiro rótulo;
o ciclo completo posterior ainda é necessário para aprovar a integração.

Um polígono com degrau real, mesmo pequeno, não é retângulo exato. O caso
V302 seg9 do 13_PAV tem degrau 0,0025 cm × 18,962 cm e nome original remoto;
medir largura por caixa não comprova identidade nem autoriza remover a tira.
Uma perda de status QA pode revelar cobertura anterior insuficiente, sem
mudança de geometria. Ela continua bloqueante até a prova original adequada.

### Contorno oblíquo: prova separada dos limites de apoio — 11/10/2026

Uma faixa oblíqua pode ter suas paredes comprovadas sem ter apoio, seção,
propriedade do encontro ou inventário comprovados. O QA deve conservar essas
provas separadamente. A subdivisão recorta somente a fronteira existente do
polígono real; as faces artificiais criadas pelo recorte não viram paredes.
Cada vértice real divide a medição, e a cobertura usa união dos intervalos de
entidades originais com handles. Uma pequena aresta sem nenhuma evidência
continua incerta, mesmo abaixo da tolerância absoluta.

O helper `qa_fv_oblique_boundary_candidate.prove_oblique_boundary` e seu caller
em `qa_fv_corridors.measure_polygon` foram instalados com guarda de fontes/jobs.
Replay14: duas de13 faixas ganharam prova independente de contorno; onze
continuam sem prova completa. Os bloqueios anteriores de limites foram
preservados. Isso não aprova nenhum fundo inteiro. Testes positivos e negativos
do caller/helper passaram; o ciclo integrado continua obrigatório.
Evidência: `integracao_v408_identidade/paths14_oblique_candidate_receipt.json`.

### FV-CRUZAMENTO-INVENTARIO-ORIGINAL-20261010 — prova independente no QA

Uma lacuna em uma aresta do fundo não equivale a uma parede comprovada. O
helper `portal/app/qa_fv_crossing_gap.py` exige par de paredes transversais,
nome e seção numérica originais alinhados; isso identifica o encontro, mas
não escolhe seu dono. D-79/D-83 só certificam cruzamento passante quando
ambas as faixas físicas se desenvolvem dos dois lados do encontro. Um T de
mesma altura fica bloqueado para a regra D-90/FV; continuidade ou soma de
vãos não podem substituir essa distinção.

Para comparar continuidade, o componente físico se reconstrói por duas
paredes originais. Uma interrupção só é atravessada por um encontro
transversal com identidade própria. Nomes e seções de outro componente
desconectado na mesma faixa não são concorrentes desse componente; nomes
concorrentes dentro dele impedem aprovação. Pilares sólidos são recortados
por seu polígono original, antes de comparar desenvolvimento e continuidade.
Não se usa caixa do fundo, dimensão global da viga ou classificação do SA
como autoridade independente.

`portal/app/qa_fv_source_inventory.py` exige nome + seção numérica + contorno
original para a propriedade do pilar e lê seu símbolo pela declaração
original. NASCE exclui somente seu próprio contorno, conservando outro
sólido sobreposto. Ambiguidade é localizada: um possível contorno original
inteiro bloqueia o corredor que o intercepta, sem impedir outro componente
distante. Nome sem contorno mantém sua região próxima como incerteza;
ausência de declaração ou de inventário de preenchimentos continua
bloqueante. Contornos manuais ou validados exigem reconciliação e não são
substituídos pela escolha automática.

A declaração do 14_PAV está no **recorte original `detalhes.dxf`**, SHA-256
`b7fb64c85187148e7850cf9f3934a32c23a6839c219e922e0fe3f470ce8b8231`, e não na
torre limpa. Cabeçalho 54A; rótulos 547=NASCE/CROSS, 548=MORRE/EMPTY,
549=SEGUE/DIAG. O loader aceita declaração explícita no estrutural ou no
detalhe vizinho do mesmo recorte, confronta conflitos e inclui o arquivo
de detalhes na chave do cache. `context.convention={}` não significa que
o desenho não tem declaração: conferir os arquivos de origem.

Evidência local: 83 testes FV passaram, incluindo ausência de legenda,
símbolo ambíguo, nome sem propriedade numérica, concorrente local/remoto,
T de mesma altura e proteção manual. O replay encontrou 31 polígonos sólidos
comprovados em cada pavimento; as incertezas restantes são preservadas.
Recibo: `integracao_v408_identidade/fv_inventory_finish_receipt.json`, dentro
de `scripts/arete/relatorios/20261010_encontros_niveis_14pav/desenvolvimento_rapido/`.
**Essa prova é local: ciclo completo após deploy e conferência final ainda
pendentes; nenhum fundo está aprovado por este registro.**

Síntese vigente, convenções recorrentes, contraprovas e pendências: [Estilos estruturais — interpretação integrada](../../CONHECIMENTO/ESTILOS-ESTRUTURAIS-INTERPRETACAO-INTEGRADA.md). Consultar a evidência local antes de aplicar a regra a outra obra; cooperação entre classes não constitui prova circular nem aprovação automática.


### FV-PONTAS-CHANFRO-SIMPLES-PRIORIDADE-20261012 — refinamento do dono

Nos encontros, priorizar chanfros simples nas pontas de todas as vigas,
harmonizando a repartição entre os fundos. Uma ponta complexa só permanece
com necessidade explícita e demonstrada. O dono reprovou a ponta da V406
no encontro com V407/VF402 na ficha 03 do 14º; não decidiu novamente a
dobra junto ao P25. Aplicar a preferência de forma geral, em conjunto com
as restrições e provas de D-85/FV acima: preservar a união externa,
exclusividade dos donos, apoios, contornos protegidos e comportamento
físico comprovado. Não apagar área nem simplificar uma peça isoladamente
criando lacunas ou sobreposição. Correção e regressão continuam pendentes.
Fonte: DECISOES-DO-DONO.md, FV-PONTAS-CHANFRO-SIMPLES-PRIORIDADE-20261012;
recibo v406_human_chamfer_receipt_20261012.json e apontamento original do dono.


### FV-ALTURA-SEGMENTACAO-DESEMPATE-20261012 — prioridade no encontro

1. Alturas diferentes: a viga mais profunda sempre passa; a menos profunda
   sempre para. A conveniência de fabricação não altera essa prioridade.
2. Apenas em alturas iguais: favorecer a alternativa válida com menos
   segmentos e tentar evitar segmentos menores que 60 cm quando possível.
3. Segmentos necessários menores que 60 cm devem ser gerados e preservados;
   não existe mínimo obrigatório nem descarte automático de peças pequenas.

Avaliar a repartição entre todos os fundos do encontro, preservando a união
externa, apoios, donos e ausência de sobreposição. A regra refina a escolha
por conveniência e D-90/FV; não escolhe sempre a mesma direção de chegada
por nome ou por formato T. Caso humano de referência: na ficha 04 do 14º,
V407 para e V413 passa para evitar um segmento pequeno desnecessário na
V413. A preferência pelos chanfros simples continua vigente. Não confundir
o limiar desejável com regras de modulação das laterais.
Fonte: DECISOES-DO-DONO.md, FV-ALTURA-SEGMENTACAO-DESEMPATE-20261012;
v407_v413_human_junction_receipt_20261012.json. Implementação e regressão
permanecem pendentes; o registro humano não aprova o QA automaticamente.
