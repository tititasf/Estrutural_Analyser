# Pré-processamento — checkpoint de 2026-09-23

**Estado:** fluxo assistido publicado na VPS em 2026-09-23, protegido por flags
independentes para gerar e consumir contexto. Esta nota complementa o status de
22/09; não altera a baseline histórica. O pré-processamento continua universal
por obra/pavimento/torre: não contém regra especial para 13_PAV ou 14_PAV.

## Desktop consultado

`main.py::_run_pavimento_preprocess` extrai a convenção de pilares antes da análise;
`_classify_pillar_hatch` é o consumidor por assinatura geométrica. A aba de níveis
do PySide usa `niveis_extractor.extract_elevacao_tipica`, mas o extrator legado
ignora zero/negativos e não estabelece unidade/datum. `PreProcessAllWorker` grava
nas tabelas estruturais e agrega torres, portanto não foi reutilizado no portal.

## Entrega local desta rodada

- Lote por torre com revisões das fontes, dependências, cortes rotulados ainda
  sem vínculo, níveis desconhecidos explícitos, consolidado de pavimento e
  índice transacional da obra. Detalhes consta como `not_supported`.
- O portal registra progresso por torres concluídas, checa cancelamento antes
  de publicar e mantém o SA inalterado pelo job de pré-processamento.
- Entrada opcional no headless e resolução de contexto antes do subprocesso,
  condicionadas por flags separadas de geração e consumo. O cache N1 é desabilitado
  quando há contexto aceito. O manifesto SA recebe hash/run/revisões e evidência
  das chamadas reais ao classificador. O fluxo sem contexto preserva a entrada
  anterior.
- `NASCE` fica como evidência no pacote, mas não é aplicado automaticamente:
  no A/B do 14_PAV mudou `ignore_in_beams` e 235 caminhos não ligados a IDs
  em vigas (dimensões, vínculos e rótulos). Aplicar o termo assim violaria o
  gate de não regressão. `SEGUE`/`MORRE` permanecem elegíveis quando a legenda
  e a fonte são inequívocas.

## Evidência A/B em cópias do 14_PAV

Fontes copiadas da VPS para diretórios temporários; nenhum dado produtivo foi
processado ou sobrescrito. A legenda real contém `CROSS → NASCE`, `EMPTY → MORRE`,
`DIAG → SEGUE`, sem conflito. O resolver fixou obra/pavimento/torre/projeto/hash
e o headless leu a entrada. A chamada real do desktop retornou o termo da fonte.

- A/A sem contexto: 35 pilares, 23 lajes e 33 vigas nos dois lados;
  diferenças em vigas restritas a IDs temporários gerados novamente.
- A/B com os três termos: 27 classificações mudaram, mas dimensões/vínculos
  de vigas também mudaram. Essa variante foi rejeitada.
- A/B com `NASCE` suspenso: 24 classificações `INDETERMINADO → SEGUE`, 37
  descrições de hachura de laje correspondentes e nenhuma diferença em vigas
  fora de IDs temporários. Geometrias de pilares preservadas.

Arquivos de evidência da cópia:
`%TEMP%/cad-pre-vps14-copy/ab-evidence.json`, `ab-diffs.json`,
`aa-diff-paths.json` e `ab-safe-diff-paths.json`.

## Gates, cobertura e publicação

