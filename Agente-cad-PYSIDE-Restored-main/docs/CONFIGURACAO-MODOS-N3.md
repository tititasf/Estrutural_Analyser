# Configuração de Modos N3

## Seleção antes de gerar — decisão de 01/10/2026

Todas as classes exibem cinco opções de seleção única acima do botão N3:
Modo iNI, Modo Nova, Modo Molde 1, Modo Molde 2 e Modo Molde 3. Os Moldes correspondem aos identificadores
MOLDE_1, MOLDE_2 e MOLDE_3 já aceitos pelos motores. O painel Motores também
exibe as cinco opções antes de Rodar desenho · todas as classes. O modo
selecionado alimenta tanto N3 quanto a sequência SA → N3 → N5, inclusive LV;
não há nova pergunta de modo após clicar nesses comandos. A seleção fica
lembrada neste navegador por obra, pavimento e classe (ALL no painel Motores),
com padrão NOVA. O job registra o modo efetivo independentemente de alterações
posteriores da seleção. A escolha posterior do N5 avulso continua existente.

As preferências de vigas são do pavimento, não da ficha da obra: Gradeadas ou
Sarrafeadas acima do N3 de LV Para/Passa; garfos Sim ou Não acima do N3 de FV;
ambas no painel Motores. Padrões: Sarrafeadas e Não. São salvas no servidor
por obra/pavimento e copiadas para o job e para os contratos de conversão.
Os controles correspondentes foram retirados da criação/edição da obra.

A opção garfos Sim está disponível para registrar a decisão, mas sua geometria
ainda depende da regra do dono. O sistema informa essa pendência e rejeita a
geração de fundos com Sim, sem publicar um desenho falsamente identificado
como contendo garfos. As demais classes continuam disponíveis. Evidência:
`scripts/arete/relatorios/20261001-opcoes-pavimento-n3/RELATORIO.md`.

## Decisão do dono — 01/10/2026

Botão no rodapé do usuário, imediatamente após Ver apontamentos. Configurações
globais com Modo iNI, Modo Nova e Modo Molde 1/2/3 e cinco classes: PL, LV Para, LV Passa, FV e LJ. Para e Passa
são independentes. O dono esclareceu que o desenho N3 atual deve ser preservado:
o legado informa a semântica dos ajustes, sem restaurar seus algoritmos antigos.

## Controles efetivos

Dentro de cada classe, as subabas separam Componentes, Textos, Hachuras, Cotas,
Disposição, Layers, Moldura, Exemplos, Detalhes especiais e Referência legada. Alternar subabas
conserva o rascunho; Salvar configuração salva o perfil da classe selecionada.

Moldura aceita upload DXF até 20 MB, separado por modo/classe, e exibe SVG
com zoom/pan por viewBox. O original é guardado sem transformação; a renderização
precisa passar antes de substituir a referência atual. Arquivo inválido não
substitui a moldura anterior. Nesta etapa a moldura é somente documento de
referência: não interfere em N3/N5, aguardando a regra funcional do dono.

- Inclusão de painéis, sarrafos, cotas, textos, hachuras, metal e carimbo.
- Nome, cor ACI e inclusão de cada layer declarado pelo gerador.
- Tipo de linha e padrão de hachura por layer, com opção Manter desenho atual.
- Textos por função: nome, referências de faces, níveis, pé-direito, sarrafos,
  extremos e reaproveitamento, conforme a classe. Inclusão, escala, cor e estilo isolados.
- Hachuras por função e classe: inclusão, padrão, escala, ângulo e cor.
- Cotas por vista: inclusão, escala, setas, cor, estilo, precisão e afastamento.
  Inclui cotas nativas e cotas compostas de linhas/textos na visão corte.
- Posições das grades de pilares e espaçamentos de apresentação de cada robô.
- LV: recuos de sarrafos, distância do corte e inclusão de hachura de laje/painel.
- FV: recuo, distância e comprimento dos sarrafos.
- LJ: afastamentos de cotas, sarrafos e hachura dos pilares.

