# Estilos estruturais — interpretação integrada PIL, LAJ, FV, LV e cortes

**Status:** canônico · **Data:** 2026-10-08 · **Escopo:** global, com evidência local e limites explícitos

Consolidação ESTILO-INTEGRADO-20261008, solicitada pelo dono. Origem: Obra_TREINO_1, TIPO_TESTE, EST-PE-007-TIPO-R01/torre_1. DXF SHA256 `80b45ff3e024ebe037fe6e6e52829216120f006c55f6b60f79adb1df2dc65641`. Este caso amplia as convenções reconhecidas; não certifica todos os estilos estruturais. Os manuais [PIL](../SA-ANALISE/CLASSES/PIL.md), [LAJ](../SA-ANALISE/CLASSES/LAJ.md), [FV](../SA-ANALISE/CLASSES/FV.md), [LV](../SA-ANALISE/CLASSES/LV.md) e a [biblioteca de objetos](BIBLIOTECA-OBJETOS-CAD.md) conservam os contratos detalhados. Resultados datados são evidência de uma rodada, não inventário atual.

## Reconhecimento por obra e cooperação sem prova circular

Inventariar entidades CAD com handles, camada, tipo, pontos, preenchimento, orientação, dimensões e relações espaciais. Identificar convenções recorrentes entre objetos com dimensões e identificação independentes. Camada e cor são pistas; proximidade ou maioria isolada não provam classe. Uma obra pode usar convenções diferentes para pilares que seguem, nascem ou morrem: não atribuir esse significado apenas pelo preenchimento.

Após a primeira busca, revisar associações discrepantes usando a convenção predominante e candidatos reais ainda disponíveis. Garantir posse única da geometria; dois nomes próximos não autorizam duplicação. Formas minoritárias válidas continuam candidatas. Empates ou falta de evidência conservam pendência; decisões humanas protegidas não são substituídas automaticamente.

Compartilhar contexto entre classes para verificar contatos e contradições, mantendo a origem de cada fato. PIL delimita a região LAJ, LAJ fornece contato local à LV, FV ajuda a localizar corpo e encontros: isso é consistência, não três provas quando todos derivam da mesma entidade. Não confirmar A por B e B por A. Alteração de contorno/apoio exige reavaliar relações dependentes; não propagar fichas ou contatos antigos como verdade nova.

## Objetos de corte e chamadas gráficas

Visão de corte é anotação de perfil/espessura/desnível: não é pilar, parede da planta, apoio, obstáculo sólido nem divisor físico. Não recorta laje, não fragmenta fundo, não secciona lateral e não bloqueia preenchimento de encontro só porque o desenho cruza a viga. Seu conteúdo dimensional permanece disponível para interpretar o perfil.

Reconhecer entidades pela semântica da fonte e composição geométrica antes de perder camada/handle na conversão em linhas. Camadas SECTION/CORTE/CUT/SECAO/LINHA-SE são pistas deste reconhecedor; nomes danificados também exigem assinatura preservada. Não transformar essa lista em convenção universal. Excluir apenas entidades reconhecidas: linha estrutural independente coincidente com um corte continua válida. Não mascarar todo o entorno do símbolo.

Retângulos fechados ortogonais encostados podem formar T/L, vigas conectadas e degraus. Particionar por corpos e contatos reais sem unir lacunas, sem alterar os pontos do DXF e sem confundir desenho composto com um único pilar. Uma ponte compartilhada pode ter atribuição visual particionada; isso não determina propriedade estrutural nem sua medida de forma.

Líder comprovado desloca a referência de h= para a ponta, em vez de usar a posição do texto. Chamada BL.1/h=45 é contexto de bloco, não semente automática da laje que contém o texto. Setas múltiplas ou polilinha simples sem assinatura suficiente não autorizam realocação. Referência: `cad_object_recognition.thickness_references` e biblioteca CAD.

## LAJ — regiões internas, hatch e nomes

