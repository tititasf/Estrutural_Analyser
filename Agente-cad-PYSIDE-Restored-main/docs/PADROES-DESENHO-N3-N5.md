# Padrões de desenho N3/N5 — INI, NOVA e Formascia

Status: canônico. Consolidado em 07/10/2026 a partir das decisões do dono, adaptadores atuais e evidências granulares. Esta matriz governa a apresentação; dimensões, apoios, níveis e aberturas continuam vindo do contrato SA. Aprovação do estilo não certifica a interpretação estrutural de todos os itens nem atualiza DXFs já gerados.

## Matriz dos três modos e quatro classes

| Classe | NOVA | INI | Formascia (`MOLDE_1`) |
|---|---|---|---|
| PIL / PL | CIMA, ABCD/EFGH e grades; distribuição de ferragens e fabricação de grades de referência | Mesmos eixos de parafusos/fabricação, apresentação nativa INI, furações equivalentes ao CIMA; detalhes abaixo | CIMA 2x, faces/grades 1x, símbolos e paleta Formascia; [padrão próprio](PADRAO-FORMASCIA-PILARES.md) |
| LV Para e Passa | AB e corte; sarrafeadas e gradeadas; [padrão aprovado](PADRAO-NOVA-LATERAIS-APROVADO.md) | Geometria sarrafeada NOVA com madeira MLINE e estilo INI; gradeadas com prolongamentos, identificação e ferragens nativas | Painéis sem grades e grades soltas em famílias independentes, com corte em ambas; [padrão aprovado](PADRAO-FORMASCIA-LATERAIS-APROVADO.md) |
| FV | Segmentos de fundo e seus apoios, contorno, numeração e cotas derivados do SA | Contorno branco, pressão vermelha tracejada nas extremidades, círculos vermelhos/números brancos, apoios cianos 6 cm para fora | Madeira MLINE vermelha, painéis verdes e encaixes próprios; [padrão aprovado](PADRAO-FORMASCIA-FUNDOS.md) |
| LAJ / LJ | Planta, painéis, reutilização, obstáculos e cotas NOVA | **Desenho N3 idêntico ao NOVA**, inclusive configurações geométricas e visuais NOVA | Planta e paginação Formascia; [padrão aprovado](PADRAO-FORMASCIA-LAJES.md) |

Para/Passa são contratos e perfis independentes; não são classes estruturais novas. Gradeadas/sarrafeadas são montagens distintas. MOLDE_2/3 não foram revisados neste escopo.

## Pilares INI — regras finais aprovadas

CIMA usa compensado rosa, madeira marrom/textura nativa, perfis laranja com bordas brancas e ferragens vermelhas. L usa a mesma linguagem do retangular, com madeira na normal exterior, nomes A/B no braço vertical, E/F no horizontal, C/D nas pontas e título VAR. à esquerda. Cotas distinguem PAINEL, GRADE, vão, estações de parafuso e envelope. A base da ponta do parafuso toca a face externa do perfil, sem entrar nele.

O perfil lateral C/D depende da **espessura**, não do comprimento: a partir de 40 cm. Afastamento externo do primeiro parafuso: **3,5 cm** com perfil lateral; **1 cm** abaixo de 40. Furação de A/B/E/F/G/H acompanha os mesmos eixos físicos: passo externo menos esse afastamento. Exemplo 69 − 3,5 = 65,5 cm; não fixar o exemplo no motor. Abaixo de 40, C/D têm sarrafos comuns encostados no painel, sem quadradinhos/cota de grade lateral.

ABCD/EFGH: números azuis, furações verdes, sem sarrafos de elevação C/D. Excluir furação a menos de 15 cm de laje, abertura ou topo conforme os limites do contrato. Texto SAR por painel: A/B/E/F/G/H quando largura >244 cm; C/D quando largura ≥30 cm; quantidade = altura/30 arredondada ao inteiro mais próximo. Painel superior de 7 cm é contado e numerado. Ponta amarela do nível sobre a linha; número ciano com duas casas, sem nome do pavimento. Não desenhar a nuvem de folga de 2 cm do Formascia. Vazios/lajes usam AR-CONC 0,1, sem preenchimento sólido.

