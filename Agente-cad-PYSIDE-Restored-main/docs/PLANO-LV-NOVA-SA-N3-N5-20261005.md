# Laterais NOVA — integração do design aprovado ao SA → N3 → N5

Data: 2026-10-05. Escopo: Laterais Para e Laterais Passa, somente Modo NOVA; duas montagens independentes, gradeadas e sarrafeadas. Design experimental aprovado explicitamente pelo dono nesta data. N3 e quatro N5 publicados em 06/10/2026; auditoria técnica completa, inspeção visual por amostragem e aprovação humana pendente.

## Entregas obrigatórias e acompanhamento

Estado atual em 06/10/2026, 12:12 UTC: geração N3 e quatro N5 na VPS concluída, resultados acessíveis em Unificados, inventários e DXFs auditados integralmente; Base Global/RAG publicado com oito regras T1 e zero vetores ausentes. Inspeção visual por amostragem; aprovação humana N5 pendente. A tabela e anotações cronológicas abaixo preservam o histórico de execução; o resultado publicado ao final deste plano é o estado vigente.

Complemento solicitado pelo dono: integração, atualização dos índices RAG/Base Global e documentação das laterais fazem parte da entrega, não são tarefas opcionais posteriores.

| Entrega | Trabalho obrigatório | Prova de conclusão | Estado |
|---|---|---|---|
| Integração N3 | AB e Visão Corte dinâmicos a partir do SA, nas duas montagens e em Para/Passa; mesmos caminhos no pipeline, ficha e exportação | Comparação com DXFs aprovados, regressões e geração efetiva no portal | Renderer integrado localmente; 22 referências reproduzidas e V301 regenerada; inventário completo e portal pendentes |
| Integração N5 | Consumir N3 correntes de cada montagem, aplicar molduras, índice, ordem, paginação e entidades editáveis | Inventário completo, índice confrontado com folhas e DXFs publicados conferidos | Montagem, despacho e seleção das quatro variantes testados localmente; cadastro do índice LV e validação VPS pendentes |
| Documentos LV | Consolidar padrão aprovado e harmonizar manuais, contratos, semântica, proveniência e referências N3 | Matriz regra → fonte vigente → implementação → teste/evidência, com regras substituídas identificadas | Especificação, precedência em seis documentos e matriz de implementação atualizadas; publicação pendente |
| Base Global | Atualizar fontes canônicas, mapa, inventário de fontes e grafo; publicar conteúdo correspondente no portal | Fontes rastreáveis e conteúdo NOVA/LV acessível na Base Global publicada | Mapa, decisões e grafo locais atualizados; publicação pendente |
| RAG e índices | Atualizar regras no RAG ativo e reconstruir índices textual/semântico derivados das fontes harmonizadas | Build registrado, avaliação de recuperação e consultas de regras aprovadas sem contradição | Sete regras T1 atualizadas sem duplicação; último build 6693 chunks/292 fontes; 30 consultas, hit@5 híbrido 97%; publicação pendente |

Atualização em 2026-10-06: N5 automático LV/NOVA requer montagem e comportamento explícitos, consulta o inventário da rodada N3 corrente e falha se uma unidade estiver ausente. Job N5 prepara os quatro artefatos Para/Passa × gradeadas/sarrafeadas; não certifica o job se qualquer variante falhar. O experimento V301 usa o índice PL explicitamente apenas para testar encaixe geométrico local, sem apresentá-lo como índice LV publicado. Na VPS foram encontradas molduras LV iguais à moldura aprovada, mas nenhum índice LV cadastrado. A publicação inicial de 21 arquivos foi concluída após confirmar fila vazia, comparar drift e salvar backup; o serviço foi reiniciado. Isso não sela geração E2E. Conhecimento e RAG ainda aguardam publicação.

Documentos a revisar e atualizar conforme seu escopo:

