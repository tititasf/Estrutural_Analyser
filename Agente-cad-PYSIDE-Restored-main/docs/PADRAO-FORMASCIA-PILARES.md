# Formascia — pilares aprovados

Modo MOLDE_1 / PL. Design aprovado explicitamente pelo dono: CIMA retangular e L/U/T, ABCD e grades v06. Correções de fidelidade publicadas em 2026-10-06 após os apontamentos do dono: níveis, vazios pontilhados, sarrafos cinza, distribuição/numeração e contato dos parafusos. No 13_PAV da Obra_TREINO_1, 35 pilares compõem 140 grupos em 19 folhas N5 incluindo índice; conjuntos Para/Passa publicados separadamente, 11 folhas cada. A auditoria inicial era ezdxf; o teste posterior no AutoCAD identificou XDATA sem registro e invalidou a compatibilidade dos DXFs antigos. A correção de compatibilidade foi confirmada no AutoCAD nos experimentos e na integração granular de 2026-10-06. Evidências e limitações no relatório 20261006_formascia_pilares_correcao. A validação de design não sela a interpretação estrutural SA. Laterais Para/Passa seguem pendentes e independentes.

## CIMA

Painéis e chapas verdes ACI 3; madeira/sarrafos e hachuras vermelhos ACI 1; perfis metálicos, parafusos e cotas cinza ACI 8; nomes e faces brancos ACI 7. Nome e medidas à esquerda do envelope real da montagem. Preservar divisões, encontros e faces a partir da geometria SA. Em camadas compartilhadas, a hachura sólida das chapas é verde. Os quadradinhos da madeira devem conservar os veios em arcos do original; a antiga substituição por ANSI31 foi rejeitada na correção de fidelidade. Não pintar todos os componentes pela cor de uma única camada.

## Faces A, B, C, D, E, F, G, H

Painéis verdes; sarrafos em MLINE CAD nativa, reproduzindo estilos do original. Contornos e montantes acompanham aberturas e são limitados pelo painel, sem ultrapassar as bordas externas. Faces C/D com largura inferior a 30 cm usam os conjuntos das extremidades com pernas verticais; a partir de 30 cm, inclusive, ficam somente os sarrafos horizontais nas extremidades. Nunca atravessar toda a altura do painel com esses montantes.

Cotas nativas do estilo FORMASCIA-PAINEL importado do original: linhas/extensões ciano ACI 4, texto magenta ACI 240, altura 10 cm, oblíquas 3 cm, afastamento 3 cm, precisão de no máximo uma casa sem zeros finais. Afastamentos das cadeias são calculados do envelope e cotas curtas podem usar outro nível para evitar sobreposição.

Cada face ABCD inclui a nuvem original com indicação de folga 2, posicionada pelo envelope da face. Marcadores de nível usam a seta original ACI 191, nome real do pavimento e nível absoluto amarelo ACI 2 com exatamente duas casas. Não mostrar CHEGADA/SAÍDA como rótulos nem inventar nomes ausentes. Cabeçalhos brancos PD/níveis acima da montagem são exclusivos de Nova e não aparecem em Formascia. Preservar os nomes individuais das faces.

## Grades

Triângulos nativos com envelope 15 × 15 cm: contorno branco ACI 7 independente da hachura cinza ACI 8; ancorados e espelhados pelo envelope real do conjunto. Madeira/sarrafos vermelhos e nomes brancos. Travessas regulares têm espessura 10 cm e faces inferiores a 50, 120 e 180 cm acima da madeira da base, configuradas em grade_positions_cm. Distribuir apenas onde os montantes e a altura realmente comportam o conjunto.

Adicionar fechamento superior no patamar mais alto com pelo menos dois montantes contíguos. Face superior coincidente com o topo e inferior 10 cm abaixo. Uma ponta única isolada, inclusive nas extremidades, não recebe tampa. Não ligar tampa de patamar inferior à travessa regular, evitando o degrau rejeitado. P1.B exibido na versão sem degrau está incluído na aprovação completa.

## N5

As vistas CIMA são emitidas pelo motor a 2×; ABCD e grades a 1×. Aprovação v04: preservar esses fatores, sem ampliar grades ou reduzir faces para preencher a célula. CIMA centralizado horizontalmente, ancorado ao topo, desenhado para baixo. ABCD ancorado na base, desenhado para cima, com margem inferior de 55 unidades da moldura para o envelope incluindo cotas. CIMA usa margem superior de 85. Não usar coordenadas de item: calcular pelo envelope e pelas paredes da célula. Se não couber nas escalas aprovadas, informar o excesso sem mudar a escala silenciosamente. Nome de pavimento genérico da Fase-4 não prevalece sobre o nome real em `_sa_mode_contract.n1_base`.

