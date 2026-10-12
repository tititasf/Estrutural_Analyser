# Padrão NOVA — Laterais de viga aprovado

**Status:** canônico, design aprovado em 05/10/2026 e encaixe N5 aprovado em 06/10/2026. **Escopo:** LV Para e Passa; AB e Visão Corte; gradeadas e sarrafeadas. **Execução:** N3 e quatro N5 gerados pelo fluxo normal na VPS em 06/10/2026 e disponíveis em Unificados. Auditoria técnica completa dos inventários e DXFs; inspeção visual dos casos V301/V304 e aprovação humana do desenho e do encaixe N5. A validação operacional de uma rodada completa de produção continua distinta da aprovação do padrão.

Esta especificação consolida as decisões finais do dono. Para o design NOVA/LV, substitui as orientações experimentais anteriores que contradigam as regras abaixo. Para/Passa compartilham o padrão visual, mantendo contratos e configurações independentes. N4 e referências humanas explicam o desenho; não fornecem dimensões ausentes no SA.

## Referências aprovadas

Raiz: `scripts/arete/relatorios/20261004_nova_lv_design_experimentos/`.

| Desenho | Fonte final | Casos |
|---|---|---|
| AB gradeado e sarrafeado | `dual_v20/{gradeadas,sarrafeadas}/AB01..06.dxf` | Longo 640; abertura esquerda; direita; direita seguida de segmento; abertura de pilar; dois segmentos comuns |
| Corte gradeado | `dual_v11/gradeadas/VC01..05.dxf` | Dimensões variadas, desníveis, duas lajes, lado sem laje, invertida |
| Corte sarrafeado | `dual_v13/sarrafeadas/VC01..05.dxf` | Mesma matriz de perfis |

Manter os DXFs e renders anteriores para comparação. Aprovação visual não equivale a implementação ou publicação. O manifesto derivado registra SHA-256 e inventário dos arquivos, sem alterar as referências.

## Contratos e origem

- Toda dimensão estrutural vem do SA local: comprimento, largura, altura, lajes, desníveis, aberturas e continuidade. Não substituir perfil local por máximo global nem emparelhar A/B somente pelo índice.
- Produzir e conservar ambas as montagens; a opção do painel seleciona resultado/saída, sem apagar a outra. Isolar edições e caches por montagem, modo e Para/Passa.
- Não alterar schema N1 nem JSON original Fase-4. Falta ou ambiguidade essencial produz pendência rastreável.
- Aberturas nunca ultrapassam o domínio do painel. Interseções com painéis e sobreposição de aberturas são calculadas, descontadas uma única vez.

## AB — regras comuns

| Regra | Valor e comportamento aprovado |
|---|---|
| Divisão | Até 244 cm: painel único, inclusive menor que 60. Acima de 244: máximo 244 e mínimo 60; sobra menor que 60 transforma o painel anterior em 122 e o seguinte em 122 + sobra. 260 → 122+138; 300 → 122+178; 304 → 244+60; 500 → 244+122+134. Soma preservada. |
| Extremidades | Montante laranja de 7 cm somente nas pontas externas, contínuo de fundo a topo. Horizontais começam na face interna desses montantes. |
| Vazio | Abertura de viga conectada à faixa de laje forma um único vazio com o mesmo hatch. Vazios contíguos entre segmentos permanecem unidos. |
| Abertura de pilar | Interrompe os horizontais e fecha suas paredes; conserva o sarrafo superior de 7 cm em ambas as montagens. Não confundir com abertura de viga. |
| Estilo | Hachuras, estilos DIMENSION, cores e patinhas vêm das definições aprovadas; não substituir por hatch genérico. Entidades CAD reais e editáveis. |

## AB sarrafeado

- Sarrafos horizontais de 7 cm; sem travessa global de 2,2 cm no topo ou fundo.
- Emendas comuns entre painéis/segmentos não recebem montante vertical.
- Exceção: depois de segmento cuja abertura direita chega ao fim, a continuação encostada recebe montante esquerdo de 7 cm. Seus horizontais começam na face interna desse montante.
- Abertura de viga: jamba e fechamento inferior de 7 cm, linhas completas. A jamba avança 7 cm abaixo do vazio; o sarrafo inferior nasce desse encontro. Fechar as pontas dos horizontais cortados.
- Abertura de pilar não recebe meios pontaletes verticais de 3,5 cm.
- Não desenhar texto de quantidade de pontaletes.

