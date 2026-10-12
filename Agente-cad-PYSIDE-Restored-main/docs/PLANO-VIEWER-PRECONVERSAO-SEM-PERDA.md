# Plano de pré-conversão e desempenho do viewer

Data: 08/10/2026. Escopo: desenvolvimento e validação planejados; este documento não representa implementação ou aprovação nos gates.

## Objetivo e referência

Melhorar primeira abertura, retorno ao desenho, navegação entre classes/itens, carregamento dos destaques, zoom e arrasto, mantendo geometria, aparência e todas as funções existentes. A implementação será universal, sem condições por obra, pavimento ou item.

Referências: `PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md`, `QA-VISAO-EVIDENCIA-CANONICA.md` e `../scripts/arete/relatorios/20261008_viewer_three_cycles/RELATORIO.md`.

O desenho TIPO_TESTE tem 392.532 paths. Reabertura com DOM reusado levou aproximadamente 207 ms para inserção/configuração, mas a pintura continua lenta. O candidato de agrupamento chegou a 4.001 paths, porém alterou pixels nas sobreposições e foi rejeitado. Esses resultados são referência, não uma garantia de desempenho de outras obras.

## Contratos que devem permanecer

- DXF original e JSONs Fase-4 imutáveis. SA, pré-processamento, N3 e N5 continuam consumindo suas fontes atuais; não consomem o pacote de visualização.
- Vetores e coordenadas preservados, sem simplificação, quantização ou deduplicação de entidades. Sobreposições podem ter efeito visual: duplicatas não são descartáveis automaticamente.
- Pan/zoom exclusivamente por viewBox; mesma transformação para fundo, destaques, seleção e OSNAP. Preservar âncora no cursor, letterboxing, reset e duplo clique.
- Preservar textos, fontes, espessura, cores, transparência, ordem de pintura, tracejados, clipping, blocos e transformações.
- Criar: ocultar destaques, preservar OSNAP. Editar: mostrar apenas o destaque alvo e preservar OSNAP. Cancelar: restaurar seleção/destaques. Salvar mantém os contratos de persistência existentes.
- Todas as regiões do desenho continuam disponíveis. Entidade fora da tela não significa entidade apagada, ausente do índice ou excluída de análise.
- Fonte/revisão/permissão do usuário prevalecem sobre cache. Erro no derivado nunca invalida o DXF nem apresenta pacote de outro pavimento.

## Arquitetura proposta

Pré-conversão em pacote derivado, versionado e regenerável:

1. **Manifesto:** revisão da fonte e do conversor, transform DXF↔SVG, viewBox home, dependências, inventário, checksums, limites conservadores e ordem de pintura das unidades.
2. **Fragmentos SVG vetoriais:** unidades de pintura originais com seus atributos e dependências. O particionamento não concatena traços nem altera compositing. Inicialmente respeita grupos originais; subdivisão só após equivalência comprovada.
3. **Índice espacial de visualização:** relaciona unidades à região visível. Cada unidade tem identidade e proprietário únicos, mesmo que atravesse várias células.
4. **Índice geométrico independente para OSNAP:** dados precisos, sem depender dos elementos que estão montados no DOM. Processamento e consulta pesada em Worker; dados em Float64 quando binários forem úteis. Formato e precisão são validados por round-trip.
5. **Camada de destaques:** dados e desenho independentes do fundo. Seleção de classe/item não deve buscar ou reinterpretar o SVG estrutural.

Uma grade de regiões é um índice, não uma autorização para recortar qualquer traço. O primeiro protótipo seleciona unidades originais por limites e as monta na ordem global. Não duplica pintura nas bordas. Grupos cuja composição dependa de todos os filhos ficam indivisíveis. Elementos com limites não comprovados permanecem sempre ativos ou usam o viewer atual.

Se o conjunto visível tiver dependências ou composição que não possam ser preservadas, o fallback é a apresentação integral original. Reduzir o número de nós é consequência esperada, nunca critério superior à fidelidade.

## Etapas e gates de desenvolvimento

