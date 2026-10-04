# Padrão Nova — N3 pilares especiais, visão CIMA

**Status: canônico — decisão de desenho do dono, 2026-10-03.**

## Autoridade, referência e limites

O dono aprovou explicitamente o CIMA em L da prévia `preview_L_v26` como padrão:
“define isso como padrão de pilares especiais em L ... perfeito esse design”.
Referência revisável: `scripts/arete/relatorios/20261002_nova_design/preview_L_v26/P26_NOVA_CIMA_L.dxf`
e `cima_L_proposta.png`. As dimensões desse exemplo não são constantes do motor.
O modelo deriva das referências DXF enviadas em Configuração de Modos / Modo Nova / Pilares.

A aprovação é do desenho em L. U/T devem aplicar os princípios a cada encontro,
mas suas prévias precisam de avaliação própria. Este registro não significa que
o motor em produção já recebeu os ajustes: as revisões v12–v26 são experimentos
isolados, e a integração requer causa G1/G2, regressão e avaliação visual.

## Entrada dinâmica e topologia

### Correção da proposta U — 2026-10-03

O dono pediu trocar D com G na proposta original do U. Ordem demonstrativa
passa a A, B, C, G, E, F, D, H, preservando as paredes físicas.
As pontas livres C e D não recebem perfil metálico. Os seis perfis laterais
mantêm contornos externo e interno completos, com parede de 1,8 cm como no L.
Painéis e sarrafos das duas pontas seguem o detalhe do L/T; as grades avançam
7 cm para fora para acomodar o prolongamento de 11 cm das chapas. Isso é
comprimento de acabamento da prévia, não constante do contorno SA.
Prévia U_v2: grades horizontais preservadas, nenhuma invasão de painéis,
folga quadradinho/parafuso de pelo menos 1 cm e passos inteiros até 46 cm
nos trechos materialmente contínuos. Continua uma proposta isolada, sem
aprovação geral do U nem integração em produção.

### Correção da proposta T — 2026-10-03

O dono corrigiu a identidade das faces do T: trocar A com H e C com E da
primeira proposta, preservando a geometria. No contorno demonstrativo, a ordem
passa a H, B, E, D, C, F, G, A. Isso é correspondência entre paredes físicas,
não regra universal baseada no índice dos vértices de qualquer SA.
O perfil metálico fica nas laterais; não fecha as três pontas livres do T.
O contorno interno do perfil deve estar completo: a referência L v26 tem
segunda linha afastada 1,8 cm de cada borda lateral, com as mesmas extremidades
longitudinais do contorno externo. A prévia T_v3 inclui os cinco pares de
contornos, sem alterar as demais entidades da T_v2.
Na revisão das pontas do T, o dono pediu o mesmo acabamento de painéis e
sarrafos das extremidades do L, com as grades do pé H descendo para acomodá-lo;
as grades do braço horizontal devem conservar sua posição. T_v4 reproduz
prolongamentos de chapa de 11 cm, apoios/retornos de sarrafo de 7 cm e estende
as grades junto a H em 7 cm. Medidas do detalhe são referência visual; o
comprimento dos braços continua vindo do contorno. Verificação: grades
horizontais preservadas e nenhuma invasão de painéis pelas grades.
A prévia `preview_UT_contour/T_v2` aplica essa correção, sem integração ao
gerador de produção e sem afirmar aprovação dos demais detalhes de U/T.

Consumir o contorno físico interpretado pelo SA (`geometry_points`, ou conversão
do `points_json`), removendo duplicados/fechamento e vértices colineares.
Preservar dimensões, orientação, espessuras locais e vínculo de cada face.
Não substituir um especial por sua bounding box nem reconstruir por nome P26.
Cada aresta física recebe faixa, letra, dimensão e tipo de encontro; L tem seis
faces e U/T ortogonais usuais têm oito. Letras devem seguir o contrato SA de faces,
não a ordem arbitrária dos vértices. O desenho não altera o schema N1.

Normal externa e tangente locais definem todos os afastamentos. Mudança de pose
deve transportar montagem, textos, perfis, grades e cotas. Escala do desenho
CIMA aprovado: 2 unidades DXF por cm; as regras abaixo são em centímetros reais.

## Painéis e encontros

- Painéis vermelhos, no tom da referência original; substituir a cor ciano/roxa
  desses painéis, sem remover o painel correto. Não remover chapa ao eliminar
  o sarrafo extra: o ajuste aprovado remove a faixa verde excedente em A/B.
- Grades, perfil metálico e cotas acompanham a redução para dentro, sem afastamento
  fixo herdado da faixa removida.
- Reproduzir divisão das chapas e pequenos prolongamentos nas pontas livres;
  não interromper a chapa antes do parafuso/grade quando a referência prolonga.
- Perfis se encontram por contato, sem sobreposição. No encontro interno, o
  vertical chega ao painel no cruze; o horizontal começa na parede direita dele.
  No externo, o horizontal ultrapassa a espessura do vertical e o vertical encosta
  sobre ele. Aplicar na base local do encontro, inclusive espelhamentos.
