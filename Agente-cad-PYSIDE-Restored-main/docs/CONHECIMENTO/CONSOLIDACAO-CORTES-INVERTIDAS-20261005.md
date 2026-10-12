# Cortes e vigas invertidas — consolidação de 05/10/2026

Escopo: decisões e entregas desta conversa na Obra_TREINO_1, 13_PAV. As regras são gerais; os nomes abaixo são casos de validação. Este fechamento não certifica toda a obra nem todo N3. Procedimentos: `docs/SA-ANALISE/CLASSES/LV.md`, `docs/SA-ANALISE/CLASSES/FV.md` e `docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md`.

## Cortes interpretados no estrutural

Reconhecer contato das lajes pelas classes e regiões locais, sem escolher a laje mais próxima nem inventar nível. A correção de contato cobre folgas de normalização de 0,1 cm e rejeita associação fora da tolerância comprovada. Posicionar sobre o segmento físico, preferindo seu centro e evitando pilares. Falta de espaço não deve apagar um corte válido.

O destaque SA deve ter cobertura de cada segmento de fundo de viga, inclusive seções repetidas. Um corte original que já cobre o segmento dispensa outro interpretado; filtragem de repetições para fabricação pertence ao N3. Inventário físico e inventário visual são distintos: agrupar o detalhe não pode eliminar sua cobertura ou proveniência.

A decisão final substitui o limiar antigo de 80 cm: desenhos acima de 50 cm comprimem somente a cauda reta para caber em 50 cm totais, podendo comprimir mais para o espaço disponível. A região com lajes conserva suas medidas; se ela sozinha exceder o orçamento, o limite não autoriza deformá-la. Cotas continuam físicas e a fonte do texto conserva o tamanho anterior. Título: `V301 - VC4 - (19/120)`. Símbolo de compressão em interrupção retangular, distinto das duas linhas inclinadas da invertida; compressão forte recebe indicação reforçada `COMP. MAX`.

Código conferido: `portal/app/lv_cut_map.py` usa orçamento `50-head_length`, preserva contatos e título de tamanho 8. A revisão de 05/10 removeu chamadas/setinhas: o corte fica no próprio intervalo, comprimindo a cauda; a prevenção de sobreposição cobre pilares e detalhes da mesma viga, sem garantia global contra textos ou detalhes de outras vigas.

Evidências: `scripts/arete/relatorios/20261003_cut_slab_contact_placement/RELATORIO.md`, `RELATORIO_VISIBILIDADE.md` e `scripts/arete/relatorios/20261003_v330_inverted_plan/RELATORIO.md`. No snapshot comparável, dez cortes válidos foram recuperados, interpretados 46→56, originais 21 preservados. A captura anterior com 93 e as coletas posteriores com 67 interpretados não são universos comparáveis; não representam por si só exclusões. Contagem final não substitui auditoria de cobertura por segmento.

## Invertidas: leitura, níveis e montagem

As duas linhas inclinadas paralelas no corte original são evidência de inversão nesta obra. A classificação segue a viga até outra estação que expresse mudança; estação não interpretada não autoriza extrapolação cega. V330 tem duas zonas estruturais, alturas 120 e 71, ambas invertidas.

Padrão confirmado pelo dono: base = nível da laje local − espessura/100; topo = nível da laje local + (altura da viga − espessura)/100. Exceção explícita do corte prevalece. Não impor um datum escalar de toda a viga sobre lajes com degrau. O fundo de invertida é tampa superior, sem sarrafos, com LISO no centro dos painéis N3.

A tampa divide entre faces incidentes conforme decisão de montagem: V330 total 311+183=494 cm, excluindo larguras de 19 e 14 cm dos encontros. Essa divisão de peças não cria outra mudança de altura da viga. Validação FV isolada produziu quatro folhas LISO, sem sarrafos, mantendo 494 cm.

O limite 71/120 é a linha transversal completa medida do DXF, não o ponto médio entre textos. V330: LINE 445, Y=3095,038; zona 71 com 112 cm. Laterais: 3 segmentos A (71, 120 antes/depois do degrau) e 2 B (120/71), Para e Passa. Todas invertidas. Cores sólidas vermelho/branco alternam por segmento lógico; partições internas conservam a cor. Fundos invertidos/tampas recebem vermelho e legenda própria, com números sequenciais distintos.