Somente diferenças explicitamente salvas são aplicadas. Salvar valores padrão
não transforma o DXF. A configuração é aplicada após a conversão visual Ini/Nova;
parâmetros do gerador são fixados antes da geração. Cada documento PL ou processo
de robô usa uma única revisão mesmo que haja salvamento simultâneo.

Mudanças influenciam novas gerações. N3/N5 já publicados continuam existentes;
operador regenera N3 e depois N5 para incorporar as escolhas.

Componentes ficam separados por vista: PL Cima, A/B/E/F/G/H, C/D e Grades;
LV Visão corte e Painéis AB; FV Fundos; LJ Planta. Um ajuste não deve remover
o componente correspondente das demais vistas.

Exemplos aceita até dez DXFs de 20 MB por perfil modo/classe, com seleção
Exemplo 1 a 10, SVG com viewBox e exclusão da lista. Originais permanecem
preservados. Exemplos e Moldura são referências, sem inserção automática no N3.

Detalhes especiais explica diferenças efetivas de representação MLINE/LINE,
paleta e layers, e permite anotações humanas persistidas. Os três modos Molde
recebem uma cópia independente da configuração Nova existente na primeira
inicialização; edições posteriores de Nova não alteram essas cópias.

Controles sem entidades correspondentes no contrato atual não acrescentam
geometria nova. O reconhecimento semântico registra funções nas entidades
geradas para aplicar os ajustes seletivamente, preservando o gerador atual.

## Referência legada e limites

Inventário extraído por AST/JSON em `config/drawing_mode_legacy_catalog.json`:
Cima, ABCD e Grades de pilares, laterais, fundos e lajes. Campos originais ficam
visíveis no inventário de referência. A janela **não reproduz todos os campos
originais como controles editáveis**. Comandos interativos AutoCAD/LISP, substituição
de blocos externos, numeração e opções sem correspondência implementada permanecem
somente referência; não são apresentados como funcionais.

LISP encontrados com busca incluindo ignorados em
`_ROBOS_ABAS/Robo_Laterais_de_Vigas/Ferramentas_viga/`: HHHH aplica AR-CONC em COTA;
ABVET desenha/recorta abertura à esquerda e ajustes locais de sarrafos. Não é
necessário executar esses comandos para aplicar configurações de apresentação.
Geometria de aberturas continua governada pelo contrato atual do N3.

## Persistência e proteção

### Valores atuais do N3 (01/10/2026)

Os valores preenchidos em Textos, Hachuras e Cotas vêm de DXFs emitidos pelos
geradores atuais, sem perfil salvo e sem importar configurações legadas.
`config/drawing_mode_current_catalog.json` registra valores distintos por papel,
modo e classe, contratos medidos e hashes dos geradores. Valores únicos preenchem
os campos; valores diferentes permanecem listados, com -1/PRESERVAR para conservar
a variação. A amostra é P1, V301 A/B Para/Passa, fundo V301, L301 e contrato de
qualidade de corte LV com desnível. Ausência na amostra não significa ausência
em todas as obras: a interface explicita que aquele componente não foi emitido.

Alturas de texto, altura do texto de cota e tamanho da seta/traço são valores
absolutos em cm. Escala DXF da hachura também é absoluta. Fatores de altura/escala
continuam relativos e multiplicam o valor atual (ou o absoluto alterado).
Cor 256 significa ByLayer; 0 conserva a cor. Perfis relativos já salvos mantêm
seu comportamento. Salvar sem alterações grava delta vazio e não redesenha.
Precisão mede tanto DIMSTYLE nativo como decimais efetivamente emitidos nas cotas
em texto; valores mistos não são reduzidos à precisão do DIMSTYLE.

`scripts/build_current_drawing_defaults.py <saída>` mede e atualiza o catálogo;
para outra instalação: CAD_CURRENT_ROOT, diretório de contratos como segundo
argumento e `--measure-only` como terceiro. Na publicação são usadas medições
da própria VPS; hashes diferentes avisam sobre medição desatualizada e deixam
de preencher padrões absolutos, preservando o gerador. Legado continua somente
na categoria de referência, sem alimentar esses padrões.