## AB gradeado

- Madeira de 7 cm e travessa de 2,2 cm: laranja, layer `SARR_2.2x7`, ACI 40. Meio pontalete de 3,5 cm: verde, layer `SARR_3.5x7`, ACI 81.
- Travessa global de 2,2 cm somente no topo; termina nos montantes externos de 7 cm, sem atravessá-los. Não há equivalente global no fundo.
- Emendas recebem meios pontaletes de 3,5 cm de cada lado. Meios pontaletes das pontas externas posicionam-se a 15 cm da extremidade, conforme referência aprovada.
- Abertura de pilar recebe meio pontalete de 3,5 cm em cada parede externa do vazio. Encostam por baixo da travessa superior de 2,2 cm, sem atravessá-la.
- Abertura de viga: jamba vertical verde de 3,5 cm até o fundo; fechamento inferior laranja de 2,2 cm. Nas interseções abaixo do vazio, meios pontaletes param na face inferior desse fechamento. No fim externo usa-se montante de 7 cm; havendo continuação, meio pontalete de 3,5 cm.
- Quantidade individual por painel = inteiro mais próximo de `(comprimento - união das extensões de aberturas) / 30`; empate .5 para cima. 244 → 8; 122 → 4; 145 → 5; 244 menos abertura de 40 → 7. Texto no espaço livre do painel, com singular/plural correto.

## Visão Corte

- Representar todas as lajes locais de cada lado, seus rebaixos e compensados; não limitar à primeira laje. Invertida possui montagem específica de topo.
- Cotas alinhadas em colunas externas à esquerda e direita. Patinhas permanecem nas faces dos elementos cotados, conforme aprovação; não deslocá-las ao alinhar os textos/linhas.
- Nome do corte com guia cinza pontilhada; dimensões locais indicadas. Letras A/B no espaço livre de seus componentes; letra C elevada 1 cm em relação à posição anterior aprovada.
- Painéis, sarrafos e grades usam as hachuras reais aprovadas, proporções físicas e encontros sem sobreposição.
- Gradeado: ferragens centrais com pontas de parafuso, sem os sarrafos espúrios acima/abaixo dessas pontas. Madeira e ferragem inferiores preservadas; extensão metálica do fundo completa de um lado ao outro. Letras não colidem com ferragens.
- Sarrafeado: garfos externos verdes preservados; não há parafuso central nem inferior. Não conservar madeiras associadas ao conjunto de parafusos, mesmo aumentando a altura.

## Integração, N5 e conhecimento

### Matriz de rastreabilidade da integração

Todas as regras desta matriz valem somente para NOVA/LV, nas duas montagens e nos contratos independentes Para/Passa. A aprovação visual é a fonte de design; aprovação não substitui validação da execução publicada.

