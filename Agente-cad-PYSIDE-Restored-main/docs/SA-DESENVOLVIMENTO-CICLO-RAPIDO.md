# Desenvolvimento do SA sem renderização ou publicação

Procedimento canônico, autorizado pelo dono em 10/10/2026. Referência de intenção:
“ciclo após ciclo até não ter pendência, aí sim a conferência visual final”.

## Sequência obrigatória

1. Congelar as fontes e criar snapshot SQLite isolado da base real.
2. Reexecutar o pré-processamento canônico completo, com coleta nova de evidências.
3. Executar o SA completo com esse contexto, usando os mesmos consumidores,
   merge, recuperação geométrica e gates internos da produção.
4. Executar o novo QA Gate pós-SA sobre o estado em memória e o DXF original.
5. Examinar pendências por unidade, diferenças de geometria/níveis e regressões.
   Corrigir a causa geral e repetir os passos 1–5. Nenhuma rodada publica.
6. Somente uma rodada completa sem pendências e com regressão aprovada libera
   a publicação. A publicação deve corresponder às fontes, contexto e código
   dessa rodada; qualquer mudança exige novo ciclo rápido antes de publicar.
7. Fazer a conferência visual final do resultado publicado. Se aparecer um erro,
   voltar ao ciclo rápido, resolver e aprovar novamente antes de republicar.

Uma aprovação numérica libera a publicação; a conclusão da missão depende também
da conferência visual. O modo rápido não fabrica selos de aprovação humana.

## Entrada canônica

`scripts/arete/dev_sa_cycle.py` é a orquestração de desenvolvimento. Ele chama
`preprocessamento.service.run_floor(output_root=...)`, o único motor headless
`headless_sa_analise.run_analysis(development=True)` e
`qa_cad_gate_run.measure_state(...)`. A medição pós-SA é a mesma usada por
`run_pavimento` para o estado publicado; tolerâncias e mecanismos não mudam.

Snapshots brutos do SA não trazem a geometria derivada `slab_steps`. Antes de
medir, `measure_state` reconstrói as regiões ausentes com `slab_steps.enrich_state`,
a mesma rotina usada pelo leitor publicado, sobre uma cópia do estado. Regiões
explícitas são preservadas, inclusive uma lista vazia revisada. Falha nessa
reconstrução deixa o QA dependente indisponível; não autoriza substituir a
espessura regional pela principal. Esse preparo não renderiza nem publica.

```powershell
D:/Agente-cad-PYSIDE/.venv/Scripts/python.exe scripts/arete/dev_sa_cycle.py `
  --obra D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1 `
  --pav 14_PAV --db D:/Agente-cad-PYSIDE/project_data.vision `
  --out scripts/arete/relatorios/novo_ciclo_14 --wait
