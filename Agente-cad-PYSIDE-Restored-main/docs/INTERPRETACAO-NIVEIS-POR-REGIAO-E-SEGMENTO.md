# Interpretação de níveis por região e segmento — PIL, FV, LV, LAJ

**Status: canônico** · Atualizado: 2026-10-01. Consolidado das instruções do dono e da investigação geométrica de 01/10. Complementa os manuais de classe; valores de exemplos não são constantes do motor.

## 1. Fonte, unidade e escopo

Cotas de nível e fundo físico estão em metros; espessuras, alturas e medidas locais do DXF estão em centímetros. Converter uma única vez: `fundo_m = nivel_m - altura_cm/100`. Registrar obra, pavimento, torre, revisão/SHA do DXF, item, região/segmento, handles, geometria, datum, método e fontes. Cota de outra região, item ou datum não é intercambiável.

O pré-processamento deve coletar as evidências SA necessárias, inclusive análise estrutural parcial ou completa quando indispensável à interpretação. A qualidade da coleta precede o consumo pelo SA. Reutilizar o contrato/fila oficial; não criar pipeline paralelo. O pacote derivado não altera o schema N1 nem aprova campos humanos. Disponibilidade de um fato no pacote não prova que todos os consumidores já o aplicam: conferir o vínculo no consumidor real.

## 2. LAJ — regiões, espessuras e degraus

Reconhecer o contorno interno real, contido na laje, e os `h=` dentro e fora, mesmo sem símbolo de corte de laje. Uma cota interna vale para seu contorno; a região principal é o contorno da laje menos a união das regiões internas. Não espalhar uma cota escalar pelo contorno inteiro de uma laje com degrau.

Comparar `nivel - h/100` em cada região. Mesmo fundo comprovado mantém uma laje, ainda que as superfícies superiores e os `h=` sejam diferentes (D-52). Fundos diferentes comprovados indicam separação e destaque vermelho na classe Lajes. Degrau/corte de laje recebe amarelo; ausência de cota é pendência, não prova de fundo igual. Na Visão de Cortes, cortes próprios/degraus de laje ficam amarelos e identificados pelo nome da laje, separados de cortes de viga. Seção T de viga não vira corte de laje.

A listagem mantém uma linha por laje e linhas internas por região: região principal e cada região do degrau, com nível, confiança e origem próprios. Cotas regionais diferentes não são conflito entre si; conflito exige duas fontes discordantes para o mesmo escopo.

## 3. Corte e transferência relativa

Antes de perguntar uma cota ao dono, medir o corte real e verificar quais regiões as abas atravessam. Nome de laje próxima ou dono textual do corte não prova a fonte. Espessuras compatíveis nas duas abas e contato geométrico com região cotada permitem medir `nivel_destino = nivel_origem + delta_cm/100`.

No resolver atual de laje sem cota, o corte horizontal usa preferencialmente `original_pts`; verifica espessuras nas duas abas em três estações, superfície constante, contato com a região e concordância entre candidatos. Corte com haste interrompida não certifica a altura absoluta da viga; pode conservar o delta local entre abas intactas. Não transportar nível absoluto pela haste encurtada.

Exemplo comprovado, não regra por nome: L317 toca no corte a região h=10/BD4 da L316 (852,16 m); a aba h=13 da L317 está 3 cm acima. Resultado 852,19 m. A associação anterior à L308/852,12 não descrevia o contato real. Fonte rastreada e fator de transferência 0,9 sobre suporte 95 resultam em 85,5%.

## 4. FV/LV — níveis por segmento e correspondência espacial

### Padrão de viga invertida — NIV-INVERTIDA-LOCAL-20261003

Decisão explícita do dono: uma vez confirmada a inversão, a referência padrão é a laje respectiva do trecho. `topo_viga_m = nivel_laje_m + (altura_viga_cm - espessura_laje_cm)/100`; `base_viga_m = nivel_laje_m - espessura_laje_cm/100`. Não conservar automaticamente a base de outro trecho quando muda a laje de referência. Indicação explícita diferente no corte prevalece. A inversão deve ser comprovada independentemente, não inferida dessa fórmula.

A laje na face oposta conserva espessura e nível locais: ela pode chegar acima da base da viga e deixar uma parte de concreto abaixo. Nível estimado da face oposta não constitui segundo datum independente. Duas referências independentes incompatíveis exigem revisão; não escolher simplesmente o maior ou menor nível. Sem referência local válida, manter pendência.

Exemplo confirmado, sem regra por nome: V330 19/71 junto à L308 (852,12 m / h=13 cm) tem topo 852,70 m e base 851,99 m. L317 a 852,19 m / h=13 cm chega 7 cm acima dessa base. O trecho 120 ligado à L317 conserva topo 853,26 m e base 852,06 m. O fundo de uma invertida é tampa superior LISO, sem sarrafos, e sua geração deve respeitar as mudanças físicas por intervalo.

Montagem das tampas — TAMPA-INVERTIDA-ENCONTROS-20261004: dividir nas faces das vigas incidentes, mesmo que o plano da tampa fique acima delas. A ausência de colisão vertical não autoriza unir esses vãos de montagem. Preservar os encontros excluídos num inventário geométrico separado e conservar as mudanças locais de perfil dentro de cada vão. Caso medido confirmado: 311 + 183 = 494 cm, retirando os encontros de 19 e 14 cm da extensão física de 527 cm. Essa divisão não altera os contatos nem os níveis das laterais.

Implementação local inicial: `beam_vertical_context.inverted_profile_levels`, `exclude_inverted_cap_junctions` e `lv_n3_cut_contract`; referências derivadas preservadas na conversão, N1 imutável. Isso não certifica aplicação em todos os caminhos SA/N3 nem publicação. Auditoria e limitações: `scripts/arete/relatorios/20261003_v330_inverted_plan/RELATORIO.md`.

Uma viga pode ter vários níveis ao longo de seu desenvolvimento. Na coluna Nível obtido, exibir uma linha interna para cada segmento FV; o nível de referência FV é superior, o fundo físico desconta a altura da seção. Não condensar segmentos em um único nível por viga.

FV usa evidência de Visão de Cortes e fontes locais válidas. LV usa corte e regiões de laje efetivamente interpretadas em seu trecho. Para/Passa e lados A/B podem possuir quantidades e limites de segmentos diferentes dos fundos. Associar por posição/interseção e cobertura do intervalo, nunca por índice/número igual. Uma LV que atravessa fundos com cotas distintas deve exibir faixas com limites, níveis e referências FV próprios.

Resolver fontes independentes uma vez: FV recebe suporte LV onde faltar evidência FV; em seguida LV lê o FV resolvido. Conservar as fontes congeladas para evitar ciclos FV→LV→FV e confiança artificial. Fonte estimada continua estimada após transferência, inclusive fundo físico e contato de pilar.

