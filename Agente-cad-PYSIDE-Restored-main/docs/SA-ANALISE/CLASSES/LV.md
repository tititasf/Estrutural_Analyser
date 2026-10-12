# LV — manual granular de interpretação, validação e evolução

> **NOVA/LV — padrão aprovado em 2026-10-05:** para o desenho N3 AB e Visão Corte, prevalece a [especificação vigente](../../PADRAO-NOVA-LATERAIS-APROVADO.md). Para/Passa conservam contratos independentes; gradeadas/sarrafeadas conservam artefatos independentes. As descrições do motor anterior abaixo continuam como referência de interpretação/contrato e não substituem as regras visuais aprovadas. Integração local em validação; geração publicada N3/N5 ainda não comprovada.

**Cortes sobre o estrutural — 2026-10-02:** o dono esclareceu que a aba
“Todos” de SA deve desenhar as seções SA sobre a viga, substituindo
as faixas e etiquetas longitudinais de segmentos. Cada VC calculada recebe
um desenho no centro do maior trecho válido dos seus pares publicados.
Largura, altura, espessuras e desníveis das lajes vêm do contrato canônico
da seção. A orientação usa a normal entre as faces A/B; coordenadas CAD
são convertidas pela transformação do estrutural original. A largura local
atravessa A→B; a altura do corte segue o eixo longitudinal da viga (corrige
a rotação anterior de 90°). Ao selecionar uma VC calculada em SA Visão Corte,
o mesmo desenho aparece isolado sobre o estrutural com recorte local,
preservando o índice original da VC e sem outros desenhos sintéticos.
São desenhados
viga, lajes e cotas, sem componentes de fôrma N3. Cortes identificados são
preservados no SVG original; recebem contorno e cotas do contrato SA,
com identificação externa. A espessura anotada da laje prevalece sobre
o símbolo geométrico, inclusive sem cota total identificada. O desnível
é preservado e o trecho inferior é recalculado. Se o símbolo divergir,
somente o destaque é normalizado; o DXF original permanece intacto.
Regressão: símbolo de 10 cm com anotação h=12 e desnível 7 em viga
de 55 cm deve produzir 7 + 12 + 36, nunca 7 + 10 + 38.
A âncora e a orientação vêm
do fundo do próprio polígono, mesmo sem pares. O destaque não usa os
círculos e o nome gigante do visualizador antigo. Se o fundo não puder ser
identificado univocamente, a vista granular original permanece disponível. Contratos inválidos
ficam em `blocked_drawings`, sem geometria inventada. Etiquetas das laterais
continuam reduzidas a 1/3. Pan/zoom continua por viewBox.

**Cotas das paredes — 2026-10-02:** nos cortes calculados sobre o estrutural,
cada lado recebe uma cadeia de cotas pelas fronteiras reais da laje:
trecho superior, espessura e trecho inferior, omitindo intervalos nulos.
Sem laje, a parede tem a cota integral. Removido o texto h= acima da laje;
espessura é cotada ao lado dela. Mantidas largura e altura total, com a
altura total em linha externa separada. Texto das cotas passou de 2,5 para
5 cm CAD (dobro), acompanhando a rotação da seção.

**Subabas SA/N3 — decisão do dono, 2026-10-02:** SA Visão Corte possui
Todos (cortes juntos no estrutural) e VC individuais, sem aba estrutural
redundante. N3 Visão Corte mantém Todos (todos os desenhos N3),
Todos no estrutural (localização SA na planta) e VC individuais.

**Contraste dos destaques — 2026-10-02:** pedido do dono de clarear a paleta
em direção ao branco e reforçar linhas/textos. Overlay mistura 35% branco,
mantendo a identidade das cores; etiquetas em peso 700 no mesmo tamanho.
Contornos de segmentos do mapa com 2,5 px; demais destaques com 3,5 px;
líderes com 2 px. Estilo inline importante prevalece sobre a normalização
de traço do SVG base, sem mudar as linhas originais do CAD.

**Aberturas e cortes — decisão do dono, 2026-10-02:** abertura causada por
outra viga fica somente nas laterais, sem acrescentar Visão Corte. O pareamento
subtrai a faixa de `beam_openings` no eixo longitudinal, respeitando o sentido
original de cada segmento e mantendo `opening_exclusions` na proveniência.
Não eliminar trechos apenas por serem curtos ou sem laje. Cobertura excluída
por abertura é conhecida e não equivale a lacuna sem contraparte.

**Lajes por região:** quando `slab_steps` fornece contornos, espessuras e cotas
regionais, a seção usa a região em contato. A principal é o contorno da laje
menos as regiões internas. Dado regional ausente não recebe a cota escalar da
laje inteira. Tolerância de contato CAD de 0,05 cm não autoriza dois perfis
simultâneos da mesma laje numa face por uma tira microscópica de arredondamento.

Validação publicada de 02/10/2026: 54 testes e auditoria independente de 258
trechos, 51 exclusões de abertura e 186 seções em 71 combinações
viga/comportamento. Sem erro de contrato, seção duplicada ou par fora da faixa
comum/dentro de abertura. Rodada SA acionada pelo motor interpretativo web,
job `7ddb2b94-1d3f-4e4e-9f49-91c2042f316b`, concluída com 186/186 cortes
materializados automaticamente em NOVA. Auditoria repetida sobre o estado
final sem erros; isso não aprova paridade N4 ou G5. Referência:
`scripts/arete/relatorios/20261002_cut_region_fix/RELATORIO.md`.

**Visão Corte — decisão do dono, 2026-09-30:** agrupar pares A/B com a mesma
seção. O inventário derivado `src/core/lv_cut_inventory.py` mede a sobreposição
longitudinal das faces paralelas, inclusive B invertido e quantidades diferentes
de segmentos. A seção usa largura, altura, diferenças relativas de nível e
espessura/posição relativa das lajes; a cota absoluta e o nome da laje não
multiplicam seções fisicamente iguais. Medidas ausentes não provam equivalência.
Cada seção preserva os pares, comprimentos, coordenadas e lajes de origem.
Cobertura parcial e sobreposição de pares são diagnósticos, nunca preenchidas
com pares por índice.

O portal reúne também cortes explícitos do snapshot SA, as geometrias/fichas
ricas em `laje_visao_corte`/`laje_nivel` e o pacote de pré-processamento da torre
e revisão correspondentes. Deduplicação geométrica preserva decisões SA e
rejeições humanas. Associação geométrica FV/LV única identifica o corte; uma
atribuição SA sem essa prova fica indicada como associação a confirmar. Chamadas
de pré-processamento sem vínculo ficam pendentes, sem associação por proximidade.
O adapter atual de pré-processamento é somente `explicit_labels_only`; não
prometer identificação completa de seções por esse inventário textual.

Os cortes calculados são esquemas estruturais SA derivados, com níveis estimados
explicitamente sinalizados, sem selo QA e sem montagem STOG. O desenho N3 comum
da viga fica em **Todos**; não prova um N3 correspondente a cada VC calculada.
Fonte/limites/testes: relatório `20260930_lv_visao_corte/VALIDACAO-INVENTARIO.md`.

**Colunas do portal — decisão do dono, 2026-09-30:** `Possui aberturas?`
lista os encontros com viga menos profunda registrados na célula do segmento,
com dimensão, posição esquerda/direita/interna e distâncias na ordem de leitura.
Abertura pertence ao segmento anterior à divisão (§5.2.3 do contrato).
`Passa por pilares?` é sempre **Não** em Para. Em Passa registra apenas a
parede física das faces **A/B/E/F/G/H**, excluindo C/D; mostra pilar, face,
distância esquerda, comprimento ocupado no segmento e distância direita, em cm.
As três medidas somam o comprimento do segmento. Não usar caixa envolvente
do pilar em L como contato, nem confundir este comprimento físico com a
abertura de sarrafo `comprimento + 22` de G8. `lv_cell` deve acompanhar o
snapshot publicado; não ler um índice legado compartilhado entre Para/Passa
quando a célula publicada está disponível.