- Grades começam na extremidade do painel para dentro. A horizontal reserva o
  espaço do perfil/grade vertical no encontro. Recortar o início real quando
  encontra o painel perpendicular; nunca atravessar chapas/sarrafos vizinhos.

## Parafusos

Distribuir da extremidade livre em direção ao centro. Parafuso terminal a 1 cm
para fora, medido pela borda da peça quando necessário para garantir folga;
distinguir centro, meia espessura e borda na validação. Não acumular cópias ao
atualizar pontas: uma peça física por posição. Pontas iguais à referência.

Passos principais inteiros, sempre ≤50 cm; 50 é teto, não passo obrigatório.
Distribuir todos os parafusos, com tamanhos de passos equilibrados. Resíduo e
frações vão na distância até a outra extremidade, não no passo principal.
Último parafuso a pelo menos 20 cm do centro interno do cruze. Não posicionar
parafuso no cruze. Conferir relação com todos os braços no U/T.

## Grades, quadradinhos e hachuras

Distância entre grades ≥3 cm. Preferir comprimentos similares, em múltiplos de
5 cm; diferenças de uma faixa de 5 cm são preferíveis. Resíduo/fração fica nos
espaços entre grades. Não criar comprimentos de grade fracionários.

Quadradinho e parafuso: folga mínima de borda de 1 cm. Primeiro buscar solução
por comprimentos das grades e espaços; só depois deslocar quadradinho interno.
Nunca aceitar colisão para preservar uma distribuição antiga.
Quadradinhos largos apenas nas esquinas/pontas dos painéis; interiores e união
de duas grades usam quadradinho fino. Distribuição interna com estações/distâncias
inteiras e equilibradas. Hachura dos quadradinhos deve conservar o padrão da
referência (PONTALETE / MEIO PONTALETE), ajustado ao tamanho real da peça.

Texto G100/G105/G85 etc procura espaço vazio dentro da própria grade, livre de
quadradinhos e linhas dos parafusos. Deslizar pelo eixo da grade; não inventar
tamanho, deslocar a peça ou apagar obstáculos para acomodar texto.

## Letras e cotas CIMA

Todas as faces têm medida interna. **Cotas internas: somente texto**, sem linha,
patinhas ou ticks. Letras e valores A/B/E/F próximos da respectiva parede;
letra B preservada no lado direito da cota central, A no lado esquerdo.
C/D centralizadas no eixo local da parede curta; valor e letra separados.
C e D também têm cota externa. No L aprovado, D tem valor abaixo da letra;
C tem valor deslocado lateralmente para não sobrepor a letra.

Texto das cotas externas: 2,5 cm entre borda visível do texto e linha de cota,
sempre no sentido para fora do desenho. Esta regra substitui o afastamento de
3 cm solicitado antes. Linhas permanecem contínuas; não apagar trechos sob
texto como solução de layout. Deslizar rótulos na direção da própria medida para
evitar qualquer sobreposição entre textos, preservando significado/intervalo.

Texto quase branco, leve tom rosa (RGB 255/235/242), Arial Bold, em primeiro
plano e visualmente mais encorpado que as linhas rosas. Preservar altura e valor;
usar caixa real da fonte para verificar colisões.

Cor das linhas de cota: ACI 241, rosa avermelhado, igual ao CIMA comum atual
(conferido em PL_CIMA_current_P28.dxf). Substitui ACI 211 das primeiras prévias
especiais. Preservar o RGB quase branco dos textos. Prévia L_v27/U_v9/T_v10:
somente cor das linhas/layer alterada; atributos dos textos preservados.

Textos das cotas de parafusos usam a mesma altura das demais cotas externas:
4,2 cm (8,4 unidades DXF), Arial Bold e RGB 255/235/242. Padronizado nas prévias
U_v10/T_v11; o L_v27 já utiliza essa altura. Manter o offset da cadeia de cotas.

Linha de cotas dos parafusos entre total do painel e total de grades; inclui
distância à outra extremidade. Omitir as pequenas cotas de 1,5 cm para fora nas
pontas dos parafusos. Valor inicial alinhado ao primeiro parafuso, junto dele;
ajustar textos vizinhos sem mudar as medidas. Não confundir omitir a cota com
retirar/deslocar o parafuso físico.

## Outras partes aprovadas nesta conversa

ABCD: o dono rejeitou a mudança de design proposta; conservar o desenho aceito.
GRADES: mudanças aceitas. Cotar verticalmente sarrafo granular somente se possui
recorte/rebaixo em relação aos demais; igual ao total direito não precisa cota
redundante. Patinhas inferiores chegam ao desenho. Cota granular sempre à
esquerda do sarrafo, com o afastamento de 2 cm solicitado, texto livre de sarrafos
horizontais. Triângulos inferiores de extremidades seguem proporção/hachura da
referência enviada. Não transportar esse afastamento para CIMA: lá vale 2,5 cm.