D-61 permite estimar onde falta contato: outro segmento da mesma viga com fonte independente concordante, depois referência próxima rastreável. Proximidade, maioria ou cota geral do pavimento não constituem medida. Divergência de fontes exige conflito/abstenção; não escolher silenciosamente a maior cota de fontes incompatíveis. Contato parcial conta apenas no trecho efetivamente comprovado (D-57).

## 5. PIL — topo final pelo contato mais alto

Nível final do pilar = maior nível válido de laje/região ou viga que efetivamente toca uma face sua. Identificar face e contato real; a região interna de um degrau não certifica a face que toca somente a principal, nem o inverso. O pilar acompanha o elemento mais alto em contato.

Exibir “Nível mais alto obtido da Face X: nível”, podendo listar faces empatadas. Base permanece em coluna própria; não repetir base como nível obtido nem apresentar topo por partes como se fossem pilares distintos. Pilar que nasce no pavimento seguinte conserva Não se aplica quando a convenção assim determina. Estimativa de viga propagada ao pilar permanece estimativa.

## 6. Confiança e QA de evidências

Confiança é suporte reproduzível da evidência, não probabilidade calibrada nem aprovação automática. Registrar componentes, fonte mais fraca, fator espacial, cobertura e pendências. Transferência nunca aumenta confiança. Os escores atuais distinguem cota CAD direta (95), inferência regional (65), outras inferências e estimativas; não usar essas constantes para mascarar proveniência ausente.

QA por unidade: inventariar todas as lajes/regiões, vigas/segmentos e pilares/faces; comparar IDs/geometria antes/depois; conferir handles e datum, cálculo em metros, fontes existentes sem ciclos, cobertura sem lacunas/sobreposições incoerentes e leitura PNG real do DXF. Ledger deve conservar valor, confiança, método, fontes e veredito por região/segmento. Preencher todos os valores não confirma todos os níveis. Resultado parcial não sela classe inteira.

Perguntar apenas a convenção que permaneça ambígua após medição e leitura: ficha visual real com alternativas e consequência, uma pergunta. Registrar resposta com escopo/revisão; nunca transformar decisão local em fórmula universal.

## 7. Decisão local e implementação rastreável

A confirmação de fundo contínuo em L313/BD3, L320/BD6, L321/BD7, L322/BD8, L323/BD9 e L324/BDA aplica-se apenas à revisão examinada do 13_PAV: h=10 em 852,16 m e principal h=13 em 852,19 m. ID persistido `D64-20261001-user-confirmation` é identificador local, distinto de D-64 do catálogo de decisões de LV.

Revisão humana derivada: `<recorte>.slab-region-review.json`, com SHA-256 do DXF, UID e decisão. `src/core/slab_steps.py` aplica somente correspondência de revisão e região; contradição com cota CAD direta gera `review_conflict` e preserva a medida.

Motor: `portal/app/preprocessamento/segment_levels.py` (fatos regionais, delta entre abas, fontes congeladas, FV/LV e faces PIL); reconhecimento: `src/core/slab_steps.py`; apresentação: `portal/app/static/drill_grade.js`. Testes: `portal/tests/test_cut_region_levels.py`, `portal/tests/test_segment_level_correspondence.py`, `tests/test_slab_level_inference.py`, `tests/test_slab_steps.py`.

Prova datada: `scripts/arete/relatorios/20261001-qa-niveis-lajes-vigas/RESOLUCAO-L317-D64.md`. O QA preservou 478 IDs e referências sem ciclos; 68 segmentos permaneciam estimados nesse pacote. São estado datado, não meta ou garantia de todas as obras. Uso de fonte regional nos seeds FV/LV e consumo de todos os fatos pelo SA devem ser auditados por segmento; cotas escalares de lajes com degraus não substituem essa prova.

## 9. Áreas sem laje — decisão NIV-SEM-LAJE-20261002

Escada, rampa e vazio marcado por X não são lajes e não recebem laje ou cota de laje fictícia. Para o teto/pé-direito das vigas e pilares nessas áreas, usar o nível base de saída do pavimento: primeiro a convenção de níveis; na ausência dessa referência, o nível mais frequente das lajes válidas da mesma torre/pavimento. Saída é `reference.top`, não a base anterior `reference.base`.

A ausência deve ser reconhecida geometricamente. Laje sem cota, região interna desconhecida e erro de coleta não são ausência de laje. Cortes, cotas locais, rebaixos e revisão humana continuam prioritários. FV conserva referência superior e fundo físico = referência − altura/100; LV corresponde por intervalos FV; PIL usa contato da face com a viga, sem inventar contato com laje no vazio.

Registrar decisão, datum, handles da convenção/geometria, cobertura e método. É referência de projeto determinada por convenção, não cota medida de corte. Moda ambígua não decide; contar uma vez cada laje, sem inflar votos por segmentos. Substitui D-61 para ausência comprovada; D-61 permanece para falta de evidência sem prova de ausência.

Implementação incremental v8: `no_slab_levels.py` reconhece X por diagonais vermelhas coincidentes e escada por séries regulares de pelo menos seis linhas neutras de degraus. Convenção direta tem suporte 95; transferência ×0,9×cobertura, exigindo 80% longitudinal. Alternativa modal exige maioria estrita e reduz suporte pela proporção de votos. Parâmetros de reconhecimento não são convenções universais de desenho. Rampas/escadas representadas de outra forma exigem reconhecimento adicional, sem forçar classificação. QA: `test_no_slab_levels.py`.

## 8. Seeds por contato regional — motor v7, 2026-10-02

O resolver derivado consulta a geometria da região de laje em contato para seeds FV/LV desconhecidos ou estimados. Não substitui fontes já inferidas, medidas ou humanas. Laje com degraus fornece somente suas regiões individualizadas; região interna sem cota não recebe a cota principal por aproximação. A tolerância geométrica atual é 1 cm e a cobertura longitudinal mínima da referência mais alta é 80%; contato só na extremidade não determina o segmento inteiro. Esses limites são parâmetros de implementação, não convenções de projeto.

Fonte desconhecida, conflitante, candidata ou estimada não promove outro segmento. Contato gera `inferred`, com `slab_contact_reference_without_cut_offset`: prova nível de referência, não offset absoluto medido da viga. Confiança = fonte mais fraca × 0,9 × cobertura; a transferência FV→LV mantém seu próprio fator e nunca aumenta o suporte. Cortes válidos continuam com prioridade. Seeds independentes preservados impedem realimentação circular.

Na rodada real `4776f8e1-1096-4bc8-abf1-364b0ba7eec1`, o contato longitudinal com L317 corrigiu VF301/S9 para 852,19 m, 77% no fundo e 73,1% nas laterais A. Laterais B que abrangem níveis diferentes conservam faixas. Estado datado: 54 segmentos estimados e 88 faixas estimadas, 478 IDs/geometrias preservados. Não significa certificação integral. Motor: `slab_contact_levels.py`; teste: `test_spatial_slab_contact_levels.py`; relatório: `scripts/arete/relatorios/20261001-motor-niveis-contato/RELATORIO.md`.


## 10. Continuidade do segmento lateral sobre pilares — NIV-LV-CONTINUIDADE-20261002

