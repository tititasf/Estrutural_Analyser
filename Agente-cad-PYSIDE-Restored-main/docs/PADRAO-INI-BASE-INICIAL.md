# iNi — histórico da base inicial e refinamentos

**Registro histórico. Estado atual: [padrão INI aprovado](PADRAO-INI-APROVADO.md).** As pendências abaixo descrevem cada etapa na data em que foi executada; não representam o estado atual dos desenhos N3. A matriz [N3/N5 por classe](PADROES-DESENHO-N3-N5.md) registra a correção posterior de paginação N5 e seus testes granulares.

Thierry autorizou em 07/10/2026 preparar a base das quatro classes e publicá-la
antes da revisão humana. Essa autorização é para execução e deploy; não é uma
aprovação do design. Plano: [PLANO-INI-N3-N5.md](PLANO-INI-N3-N5.md).

## Referências e limites

Os originais cadastrados de pilares, laterais Para gradeadas e fundos foram
inventariados separadamente das propostas. Há índice/moldura iNi para pilares e
índice de laterais Para. Não há referências próprias suficientes para lajes,
laterais Passa e legenda de fundos. Nesses casos a base é uma adaptação explícita
para futura revisão, sem declarar fidelidade a uma referência inexistente.

## Comportamento implementado

- Seleção explícita `INI`, arquivos/cache próprios, contratos e fingerprints;
  N5 exige unidades N3 atuais do modo, sem reutilizar arquivos de outro modo.
- Paleta própria medida nos originais: contorno branco, sarrafo ACI 24,
  componentes ACI 12/18, ferragens vermelhas, metal 255, vazios cinza,
  linhas de cota ciano e texto de cota ACI 240. MLINE preservada e editável.
- Pilares: anatomia dinâmica do SA para cima/ABCD/grades, painelização e
  numeração. Cima já é construída em 2x no N3 e transferida uma vez no N5;
  ABCD/grades em 1x. Cima/ABCD compartilham módulo, grades em módulo próprio;
  níveis chegam às paredes. Se o envelope não cabe no módulo de nove células,
  usa uma folha com área ampliada, sem reduzir escala ou atravessar divisórias.
- Laterais: perfis independentes Para/Passa, gradeadas/sarrafeadas. Corte 2x,
  faces/grades 1x; gradeadas têm famílias de painéis sem grades e grades soltas,
  com cortes. Margem útil 50, intervalos 25, linhas 45 e vigas 60 com separador.
  Unidades extensas são paginadas em divisões físicas. As grades são recortadas
  pelas divisões existentes no DXF publicado, preservando intervalos entre
  segmentos; N5 não regenera sua fabricação.
- Fundos: segmentos do contrato SA, sarrafos dinâmicos nas extremidades,
  recortes e chanfros, nomes/identificadores, numeração e cotas. Ocupação da
  folha da esquerda para direita, intervalos 35, quebra de linha/folha por
  envelope. Moldura adaptada enquanto falta referência própria.
- Lajes: planta completa coerente do SA, contornos brancos e cotas próprias.
  Escala de papel declarada 1:50, 1:100 ou 1:200 pelo envelope; sem reduzir
  escala silenciosamente. Moldura adaptada, revisão visual pendente.
- Hachuras copiadas ficam não associativas, com limites explícitos; retirar a
  marca de contorno derivado evita o erro do leitor estrito do AutoCAD.

## Isolamento e evidências

Correção de 07/10/2026: a visão cima dos pilares especiais reconhecidos pelo
adaptador Nova usa o mesmo contrato de contorno, folgas dos cantos, deduplicação,
quantidade, estações e pontas dos parafusos do Nova. A apresentação continua iNi.
Não usar a distribuição antiga das faces opostas, que duplicava hastes e
produzia estações diferentes. P26/P27 do 13_PAV: nove parafusos em cada caso,
com geometria idêntica em Para/Passa. Retangulares, ABCD e grades permanecem
no caminho anterior. Evidência: `20261007_ini_parafusos_especiais`.

Nenhum gerador STOG certificado foi editado. SA, JSONs Fase-4 e originais são
preservados. As alterações de apresentação ficam em adaptadores iNi. Os padrões
aprovados NOVA/Formascia permanecem como estavam; seus defaults foram comparados
antes/depois do deploy seletivo. Backups na VPS precedem cada publicação.

Evidências, DXFs e logs: `scripts/arete/relatorios/20261007_ini_base_integracao/`.
O relatório de entrega distingue experimento, integração, publicação e auditoria
CAD. O aceite visual de todas as classes iNi continua pendente de Thierry.