## Cruzamentos e continuidade

Comparar intervalos verticais absolutos dos painéis: cruzamento em planta e faixa comum da laje não provam colisão. Exigir duas paredes medidas, contexto local confirmado e ausência de choque real. Preservar pilares reais, degraus, mudança de seção/nível explícito, edições manuais e rastreabilidade. Não usar exceção por nome de viga.

V301 A16/B1 alcança a face distante B da V330: 247,52→266,52 cm. VF301 fundos 8+9 tornam-se fundo 8 contínuo de 405,5 cm; 90 donos físicos e 91 polígonos de destaque, porque V330 tem duas partes de altura.

VF301 laterais A8+A9→A8 de 405,5 cm; B1+B2→B1 de 3490 cm, tanto Para quanto Passa. Diferença de nível escalar estimado 852,12/852,19 não bloqueia sozinha a união quando os perfis pareados comprovam datum contínuo e travessia livre. Isso não confirma os níveis estimados. Níveis explícitos diferentes ou degrau continuam impedindo união. `source_level_sections`, `merged_source_segments` e UIDs conservam fontes e valores originais.

Última geração SA confirmada: job `a00f4771-1517-4a46-8037-1e36a31b42bc`, 05/10/2026 10:18:54 Brasília. Após regeneração: Para 220 (113A/107B), Passa 212 (108A/104B); VF301 8A/1B e V330 3A/2B preservadas. 51 testes do último ajuste passaram; evidência por unidade em `scripts/arete/relatorios/20261004_lv_regeneration/vf301_sa_verdict.json`, dados em `effective_regenerated.json` e PNG `portal_vf301_unida.png`.

## Regeneração e data granular

SA bem-sucedido limpa marcas de remoção somente dos itens efetivamente regenerados no escopo obra/pavimento/classe/vigas. Isso recupera VF301 removida para teste e preserva edições manuais, outras classes e itens fora do snapshot. Falha não limpa marcas.

Botões exibem última conclusão válida por obra, pavimento, classe e motor SA/N3/N5 em Brasília. Falha ou execução de item isolado não substitui a conclusão da classe. A data SA não prova nova geração N3.

## Pendências reais e limites do fechamento

- Perfil local de 124 cm: o dono informou que a pendência já está resolvida; não reabrir como pendência desta conversa.
- Regenerar e validar N3 publicado com as últimas uniões VF301, leitura PNG e confronto por unidade. Houve gerações N3 isoladas de validação, mas a rodada final de 05/10 foi SA; não há selo global G2V/N3/N4/N5.
- Desempenho de “carregando classes”: reutilização acelerou chamadas com cache; primeira leitura ainda lenta, conforme medição abaixo. Não há aceite global de latência.
- A auditoria atual verifica cobertura dos intervalos exibidos, conservando os donos e as fontes unidos; não comprova ausência global de sobreposição entre textos de vigas diferentes nem certificação de engenharia.

Estas pendências são deste escopo; não importar tarefas de Formascia, PIL ou confiança de níveis de outras conversas como se fossem entrega desta rodada.


## Revisão final dos destaques: perfis locais, degraus e datum (05/10/2026)

O original dispensa somente um perfil físico equivalente no mesmo fundo: largura, altura, condição normal/invertida e contatos A/B com espessura e desnível. Um original 120 não suprime o interpretado 71, nem elimina o perfil distinto de um degrau. O mesmo fundo pode exigir vários cortes locais; deduplicar Para/Passa conserva esses perfis. Inventário publicado: 91/91 fundos atendidos (5 exclusivamente originais, 86 com interpretação), 109 destaques interpretados. Atendimento do contador não é certificação de engenharia.

Não há setinhas nem deslocamento para grade externa quando falta espaço. O corte permanece no intervalo local, com COMP./COMP. MAX, medidas físicas e tamanho de texto preservados. Cores do corpo interpretado: azul claro #7dd3fc para confiança alta, laranja #ff9a1f para revisão, vermelho #ff4545 para invertida; legenda explícita. Cotas e textos conservam suas cores próprias. Confiança alta exige contrato sem avisos e referências locais confirmadas.