## 1. Contrato: quatro interpretações, não uma lateral genérica

LV é a matriz fechada **lado A/B × comportamento PARA/PASSA**. Cada célula tem
seleção, segmentos, ajustes, painéis e prova próprios. O corte é contexto comum,
mas nunca autorização para espelhar dado. `BeamTracer` fornece topologia bruta;
`src/core/beam_interpreters/lateral_viga.py` é dono da semântica; o contrato N3 é
`src/core/lv_generation_contract.py`.

**Jev opcional:** só para conflito localizado de célula A/B × Para/Passa
**no mesmo encontro** (uma parede fonte + um extremo), atribuição à própria
ocorrência ou apoio; fornecer a cena medida e os quatro contratos, sem decidir
pelo flag `lv_is_h` sozinho. PARA num extremo e PASSA no outro são encontros
distintos (catálogo v2 retirado). Inventário fonte: catálogo v3
(`scripts/arete/jev_calibration/adapters_lv_v3.py`). Ver [segunda leitura do
SA](../JEV-SEGUNDA-LEITURA-OPCIONAL.md) e
[registro de capacidades](../JEV-CAPACIDADES-E-REGISTRO-DE-MEDICAO.md).

| Contrato | Significado | Saída exclusiva | Invariante |
|---|---|---|---|
| A_PARA | lado A termina no encontro | slots A/PARA | não recebe dados B/PASSA |
| B_PARA | lado B termina no encontro | slots B/PARA | não recebe dados A/PASSA |
| A_PASSA | lado A continua pelo encontro | slots A/PASSA | não recebe dados B/PARA |
| B_PASSA | lado B continua pelo encontro | slots B/PASSA | não recebe dados A/PARA |

FV não pode fornecer dimensão, painel, apoio nem fallback semântico a LV. A presença
de `_sa_meta.fv_dimension_fallback` é FAIL de isolamento, não conveniência.

**Regra do dono (2026-09-25): FV é referência/comparação para a LV, nunca lei.**
A segmentação N1 das quatro células sai de `lateral_viga_cells.py` sobre a cena
medida em `lv_beam_scene.py` (regras do guia G0/G1/G6-G9, Casos 9 e 11). Estado,
defeitos corrigidos e prova: `docs/CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md` §6.1.1.
Dúvidas abertas: `docs/QUESTIONARIO-LV-SA-2026-09-25.md`.

**Passa sobre pilar tem laje (D-91, 2026-10-10):** o trecho Passa que segue a parede do pilar declara a laje que encosta na face, igual ao Para; não ficar sem laje só por estar no pilar.

**Encontro colinear de alturas iguais — dono, 2026-10-10:** escolher apenas
um trecho para englobar o pilar, por conveniência. Vale também para trechos
da mesma viga com larguras diferentes, nas faces longas A/B/E/F/G/H;
preservar a exceção C/D e Para de D-64/G10. Substitui a parte de D-63 que permitia
ambos englobarem quando as alturas fossem iguais. No caso V408/P33, o dono
confirmou escolher o trecho 19/55. O escolhido recebe ajuste **+11 cm além
da face oposta do pilar**; o outro recebe **−11 cm antes da face de entrada**.
São os ajustes de destaque das laterais: manter os contornos estruturais nas
paredes medidas, com sinais em `lv_cell.adjustment_start/end`; converter para
comprimento executivo uma única vez. A escolha automática geral usa maior
largura, depois identidade/geometria estável, sem regra por item. Resolver
somente a parede física compartilhada; não transferir a decisão à outra face
nem à interpretação Para. Profundidades diferentes mantêm a regra da mais
profunda. Níveis distintos permanecem separados e não são igualados pela
escolha de montagem.

**Passa — decisão do dono de 2026-09-30:** a lateral pode seguir toda a parede
externa do pilar (inclusive faces A–H), mas nunca atravessar seu interior.
Pilares côncavos exigem intervalos separados de parede e miolo por lado; um
indicador único para o pilar inteiro não basta. A extensão deve medir a parede
completa, sem truncá-la pela janela de busca do apoio. Um encontro externo com
viga menos profunda continua por baixo e abre novo segmento na borda final da
incidente, mesmo quando ocorre na parede de um pilar da extremidade. Isso não
altera Q3 para vigas realmente embutidas no pilar, nem a interpretação PARA.
Prova e regressão: `scripts/arete/relatorios/20260930_thierry_passa/`.

## 2. Ficha e matriz de campos N1

A ficha `laterais_viga/` deve separar explicitamente lista PARA/PASSA e face A/B.
Ler SVG local antes de contexto/corte: o local decide segmento e extremidade; o
corte só contextualiza altura e sequência. Conferir todos os quatro contratos mesmo
quando um esteja N/A; ausência justificada não é célula copiada.

| Família | N1/contrato | O que provar no SVG e DB | Falha que o número não vê |
|---|---|---|---|
| identidade | `fields.nome`, `fields.dimensao`, versão | viga certa e seção correta | campo de viga vizinha |
| lado A | `viga_a_seg_N_*`, links A | contorno, ordem, largura/altura e apoio A | A desenhado na posição B |
| lado B | `viga_b_seg_N_*`, links B | idem para B | espelhamento silencioso |
| comportamento | `lv_generation_contracts.{Para,Passa}.{A,B}` | `contract_id`, `side`, `behavior`, readiness | PARA reaproveitado como PASSA |
| origem | `structural_segments.*.source_key/source_slot` | cada painel aponta ao segmento N1 correto | origem agregada sem painel |
| exceção | pilar, laje, pontalete, grade, endpoint event | evento pertence à célula certa | evento aplicado ao lado oposto |

O probe `four_contracts_and_support` verifica contrato, isolamento, source key/slot,
readiness e apoio. É a primeira consulta para item persistido. Não use uma dimensão
de corte ou de FV para “consertar” uma lateral.

## 3. Diagnóstico, score N1×N2 e visual CLI

`diagnostico_lv_n1_n2.py` é principalmente comparador de dimensões/segmentos por
lado. Ele não prova comportamento PARA/PASSA, ajuste, grade, abertura, pontalete ou
espelhamento; estes entram obrigatoriamente na matriz S5 e no SVG. Pontuar por célula:

1. identificar a parte N2 equivalente (A/B, PARA/PASSA, corte quando aplicável);
2. comparar nome, lado, comportamento, quantidade/ordem, altura, comprimento,
   ajuste inicial/final, apoio e exceções;
3. registrar match/mismatch/N/A e score; N/A só com fonte;
4. sem divergência não triada nos campos extraíveis/algorítmicos (0,05), liberar N3.

```powershell
# DB/probe: segundos, sem headless
python scripts/arete/qa_evidence_auditor.py review --project-id <ID> --classe LV --include-sealed
python scripts/arete/qa_profile_probe.py --classe LV --probe four_contracts_and_support `
  --item V328 --project-id <ID>

# mudança de interpretação somente aqui
python scripts/arete/headless_sa_analise.py --obra <OBRA> --pav <PAV> `
  --secao laterais_viga --item V328 --wait
python scripts/arete/g2v_harness.py --classe LV --pav <PAV> --par n1xn2 `
  --item V328 --backend cli --lista-lv passa
