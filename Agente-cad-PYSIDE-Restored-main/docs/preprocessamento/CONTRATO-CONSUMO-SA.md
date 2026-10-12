# Contrato de consumo assistido pelo SA

**Leitura temporal:** as seções abaixo conservam estados datados de implantação.
Para o consumo de níveis atualmente comprovado, consultar a atualização de
09/10/2026 ao final; `consumed` sozinho não comprova todos os campos do pacote.

Data: 2026-09-22. Estado inicial: investigação P26. Atualização de 2026-09-23
ao final deste documento registra a integração habilitada e seus limites.

## Resultado da inspeção

O headless canônico inicializa `runner.pavimento_preprocess` somente com obra,
pavimento e mapas vazios. A leitura pesada monta pilares, lajes, níveis e vigas
antes de construir `PreValidationDialog`. O arquivo legado de convenção é passado
ao diálogo depois dessa etapa. Portanto, apenas gravar um pacote JSON novo não faz
o SA consumi-lo.

O cache `_fast_context_cache_path()` é derivado do DXF e de versões de arquivos do
motor. A revisão de um contexto externo ainda não faz parte da chave. Ativar o
consumo sem corrigir essa dependência permitiria reaproveitar uma interpretação
antiga após novo pré-processamento.

Rechecagem após a integração local do botão (2026-09-22):
`scripts/arete/headless_sa_analise.py` inicializa `pavimento_preprocess` com
`convention={}` antes de `_fast_context_cache_path(dxf_path)`; o caminho rápido
pode restaurar `pavimento_pillar_report` e `pavimento_nivel_report` do pickle.
Depois, `_build_fast_pre_validation_dialog` e o fluxo completo criam
`PreValidationDialog(..., convention={}, convention_file=<json legado da obra>)`.
O runner do portal invoca o módulo com `--persist-db --wait` e não oferece
argumento de pacote contextual. Logo, não há entrada segura já comprovada para
injetar o pacote novo antes das decisões sem editar o headless/diálogo ou
sobrescrever o JSON legado. O botão local executa inventário parcial real,
mas **não** alimenta SA nesta revisão.

## Interface mínima, sem mudar o schema N1

O adapter futuro deve atuar na orquestração do headless:

1. Resolver obra, pavimento, recorte de torre e revisão antes de iniciar o processo.
2. Selecionar um pacote `complete`/`partial` compatível e sem conflito no campo usado.
3. Passar um caminho/manifesto explícito ao subprocesso; nunca sobrescrever o JSON
   global legado para simular integração.
4. Carregar o contexto antes das decisões que ele pode assistir.
5. Registrar `context_run_id`, hash e revisão no manifesto SA.
6. Incluir esse hash na chave do cache ou desabilitar o cache para essa rodada.
7. Ausência, conflito ou revisão incompatível preserva o comportamento atual.

## Matriz inicial de consumo

| Fato contextual | Destino candidato | Regra de segurança | Estado |
|---|---|---|---|
| termo/símbolo de convenção de pilar | mapa de convenção usado para classificar hatch | fonte vinculada e revisão atual; conflito não decide | interface a provar |
| referência/faixa de níveis | contexto de inferência de lajes | unidade e datum explícitos; zero é válido | interface a provar |
| corte ligado a viga/lajes | suporte à inferência de nível e vínculo | chamada e seção separadas; vínculo geométrico comprovado | interface a provar |
| inventário candidato por torre | comparação de cobertura | consultivo; não cria/exclui N1 | possível sem mutação |
| conflito/ambiguidade | diagnóstico da rodada | nunca preencher campo automaticamente | possível sem mutação |

## Fora do contrato desta etapa

- Alterar schema N1, geradores ou motores.
- Produzir N3/N5 no pré-processamento.
- Usar RAG/ML como dependência operacional.
- Promover hipótese ou resultado automático a conhecimento global.
- Consumir contexto por nome de item sem identidade de obra/pavimento/torre/revisão.

## Gate para P27

P27 somente pode começar após um teste isolado provar um ponto de entrada anterior
à decisão assistida e demonstrar que contexto ausente é semanticamente idêntico ao
fluxo atual. Enquanto isso, o pacote e o botão podem ser construídos, mas o recurso
não pode ser anunciado como “usado pelo SA”.

Interface mínima proposta para uma decisão futura: parâmetro opcional de
manifesto contextual no entry point canônico, lido antes da construção do
contexto, com hash na chave de cache e proveniência no manifesto SA. A ausência
do parâmetro deve preservar o comportamento anterior; uma mudança no núcleo
exige prova A/B antes de habilitar a flag de consumo.

## Atualização 2026-09-23 — prova e restrição de campo