Os testes focados passaram (67 testes antes do último ajuste de cancelamento,
mais testes específicos do checkpoint). O headless completo read-only na cópia
terminou com exit code 0 em A e B. Em A não há contexto no manifesto; em B há
`status=consumed`, 89 chamadas reais e 32 itens com assinatura e termo
rastreáveis. O baseline desse microciclo não gerou dois previews N3 de P26
mesmo sem contexto (0 gerados/2 ausentes em A e B); portanto N3/N5 ainda não
têm prova A/B completa. Logs da cópia: `%TEMP%/cad-pre-package-4kzyt91m/`
`headless-A.log` e `headless-B.log`, com `arete_manifest.json` em cada rodada.
O extrator desktop `get_pavimento_niveis_abs` retornou `{}` para essa cópia:
não há DXF de convenção de níveis nesse recorte, e o snapshot de P26 tem
`altura`, `nivel_saida` e `nivel_chegada` nulos. Sem altura comprovada, o
construtor N3 recusa corretamente criar o payload. O log agora informa os
campos ausentes por variante. A CLI headless também passa `--db` para o
construtor da janela PySide antes da inicialização, evitando a seleção implícita
do banco principal nesse caminho; a inicialização completa da UI ainda não foi
usada como prova de isolamento de todos os robôs integrados.

Um segundo A/B foi executado em cópia isolada do 13_PAV de Obra_TREINO_1,
com torre, convenção de pilares e convenção de níveis da mesma obra. O extrator
desktop retornou saída 848,98 m, chegada 852,19 m e altura 321 cm. O SA
headless terminou com exit code 0 nos dois braços; A sem contexto e B com
`preprocess_context.status=consumed`, 230 chamadas reais do classificador e 32
itens com evidência. Cada braço gerou
P26 PARA e PASSA (2/2, nenhuma falha). As seis vistas N3 contêm 1.844
entidades ao todo; todas coincidiram entre A/B após ignorar apenas handles e
owners DXF. O N5 PL de P26 montou 1/1 item, sem ausentes, em cada braço; as
entidades da prancha também coincidiram integralmente. Evidências em
`%TEMP%/cad-pre-13-ab-20260923/` (`headless-A.log`, `headless-B.log`, packs
e `n5-A`/`n5-B`). Isto comprova não regressão N3/N5 nesse item; não substitui
o gate da obra de referência 14_PAV, sem convenção de níveis validada.
Uma nova rodada do pré-processador nessa cópia preservou integralmente o
snapshot lógico das 24 tabelas do banco SA e os hashes de 83 arquivos externos
ao armazenamento próprio; somente uma nova revisão interna foi publicada.
O contorno de P26 (7 pontos) no pacote interno coincide coordenada por
coordenada com o estado N1 do SA; sobreposição PNG em
`%TEMP%/cad-pre-13-ab-20260923/p26_geometry_ab.png`.

O vínculo de convenções agora aceita um recorte único do mesmo pavimento em
outro bruto quando a torre não tem convenção local. Duas convenções externas
mantêm a escolha indeterminada. Testes com duas torres que repetem P1 confirmam
pacotes e hashes distintos; o manifesto fixado para uma torre é recusado para
o DXF da outra.

No inventário isolado da mesma cópia, 58 rótulos de laje/viga foram encontrados,
mas nenhum recebeu contorno único inequívoco; 6 nomes são ambíguos. De 84
candidatos de pilar, 12 ligaram geometria e 72 permaneceram pendentes. O SA
headless identificou 35 pilares. Essa cobertura impede declarar a interpretação
interna de torre completa ou usar contagens como evidência de precisão.
Páginas P18–P22 continuam adiadas; cortes e níveis por item ainda têm cobertura
parcial e explícita. O fluxo está funcional para inventariar fontes validadas,
produzir pacotes por torre e disponibilizar ao SA convenções inequívocas. Não
equivale à interpretação estrutural completa de torres/lajes/vigas.

Na suíte ampla do portal, 448 passaram e 18 falharam. Uma falha nova era
colisão do nome `main` no teste de contexto; corrigida e os 73 testes focados
de pré-processamento passaram depois. As outras 17 reproduzem o conjunto
anterior em ficha_reader, n1_routes, pillar_n3_ficha e viewer_routes.

