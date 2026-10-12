# Apresentação numérica global — 2026-10-03

**Status:** canônico · **Tier:** T1 · **Escopo:** global

Decisão do dono: medidas e valores decimais apresentados ao humano usam uma casa
decimal no máximo, com vírgula e arredondamento: 417,98 → 418; 417,88 → 417,9;
18,717 → 18,7. Vale para todas as classes, campos, portal/app, SA, N3/N5 e
evidências humanas dos agentes. A regra não depende da viga ou do pavimento.

## Exceção obrigatória: níveis em metros

Níveis absolutos (laje, viga/fundo, pilar, chegada, saída e elemento vinculado)
usam **exatamente duas casas decimais**, inclusive zeros: 852,19; 852,10;
852,00; -0,05. Esta exceção prevalece sobre a regra de uma casa e de omitir ,0.
Vale para campos, colunas, etiquetas, convenções gráficas, SA, N3/N5,
documentação, agentes e evidências humanas de todas as classes. Um trecho
interno só com diferença de h não ganha um segundo nível: continua o nível da
laje, nas duas casas. Fundo diferente só aparece quando a comparação de fundos
está comprovada. Sem essa prova, a ficha diz que o fundo ainda não foi
determinado, em vez de inventar outro número.

O valor deve estar em metros. Não inferir a unidade pela magnitude; converter
somente quando a origem declara outra unidade. Distância até o topo, altura,
pé-direito e diferenças/desníveis declarados em cm continuam sendo medidas
com no máximo uma casa. Campos internos chamados `level` podem ser deslocamentos
locais em cm: o nome sozinho não autoriza tratá-los como nível absoluto.
Preservar dados e precisão interna; formatar apenas na apresentação.

Identificadores, índices de segmentos/painéis, contagens e datas mantêm seu
formato próprio. URLs, caminhos, versões de software e códigos não são medidas.

A apresentação não arredonda coordenadas, cálculos, dimensões persistidas nem
dados de máquina. Salvar um campo sem editá-lo preserva seu valor exato. Não
reescrever DXFs históricos, originais N2/N4 ou evidências brutas: apresentar uma
cópia formatada, mantendo a proveniência. Se a casa decimal for zero, exibir somente o inteiro: 244,0 → 244. Valores pequenos exibidos como 0
continuam não nulos internamente; isso não autoriza descartar nenhum trecho.

Implementação em revisão: `src/core/number_presentation.py` para CAD e
`portal/app/static/decimal_display.js` para web. A existência desta regra não
significa que todos os caminhos legados já foram auditados/publicados.

Etiquetas CAD em camada genérica também podem ser níveis. O formatador reconhece
as convenções de altitude em planta (círculo com dois diâmetros e linha-guia)
e em corte (triângulo fechado, haste no meio da base e linha-guia), associando
o texto à própria linha-guia. Círculo isolado, seta de cota e proximidade sem
essa topologia não bastam. Não classificar pelo valor do número ou por nomes
de itens/pavimentos. A regra é de apresentação em cópia: não modifica a fonte
nem substitui a interpretação/proveniência do SA.