| Regra aprovada | Implementação atual | Verificação reproduzível |
|---|---|---|
| Divisão 244/122, mínimo 60 somente em laterais maiores que 244; soma preservada | `lv_nova_design.panel_spans`, `lv_generation_contract.distribute_lv_panels` | `tests/test_lv_nova_approved_rules.py`, referências AB aprovadas |
| Sarrafeado: montantes externos 7; emenda comum sem montante; continuação após abertura com montante | `lv_nova_design.draw_ab` | AB04/AB05 no manifesto aprovado; comparação integral do renderer |
| Gradeado: 3,5 nas emendas/aberturas, 2,2 somente topo; encontros sem atravessamento | `lv_nova_design.draw_ab` | AB01..06 gradeadas no manifesto aprovado |
| Vazio conectado de abertura/laje, desconto único de abertura na contagem de pontaletes | `lv_nova_design.draw_ab`, `pontalete_count` | fixtures de aberturas e contagem em `tests/test_lv_nova_approved_rules.py` |
| Abertura de pilar preserva folga SA, eixo original, recorte de peça e ajuste inicial | `lv_nova_sa_adapter.ab_runs` | `tests/test_lv_nova_sa_adapter.py`: allowance, partition, start trim; origem SA imutável |
| Corte gradeado com ferragens aprovadas; sarrafeado sem parafusos ou travessas espúrias | `lv_nova_design.draw_cut` | cinco cortes por montagem no manifesto aprovado |
| Perfis locais e dimensões fracionadas, sem substituir por máximos globais | `prepare_lv_sources`, `build_cut_contract`, `lv_nova_design` | testes de múltiplas lajes, perfis locais, textos 305,5/61,5 |
| N3 separados com unidades CAD e hashes por montagem/comportamento | `generate_ab`, `generate_local_sections` | `tests/test_lv_nova_sa_adapter.py`, manifesto `.units/manifest.json` |
| N5 sem omissão, mistura de variantes ou retorno a N3 antigo | `n5_lateral_frames.published_manifests/read_units` | `tests/test_n5_lateral_frames.py`: pendente, SHA, variante, completude |
| N5 com linhas e entidades editáveis, escala declarada e índice cadastrado | `n5_lateral_frames.assemble_lateral_frames`, `SheetBuilder` | testes de preservação geométrica; fixture de índice não certifica cadastro LV |
| Job N5 só conclui com quatro saídas Para/Passa × gradeadas/sarrafeadas | `pipeline_runner.executar_n5` | `portal/tests/test_n5_lateral_variants.py` |

Situação em 2026-10-06: N3 normal e quatro saídas N5 concluídos na VPS. Índice próprio LV cadastrado; inventário das 36 vigas por variante, cobertura nativa e auditoria DXF completos; quatro previews/downloads disponíveis no portal. Evidências em `scripts/arete/relatorios/20261006_lv_nova_integracao/n5_pagination/`. Inspeção visual realizada por amostragem; aprovação humana dos N5 e certificação visual individual de todas as unidades permanecem distintas da auditoria técnica.

O renderer NOVA deve ser geral e determinístico, calculado do contrato SA. Não executar scripts experimentais de substituição textual em produção. Estilos/blocos podem ser ativos de desenho; geometria particular dos exemplos não pode ser transplantada para os itens.

Fingerprints incluem contrato, configuração, montagem e todas as dependências/versionamento do renderer. N5 consome somente N3 atuais da montagem correspondente, conserva entidades editáveis e valida cobertura por segmento e corte. Molduras, índices, áreas úteis, ordem e paginação seguem cadastro NOVA/LV e o plano de integração, sem assumir que PL/FV equivale a LV.

Fontes de conhecimento recebem vínculo a esta especificação. Reconstruir índice KB e avaliar recuperação das regras; curadoria do RAG ativo deve manter proveniência e distinguir intenção aprovada de execução comprovada. Não atualizar índices legados.

Plano e critérios de entrega: [PLANO-LV-NOVA-SA-N3-N5-20261005.md](PLANO-LV-NOVA-SA-N3-N5-20261005.md).

## Encaixe nativo de conjuntos AB longos no N5

Quando o conjunto excede a área útil, quebrar sua apresentação nas divisões reais
dos painéis calculados pelo N3. A quebra de folha não é extremidade física:
não acrescentar sarrafo de 7 cm, meio pontalete, fechamento de abertura ou painel.
Preservar a escala 1, as posições globais das peças, a distribuição dos painéis,
as quantidades de pontaletes e a continuidade das hachuras. Cada folha recebe
a porção correspondente das linhas/hachuras originais; cotas horizontais que
atravessam a quebra são apresentadas pelas medidas parciais efetivas nessa folha.
Identificar a continuação com `Cont. Vxxx.A/B` quando a quebra ocorre dentro do
mesmo segmento. Manter o N3 original imutável e registrar os intervalos de origem
no manifesto N5 para provar cobertura completa, sem lacunas ou duplicações.