Na VPS, 27 arquivos foram publicados seletivamente após validação em staging;
o backup dos arquivos compartilhados está em
`/opt/cad-analyzer/.deploy/preprocess-20260923/backup-shared.tar.gz`.
`cad-portal.service` tem `PORTAL_PREPROCESS_ENABLED=1` e
`PORTAL_PREPROCESS_SA_ENABLED=1`; o endpoint público `/health` respondeu
`status=ok`. No portal autenticado da obra de referência, o 14_PAV mostra o
botão **Pré-processar pavimento** habilitado e o status inicial “Inventário e
convenções; não executa SA/N3/N5.” Os recortes Torre 1, Detalhes e Convenção
de Pilares constam validados; Convenção de Níveis permanece ausente.

O gate Linux em cópia isolada do 13_PAV executou o pré-processamento, fixou o
contexto e concluiu o headless com `preprocess_context.status=consumed`, 230
chamadas reais ao classificador, 32 itens, N3 PARA/PASSA 2/2 e exportação do
pack/manifesto. O primeiro ensaio expôs `NameError: n2b64` no widget de
pré-validação existente na VPS; o reparo de três linhas foi publicado com
backup próprio e o ensaio repetido concluiu sem esse erro. A obra produtiva
14_PAV não foi processada para teste, conforme a restrição de usar cópias.
Quando o operador executar o pré-processamento e depois o SA nesse pavimento,
o consumo estará ativo; até lá, não há manifesto de consumo produtivo para
14_PAV. Sem recorte validado de Convenção de Níveis, a altura permanece
desconhecida e N3 não pode ser considerado comprovado nessa obra.

Revisão final: a seleção de convenção local exige unicidade; sem fonte local,
uma única convenção do pavimento em outro bruto passa também ao inventário de
pilares, não somente ao pacote. Em prancha que declara “medidas em centímetros
— níveis em metros”, a unidade dos níveis é `m`; declarações conflitantes de
cotas/níveis continuam ambíguas. Os 73 testes focados passaram. Após backup
`/opt/cad-analyzer/.deploy/preprocess-20260923/backup-fix-20260923.tar.gz`,
somente os três módulos alterados foram publicados. Fixture Linux no código
instalado confirmou duas torres, vínculos externos e unidade mista. Nova
rodada headless isolada do 13_PAV terminou com exit code 0,
`preprocess_context.status=consumed`, 230 chamadas, 30/32 evidências de item
coincidentes e N3 PARA/PASSA 2/2. As outras duas evidências permaneceram
`INDETERMINADO`, sem serem promovidas a classificação automática. O serviço
permaneceu ativo, `/health` saudável e sem erros recentes no journal.

Também foi executado o fluxo completo na VPS sobre uma **cópia isolada dos
recortes validados do 14_PAV**: cobertura do pré-processamento 1/1 torre,
convenção de pilares vinculada, convenção de níveis explicitamente ausente,
manifesto contextual aceito e headless SA com exit code 0. O manifesto registrou
`status=consumed`, 89 chamadas reais ao classificador e 24 evidências de item
coincidentes. A cópia fica em
`/opt/cad-analyzer/.deploy/preprocess-20260923/ab14/`; a obra produtiva não
recebeu job de teste. Assim, botão/status foram vistos no portal produtivo,
enquanto a execução e o consumo do 14_PAV foram provados no mesmo código da VPS
sem escrever nos dados da obra.

## Convenção de níveis consultiva v3 — 23/09/2026

A Convenção de Níveis agora abre no portal mesmo sem recorte aprovado. O
pré-processamento localiza o DXF bruto correspondente à torre, fixa seu hash
como dependência e lê nele a unidade e as cotas diretas do pavimento. Um
recorte de níveis, quando presente, continua fonte possível, mas não é
pré-requisito. O endpoint autenticado
`GET /obras/{obra_id}/preprocessamento/niveis?pavimento=...` apresenta por
torre cada candidato de pilar, laje e viga, seus fatos de nível e os
segmentos de fundo candidatos detectados pelo tracer. A tela distingue cota
observada, texto sem referência, conflito e nível ainda desconhecido; lajes
vizinhas aparecem como alternativas para pilares e vigas, sem inferir apoio
ou promover proximidade a fato. Cotas zero e negativas são aceitas quando
há referência direta e unidade explícita; tabelas concorrentes sem seleção
inequívoca permanecem parciais.