- `docs/SA-ANALISE/CLASSES/LV.md`: manual e distinção gradeado/sarrafeado, Para/Passa, AB/cortes.
- `docs/CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md`: contrato executivo, fronteiras das origens e determinismo do desenho.
- `docs/SEMANTICA-VIGA-NOVA.md` e `docs/PROVENIENCIA-CAMPOS-LV.md`: significado, unidades e origem dos campos consumidos pelo N3, sem alterar regras FV alheias ao escopo.
- `docs/MASTERPLAN-ARETE-LATERAL-VIGA.md` e `docs/LV-COMPREENDER-INTERPRETACAO-FICHAS-N2-N4.md`: alinhar referências aplicáveis ao padrão aprovado, preservando a independência N2/N4.
- `docs/CONHECIMENTO/DECISOES-DO-DONO.md` e `MAPA-DO-CONHECIMENTO.md`: aprovação, precedência e ligação à especificação única LV NOVA a criar.
- Referências de desenho N3 e configurações NOVA/LV_PARA e NOVA/LV_PASSA: indicar os exemplares aprovados e as regras realmente implementadas.

Após harmonizar as fontes: atualizar inventário/curadoria, regras elegíveis do RAG ativo, executar `kb_build.py`, `kb_grafo.py` e `kb_eval.py`, conferir consultas por `kb_query.py` e publicar os derivados correspondentes na VPS. Repetir atualização incremental se testes e integração exigirem correções documentais. Documentos históricos mantêm seu caráter histórico e recebem ponteiro para a regra vigente quando necessário; não são reescritos como fonte atual.

## Resultado exigido

A geração normal pelo portal deve produzir AB e Visão Corte com o mesmo padrão dos DXFs aprovados, calculados dos dados locais do SA. Produzir e conservar ambas as montagens, independentemente da opção selecionada no painel esquerdo. A opção seleciona a visualização e a saída solicitada, sem substituir ou apagar a outra montagem. Para/Passa continuam com contratos e configurações independentes, utilizando as mesmas regras visuais NOVA.

N5 precisa consolidar exclusivamente esses N3 atuais, em molduras e índice NOVA, mantendo entidades CAD editáveis, conteúdo completo, ordem verificável e segregação das montagens. A aprovação do experimento não comprova implementação nem publicação.

## Diagnóstico inicial confirmado no código

- `src/core/vigas_drawing_config.py`: contratos gradeados/sarrafeados independentes; `prepare_lv_sources` correlaciona A/B por sobreposição física, não por igualdade do índice do segmento. Não substituir perfis locais por máximos globais.
- `portal/app/lv_n3_operations.py`: fichas e ajustes isolados por montagem. Preservar esse isolamento e a imutabilidade da origem SA.
- `portal/app/lv_n3_panels.py` e `lv_n3_cuts.py`: resolução/cache separados por montagem, modo, comportamento e contrato. AB chama `generate_local_panels`; cortes chamam `generate`, em `scripts/arete/lv_n3_cut_draw.py`.
- O hash atual inclui o renderer e configurações. Se a implementação for extraída para novos módulos, incluir também as dependências e versão do padrão no fingerprint para impedir reaproveitamento de DXF antigo.
- `src/core/n5_assembler.py`: o caminho específico de molduras NOVA contempla PL/FV; LV permanece no empacotamento genérico. O inventário autoritativo e a seleção dos artefatos dual precisam ser verificados e integrados para LV.
- Existem testes de contratos, aberturas, cortes, variantes dual e N5. Existência de testes não significa que a nova integração passou neles.

## 1. Congelar a referência aprovada e inventariar a execução

1. Preservar originais e todas as versões experimentais. Criar manifesto com caminho, SHA-256, variante, caso e aprovação:
   - AB: `scripts/arete/relatorios/20261004_nova_lv_design_experimentos/dual_v20/{gradeadas,sarrafeadas}/AB01..06.dxf`;
   - Visão Corte gradeada: `dual_v11/gradeadas/VC01..05.dxf`;
   - Visão Corte sarrafeada: `dual_v13/sarrafeadas/VC01..05.dxf`.
2. Congelar os PNGs correspondentes e contratos sintéticos dos casos. Não elevar scripts sucessivos de substituição textual a motor de produção; usá-los como evidência das regras.
3. Inventariar estado SA corrente do 13_PAV, vigas, comportamentos Para/Passa, faces, segmentos, perfis de corte, aberturas e pendências. Contagens derivadas do inventário vivo, nunca dos números históricos da sessão.
4. Conferir jobs ativos e propriedade de arquivos compartilhados antes de alterar UI ou publicar. Não interromper jobs de outros agentes.
5. Inventariar molduras, índices, legendas e recortes cadastrados em NOVA/LV_PARA e NOVA/LV_PASSA, inclusive múltiplos arquivos e área útil. Não usar cadastro PL/FV como substituto silencioso.