Índice próprio LV cadastrado em NOVA/LV_PARA e NOVA/LV_PASSA. Na publicação N5,
usar somente CAPA e ÍNDICE; omitir as quatro folhas de exemplificação do arquivo
cadastrado (legenda, AB gradeado, AB sarrafeado e montagens de corte). O índice usa as mesmas origens calibradas da moldura NOVA;
conteúdo e hash pertencem às laterais, sem substituir os cadastros PL/FV.
Títulos e paginação do índice são calculados após distribuir as folhas reais.
As quatro combinações Para/Passa × gradeadas/sarrafeadas conservam inventários
e arquivos separados. A execução publicada e a inspeção visual final devem
constar no relatório da rodada; cadastro e testes isolados não certificam entrega.


## Revisão do encaixe N5 — 06/10/2026

A primeira linha recebe o máximo de cortes pendentes da viga que couberem,
em escala 2×, sem aguardar os segmentos correspondentes nem deixar cortes
para folhas posteriores quando houver espaço. Abaixo vêm os segmentos AB
em escala 1×, da esquerda para a direita e de cima para baixo. Quando acabam
os cortes, toda a área útil fica disponível aos segmentos. Ao terminar uma
viga, iniciar a próxima à direita na mesma folha somente se seu primeiro
corte couber no espaço restante, separando as áreas com linha vertical ciano;
caso contrário iniciar nova folha. Revisão do dono em 06/10/2026: cada
design de corte aparece somente uma vez por viga, sem repetição nas
continuações. Nunca unir cortes de vigas diferentes, mesmo quando idênticos:
cada viga mantém seus próprios cortes e associações. Não adicionar cabeçalho automático no topo:
o nome existente nos desenhos N3 identifica o conteúdo. Cortes sem ocorrência
AB devem continuar cobertos pelo inventário e índice, sem descarte silencioso.
Os índices excedentes continuam imediatamente após o índice e deslocam a
numeração das folhas seguintes; molduras continuam em quatro colunas.

A abertura de pilar na lateral exige passagem ao longo da face A/B/E/F/G/H.
Passagem ao longo de C/D não abre o painel. Identificar a face pelo contorno
SA do pilar e eixo medido da lateral, preservando o comportamento Para/Passa
já interpretado. Enriquecer somente a cópia do contrato N3, sem reescrever SA.
A face inferida recebe proveniência `sa_physical_edge_overlap`.

### Alinhamento altimétrico dos segmentos (2026-10-06)
Segmentos contíguos e sucessivos são posicionados pela elevação real da montagem: `section_contract.base_level_m + mounting[side].panel_base_cm/100`. Diferenças de altura não devem deslocar lajes que têm a mesma elevação estrutural. O N3 conserva o deslocamento vertical de cada segmento em centímetros, sem alterar medidas nem SA. O N5 alinha as unidades pela referência de nível da viga em cada linha, incluindo as unidades recortadas para paginação; não alinha pela caixa externa dos textos nem pelo fundo do painel.

### Conjuntos contíguos e aproveitamento N5 (2026-10-06)
Cotas granulares horizontais usam uma altura comum, abaixo da base mais baixa do conjunto, estendendo as chamadas dos painéis mais baixos. Há uma única cota total para todos os segmentos fisicamente encostados, inclusive continuidade por abertura parcial. Obstáculos completos permanecem separados. Nomear apenas o início do conjunto: primeira ocorrência de cada face usa `VIGA.A` ou `VIGA.B`; demais conjuntos e quebras da mesma face usam `Cont. VIGA.A/B`, sem S1/S2 ou SEG. O vazio de laje e abertura parcial é a união geométrica dos vazios contíguos: hachura e contorno sem divisões internas, paredes livres no layer rosinha da hachura (COTA); interface compartilhada com painel conserva o layer Painéis. Unir linhas colineares contínuas. N5 deve tentar preencher o espaço restante da linha em limites físicos de painel antes de abrir outra linha/folha, conservando 1× para AB, 2× para cortes, medidas e membros do N3.


### Refinamento aprovado — 07/10/2026

Primeiro A é VIGA.A e primeiro B é VIGA.B; B não é continuação de A. Cont. somente nas continuações da própria face, também no INI. No corte sarrafeado, incluir o fechamento horizontal de 2,2 cm acima dos verticais A/B; não confundir com uma travessa global de AB. Evidências em `20261007_ini_lv_sarrafeadas/resultado_real_13pav`.