Na VPS, o código instalado foi exercitado sobre cópia isolada do 14_PAV:
1/1 torre processada, referência local 852,19→855,25 m (altura 3,06 m),
84 candidatos de pilar, 23 rótulos de laje, 35 de viga, 13 cotas de laje
observadas e 72 segmentos candidatos de fundo (31 vigas; zero segmentos
validados). O headless SA da mesma cópia terminou com exit code 0, contexto
consumido, 88 chamadas reais e 23 itens com evidência coincidente. O consumo
do SA nesta etapa continua limitado à convenção de pilares: a listagem de
níveis é preservada no pacote para consulta e cruzamento posterior, sem
preencher campos N1 automaticamente. A obra produtiva não recebeu job de
teste. Backup desta atualização:
`/opt/cad-analyzer/.deploy/preprocess-20260923/backup-level-before-v3.tar.gz`;
correção subsequente de cotas zero/negativas e nomes de lajes em
`/opt/cad-analyzer/.deploy/preprocess-20260923/v3-level-fix/`.
Os 79 testes focados de pré-processamento passaram. A suíte ampla teve
459 PASS e as mesmas 17 falhas anteriores em módulos fora deste recurso.
`cad-portal.service` permaneceu ativo após a instalação.

## Execução produtiva e interface do 14_PAV — 23/09/2026

A Convenção de Níveis abre como página do pavimento, sem janela de aviso. Antes
da execução, a própria página apresenta a orientação para pré-processar; após
a execução, apresenta o inventário. Quando existir recorte de níveis, o viewer
do recorte permanece na página acima da listagem. A ausência de recorte não
bloqueia o inventário.

O pré-processamento produtivo do 14_PAV concluiu no job
`50b3fe16-47dc-49e8-9137-4cabe63e0791`: 1/1 torre, referência direta
852,19→855,25 m (altura 3,06 m), 84 candidatos de pilar, 23 rótulos de laje,
35 de viga, 13 cotas de laje observadas e 72 segmentos candidatos de fundo.
Nenhum desses segmentos foi promovido a nível validado sem evidência suficiente.

O primeiro SA produtivo falhou na geração PL/N3 porque o contrato antigo exigia
recorte de níveis para a altura do pavimento. O consumidor agora usa a
referência direta fixada no pacote do pré-processamento, conferindo escopo,
hash, unidade e altura. Uma busca combinatória de distribuição inteira em PL
também foi substituída por programação dinâmica exata nos casos extensos.
Depois de prova isolada completa no mesmo código instalado, o job produtivo
`df9e040c-73f4-4f63-ac4f-ebfd6a3f6793` terminou `concluido`.
O manifesto registra N1 com 35 pilares, 22 lajes e 33 vigas; N3 gerou 30 FV,
162 LV, 22 LJ e 70 PL, sem falhas nessas classes. O recibo do contexto ficou
`consumed` e aponta para o job de pré-processamento acima. A interface do
portal mostrou SA e N3 de pilares concluídos; N5 permanece pendente, pois não
foi solicitado nesta rodada. O `/health` público respondeu `status=ok`.

Os backups anteriores ao SA e ao retry estão em
`/opt/cad-analyzer/.deploy/preprocess-20260923/prod14-before-sa/` e
`/opt/cad-analyzer/.deploy/preprocess-20260923/prod14-before-retry/`.
O manifesto produtivo está em
`DADOS-OBRAS/thierry/TMC-EST-PE-7000-14P-R03/Fase-6_Execucao_CAD/production_sa/14_PAV/20260923_131522_3470818/production_manifest.json`
na VPS. Foram aprovados 80 testes focados de pré-processamento e 33 testes
focados do gerador PL; o gate de 70 snapshots do 13_PAV também passou.