## Revisão granular aprovada — 07/10/2026

O dono aprovou os três exemplos anteriores e corrigiu o afastamento do primeiro parafuso externo no CIMA com perfil lateral: **3,5 cm**, substituindo 4,5 cm. O perfil lateral aparece a partir de 40 cm de espessura; abaixo disso o afastamento externo permanece 1 cm. A primeira furação interna de A/B/E/F/G/H deve corresponder ao eixo real do CIMA: distância entre o parafuso externo e o primeiro interno menos o afastamento externo. No exemplo com passo inicial 69 cm: 69 − 3,5 = 65,5 cm. Para uma largura de painel de 265 cm, a cadeia simétrica do experimento passou a 69 / 67 / 67 / 69, mantendo o eixo central e os extremos externos. Sempre calcular pelo SA/eixos reais, sem fixar esses valores por item.

Grades da revisão v05: cotar o vão físico entre peças da mesma face conforme o CIMA; cotas à direita por face, com cadeia comum quando duas grades pertencem à mesma face; omitir cota granular do montante igual à altura total. Fechamento horizontal somente no topo real, com pelo menos dois montantes; pontas rebaixadas não recebem fechamento no topo. Travessas intermediárias devem continuar nas outras grades da face, limitadas aos trechos apoiados por pelo menos dois montantes que alcancem a borda superior da travessa, sem atravessar o vão. Não desenhar quadradinhos ou fragmentos de montantes nos extremos das travessas.

Estado separado: regras e exemplos aprovados; ajustes v05 e correspondência 3,5 cm ainda experimentais, sem integração/publicação N3/N5 desta revisão. O exemplo L P26 foi extraído do caminho N3 atual para revisão específica, sem aprovação inferida: há sobreposições de cotas no encontro interno e diferenças visuais em relação ao retangular aprovado.

## iNi — encontros e grades C/D, revisão experimental v03 — 07/10/2026

- A cota do vão físico entre grades deve compartilhar a linha das cotas totais de largura das grades adjacentes.
- Grades C/D com largura de 30 cm usam somente os dois montantes extremos, sem montante central. Acima de 30 cm incluir montantes intermediários, mantendo o espaçamento máximo de 30 cm. Espessuras 40/50/60 cm produzem grades C/D de 30/40/50 cm, respectivamente.
- No CIMA em L, os blocos de madeira das grades ocupam a faixa externa ao painel, pelo vetor normal exterior da face; não espelhar a textura para dentro do concreto.
- No CIMA retangular, os sarrafos C e D devem encostar no painel. O experimento corrigiu a justificação central das MLINE e a transformação uniforme 2x, para escalar também a espessura nativa das multilinhas.

Evidência: `scripts/arete/relatorios/20261007_ini_encontros_v03/RELATORIO.md`. Foram verificados dez encontros painel/sarrafo, quatro alinhamentos de cotas e cinco DXFs no AutoCAD, sem erros de auditoria. Estas regras foram solicitadas pelo dono; os novos desenhos estão em revisão visual, sem aprovação presumida e sem integração/publicação N3/N5 nesta etapa.


## iNi CIMA em L — cotas e nomes, proposta v04

A referência nativa P31 distingue cotas de grade com sufixo GRADE, cotas do painel com sufixo PAINEL, vãos entre grades, cadeia de parafusos e envelope total. Preservar esses nomes ao escalar a vista 2x; os números expressam centímetros físicos. Medir o painel na CHAPA, sem confundir com o comprimento de grade. No L da referência: A/B no braço vertical, E/F no horizontal, C/D nas pontas; título do pilar com (VAR.) à esquerda. Proposta com P26 real e medidas próprias em `20261007_ini_L_cotas_v04/RELATORIO.md`; AutoCAD sem erros. Revisão visual e integração ainda pendentes.


## iNi L — contato das pontas, proposta v05

A borda interna da ponta do parafuso deve encostar na face externa do perfil metálico, sem interpenetração. Não usar o centro do bloco como ponto de contato: projetar seu envelope no eixo da haste e ajustar ao limite externo do perfil real. Manter estações, quantidade e orientação. Proposta P26 L v05: 18 contatos com folga zero, AutoCAD sem erros; evidência em `20261007_ini_L_pontas_v05/RELATORIO.md`. Integração N3/N5 pendente.


## Aprovação final e integração N3 dos pilares — 07/10/2026

Thierry aprovou o conjunto refinado («ta td aprovado agora garanta que n3 gere tudo conformme combinamos»). Esta seção substitui o estado pendente das revisões granulares acima para o N3 de pilares iNi: exemplos convertidos em adaptadores de produção, publicados na VPS e exercitados pelo serviço normal do portal.