| Etapa | Trabalho | Critério para avançar |
|---|---|---|
| 0 — baseline | Instrumentar rede, servidor, parsing, primeira pintura, latência percebida, frames, memória e OSNAP; coletar corpus e câmeras reproduzíveis | Relatório da referência com hardware, navegador, rede e revisões identificados |
| 1 — pacote offline | Gerar manifesto/inventário e índices sem trocar o viewer; publicar cache atomically somente após integridade | Fonte inalterada; cobertura completa de unidades; checksums, revisão e transformação corretos; pacote incompleto rejeitado |
| 2 — OSNAP independente | Implementar leitura/consulta em Worker e comparar com geometria de referência; manter seleção em coordenadas DXF/SVG corretas | Sem perda de alvos/funções; sem arestas falsas entre subcaminhos; cruzes/T/projeções corretas; resposta sem bloquear interação |
| 3 — pintura regional | Ativar seleção espacial atrás de flag, mantendo SVG/viewBox e ordem original | Imagens equivalentes em todas as câmeras; nenhuma linha/texto ausente ou duplicada; nenhuma costura em fronteiras |
| 4 — integração | Aplicar à página real; desacoplar destaques; cancelar trabalho obsoleto; caches limitados; revisão e contexto consistentes | Matriz funcional completa passa, sem mistura entre documento/pavimento ou resultados atrasados |
| 5 — VPS e rollout | Benchmark e teste visual na VPS, inicialmente um pavimento; depois outro desenho; ampliar gradualmente | Ganho medido, qualidade aprovada, limites de memória/CPU atendidos e fallback exercitado |

Não começar por substituir todo o renderer. Validar pacote e OSNAP antes de tornar o DOM parcial a fonte de interação.

### Etapa 0: medição honesta

Separar tempo de fetch, tempo no backend, parsing/inserção, construção de overlay, pintura e resposta a input. `renderMs` atual do overlay não mede pintura. Registrar a sequência completa, não apenas timers curtos de JavaScript.

Usar 5 execuções por cenário, reportando mediana e pior execução; para latência de interação coletar no mínimo 100 eventos e p95. Separar primeira conversão, primeira abertura sem cache, abertura com cache e retorno na mesma página. Não manter abas gigantes de comparação abertas durante benchmark; comparar imagens em carregamentos isolados na mesma posição, sem colisão de IDs.

### Etapa 1: integridade, cache e produção

Chave por identidade/contexto, digest da fonte, versão do conversor, opções de render e transform. O caminho exibido não é chave suficiente. Escrita temporária + rename atômico, lock por revisão, deduplicação de solicitações e publicação do manifesto somente quando todos os componentes estiverem prontos.

Executar com concorrência limitada e sem competir agressivamente com jobs SA/N3/N5. Medir CPU/RAM/tempo de geração na VPS. Cache ausente não bloqueia permanentemente a página: renderer atual continua disponível. Fonte alterada durante conversão cancela/rejeita resultado da revisão antiga. Falha/corrupção gera log e regeneração controlada, sem reprocessar engenharia automaticamente.

Rotas mantêm autenticação/autorização por obra, cache privado e revalidação. Nunca servir um pacote memorizado antes de validar acesso. Defs, máscaras, clipping, gradientes, fontes, IDs e links entre fragmentos precisam de resolução inequívoca. Não usar dois SVGs com IDs conflitantes no mesmo documento.

### Etapa 2: OSNAP completo, independente da pintura

Inventariar as funções atuais: vértices/endpoints, projeção em segmento, interseções e T. Identificar explicitamente limites atuais de 60.000 alvos e 25.000 testes; não convertê-los em corte permanente do novo índice. Consulta espacial deve limitar trabalho local sem excluir regiões ou alvos arbitrariamente.

Cobrir caminhos absolutos/relativos, múltiplos M, fechamento Z, linhas/polilinhas, curvas/arcos usados pelo corpus, entidades transformadas e blocos. Evitar transformar curvas em cordas falsas. Definir a referência geométrica para cada tipo antes de implementar. Tipo ainda não suportado não é silenciosamente ignorado: bloquear ativação desse pacote ou usar fallback comprovado.