## Correção das vistas N1 de pilares no portal

Após a execução produtiva, a aba “N1 distante” do P10 mostrava “desenho ainda
não gerado” e a vista próxima caía no fallback, apesar de o exportador ter
publicado as três vistas no pack central de fichas. O leitor do portal procurava
o HTML para próximo/distante apenas dentro da pasta da obra, enquanto já
procurava a tag no pack central. O leitor agora usa o pack central mais recente
que contenha o item, preserva os painéis explícitos `near`/`far` e não os
sobrescreve com uma busca genérica de SVG.

No código instalado da VPS, o P10 devolveu SVGs distintos para próximo sem
tag (1.886.832 caracteres), distante (1.948.984) e com tag (1.993.987).
Depois do restart, as duas primeiras abas renderizaram desenho no navegador;
o `/health` voltou a `status=ok`. O teste focado de resolução das três vistas
passou (3/3). A suíte inteira de `test_portal_ficha_reader.py` continua com
oito falhas ligadas à fixture local antiga do 13_PAV; as 19 demais passaram.

## Cotas por item nas faces ABCD dos pilares

O P10 mostrava `—` para vigas nas tabelas ABCD embora o estado SA já tivesse
cotas nos segmentos de fundo. O leitor N1 agora cruza cada linha da tabela com
o registro da laje ou com os segmentos da viga no mesmo estado de pavimento.
Quando há geometria do pilar e dos segmentos, prefere os trechos que o tocam;
assim uma viga com cotas diferentes ao longo do pavimento pode ter a cota
correta no pilar consultado. A leitura do pacote de pré-processamento é limitada
à torre e à execução fixadas no manifesto do SA, e serve para evidenciar
divergências, sem substituir silenciosamente a cota do SA.

Cotas inferidas, geometricamente não vinculadas, conflitantes ou ambíguas
recebem `⚠` com motivo. Quando não há conclusão única, a célula mostra
provisoriamente o nível de chegada do pilar. Linhas `nenhuma` continuam
sem cota por não representarem um item. O enriquecimento ocorre na resposta
do portal e não altera o snapshot SA nem os SVGs N1 publicados.

Na cópia do estado produtivo do 14_PAV, as 35 fichas de pilar ficaram sem
linhas de item real com nível vazio. O vínculo geométrico reduziu de 59 para
24 as linhas com trechos de cotas distintas que ainda exigem revisão. No P10,
V409/V410/V402 aparecem com 855,25; L410 exibe 855,22 com `⚠` porque o
pacote de pré-processamento aponta 855,25 para esse rótulo. A divergência
permanece aberta para conferência no DXF. Os 55 testes focados passaram; o
`cad-portal.service` voltou a `active`, e os valores e a legenda foram
conferidos na página produtiva do P10 na aba “N1 com tag”.

## Cruzamento de dimensões, distâncias e tags ABCD

A tabela SA original do P10 trazia V409/V410 como 19/60, enquanto os
registros de laterais dos segmentos ligados ao pilar trazem 19/55 e os fundos
confirmam largura 19. Não há corte independente dessas vigas no estado do
14_PAV. O portal agora usa a dimensão da lateral correspondente ao segmento,
cruza a largura do fundo e o corte local quando existe, e marca divergências ou
altura ainda sem confirmação independente com `⚠`. A dimensão anterior da
tabela é somente comparada: não pode ser reutilizada como evidência da viga.
Nomes sem item correspondente ou sem vínculo geométrico também recebem aviso.
O cruzamento dos textos posicionados no DXF achou `19/55` junto a V409 no P10;
o `19/60` coincide com a seção do pilar e é excluído como prova da viga.
Em V410 há ainda um texto `19/50` próximo: a tela mantém `19/55 ⚠` da lateral
e explicita essa divergência para revisão, sem promover uma leitura arbitrária.