O dono confirmou: a parte que passa pelo pilar não afeta o nível do segmento da lateral de viga. O segmento segue a definição já obtida pelas lajes, fundos e Visão de Corte. Ausência de FV desenhado em uma faixa não é mudança de nível nem uma nova estimativa automática. Quando há mudança real de nível, conferir a segmentação/corte; não impor uma cota comum a fontes distintas.

O resolver conserva os intervalos FV para rastreabilidade e completa somente faixas estimadas/desconhecidas sem FV correspondente, dentro do mesmo segmento lateral existente, quando todos os intervalos suportados concordam. Fonte estimada não se confirma; conflito e níveis suportados distintos bloqueiam a extensão. Não altera geometria/IDs ou une segmentos. Fonte congelada por intervalo evita ciclos. Método same_lateral_segment_level_continuity, fator conservador 0,95 sobre suporte mais fraco. Mantém inferência, não medição nova. Motor segment_levels.py, testes test_lateral_level_continuity.py.


## 11. Degrau de laje secciona a lateral — NIV-LV-DEGRAUS-20261002

Decisão do dono: as laterais Para e Passa devem ser seccionadas onde a face encontra o degrau de laje. Os trechos executivos N3 permanecem sequenciais e encostados, conservando aberturas. Um degrau interno que não toca a face não secciona essa lateral; a outra face não herda a divisão automaticamente.

O SA LV reutiliza as regiões do SA LAJ: polígono principal menos regiões internas, com nível e espessura próprios. Contatos desconexos não são unidos por um intervalo retangular. A cota escalar antiga não substitui a cota da região. A transição geométrica entre regiões da mesma laje com nível/espessura distintos cria suporte `degrau_laje`, sem deslocá-lo para a face externa de um pilar. Tolerância atual de união de extremidades: 0,5 cm; parâmetro geométrico, não convenção universal.

Manter separados o nível regional de laje, o nível de referência superior da viga e o fundo físico da viga. Seccionar a lateral por degrau não significa mudar automaticamente o nível do fundo. A correspondência espacial FV/LV continua vigente, e fontes distintas permanecem em faixas explícitas.

Trecho lateral inteiramente sobre a parede de pilar, separado apenas pela abertura de uma viga incidente menos profunda, pode conservar a referência de um segmento encostado da mesma face, comportamento e profundidade. Exigir fonte suportada independente, valores concordantes e extremidades coincidentes (tolerância 0,1 cm). Bloquear transferência se o degrau estiver na ligação atravessada; um degrau no outro extremo do segmento fonte não bloqueia essa ligação. Fonte congelada, fator 0,95 e cadeia sem ciclos; não promover estimativa como prova.

Caso observado V329: existe FV; L318 toca a face A em 852,19 m; face B encontra vazio. Ao disputar passagem no P27 com V328 19/55, V329 19/60 mantém precedência por profundidade. Pilar não altera o nível da lateral. Caso V309A: face B encontra L309 h10/852,16 e h13/852,19; ambas as modalidades são divididas no limite real. São exemplos de QA, não exceções codificadas por nome.

Implementação: `lv_beam_scene._slab_polygons`, `lateral_viga_cells.segment_cell`, `segment_levels.continue_pillar_wall_segments`. Testes: `test_lv_cells_slab_steps.py`, `test_pillar_wall_level_continuity.py`. Evidência e estado datado: `scripts/arete/relatorios/20261002-lv-degraus-continuidade/`.

## 12. Auditoria de fontes e consumo pelo SA — 2026-10-02

Uma faixa interior sem FV pode herdar o nível quando as duas faixas suportadas imediatamente adjacentes concordam, mesmo que haja outro nível numa região distante do mesmo segmento. Não atravessar vizinhos discordantes, prolongar extremidade sem suporte nem encadear novas extensões como fontes. Usar fontes congeladas, fator 0,95 e conservar a rastreabilidade. Contar faixas estimadas separadamente do status agregado do segmento.

Nível principal de laje e nível de degrau interno pertencem a regiões diferentes. Uma cota interna não invalida automaticamente o nível principal. A remoção desse falso conflito exige uma região principal explicitamente reconstruída e concordante; discordância na própria região permanece conflito. O inventário deve referenciar os IDs dos fatos efetivamente resolvidos, conservando os fatos anteriores como histórico.

O SA deve receber também a derivação por delta de abas comprovado, e não somente cotas textuais. Exportar somente derivação rastreável, fontes não estimadas/conflitantes e candidatos concordantes. Conferir novamente a mesma geometria da laje no consumo; preservar valores e vínculos humanos. Conservar confiança e fontes da derivação: inferência não vira medição nem certeza de 100%. A espessura canônica do snapshot LAJ é `fields.laje_dim` (ex. h=12), com fallback legado explícito.

Seção automática de viga deve ser conferida contra a largura do próprio FV antes de alimentar PIL. Rótulo de seção de pilar pode parecer B/H, mas é inválido como seção de viga se diverge da largura FV. Na ausência de altura FV, rótulos vinculados às laterais da própria viga podem fornecer a seção somente quando são únicos e compatíveis com a largura geométrica. Divergência exige abstenção; campos humanos permanecem protegidos. Não usar votação de textos próximos como confirmação.

## 13. Referência da viga e painel sobre a laje — NIV-VIGA-LAJE-PAINEL-20261003

Mudança de nível da própria viga exige corte ou transição do hatch/preenchimento da viga. Degrau regional de laje não é essa prova. Conservar nível da viga e nível/espessura da região da laje separadamente; o painel superior fecha a diferença vertical. Seccionar Para/Passa no contato do degrau continua necessário, mesmo quando o nível da viga permanece constante.

O SA lateral usa a região principal da mesma laje como referência do degrau somente quando ambas pertencem à mesma zona de seção da viga e as fontes principais concordam. A região interna continua com sua própria cota e espessura na ficha. Ausência de principal compatível não autoriza copiar a cota do degrau para a viga. Corte real permanece prioritário na resolução FV/LV. Essa transferência é referência inferida, não medição nova nem confiança de 100%.

O contrato de corte N3 recebe a referência superior da viga e a cota da laje separadas; calcula o desnível e desenha o painel superior com as tolerâncias executivas existentes. Exemplo de teste: viga 55 cm, referência 852,19, laje h10/852,16, fechamento nominal 3 cm. Nenhum nome ou valor do exemplo é regra do motor. Reconhecimento geral de mudanças de hatch/preenchimento e certificação das vistas longitudinais ainda precisam de evidência própria; não concluir ausência de mudança só porque um coletor não encontrou corte.


## 14. Corte medido ancora a continuidade da seção — NIV-CORTE-CONTINUIDADE-20261003

Um corte não encurtado pode ancorar a referência da viga ao longo de uma lateral canônica reta que toca os fundos. Exigir correspondência geométrica: haste do corte dentro do FV com profundidade e largura da seção; espessura da aba consistente com a laje proprietária. Nome textual isolado não comprova associação. A cota regional da laje somada ao deslocamento superior do corte fornece o datum; a associação sem corte segue agora a convenção padrão confirmada pelo dono em NIV-PADRAO-EXCECAO-20261003, mantendo prioridade para indicação explícita diferente.