- CIMA retangular: símbolos/texturas nativos, compensado rosa, perfis laranja com bordas brancas, parafusos vermelhos. Perfil C/D a partir de 40 cm de espessura; afastamento externo do parafuso 3,5 cm nesses casos e 1 cm abaixo disso. Sarrafos C e D abaixo de 40 encostam no compensado, sem quadradinhos de grade ou cota de grade lateral. MLINE com justificação central e transformação uniforme 2x.
- CIMA em L: madeira na normal exterior, nomes A/B no braço vertical e E/F no horizontal, C/D nas pontas, título à esquerda com VAR.; cotas PAINEL, GRADE, vãos, estações e envelope conforme a referência. A borda interna de cada ponta toca o limite externo real do perfil. P26: nove hastes e dezoito contatos com folga zero.
- ABCD: furações verdes equivalentes aos eixos reais do CIMA; excluir furo a menos de 15 cm dos limites de laje, abertura ou topo. Números dos painéis azuis, incluindo o painel de 7 cm. Texto SAR por painel para A/B/E/F/G/H com largura >244 cm e C/D com largura >=30 cm; quantidade arredondada ao inteiro mais próximo da altura/30. C/D sem sarrafos de elevação. Níveis com ponta amarela sobre a linha e valor numérico ciano de duas casas, sem nome do pavimento; sem nuvem de folga de 2 cm do Formascia. Vazios/lajes AR-CONC, escala 0,1, geometria de padrão reconstruída após transferências.
- Grades: dimensões/condições de fabricação Nova com apresentação iNi. Cotas granulares e total por face; grades da mesma face compartilham cadeia direita. Vão físico entre grades alinhado às cotas de largura total. Omitir cota do montante que repete a altura total. Topo fechado apenas no topo real apoiado por dois montantes; intermediárias completas onde suportadas, sem fragmentos nos extremos. Grades C/D com largura espessura−10; 30 cm com apenas dois extremos, acima de 30 com intermediários e espaçamento <=30 cm. Triângulos azuis com bordas brancas.

Implementação: `ini_pillar_design.py`, `ini_pillar_top.py`, `ini_pillar_elevation.py`, `ini_pillar_grades.py` e símbolos compactos nativos em `src/core/assets/ini_pillar_symbols.dxf`. O gancho genérico de furação reconhece o adaptador que já gera furações nativas, evitando duplicação. Gerador STOG certificado preservado. A publicação não substituiu motores Nova/Formascia nem dados SA/Fase-4.

Verificação: 19 vistas granulares de P1, P26 e casos de espessura 20/40/50/60, auditoria ezdxf sem erros/reparos; arquivos publicados de P26 CIMA e grades abertos no AutoCAD 2021, AUDIT 0 erros/0 correções. Portal N3: seis operações reais (P1/P26 × CIMA/ABCD-Para/Grades-Para); CIMA também publica Para/Passa. Serviço ativo, backup seletivo e verificação de drift antes do deploy. Evidência: `scripts/arete/relatorios/20261007_ini_pilares_aprovados_integracao/`. O motor está integrado para as próximas gerações; esta etapa não regenerou todo o pavimento nem pranchas N5 já existentes.


## Laterais iNi — madeira, vazios e ferragens — 07/10/2026

Revisão solicitada pelo dono: A/B usa sarrafos com linhas ACI 24 e preenchimento MLINE 17; meios pontaletes com linhas ACI 12 e preenchimento MLINE 33. Lajes e aberturas usam contorno cinza e AR-CONC nativo, escala 0,1, sem SOLID. No corte, compensado e lajes não têm preenchimento cinza. Madeira usa MLINE nativa; montantes da grade usam o preenchimento do meio pontalete e prolongamento de 20 cm abaixo da base, conforme o original registrado. Ferragens gradeadas usam símbolos extraídos do original (presilhas de fundo, chapas/porcas/rosca vermelhas e laranja, ligação interna amarela), substituindo os retângulos brancos simplificados.

Implementação restrita a ini_lv_design.py, ini_design.py, lv_ini_sa_adapter.py e ini_lv_symbols.dxf. Referências de plotagem importadas são normalizadas antes de salvar; linetype HIDDEN é materializado. Não altera geradores certificados nem os desenhos NOVA/Formascia. Teste granular V316: faces A/B e cortes nas duas montagens, relatório em 20261007_ini_lv_ajustes. Aprovação visual desta revisão permanece com o dono.