As distâncias d.esq/d.dir preservam a convenção de cantos e passantes `—`.
O portal mede distâncias ausentes de laje pelo contorno associado, indicando
inferência, e alerta se uma distância existente ultrapassa a face ou diverge
do contorno. No P10, L410 na face B passou a mostrar 0,00/19,03 cm com aviso
de medida pelo contorno. As tags da vista “N1 com tag” são regeneradas a partir
da tabela consultiva e do DXF da mesma obra, com cache por conteúdo. No P10,
o novo SVG contém 19/55 para as vigas, sem a antiga tag 19/60. Se a geração
não estiver disponível, o portal conserva o desenho original com aviso visível
de que as tags não estão sincronizadas.

Nome, dimensão e nível das linhas reais podem ser corrigidos pelo usuário no
portal. As revisões são gravadas atomicamente em `.portal_overrides/pilares_abcd`
por pavimento e pilar, com guarda da identidade original da linha; o snapshot
SA não é modificado. A tabela e a tag consultivas são atualizadas na próxima
leitura. Na auditoria local das 35 fichas do 14_PAV, houve 265 linhas reais:
32 divergências de dimensão, 24 níveis ambíguos e 4 pares de distância em
conflito. Nenhum nome ficou sem correspondente nos itens SA; 38 vínculos de
nome ainda exigem confirmação geométrica. Os testes focados passaram (59/59),
e o P10 foi conferido no navegador produtivo, inclusive abertura/cancelamento
do editor sem gravação.

O campo **Canto** também passou a ser editável no mesmo formulário para faces
A–F. A API normaliza as duas letras para maiúsculas e preserva a correção no
override do pilar, mantendo a guarda pela identidade original da linha. Em
23/09, os 53 testes focados de ABCD e faces especiais passaram; a versão na
VPS permaneceu ativa e o editor do P10 exibiu oito campos de canto, com
abertura/cancelamento conferidos sem alterar dados produtivos.

## Posição vertical das aberturas N3 ABCD

No P10 do 14_PAV, as vigas V409/V410 têm cota explícita 855,25 nos segmentos
SA/N1, mas a variante N3 antiga trazia `_nivel_origem=852,19` e `y_rel=0`.
O editor ABCD passou a cruzar cada abertura com a viga/canto da tabela ABCD,
usar a cota da viga para a distância ao topo e desenhar pela cota absoluta.
Mantém aviso da divergência de 306 cm com o recorte N3 antigo. Uma edição
humana já salva na ficha N3 continua prevalecendo. Ao converter a ficha em
payload do robô, `y_rel` é derivado da nova posição em vez do valor antigo.
O SVG interativo do P10 foi conferido na VPS com D1 da face A no topo,
nível 855,25 e distância ao topo 0 cm. Faces A–D compartilham a mesma
linha de fundo no SVG, inclusive C e D com malha menor. A posição de cada
abertura continua calculada pela cota da sua face. O DXF N3 já publicado
não foi refeito por esta correção de visualização.

No desenho interativo ABCD, o vazio superior confirmado pelo contrato N3
agora aparece em C e D (64 cm no P10). Aberturas e lajes dessas faces usam a
mesma origem absoluta do topo do pavimento que A/B, enquanto os painéis
continuam alinhados pelo fundo. O recorte central CC de V402 mede 27 cm no
payload N3, mas a face C e a viga nominal têm 19 cm. O SA indica contato
interno: a ficha mantém os 27 cm originais editáveis e sinaliza a divergência,
enquanto o desenho limita o vazio à largura da face, sem transbordar. A face D
sem abertura própria no contrato não recebe uma abertura inventada.