Transferir somente entre fundos com largura e profundidade compatíveis, cobertura longitudinal >=80%, sem corte discordante, mudança de seção, decisão humana discordante ou preenchimento interno não revisado. Ausência de DXF legível bloqueia. A implementação usa bbox de HATCH/SOLID/TRACE como bloqueio conservador, não como classificador completo de mudanças de hatch. Não certificar todos os casos de preenchimento por este guard. Fontes congeladas, fator 0,95, histórico anterior e IDs do corte permanecem; concordância de várias fontes não infla confiança.

A altura FV exige largura B/H compatível com o polígono do próprio fundo. Se faltar ou divergir a dimensão FV, uma seção lateral espacialmente coincidente e cobrindo >=80% do fundo pode fornecer H quando única; seções distantes ou conflitantes não são usadas. Registrar fonte e IDs da seção. Não votar uma altura global para vigas com múltiplas seções.

Coleta temporária monta cortes com registros da própria passagem em memória: não pressupor tabela beams persistida no SQLite temporário e nunca recorrer ao banco de produção para completar evidência. Métodos: beam_cut_continuity.fund_section/propagate, sa_levels, preprocessamento_coleta_niveis. Scores representam suporte de evidência, não probabilidade calibrada nem certeza de 100%.


## Referência padrão e exceções explícitas — NIV-PADRAO-EXCECAO-20261003

Decisão global do dono em 03/10/2026: o topo da viga acompanha inicialmente o nível principal da laje de referência ou o nível base de saída do pavimento onde não há laje. Esse padrão é uma convenção válida de interpretação, não uma estimativa arbitrária, quando a coleta do desenho não apresenta indicação de exceção. Não exigir um corte adicional apenas para confirmar o padrão. Mudanças do nível comum das vigas ou lajes são indicadas explicitamente por suas representações, cotas, cortes ou hachuras de convenção; uma exceção local prevalece sobre o padrão.

Associar a referência pela posição, região, seção e contatos reais, conservando IDs das fontes e a convenção aplicada. Uma laje com degrau conserva níveis e espessuras por região; o degrau sozinho não desloca a viga. FV e LV compartilham o datum da viga, com fundo físico = topo - altura/100, e o painel superior fecha o desnível local da laje. Pilares acompanham o maior nível dos elementos que realmente tocam cada face; não definem o nível das vigas ou lajes.

QA deve distinguir nível por convenção padrão, nível medido e nível derivado de corte. Não manter uma pendência somente por ausência de corte de confirmação do padrão, nem atribuir 100% por ausência de exceção detectada. Conferir cobertura da leitura do DXF, correção da associação espacial, legibilidade das cotas, possíveis hachuras/cortes e concordância entre classes. Leitura incompleta ou conflito continua revisão; ausência de resultado do coletor não prova ausência de indicação. Confirmações independentes se complementam, sem realimentação circular ou multiplicar a mesma fonte como várias provas.

**Pendente de treino e validação:** interpretação de vigas com níveis diferentes explicitamente sinalizados por hatch/preenchimento ou visão de corte. O dono informa que ainda não temos exemplos desse tipo aqui. Catalogar futuros exemplos reais com geometria, legenda/hatch, corte, datum, trecho afetado e contraste com o padrão; validar os reconhecedores antes de afirmar cobertura geral. Um bbox de HATCH/SOLID/TRACE não classifica sozinho uma exceção de nível.

### Leitura do corte de planta na trava QA — regra derivada 2026-10-04

Regra derivada de NIV-PADRAO-EXCECAO (exceção por corte prevalece; o corte não é exigido para confirmar o padrão). Não é decisão nova do dono. Vale na trava MEDIDA de nível FV (`portal/app/qa_cad_gate.py`, `_section_level`), ainda não publicada.

A marca de corte na planta (par de letras iguais) não é, sozinha, o desenho do corte. A trava lê a **elevação**: título `CORTE k` único fora do recorte, vãos das lajes ao longo da marca, linha de topo contínua com a espessura (5–40) abaixo, e um único nível escrito até 40 acima do topo. O sentido da elevação só fecha com rótulos únicos V/P/L presentes na planta e na elevação.

O que essa leitura pode afirmar:

- elevação plana com o nível escrito igual ao datum do pavimento (±0,005): a marca **não indica exceção**. A laje sem cota segue o padrão, e a guarda das vizinhas continua;
- elevação com degrau desenhado (topos diferentes por vão, ou dois topos sem o mais próximo do título isolado por fator 2) ou nível escrito diferente do datum: a marca **indica exceção**. A laje fica não certificada. A trava não atribui esse valor à laje;
- título ausente, elevação não alinhada ou sentido simétrico sem rótulos: leitura insuficiente. A marca continua exceção possível.

Medido no 13_PAV (DXF original Fase-1, `probe_corte_bb*.py`, `corte_bb.png`): o corte B-B (título em (2673,1658), elevação ao longo da V301) tem o mesmo x da planta e desenha o topo como uma linha plana y=1482,98, espessura em 1470,98, com um só nível 852,19. Os degraus 852,16 escritos (L309 BD1, L312 BD2, L316 BD4) aparecem planos. O corte não resolve 3 cm; serve só para dizer se indica nível diferente. A-A ficou sem sentido decidido (dois rótulos). Evidência: `scripts/arete/relatorios/20261004_qa_jev_fv_f0_f2/RELATORIO.md`, 5ª passada.

O recorte `torre_1.dxf` descarta SOLID e as definições de LTYPE. Ausência de preenchimento e tipo de linha (tracejado) só se provam no original Fase-1, localizado por `crop_result.json:dxf_bruto`, com as LINEs do recorte contidas no original.

Esta decisão atualiza a intenção canônica; não comprova por si só implementação, reprocessamento ou aumento de confiança dos resultados existentes. Conferir consumo no motor e executar QA por faixa antes de anunciar resolução.

### Aplicação e pontuação v16

`standard_beam_level` aplica a convenção somente após resolver suporte independente FV/LV existente, sem substituir corte ou decisão humana. Exige DXF legível, FV poligonal, contato longitudinal mínimo de 80% com lajes principais concordantes, fontes não estimadas/conflitantes, ausência de corte local (inclusive encurtado) e ausência de preenchimento interno não revisado. Não muda um datum já derivado diferente. A região interna do degrau não se torna datum da viga: usar a principal da mesma laje, com sua proveniência.

Score de convenção = menor suporte das fontes × 0,95 × cobertura longitudinal, limitado provisoriamente a 85 pontos pela leitura ainda não certificada de exceções de hatch. Esses parâmetros formam uma rubrica conservadora versionada, não uma probabilidade calibrada. Fonte fraca permanece fraca; convencional nunca recebe 100% nem aprovação humana. Somente adotar a convenção se melhorar o suporte atual. Origem `level_basis=owner_convention` e status `inferred` acompanham transferências FV→LV e fundo físico, mesmo com score acima de 80. Comparar faixa por faixa e verificar valores/geométricas antes de publicar; estado de implantação no relatório `20261003-nivel-padrao`.


