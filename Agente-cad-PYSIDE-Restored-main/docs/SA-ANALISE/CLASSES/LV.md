# LV — manual granular de interpretação, validação e evolução

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