A ficha web ABCD lê `paineis_intervals_*` do payload N3 como malha efetiva,
inclusive subdivisões `paineis_unidos_*`. A/B mantêm os módulos de 122 cm;
C/D são recalculadas pelo contrato SA com módulos contínuos de até 244 cm,
independentemente de abertura lateral. No P10, C e D mostram uma chapa de
240 cm acima da cinta de 2 cm e abaixo do vazio superior de 64 cm. O robô
também foi corrigido para gerar essa regra em novas execuções. O DXF N3 já
publicado não foi regenerado; suas divisões antigas podem divergir da ficha.
Overrides humanos de painéis continuam a prevalecer sobre a malha automática.

Os vazios de viga e laje usam o mesmo rosa e se unem visualmente quando se
tocam. Cada recorte conserva sua identidade e pode ser selecionado nos campos;
o vazio superior também tem um controle próprio para seleção quando fica
coberto por outra abertura. Quando um recorte atravessa um painel, a ficha
agrupa áreas que compartilham uma borda como um único painel recortado, inclusive
em L, e separa somente regiões desconectadas. Cada painel recortado apresenta
largura e altura totais pelo contorno, mesmo quando sua área útil é em L. Ao
editar essas duas medidas, a ficha redimensiona o painel de base, recalcula os
recortes e mantém alinhada uma laje cujo limite tocava um recorte ancorado à
borda oposta. O componente selecionado continua indicado. Nome,
dimensão e comportamento vêm do SA/N1:
vigas que chegam ou param aparecem como aberturas laterais; vigas que passam
ou são internas e lajes são vazios limitados à face.

Em 24/09, um teste de navegador local reproduziu o B4 do P10: o recorte gera
dois componentes, sendo um retângulo isolado e um painel em L composto de duas
áreas unidas. A dimensão do L é exibida como 60 × 41 cm pelo contorno. Ao
editar para 65 × 45 cm, o L continua uma peça única, e a laje que tocava a
abertura acompanha o alargamento para conservar o contato.

Em 24/09, a ficha N3 passou a usar a mesma dimensão ABCD enriquecida e revisada
que a tabela SA/N1 exibe, inclusive o texto de dimensão da viga encontrado no
desenho. Para uma viga 19/55, a abertura e o vazio superior têm 59 cm; para uma
laje de 14 cm, o vazio tem 16 cm. A face curta com viga interna recebe recorte
com a largura da própria face. Alterações manuais de geometria que já divergem
do contrato do robô são preservadas. No viewer, recortes inteiramente cobertos
por outro deixam de duplicar a área rosa, mas permanecem editáveis nos campos;
qualquer trecho que ultrapasse o outro recorte continua visível. Os 21 testes
focados do backend, cruzamento de níveis e navegador passaram. A publicação
e a conferência no P10 da VPS aguardam conectividade da máquina: SSH/22 e
HTTPS/443 em 62.238.111.147 não respondiam na verificação de 24/09.

Em 25/09, a VPS voltou e os quatro arquivos da ficha N3 foram publicados com
backup remoto. A conferência de produção do P10/14_PAV mostrou V410, V409 e
V402 como 19/55 e recortes de 59 cm; a L410 usa 14+2=16 cm. A face B tinha
`vazio_topo=0` explícito porque a laje já possuía recorte próprio: corrigimos a
sincronização para não criar um vazio superior de largura total. No B4 real
há uma peça isolada 37×3 e outra peça conectada recortada 82×64, coerente com
as três vigas agora de 59 cm e com a altura de painel salva por override
humano. A segunda peça tem formato de T, portanto não deve ser rotulada L;
o caso sintético L continua coberto pelo teste de navegador. Uma abertura
inteiramente coberta deixa de ser desenhada, mas segue nos campos editáveis.
O SVG usa pequena sobreposição interna entre retângulos da mesma peça para
eliminar a linha escura sem mudar a medida lógica; validado no navegador da
VPS. A evidência do vazio C/D agora distingue a dimensão SA atual da evidência
original N3. Nenhum DXF ou JSON produtivo foi modificado na publicação.