### Rastreio de confiança por região e segmento — QA-NIV-RASTREIO-20261003

Antes de perguntar ao dono ou alterar score, seguir `source_fact_ids` até as fontes independentes; registrar CAD/handles, região principal ou interna, posição do corte, datum, unidade, cobertura e fator de transferência. Fonte inferida com somente nome da laje ou ID de coleção não equivale a uma cota CAD rastreada. Uma região medida não confirma automaticamente outra região da mesma laje. Não contar a mesma origem em FV/LV/LAJ como provas independentes.

Conferir primeiro se o problema é leitura/associação: corte com haste interrompida pode conservar delta de abas, mas não comprova altura absoluta; ligar a aba à região realmente tocada e à espessura correspondente. Não elevar confiança apenas pelo nome do método ou por concordância que nasceu do mesmo fato. Avisos de níveis múltiplos só podem ser removidos após resolver a região proprietária e o contato; não apagar a penalidade genericamente.

FV e LV têm contratos próprios de geometria, apoios e segmentos. Transferência de nível com fonte independente congelada, prova espacial e grafo acíclico é permitida; não autoriza copiar esses outros campos nem equiparar a quantidade de segmentos. Padrão aprovado pelo dono, medida e derivação permanecem origens distintas. Score é suporte de evidência, não probabilidade calibrada; melhorar rastreabilidade pode mudar o suporte somente após validação por faixa, sem selo automático.

Pergunta humana deve indicar o trecho e alternativas concretas após tentar cortes, hachuras, cotas, regiões LAJ e correspondência FV/LV. Falha do coletor em encontrar uma fonte não prova ausência no desenho. Caso datado e diagnóstico reproduzível: `scripts/arete/relatorios/20261003-nivel-padrao/remaining-audit.json`; não transformar seu resultado em regra fixa por item.


### Proveniência de regiões e reverificação de inferências — NIV-CORTE-PROVENIENCIA-20261003

Implementação v17: região derivada de degrau por fundo contínuo só usa a contraparte com cota CAD direta, seção comprovada, espessuras regionais, ausência de conflito e delta coerente. Registrar source_fact_ids e delta_cm; score = fonte × 0,90. Duas regiões inferidas não se confirmam mutuamente. Conservar IDs do corte e cotas e geometria originais.

Um escalar LAJ já inferido não deve impedir a busca de prova geométrica independente. Resolver abas horizontais em três estações com espessura coerente, fontes congeladas e valores concordantes; aceitar somente o mesmo nível existente com suporte maior, preservando evidência anterior. Nível humano/medido, conflito, alternativa diferente, fonte inferida sem âncora e espessura incompatível não são substituídos. Esse mecanismo não certifica cortes verticais, escala arbitrária ou todas as exceções de hatch.

QA distingue implementação geral de resultado datado. No 13_PAV/Torre 1, job v17 c7568d3f-6bba-475d-9720-1e320b272e61 confirmado: 28 faixas com suporte maior, 213→196 abaixo de 60, níveis e geometria preservados, fontes acíclicas. Restante não foi certificado. Evidência e limites: scripts/arete/relatorios/20261003-auditoria-confianca/RELATORIO.md. Não elevar percentuais de outras obras por esse resultado.


## Harmonia de fontes, gates e explicação — NIV-HARMONIA-GATES-20261003

**Estado:** contrato e plano aprovados pelo dono em 03/10/2026; a implementação nova está delegada a outra IA. Este registro documental não comprova implementação, deploy, reprocessamento ou certificação de níveis. O resultado datado v17 continua separado. Não substituir a rubrica vigente por pesos novos somente porque este plano existe.

### Origem e confirmações independentes

Cada evidência deve conservar revisão/SHA do DXF, entidades/handles originais, região, segmento/face, grandeza, unidade, datum, alcance espacial e cadeia de fontes. Diferenciar corte original do CAD, seção reconstruída A/B, convenção de projeto e revisão humana. A confiança do nome/associação da viga não equivale à confiança do nível.

Um corte LV reconstruído a partir de níveis das fichas pode conferir seção, contatos e coerência, mas não constitui nova medida desses níveis. A mesma cota reaparecendo em LAJ, FV, LV ou seção reconstruída conta uma única origem. Duas cadeias que compartilham uma entrada necessária não são confirmações inteiramente independentes. Deduplicar pela origem física e revisão, não apenas pelo ID final, nome do método ou classe.

Associar cortes por posição, orientação, contato, cobertura, largura, profundidade e espessuras das abas. Nome textual auxilia a busca; não decide sozinho. Usar geometria física original, nunca a cauda comprimida para exibição como medida. Preservar alternativas válidas e conflitos; não decidir por maioria simples de cópias ou por textos próximos.

### Gates de nível por unidade

- Origem: fonte atual, existente e rastreável, sem ciclos nem dependências ausentes.
- Associação: região/face/intervalo e seção compatíveis; cobertura medida, com tolerâncias existentes explicitadas.
- Interpretação: distinguir topo/referência da viga, fundo físico, nível regional da laje e painel de fechamento. Comparar somente a mesma grandeza, unidade e datum.
- Exceções e leitura: preservar corte discordante, mudança de seção, decisão humana e preenchimento não interpretado. Ausência de resultado do coletor não certifica ausência de exceção.
- Concordância: confirmar apenas o trecho efetivamente coberto. Fontes congeladas impedem que LV derive de FV e retorne para certificar o mesmo FV. Pilar consome o maior contato superior válido por face; não devolve votos às vigas/lajes.

RAG recupera regras e exemplos; não é uma observação do desenho atual nem acrescenta voto ao nível. Exemplos aprovados por nome continuam casos de regressão, nunca cotas universais. Geração N3/N4 ou igualdade com seção reconstruída não certifica sozinha a interpretação original.

### Pontuação e apresentação aprovadas

Escolha explícita do dono: percentual com explicação acessível na ficha por região, segmento ou face. Expor fonte principal, cálculo, confirmações independentes, limitações e resultado dos gates. O percentual continua denominado suporte de evidência, não probabilidade calibrada.

Plano aprovado: avaliar cada caminho pelas entradas necessárias, cobertura e fatores; escolher o melhor caminho válido sem penalizá-lo por alternativas fracas irrelevantes. Entradas necessárias do mesmo caminho continuam limitantes; fonte forte não apaga conflito válido. Não conceder bônus arbitrário por concordância. Aumento exige prova melhor ou limitação realmente resolvida, com comparação antes/depois. Não remover um aviso genericamente nem elevar score pela troca do nome do método.

Primeira etapa determinística, explicável e versionada. Aprendizado por reforço/premiações está fora desta etapa. Calibração probabilística futura exige rótulos independentes e avaliação separada das obras/pavimentos usados no ajuste; nenhum treinamento baseado apenas na concordância do próprio motor. Exemplos reais de exceções de nível de viga por hatch/corte ainda estão pendentes de treino e validação.