Separar topo da viga do topo da laje. Em viga normal, cortes originais medidos da própria viga podem ancorar o topo pela soma nível regional da laje + distância cotada até o topo. Aplicar a referência somente quando única e compatível com a largura; originais contraditórios sinalizam revisão. Não copiar automaticamente a maior ou menor cota de laje para o topo da viga. Preservar originais e campos N1. Casos conferidos: V313/V317 têm regiões rebaixadas 3 cm; V315 e VF203 têm lajes 7 cm abaixo do topo. A fórmula local das invertidas permanece independente.

VF202: o dono confirmou em 05/10/2026 que sua laje deve seguir o nível expresso pelo VC3 da VF203. Conferência: laje local L326 com 852,12 m e h=10; original da VF203 ancora topo em 852,19 m, com rebaixo de 7 cm. A correção usa o original de uma viga diretamente conectada somente se largura, espessura e nível da laje local forem compatíveis e a referência for única. Não usa proximidade, nome ou extrapolação por cadeia. Originais próprios têm prioridade; divergências continuam para revisão. Esta referência afeta o corte apresentado, preservando o inventário físico de colisões e N1.

Desempenho: geometria das regiões de laje e dos pilares reutilizada por análise; reconhecimento das regiões possui cache limitado por conteúdo das lajes e revisão do DXF/sidecar, com cópias independentes. Viewer com SA disponível evita ler pacote antigo de pré-processamento. Medição direta do endpoint completo em processo novo: 23,91 s na primeira chamada, 1,69 s e 1,45 s nas seguintes. O primeiro carregamento continua sendo uma limitação explícita; não declarar toda a latência resolvida.

Validação: 99 testes passaram; fonte e JSONs originais preservados. Publicações protegidas por hash anterior, ausência de jobs ativos e backups em 05/10/2026 às 14:30 e 14:41 UTC. Evidência e scripts em `scripts/arete/relatorios/20261005_cut_local_profiles/`. N3/N5 global continua fora do selo desta revisão visual SA.

### Conferência de continuidade e identidade dos perfis (05/10/2026, revisão final)

A referência cotada do original ancora o corte apresentado, mas não estabelece sozinha o datum físico de colisão em todo encontro remoto da viga. Aplicá-la indiscriminadamente à lista de colisões reintroduziu divisão indevida na VF301; a correção mantém o inventário de contato local independente. Conferência real posterior: VF301 A8 com 405,5 cm e B1 contínuo com 3490 cm; V301 A16/B1 com 266,52 cm; V330 com 3 A e 2 B. Totais Para 220 e Passa 212. Níveis explícitos e choques localmente comprovados continuam prevalecendo.

Perfis distintos de degrau derivados do mesmo VC recebem identidades de destaque distintas e estáveis, sem alterar o nome do VC. A cobertura da legenda usa os intervalos efetivamente exibidos: união conserva `source_fundo_ids`; subdivisão de altura possui `display_id` próprio. O inventário anterior permanece em `source_soffit_coverage` como proveniência, não como contagem atual.

Regressão final: 101 testes passaram. Endpoint completo medido diretamente no servidor após a correção de continuidade: 22,08 s na primeira chamada, 1,38 s e 1,25 s nas seguintes; são tempos do processamento do endpoint, sem transporte HTTP e pintura no navegador. A primeira leitura permanece pendente de melhoria.


### Fechamento VF202 (05/10/2026)

Conferência no servidor: corte VF202 com topo 852,19 m e laje L326 (h=10) em 852,12 m, rebaixo de 7 cm. 103 testes passaram; VF301 preserva 8 A/1 B e V330 3 A/2 B. Publicação protegida às 23:42 Brasília. Evidências: `scripts/arete/relatorios/20261005_vf202_datum/RELATORIO.md`. A largura do fundo diagonal recortado não representa a largura nominal: testar conectividade pelo contato, e compatibilidade dimensional pelo contrato do corte. Esta pendência específica foi resolvida; N3/N5 global e latência inicial permanecem nos limites acima.


### Amarelo: degrau sem corte original da transição (05/10/2026)