```

O manifesto vigente fornece as declarações de fontes, que são inventariadas de
novo. `--input-manifest` permite fornecer explicitamente obra_id,
pavimento_id e declarations. Não reutiliza os níveis interpretados antigos como
resultado da nova rodada. Cada execução exige pasta nova. `--baseline` aponta
para um relatório anterior e detecta itens que deixaram de conferir no QA.
Também compara o `analysis_state.json` situado junto desse relatório.
`--baseline-state` permite indicar outro estado de referência explicitamente.
Sem referência espacial, a rodada registra uma pendência e não libera publicação.
O status verde, sozinho, não prova que a área ou o nível foi preservado.

## Isolamento e resultados

A rodada grava somente evidências JSON, relatório e snapshot SQLite na pasta
isolada. Não gera HTML, SVG, PNG, N3 nem manifesto de produção; não persiste na
base real. A serialização em memória é compartilhada com a publicação normal.
A construção do diálogo oculto mantém a lógica canônica; callbacks de render
não são processados nessa etapa. O histórico humano do diálogo não é gravado.
Qt em modo offscreen ainda pode desenhar o CAD. Por isso a instância de
desenvolvimento suprime os métodos gráficos do canvas antes do carregamento,
conservando os metadados de entidades, DXFLoader, índice espacial, motores e
serializador canônico. A instância normal permanece intacta. Testes usam o
CADCanvas real e verificam ausência de leitura/renderização visual e de novos
GraphicsItems. Validar equivalência de dados e QA com as mesmas fontes e código;
somente tempo, IDs da execução e timestamps são metadados descartáveis.
O guard observa os arquivos e índices da produção vigente de cada pavimento,
além de verificar o hash da base e do DXF; não reprocessa os renders históricos.
O intervalo protegido começa depois de adquirir todos os locks canônicos,
antes de copiar a base. Uma publicação do dono anterior durante a espera na
fila não pertence ao ciclo que ainda não começou. Alterações durante o
intervalo protegido continuam reprovando a execução. Mesmo nessa falha,
preservar estado e relatório diagnóstico, marcar isolamento `failed` e impedir
aprovação; não repetir todo o processamento apenas para recuperar evidências.
O relatório também conserva os contadores de desenho suprimido da instância
Qt. Ausência de arquivos visuais, sozinha, não comprova ausência de desenho.
Na prova de paridade, comparar o estado canônico serializado: tuplas em memória
e listas JSON representam os mesmos dados. No QA, excluir somente timestamps,
hash do snapshot derivado desses timestamps e campos explícitos de duração
(`duracao_s`, `tempos_s`). Conteúdo estrutural, erros, incertezas, unidades e
evidências devem coincidir. Paridade aprovada não substitui um ciclo completo
cujo isolamento tenha falhado por atividade concorrente.

`cycle_report.json` contém tempos de pré/SA/pós-SA, contexto recebido, QA por
classe/item, pendências e verificação dos arquivos protegidos. Código de saída
0 significa elegível para publicar; 3 indica pendências, com relatório disponível
para a próxima correção. Erro de execução ou isolamento não equivale a aprovação.

`assess_cycle` bloqueia divergências, incertezas, indisponibilidade, inventário
ou QA incompletos, revisão de fonte diferente, níveis atuais não resolvidos e
regressões. `not_applicable` não é pendência. A lista explicita o item e a razão;
não se reduz uma incerteza mudando tolerâncias ou excluindo o item.

O resumo do QA exige pelo menos um aspecto realmente medido para apresentar
`confere`. Um relatório vazio, ou contendo apenas aspectos incertos opcionais,
fica `incerto`; nesse último caso conserva a razão de cada aspecto sem medição.
Aspectos opcionais não bloqueiam um item que já tenha uma medição válida,
salvo divergência ou outra incerteza bloqueante. Essa regra de apresentação não
substitui a avaliação de cobertura por unidade feita pelo ciclo rápido.

Alertas não são uma contagem de defeitos físicos: o mesmo problema pode aparecer
no fato, segmento, intervalo e resumo QA. Preservar essa rastreabilidade ao agrupar
por causa. QA com status `confere` e nenhuma medição não libera a unidade.
Ocorrências históricas e atuais de mesmo nome exigem reconciliação pela fonte,
contorno e identidade; nome igual não autoriza substituir um fato desconhecido.
Uma geometria de levantamento com nome de pilar pode ser um corte de viga.
Esse papel exige associação nomeada independente, mesmo contorno original e
interseção dos identificadores originais de entidade. Capturar os handles ao
ler o DXF e transportá-los pelos vínculos; não inventar proveniência procurando
um contorno parecido depois. A extensão interpretada conserva o contorno original
para essa comparação. Geometrias canônicas de pilares têm precedência e nunca
são descartadas porque outra associação compartilha seu nome.
Níveis diferentes em regiões disjuntas podem ser legítimos, desde que os contornos,
fatos únicos, unidade e datum comum estejam comprovados. Fato duplicado ou datum
ausente mantém a pendência, mesmo quando as regiões não se sobrepõem.

## Regressão dinâmica

Antes de priorizar correções, agrupar as ocorrências do relatório por mecanismo
e conservar a correspondência de cada grupo com todos os registros originais.
Separar evidências diretas de resumos QA, cobertura ausente e mudanças de status
que podem decorrer da mesma causa. Campo de nível desconhecido e valor ausente
são duas ocorrências do mesmo campo, não dois defeitos independentes. Não contar
essas consequências como alterações a implementar nem removê-las do gate.
Uma frente de investigação pode conter várias causas; só consolidar uma causa
comum depois de comprová-la. Priorizar a causa geral com maior alcance e validar
todo o conjunto afetado, mantendo casos negativos e decisões humanas.

Na perda de vínculos, comparar as etapas da mesma rodada e mesma fonte:
coleta, resultado SA, merge, recuperação e enriquecimento final. Um replay de
outra rodada não prova em qual etapa o vínculo desapareceu. Ganho de vínculos
também exige prova; não restaurar indiscriminadamente um snapshot anterior.

Rastrear consumidores reais em processo isolado permite comparar suas entradas
e saídas sem renderização. Retângulos finais de fundo produzidos por reparadores
distintos são propostas: uma marca específica do produtor não substitui a prova
das duas paredes originais nem deve excluir propostas de outro produtor. Somente
a recuperação que confirma essas paredes pode disponibilizar um corredor para
medição. Medidas de contatos interiores usam os trechos locais assim confirmados;
a caixa envolvente ou o acolchoamento gráfico de um traçado não prova folgas.

Durante correção localizada, rodar os testes da causa e o ciclo completo do
pavimento alvo. Antes de liberar publicação, rodar também os pavimentos de
controle relevantes ao comportamento alterado. Nesta missão, 14_PAV é alvo e
13_PAV é controle; isso não certifica todos os pavimentos. Mudança transversal
exige ampliar a matriz para os estilos e casos realmente afetados.

Comparar identidade dos itens, polígonos/uniões físicas, parcelas, níveis,
seções numéricas e preservação de decisões humanas. Partitionamento pode mudar
sem alterar a união física; uma perda de área pode existir mesmo com os mesmos
nomes e status QA. O caso V406 motivou essa distinção.
Laterais representadas por dois pontos são linhas válidas: comparar comprimento,
deslocamento e níveis no trecho comum, em vez de tentar construir um polígono.
Diferenças ficam pendentes para análise; o comparador não as aprova sozinho.

## Observação sobre a cadeia atual do portal

Inspeção local/VPS de 10/10/2026: o ramo `SA-only` retorna antes de chamar
`qa_cad_gate_run.best_effort`; a chamada existente fica no ramo posterior à
materialização. Portanto, não presumir QA automático em SA-only. Este modo
rápido chama o novo gate explicitamente antes de qualquer publicação. Uma
alteração futura no encadeamento do portal deve ter teste próprio.

## Eficiência

O ganho deve ser medido no mesmo ambiente, fonte e contexto. O modo rápido
economiza exportação, renderização, materialização e publicação; preserva o
tempo necessário para interpretação completa e QA. Tempos reais e limitações
ficam no relatório datado da validação, sem promessa de “super rápido” nem uso
de cache antigo para simular progresso.

Na VPS, a segunda rodada de 14_PAV levou 64,49 s de pré-processamento,
70,83 s de SA e 11,77 s de QA, com 153,76 s no total. Uma rodada histórica
publicada tinha 68,44 s dentro do SA e cerca de 118 s no job completo.
Isso demonstra o funcionamento sem publicação; não demonstra aceleração do
motor SA nem constitui benchmark controlado de renderização.
Resultados e pendências: `scripts/arete/relatorios/20261010_encontros_niveis_14pav/desenvolvimento_rapido/RELATORIO.md`.

Este entry point não publica. A autorização de publicação exige conferir também
a regressão dos controles e a correspondência de código, fontes e contexto com
a última rodada aprovada. O ramo SA-only do portal ainda não impõe essa política
automaticamente; não tratar o relatório rápido como aprovação visual final.

## Ambiente e guarda da rodada

### Guarda de versão do código — 11/10/2026

O isolamento inclui os bytes dos fontes Python do motor, pré-interpretação,
QA e entry points Arete. O ciclo registra SHA-256 antes e depois; alterações,
arquivos novos ou removidos impedem aprovação, mesmo se o banco e as publicações
permanecerem intactos. O relatório diagnóstico é conservado. Uma rodada com
código alterado por outra sessão deve ser repetida com versão estável.
Esta guarda detecta mudanças durante o intervalo, não substitui a coordenação
de deploy ou comprova uma versão carregada antes desse intervalo.

Caso real: o controle 13º de 11/10 terminou com 330 ocorrências e proteção de
produção aprovada, mas leitores PIL/QA foram alterados durante a execução.
O recibo externo detectou a mudança; a rodada serve somente para diagnóstico.
A guarda incorporada foi validada localmente, inclusive alteração de conteúdo
com mtime preservado. A medição local de 701 fontes levou cerca de 0,26 s.
Na VPS, duas coletas de 575 fontes (11.367.775 bytes) somaram 0,263 s,
sem mudanças entre elas: cerca de 0,11% do tempo do controle diagnóstico.
A guarda foi depois instalada na VPS com jobs ociosos, hashes esperados e
compilação verificada. Foi exercitada nos ciclos completos14/13 de11/10:
202,17s e246,21s, código estável, 4916 caminhos de produção protegidos,
zero renderização/publicação/mutações detectadas. As300/340 ocorrências
preservadas mostram que isolamento aprovado não aprova a missão.
Recibo da medição e hashes estão em
`scripts/arete/relatorios/20261010_encontros_niveis_14pav/desenvolvimento_rapido/integracao_v408_identidade/runtime_guard_benchmark_readonly.json`.

### Revisão explícita dos diffs — implementação de11/10/2026

O CLI aceita `--review-receipt`, `--reviewer` e registros explícitos
`--review-evidence ID=PATH`. Salva o estado atual uma única vez, conserva
todos os diffs em `regressions` e registra `regression_review`. Só diferenças
exatas de geometria/número com prova e contraprova original vinculadas aos
hashes da fonte, baseline, estado e evidência podem ser revistas. Recibo
inválido acrescenta bloqueio; QA, isolamento e pendências de nível não são
dispensados. Sem recibo, o comportamento permanece conservador.

Cada nova rodada precisa de revisão própria: um recibo dos bytes de um estado
anterior não aprova automaticamente outro estado, mesmo com o mesmo nome de
item. Não substituir o baseline pela correção para esconder o histórico.
Os25 diffs de contorno LAJ revisados no ciclo14/13 de11/10 têm recibos próprios;
não são aprovação de níveis ou da missão. A integração passou78 testes e foi
instalada na VPS com guarda de jobs/hashes e compilação. O próximo ciclo combinado
com a correção de serialização PIL precisa comprovar seu funcionamento integrado.

Uma revisão posterior usa `scripts/arete/review_sa_cycle.py` sobre o relatório
congelado e gera artefato separado, sem repetir SA, renderizar ou publicar.
Exige hashes dos estados gravados pelo produtor, comparador integral reproduzido,
guarda de isolamento/código aprovada, revisor explícito e prova exata. Conserva
`raw_assessment` e não remove bloqueios QA/níveis. Relatórios antigos sem esses
hashes não ganham aprovação por esse caminho. Isso permite revisar correções
depois de olhar sua evidência, conservando a exigência de novo ciclo fresco após
mudanças do motor. Implementação ampliada:84 testes passaram; complemento
instalado na VPS em11/10 com guarda de jobs/hashes e compilação. Rodada nova
14/13 `root-owner-final-20261011` iniciou para validar o consumo integrado,
incluindo confirmação humana regional L414 e correções PIL coordenadas.

Uma auditoria complementar identificou perda de contatos PIL mesmo quando as
distâncias dos contatos restantes passaram. Portanto redução de divergências
não prova inventário: comparar conjuntos por pilar/face/papel/nome, conservar
adições e remoções como diferenças pendentes e confrontá-las com o original.
A integração foi instalada na VPS em11/10: comparador v2 registra
`contact_changes` por pilar/face/papel/nome e mantém adições/remoções como
pendências. Recibos antigos de contorno não aprovam esse inventário. O revisor
congelado também reproduz esse conjunto e exige prova original específica.
O lote passou168 testes locais, incluindo consumo regional e casos de conflito.
Ciclo fresco14 `root-regional-v2-20261011`:202,809s, código/isolamento aprovados,
320 ocorrências brutas, nenhuma renderização/publicação. A revisão independente
dos11 contornos LAJ sobre os bytes desse novo estado gerou artefato separado
com309 pendências. O bruto permanece intacto; a missão continua sem selo.
O consumo real L414/P22 B confirma h10/855,22 por67cm.

O controle13 teve código estável, mas foi recusado porque outro job do portal
criou entrada em `preprocessamento/v1/sa_inputs` durante a rodada. Essa escrita
concorrente é diferente de alteração de código e exige janela de entradas
estáveis; não remover a guarda, excluir entradas ou interromper o job detentor.
O resultado357 serve somente para diagnóstico.

### Referência de nível no consumo

Os consumidores devem usar o datum verificado da própria rodada, vinculado
à fonte/projeto/pavimento, antes da convenção externa. Valores absolutos desse
contrato têm unidade explícita em metros; não decidir unidade pela magnitude.
O datum padrão de viga não substitui uma cota própria vinculada à viga e nunca
resolve nível de região de laje por espessura. Sem contexto, não selecionar
obra ou pavimento fixo para preencher o campo.

Caso de11/10: linhas PIL de vigas exibiam572.9cm de uma convenção legada,
embora o contexto fresco tivesse topo855,25m. Correção estreita em seis caminhos
de consumo preserva níveis locais e usa o datum verificado.104 testes relevantes
passaram; instalação com guarda idle/hash concluída. O ciclo fresco14
`root-datum-fv-20261011` confirmou o consumo real em202,710s:221 linhas com
855,25m, sem572.9, região L414/P22 preservada, código/dados estáveis e sem
renderização/publicação. Dez linhas sem nível permanecem em revisão.324
ocorrências brutas/313 após revisão exata dos11 contornos LAJ; nenhum selo geral.

Ao investigar regressão, capturar entradas e saídas das chamadas sucessivas
no ciclo real, além do snapshot final. Coleções históricas do DB ou uma
reexecução com esses dados não comprovam a entrada nova do SA. Instrumentação
diagnóstica deve ficar em wrapper isolado, preservando runtime, fonte e guardas.
Caso11/10: os contatos P47 C/V420 e P51 D/V402 existiam na primeira chamada
e desapareciam na seguinte, quando um subset FV verificado era consumido como
se descrevesse toda a ocupação estrutural. A correção coordenada está local;
exige instalação guardada e novo ciclo antes de aprovação.

A rodada anterior14 `root-owner-final-20261011` passou isolamento em217,33s,
com290 ocorrências. O13 dessa sequência foi recusado por alteração concorrente
em `pillar_special_faces.py`, assim como TIPO da outra sessão. Preservar os
relatórios apenas como diagnóstico; não aprovar nem restaurar versões antigas.

### Consumo real e temporários de desenvolvimento — 11/10/2026

Um pós-QA sem alerta numérico não comprova que o SA consumiu a prova do PRE.
Comparar também a origem do valor no estado final e o recibo da chamada real.
Caso VF402: o pacote resolveu as laterais por fronteira do FV original, porém
o SA ainda serializava `lv_cell_estimado`. O adaptador instalado corrobora
somente valor concordante em célula estimada, por geometria coincidente,
com contexto fresco e cadeia inteira até raiz CAD/humana independente.
Não muda geometria, valor, ajuste ou convenção; conserva inferência e avisos.
Ambiguidade ou conflito vira pendência; testes/replay não substituem ciclo fresco.

O consumidor deve usar o schema real de vínculos: o conjunto de links também
contém slots em lista, além dos dicionários de segmentos laterais. Validar tipos
como o coletor canônico e limpar anotações antigas apenas em células válidas,
mesmo quando a PRE não entrega parcelas. Não percorrer recursivamente outros
contratos. Em11/10 os testes iniciais passaram, mas o ciclo completo revelou
essa diferença de schema; as duas rodadas falhas ficaram sem aprovação,
com logs preservados e repetição obrigatória após a correção pontual.

Repetição completa14 confirmou quatro células consumidas, incluindo as
duas laterais angularesVF402, mantendo status inferred. Comparação espacial,
numérica e de contatos contra a versão imediatamente anterior: zero diferenças.
PRE84,00s/SA76,18s/QA31,57s, total200,39s; isolamento e código estáveis.
As233 ocorrências brutas incluem duas restaurações de inventário contra um
baseline mais antigo. Revisão nova dessas duas, restrita às identidades e
com hashes atuais, deixa231 bloqueios. Isso comprova o consumidor; não
libera publicação nem a conclusão da missão. Recibo no relatório da rodada.

Controle13 da mesma versão: PRE97,02s/SA91,67s/QA50,20s, total447,39s
inclui a fila do14. Isolamento e código aprovados; zero diferenças físicas,
numéricas ou de contatos contra o controle imediatamente anterior. Nenhuma
parcela sem prova consumida.361 brutas/347 após nova revisão exata dos14
contornosLAJ, com todos os demais bloqueios preservados. Os controles têm
recibos de consumo separados da aprovação geral da missão.

Em execuções concorrentes de pytest, dar `--basetemp` distinto a cada rodada.
O diretório compartilhado de fixtures pode ser limpo pela outra execução,
invalidando testes que ainda leem DXFs temporários. Repetir a falha em pasta
isolada antes de atribuí-la ao motor; registrar a colisão e a repetição real.

Snapshots SQLite isolados são grandes. Antes da rodada, verificar espaço.
Após preservar relatório, estado, contexto, recibos e respectivos hashes,
uma cópia SQLite descartável de rodada própria encerrada pode ser retirada
com lista exata de caminhos e manifesto; não aplicar esse procedimento a
DB real, dados da obra, evidências, jobs ativos ou históricos de outras sessões.
Na recuperação de11/10, esta sessão retirou7,374GB apenas de cópias isoladas
próprias e preservou os dois manifestos e as provas. Sem limpeza de produção.

Versão P34/parcelas:14 terminou209,20s com231 ocorrências brutas e guarda
aprovada;13 repetiu361 brutas/347 após revisão exata dos14 contornos LAJ,
guarda aprovada, PRE98,95s/SA92,72s/QA50,40s (total321,17s inclui fila).
TIPO manteve1038 ocorrências de níveis iguais ao baseline; diferenças novas
de contatos continuam em revisão. Nenhum desses controles aprova a missão.

### Dependências no runtime

#### DEV-RECURSOS-E-CONTRATOS-N3-N5-20261012

O ciclo rápido PRE → SA → pós-QA usa o mesmo motor e gate, omitindo desenho e
publicação. Uma cópia congelada suficiente para SA não comprova que referências
de desenho estejam disponíveis para N3/N5. Para testar os geradores, verificar
os módulos efetivamente importados, os recursos do modo e seus SHA-256. Instalar
somente a referência canônica ausente, sem substituir dados originais ou copiar
uma versão antiga inteira para o código corrente.

Fixtures N3/N5 devem cumprir os contratos atuais: manifesto da rodada e do modo,
inventário de segmentos, painéis fechados, arquivos das cinco zonas PL e nomes
de faces LV. Se um item falhou no N3 da rodada atual, N5 não pode reaproveitar o
sucesso de uma rodada anterior. Atualizar uma fixture antiga exige preservar
esse teste negativo; não dispensar o manifesto nem relaxar os gates do motor.
Contar recursos fabricados pela classe/estilo apropriado, separando os recursos
da legenda INI dos recursos do painel que ela enquadra.

Em 12/10, 111 testes locais N3/N5 passaram após instalar duas referências INI
ausentes com SHA conferido e atualizar fixtures para esses contratos. A mesma
versão passou 235 testes PIL e três ciclos completos em fixtures isoladas, sem
regressão nem mudança espacial. Permaneceram 180/132/1141 ocorrências em
13_PAV/14_PAV/TIPO, respectivamente. Isso não aprova o pavimento: os ciclos
terminaram com pendências e não houve publicação nem conferência visual final.
Prova: `scripts/arete/relatorios/20261011_pil_continuacao/current_30_completed_receipt.json`.

#### DEV-REVISOES-HUMANAS-COMO-ENTRADA-20261012

Uma resposta humana já registrada precisa acompanhar a fonte na cópia isolada
de desenvolvimento, com SHA do DXF, região/segmento e handles originais. A
ausência do sidecar de revisão pode fazer uma decisão resolvida voltar como
`unknown`; não repetir a pergunta nem tratar isso como regressão do motor sem
conferir os inputs. Copiar somente a decisão correspondente à revisão exata,
manter o guard dos sidecars e repetir PRE → SA → pós-QA. A remoção de uma
pendência só é válida depois de comprovar o consumo e revisar os deltas atuais.

O caso L414/h=10 usa a decisão `LAJ-L414-FUNDO-CONTINUO-20261011`: topo 855,22 m,
mesmo fundo 855,12 m da principal h=13/topo 855,25 m. A decisão pertence somente
à região `slab-step:L414:972` da revisão explicitamente confirmada. Não aprova
outras regiões nem transforma falta de espessura em uma regra de mesmo fundo.

#### DEV-DETALHE-NO-BRUTO-DECLARADO-20261012

O recorte da torre pode não conter o detalhe ampliado da própria prancha. A
pré-interpretação consulta também o `raw_level_reference` explicitamente
declarado no manifesto, da mesma obra, pavimento e `bruto_id` da torre. Não
buscar desenhos vizinhos por nome. Exigir fonte validada, caminho dentro da
obra e SHA original. Declaração concorrente ou revisão alterada bloqueia o
consumo. Preservar os handles do bruto em seu próprio namespace: eles não
podem reclassificar entidades com o mesmo handle no recorte da torre.

Um detalhe só autoriza a conferência dimensional quando há legenda explícita
de igualdade dos pilares, contorno correspondente e cadeias originais de cotas
com extensões, marcas, ticks e números vinculados. O SA confere a geometria
real resultante contra a medida provada, sem criar outro pilar nem transportar
posição ou nível. A conferência não aprova automaticamente encontros PIL/FV.

Prova de 12/10: 42 testes passaram; três ciclos completos isolados terminaram
sem regressões ou mudanças espaciais. P26/P27 do 13º foram conferidos contra
o detalhe do bruto declarado; no 14º o detalhe local continuou conferido.
TIPO permaneceu sem detalhe provado. A entrada do 14º também recebeu as
decisões existentes `PIL-ESCADA-PAREDE-3DC-20261011` e
`LAJ-L406-REGIAO-96B-C0B-20261011`, vinculadas à revisão exata. O ciclo completo
removeu quatro avisos indevidos de nível da parede da escada: 130 → 126
ocorrências, sem alteração geométrica, numérica ou de contatos. Isso valida
o consumo das decisões, mantendo o gate de publicação reprovado pelas
pendências técnicas restantes. Evidência:
`scripts/arete/relatorios/20261011_pil_continuacao/current_31_completed_receipt.json`.

Coordenação de11/10/2026: o controle13 `root-datum-fv` terminou em409,77s,
mas a guarda detectou alteração concorrente de `lv_inverted_crossings.py`.
Nenhum dado protegido mudou. Guardar como diagnóstico e repetir com código
estável; um teste que passou depois do deploy não retroativamente aprova essa
rodada. O ciclo14 coordenado `contact-axis-fixed` terminou em203,12s com guarda
aprovada e250 ocorrências brutas, sem render/publicação. A redução da contagem
não dispensa revisão dos contatos adicionados nem das regressões restantes.
Repetição do controle13 `root-contact-axis` aprovada na guarda em246,068s,
com361 ocorrências brutas e347 após revisão exata de14 contornos LAJ no novo
estado. O controle permanece com QA pendente; guarda aprovada certifica apenas
que a comparação ocorreu sobre dados e código estáveis. Ao mudar o baseline
para um estado já corrigido, não subtrair novamente as revisões anteriores:
aprovar somente diferenças presentes no relatório atual e nos hashes atuais.

Conferir as dependências no Python que executa o SA, além do ambiente local e
do portal. Antes de um ciclo completo, verificar importação, compatibilidade
dos pacotes e execução real dos detectores necessários na fonte da rodada.
Uma dependência declarada no requirements não comprova que esteja instalada.
Falha do detector deve virar pendência bloqueante, nunca uma lista vazia de
regiões apresentada como sucesso. Depois de corrigir o ambiente, repetir pré +
SA + pós-QA no alvo e no controle, conservando as referências de regressão.

Caso de 10/10/2026: faltava scikit-learn no `.venv-sa` da VPS. O detector de
detalhes retornava erro e o inventário o tratava como ausência de detalhes.
A dependência foi instalada e essa falha passou a bloquear o gate. Na nova
rodada do 14_PAV, o detalhe original P26/P27 foi consumido e conferido; quatro
ocorrências indevidas de nível do contorno ampliado foram removidas. Isso
valida essa correção, sem aprovar as demais pendências ou a publicação.