Traçar lajes pelas faces físicas de vigas e pilares, verificando contorno e interior. Laje não atravessa parede estrutural de viga/pilar; retornos curtos continuam paredes. Cotas, strokes de hatch e símbolos de corte não são fronteiras estruturais. Recortar por pilares reais; não por geometria apenas próxima a uma etiqueta P. Não fechar lacunas reais com tolerância arbitrária e não aceitar linha estrutural pendurada no interior da célula.

Hatch listrado pode ser repetição de linhas, mesmo sem entidade HATCH no DXF. Com delimitadores reais, sinaliza região de atenção para possível mudança de espessura, degrau ou nível. Associar h= à região correta, separando principal e interna. Hatch sozinho não prova altitude, fundo contínuo ou degrau de nível; espessura diferente não determina diferença de nível. Sem prova local adequada manter nível desconhecido.

Sem nomes observados, gerar apenas L1, L2, L3, em filas da esquerda para a direita e de cima para baixo. Preservar rótulos existentes e identidade geométrica separada do nome. A instrução inicial com sufixo de pavimento foi revogada por LAJ-OBJETOS-NOMES-REV2-20261008; não reutilizar L1_TIPO_TESTE em novas interpretações.

## PIL — sólidos recorrentes, U e círculo

Associar etiqueta e dimensões à seção fonte compatível. No caso observado, sólido cinza de MTH-PILAR-SEGUE foi confundido com peça de corte/viga próxima. Segunda passada por dimensão, semântica e recorrência corrigiu nove associações; esses nomes/camadas/coordenadas são exemplos, nunca constantes do motor.

Contorno em U conserva concavidade, braços e vazio: não substituir por bbox retangular nem T. P12 envolve os elevadores. A forma especial reconhecida não autoriza publicar quatro faces artificiais se o método de desenho físico não existe.

Pilar circular permanece listado no SA com centro, raio, diâmetro, perímetro e área. Registrar contato real com viga, ponto/intervalo e ângulo CAD (0° no eixo +X, anti-horário), fonte e eventual sobreposição. P21 Ø60 foi observado livre dentro do bloco: estar dentro de bloco não prova contato com viga. Quando não existe método N3/CIMA/ABCD circular, omitir apenas a geração não suportada e explicitar pendência; outros pilares continuam elegíveis ao N5. Reconhecimento geométrico não preenche níveis ou ficha completa por suposição.

## LV — encontros, transições e canto externo

Passa percorre a parede externa do pilar, mas termina na primeira face de viga de profundidade igual ou maior, inclusive depois do intervalo inicial. Não reaparece fragmento depois do bloqueio. Viga menos profunda segue a regra de passagem por baixo; aplicar profundidade e nível locais, sem generalizar só pela etiqueta global. Continuação geométrica interna ao sólido do pilar não é viga incidente física que bloqueia essa passagem.

Seccionar na transição física laje↔degrau, laje↔vazio e degrau↔vazio. Usar união dos intervalos de contato com cada face; contatos sobrepostos/adjacentes não criam vazio. Degrau interno sem tocar a face não divide LV. Limite truncado da cena não prova borda física. Trechos curtos reais permanecem; preservar cobertura e extremos, numerando em ordem do lado. A divisão não altera sozinha o datum da viga.

Em canto em L, laterais externas Para/Passa chegam ao canto externo completo com parede estrutural contínua e largura da perpendicular medidas. Faces internas continuam obedecendo ao encontro. Não extrapolar a T/cruzamento, cota ou parede sem continuidade. Caso V516/V526: quatro extensões localizadas validadas; não copiar o fundo como lei universal da lateral.

## FV — paredes, apoios e seção local

Faixa pertence ao intervalo axial do par de paredes junto ao rótulo; par remoto não vence por distância transversal. Reconstruir retângulo automático deslocado pelas paredes medidas e preservar geometrias humanas. Reassociar apoio somente com identificação/dimensão independentes. Cauda além de apoio exige par de paredes e chamada local compatível; o pilar mantém sua área.