Usar os arquivos registrados INDICE E MOLDURA ABCD CIMA PILARES.dxf, INDICE PRIMEIRA FOLHA PILARES ACBD CIMA.dxf e INDICE GRADES PILARES.dxf. CIMA e faces agrupadas por Para/Passa; grades em suas folhas. Primeira folha mantém a legenda técnica de montagem. Índice calculado a partir dos itens efetivamente gerados, carimbo da obra/pavimento atual, numeração e escala ajustadas ao envelope. Entidades CAD individuais editáveis, incluindo MLINE, DIMENSION e HATCH. Não herdar nomes ou quantidades da obra de exemplo.

## Evidências e versões

Originais em D:/Agente-cad-PYSIDE/Exemplos Modos/FORMASCIA. Experimentos preservados em scripts/arete/relatorios/20261004_formascia_cima_experimento (retangular v01, U/T v01, L v02), 20261004_formascia_abcd_experimento (v06_folga_cd40) e 20261004_formascia_grades_experimento (v06_contorno_branco). Versões rejeitadas e histórico documental preservados. Testes e validação publicada são relatados separadamente em 20261005_formascia_integracao_vps; aprovação do experimento não sela a geração publicada.

## Encaixe de continuação — 2026-10-06

Detectar oito células úteis, excluindo o carimbo pelas etiquetas Obra/Folha. O limite superior da célula inferior esquerda vem da borda da faixa intermediária, e não da base das demais células inferiores. Campos ausentes no carimbo de continuação usam as posições da primeira folha registrada, com conferência de dimensões da moldura.

## Correção de fidelidade — 2026-10-06 (motor publicado)

A aprovação dos experimentos permanece. A correção foi publicada na VPS e regenerada pelo runner granular do portal: 35 pilares, 175 chamadas, 210 DXFs N3 com CIMA duplicada nos conjuntos Para/Passa, preservando os payloads SA. O motor N5 do portal gerou 19 folhas combinadas e 11 por conjunto. Auditoria de 254 DXFs sem erros/correções; 70 ABCD passaram nas verificações de níveis, numeração, hachuras e sarrafos. Renders efetivos P1 e folhas de índice, ABCD/CIMA e grades foram comparados visualmente. Evidências: scripts/arete/relatorios/20261006_formascia_pilares_correcao. A execução pelo botão N5 concluiu com HTTP 200, release dc93aa8a-559d-4bab-ae6c-1c8b429c2741; as 11 folhas de cada conjunto foram carregadas no portal e os 254 DXFs dessa execução foram auditados. A aprovação final do N5 permanece pendente do usuário; a aprovação do design não sela a interpretação SA.

- Preservar as duas linhas de nível horizontais, atravessando o conjunto inteiro ABCD, nas alturas reais do motor.
- Vazios de lajes e aberturas: HATCH AR-CONC cinza ACI 8, escala 0,1 e ângulo 0; nunca SOLID. Sarrafos de topo/abertura são MLINE com preenchimento próprio cinza; não confundir as duas representações.
- A/B: módulos lógicos de 122 cm mais sobra, sobre a altura útil confirmada pelo SA, sem inserir juntas no fundo de recortes. C/D conservam a distribuição contínua até 244 cm. Uniões explícitas de fabricação devem conservar suas partes e totais.
- Numerar cada painel lógico de baixo para cima; círculo vermelho e texto branco, colocados dentro da área sólida restante após os recortes. A numeração acompanha qualquer divisão nova.
- CIMA: contorno dos parafusos cinza ACI 8, com as pontas nativas do bloco C do original, encostadas nas faces externas reais do perfil metálico; as hastes terminam nesse contato, sem afastamento. Quadrados das grades usam os veios em arcos dos blocos de madeira corte do original; não substituir por ANSI31.
- O detalhe simbólico vem de config/formascia/cima_details.dxf; posições, dimensões e quantidades vêm do desenho do motor, sem coordenadas fixas por item.
- O contato é calculado pela interseção do eixo da haste com os perfis perpendiculares; perfis paralelos próximos em cantos L não alteram o encaixe. Sem um par de perfis, conservar a haste original. Verificação geométrica de 376 grupos em 92 variantes SA.
- A prévia PL seleciona Formascia quando solicitado pela URL e quando o DXF pertence à pasta MOLDE_1; metadados SA Nova de outras vistas não mudam a identidade do desenho.


## Montagem e compatibilidade aprovadas — v04, 2026-10-06