```

N1-V/G4-V (interpretação N1×N2) e G5-V (paridade final N3×N4): SVG canônico
rasterizado em PNG pelo `g2v_harness.py --backend cli` — o agente CLI **lê o PNG**
(`--zoom` para região densa), sem API visual; SVG como texto só para consulta pontual.

### 3.0 Visão canónica (obrigatória — senão é ruído)

Documento mestre: [`docs/QA-VISAO-EVIDENCIA-CANONICA.md`](../../QA-VISAO-EVIDENCIA-CANONICA.md).

| Etapa vision | Evidência N2 | Evidência N3/N4 |
|--------------|--------------|-----------------|
| G2-V N2×N4 | DXF `recorte_path` → **SVG full layers** (como CE) | `VIEW_A`/`VIEW_B`/`CORTE` → SVG |
| N1-V / G4-V | recorte se existir + SVG ficha | SVG N1 da ficha |
| G5-V N3×N4 | — | SVGs N3 e N4 da ficha granular |

- **N2 no CE** = recorte full layers — autoridade visual humana.
- **Agente** julga em **PNG** full-render; **SVG** no HTML persistido/portal.
- Headless **sem** `--persist-db` = imagem dinâmica; **com** persist = SVG no HTML.
- Plot LINE-only = audit interno; **não** se chama “N2” sozinho.
- Botão **Passa** no CE = Para/Passa estrutural; **não** é PASS visual.
- Mecanismo: `g2v_harness.py --backend cli` + inventário + pack PNG vision.

### 3.1 Inventário mínimo (obrigatório para PASS visual N2×N4)

**Proibido** aprovar LV por contagem de entidades, score de imagem ou “parece
igual”. Antes do veredito visual:

0. SVG canónico N2 (recorte CE) e N4 (VIEW_*) — §3.0.
1. Extrair inventário N2 face (e B/corte se no par): cada `LINE` Painéis+SARR
   com coords relativas, cada cota, cada texto de identidade.
2. Match N2→N4 com status `MATCH|NEAR|MISSING_N4|EXTRA_N4|N2_VOID_JUNK…`.
3. Anexar path no veredito (`inventario.path`) e marcar checklist
   `inventario_minimo_extraido`, `linhas_estruturais_rastreadas`,
   `cotas_valores_rastreados`, `textos_identidade_rastreados`,
   `sem_aprovacao_por_contagem`.

**Contrato de cotas:** N2 LV usa `TEXT` numérico (muitas vezes layer `Painéis`);
N4 usa `DIMENSION` dimstyle `PAINEL`. Match por **valor + posição**, não por
tipo de entidade.

Protocolo: [`docs/QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md`](../../QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md).  
Exemplo ouro V301: `scripts/arete/relatorios/g2v/v301_arete_review/` (SVG).

## 4. Casos difíceis e roteamento de correção

| Sintoma | Hipótese/refutação | Dono do fix | Não fazer |
|---|---|---|---|
| A e B iguais sem origem equivalente | verificar `source_slot`, geometria local e eventos | contrato lateral do lado afetado | copiar A→B |
| PARA e PASSA iguais | só aceitar se ajustes/eventos também coincidem | contrato do comportamento | assumir igualdade pela dimensão |
| comprimento certo, painel errado | conferir soma de painéis, ordem e offsets | contrato/gerador LV | fechar por bbox total |
| abertura em lado errado | provar contato do pilar/laje e extremidade | lateral + relação contextual | espelhar exceção |
| corte correto, faces erradas | corte é contexto, não fonte de face | interpretador lateral | usar corte como preenchimento |
| quatro contratos falham a partir do eixo | provar defeito bruto multi-contrato | `BeamTracer` | corrigir cada slot com hack |

## 5. N3, variantes e não regressão

Gerar variante individual (`A_PARA`, `B_PARA`, `A_PASSA`, `B_PASSA`) sem headless;
depois `qa_n3_smoke.py` e `ficha_motor_item.py`. O smoke prova identidade/texto/camadas
e contrato; a leitura SVG prova painel, ajuste, abertura, grade e posição. G5
(paridade final N3×N4) não pode ser “por construção”, e match por herança N2/N4 é
`vazamento_gabarito`.

Validação congela topologia apenas na célula correspondente: validar A_PARA não
congela B_PARA/A_PASSA/B_PASSA. Campos e vínculos ainda não validados continuam
recalculáveis. Depois de tocar `lateral_viga.py`/contrato LV: teste da célula, teste
negativo das três células, microciclo e diagnóstico LV. Se tocar `BeamTracer`, aplicar
regressão das quatro classes e registrar em `HISTORICO/LV.md`.

## 6. Autoevolução e candidato RAG LV

Toda descoberta BLUE/laranja registra lado, comportamento, `source_key/source_slot`,
ajustes, evento e contraexemplo A/B×PARA/PASSA. Atualizar o manual somente depois de
prova e teste negativo das três células vizinhas. O HTML/SVG aprovado vira candidato
RAG multimodal por contrato, nunca por “viga lateral genérica”. Ao fechar os laranjas
LV do pavimento, pedir validação humana do pacote para futura curadoria RAG LV.

## 7. Quadro QA read-only por pavimento

`scripts/arete/qa_lv_quadro_pavimento.py` projeta somente evidência já persistida
no DB e artefatos canônicos em `QUADRO-LV-PAVIMENTO.{html,json,csv,md}`. Ele nunca
executa headless, gate, gerador ou escrita no DB; portanto não cria N1/N3, não altera
N2/N4/DXF/JSON Fase-4 e não concede selos.

O HTML possui duas tabelas independentes, **PARA** e **PASSA**; cada uma tem uma
linha por viga/comportamento e conserva seus dois contratos explícitos (`A_PARA` /
`B_PARA` ou `A_PASSA` / `B_PASSA`) dentro das etapas N1/SA e N3. Para cada uma o quadro mostra
`contract_id`, readiness, segmentos/painéis, dimensão, apoio inicial/final, ajustes,
eventos de extremidade/recortes, `source_key/source_slot`, `behavior_isolated` e o
veto `fv_dimension_fallback=false`. O corte aparece somente como contexto comum; não
duplica nem espelha face ou comportamento.

As colunas seguem: etapa/próximo passo → N2 → N4 → N1/SA → N1-V CLI → N1×N2 → N3
→ N3×N4 → N3×N2 → S8/RAG HTML pós-QA. A coluna S8 lê exclusivamente
`rag_artifact_validations`: só mostra ingestão quando o registro é HTML, ativo, não
revogado e tem `validation_origin` QA. A geração de uma ficha HTML nunca promove o
item automaticamente para RAG. G2 e G2-V ficam dentro de N4; N4 admite exclusivamente selo azul
humano e laranja QA. N1/N3 exibem quatro selos, sempre como estado lido e nunca
inferido. Evidência visual é SVG de relatório do `g2v_harness.py --backend cli`;
ausência de veredito fica “não registrado”, sem virar aprovação ou FAIL.

O quadro também pode ler, sem alterar nada, o último pacote completo de
`html_fichas/..._laterais_viga_*` e os DXFs `LV_preview_*.dxf` N4. Esses artefatos
recebem o símbolo de realização (✓) somente como evidência de execução/materialização;
eles não viram selo e não substituem contrato persistido. Em especial, um pacote
headless sem `--persist-db` é snapshot para revisão humana: deve ser exibido como tal,
sem alegar que atualizou o DB. O DXF N4 existente é referência do fluxo N2/PASSA e
nunca preenche ou valida a linha PARA.

```powershell
D:\Agente-cad-PYSIDE\.venv\Scripts\python.exe -X utf8 scripts/arete/qa_lv_quadro_pavimento.py `
  --project-id dd238e47-1dc6-4f63-a760-4e7ce19a7386 --obra Obra_TREINO_1 --pav 13_PAV `
  --output-dir scripts/arete/relatorios/qa_quadro_lv/Obra_TREINO_1/13_PAV/<timestamp>