## Verificação para integrar ao N3

Em 2026-10-03 o dono aprovou U_v10 e T_v11 e declarou finalizados os designs
de pilares do Modo Nova. Os DXFs aprovados foram adicionados aos exemplos
NOVA/PL da VPS, preservando o exemplo original:
U `bc6c6ab827a342f6928454bd9092dea2` e T
`2857a3f2509745b1b6dc772071d6445b`. Fontes e SVGs de visualização conferidos.
Aprovação do padrão visual e armazenamento de referências não equivalem à
integração destes protótipos ao gerador N3 de produção; os gates abaixo continuam
necessários para essa integração.

Hachuras de painéis e sarrafos, conferidas na prévia U_v3 em 2026-10-03:
CHAPA com SOLID e SARRAFO com ANSI31, ambos ACI 8, como no L aprovado.
Aplicar também aos suportes e retornos das extremidades, limitados ao contorno
real de cada peça. ANSI31 com offset (-0,5612660076; 0,5612660076) nas unidades
do DXF (2 unidades/cm). A verificação comparou as 3175 entidades anteriores:
nenhuma geometria ou texto mudou; somente 18 HATCH foram acrescentados.
Esta evidência pertence à prévia sintética, ainda não à geração N3 de produção.

Nas extremidades livres sem perfil metálico, as patinhas da cota externa devem
parar na primeira borda do desenho: retorno externo do sarrafo (offset 11 cm).
Não atravessar o sarrafo até a chapa nem começar no offset de 21 cm do perfil
ausente. Correção do dono conferida nas 4 patinhas do U_v6 e nas 6 do T_v7,
mantendo posições e valores dos textos; substitui a ancoragem à chapa de U_v4/T_v5.

Correção do dono em 2026-10-03: afastamento mínimo dos parafusos à esquina
interna é 30 cm em U/T; permanece 20 cm no L. Considerar a projeção da esquina
interna também nas faces opostas do braço, não apenas o início/fim da face
externa. Ajustes por colisão com quadradinhos não podem reduzir essa folga.
U_v5 e T_v6: nenhuma interseção entre corpos dos parafusos; espaçamentos
inteiros e máximos de 50 cm e 45 cm respectivamente. Evidência de prévia.

U_v7/T_v8 incluem cadeia de cotas dos parafusos no offset 50 cm, entre total
das grades (39 cm) e painel (61 cm). Medir os eixos reais, inclusive parafusos
gerados pela face oposta, e o restante até a extremidade. Omitir pequenas cotas
de saída de até 3 cm. Comparação confirmou todas as entidades fora de COTA
inalteradas em relação a U_v6/T_v7; DXFs sem erros de auditoria.

Revisão posterior do dono: aumentar o mínimo U/T para **35 cm**, medidos da
esquina do concreto (confirmado explicitamente), mantendo 20 cm no L.
Não alterar o posicionamento das cadeias de cotas: atualizar somente valores
e pontos correspondentes à redistribuição. U_v8/T_v9 sem colisões entre
parafusos; espaçamento máximo por trecho material 46/44 cm, inteiro; auditoria
sem erros. Esta decisão substitui o mínimo anterior de 30 cm para U/T.

Implementar por fórmula geral a partir do SA, não scripts de edição por handle.
Verificar rotações/espelhamentos, espessuras diferentes, braços curtos, vãos
estreitos e contornos fracionários. Se as restrições são inviáveis, reportar o
conflito em vez de deformar o contorno/aceitar colisão. Detectar alterações de
topologia causadas pelo offset antes de desenhar. Provar grades/painéis/perfis
sem interseção positiva, folgas reais, cotas sem sobreposição, identidade das
medidas e preservar variantes INI/outros modos. Ler PNG completo e detalhes;
rodar gates/regressão antes de publicar. A aprovação de L não sela U/T nem
certifica outros itens do pavimento.

## Cobertura das grades no N5 — decisão do dono, 2026-10-03

Todas as faces existentes A, B, C, D, E, F, G e H devem ser conferidas pela ficha SA/N3, sem presumir que todo pilar possua oito faces. C e D só recebem grade quando a largura da face é **maior que 40 cm**; 40 cm exatos não recebem. No pilar T, H também exige largura maior que 40 cm. As demais faces positivas precisam de grades.

O N5 deve verificar cada pilar, variante Para/Passa e face antes de agrupar peças geometricamente idênticas. A soma das ocorrências de cada grupo deve ser igual à quantidade de peças necessárias dos N3; todos os nomes de pilar/face ficam preservados. Falta de uma face obrigatória interrompe a geração, em vez de produzir uma unificação incompleta. Grades indevidas das faces estreitas são excluídas da montagem N5, sem alterar os DXFs de origem.

As continuações do índice ficam imediatamente após a folha do índice; todas as folhas seguintes são deslocadas e renumeradas, inclusive as referências do próprio índice. Grades individuais continuam sem numeração.
