# INI — padrão aprovado de desenho por classe

Status: canônico. Aprovação visual de pilares, laterais e fundos pelo dono em 07/10/2026; lajes configuradas por decisão explícita para serem idênticas ao NOVA. Regras detalhadas e matriz de motores: [PADROES-DESENHO-N3-N5.md](PADROES-DESENHO-N3-N5.md). Este documento substitui o estado inicial/experimental para o desenho N3 aprovado; aprovação visual não certifica todo o pavimento ou a paginação N5.

## Pilares

CIMA 2x, ABCD/EFGH e grades 1x. Compensado rosa, madeira marrom nativa, perfis laranja com bordas brancas, ferragens vermelhas. Eixos/quantidades de parafusos equivalentes ao NOVA; perfil C/D somente a partir de 40 cm de espessura. Primeiro parafuso 3,5 cm para fora com perfil lateral; abaixo de 40, 1 cm. Furação interna corresponde ao eixo CIMA, subtraindo esse afastamento do passo inicial. Pontas encostam no exterior do metal, sem interpenetração.

L segue o mesmo estilo do retangular; nomes A/B e E/F nos braços, C/D nas pontas; cotas PAINEL/GRADE/vãos/parafusos/envelope. Madeira das grades para fora do painel. C/D comuns encostados, sem quadradinhos abaixo de 40.

ABCD: furações verdes e números azuis; regra de 15 cm junto aos limites de laje/abertura/topo; SAR por painel A/B/E/F/G/H largo >244 e C/D ≥30, quantidade altura/30 arredondada. C/D sem sarrafos de elevação. Nível com ponta amarela sobre a linha, texto ciano com duas casas, sem pavimento acima e sem nuvem Formascia de 2 cm. Lajes/vazios AR-CONC 0,1, padrão reconstruído após transferência.

Grades: montantes e travessas completos onde apoiados; fechamento somente no topo real, sem quadradinhos nas extremidades. Cotas direita por face, granular e total, omitindo montante igual à altura total; vão entre grades na linha das larguras totais. C/D = espessura−10; grade 30 sem montante central, maiores com passo máximo 30. Triângulos e números azuis. N5 mantém nove células, atlas de três colunas e unificação de conjuntos equivalentes de uma face, conservando cotas/vãos e nível. Limites e teste granular em [PADROES-DESENHO-N3-N5.md](PADROES-DESENHO-N3-N5.md).

## Laterais Para e Passa

Sarrafeadas: mesma geometria NOVA, MLINE e estilo INI. Gradeadas: ferragens nativas, grades correspondentes às faces A/B, prolongamento cotado no corte e AB. Corte 2x e faces 1x. Sarrafo de fechamento 2,2 cm acima dos verticais A/B; sem painel com fundo sólido cinza. Madeira ACI 24/preenchimento 17; meios pontaletes ACI 12/preenchimento 33. Vazios/lajes cinza AR-CONC 0,1 com mesma configuração A/B. Número de painel e quantidade de pontaletes no estilo original; apoios inicial/final junto às cotas totais.

Primeiro A `VIGA.A`, primeiro B `VIGA.B`; `Cont.` apenas para outro segmento da mesma face. Essa regra também vale para NOVA. Para/Passa e as duas montagens mantêm contratos, perfis e caches independentes.

## Fundos

Contorno dos painéis branco, pressão vermelha tracejada HIDDEN nas extremidades, dois contornos abertos de 30 cm e um fechado de 20 cm, largura nominal 7 cm limitada pela geometria disponível. Numeração em círculo vermelho/texto branco. Apoios cianos rotacionados 90° a 6 cm para fora das extremidades. Segmentação, dimensões, recortes e chanfros continuam SA; não transformar pressão em sarrafo marrom preenchido.

## Lajes

INI usa a geração e o perfil **NOVA/LJ**: geometria, textos, cotas, hatches e cores iguais. Editar em **Modo Nova → Lajes**. Perfil antigo INI/LJ não modifica essa planta. Documentos de exemplo/moldura continuam separados por modo; N5 INI conserva compositor próprio. Identidade do N3 não implica identidade da moldura N5.

## Publicação e verificação

Adaptadores integrados/públicos e evidências granulares: `20261007_ini_pilares_aprovados_integracao`, `20261007_ini_lv_sarrafeadas`, `20261007_ini_fv_comparacao`, `20261007_ini_lj_nova`. DXFs já publicados precisam de nova geração para incorporar alterações; não foi solicitada nova rodada completa. Catálogo de valores absolutos só é atual com hashes e medição compatíveis; ausência de medição preserva as variações do desenho.