Grades: apresentação INI com madeira marrom, números e triângulos azuis, bordas brancas; cotas cianas/textos conforme o original. Cada face tem cadeia direita granular e total; duas grades da mesma face compartilham a cadeia. Omitir granular do montante quando repete a altura total. Cotar o vão físico entre grades na mesma linha das larguras totais, consistente com CIMA. Travessa de topo somente no topo real apoiado por dois montantes; pontas rebaixadas não recebem fechamento artificial. Travessas intermediárias continuam nas peças suportadas, sem atravessar vãos e sem quadradinhos nas extremidades. Grades C/D têm largura espessura−10: 40/50/60 → 30/40/50; 30 cm usa somente extremos, maiores incluem intermediários com passo ≤30.

## Laterais — nomes, madeira e prolongamentos

NOVA e INI: primeiro segmento A = `V316.A`, primeiro B = `V316.B`; `Cont. V316.A`/`Cont. V316.B` somente para outro segmento **da mesma face**. B nunca é continuação de A. A/B mantêm a mesma configuração física de hatch cinza de lajes/aberturas, inclusive após transferências.

INI sarrafeadas seguem a anatomia NOVA, usando MLINE nativa e paleta INI. No corte há fechamento horizontal de **2,2 cm** acima dos verticais A/B nos dois modos. Painéis do corte INI não têm fundo sólido cinza. Gradeadas usam ferragens nativas do original, sem duplicar parafusos de fundo nem sobrepor sarrafos às grades. A representação de cada grade no corte corresponde à grade de sua face A/B. Prolongamentos abaixo do painel têm cota própria por lado no corte e em AB.

INI AB: sarrafos ACI 24/preenchimento MLINE 17; meios pontaletes ACI 12/preenchimento 33. Numeração no estilo original: círculo vermelho/número branco, quantidade de meios pontaletes quando aplicável, apoios inicial/final ao lado das cotas totais. Vazios/lajes cinza AR-CONC 0,1; copiar somente o scale sem reconstruir o padrão não basta. Estilos e espessuras MLINE devem acompanhar a geometria real, inclusive 2,2 cm.

## Fundos INI

Preservar segmentos, recortes, chanfros e apoios do SA. Linha dos painéis branca, inclusive entidades com cor explícita; pressão vermelha tracejada (`Sarrafo de pressão`, HIDDEN), não madeira preenchida genérica. Cada extremidade usa dois contornos abertos de 30 cm e um fechado de 20 cm, com largura de 7 cm conforme o desenho original. Numeração: círculo vermelho, texto branco. Apoios: ciano, rotacionados 90°, a 6 cm para o exterior da extremidade (3 cm originais + ajuste de 3 cm). Os valores geométricos são derivados do painel, não da imagem demonstrativa.

## N3 e N5 — responsabilidades e limites

N3 desenha unidades granulares; N5 compõe os DXFs atuais, conservando escalas e recursos CAD. CIMA/corte 2x e faces/grades 1x não devem ser multiplicados novamente na transferência. Não redesenhar a fabricação no packer. N5 requer unidades atuais compatíveis com modo/montagem/contrato; mudança de código/perfil requer nova geração, não reutilização de cache antigo.

Pilares INI: nove células por grande moldura; três grandes molduras por linha, a quarta abaixo da primeira. Especiais ocupam três células (CIMA, ABCD, EFGH), sem romper a grade de nove. O compositor `ini_pillar_pagination.py` mantém escala nativa e recusa envelopes que atravessem as paredes. Retangulares largos podem separar AB/CD em células próprias. Grades equivalentes são unificadas por conjunto de face, geometria, numeração, cotas e nível; nomes são reunidos, grupos separados por linha vertical e faixa de nível mantida. Grades pareadas conservam vão e cotas da face; não se deduplicam peças isoladas entre conjuntos diferentes. Validação granular P1/P26/EX40: duas grandes molduras, nove conjuntos únicos de dez ocorrências, sem reparos DXF; fixture de quatro molduras confirma três colunas. Evidência: `20261007_ini_pendencias/verificacao_n5.json`. Não é certificação do pavimento completo.