Saída: manifesto do padrão aprovado + baseline SA/artefatos/configurações + lista de lacunas. Não alterar motores nesta fase.

## 2. Consolidar e harmonizar conhecimento global e RAG

1. Produzir uma especificação canônica única do padrão LV NOVA, vinculada ao manual LV, contrato rígido N3/N4, decisões do dono e mapa do conhecimento.
2. Reunir as regras da sessão com dimensões, layers/cores, hachuras reais, famílias de ferragens, cotas, textos, encontros e alcance de cada regra. Distinguir dimensão física, escala visual e posição de anotação.
3. Resolver divergências por decisão mais recente, preservando histórico com indicação explícita de revogação/substituição. Exemplos importantes:
   - ausência de vertical nas emendas vale para sarrafeados comuns, não para gradeados;
   - continuação sarrafeada após abertura recebe vertical esquerda de 7 cm;
   - topo 2,2 somente gradeado; sem travessa 2,2 no fundo;
   - abertura de pilar conserva sarrafo superior de 7 em ambas as montagens;
   - fechamento verde 3,5 da abertura de pilar somente gradeado;
   - corte sarrafeado sem parafusos nem madeiras remanescentes desses conjuntos.
4. Incluir regras aprovadas e exemplos mínimos:
   - painéis até 244: único, inclusive abaixo de 60; acima de 244: nenhum painel abaixo de 60; sobra curta redistribuída em 122 + restante;
   - gradeado: meios pontaletes 3,5 verdes nas emendas e posição das extremidades medida na referência; madeira 7 e 2,2 laranja;
   - quantidade de pontaletes por painel = inteiro mais próximo do comprimento útil/30, descontando união das aberturas; texto somente gradeado;
   - aberturas conectadas ao vazio da laje e continuidade dos vazios entre segmentos;
   - jambas e encontros das aberturas respeitam a face inferior da travessa 2,2 nos gradeados;
   - sarrafeado: aberturas com madeira 7 completa e fechamentos; vertical da extremidade de fundo a topo;
   - cotas, patinhas, letras, ferragens e hachuras dos cortes conforme exemplares aprovados; C elevada 1 cm;
   - limites de geometria do painel e ausência de componentes espúrios/duplicados.
5. Alinhar as descrições e valores das configurações NOVA/LV_PARA e LV_PASSA com o desenho executado; preservar configurações independentes e alterações deliberadas do usuário. Não aplicar padrão a outros modos/classes.
6. Atualizar inventário/curadoria e referências de desenho N3. Registrar regras T1 no RAG ativo segundo seu contrato, sem copiar instâncias de obra como regra global nem usar N2/N4 para preencher SA.
7. Executar `scripts/kb/kb_build.py`, `kb_grafo.py` e `kb_eval.py`; conferir recuperação por `kb_query.py` das regras novas e ausência de contradição nas respostas. Publicar fontes e índice derivados pertinentes na VPS. Não atualizar FAISS, LanceDB ou ByteRover legados.

Saída: especificação harmonizada, trilha de decisões, índice/RAG recuperável e evidências de consultas. A aprovação do dono é fonte; similaridade do RAG não é prova geométrica.

## 3. Contratos dinâmicos a partir do SA

1. Mapear cada campo necessário para sua origem: comprimento local, direção, lado A/B, altura local, largura, datum/nível, lajes por lado, espessuras/rebaixos, invertidas, aberturas de viga/pilar e continuidade.
2. Calcular divisão de painéis e atribuir aberturas às interseções corretas. Não alterar JSONs originais Fase-4 nem schema N1; gerar contratos derivados novos.
3. Resolver perfis locais e correspondência espacial A/B. Segmentar mudanças reais de altura/lajes; não inventar geometria quando houver ambiguidade.
4. Criar ambos os contratos de fabricação a partir da mesma origem SA, com namespace de montagem. Ajustes de uma variante não podem contaminar a outra.
5. Definir identidade estável por obra/pavimento/torre/Para-Passa/viga/lado/segmento ou perfil/modo/montagem, com hashes de origem, regras e configurações.
6. Dados essenciais ausentes geram pendência explícita com campo e unidade; não omitir silenciosamente o item nem completar usando N4/referência humana.