### Progressão e QA

Congelar baseline, revisão, inventário e IDs; comparar por unidade valor, geometria, associação, origem, score e pendência. Testar duplicação de fonte, ordem do processamento, ciclos, conflitos, corte interrompido, degrau que toca só uma face, ausência de laje, passagem por pilar e contagens diferentes FV/LV. Duplicar evidência não aumenta confiança. Mudança de nível exige prova específica. Preservar decisões humanas e histórico.

Atualizar motor, manual, perfis/checklist do QA e índice RAG de forma coordenada, sem marcar como realizado o que permanece plano. Rodar QA canônico e conferência PNG, deploy protegido e reprocessamento oficial antes de afirmar resultado novo. Relatório de cada ciclo distingue regra, implementação, teste, publicação, consumo SA e veredito visual. Não há meta artificial de 100%; perguntas ao dono somente após tentar a leitura/associação e apresentar dúvida concreta.


## Caminho de evidência explicado — NIV-EVIDENCIA-CAMINHOS-20261003

**Estado:** implementação v18 (`preprocess-context-v18-evidence-path-explanation`) do plano NIV-HARMONIA-GATES-20261003. Rubrica `level_evidence_completeness_v1.1-best-validated-path`: mesmos pesos da v1; muda apenas a escolha do caminho e a explicação. Publicação e confirmação no portal: ver relatório datado (não inferir deste texto).

### O que a explicação expõe por fato

`portal/app/preprocessamento/level_provenance.py` anota cada fato (`support_explanation`) sem alterar valor: fonte principal e tipo de origem (revisão humana, convenção do dono, cota CAD direta com handles, convenção de piso, estimativa, campo SA sem raiz rastreada), grandeza, cadeia de cálculo do caminho mais fraco que limita o score, origens independentes, confirmações, limitações e gates. Na grade (`drill_grade.js`) aparece como "Suporte de evidência X% · por quê?"; o texto diz explicitamente que não é probabilidade calibrada.

Gates por fato: origem, sem ciclo, fontes presentes, associação espacial, grandeza/datum, exceções (convenção do dono = `pending_training`; contato de laje sem offset de corte = `not_certified`), concordância e "transferência não aumenta". Associação por intervalo/contato construída geometricamente (faixa FV sobre a lateral, aresta da face tocando o elemento) conta como medida; cobertura < 0,8 reprova.

### Origem única e confirmação sem bônus

A mesma cota CAD (mesmos handles) vista por LAJ, FV, LV ou PIL é uma única origem. Confirmações são alternativas concordantes cuja raiz difere da raiz do caminho principal; são listadas e nunca somam score. O salto do corte virou fato próprio (`cut_level_facts`, `field=cut_beam_reference`), portanto a cadeia corte→FV→LV é rastreável.

### Melhor caminho validado

- FV por corte: um corte só é associado ao fundo quando o tronco desenhado tem a profundidade da FV (±0,25), a largura do fundo (±0,25) e área coerente (`cut_matches_fund`). Havendo cortes validados, usa-se o mais forte; os demais concordantes viram confirmação. Sem corte validado, mantém-se a regra anterior (o mais fraco de todos, `cut_association=contact_only`).
- LAJ por asas de corte: cada candidato já passou nas duas espessuras em três estações; pontua o mais forte, sem penalização por alternativas irrelevantes.
- Corte desenhado girado (vertical): a orientação vem do lado do tronco. Como a geometria não distingue viga invertida de viga normal girada, a leitura girada só re-prova um valor já existente igual; valor novo ou orientação ambígua → abstém.

### Pendências explicadas (13_PAV/Torre 1)

- L303: a asa desenhada no corte mede 10 cm, contra laje h=12. L328/L321: a asa de L321 é desenhada com 12 cm, contra h=13. A espessura incompatível bloqueia a prova, com razão; não relaxar a tolerância. *(Superado por NIV-LAJE-CAMADAS-20261003: a asa ≠ h é erro de desenho, o h declarado vence; a asa só re-prova o valor existente, com fator × 0,95.)*
- L301/L305/L307/L326/L330 (consenso de vizinhos), L320 (região principal com escopo) e L325 seguem sem corte independente.
- Bandas fracas por raiz primária: campo SA sem raiz rastreada é a maior parte. O próximo ganho real é rastrear essas raízes até handles CAD, não mexer em pesos.


## Datum comum com laje vizinha mais baixa — NIV-DATUM-COMUM-20261003

**Estado:** implementação v19 (`preprocess-context-v19-common-datum-lower-slab`). Não é decisão nova: aplica NIV-PADRAO-EXCECAO (topo da viga segue o nível comum/principal) e NIV-VIGA-LAJE-PAINEL (degrau de laje não muda a viga; o painel de topo fecha a diferença; mudança da viga só por corte/hachura).

`standard_beam_level.common_datum_contacts`: quando as lajes que tocam o fundo discordam, a convenção só resolve se (a) o datum do pavimento (`floor_source`, saída do piso) existe e não é desconhecido/conflito/candidato/estimado; (b) há contato(s) com valor igual ao datum (±0,0025 m) cobrindo ≥ 0,8 do fundo; (c) **todas** as outras lajes estão **abaixo** do datum. Laje acima do datum exigiria mudar a viga → abstém (só corte/hachura provam). O datum entra no caminho limitante (fonte), a laje mais baixa não é fonte e fica registrada em `lower_contact_slabs` com o aviso `lower_adjacent_slab_closed_by_top_panel`. Teto de 85% e `level_basis=owner_convention` mantidos. O datum do pavimento passa a ser publicado como fato (`floor-exit-reference`) também em pavimentos sem região de ausência de laje, para ser rastreável.

### Faixas fracas restantes com raiz SA não rastreada (13_PAV/Torre 1, 97)

- **Lajes sem cota escrita no DXF** (L301, L303, L305, L307, L320, L325, L326, L328, L330 — e as vigas/laterais que herdam delas): os únicos caminhos existentes são consenso de vizinhos *(corrigido em NIV-LAJE-CAMADAS-20261003: vizinha através de viga, com seção de FV no corredor, é contato espacial e não proximidade; vota em camadas)*, delta de corte com asa incompatível com o h declarado, ou hachura (leitor de exceção sem treino). Pendência explicada; resolução = cota escrita no projeto ou convenção de hachura confirmada pelo dono.
- **V309A fundo s1**: um corte encurtado por quebra (`shortened_section_break`) toca o fundo; a convenção não passa por cima de corte não resolvido. Abstenção correta. *(Resolvido no v22: a quebra fica na alma, abaixo da aba; o afastamento do topo é lido acima dela. Ver "Corte encurtado: leitura do topo".)*
- **Laterais por `lv_cell_slabs`** (V312, V314, V315, V316, V318, V320–V323, V325): herdam de laje fraca da lista acima ou do próprio campo SA da célula; resolvem junto com as lajes.