Laterais: corte 2x, faces 1x, margem esquerda 50, intervalo entre unidades 25, linhas 45; entre vigas 60 com separador. Gradeadas Formascia mantêm LV_PAINEIS/LV_GRADES separados no espaço final, com cortes correspondentes. Fundos usam fluxo compacto do alto à esquerda para a direita, descendo quando o próximo envelope não cabe; evitar títulos internos de robôs. Lajes INI compartilham **N3** NOVA; o compositor/índice N5 INI continua próprio e não é uma promessa de moldura NOVA idêntica.

## Configurações e campos

Fonte funcional: `scripts/drawing_mode_config.py`, `drawing_semantics.py`, `visual_modes.py`; store `portal_runtime/drawing_mode_settings.json`. Componentes/textos/hatches/cotas são funções, não uma garantia de que todas aparecem em toda amostra. MLINE contém linhas e preenchimento próprios; cor de layer não necessariamente substitui cor explícita da entidade. Recursos nativos/símbolos podem não corresponder aos nomes do catálogo antigo do gerador STOG.

INI/LJ consome o perfil **NOVA/LJ** na geração. Alterações para as duas plantas devem ser feitas em NOVA → Lajes; um perfil INI/LJ salvo anteriormente não governa essa planta. Documentos de exemplo/moldura permanecem separados por modo. Referências enviadas não substituem automaticamente algoritmos ou templates calibrados; o caminho N5 nativo e seus hashes determinam o template efetivo.

Valores medidos só são apresentados como atuais quando os hashes do catálogo conferem. Catálogo desatualizado não autoriza revalidar hashes de medições antigas; manter PRESERVAR/−1 e explicitar a ausência de medição atual. Reconstrução de 07/10: `build_current_drawing_defaults.py --approved-adapters`, quinze perfis INI/NOVA/Formascia medidos pelos adaptadores SA aprovados e caminhos atuais. PARA/PASSA usam a amostra V316 para calibrar apresentação; não certificam interpretação de todas as vigas PASSA. MOLDE_2/3 ficaram fora desta medição. Planos e relatórios experimentais não vencem esta consolidação e os padrões aprovados específicos.

## Caminhos e evidências

| Classe | Implementação de apresentação/encaixe |
|---|---|
| PIL | `ini_pillar_design.py`, `ini_pillar_top.py`, `ini_pillar_elevation.py`, `ini_pillar_grades.py`, `pillar_nova_design.py`, `formascia_design.py`; `n5_pillar_frames.py`, `n5_ini_frames.py`, `n5_formascia_frames.py` |
| LV | `lv_nova_design.py`, `ini_design.py`, `ini_lv_design.py`, `lv_ini_sa_adapter.py`, `lv_formascia_design.py`; `lv_ini_packer.py`, `lv_formascia_packer.py`, `n5_lateral_frames.py` |
| FV | `scripts/arete/fv_ini_draw.py`, `ini_fv_design.py`, `formascia_design.py`; `n5_beam_frames.py`, `n5_ini_frames.py`, `n5_formascia_frames.py` |
| LAJ | `gerar_lj_dxf_stog.py`, `visual_modes.py`, `drawing_mode_config.py`, `formascia_design.py`; `n5_ini_frames.py`, `n5_formascia_frames.py` |

Evidências em `scripts/arete/relatorios/`: `20261007_ini_pilares_aprovados_integracao`, `20261007_ini_lv_mlines_numeracao`, `20261007_ini_lv_sarrafeadas`, `20261007_ini_fv_comparacao`, `20261007_ini_lj_nova`. L301 INI/NOVA: comparação de entidades e recursos iguais exceto timestamp de criação; FV V301: geração granular real na VPS. Esses testes não representam uma regeneração completa do pavimento.