O entry point opcional foi implementado com `--context-manifest` e
`--context-hash`. A fonte e o projeto são conferidos antes da análise; o cache
N1 é desligado na rodada contextual; o manifesto registra as chamadas reais do
classificador. Sem manifesto, continua a leitura anterior. O portal mantém
`PORTAL_PREPROCESS_SA_ENABLED=0` por padrão.

O consumidor comprovado é `MainWindow._classify_pillar_hatch`, alcançado pelo
headless antes de montar o relatório de pilares. Tradução suportada:
assinatura e termo textual extraídos da mesma legenda validada →
`pavimento_preprocess.convention[termo].sig/label` → `classification` do pilar.
Nenhum nível é traduzido sem unidade/datum; cortes sem vínculo continuam
consultivos. A evidência por item inclui assinatura, termo devolvido, chave do
relatório, source_id, handles e hash/run da entrada.

O A/B do 14_PAV mostrou que `NASCE` também aciona `ignore_in_beams` no SA e
altera dimensões/vínculos de vigas. Isso ultrapassa o campo autorizado nesta
fase. O adapter mantém `NASCE` no pacote, mas não o entrega ao classificador
até haver regressão N3/N5. Com `SEGUE`/`MORRE`, o A/B mudou apenas classificações
e descrições correspondentes em lajes; o conteúdo de vigas permaneceu igual
exceto IDs temporários não determinísticos. A publicação segue condicionada ao
microciclo headless completo e ao gate estrutural descrito no status de 23/09.

## Estado publicado em 2026-09-23

As flags independentes `PORTAL_PREPROCESS_ENABLED=1` e
`PORTAL_PREPROCESS_SA_ENABLED=1` estão ativas na VPS. A entrada contextual
continua opcional, fixada por obra/pavimento/torre/revisão/hash antes do
subprocesso; rodadas sem contexto preservam o caminho anterior. Em cópia
isolada do 13_PAV, a rodada headless Linux após a publicação registrou
`status=consumed`, 230 chamadas reais e 30 evidências coincidentes em 32 itens,
com N3 PARA/PASSA 2/2. Duas classificações permaneceram indeterminadas; o
manifesto não as apresenta como consumos coincidentes. `NASCE` segue suspenso
por alterar vínculos de vigas no A/B, e níveis sem unidade/datum não são
injetados. O 14_PAV produtivo ainda não foi pré-processado para teste.
Uma cópia isolada dos recortes validados do próprio 14_PAV foi executada na
VPS após a publicação: pré-processamento 1/1 torre, contexto fixado e headless
com `status=consumed`, 89 chamadas e 24 evidências coincidentes.

## Inventário de níveis v3

O pacote por torre inclui `level_inventory` com referência direta do DXF
bruto, listagem de todas as classes e segmentos candidatos de fundo de viga.
Fatos de laje exigem texto próximo a um rótulo único e referência de unidade
e datum; proximidade de laje a pilar/viga é apenas alternativa consultiva.
O endpoint web expõe esse inventário sem depender de recorte aprovado de
níveis. O consumidor SA atual **não aplica** esses níveis aos campos N1; a
prova de `preprocess_context.status=consumed` se refere à convenção de
pilares. Uma futura aplicação de níveis exige vínculo estrutural por item e
segmento, além de A/B N1–N5 antes de ativação.

No 14_PAV, a referência direta do DXF bruto (base 852,19 m, topo 855,25 m,
altura 3,06 m) também é consumida pelo contrato geral de altura do pavimento
do PL/N3. O resolver só entrega essa referência quando fonte, revisão, escopo,
unidade e altura são válidos. Isso não atribui cotas individuais aos pilares,
lajes, vigas ou segmentos no N1. O SA produtivo de 23/09/2026 registrou o
contexto `consumed` e gerou PL 70/70 após essa integração.


## Níveis regionais em lajes com degraus (2026-10-01)

A Convenção preserva fatos derivados `slab_region_level` com `region_geometry` GeoJSON e `region_id`. A região principal exclui as regiões internas; cotas internas não certificam todo o contorno. A face do pilar consulta geometricamente cada região e adota o maior nível de contato. Regiões sem nível escopado não recebem a cota escalar da laje. Esses fatos não substituem o schema N1 nem validam automaticamente campos humanos.

Estimativas entre segmentos da mesma viga seguem D-61: somente fontes independentes e concordantes, com `source_fact_ids`, fator de confiança e estado `estimated` preservado em FV, fundo físico, match espacial LV e contatos do pilar. Estimativa não vira evidência medida por transferência. QA: `scripts/arete/relatorios/20261001-niveis-regioes-degraus/RELATORIO.md`.