Correção do dono em 06/10/2026: amarelo #ffe033 identifica o próprio desenho interpretado da transição entre regiões de laje, na aba Cortes de viga interpretados. Não basta colorir um corte de viga próximo. Gerar um corte por degrau sem seção original, no limite interno real, a partir dos níveis e espessuras confirmados de ambas as regiões. O desenho representa os fundos e topos regionais sem assumir alinhamento; níveis ausentes deixam pendência explícita. Conservar o corte original quando existente. L322/L323 exemplificam ausência; L309/L312 possuem cortes originais. Legenda: **Visão corte degrau de laje**. Os cortes de viga mantêm azul/laranja por confiança e vermelho para invertidas, independentemente da proximidade de um degrau. A geração é somente um destaque derivado, sem alterar N1, colisões ou cobertura de fundos.
### APONTAMENTO-CONTEXTO-ESTRUTURAL-20261007 — entorno preservado

O antes/depois do apontamento automático inclui o recorte real do estrutural limpo, vizinhos e a área do item marcada, usando enquadramento idêntico. Excluir um destaque deixa esse entorno visível no depois; o detalhe isolado continua como complemento. O JSON registra entidades antes/depois, comentário, vizinhos identificados com campos, bbox DXF, fonte, SHA256 e instante UTC da captura. A evidência congelada acompanha a fila persistida; repetir a entrega ao banco não captura outro estado. Eventos anteriores sem entorno não são convertidos em falsas capturas históricas. Regra do dono APONTAMENTO-CONTEXTO-ESTRUTURAL-20261007.

### Revisão humana dos cortes e evidência automática (06/10/2026)

Complemento de 07/10/2026: o painel Pré-processamento lista **Visão de Cortes Interpretados**, usando o mesmo inventário de destaques do estrutural limpo, inclusive degraus. O botão Pré-processar pavimento já coleta `beam_sections` no pacote de níveis antes do SA; a lista permite selecionar cada ocorrência para validar ou excluir. Coleta não equivale a validação humana nem garante ausência de pendências. Cortes excluídos ficam fora da lista e da contagem; validações aparecem com ✓. A confirmação de exclusão de corte interpretado permite comentário opcional, preservado na decisão e no apontamento com o desenho excluído e JSON. Publicação: `section_review_20261007_123015`; 56 testes passaram.

Cortes originais podem ser selecionados e editados (contorno e campos semânticos), incluindo seções de degraus originais. Alterar o contorno não reinterpreta automaticamente sua ficha: os campos são editáveis separadamente. Cortes derivados aceitam somente validar ou excluir. A validação de corte de viga promove seu datum local para `human_validated_section`, com escopo da obra, pavimento e intervalo físico compatível. Mudança dimensional invalida a referência antiga; fontes humanas conflitantes ficam pendentes. Excluir retira o destaque e sua validação, preservando os níveis comprovados do CAD original. A decisão acompanha renumerações compatíveis e uma validação antiga não pode ressurgir após exclusão.

Edições e exclusões de qualquer classe estrutural registram automaticamente um apontamento na janela existente, com PNG antes/depois e JSON das entidades, autor, escopo e evento idempotente. Se o banco estiver temporariamente indisponível, uma fila persistida permite completar o apontamento sem repetir a mutação. Fontes CAD permanecem intactas. Publicação protegida em 06/10/2026 às 15:41 UTC; 38 testes locais passaram e as rotas reais foram testadas com dados isolados no servidor. Inventário HTTP da obra: 32 originais e 115 interpretados. Conferência visual dos cliques pendente porque a ferramenta de navegador falhou.



### CORTE-REJEICAO-NOVA-GERACAO-20261008

Correção de política solicitada pelo dono: excluir um corte interpretado rejeita a ocorrência atual, preservando o apontamento com comentário, desenho anterior e contexto estrutural. Não é uma proibição permanente de interpretar aquela viga. A próxima publicação válida do pré-processamento ou SA de laterais/fundos do mesmo escopo permite repopular a interpretação, inclusive quando o perfil foi corrigido pelo motor. Apenas recarregar o viewer, gerar outra classe ou falhar no processamento não libera a rejeição. Uma exclusão feita durante uma rodada permanece vigente para evitar que o job em curso a desfaça.

O histórico local conserva a evidência rejeitada e o evento de auditoria. A nova ocorrência nunca recupera a antiga validação humana nem a confiança de nível atribuída por ela; requer nova revisão. Evidências CAD independentes continuam válidas. A regra também atende exclusões de teste antigas sem apagar seus apontamentos. Esta decisão substitui qualquer leitura anterior de exclusão permanente de cortes interpretados.