Cruzamento ortogonal sem divisória física pode redistribuir ocupação reduzindo painéis, preservando área, alturas locais, apoios e decisões humanas. Divisória real, abertura, mudança de nível/seção ou risco físico vetam união/troca. Uma costura automática não vira painel físico só por haver textos dimensionais distintos: conservar referências locais e pendência quando a transição não foi localizada. Não homogeneizar seção local pela dimensão global da viga.

Vão sem repetição do nome do outro lado do apoio pode ser recuperado pelo inventário FV/LV apenas com paredes fonte, chamada local, apoio sólido e único trecho adjacente identificado da mesma seção. Nome concorrente, seção diferente ou decisão protegida vetam associação. Visão de corte não é máscara de sólido.

Adendo 10/10/2026: uma mudança de largura pode atravessar o apoio com altura
declarada igual e parede longitudinal comum, quando o apoio cobre as duas
faixas e ambas as paredes novas saem da sua face oposta. Somente nessa
transição física de largura recortar antes do veto inicial de sobreposição;
exigir chamada local no trecho novo e dono único. Para a mesma largura e
seção, manter o veto da extensão bruta sobreposta e a exigência de término
na face do apoio, preservando a união completa dos fundos e seus cantos.
Conservar larguras locais e o sólido do apoio. O gate de linhas deve receber
os apoios reais; etiqueta de recuperação não substitui prova geométrica.
Detalhes e contraprovas em `docs/SA-ANALISE/CLASSES/FV.md`, seção de mudança
de largura através do apoio.

Canto diagonal com retorno já reconhecido: o retângulo contido na faixa do
retorno não recebe o fechamento do corpo angular. Escolher o corpo que
chega ao canto, independentemente do índice do painel, e conservar a união
completa da geometria; dois painéis não podem deixar a cunha entre as pontas
oblíquas descoberta. Contraprova e controles em FV.md, seção de canto
diagonal com retorno retangular já reconhecido.

## Visão de cortes — medidas úteis e apresentação vigente

Título acompanha o eixo de largura do corpo, rotacionado corretamente e fora do contorno completo. Medir largura do fundo, altura total do corpo, espessura das lajes e alturas livres das paredes acima/abaixo dos contatos. Usar somente peças fonte atribuídas ao corte e conservar contornos originais. Desnível relativo medido não fabrica nível absoluto; anotação incompatível exige conferência.

Não cotar extensão gráfica do braço para dentro da laje. A extensão fica na geometria, inclusive pontes compartilhadas; a orientação anterior sobre cotar essas extensões foi corrigida por VC-COTAS-UTEIS-20261008. Cota de parede fica perto da própria face, independentemente do alcance do braço (margem atual 8 cm no desenho em cm). Cota total fica 4 cm mais externa que a faixa granular/laje (12 cm versus 8 cm), também nos cortes rotacionados. Isto é apresentação de cotas, não mudança dimensional/geométrica.

## Evidências e lacunas — consultar antes de promover confiança

| Tema | Evidência datada em scripts/arete/relatorios/ | Limite a manter |
|---|---|---|
| LAJ internas, nomes, cortes e líderes | 20261008_lajes_tipo_contexto; 20261008_lajes_cortes_callouts | hatch não prova nível; novas convenções exigem contraprovas |
| PIL segunda passada, U, círculo | 20261008_pilares_associacao/RELATORIO.md | associação validada não é PASS completo das fichas; vínculos/níveis de P14 e faces U pendentes |
| LV cortes não seccionam | 20261008_lv_corte_seccionamento | preservar divisor estrutural coincidente |
| Passa encontra viga após pilar | 20261008_lv_passa_end_junction | seção/profundidade e contato físico locais |
| LAJ/degrau/vazio | 20261008_lv_laje_vazio/RELATORIO.md | V519: fronteira validada, associação laje/vazio diverge do comentário humano; revisar LAJ |
| Canto externo | 20261008_lv_canto_externo/RESULTADO.md | valida SA, não certifica N3/N5 |
| FV paredes, encontros e seção local | 20261008_fv_missing_crossings, recibos CONTINUIDADE/V514/V517 | não uniformizar altura sem transição provada |
| Cortes fonte conectados | 20261008_connected_sections/RELATORIO.md | particionamento geométrico não aprova vínculos nem nível absoluto |
| Cotas atuais | 20261008_vc_cotas_uteis; 20261008_vc_cotas_proximas; 20261008_vc_total_externa | 55 cortes e 80 cotas de parede auditados naquela rodada; não inventário vivo |