Decisões humanas sobre fundo contínuo podem ser preservadas no arquivo derivado adjacente `<recorte>.slab-region-review.json`. O coletor exige SHA-256 correspondente ao DXF e identificação explícita da região e decisão; não aplica a regra a outras revisões ou regiões. Uma decisão contraditória com cota CAD direta fica em `review_conflict` e não sobrescreve a cota.

Para lajes sem cota, a relação entre abas de um corte horizontal pode fornecer diferença relativa em centímetros mesmo com haste interrompida. O resolver exige contato geométrico com uma região de cota conhecida e espessuras correspondentes nas duas abas em três estações. A associação textual a uma laje próxima não basta. L317 foi resolvida por L316/BD4: 852,16 m + 3 cm = 852,19 m, confiança 85,5%. Essa inferência pertence ao pacote derivado de pré-processamento; não equivale à validação humana do N1.


### Consolidação de níveis — 2026-10-01

Regra integrada: `docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md` (canônico). O pacote pode coletar evidências SA necessárias antes da convenção. Registrar separadamente produção do fato e consumo real pelo SA. Cota regional derivada/QA não escreve aprovação N1. Ledger por segmento e grafo acíclico de fontes são obrigatórios; ver relatório de resolução L317 e D64 local.

### Cadeia da obra — 2026-10-08
A cadeia completa roda o inventário escopado antes do SA/N3, com recibo e duração próprios por pavimento. A revisão humana dos recortes é opcional; o estado real `validated` permanece nas fontes, e mudança de arquivo ou revisão durante a rodada impede o commit. Uma referência absoluta indisponível não bloqueia a coleta SA de geometrias, segmentos e cortes. O consumo de altura absoluta continua exigindo unidade, vínculo e referência direta coerente. Níveis desconhecidos não são preenchidos para completar a produção.

### Consumo de níveis com contorno final menor — 2026-10-09

Correção técnica comprovada de `portal/app/preprocessamento/sa_levels.py`, sem
nova decisão de projeto: uma laje interpretada pelo SA pode ter contorno menor
que o candidato pré-processado. Rejeitar o fato inteiro porque uma das posições
ficou fora descartava também a marca válida interna; conservar todas as posições
contaminaria a proveniência do campo efetivamente aplicado.

O pacote atual transporta `cad_marks` por marca, com handle original, posição e
valor. O consumidor seleciona as marcas do valor solicitado dentro do contorno
final, restringe posições e evidências CAD a essa seleção e conserva as
referências não CAD de origem. Sem marca válida interna, não aplica o nível.
Pacotes antigos sem `cad_marks` mantêm a exigência anterior de todas as posições
internas. Campos humanos protegidos não são substituídos. O carregador
`src/core/dxf_loader.py` conserva o handle do texto original, inclusive texto
transformado de bloco; a identidade não é retirada de uma cópia sem handle.

Prova de consumo exige manifesto escopado com hash/run da entrada, chamada real
por item/campo e valor/evidências do estado SA persistido. Quantidades do
inventário pré-SA e do estado SA podem diferir por topologia; não associar
segmentos por número igual nem tomar quantidade preenchida como aprovação.

Evidência datada e local da Obra_TREINO_1/14_PAV:
[relatório de produção](../../scripts/arete/relatorios/20261009_continuacao_niveis_14pav/RELATORIO.md).
O caso L401 preservou D8B interno e excluiu D7D externo; a primeira rodada
divergente e a segunda corrigida foram conservadas. Os 56 testes locais/VPS
incluem exclusão de marca externa, pacote sem marca interna, proteção humana e
identidade original do texto. Isso prova o reparo técnico e o consumo observado,
não valida todas as lajes/obras nem certifica N3/N5. Valores e handles desse caso
permanecem exemplos de auditoria, jamais constantes do motor ou regra global.

### Comparabilidade do recibo de cortes — inspeção 2026-10-09

`beam_section_crosscheck` deve ser lido com a origem de cada inventário:
`runner_sections` projeta o runner transitório; `collect_sections` sobre o estado
publicado percorre outro caminho. Comparar contagens desses caminhos não prova
sozinho perda de cortes ou erro físico. A chave atual inclui tipo, fingerprint,
semântica, âncora e desenho em coordenadas absolutas; mudança de âncora ou warning
pode impedir igualdade mesmo conservando o desenho relativo. Separar esses
componentes antes de decidir a causa; diferenças de datum/painel continuam
pendentes de prova local. `human_confirmation=pending` não certifica uma rodada.

Reconstrução somente leitura e diferenças ainda abertas:
[dossiê de cortes 14_PAV](../../scripts/arete/relatorios/20261009_continuacao_niveis_14pav/inspecao_cortes/RELATORIO.md).
Esta nota corrige a interpretação do diagnóstico, sem trocar o comparador,
reescrever o manifesto histórico ou aprovar cortes automaticamente.