```
# Preferência de laterais por pavimento — 01/10/2026

Decisão do dono: Gradeadas/Sarrafeadas são opções de seleção única antes de
gerar N3, compartilhadas pelas laterais Para e Passa do mesmo pavimento.
Sarrafeadas é o padrão; não há Não informado. A configuração mora separada
do N1 e altera apenas cópias dos contratos de geração (panel_type e grade_h1/2).
INI/NOVA/Base 1/Base 2/Base 3 são selecionados acima do N3 de cada classe.
Ver `docs/CONFIGURACAO-MODOS-N3.md`, seção Seleção antes de gerar.

## QA de quantidade Visão Corte — 01/10/2026

Rodada real na VPS pelos botões SA e desenho de classe do 13_PAV:
105 cortes Passa (36 vigas), 89 Para (35 vigas). Materialização complementar
do resolvedor publicado: 194 SVGs, zero bloqueados. A lacuna inicial do botão
de classe foi corrigida em `pipeline_runner._rodar_subprocess_sa`: depois
de promover o snapshot atual, SA completo ou `laterais_viga` chama
`lv_n3_cuts.materialize_pavimento` para ambos os comportamentos. Microciclo
respeita `--item`; modo respeita `--visual-mode`. O inventário é refeito do
estado atual, não contado a partir de DXFs antigos. Falhas de contrato/SVG
impedem sucesso do job; o log inclui quantidade esperada e materializada.

N4 local do mesmo pavimento: 34 cortes em 31 vigas, contagem concordante
entre ficha N2 extraída live e anatomia a/b/c dos DXFs CORTE. Sem referência
N4 disponível: V307, V309, V309A, V313, VF202. Comparação Passa nas 31 vigas:
94 N3 contra 34 N4. Zero assinaturas físicas exatamente duplicadas no novo
inventário, sem conceder aprovação de interpretação ou selo G5.

V301: 16 trechos A/B viraram 8 seções, enquanto N4 tem 2. A diferença resulta
de quatro perfis de laje por duas alturas (55/120). SA usa espessuras anotadas
12/13/10 cm; N4 desenha 13/10 cm. Divergência de critério de laje deve ser
resolvida antes de descartar variantes. V330 tem 6 cortes contra 2 N4, com
cinco entradas usando nível estimado. N4 é referência do fluxo N2/Passa;
quantidade Para consta apenas como inventário, não como paridade com N4.

Evidências por viga e seção:
`scripts/arete/relatorios/20261001_qa_cut_n3_n4/RELATORIO.md`, CSVs e JSONs.

Pareamento: sobreposição positiva no eixo longitudinal (X horizontal, Y
vertical, projeção longitudinal nos inclinados), faces paralelas e distância
compatível com a largura. Extremos que só encostam não formam par. Um A sobre
três B gera uma seção se os perfis forem iguais, três se forem diferentes.
36 testes passaram, incluindo esses casos, mudança de inventário entre
rodadas, escopo de item/modo/pavimento e erro de SVG. Auditoria independente
dos 258 pares publicados: zero trechos fora da faixa compartilhada.

Validação da integração pelo botão interpretativo na VPS: job
`4d972ff2-12df-4650-928e-b49e367dee42`, 01/10/2026 21:48:34–21:52:42 UTC,
concluído. Snapshot novo: 186/186 cortes materializados automaticamente
(101 Passa, 85 Para), zero erros de contrato/SVG e zero assinaturas duplicadas.
Auditoria final novamente: 258 pares, nenhum fora da faixa longitudinal.
Relatório: `scripts/arete/relatorios/20261001_dynamic_cut/RELATORIO.md`.

### Diagnóstico do excesso de cortes (01/10/2026)

A auditoria longitudinal não aprova a semântica dos cortes. Nas 31 vigas
Passa com N4: 90 N3 versus 34 N4; só 37 combinações de largura/altura,
as outras 53 variantes decorrem dos perfis de laje. `pair_sections` não
consulta `beam_openings`, e `_profile`/contrato não representam a abertura.
Faixas dentro de aberturas acabam representadas como seções sem laje e
concreto integral. Confirmado por projeção dos intervalos: V302/V303 na
V310 (~14 cm), V312 na VF301 (13,99 cm), V330 na V301/VF301/V302 (14/19 cm).
Não excluir toda ausência de laje ou todo trecho curto: distinguir regiões
de abertura e ausência real; resolver medidas por localização.
V301 multiplica 2 alturas por 4 perfis de laje anotados. V302 e VF301 também
têm divergências de altura/desnível entre identificado e calculado. Nenhuma
redução de quantidade foi aplicada durante esta investigação somente leitura.
Evidência: `scripts/arete/relatorios/20261001_dynamic_cut/EXCESSO-CAUSAS.md`.


### Consolidação de níveis — 2026-10-01

Regra integrada: `docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md` (canônico). Associar nível aos fundos por posição e cobertura, não por número de segmento. Para/Passa e A/B podem ter mais ou menos segmentos que FV. Separar faixas quando a LV toca fundos de cotas diferentes; conservar limites, fontes e confiança de cada faixa. Regiões de laje e corte fornecem suporte local. Transferência de fonte estimada continua estimada.


### Referência padrão e treino de exceções — NIV-PADRAO-EXCECAO-20261003

Aplicar o contrato global em `docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md`, seção Referência padrão e exceções explícitas. O padrão confirmado é topo da viga no nível principal da laje ou base de saída do pavimento quando não há laje, salvo indicação explícita diferente. Ausência de corte não torna esse padrão uma estimativa por si só. Preservar regiões de laje, datum da viga, contato por face do pilar e fontes independentes. QA distingue convenção de medida e verifica qualidade/cobertura da leitura antes de confirmar; não elevar score apenas renomeando status. Interpretação de vigas em níveis diferentes por hatch/corte está pendente de treino com exemplos reais futuros; não foi certificada neste caso.


### Laterais cruzando invertidas — 2026-10-04

No destaque estrutural, laterais de invertidas confirmadas alternam segmentos com cores sólidas vermelho/branco; partições do mesmo segmento mantêm sua cor, sem tracejado ou listras. A continuidade de laterais normais exige duas paredes medidas, cobertura local da invertida e comparação dos intervalos absolutos de montagem dos painéis. Faixa de laje comum só pode ser descontada quando ambos os contratos confirmam nível e espessura compatíveis. Contato fora dessa faixa continua bloqueando. Pilares, alterações de profundidade/nível e geometria manual validada permanecem obstáculos. A união mantém coordenadas físicas das aberturas; remove apenas a abertura da viga incidente dentro da travessia comprovadamente livre. Aplicação derivada para portal/N3, sem alterar N1.

Na produção 13_PAV, VF301 Passa A une 8+9 em 405,5 cm; B une a chegada correspondente preservando aberturas de pilares. Na chegada V301/V330, a lateral normal alcança a face B medida; o P49 termina nessa mesma face e não impede os 19 cm de chegada. Pilar que ultrapassa a face de destino continua bloqueando. As pendências N3 da V330 foram resolvidas pela prioridade de cobertura real e continuidade restrita ao pilar terminal, conforme consolidação abaixo. Evidência: scripts/arete/relatorios/20261004_lv_inverted_crossings/RELATORIO.md.

### N3 invertidas: estações estreitas e pilares terminais (04/10/2026)

Contrato N1 com alturas iguais nas pontas representa uma única banda de painel, não duas alturas somadas no esquema robô. As estações confirmadas usam `generate_local_panels` e preservam comprimentos, alturas locais e aberturas, sem heurísticas de marco N2. Cobertura vertical terminal só se estende dentro do contorno medido do pilar nomeado e com seção adjacente confirmada e única. Resolução incidente prioriza footprint real, depois footprint de encontro, depois tolerância; tolerância não mistura perfis vizinhos. Evidência: `scripts/arete/relatorios/20261004_lv_inverted_crossings/RELATORIO.md`, 186 testes e 18 DXFs de validação VPS.

O destaque Passa compartilha essa continuidade terminal com o N3. Após reconciliar os cruzamentos sem colisão, no degrau da V330 os segmentos lógicos A2 e A3 continuam distintos e ambos invertidos: níveis 852,19/852,16 e lajes 13/10 cm. Uma cobertura pendente dentro do P18 não deve transformar toda a lateral terminal em normal. A extensão confirmada limita-se ao sólido medido do pilar; não cobre vão livre nem apaga mudanças locais. Cores sólidas alternam por segmento lógico, incluindo suas partições.


### V330: segmentação lógica das laterais invertidas (04/10/2026)

Regra simétrica: a lateral invertida também atravessa a viga normal abaixo quando os intervalos absolutos dos painéis comprovam ausência de colisão. Não basta o nome ou a classificação da viga. Exigir cobertura confirmada dos dois trechos adjacentes, mesma altura, encontro incidente medido e suportes de viga correspondentes. Pilares, degraus, mudanças de altura e geometria manual validada continuam preservados.

Na V330 são **3 segmentos A e 2 B**, tanto Para quanto Passa. A separa 71, 120 antes do degrau e 120 depois; B separa apenas 120 e 71. Os encontros com V301/VF301 abaixo não criam divisões. O destaque desenha um contorno e nome por segmento lógico, alternando vermelho/branco; os perfis internos de montagem ficam no contrato N3 e não geram contornos adicionais na planta. UIDs de origem permanecem estáveis; a numeração exibida é sequencial após a união. Aberturas reais de pilares preservam sua posição e fragmentos da mesma abertura são reunidos sem duplicar a folga.

Verificação: 67 testes, fixture real imutável e idempotente, cinco contornos da V330 em cada comportamento e capturas do portal publicado. Comprimentos totais preservados: 527 cm Para e 606 cm Passa. Seis DXFs N3 regenerados em validação isolada, sem falhas de geração. Isso não certifica os perfis de laje: permanece a revisão da estação local de 124 cm no encontro V301. Evidências em `scripts/arete/relatorios/20261004_lv_inverted_crossings/RELATORIO.md`.

### V330: limite medido de mudança de altura (04/10/2026)

A linha transversal estrutural que fecha as duas paredes tem prioridade sobre o ponto médio estimado entre textos de dimensões. Estados N1 antigos podem conservar a estimativa: reconciliar somente a geometria derivada antes de construir o inventário de seções. Exigir linha única, ortogonal e de largura integral, lados adjacentes da mesma viga com profundidades diferentes e suporte de seção. Preservar geometria validada, edições manuais e aberturas de pilares; não escolher entre marcas ambíguas.

Na V330, LINE 445 do DXF, camada 3, mede Y=3095,038 cm. O limite legado era Y=3035,163 cm. A faixa 71 fica com 112 cm de comprimento; a quantidade continua 3A/2B em Para e Passa, mantendo degrau e comprimentos totais. A correção precede o inventário compartilhado com os contratos N3. Evidências: `scripts/arete/relatorios/20261004_lv_inverted_crossings/boundary_verified.json` e capturas `portal_limite_v330_para.png`/`portal_limite_v330_passa.png`. Originais N1 e Fase4 preservados.


### LV: chegada à face B e regeneração SA (04/10/2026)

Uma chegada sem colisão vertical à invertida deve alcançar a face distante medida. Pilar que ocupa a faixa entre faces e termina exatamente na face de destino não impede essa chegada; qualquer extensão do sólido além da face bloqueia a proposta. Aplicar com simetria de eixo/sentido e conservar pilares reais fora desse caso, mudança de altura e degraus. V301 A16/B1: 247,52 → 266,52 cm em Para e Passa, destino X=4552,4. V330 continua 3A/2B; transição Y=3095,038, faixa 71 de 112 cm.

Após publicação válida de um snapshot SA, limpar marcas de remoção apenas dos segmentos efetivamente regenerados, restritos ao pavimento, seção e vigas solicitadas. Preservar edições, criações manuais, itens ausentes do snapshot e outras classes. VF301 desaparecia por marcas persistentes UID/beam:VF301; a nova rodada recuperou 9 laterais A e 2 B Para. Regeneração falha não limpa essas marcas.

Os botões granulares mostram a última conclusão SA/N3/N5 da classe, obra e pavimento, no horário de Brasília. Excluir falhas, jobs sem pavimento/data válida e geração de item isolado. Não confundir a data SA com geração N3. Evidências: scripts/arete/relatorios/20261004_lv_regeneration/RELATORIO.md; 96 testes Python e verificação JavaScript.

### VF301: continuidade lógica e datum pareado (05/10/2026)

Em travessia de invertida já comprovada nos dois sentidos por paredes medidas e painéis verticalmente separados, uma diferença de nível escalar derivado das lajes não deve impedir sozinha a união. Exigir mesma dimensão, profundidade e sobrecota, datum único concordante nos perfis pareados de uma das faces e ausência de suporte de degrau. Nível explícito, datum divergente/desconhecido, degrau, validação manual e colisão real continuam impedindo a união. Conservar os níveis locais e UIDs de origem em `source_level_sections` e `merged_source_segments`; não reescrever N1 nem tratar a união como confirmação dos níveis estimados.

VF301: A8+A9 → A8 (405,5 cm) e B1+B2 → B1 (3490 cm), Para e Passa. Aberturas de pilares preservadas. Comparação da produção alterou somente esses quatro segmentos; V330 3A/2B e V301 preservadas. 51 testes de cruzamentos passaram. Evidência: scripts/arete/relatorios/20261004_lv_regeneration/vf301_united.json.


### Fechamento de cortes e invertidas (05/10/2026)

Consolidação das regras finais, evidências e pendências: `docs/CONHECIMENTO/CONSOLIDACAO-CORTES-INVERTIDAS-20261005.md`. Compressão tem orçamento de 50 cm, mantendo região das lajes, medidas físicas e fonte original; sinal distinto da inversão. Cobertura SA por segmento de fundo inclui repetições e dispensa interpretado quando o original cobre o trecho. A rodada final confirmou continuidade VF301, mas não regenerou N3 publicado: revisão independente do perfil de 124 cm e certificação por unidade permanecem abertas.

### Experimentos de design NOVA AB: pontas e passagem de pilar (05/10/2026)

**Revisão posterior do dono:** as duas generalizações seguintes sobre ausência de montantes nos gradeados e interrupção da travessa superior foram corrigidas; seguir a seção "Montagens AB NOVA distintas" abaixo. Preservadas aqui como histórico do experimento v08.

Decisão explícita do dono `LV-NOVA-AB-EXTREMIDADES-PILAR-20261005`, aplicável ao desenho AB de Laterais Para e Passa: sarrafos verticais das extremidades somente nas duas pontas da lateral. Divisões de painéis e emendas entre segmentos contínuos não criam esses sarrafos. As linhas de divisão dos próprios painéis permanecem distintas da madeira. Fechamentos locais de recortes são outra função, não novos sarrafos de extremidade.

A passagem geral de pilar recorta todos os sarrafos até o topo da montagem lateral, inclusive a travessa superior, sem retirar o painel. O original analisado na v07, com passagem parcial e travessa superior contínua, é caso especial segundo o dono; não generalizar essa exceção. Aberturas de viga conservam a hachura contínua da v07, conectada à faixa de laje e a segmentos adjacentes.

Exemplos gradeados sintéticos v08 e verificações geométricas em `scripts/arete/relatorios/20261004_nova_lv_design_experimentos/dual_v08/`. São propostas para revisão visual; não comprovam integração ao N3/N5 nem geração publicada. Motores certificados, N1, resultados da VPS e exemplos originais permanecem preservados nesta etapa.

### Experimentos NOVA: parafusos centrais do corte gradeado (05/10/2026)

Decisão `LV-NOVA-CORTE-PONTAS-CENTRAIS-20261005`: remover os sarrafos extras acima/abaixo das pontas metálicas dos parafusos centrais. Não aplicar essa remoção aos sarrafos do conjunto inferior, aprovado pelo dono. Na proposta v09, A/B ficam centralizadas na largura da lateral, num trecho livre de eixos e encontros. Os cinco DXFs sintéticos e PNGs estão em `scripts/arete/relatorios/20261004_nova_lv_design_experimentos/dual_v09/`; comparação por entidade confirma preservação de todas as demais entidades da v07, incluindo o conjunto inferior. Experimento para revisão, sem integração ao motor nem publicação na VPS.

### Montagens AB NOVA distintas — correção vigente (05/10/2026)

**Complemento ao corte sarrafeado:** não existem os pares de madeira acima/abaixo dos antigos parafusos centrais, em nenhuma altura. A v12 removeu as ferragens mas deixou indevidamente a madeira associada; v13 retira essas peças e suas hachuras em todos os cinco casos, incluindo 65×130. Sarrafos regulares, garfos verdes, fundo, cotas e letras preservados por comparação de entidades. Evidência: `scripts/arete/relatorios/20261004_nova_lv_design_experimentos/dual_v13/`. Sem integração/publicação nesta etapa.

**Corte sarrafeado:** decisão vigente `LV-NOVA-CORTE-SARRAFEADO-GARFOS-20261005`. Sem parafusos, inclusive no fundo; sustentação pelos garfos verdes externos. Design aprovado com retirada dessas ferragens, alinhamento A/B e C 1 cm acima, executados nos cinco experimentos v12. Garfos e demais geometria preservados por comparação de entidades. Integração no motor e validação publicada permanecem etapas não executadas.

**Aprovação posterior, somente corte gradeado:** decisão `LV-NOVA-CORTE-GRADEADO-APROVADO-20261005`. Experimento v09 aprovado com letra C 1 cm acima, aplicado nos cinco DXFs v11. Não implica aprovação dos AB ou corte sarrafeado, nem comprova integração ao motor/VPS.

Decisão `LV-NOVA-AB-MONTAGEM-DISTINTA-20261005`: nos sarrafeados, vertical 7 cm apenas nas pontas. Nos gradeados, meio pontalete 3,5 cm verde nas emendas: no original cada painel contribui com uma metade adjacente. Nas pontas, primeira borda do meio pontalete a 15 cm do limite da lateral (medida original 8241,266004 − 8226,266004). Sarrafos 7 cm e linha 2,2 superior são laranja 40; meio pontalete verde 81.

A passagem de pilar mantém a travessa superior de 7 cm nos dois tipos e tem meios pontaletes nas bordas externas da passagem, fechando o interior. A abertura de viga gradeada tem vertical 3,5 até o fundo e travessa 2,2 laranja sob a abertura. A ponta abaixo da abertura usa vertical 7 laranja se é ponta final, ou 3,5 verde se segue outro segmento. Não confundir essas funções e dimensões.

Doze DXFs experimentais e PNGs em `scripts/arete/relatorios/20261004_nova_lv_design_experimentos/dual_v10/`. Cortes v09 preservados. São propostas de encaixe para revisão, sem integração ao motor/VPS. Esta regra substitui as generalizações v08; indexação global derivada ainda não refeita nesta rodada.

### LV-NOVA-AB-PILAR-E-EXTREMIDADES-20261005
Correção vigente do dono: nos AB sarrafeados, abertura de pilar não recebe montantes verdes de 3,5 cm; somente fechar as paredes dos sarrafos horizontais interrompidos pela abertura. Nos gradeados, os meios pontaletes externos à abertura sobem até 2,2 cm abaixo do topo, encostando no sarrafo superior de 2,2 cm. Em ambos os tipos, a borda interior laranja do sarrafo vertical de 7 cm nas extremidades deve ser uma linha reta contínua do fundo ao topo (limitada pelo vazio quando há abertura de viga na própria ponta). Travessa superior da abertura de pilar preservada. Experimentos dual_v14: 12 DXFs sintéticos com auditoria sem erros; renders lidos. Ainda não integrado ao motor nem publicado. Esta decisão substitui a regra v10 que incluía meios pontaletes nas aberturas de pilar sarrafeadas e limitava os dos gradeados a 7 cm abaixo do topo.

### LV-NOVA-AB-TRAVESSAS-E-ABERTURAS-20261005
Correção vigente: sarrafo de 2,2 cm somente no topo dos AB gradeados, terminando nos montantes de 7 cm das extremidades; não atravessar esses montantes até a parede externa. Não existe essa travessa de 2,2 cm no topo dos sarrafeados nem no fundo dos gradeados. Travessas locais de aberturas gradeadas aprovadas permanecem. Em abertura de viga sarrafeada, jambas e travessa inferior têm 7 cm; ambas paredes da jamba são completas, descendo 7 cm abaixo da abertura com fechamento inferior; a travessa inferior nasce desse encontro. Experimentos dual_v15: 12 DXFs sintéticos auditados; dimensões, hachuras, painéis, textos e meios pontaletes gradeados preservados por comparação de entidades. Renders examinados; integração ao motor e VPS pendente. Substitui as regras anteriores de travessa 2,2 no topo sarrafeado e fundo gradeado.


### Cortes locais por perfil e datum medido — revisão 05/10/2026

Cobrir cada perfil físico de cada fundo, incluindo altura diferente e degrau, mesmo quando outro original já cobre um perfil do fundo. Desenhar localmente sem setinhas, comprimir somente cauda e conservar cotas físicas. Confiança: azul claro confirmado, laranja revisar, vermelho invertida. Em viga normal, topo medido da viga e nível regional da laje são referências distintas; referência original única pode ancorar o datum sem alterar N1. Ausência ou conflito de evidência não autoriza assumir datum de viga vizinha. Regras, casos e limites: `docs/CONHECIMENTO/CONSOLIDACAO-CORTES-INVERTIDAS-20261005.md`, seção Revisão final dos destaques.

### LV-NOVA-AB-CONTAGEM-PONTALETES-20261005
Texto de pontaletes somente em painéis AB gradeados: quantidade = arredondamento ao inteiro mais próximo de (comprimento do painel menos extensão das aberturas dentro desse painel) / 30. Exemplos do dono: 244 cm → 8 pontaletes; 122 → 4; 145 → 5; painel 244 com abertura 40 → comprimento útil 204 → 7. Descontar a interseção de cada abertura com o painel respectivo, unindo intervalos sobrepostos para evitar desconto duplicado. Não usar texto fixo 8 1/2pont. Texto individual por painel; sem indicação nos sarrafeados. Experimentos dual_v16: 12 DXFs auditados e demais entidades preservadas; integração ao motor/VPS pendente. Convenção para empate exato .5 adotada no experimento: arredondar para cima.

### LV-NOVA-AB-MEIO-PONTALETE-ABERTURA-20261005
Na parede da abertura AB gradeada, o meio pontalete verde de 3,5 cm começa abaixo do sarrafo superior de 2,2 cm e segue para baixo; seu fechamento superior encosta na face inferior desse sarrafo, sem atravessar a travessa. Corrigidos apenas endpoints/fechamentos das jambas gradeadas em dual_v17; demais entidades e textos de contagem v16 preservados. Doze DXFs experimentais auditados, render das aberturas lido; integração ao motor/VPS pendente.

### LV-NOVA-AB-INTERSECCOES-SOB-ABERTURA-20261005
A regra de não atravessar sarrafo de 2,2 cm também vale para meios pontaletes sob a abertura gradeada, inclusive nas interseções/emendas de painéis e segmentos. A ponta e seu fechamento superior devem encostar na face inferior da travessa local de 2,2 cm. Experimento dual_v18: linhas verdes desses encontros corrigidas; outras entidades preservadas e 12 DXFs auditados. Render examinado; motor/VPS pendentes.

### LV-NOVA-AB-PAINEL-MINIMO-60-20261005
Decisão do dono para ambos os AB: lateral até 244 cm sempre usa um painel único, podendo ter menos de 60 cm. Nas laterais acima de 244 cm, não admitir painel inferior a 60 cm. Quando a sobra após a divisão em 244 for menor que 60, substituir o painel anterior de 244 por 122 e somar os outros 122 à sobra no painel final. Ex.: 260 → 122+138; 300 → 122+178; 500 → 244+122+134. Sobra exata de 60 permanece: 304 → 244+60. Recalcular paredes, cotas, meios pontaletes das emendas e textos de contagem conforme comprimento útil de cada painel. Experimentos dual_v19: 12 DXFs auditados, cotas confrontadas com a divisão calculada. Fórmula verificada em 30000 comprimentos de 0,1 a 3000 cm: soma preservada, máximo 244, mínimo 60 exceto painel único. Não integrado ao motor/VPS.

### LV-NOVA-AB-CONTINUACAO-APOS-ABERTURA-20261005
Somente nos sarrafeados: quando a abertura direita chega ao fim de um segmento e há segmento seguinte encostado, esse seguinte recebe sarrafo vertical de 7 cm à esquerda, de fundo a topo. Seus horizontais começam na face interna desse montante. É exceção à ausência de montante em emenda comum sarrafeada; não aplicar às emendas sem abertura nem aos gradeados. Experimento dual_v20: AB04 corrigido, demais 11 DXFs preservados byte a byte em relação a v19; entidades fora das linhas afetadas preservadas, 12 auditorias sem erro e render examinado. Integração ao motor/VPS pendente.

### LV-NOVA-DESIGN-APROVADO-INTEGRACAO-20261005
O dono aprovou explicitamente todo o design experimental das laterais de viga NOVA, AB e Visão Corte, gradeadas e sarrafeadas, compartilhado visualmente por Para/Passa com configurações independentes. Referência final AB: dual_v20, seis casos por montagem. Corte gradeado: dual_v11, cinco casos. Corte sarrafeado: dual_v13, cinco casos. Todas as correções posteriores substituem as convenções anteriores no mesmo ponto; em especial a ausência de montante em emendas sarrafeadas admite a exceção da continuação após abertura. A aprovação autoriza integrar o padrão ao N3 dinâmico de origem SA e validar o N5 com molduras/índice NOVA. Não comprova que a integração foi realizada. Plano completo e critérios: docs/PLANO-LV-NOVA-SA-N3-N5-20261005.md. Consolidação integral da especificação, atualização dos índices KB/RAG e validação publicada permanecem próximas etapas do plano.


## Apresentação N3/N5 por modo — 07/10/2026

INI, NOVA e Formascia têm padrões de desenho distintos sobre o mesmo contrato estrutural. Consultar a [matriz canônica de desenho](../../PADROES-DESENHO-N3-N5.md) e o [padrão INI aprovado](../../PADRAO-INI-APROVADO.md). A aprovação visual não altera os dados SA nem certifica automaticamente todos os itens. LAJ INI compartilha o N3/perfil NOVA; os compositores N5 continuam separados.


### LV-VISAO-CORTE-NAO-SECCIONA-20261008

Visão de corte é anotação: seus traços transversais, diagonais, polilinhas e setas não delimitam banda nem seccionam lateral. Reconhecer a camada fonte antes de converter entidades em coordenadas sem semântica; excluir somente a entidade reconhecida, preservando linhas estruturais independentes mesmo quando coincidentes. Aplicar o mesmo filtro à leitura DXF de divisores usada pelo portal. Não mascarar uma região inteira em torno do símbolo: isso apagaria encontros reais de vigas/pilares.

Causa comprovada na Obra_TREINO_1/TIPO_TESTE: múltiplos divisores gráficos da visão de corte tornavam ambígua a busca e mantinham uma fronteira antiga. V501 tinha trecho falso de aproximadamente 102,44 cm. Depois do filtro, A Para/Passa passou de quatro para três segmentos; o encontro real com V523 foi preservado. Coordenadas observadas são evidência, nunca constantes do motor. Implementação: lv_beam_scene._line_segments/build_scene_runs e fv_inverted_crossings.structural_lines_from_dxf, com reconhecedor compartilhado cad_object_recognition.section_layer. Proveniência registra entidades_visao_corte_excluidas.

Contraprovas: divisor estrutural coincidente permanece; mudança real de altura permanece; polilinha fechada de corte não produz banda; orientações horizontal/vertical e translações têm regressão. Testes: test_lv_section_symbol_exclusion.py. Fonte torre_1.dxf SHA256 80b45ff3e024ebe037fe6e6e52829216120f006c55f6b60f79adb1df2dc65641. SA publicado em produção, recibo e comparação no relatório 20261008_lv_corte_seccionamento. Esta validação de interpretação não certifica N3/N5 nem estilos ainda não observados.


## Passa: encontro depois de percorrer a parede do pilar

<!-- LV-PASSA-ENCONTRO-APOS-PILAR-20261008 -->
A lateral Passa percorre a parede externa do pilar, mas termina na primeira face de uma viga de profundidade igual ou maior, mesmo quando o encontro fica além do trecho original ou da margem normal de busca. A busca de incidentes deve cobrir a parede conectada completa. Não reaparece um fragmento da parede depois desse bloqueio. Viga menos profunda mantém a regra de passagem por baixo; visão de corte continua sendo anotação sem bloqueio estrutural. Evidência: TIPO_TESTE, V526 SEG1-A contra V501, ambas 19/50; término corrigido de y=3729,8 para y=3710,8. Regra geral, sem exceção por nome.

## Transição de laje ou degrau para vazio

O inventário compartilhado também recupera um vão sem repetição do nome além
de apoio: exige paredes reais, seção local e um único trecho identificado
adjacente com a mesma seção. Não atribuir por proximidade nem atravessar o apoio
como material de viga. Caso V517 acima de P16: FV e as células A/B Para/Passa
recuperadas; recibo `scripts/arete/relatorios/20261008_fv_missing_crossings/RELATORIO-V517.md`.

<!-- LV-LAJE-DEGRAU-VAZIO-20261008 -->
A lateral secciona na borda física entre laje/degrau e vazio, tanto Para quanto Passa, com segmentos encostados e numeração na ordem de leitura do lado. Usar a união dos intervalos de contato das lajes com a face: contatos sobrepostos ou adjacentes não representam vazio. Degrau interno sem contato com a face não divide a lateral. Limites truncados pela extensão da cena não provam uma borda física no prolongamento Passa sobre pilar. Não alterar a referência de nível da viga apenas por esta divisão. Exemplo apontado pelo dono: V519 SEG4-B, TIPO_TESTE, trecho de vazio seguido por degrau/laje.


## Parede externa completa nos cantos ortogonais

<!-- LV-CANTO-EXTERNO-20261008 -->
Nos encontros em L, as laterais externas completam a parede ate o canto externo; nao terminam na face interna da viga perpendicular. Aplica-se a Para e Passa. Medir a largura da perpendicular e exigir linha estrutural continua ate o canto, com a perpendicular terminando na face interna da propria viga. T, cruzamentos e linhas de cota nao autorizam prolongamento. Faces internas continuam obedecendo ao encontro e a profundidade G7. Nao copiar o fundo como lei nem usar coordenadas fixas por obra. Evidencia: encontro V516/V526, TIPO_TESTE, apontamento do dono em 2026-10-08.


## VC-TEXT-COTAS-20261008 — apresentação dos cortes originais

O título acompanha o eixo de largura do corpo do corte e fica fora do contorno completo, incluindo braços de laje. Cada face do corpo recebe cotas dos intervalos livres entre os contatos de lajes, acima e abaixo deles. Medir contatos somente nas peças fonte atribuídas àquele corte; manter as medidas completas das peças compartilhadas e a geometria DXF intacta. Medidas geométricas não certificam nível absoluto. Regressão: cortes verticais e girados, 50/58 cm de paredes em corpo 120 com laje de 12; braço separado por lacuna não cria contato.


### VC-COTAS-UTEIS-20261008 — Cotas úteis da visão de cortes

Correção do dono: não cotar a extensão do símbolo de laje para dentro do vão. As cotas úteis são a espessura/altura de cada laje, as alturas das paredes da viga acima e abaixo dos contatos e a largura do fundo da viga (com altura total do corpo como referência). O comprimento dos braços permanece somente na geometria fonte, inclusive pontes compartilhadas; não é medida de forma. Aplicar também a cortes rotacionados e degraus. Esta regra corrige a orientação anterior sobre cotar extensões de peças compartilhadas. Validação: 42 testes; 55 cortes reais com contornos preservados e 80 cotas de parede mantidas.


### VC-COTAS-PROXIMAS-20261008 — Posição das cotas de parede

Preferência do dono: colocar cada cota próxima da parede que mede, sem deslocá-la além da extensão dos braços de laje. O afastamento usa a face física da viga com margem de 8 unidades do desenho, acompanhando a orientação do corte. Valores, contornos e espessuras permanecem iguais. Conferência de 55 cortes e 80 cotas de parede, com 42 testes aprovados.


### VC-TOTAL-EXTERNA-20261008 — Cota total em linha externa

Preferência do dono: a cota total deve ficar 4 cm mais para fora da linha de cotas da laje/granulares para evitar leitura ambígua. Margem total 12 cm versus margem granular 8 cm; aplicar conforme a orientação do corpo do corte, sem alterar valores. Cotas de parede continuam próximas da face medida.


### Esquina de pilar: incidência do Passa (2026-10-08)
Ao medir uma viga incidente, excluir sua continuação geométrica interna aos pilares sólidos de origem. Uma faixa ainda não aparada não pode impedir o Passa sobre a face externa do pilar. A medição deve independer da ordem de montagem das cenas; encontros reais fora do sólido continuam respeitando a profundidade. Tolerância geométrica de 0,05 cm absorve o arredondamento da faixa, sem estender paredes.

## ESTILO-INTEGRADO-20261008 — harmonização entre classes

Síntese vigente, convenções recorrentes, contraprovas e pendências: [Estilos estruturais — interpretação integrada](../../CONHECIMENTO/ESTILOS-ESTRUTURAIS-INTERPRETACAO-INTEGRADA.md). Consultar a evidência local antes de aplicar a regra a outra obra; cooperação entre classes não constitui prova circular nem aprovação automática.

Pendência documentada em 20261008_lv_laje_vazio/RELATORIO.md: a fronteira V519 foi validada, porém a associação LAJ/vazio dos dois trechos diverge do comentário humano. Não promover essa associação a verdade validada.

## LV-AJUSTES-PONTAS-20261008 — ajustes de ponta e tags de revisão SA

Escopo: destaques A/B de laterais Para e Passa. Decisões humanas deste chat, implementação e evidência datada em `scripts/arete/relatorios/20261008_lv_endpoint_tags/RELATORIO.md`; curadoria em `scripts/arete/relatorios/20261008_chat_kb_endpoint_harmonia/RELATORIO.md`. Esta informação explica a revisão da interpretação, sem certificar o ajuste de cada item ou novos estilos de obra.

### Origem, sentido e sinal dos valores

Cada segmento expõe dois ajustes em cm: `lv_cell.adjustment_start` e `lv_cell.adjustment_end`, publicados no viewer como `ajustes_pontas`. Ponta esquerda corresponde ao primeiro ponto local (início), direita ao último (fim). Não confundir com lado A/B nem com esquerda/direita absoluta da tela: um segmento B pode ter orientação invertida. As tags não deslocam a geometria.

Mostrar `Ajuste (-11 cm)`, `Ajuste (-4 cm)`, `Ajuste (+4 cm)` ou `Ajuste (+11 cm)` conforme o valor registrado: negativo subtrai, positivo soma. Zero explícito é `Ajuste (0 cm)`, neutro. Ausente, booleano, NaN ou infinito são inválidos: `Ajuste (não informado)`, nunca zero presumido. Os valores exemplificam a apresentação; não constituem tabela universal de descontos independente do encontro e da montagem.

SA e N3 são etapas distintas. As tags leem o SA; o recuo Passa de -4 calculado posteriormente por `lv_generation_contract._passa_endpoint_adjustments` não é copiado silenciosamente para elas. +4/+11 em regras de aberturas não provam ajuste externo de ponta. No retrato de 08/10: Para tinha 155 segmentos/310 tags (113 ajustes -11, 197 zeros); Passa 157/314 tags com zero. Esses números são evidência datada de exibição, não aprovação de que os zeros estejam corretos. Revisar o contrato SA quando o encontro físico exigir ajuste.

### Disposição vigente das tags

Texto compacto apenas `Ajuste (valor cm)`, sem escrever esquerda/direita; tooltip e metadados preservam a identificação. Mesma cor e estilo do nome, fonte 3,25 e opacidade 0,85, obedecendo ao checkbox nomes e pan/zoom por viewBox.

Posicionar o nome primeiro. Em segmentos com espaço, cada ajuste fica alinhado ao nome na orientação local do texto, a meia distância longitudinal entre nome e respectiva ponta. Linha-guia diagonal conecta a tag à extremidade exata; não associar à ponta do segmento vizinho.

Quando a disposição alinhada sobrepõe o próprio nome por falta de espaço, empilhar ambos: ajuste esquerdo acima do nome; ajuste direito acima do esquerdo. Acima segue a orientação do texto (em vertical rotacionado, não é necessariamente para cima na tela). Busca conjunta preserva a ordem e evita sobreposição interna, considerando obstáculos para a posição do par. Obstáculos de outros segmentos não acionam empilhamento indiscriminado. A regra substitui a disposição inicial de tags perto das pontas e o alinhamento obrigatório em segmentos curtos. Não garante ausência de qualquer colisão em toda cena densa.

Validação da implementação: 23 testes Python local/VPS (quatro classes, sinais, desconhecido, ordem B e geometria preservada), verificação Node com longos/curtos horizontais/verticais/invertidos e capturas reais Para/Passa em `20261008_lv_endpoint_tags/`. Não implica validação completa de interpretação ou geração.