Validação: 67 testes focados e 35 DXFs reais nos 25 pares modo/classe.
Salvar padrões preservou todas as entidades; altura absoluta 23,75 alterou
somente os nomes. Zero erros de auditoria. Evidências em
`scripts/arete/relatorios/20261001_current_defaults/`.

`portal_runtime/drawing_mode_settings.json`, ou ARETE_DRAWING_MODE_CONFIG para
testes isolados. Gravação atômica, bloqueio de arquivo e revisão otimista; edição
restrita ao dono e leitura aos membros autenticados. Conflito retorna 409.
DXF inclui hash do perfil e revisão para diagnóstico. Não modifica SA, JSONs
Fase-4 ou DXFs de origem. Configuração compartilhada também é consumida por
chamadas dos mesmos geradores em outros fluxos; os valores padrão são inertes.

## Evidência

Ampliação granular de 01/10: 50 testes focados e 34 testes de contratos/N5
passaram. Geração isolada produziu 50 DXFs nos 25 pares modo/classe, alterando
somente nomes ao configurar escala 1,7/cor 1. Publicado na VPS às 19:19 UTC;
navegador de produção confirmou cinco modos, dez categorias e componentes
por vista. Exemplos continua vazio em produção para receber documentos do dono.
Relatório: `scripts/arete/relatorios/20261001_config_granular/RELATORIO.md`.

45 testes focados passaram: API/autorização, revisão, validação, configuração
por modo/classe, cores/layers, blocos, tipos de linha, hachura, cotas e snapshot.
Geração real em cópias: P1 (PL), V301 (LV Para, LV Passa, FV), L301 (LJ), nos dois
modos, antes/depois de escala 1,5. Auditoria sem erros em todos os DXFs.
PNG completos antes/depois foram lidos pelo agente; não é certificação Arete.

Na VPS, salvar Nova/LV Para = 1,2 pelo navegador e executar o gerador confirmou
o fator em todos os TEXT do V301. Restaurado = 1 pela mesma interface. Revisão 2,
sem mudanças de desenho remanescentes. Saídas do teste isoladas em
`portal_runtime/drawing_config_validation_20261001_v2`.

Relatório local: `scripts/arete/relatorios/20261001_drawing_mode_config/`.

Validação das subabas e Moldura: 10 testes focados passaram; arquivo inválido
não substitui o anterior, autenticação e permissão de dono verificadas, isolamento
Ini/Nova e LV Para/Passa verificado. Navegador local isolado carregou o DXF real
FV_preview_V301.dxf; zoom alterou o viewBox e Enquadrar restaurou exatamente
0 0 864 504. Rascunho preservado ao alternar subabas. Publicação confirmada no
portal do dono com Moldura vazia para receber seu documento, sem arquivo de teste.

### Cards de seleção antes do N3 (2026-10-02)

Os cinco modos aparecem em cards compactos, em uma única linha horizontal com cinco colunas que dividem a largura disponível, acima do N3 em todas as classes e no painel unificado. O texto quebra dentro do card e a altura cresce conforme necessário; economizar espaço vertical é a preferência do dono. Cards não selecionados têm fundo azul; somente o selecionado fica verde. O controle mantém seleção única, navegação pelas setas do teclado e indicação de foco. A alteração visual preserva os valores e a persistência dos modos existentes. Gradeadas/Sarrafeadas e Garfos Sim/Não usam o mesmo visual em pares lado a lado, com opções persistidas por pavimento.

As opções de vigas não exibem a legenda permanente “Opções deste pavimento”, para economizar altura. Status aparece somente enquanto salva ou em caso de erro.

### Remover documentos enviados (2026-10-02)
Nas abas Moldura e Exemplos, o botão de remoção fica junto ao nome do arquivo, antes do visualizador. A moldura removida deixa de ser a referência ativa; os exemplos saem somente da lista do modo/classe selecionado. Os originais permanecem preservados. Uma remoção de moldura com token antigo retorna 409 e preserva a substituição mais recente.



### Desempenho dos documentos de exemplo (2026-10-02)

