# Formascia — laterais de viga (MOLDE_1)

Design aprovado explicitamente por Thierry em 07/10/2026, após revisão de V301/V304
nas quatro combinações Para/Passa × sarrafeadas/gradeadas. Aprovação do experimento
e validação da geração publicada são etapas distintas. Relatório de integração:
`scripts/arete/relatorios/20261007_formascia_lv_integracao/`.

## Fonte e isolamento

Dimensões, segmentos, encontros, lajes, níveis, aberturas e variações de altura vêm
do SA atual, sem coordenadas por viga. Para e Passa têm configurações independentes.
Este padrão aplica-se apenas ao Formascia LV; preserva iNi, NOVA e outras classes.
Referências cadastradas: painéis A/B, grades soltas, visão corte, moldura ABCD,
moldura de grades e índice de primeira folha Formascia.

## Painéis A/B

- Contornos verdes; números brancos em círculos vermelhos; título nome/face,
  altura 16,5 cm. Sem dimensão repetida acima do nome nem título interno.
- Sarrafos vermelhos com preenchimento vermelho e contorno editável.
  Horizontais curtos nas extremidades, de 7 até 30 cm, respeitando aberturas.
- Vazios de laje/aberturas com contorno cinza e hachura AR-CONC cinza.
- Painéis até 244 cm e ajuste de 122 cm para evitar sobra menor que 60 cm.
  Numeração contempla cada painel; medidas sempre calculadas a partir do SA.
- Cotas gerais/granulares de altura à esquerda; à direita somente as necessárias
  para aberturas e alturas diferentes. Cotas nativas, linhas ciano, texto vermelho,
  traço oblíquo e estilo FORMASCIA-PAINEL.
- Gradeadas: painéis sem grades, anotação vermelha UTILIZAR GRADE SOLTA,
  duas linhas amarelas pontilhadas a 3 e 10 cm da base, recortadas pela geometria.
  À esquerda: 7 cm entre linhas e distância ao topo. Em uma união: 10 cm até a
  base e restante até o topo.

## Grades soltas

- Família independente de painéis, contendo os mesmos cortes completos.
  N3 gera unidades nativas de painéis e grades; N5 posiciona essas unidades.
- Travessas vermelhas de 2,2 cm; montantes ACI 43, largura 3,5 cm e passo de 30 cm
  reiniciado por painel, com montantes nas extremidades. Divisões/extremidades verdes.
  Números e círculos brancos; título GRADE SOLTA e quantidade (nX).
- Segmentos de alturas diferentes são peças independentes alinhadas na base.
- Cota do primeiro passo real, sem inventar 30 cm em peça curta. Comprimentos
  dos painéis e total quando pertinente. À direita: 2,2 + altura útil + 2,2;
  mais à direita altura total. Texto fora dos pequenos intervalos.
- Quantidades agrupam geometria física igual dentro da mesma viga, preservando
  diferenças de dimensões, alturas e aberturas.

## Cortes

- Construção física/cotas usam a base geométrica NOVA com acabamento Formascia.
  Painéis sem preenchimento cinza; madeira com hachura ANSI31 vermelha.
- Sarrafeadas: sem parafuso do fundo e sem horizontal unindo os apoios longos.
  Manter sarrafos verticais amarelos e demais fixações.
- Gradeadas: montagem única de parafusos do fundo, sem duplicação grande.
  Presilhas e parafusos centrais/laterais completos; capuzes de 2,2 cm,
  grade externa e sarrafos discretos encaixados sem sobrepor a grade.
- Gradeadas sem cota da largura abaixo do fundo. Identificação b×h interna e
  demais cotas úteis permanecem. Nome proporcional ao original e uma única b×h.

## N5

- Cortes 2× com legenda CORTE — ESC. 1:25; painéis/grades 1× (1:50).
- Área útil medida na moldura: esquerda livre de 50 cm, 25 cm entre unidades
  da mesma viga, 60 cm entre vigas com separador tracejado e 45 cm entre linhas.
  Preservar carimbo/legendas e remover exemplos do template.
- Paginação em limites físicos de painel, sem reduzir escala nem criar extremidades
  construtivas artificiais. Índice identifica família, folha e vigas.
- Gradeadas geram LV_PAINEIS e LV_GRADES separadas no modelspace. Manifest registra
  unidades nativas, identidade e hash. Entidades CAD individuais e editáveis.
- Verificar auditoria DXF e abertura no AutoCAD; render web não comprova sozinho
  a integridade nativa.

## Evidências

Experimentos preservados em `scripts/arete/relatorios/`:
v04 grades/paginação; v06 painéis/cotas; v05 corte gradeado; v07 corte sarrafeado,
nas pastas `20261007_formascia_lv_v301_v304_vXX`.