N3 inclui os marcadores nativos de nível também nas grades: seta na cor original, nome real do pavimento e nível absoluto com duas casas. Datum vertical vem do SA, não da extremidade de um montante encurtado. No N3 as linhas atravessam o envelope da montagem; no N5 chegam às paredes reais da moldura. ABCD ocupa a mesma célula de CIMA. Grades ficam lado a lado e alinhadas pela base, nas folhas de grades respectivas. Nessas folhas, sem divisórias internas, a linha atravessa a faixa inteira até as paredes da moldura; limites virtuais de distribuição não cortam a linha. As cotas mais baixas definem a margem de segurança comum das bases do conjunto.

Preservar MLINE e seus estilos com o número original de elementos. Registrar todos os APPIDs dos símbolos copiados (incluindo RevcloudProps e GradientColor1ACI/GradientColor2ACI), remapear recursos de layer inválidos e não carregar vínculos de hachura apontando para entidades de outra folha. Folga e hachuras permanecem editáveis. A abertura no AutoCAD e AUDIT sem correções são verificações adicionais à auditoria ezdxf; uma não substitui a outra.

Aprovação do desenho: folha experimental v04. Integração: relatório scripts/arete/relatorios/20261006_formascia_layout_integracao. Os DXFs N5 antigos não são regenerados por simples publicação do código; a compatibilidade e o posicionamento da geração completa permanecem sem verificação enquanto não houver rodada autorizada do pavimento.

## Cor nativa e textos de montagem — 2026-10-06

Não acrescentar títulos de robô como P1 — Para/Passa, CIMA 2× · ABCD 1× ou GRADES 1× nas células. Preservar nomes dos itens, faces, índice e carimbo. Sarrafos de topo e abertura ABCD usam o estilo exclusivo FORMASCIA-PL-SARRAFO-CINZA: preenchimento e elementos ACI 8 explícitos, sem BYLAYER. A camada importada da moldura pode ser vermelha; sua cor não pode alterar esses sarrafos. SAR15 mantém seu preenchimento cinza e contorno branco nativos. Madeira vermelha de CIMA, grades e fundos não é alterada.

## Painel acima da laje e hachura — 2026-10-06

A faixa acima do vazio de laje é um painel independente e recebe seu próximo número na sequência de baixo para cima, inclusive quando sua altura é pequena (7 cm no P1 confirmado pelo dono). Dividir a contagem pelo topo do vazio, calculado com rebaixo_laje e vazio_laje da face; não fixar 7 cm ou coordenadas por item. Aberturas parciais mantêm a numeração do painel lógico. Ajustar o círculo e o texto pela altura disponível da faixa. Vazios de lajes e aberturas: AR-CONC cinza ACI 8, Pattern Scale 0,1, ângulo zero.

## Coerência do padrão HATCH no N5 — 2026-10-06

As linhas da definição AR-CONC gravadas no DXF devem corresponder ao Pattern Scale 0,1 declarado. A biblioteca ezdxf instalada reaplicava esse fator ao transformar o hatch, mesmo com translação apenas, reduzindo o espaçamento 10 vezes na folha e 100 vezes no unificado. O AutoCAD recompunha o padrão ao editar o hatch; AUDIT sem erros não detectava essa incoerência. Após cada montagem PL, reconstruir somente a definição dos vazios FORMASCIA-VAZIOS a partir da escala e ângulo declarados, preservando seus contornos e entidades individuais. Validar os dados do padrão antes e depois de HATCHEDIT no AutoCAD, incluindo a folha unificada. Não alterar os padrões das legendas ou outros modos/classes.

## Cota total das grades — 2026-10-06

Somente a grade mais à direita recebe a cota vertical de altura total, posicionada à direita das cadeias existentes. Medir da base dos montantes, acima da madeira inferior, até o topo máximo dessa grade. Suprimir cotas granulares de sarrafos que repitam essa medida total; preservar cotas de montantes mais baixos e segmentos distintos. Calcular seleção, medida e afastamento pelos envelopes efetivos, sem coordenadas por item.

## Cadeia vertical das travessas — 2026-10-06

As cotas das travessas devem ser reconstruídas após a redistribuição Formascia, usando as faces inferiores e superiores dos horizontais efetivamente desenhados na última grade. Incluir fechamento superior quando existir; pontas isoladas não criam tampa nem intervalos fictícios. Unir intervalos verticais coincidentes ou sobrepostos antes de cotar. Não conservar a cadeia antiga do gerador se ela usar outra distribuição. A soma dos segmentos deve coincidir com a altura total; preservar cotas dos montantes de outras alturas e o total externo único.