Saída: contratos executivos rastreáveis e inventário esperado por montagem, antes do desenho.

## 4. Integrar os desenhos AB e Visão Corte no N3

1. Com base em causas comprovadas e gates aplicáveis, extrair geometria e estilo do padrão aprovado para funções gerais NOVA, alimentadas pelos contratos. Eliminar coordenadas fixas de fixtures e dimensões particulares dos exemplos.
2. Implementar AB gradeado e sarrafeado: divisão, rails/montantes, tipos de aberturas, vazios unidos, encontros, continuidades, hachuras, nomes, cotas e textos de pontaletes.
3. Implementar Visão Corte das duas montagens: perfis de lajes e compensados, madeira realmente necessária, grades, garfos, ferragens corretas, letras, cotas alinhadas e guia cinza pontilhada do nome.
4. Reutilizar as entidades CAD/hachuras/blocos aprovados como definição de estilo; produzir linhas e objetos reais. Não rasterizar o N3 nem transplantar a geometria fixa do exemplo para uma viga.
5. Conectar a implementação aos consumidores efetivos: visualização por segmento, todos os segmentos, inventário de cortes, execução do pipeline e exportação. Todos devem chamar o mesmo caminho de geração.
6. Atualizar fingerprints/cache para que a geração use o novo padrão e nenhum preview antigo apareça com etiqueta nova.

Gate N3: gerar os mesmos contratos sintéticos pelo caminho real do motor, comparar com DXFs aprovados após normalização de handles/origem, conferir entidades, layers, medidas, hachuras, cotas e PNG. Executar regressão golden pertinente e testes existentes de LV. Falha impede afirmar integração concluída.

## 5. Testes geométricos e visuais

Matriz mínima em ambas as montagens e nos contratos Para/Passa:

- AB longo 640 cm; abertura esquerda; abertura direita; abertura direita com segmento seguinte; dois segmentos sem abertura; abertura de pilar.
- Limites de divisão: menor que 60, 244, 244 + sobra curta, 260, 300, 304, 500, 640; soma preservada e máximo 244.
- Aberturas atravessando emendas, chegando à ponta e sobrepostas: desconto único, limite do painel e continuidade de vazios.
- Cinco cortes aprovados: dimensões distintas, desníveis, duas lajes no mesmo lado, lado sem laje e invertida.
- Alturas maiores: nenhum sarrafo extra de parafuso no sarrafeado; distribuição e ferragens gradeadas coerentes com o perfil.
- Letras/textos/cotas legíveis; patinhas nos pontos aprovados; nenhuma mudança indevida de cor, escala ou espessura.
- Isolamento dos ajustes gradeados/sarrafeados e imutabilidade das fontes SA.

Depois dos fixtures, gerar um lote pequeno real incluindo V301 e casos SA disponíveis com alturas/aberturas distintas; em seguida todo o inventário LV do 13_PAV. Casos não existentes no pavimento ficam cobertos pelo conjunto sintético, sem fabricar SA de produção.

Saída: ledger por unidade com esperado/gerado/pendente, set-diff, auditoria DXF, comparação geométrica e PNG completo + detalhes. Quantidade correta sozinha não prova design correto.

## 6. Integração N5 NOVA para ambas as montagens

1. Fazer o N5 consumir manifesto dos N3 correntes por montagem e comportamento, não glob de previews históricos nem geração paralela com outro estilo.
2. Produzir saídas segregadas gradeadas/sarrafeadas e Para/Passa, identificadas no nome, manifesto, seleção e download; evitar sobrescrita e mistura de contratos.
3. Medir área útil e escala das molduras LV cadastradas. Encaixar AB e cortes mantendo proporção, cotas e espaços; elementos grandes exigem divisão lógica/folha adicional, não redução arbitrária que modifique medidas ou esconda itens.
4. Ordenar naturalmente por viga e sequência de segmentos/perfis; deixar associação A/B/corte e continuidades explícita. Ordem esquerda → direita e topo → baixo dentro das folhas e conjunto de molduras em quatro colunas, conforme convenção NOVA e cadastro LV.
5. Preencher índice a partir das folhas reais, usando as seis folhas iniciais do modelo cadastrado. Se uma seção do índice transbordar, inserir sua continuação imediatamente e deslocar as seguintes antes de numerar. Recalcular referências de página depois do encaixe completo.
6. Número de página progressivo, cliente da obra ou NÃO INFORMADO, obra, pavimento, projeto e revisão 00 em todos os locais correspondentes do cadastro, inclusive capa/índice.
7. Preservar entidades individuais: nenhum IMAGE/PDFUNDERLAY como desenho; blocos estruturais de agrupamento não podem transformar a folha inteira em objeto único. Conferir edição das linhas, textos, hachuras e ferragens no DXF final.
8. Confirmar completude por entidade/unidade: cada segmento A/B e cada perfil de corte necessário aparece na saída da montagem correspondente; repetição só por regra identificada, não importação duplicada. Índice não pode apontar item ausente.