Exemplos e molduras usam câmera numérica e atualizações de viewBox agrupadas por requestAnimationFrame. O arraste evita leituras de layout a cada evento; o SVG não participa de hit-testing por entidade. Todos os vetores permanecem completos. Teste e evidência: `scripts/arete/relatorios/20261002_example_performance/RELATORIO.md`.

### Página de configurações e carregamento (2026-10-02)

Configuração de Modos abre em `/app/configuracao-modos/pagina`, no conteúdo à direita, com o painel esquerdo do portal e link de retorno ao desenho. O modal global foi removido. Os parâmetros `modo`, `classe` e `categoria` preservam a seleção ao recarregar; `retorno` aceita somente caminhos locais de obras.

Somente os campos da categoria selecionada são montados. O catálogo compartilha uma medição por requisição; a árvore sintática dos motores é reutilizada enquanto o texto fonte permanece igual. Em medição local, o catálogo passou de 3,394 s para 1,023 s na primeira execução e 0,808 s na seguinte. Esses tempos não representam o tempo total do navegador ou da VPS. Os geradores e os vetores dos visualizadores permanecem sem alteração nesta entrega.

Validação: 22 testes focados passaram, sintaxe JavaScript verificada e navegação publicada conferida no navegador. Relatório e imagem: `scripts/arete/relatorios/20261002_config_page/`.

### Compactação vetorial dos exemplos e molduras (2026-10-02)

O exemplo real de pilares NOVA tinha 144.283 nós no SVG: 64.312 instâncias de marcadores, principalmente pontos de hachura, além de dezenas de milhares de paths. A navegação por viewBox continuava custosa devido à estrutura de renderização. `portal/app/svg_compact.py` agrupa paths de traços com estilo e clipping iguais, expande marcadores M/C em subpaths com as mesmas curvas e posições e remove grupos sem efeito gráfico. Lotes limitados a 128 evitam um único path gigantesco. Elementos com transformações ou transparência explícitas não suportadas permanecem intactos.

Os previews de Moldura e Exemplos usam cache derivado `compact-v1`, enviado comprimido quando o navegador aceita gzip. O DXF e o SVG originais permanecem preservados. No arquivo real, 144.283 nós passaram a 6.255 (96% de redução); o navegador confirmou 6.254 descendentes e zero uses. A comparação raster mostrou diferenças pequenas de suavização em sobreposições; não é identidade pixel a pixel. Zoom, arraste e reset foram executados na aba real. Não foi medida taxa de quadros.

12 testes focados passaram. Evidências e publicação: `scripts/arete/relatorios/20261002_svg_compact/RELATORIO.md`.

### Recortes dos exemplos (2026-10-02)

Cada exemplo possui uma lista de recortes, isolada por modo e classe. Clique em Recortar exemplo, desenhe um ou mais retângulos com o botão esquerdo, escolha o tipo e salve. Botão do meio move e scroll amplia durante a seleção. Original retorna ao documento completo; os demais botões abrem o recorte correspondente. Remover recorte retira a entrada da lista e preserva os arquivos.

Cada retângulo concluído abre sua própria linha de tipo e nome. O botão × dessa linha remove somente sua seleção; os dados das demais linhas são preservados. Recortar e salvar processa todos os retângulos em uma ação, criando um documento separado por retângulo. Se algum processamento falhar, as seleções ainda não salvas permanecem disponíveis para tentar novamente. As abas ficam bloqueadas durante o lote.

Pilares: Cima, ABCD e Grades. Laterais Para/Passa: Visão corte sarrafeado, Visão corte gradeado, Visão corte com garfo, AB sarrafeado e AB gradeado. Fundos: Fundos e Garfos. Lajes não possuem subclasses.

A seleção conserva entidades inteiramente contidas no retângulo, como os recortes manuais de pavimentos. O documento derivado mantém blocos, layers e estilos do original. Entidades sem geometria não deslocam a correspondência entre entidades e limites. Os originais enviados e os geradores N3 não são modificados. Cinco testes focados passaram; criação, persistência e abertura foram verificadas no exemplo real NOVA/PL no navegador.