Tolerância de captura é em pixels de tela, convertida pela transformação real; tolerância numérica deriva da precisão/escala da fonte e não de arredondamento de apresentação. Preservar prioridade/desempate existentes e proximidade exata. Indexar toda a geometria necessária, mas consultar apenas a vizinhança do cursor. Interseções podem ser calculadas localmente quando necessário para evitar explosão quadrática, desde que a cobertura seja verificada.

Mensagens de Worker carregam revisão, documento e geração da câmera; respostas antigas são descartadas. Enquanto um índice necessário está indisponível, informar estado e impedir commit sem snap válido; não salvar pontos fingindo que OSNAP funcionou. Exercitar criação, edição, arrasto, Ortho F8, Enter, Esc e desfazer.

### Etapa 3: pintura, fronteiras e mudanças de câmera

#### Abertura com enquadramento próximo — pedido do dono

Ao abrir o estrutural limpo, iniciar com uma câmera mais próxima em uma região útil do desenho, carregando primeiro as unidades que intersectam esse enquadramento e uma margem de prefetch. Não iniciar obrigatoriamente com a planta inteira. Essa política deve ser universal e derivada da geometria/contexto, sem coordenadas fixas por obra ou pavimento.

Prioridade de enquadramento: item explicitamente solicitado e com geometria válida; câmera anterior válida do mesmo documento/revisão, quando houver; caso contrário, região estrutural de densidade útil encontrada pelo índice espacial. Evitar escolher apenas legenda, carimbo ou área vazia; validar a heurística no corpus. Limitar a aproximação para manter contexto e não recortar o item solicitado. Se não for possível escolher uma região confiável, usar o enquadramento integral atual.

Oferecer controle visível **Ver planta inteira**. Distinguir o enquadramento inicial próximo do home integral: reset/duplo clique mantém o contrato de restaurar a planta inteira. Retornar ao enquadramento inicial pode ser uma ação separada. Câmera salva só é reutilizada no mesmo documento/revisão e com viewport compatível ou reenquadramento calculado.

O ganho depende do pacote regional: aproximar somente o viewBox de um SVG integral não evita download/parsing de todos os paths e pode não melhorar a pintura. Comparar abertura integral e próxima em cache frio/quente, medindo bytes/unidades transferidos, nós ativos, primeira pintura íntegra e latência. Não considerar o zoom inicial uma otimização aprovada sem ganho observado e sem validação de contexto/qualidade.

Preservar OSNAP de toda a geometria necessária, inclusive unidades ainda não pintadas. Ao sair da região inicial, carregar as novas regiões sem linhas ausentes, duplicação ou saltos de câmera; aplicar os mesmos gates de fronteira e edição. Exibir um estado claro enquanto uma região necessária estiver carregando, sem sugerir que o restante do desenho não existe.

Limites espaciais precisam incluir curvas, textos/glifos, marcadores, traços e efeitos. Limites de endpoints não bastam para curvas. Traços non-scaling exigem margem dependente da câmera. Transformações e clipPaths fazem parte do cálculo; bounds não comprovados usam fallback conservador.

Preservar ordem global de pintura entre unidades selecionadas, incluindo transparência e grupos isolados. Não agrupar por região de forma que reordene entidades sobrepostas. Não pintar duas cópias de uma entidade atravessando células. Não substituir vetores por imagem ampliada.

Preparar novas unidades antes de confirmar a nova câmera/conjunto visível. Prefetch com margem e troca consistente devem impedir buracos ao arrastar rápido. Se a região necessária ainda não estiver pronta, manter uma apresentação íntegra, mostrar carregamento e recorrer ao caminho completo quando necessário; edição não usa conteúdo parcial como prova de ausência de geometria.

Limitar bytes/unidades residentes, com descarte de fragmentos distantes e possibilidade de recarga. Não conservar todos os fragmentos, clones e índices de documentos antigos indefinidamente. Sempre liberar handlers, Workers e requisições no fechamento/troca de contexto.

### Etapa 4: destaques e integração

Selecionar classe altera apenas overlay e painel correspondente; selecionar item enquadra pela mesma transformação do fundo. Cache de overlay é opcional e invalida por revisão dos dados, nomes/rótulos, classe, modo de edição e item alvo. Medir antes de adicionar cache: a construção atual de algumas classes já leva ~1 ms.