## Nível de laje em camadas — NIV-LAJE-CAMADAS-20261003

**Estado:** decisão do dono (03/10/2026), implementada no v20 (`preprocess-context-v20-slab-level-layers`), módulo `portal/app/preprocessamento/slab_level_layers.py`.

Para uma laje sem cota própria, o nível é decidido por camadas de confiança. Cada camada só entra quando a anterior falta, e nenhuma ultrapassa o próprio teto:

| Camada | Prova | Fator / teto |
|---|---|---|
| L0 | Texto de nível CAD dentro da laje | 95 |
| L1/L3 | Asa da laje medida na visão de corte (`resolve_missing_slab_cut_regions`) | × 0,9; asa ≠ h → × 0,9 × 0,95, só re-prova |
| L2 | Vizinhas através de viga, todas as origens independentes concordam (sem corte de degrau = sem degrau) | mais fraca × 0,95, teto 85 |
| L4 | Vizinhas discordam: vence o nível mais frequente entre origens independentes | mais fraca vencedora × 0,95 × fração de votos, teto 75; empate abstém |

Regras que separam consenso de alucinação:

- **Vizinha ≠ proximidade:** só vota a laje do outro lado de uma viga real, quando o corredor entre os dois contornos (largura = vão até 100 cm) contém uma seção de fundo de viga com extensão ≥ 10 cm. Distância sozinha nunca associa; lajes encostadas sem viga entre elas não votam.
- **Sem ciclicidade:** votos são congelados antes de qualquer atualização. Só vota um fato com raiz própria (`sa_evidence`/`human_review`), um voto por origem (handles CAD das raízes). Um fato cujas raízes incluem a própria laje alvo não vota. Inferidas não votam.
- **Voto local:** se a vizinha tem regiões de nível, vota a região que toca o corredor; senão, o nível único da laje.
- **Concordância só sobe entre origens independentes** e nunca acima do teto da camada.
- **Valor da camada ≠ valor SA:** reportado em `tower.slab_level_layers.not_applied` (`differs_from_sa_value`), nunca aplicado.
- **Asa desenhada ≠ h:** erro de desenho humano; o h declarado vence (a interpretação de corte já redesenha com a medida correta). Aviso `drawn_wing_thickness_differs_from_declared_h`.
- Hachura de laje não existe neste desenho (a hachura vista era de pilar); não é camada.
- Votos de segmentos que tocam a laje (pedidos pelo dono no desempate) ainda não entram: os níveis de fundo derivam das próprias lajes e colapsariam na mesma origem. O desempate por corte é aplicado quando há visão de corte no corredor.

### Linha de degrau provada (v21, `preprocess-context-v21-proven-step-lines`)

O dono aprovou a recomendação em 03/10/2026 ("o importante é solucionar; dinâmico e universal").

- **Regra:** uma viga (item) através da qual duas lajes com nível próprio e de origens independentes já diferem é uma *linha de degrau provada*. Ali o próprio CAD refuta "sem corte = sem degrau", então nenhum voto de continuidade atravessa essa viga. Os votos retidos aparecem em `withheld_votes` (`proven_step_line`) e as linhas em `slab_level_layers.proven_step_lines`.
- **Efeito:** só retira votos, nunca cria valor.
- **Limite conhecido:** a regra vale para a viga inteira. Um degrau provado num trecho também retém votos em outro trecho da mesma viga (ex.: V317 entre L322×L323 retém L329→L330). É conservador.
- **Face a face:** borda que encara de verdade ≥ 5 cm. O contato diagonal num cruzamento de vigas dá cerca de 2 cm por borda e é descartado.
- **Viga do corredor:** quando há mais de uma, conta a de maior área.

### Resultado 13_PAV/Torre 1 (v21)

- L301, L305, L307, L326, L330 → 852,12 e L320 → 852,19, todas por unanimidade das vizinhas válidas (teto 85%). As seis concordam com o valor SA; nenhuma ficou pendente.
- Linhas de degrau provadas: a viga longitudinal entre a faixa de borda e a faixa interna (pares L302×L310, L304×L312, L308×L316), a faixa inferior (L322×L329, L324×L331) e outras 6.
- L303, L325, L328: asa ≠ h re-prova (81,2%).

### Resultado 13_PAV/Torre 1 (v20, histórico)


- L303, L325, L328: asa ≠ h, o valor existente é re-provado com 81,2%.
- L320: maioria 3/4 (L318, L319, L321 em 852,19 contra L327 em 852,12), 67,7%.
- Empates que abstêm, com 2 votos contra 2: L305 (L304/L306 852,12 × L312/L313 852,19), L307, L326, L330 (com L322 852,16).
- L301: a maioria (L309/L310 em 852,19) difere do valor SA 852,12. Reportado, não aplicado.
- **Padrão observado:** as faixas de borda (L301–L308, L326–L331) estão em 852,12. As lajes com cota CAD dos dois lados da viga longitudinal já diferem (por exemplo L304 852,12 × L312 852,16) e não há corte desenhado ali. Ou seja, nessa linha de viga, "sem corte = sem degrau" é refutado pelo próprio CAD. A proposta de linha de degrau provada aguarda o dono.


## Corte encurtado: leitura do topo — NIV-CORTE-ENCURTADO-TOPO-20261004

**Estado:** implementação v22 (`preprocess-context-v22-shortened-cut-top-read`). Não é decisão nova. Aplica NIV-VIGA-LAJE-PAINEL (mudança da viga só por visão de corte ou hachura) e a regra geométrica: uma quebra só invalida as medidas que a atravessam.

- **Leitura do topo (`break_spares_top`).** Vigas altas (120 cm) têm a visão de corte encurtada por uma quebra na alma. A seção precisa estar em pé, em T ou L, com pelo menos uma aba. A quebra precisa ficar inteira abaixo da aba (a base da aba acima da quebra). O afastamento entre o topo da alma e o topo da aba é medido no próprio contorno desenhado, não por cadeia de altura que cruze a quebra, e precisa conter o `own_dist_top` declarado. Se tudo isso vale, o corte gera fato com `shortened_section_top_read` e o aviso `shortened_section_top_offset_only`. A profundidade da seção não é validada através da quebra: o perfil não é usado para casar a haste, e a associação ao FV fica `contact_only`. Se a quebra alcança a aba, o corte continua rejeitado (`shortened_section_break`).
- **Um desenho, duas lajes.** A mesma visão de corte é ligada às lajes dos dois lados, e cada laje lê o próprio lado. Antes, a primeira laje dona do desenho escondia a outra; uma laje multi-parte, sem nível escalar, fazia o corte se perder.
- **Laje multi-parte (`cut_region_source`).** Lê a região de nível que o desenho do corte toca. Só aceita quando todas as regiões tocadas têm o mesmo nível.
- **Lados de um mesmo desenho.** São leituras do mesmo corte: quando concordam, vale o lado mais forte, sem soma. Entre desenhos diferentes sem casamento de haste continua valendo o mais fraco de todos. Sem isso, a leitura do segundo lado baixava o suporte, o que é anti-monotônico (V301 s10 cairia de 81,2% para 73,1%).