Gate N5: comparação N3 de origem × geometria consolidada após transformação declarada, caixas dentro da área útil, textos legíveis, índice e paginação consistentes, zero unidades ausentes ou extras sem justificativa. Validar as duas montagens e ambos os comportamentos.

## 7. Publicação e validação pelo portal da VPS

1. Antes do deploy, conferir jobs e alterações concorrentes, preservar artefatos existentes e limitar mudança a LV NOVA e infraestrutura estritamente necessária.
2. Publicar código, configurações harmonizadas, fontes/índice da KB e recursos aprovados. Confirmar versão/hash executado na VPS.
3. Executar pelo portal N3 de todas as laterais do 13_PAV, materializando AB e cortes em ambas as montagens. Não considerar sucesso apenas a conclusão do job: conferir contratos e arquivos efetivos.
4. Abrir N3 real nas duas subabas, por segmento e conjunto; verificar seleção esquerda, navegação e dados granulares independentes.
5. Executar N5 das duas montagens, conferir os downloads DXF, molduras, índice, numeração e conteúdo. Validar que o N5 deriva da rodada N3 atual.
6. Capturar PNG para avaliação agêntica e fornecer SVG para pan/zoom no portal. Registrar tempos e falhas; a seleção/navegação não pode reprocessar toda a obra desnecessariamente.
7. Conferir ausência de regressão em outros modos/classes e publicação incorreta de previews antigos.

Saída: relatório datado por unidade, hashes, versões, matriz SA → N3 → N5, evidências visuais e downloads. Bloqueios permanecem explícitos e impedem selo de entrega completa.

## Critério final de conclusão

- Design aprovado consolidado, fontes antigas harmonizadas e regras recuperáveis na KB/RAG atual.
- Contratos SA dinâmicos, rastreáveis, sem contaminação N2/N4.
- N3 AB e cortes equivalentes ao padrão aprovado, em ambas as montagens e Para/Passa.
- N5 completo, editável, segregado, corretamente encaixado e indexado.
- Regressões e gates aplicáveis aprovados; geração publicada executada e visualmente verificada pelo agente no portal.

Sequência: referência/inventário → conhecimento/contratos → motor N3 → testes locais → N5 → testes locais → publicação → geração portal → veredito final. Nenhuma nova aprovação de design é necessária para reproduzir as regras já aprovadas; convenção nova não resolvida recebe comparação concreta.

## Andamento verificado em 2026-10-06

- Base Global/RAG: publicação incremental de oito fontes e sete regras T1 concluída; vetores e grafo atualizados, preservando fontes de outros temas. Consultas LV canônicas recuperadas na VPS.
- Portal: geração N3 normal concluída após correção da propriedade de caches e dos contratos. Auditoria por unidade em andamento; N5 ainda sem certificação E2E.
- Partição derivada por perfil: publicada; 12 jobs normais do portal concluíram, cobrindo 24 DXFs V314/V318/V322, Para/Passa, A/B e ambas as montagens.
- Índice LV: proposta de seis folhas preservada separadamente, aguardando composição definida. Quatro saídas N5 ainda devem passar completude e validação visual publicada.

- Rodada N5 normal `6cbb5270-47f0-44d6-98f8-7a0b80305bf4`: recusada por ausência de índice LV_PARA cadastrado; nenhuma saída completa certificada.
- Filtro de nomes VF corrigido e corte invertido V330 corrigido/publicado. Rodada normal N3 `470c5e2d-824e-41ae-9e2a-cb7426c2e28d` concluída, sem falhas LV no manifesto.
- VF301: oito DXFs locais Para/Passa auditados, zero erros e comprimento preservado. A rodada contextual publicada já recuperou L317 corretamente; adaptador adicional permanece candidato local, sem necessidade comprovada de publicação.