Preservar toggle de nomes, nenhuma/todas as classes disponíveis, picking, tags/conectores, convenções, criar, redesenhar, cancelar, salvar e atualização após mudança. Nada de reaproveitar dados antigos porque o SVG não mudou. Falhas em metadados/destaques devem mostrar estado explícito e permitir recuperação sem desmontar o fundo saudável.

## Matriz de validação

| Área | Casos obrigatórios | Evidência |
|---|---|---|
| Inventário | Origem→manifesto→fragmentos; duplicatas legítimas; fontes alteradas; pacote incompleto | Set-diff por unidade, checksums e relatório de dependências |
| Geometria | Coordenadas, ordem, transform, curvas, textos, clipping e precisão de serialização | Testes de round-trip e comparação da fonte canônica |
| Visual | Home e múltiplos zooms, regiões superior/centro/inferior, fronteiras, sobreposições, tracejados, fontes e margens | PNGs isolados mesma câmera/viewport/DPR; diff/heatmap e inspeção visual |
| Navegação | Wheel ancorado, pan, reset/dblclick, zoom no item, resize/letterboxing, pan rápido que cruza regiões | Estado da câmera, alinhamento dual e capturas/sequências |
| Abertura próxima | Item solicitado, câmera anterior válida, seleção automática de região útil, fonte/revisão diferente, desenho vazio e fallback; Ver planta inteira e reset | Região inicial com contexto, nenhum hardcode, comparação frio/quente e cobertura após sair da região |
| Destaques | Pilares, lajes, laterais Para/Passa, fundos, cortes quando disponíveis; nomes; itens com/sem geometria | Inventário por classe e testes de selecionar/ocultar/enquadrar |
| OSNAP | Endpoint, projeção, cruz/T, múltiplos M, curvas/blocos suportados, alvos fora da região inicial, fronteiras, zoom extremo | Coordenadas e alvos esperados; nenhum falso snap; tempos de consulta |
| Edição | Criar sem destaques, editar só alvo, cancelar/restaurar, Ortho, fechar/desfazer, salvar e recarregar | E2E em cópia de teste; persistência conferida; nenhuma alteração fictícia na produção |
| Contexto | Troca rápida de obra/pavimento/bruto/torre/detalhes; navegar e voltar; troca durante fetch/Worker | Revisão/documento exibidos corretos, respostas antigas descartadas |
| Falhas | Rede lenta/offline parcial, 403, cache corrompido, fragmento faltante, Worker interrompido, fonte trocada | Fallback, mensagens/logs e recuperação sem perda de edição |
| Recursos | Abrir/fechar/trocar 20 vezes, sessões longas, conversão simultânea a jobs reais | RAM/CPU, handlers/Workers/requests, ausência de crescimento contínuo |
| Engenharia | Hashes de DXF/JSON antes/depois; motores usam fontes originais | Nenhuma mudança de entrada ou schema do SA/N3/N5 |

Corpus inicial: TIPO_TESTE e 13_PAV; depois uma fonte distinta que exercite recursos ausentes desses dois. Incluir fixtures controladas para curvas, transformações, transparência, clipping e entidades cruzando fronteiras. Não declarar universalidade apenas porque dois pavimentos passaram.

## Gates de qualidade e desempenho

Qualidade é bloqueante, desempenho é otimizado depois:

- Nenhuma unidade estrutural omitida, simplificada ou duplicada na região visível. Fonte e ordem preservadas.
- No primeiro protótipo, exigir igualdade de pixels na mesma configuração de render. Qualquer diferença passa por diagnóstico; não elevar tolerância para aprovar o candidato. Exceções de antialiasing entre configurações diferentes não justificam perda no mesmo navegador/câmera.
- Nenhuma regressão funcional ou de persistência. OSNAP não perde alvos por limites arbitrários ou por DOM parcial.
- Comparação de câmera/picking/snap em coordenadas de fonte; erro permitido não excede a precisão documentada da fonte/referência.
- Fallback e recuperação exercitados, sem abrir acesso nem misturar contextos.

