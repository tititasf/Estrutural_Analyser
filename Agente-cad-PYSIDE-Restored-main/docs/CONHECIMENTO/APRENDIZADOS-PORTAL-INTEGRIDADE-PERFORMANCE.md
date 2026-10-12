# Aprendizados do portal: integridade, interpretação e desempenho

Status: fonte canônica de consulta; evidência datada de 08/10/2026. Complementa [Estilos estruturais — interpretação integrada](ESTILOS-ESTRUTURAIS-INTERPRETACAO-INTEGRADA.md) e os manuais PIL, LAJ, FV e LV. TIPO_TESTE / EST-PE-007-TIPO-R01 é caso de origem, nunca condição no motor. Regras são gerais; validação nesta obra não certifica toda convenção futura. RAG recupera contexto, não substitui o CAD nem aprova itens.

## Integridade antes da interpretação SA

Ausência de pilares, lajes ou cortes exige comparar bruto, recorte e representação visual antes de ajustar reconhecimento. Neste caso houve descarte real de POLYLINE clássico e SOLID anterior às otimizações: métodos incompatíveis retornavam None silenciosamente. A mesma janela recuperou 166 POLYLINE e 498 SOLID, preservando todas as LINE/CIRCLE/TEXT anteriores. Usar geometria WCS própria de cada tipo e testar cobertura; não converter exceção em desaparecimento silencioso. HATCH, TRACE, POINT e blocos também exigem suporte explícito. Isso não significa que todo zero tenha a mesma causa.

Bruto e derivados precisam vínculo estrito de documento, pavimento, torre, revisão e hash. Nunca preencher uma aba com outro pavimento por fallback. Cortes externos à torre podem estar em detalhes/outliers: conservar contexto documental sem confundir detalhes com sólidos da planta. Um recorte corrigido invalida resultados dependentes anteriores; arquivo antigo não comprova regeneração. Evidência: scripts/arete/relatorios/20261008_tipo_geometry_audit/RELATORIO.md, 20261008_tipo_regeneration/RELATORIO.md e 20261008_tipo_fullpipeline/RELATORIO.md.

## Cotas e visão de corte não são limites de viga FV/LV

Cotas explodidas podem ser LINE/CIRCLE/TEXT, sem DIMENSION nativa. Cruzar marcadores concêntricos, testemunhas perpendiculares, valor numérico, distância e orientação; manter proveniência ao expandir DIMENSION. Linhas comprovadamente de cota ficam visíveis, mas deixam de fornecer paredes de FV e LV Para/Passa. Cor ou layer isolado não basta. Preservar uma parede estrutural independente coincidente. Evidência: 20261008_fv_dimension_guard/RELATORIO.md, 146 testes e regeneração FV/LV na VPS; N3/N5 antigos não certificam essa correção.

Visão de corte é informação de perfil e nível, não sólido, apoio ou risco físico de divisão. Seu símbolo não pode segmentar fundos ou laterais. Excluir entidades de anotação comprovadas, não toda a caixa envolvente: uma parede real pode cruzar a vista. Pré-interpretação compartilha identidades e proveniência entre classes; conclusão derivada não pode confirmar a si mesma. Contradição permanece pendência. Esse contrato complementa FV/LV e a síntese integrada, inclusive V514, V517, encontros, seções locais e cantos; nomes de exemplo não são exceções codificadas.

## Cortes originais e cortes interpretados

Inventário original conserva medições, identidades e desenhos da fonte. Lista de cortes interpretados exibe somente os gerados/identificados pela interpretação, sem cópias artificiais interpreted:source-section. No caso observado: 55 originais e 18 interpretados; os 73 anteriores incluíam duplicação. Filtrar a apresentação não apaga evidência nem exige alterar o SA. Evidência: 20261008_fv_missing_crossings/RELATORIO-CORTES-LISTA.md. Contagens históricas nos screenshots não são estado vigente universal.

## Cadeia completa e pendências por item

Ordem solicitada: triagem/recortes, depois pré-processamento → SA → N3 → N5; seleção de um pavimento ou todos. SA isolado não implica N3; N4 compara outra origem e não fornece dados ao N3. Configuração de laterais gradeadas/sarrafeadas, fundos com/sem garfos e modo INI/NOVA/Formascia deve acompanhar variante e revisão. Opção existente na interface não prova implementação; Molde 2/3 e garfos não devem receber sucesso fictício.

Falta de dados de um item registra identificação, motivo e variante no ledger e permite produzir os válidos. Erros sistêmicos de execução/integridade continuam fatais. Não substituir item falho por preview antigo nem publicar N5 vazio como completo; revisão humana opcional não equivale a validado. Evidência: 20261008_item_pending/RELATORIO.md (115 testes, fixture N5 com um válido e uma pendência) e 20261008_tipo_fullpipeline/RELATORIO.md. Esses ensaios não certificam cadeia integral de toda obra.

## Viewer leve sem reduzir qualidade CAD

Representação visual otimizada é derivado; DXF integral, geometria de interpretação SA e precisão OSNAP permanecem fontes independentes. Compactação/compressão não pode retirar entidades para acelerar o motor. Em edição mostrar somente destaque ativo; na criação ocultar outros destaques mantendo OSNAP do desenho original. Cache deve invalidar por fonte, revisão, configuração e versão do renderizador; autorização continua aplicada.

Bruto regional apresentou pop-in: câmera movia antes de receber entidades novas. A solução publicada usa SVG integral agrupado por padrão, regional apenas explícito. Agrupar somente traços M/L consecutivos de pintura opaca idêntica, fill:none e clip compatível, preservando coordenadas, ordem e início M de cada traço; não aplicar cegamente a curvas, IDs, transforms, hatch/preenchimentos ou efeitos. Hatch sólido pode admitir preenchimento único só após comprovar contorno, ilhas, buracos e equivalência; não há certificação geral dessa conversão neste dossiê.

Gzip HTTP sem perda e cache por revisão evitam recompressão. Na amostra bruto: 859047 paths originais → 32645 nós representando a geometria completa; SVG agrupado 53870167 bytes → gzip 13032276 bytes, igualdade após descompressão. Abertura única: fetch 3639,9 ms, parse 543,4 ms; cache quente 8,84 ms. Não são FPS nem garantia de 9/10 em todo dispositivo. Zoom/arraste mantiveram os 32645 paths residentes, sem buscar regiões. Recorte manual temporário foi desenhado e removido sem submissão. Evidência: 20261008_raw_viewer_perf/RELATORIO.md e bruto_integral_sem_popin.png.

## Medir, reutilizar e generalizar sem perda

Separar leitura, análise, fichas, geração, publicação, rede, parse e pintura. Pré-processamento mais curto não prova SA completo nem que minutos restantes sejam apenas publicação. Menos itens válidos pode falsear ganho. Reuso entre classes/rodadas exige mesma origem/hash/configuração/versão e dependências; confirmação independente deve apontar entidade, medida ou convenção CAD externa ao resultado confirmado. CPU pesada pede avaliar processos e RSS, I/O pode beneficiar threads; não há promessa de quatro workers serem sempre melhores nem de três minutos por classe.

Antes de aplicar em novas obras, testar rotação/escala, convenções diferentes e contraprovas: cota vs parede coincidente; corte sobre viga vs risco real; apoio verdadeiro vs vazio; seções locais diferentes; pilares U/circular; laje sem nome; fonte de outro pavimento. Preservar pendências da síntese: P14, associação laje/vazio V519, faces especiais e N3 circular. Documentação/indexação não promove candidatos de semantic_rag_kb nem treina automaticamente o motor.