### Validação adicional da rodada publicada

- Job normal `470c5e2d-824e-41ae-9e2a-cb7426c2e28d` concluído: manifesto registra 432 resultados LV e nenhuma falha LV; materialização portal de cortes registra 360/360. Isso ainda não certifica o N5 nem substitui inspeção visual por unidade.
- A nova rodada contextual já resolveu o contato L317/VF301: nível 852,19 no contrato atual e montagem A44/B59. A recuperação adicional de nível testada localmente permanece candidata, sem publicação necessária para esse resultado corrente.
- N5: corrigida identificação de unidades de fabricação. Partes diferentes de um mesmo segmento estrutural (V314.A S1 com montagens de 110 e 103 cm) devem permanecer; importação do mesmo arquivo nativo continua proibida.
- Publicação N5 com backup `lv_n5_unit_identity_20261006_044625`, proteção contra drift e fila ociosa. 14 testes LV e 43 testes de regressão do unificador/pilares passaram.
- Primeira medição das unidades correntes Para/gradeadas encontrou nove AB maiores que a área útil. Próxima implementação: distribuir os conjuntos longos em unidades de folha, preservando escala, medidas, aberturas, sequência, cotas e tratamento das extremidades; a quebra de folha não pode inventar sarrafos nem fechar um vão de continuidade.
- A composição do índice LV ainda precisa ser definida; proposta preservada separadamente. Não substituir cadastros de outra classe nem certificar quatro N5 enquanto índice e conjuntos longos não estiverem resolvidos.

- Auditoria nativa corrente: 912 unidades das quatro variantes, zero erros DXF; 227 por montagem Para e 229 por montagem Passa. Nove AB excedem a área útil em cada variante; distribuição entre folhas e índice LV continuam pendentes.


## Resultado publicado — 06/10/2026, 12:04 UTC

N3 normal concluído: `470c5e2d-824e-41ae-9e2a-cb7426c2e28d`. N5 normal concluído: `dee2a518-fa5c-42f1-83a6-dbda49e4a464`. Release beta `c8034783-e402-4edc-a4c2-ee5d0210b725` registrado a partir dos quatro arquivos efetivamente produzidos; aprovação humana permanece pendente.

| Resultado NOVA | Vigas | Unidades de origem | Colocações em folhas | Folhas |
|---|---:|---:|---:|---:|
| Para gradeadas | 36 | 227 | 241 | 36 |
| Para sarrafeadas | 36 | 227 | 241 | 36 |
| Passa gradeadas | 36 | 229 | 244 | 39 |
| Passa sarrafeadas | 36 | 229 | 244 | 39 |

Todas as variantes: zero unidades ausentes/extras, fontes N3 com hashes preservados, escala 1, quatro colunas, três continuações do índice imediatamente após sua folha inicial, numeração progressiva e caixas dentro da área útil. Nove conjuntos AB longos por variante distribuídos nas fronteiras de painéis, sem inventar montantes: união das linhas e áreas das hachuras comparada à fonte, sem perdas. Auditoria do DXF completo e de cada folha: zero erros; entidades editáveis, sem INSERT, DIMENSION residual ou imagem.

Índice próprio LV de seis folhas cadastrado em NOVA/LV_PARA e NOVA/LV_PASSA, SHA-256 `cbce4855d9dcdbcdee43589fc84e6d5f55d3d77286058b703c47ecc974748833`; mantém cadastros de outras classes. Paginação nativa publicada com backup `lv_n5_pagination_20261006_115026`; regressão 60 testes passou.

Portal: as quatro seleções mostram AB + Visão Corte e download correspondente; Para gradeadas deixado aberto em Unificados. Inspeção visual do portal e da folha 10 Para gradeadas realizada; isso é amostragem visual, não aprovação visual individual de todas as peças. Evidências: `n5_pagination/n5_generated_validation.json`, `release_registered.json`, `portal_n5_laterais.png`, `Para_gradeadas_folha10.png`. Anotações anteriores descrevem estados históricos e são superadas por este resultado.
