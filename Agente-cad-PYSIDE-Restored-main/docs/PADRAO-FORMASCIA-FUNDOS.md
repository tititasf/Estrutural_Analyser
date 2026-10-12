# Formascia — fundos de viga

Escopo desta revisão: MOLDE_1 / FV. Design aprovado explicitamente pelo dono em 2026-10-05. Integração N3/N5 publicada na VPS e geração pelo portal verificada em 2026-10-06 para 13_PAV da Obra_TREINO_1: 36 vigas, 91 segmentos, 8 folhas N5 incluindo índice. Auditoria CAD das folhas sem erros ou correções; renders completos conferidos. Esta validação de design não sela a interpretação estrutural SA.

## Aberturas — orientação explícita do dono, 2026-10-05

Aberturas são recortes nas esquinas/extremidades do segmento, não furos internos centrais. Se um vazio aparecer no interior da composição, apresentar dois segmentos independentes: recorte em L no topo direito do primeiro e no fundo esquerdo do segundo. Derivar contornos e posições das arestas reais da geometria SA, preservando o vazio, a área física total e a ausência de sobreposição entre segmentos. Não adotar as coordenadas demonstrativas como regra do motor nem reescrever dados SA originais nesta revisão de design.

O exemplo v02 com furo central foi rejeitado. Correção v03 em `scripts/arete/relatorios/20261005_formascia_fundos_experimento/v03/`: dois contornos sem anéis internos, geometria conservada e MLINE editáveis. A orientação de segmentação foi determinada pelo dono; o desenho v03 foi refinado até a v06 aprovada.

## Sarrafo horizontal na faixa de abertura — orientação do dono, 2026-10-05

O dono confirmou a divisão em dois segmentos e pediu complemento aos sarrafos da v03: quando houver abertura, os horizontais não ficam somente nas extremidades. Incluir uma MLINE horizontal extra abaixo do fundo do recorte superior direito ou acima do recorte inferior esquerdo, conforme a orientação da esquina. Ela deve ser curta, com a mesma extensão do horizontal existente ligado à quina da abertura, e não percorrer toda a largura do recorte. Derivar seu comprimento da configuração comum de sarrafo e seu posicionamento da aresta efetiva do recorte. No exemplo o comprimento é 30 cm.

O vertical da quina da abertura ultrapassa a medida do recorte em 7 cm para encaixar o horizontal extra: prolongar para baixo no recorte superior e para cima no inferior, dentro da área física remanescente. O horizontal extra nasce nessa quina, ligado ao prolongamento vertical; não transferi-lo para a outra ponta da faixa aberta. No exemplo, os 7 cm correspondem à largura do sarrafo, parametrizada pelo estilo MLINE. Preservar os demais sarrafos, letras A/B, cotas e contorno. Evidência v06 em `scripts/arete/relatorios/20261005_formascia_fundos_experimento/v06/`; a proposta v06 foi aprovada explicitamente; aprovação do experimento não equivale a validação da geração publicada. As versões v04 (extra pela faixa inteira) e v05 (extra curto ancorado na outra ponta) permanecem como histórico superado pelas instruções subsequentes.

## Evidências

Originais: `D:/Agente-cad-PYSIDE/Exemplos Modos/FORMASCIA/Fundos FORMASCIA.dxf` e `moldura e indice fundos.dxf`. Experimentos v01/v02/v03 preservados em `scripts/arete/relatorios/20261005_formascia_fundos_experimento/`. Relatórios distinguem referência original, geração atual, proposta e limites.

## Padrão aprovado

Cada segmento N3 tem identificação e linha própria no índice. A distribuição compacta aprovada preenche a moldura da esquerda para a direita, começando no canto superior esquerdo, com quebra de linha quando não couber o próximo envelope completo. Escala e posição são calculadas dos desenhos e da área disponível, mantendo a legenda técnica da moldura.