### Resultado 13_PAV/Torre 1 (v22, job `eaee701a`)

- Faixas abaixo de 60%: 127 → 52. Valores alterados 0, quedas 0, 93 faixas sobem; ciclos e violações 0.
- 11 cortes encurtados lidos pelo topo, todos com afastamento 0 e a quebra 17,6 cm abaixo da aba.
- Fundos resolvidos: V309A, V311, V312, V314, V316, V318, V325 s1. A alma de cada um cruza da faixa de borda (852,12) para a faixa interna (852,19). Pela NIV-VIGA-LAJE-PAINEL, a viga fica em 852,19 e o painel fecha o degrau; os cortes "7" nas vigas de borda confirmam a mesma leitura.
- Comparando os contatos de pilar pela chave (pilar, face, item, segmento): nenhum perdido, rebaixado ou com valor mudado; 12 contatos novos. As "quedas" por id posicional eram só deslocamento de índice.
- Restam fracas:
  - VF202 s1: cobertura 0,8 no limite e teto nativo 40;
  - V308 s1: LV com cobertura 0,73;
  - V320 s2 e V322 s2: trechos diagonais entre a faixa de borda e a interna, com laje "requer revisão" no SA;
  - 6 laterais com campo SA próprio da célula.

## Penalidade do SA cede à laje comprovada — NIV-PENALIDADE-SA-LAJE-20261004

**Estado:** implementação v23 (`preprocess-context-v23-proven-slab-lifts-sa-penalty`). Não é decisão nova. Corrige a ordem das provas e aplica NIV-VIGA-LAJE-PAINEL.

- **Penalidade antiga (`stale_slab_penalty_lift`).** O SA marca `source_slab_level_not_uniquely_observed` e `source_slab_requires_review` antes de as camadas de laje (v20/v21) comprovarem a laje. Essas marcas viravam um teto fixo (55 − 15 − 15 = 25). Agora elas deixam de valer quando três condições se cumprem:
  - todas as lajes de origem do segmento estão comprovadas;
  - essas lajes estão no mesmo nível da viga (± 0,25 cm);
  - nenhuma laje comprovada que toca o segmento afirma outro nível.

  Não há bônus: o teto passa a ser o da base (75), e a origem mais fraca × 0,95 continua limitando. O registro guarda `stale_sa_native_cap` e o aviso `sa_slab_penalty_superseded_by_proven_source`.
- **Lateral do lado baixo não preenche o fundo.** O preenchimento do FV pela LV (`lv_independent_evidence_fills_fv`) usava a lateral mais alta entre as fortes. Quando a face oposta lê um nível maior, ainda que fraca, a lateral do lado baixo só informa a própria laje e não limita o topo da viga. Nesse caso o preenchimento se abstém e a referência padrão decide. Antes, a fraqueza das laterais escondia esse erro; com as laterais levantadas, ele trocaria os valores da V301.

### Resultado 13_PAV/Torre 1 (v23)

- Faixas abaixo de 60%: 52 → 25. Contatos de pilar: 203 → 203, nenhum perdido, rebaixado ou com valor mudado.
- Valores corrigidos: 24 faixas laterais de 852,12 para 852,19.
  - V301 s3, s4, s7 e s13 e V306 s2 e s4 ficam entre uma laje de borda (852,12) e uma laje interna (852,19).
  - Em v22, esses fundos eram preenchidos pela lateral do lado baixo; agora seguem a laje principal, como os vizinhos s1, s2, s5 e s6 já faziam.
- As 4 faixas da V306 s4 passam a 58,7%, já no valor novo. Elas vêm da laje principal FC0 com cobertura menor.
- Sobem: VF202 s1 (40 → 75), V308 s1 (56,9 → 75), V320 s1 e V322 s1.
- Restam fracas: V322 (8 faixas), V320 (4), V306 s4 (4), V303 (2), V302 (2) e casos isolados.

### Degrau fechado no datum e laje multi-parte na semente (v24)

**Estado:** implementação v24 (`preprocess-context-v24-datum-step-multipart-region-source`). Não é decisão nova. Aplica NIV-VIGA-LAJE-PAINEL e NIV-DATUM-COMUM ao levantamento da penalidade e à semente lateral.

- **Laje mais baixa no datum não contradiz.** Quando a viga está no datum comum do pavimento e toca uma laje comprovada mais baixa, isso é um degrau fechado pelo painel de topo, não outro nível para a viga. A penalidade antiga do SA cede como na v23. Uma laje mais alta continua contradizendo sempre. Fora do datum, uma laje mais baixa também contradiz.
- **Laje multi-parte lê a região percorrida (`segment_region_source`).** Laje com mais de um nível (principal e degrau) não tinha `slab_level` único e ficava fora das origens da semente lateral. O resultado era o teto de origem incompleta (35) ou de origem ausente (30). Agora a semente usa a região de nível que o segmento percorre, com três condições:
  - um toque só na ponta não conta;
  - as regiões percorridas devem ter um único valor;
  - esse valor deve ser igual ao do segmento.

  Se o segmento percorre principal e degrau com valores diferentes, a origem continua incompleta. A região mais forte entra com o teto × 0,95 de sempre.

### Resultado 13_PAV/Torre 1 (v24)

- Faixas abaixo de 60%: 25 → 5. Nenhum valor mudou e nenhuma faixa caiu.
- Contatos de pilar: 203 → 203. Ciclos 0, violações 0, fontes ausentes 0.
- Sobem as laterais de V320 s2 e V322 s2 (24 → 71) e as laterais de V302, V303, V308, V309, V315 e V316 com laje multi-parte (30–40 → 62–75).
- Restam fracas: V306 s4 (4 faixas, laje principal FC0 com cobertura menor) e V330 (1 faixa, cota CAD direta).

### Fundo plano confirmado pelo dono amarra a região principal (v25)

**Estado:** implementação v25 (`preprocess-context-v25-owner-confirmed-flat-bottom`). Não é decisão nova. Aplica a D64 (01/10/2026) como prova.

- A região principal de uma laje com degrau herda a cota CAD direta do degrau (× 0,9) quando um corte desenhado prova o fundo plano. A confirmação do dono de "mesmo fundo" (`owner_confirmed_scoped_same_bottom`, com `decision_id`) prova a mesma coisa e agora entra no lugar do corte.
- A confirmação nunca passa por cima de uma cota CAD direta: um conflito (`review_conflict`) continua bloqueando. Sem `decision_id`, nada muda.

**Resultado 13_PAV/Torre 1:**
- L322 principal: 65 → 85,5.
- Faixas abaixo de 60%: 5 → 1. Nenhum valor mudou e nenhuma faixa caiu. Contatos de pilar: 203 → 203.
- A faixa restante é a V330 `lateral_b_passa` s14 (57,7%). O valor chega por seis transferências (laje → semente → fundo → lateral → continuidade pela parede do pilar). A queda por salto é de propósito, então não é defeito.