Pendências explícitas: método de desenho circular e faces especiais U; validação completa de vínculos/níveis/fichas após reassociação; vínculo de cada corte ao segmento local; casos de hatch/nível sem altitude independente; estilos não vistos. Aumentar cobertura de conhecimento não equivale a corrigir todas essas pendências no motor.

## Procedimento reutilizável para a próxima obra

1. Recuperar este guia, biblioteca e manual da classe pelo RAG; abrir fontes e localizar evidência CAD da nova obra.
2. Inventariar convenções e candidatos com identificação/dimensões independentes; distinguir plano estrutural de anotação e detalhe.
3. Fazer busca inicial e revisão por recorrência com posse única, preservando minorias e abstenção.
4. Conferir classes em conjunto sem ciclos de prova; mapear dependências para reavaliar contatos quando geometria mudar.
5. Validar casos positivos e negativos: corte coincidente com parede real, rotações/translações, dupla etiqueta, forma minoritária, U/círculo, mudança real de seção, vazio e canto externo.
6. Registrar versão, handles, hash, fonte humana, medições e PNG local; verificar conservação da área/cobertura, apoios, geometria protegida e pendências. Executar o loop canônico adequado se houver mudança de motor.
7. Alimentar documento canônico e biblioteca com assinatura e contraprovas, indexar e testar recuperação. T1 exige validação humana em uma obra; T2 exige consolidação em ao menos duas obras. Solicitação/regra aprovada não certifica automaticamente cada item; hipótese permanece explicitamente hipótese.

RAG é memória recuperável, não treinamento automático nem prova suficiente. Os reconhecedores determinísticos e o QA precisam consumir e validar a evidência local. Sem segunda obra validada não declarar este estilo universalmente certificado.

## LV-AJUSTES-PONTAS-20261008 — revisão dos ajustes por extremidade

Contrato canônico: [LV — ajustes de ponta e tags de revisão SA](../SA-ANALISE/CLASSES/LV.md#lv-ajustes-pontas-20261008--ajustes-de-ponta-e-tags-de-revisão-sa). Abrange Para/Passa A/B, sentido local início/fim, sinais explícitos, valor desconhecido distinto de zero, origem no SA distinta do recuo N3 e disposição alinhada/empilhada. É anotação gerada pelo portal para revisar interpretação, não uma convenção gráfica do DXF fonte. Não acrescentar essas tags à biblioteca de objetos CAD como evidência de geometria estrutural.

Harmonia deste chat: regras de lajes L1/L2 sem sufixo, limites entre vigas/pilares, hatch como atenção; pilares por convenção recorrente e dimensões com segunda passada, U e circular; cortes como anotação sem barreira física; laterais com encontros reais, laje/degrau/vazio e cantos externos; cotas úteis de parede/laje/fundo e total 4 cm mais externa permanecem nas seções anteriores. A solicitação isolada sobre VF3 foi retirada pelo dono por ter sido feita no chat errado; não é nova decisão confirmada deste chat. Associação V519, níveis P14, geração U/circular e zeros de ajuste Passa permanecem dependentes de validação própria. Um estilo recorrente nesta obra fornece contexto para outras obras, não certificação universal nem prova circular entre classes.

## CHAT-CONSOLIDACAO-20261008 — integridade e desempenho

Complemento vigente: [Aprendizados do portal — integridade, interpretação e desempenho](APRENDIZADOS-PORTAL-INTEGRIDADE-PERFORMANCE.md). Inclui recorte sem perda, cotas explodidas, corte não segmentando FV/LV, listas sem duplicação, cadeia com pendências por item e viewer integral sem pop-in. Evidências e limites acompanham cada tema; manter os contratos e pendências das classes.