Painéis verdes (ACI 3); sarrafos vermelhos (ACI 1) em MLINE nativa, seção 7 cm. Conjuntos nas extremidades com recuo de 2 cm e horizontais de 30 cm, reduzidos proporcionalmente quando não há espaço para dois conjuntos sem sobreposição. Letras A-----A / B-----B brancas, altura 6 cm; identificação dos painéis branca, altura 12 cm, círculo vermelho de raio 10 cm. No L o conjunto acompanha a extremidade elevada. No chanfro o montante acompanha a diagonal real e os horizontais terminam alinhados nessa diagonal. Cotas e dados geométricos continuam derivados do motor atual/SA.

N5 utiliza o arquivo registrado `moldura e indice fundos.dxf`, com legenda original de montagem, carimbo preenchido pela obra/pavimento atuais, numeração calculada e índice das folhas geradas. Entidades individuais permanecem editáveis. Quantidades da obra de exemplo não são reutilizadas. Laterais de viga continuam pendentes.

## Compatibilidade CAD nativa — três vigas, 2026-10-06

Teste corrente com V303, V308 e V322: dez segmentos. A importação do N5 deve preservar estilos MLINE com a quantidade exata de elementos (limpar os elementos padrão antes de copiá-los), registrar APPIDs das XDATA copiadas e manter vetor de extrusão unitário. Folhas FV exportadas em documento limpo, com entidades e recursos usados, normalizando handles inválidos de material/estilo de impressão das camadas. O N3 Formascia FV também normaliza esses handles de camadas importadas. Correção sem mudança de geometria ou paleta; outras classes preservadas. Prova local: AutoCAD AUDIT zero em índice, folha, unificado e segmento âncora. Validação final da VPS em `scripts/arete/relatorios/20261006_formascia_fv_3/`.


Na geração final das três vigas, a camada `FORMASCIA-SARRAFOS` deve usar ACI 1 explicitamente: elementos e preenchimento MLINE BYLAYER herdam a cor da camada, mesmo quando a entidade declara vermelho. Os 16 DXFs finais da VPS passaram em AutoCAD AUDIT zero; índice e folha dos dez segmentos renderizados foram conferidos. Esta geração isolada está entregue para aprovação visual do dono; não certifica interpretação SA.


## Revisão solicitada — distribuição compacta, 2026-10-06

O dono substituiu a organização em células fixas pelo preenchimento semelhante a uma folha de caderno: iniciar no canto superior esquerdo, avançar à direita até o próximo segmento não caber e continuar na linha inferior. Reduzir intervalos horizontais e verticais. Remover títulos internos adicionados acima de cada fundo; conservar o nome normal do N3. A regra também respeita a legenda e o carimbo reais da moldura. Esta orientação substitui a distribuição por células descrita anteriormente, mas não altera o design dos fundos nem suas cotas e componentes.

Proposta v02 em `scripts/arete/relatorios/20261006_formascia_fv_compacto_v02/`: mesmos dez N3 da VPS, escala comum 1:5, dez segmentos em três linhas; envelopes completos, sem sobreposição, três DXFs N5 AUDIT zero. Proposta v02 aprovada explicitamente pelo dono neste chat. Intervalos entre envelopes de 35 unidades da moldura, margem interna de 30 e escala comum 1:5 para as três vigas demonstradas. A escala é calculada para o conjunto, limitada ao valor aprovado e reduzida somente se um desenho exceder a área total. Títulos internos por segmento não são desenhados; permanece o nome normal do N3.

### Integração e validação publicada — 2026-10-06

A regra foi integrada no compositor N5 Formascia FV. A posição é calculada pelos limites CAD completos de cada segmento, pela moldura efetiva e pela parede da legenda de montagem; não há posições por viga, segmento, pavimento ou obra. A VPS executou o compositor publicado com V303, V308 e V322, produzindo dez segmentos em uma folha de conteúdo, além do índice. O resultado manteve a ordem de leitura 4 + 4 + 2, sem títulos internos, sem colisão entre envelopes e sem invadir a legenda. Os três DXFs N5 resultantes (unificado, índice e folha populada) passaram no AutoCAD AUDIT com zero erros, zero correções e zero objetos apagados. Evidências e manifesto: `scripts/arete/relatorios/20261006_formascia_fv_compacto_integracao/RELATORIO.md`.