Metas iniciais, a confirmar com baseline e hardware identificado — não promessas:

| Métrica | Meta |
|---|---|
| Frame durante pan/zoom, conteúdo já carregado | p95 ≤ 33 ms; ideal ≤ 16,7 ms |
| Resposta visual a seleção de classe/item | p95 ≤ 100 ms, separando event→paint de fetch |
| Consulta OSNAP local após índice pronto | p95 ≤ 16 ms, sem travar thread principal |
| Abertura com pacote pronto | Desenho útil e íntegro em ≤ 2 s na rede/hardware de referência |
| Memória em navegação repetida | Estabiliza após descarte; sem crescimento contínuo em 20 trocas |

Se as metas não forem atingidas, relatar valores e gargalo restante. Não atribuir nota 9/10 com base somente em parsing, nem usar a ausência de timeouts como prova de fluidez.

## Três rodadas de validação da implementação

1. **Offline:** pacote, integridade, geometria, comparação PNG e OSNAP contra referência. Corrigir causas antes da integração.
2. **Integrada:** página real com flag desligada/ligada, mesma sequência de câmeras/ações; matriz funcional e falhas; qualidade primeiro, depois comparação de performance.
3. **VPS:** um pavimento, outro corpus e sessão prolongada; medir browser e servidor; registrar evidências e ampliar apenas onde os gates passaram.

Cada rodada produz `RELATORIO.md`, versão/configuração, inventário, métricas, imagens/diffs, falhas e próximo passo. Flag permite retornar ao renderer existente sem restaurar código antigo ou remover dados. Antes de restart/deploy, conferir jobs ativos; aplicar patches contextualizados e preservar mudanças concorrentes. Depois do deploy, repetir smoke funcional e visual no portal do dono.

## Ordem prática de implementação

### Hatches, sólidos e expansão de tipos de linha

Inventariar a entidade de origem antes de escolher uma conversão. HATCH sólido deve permanecer preenchimento vetorial composto, com contornos, ilhas/vazios, curvas, OCS, clipping, transparência e ordem de pintura. Não converter padrões de pontos/traços em sólido só porque parecem densos na visão geral. SOLID e preenchimentos existentes também não podem virar malha de pontos.

Medir separadamente HATCH, SOLID, padrões de linha e geometrias já explodidas no DXF. A pré-conversão fica apenas no derivado do viewer; DXF, geometria do motor e alvos de OSNAP não mudam. Testar fixtures de sólido com vazio, padrões pontilhados e tracejados, escala/rotação e sobreposição. Exigir a mesma comparação de pixels em vários zooms. Representação SVG compacta de padrões só é promovida quando mantém fase, espessura, limites e aparência; falha visual conserva os fragmentos originais.

Diagnóstico de 08/10/2026: a cópia read-only da torre TIPO_TESTE (SHA `80b45ff3e024ebe037fe6e6e52829216120f006c55f6b60f79adb1df2dc65641`) tem 498 SOLID e zero HATCH. O tipo de linha nomeado CONTINUOUS contém o padrão `(0.8,0.2,0.2,0.2,0.2,0.2)` no próprio arquivo; a linha 73BA é expandida em 5.200 segmentos. Portanto a ausência de HATCH nesse corpus não certifica outros arquivos nem justifica converter suas linhas em contínuas. Perfil reproduzível: `scripts/arete/relatorios/20261008_viewer_regional/profile_hatches.py` e `hatch_tipo.json`. O renderer atual usa preenchimento vetorial para HATCH sólido, com detecção de vazios; os padrões são emitidos como linhas/pontos.

Primeiro entregar baseline + pacote offline + prova de integridade. Em seguida OSNAP independente com consultas espaciais. Só então validar pintura regional em protótipo e integrar ao portal. Compactação de tracejados/agrupamento permanece investigação separada e não é requisito para publicar as etapas seguras.

O desenvolvimento só se considera encerrado quando a matriz funcional, a fidelidade visual e a recuperação passaram, e o ganho foi medido no portal da VPS. Este plano autoriza a organização do trabalho; não afirma que esses resultados já foram obtidos.
