# Checklist do gate de evidência

## Escopo

- [ ] `project_id` resolvido sem ambiguidade.
- [ ] Obra, pavimento, classe, item, nível, parte e variante explícitos.
- [ ] DB real e Python 3.12 confirmados.

## Proveniência

- [ ] Cada conclusão cita fonte, caminho, hash e versão do adaptador.
- [ ] N1 não é usado como prova de si próprio.
- [ ] N3 recebe somente N1 + contrato/configuração.
- [ ] N2/N4 aparecem apenas como comparação independente.
- [ ] HTML/checkbox é apresentação, não ground truth.

## Rota de execução

- [ ] Mudança N1 usa headless único com `--wait`.
- [ ] Mudança apenas N3/N4 usa gerador/ficha individual, sem headless.
- [ ] Gate visual usa `g2v_harness.py --backend cli` e o PNG foi lido.
- [ ] Não há execução AutoCAD/headless paralela.

## Decisão

- [ ] `CONFIRMAR` somente com adaptador autorizado (LAJ/PIL/FV/LV) e evidência independente.
- [ ] PASS de um segmento/contrato FV/LV não é tratado como ficha/viga inteira aprovada.
- [ ] Autoridade da classe confere com `data/authority_matrix.json`.
- [ ] Achado tem causa geral; nenhuma medida foi hardcodada por item.
- [ ] Fix executado tem regressão proporcional e nenhum FAIL novo.

## RAG

- [ ] Consulta filtra classe, família, campo, tier e escopo.
- [ ] T1/T2 é citado; T3 nunca confirma campo.
- [ ] Candidato exige aprovação humana; promoção não é automática.


### Consolidação de níveis — 2026-10-01

Regra integrada: `docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md` (canônico). Para níveis: conferir região efetivamente tocada; converter cm/m; separar topo FV de fundo físico; conferir correspondência FV/LV e intervalos; exigir fonte mais fraca/fator/cobertura no score; rejeitar ciclos e conflitos no mesmo escopo; preservar estimated; não confundir cotas de regiões distintas com conflito; registrar veredito por unidade e ler PNG real antes de selar.

### QA de ausência de laje — NIV-SEM-LAJE-20261002

Conferir PNG e handles de escada/rampa/X; ausência comprovada não é laje sem nível. Saída vem da convenção, não da base anterior; alternativa modal conta um voto por laje válida e rejeita ambiguidade. Preservar corte, cota local, rebaixo e revisão humana. Referência de projeto não é medida de corte; confiança deriva de fonte e cobertura. FV/LV/PIL mantêm cadeia sem ciclos; fundo desconta altura; pilar lê a face em contato. Representações ainda não reconhecidas continuam pendentes, sem inventar laje ou certificar ausência por proximidade.

### QA de seeds espaciais — 2026-10-02

Conferir no manual integrado §8: contato regional deve ter cobertura longitudinal suficiente, não apenas uma extremidade; buraco regional desconhecido não herda cota principal; seeds humanos/medidos/inferidos existentes permanecem preservados; contato sem offset de corte continua inferência explícita. Auditar confiança por cadeia, fontes congeladas sem ciclos e faixas sem lacunas. Contar segmentos estimados e faixas estimadas separadamente: reduzir um total não certifica o restante. Recorte PNG deve incluir a região inteira quando o rótulo estiver distante do trecho tocado (exemplo datado VF301/S9 e L317).


### QA continuidade de nível da lateral — NIV-LV-CONTINUIDADE-20261002

Passagem pelo pilar não altera nível do segmento lateral. Auditar extensão apenas dentro do segmento existente com fontes suportadas concordantes; preservar intervalos, IDs, geometria e referência de origem. Estimativas não confirmam outras estimativas. Níveis distintos/conflito impedem propagação e exigem conferir segmentação/corte. Confiança nunca aumenta; grafo deve continuar acíclico.


### QA de lateral no degrau — NIV-LV-DEGRAUS-20261002

- Conferir PNG CAD real, limite das regiões LAJ e contato da face LV; inset que não toca a face não gera divisão.
- Auditar Para e Passa separadamente: segmentos encostados, sem lacunas/sobreposição ou perda de comprimento; N3 conserva sequência e aberturas.
- Não unir contatos desconexos da mesma laje nem usar sua cota escalar sobre uma região diferente.
- Separar nível da laje, referência FV/LV e fundo físico; degrau de laje não implica mudança automática do fundo.
- Trecho sobre pilar usa fonte congelada da mesma face/comportamento/profundidade e ligação geométrica. Não cruzar degrau na ligação; degrau remoto não bloqueia continuidade no pilar.
- Auditar precedência por profundidade no cruzamento, inclusive abertura de viga menos profunda; pilar não altera nível.
- Preservar fonte mais fraca, fator de transferência, estimativas e conflitos reais; não certificar pela redução da contagem de pendências.

### Auditoria de fontes cruzadas e consumo SA — 2026-10-02

- Conferir B/H da viga contra a largura do próprio fundo antes de aceitar rótulo ou alimentar PIL; seção do pilar vizinho não é seção de viga. Alternativas incompatíveis exigem abstenção.
- Conferir espessura LAJ canônica `fields.laje_dim` no snapshot de evidências; campo legado vazio não prova ausência de espessura.
- Auditar IDs reais dos fatos resolvidos e regiões principal/interna separadamente, sem falso conflito entre cotas de regiões distintas.
- Derivação de cota por corte deve chegar ao consumidor SA com geometria, fontes, delta, confiança e proteção de valores humanos; testar também mudança de geometria, conflito e fonte estimada.
- Faixa interior sem FV exige vizinhos imediatos suportados concordantes; não atravessar transição nem preencher extremidade sem fonte. Status agregado preenchido não certifica todas as faixas.
- Degrau LAJ não prova mudança da viga: exigir corte ou transição de hatch/preenchimento da própria viga. Conferir cota regional LAJ, referência FV/LV e painel superior separadamente; manter a divisão Para/Passa. Principal ausente ou outra zona de seção não fornece confirmação. Conferir o fechamento nominal e as tolerâncias do painel no PNG N3.


### QA de corte e seção contínua — NIV-CORTE-CONTINUIDADE-20261003

- Inspecionar PNG do DXF real: haste do corte, largura FV, profundidade e aba com espessura da laje; não aceitar somente nome de viga.
- Conferir dimensões por trecho, rejeitar B/H de pilar e manter múltiplas seções. Conferir cobertura espacial e IDs da seção lateral usada para H.
- Bloquear corte discordante, mudança de largura/profundidade, decisão humana discordante e preenchimento interno não revisado; DXF ausente bloqueia transferência. Bbox de hatch é guard conservador, não reconhecimento completo.
- Fonte congelada e grafo acíclico; fator 0,95 sem amplificação por concordância. Contar estimativas por faixa, separadamente de inferências e status agregado.
- Executar coleta oficial desde o SA bruto, não somente resolver novamente um pacote já derivado. Registros de cortes temporários devem vir da mesma passagem em memória.


### Referência padrão e treino de exceções — NIV-PADRAO-EXCECAO-20261003

Aplicar o contrato global em `docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md`, seção Referência padrão e exceções explícitas. O padrão confirmado é topo da viga no nível principal da laje ou base de saída do pavimento quando não há laje, salvo indicação explícita diferente. Ausência de corte não torna esse padrão uma estimativa por si só. Preservar regiões de laje, datum da viga, contato por face do pilar e fontes independentes. QA distingue convenção de medida e verifica qualidade/cobertura da leitura antes de confirmar; não elevar score apenas renomeando status. Interpretação de vigas em níveis diferentes por hatch/corte está pendente de treino com exemplos reais futuros; não foi certificada neste caso.

- V16: conferir `level_basis=owner_convention` preservado nas transferências e `status=inferred` mesmo acima de 80; fonte × 0,95 × cobertura, cap provisório 85, sem soma de corroboradores. Resolver fonte FV/LV independente antes da convenção; a convenção fraca não pode suprimir suporte melhor. Conferir bloqueios de DXF ausente, corte local/encurtado, preenchimento interno não interpretado, conflito, decisão humana e mudança de datum. Validar valores e geometria antes/depois; não confundir prova isolada com publicação oficial.


### Rastreio de confiança por região e segmento — QA-NIV-RASTREIO-20261003

Antes de perguntar ao dono ou alterar score, seguir `source_fact_ids` até as fontes independentes; registrar CAD/handles, região principal ou interna, posição do corte, datum, unidade, cobertura e fator de transferência. Fonte inferida com somente nome da laje ou ID de coleção não equivale a uma cota CAD rastreada. Uma região medida não confirma automaticamente outra região da mesma laje. Não contar a mesma origem em FV/LV/LAJ como provas independentes.

Conferir primeiro se o problema é leitura/associação: corte com haste interrompida pode conservar delta de abas, mas não comprova altura absoluta; ligar a aba à região realmente tocada e à espessura correspondente. Não elevar confiança apenas pelo nome do método ou por concordância que nasceu do mesmo fato. Avisos de níveis múltiplos só podem ser removidos após resolver a região proprietária e o contato; não apagar a penalidade genericamente.

FV e LV têm contratos próprios de geometria, apoios e segmentos. Transferência de nível com fonte independente congelada, prova espacial e grafo acíclico é permitida; não autoriza copiar esses outros campos nem equiparar a quantidade de segmentos. Padrão aprovado pelo dono, medida e derivação permanecem origens distintas. Score é suporte de evidência, não probabilidade calibrada; melhorar rastreabilidade pode mudar o suporte somente após validação por faixa, sem selo automático.

Pergunta humana deve indicar o trecho e alternativas concretas após tentar cortes, hachuras, cotas, regiões LAJ e correspondência FV/LV. Falha do coletor em encontrar uma fonte não prova ausência no desenho. Caso datado e diagnóstico reproduzível: `scripts/arete/relatorios/20261003-nivel-padrao/remaining-audit.json`; não transformar seu resultado em regra fixa por item.


### Proveniência de regiões e reverificação de inferências — NIV-CORTE-PROVENIENCIA-20261003

Implementação v17: região derivada de degrau por fundo contínuo só usa a contraparte com cota CAD direta, seção comprovada, espessuras regionais, ausência de conflito e delta coerente. Registrar source_fact_ids e delta_cm; score = fonte × 0,90. Duas regiões inferidas não se confirmam mutuamente. Conservar IDs do corte e cotas e geometria originais.

Um escalar LAJ já inferido não deve impedir a busca de prova geométrica independente. Resolver abas horizontais em três estações com espessura coerente, fontes congeladas e valores concordantes; aceitar somente o mesmo nível existente com suporte maior, preservando evidência anterior. Nível humano/medido, conflito, alternativa diferente, fonte inferida sem âncora e espessura incompatível não são substituídos. Esse mecanismo não certifica cortes verticais, escala arbitrária ou todas as exceções de hatch.

QA distingue implementação geral de resultado datado. No 13_PAV/Torre 1, job v17 c7568d3f-6bba-475d-9720-1e320b272e61 confirmado: 28 faixas com suporte maior, 213→196 abaixo de 60, níveis e geometria preservados, fontes acíclicas. Restante não foi certificado. Evidência e limites: scripts/arete/relatorios/20261003-auditoria-confianca/RELATORIO.md. Não elevar percentuais de outras obras por esse resultado.


### Harmonia das confirmações — NIV-HARMONIA-GATES-20261003

Contrato canônico: docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md, seção Harmonia de fontes, gates e explicação. Plano aprovado; implementação nova delegada e não certificada por este texto.

- Auditar origem/revisão, associação espacial, grandeza/unidade/datum, exceções/completude da leitura e concordância por intervalo.
- Separar corte CAD e seção A/B reconstruída. Nível herdado em corte reconstruído, N3/N4 ou outra classe não é nova prova; deduplicar raízes físicas compartilhadas. RAG é regra/contexto, não voto.
- Fonte forte não apaga conflito válido. Entradas necessárias limitam o caminho; alternativas fracas irrelevantes não devem ser confundidas com essas entradas.
- Exigir fontes congeladas, grafo acíclico e preservação humana; PIL não certifica de volta FV/LV/LAJ.
- Percentual com explicação por unidade: fonte, cálculo, confirmações independentes, gates e limitações. Confiança do nome não é confiança do nível. Nenhum bônus arbitrário ou probabilidade sem calibração independente.
- Comparar baseline/revisão por unidade e testar duplicação, permutação, ciclos, contradições, degraus, cortes interrompidos, ausência de laje e passagem por pilar. Relatar implementação, teste, publicação, consumo e PNG separadamente.


### Caminho de evidência v18 — NIV-EVIDENCIA-CAMINHOS-20261003

Implementação do plano acima no motor v18 (`level_provenance.py`, rubrica `level_evidence_completeness_v1.1-best-validated-path`). Ao revisar um nível:
- Ler `support_explanation` do fato: fonte principal/tipo de origem, cadeia de cálculo, origens, confirmações (sem bônus), limitações e gates. Gate `fail` em origem, ciclo, fontes presentes, grandeza ou transferência = nível não certificável.
- Associação FV↔corte só vale com `cut_association=stem_matches_fv_section` (tronco com profundidade/largura da FV); `contact_only` mantém o mais fraco.
- Corte girado só re-prova valor existente; espessura de asa desenhada ≠ h declarado = abstenção correta (ex.: L303, L321 no 13_PAV), não FAIL do motor.
- `evidence_provenance` da torre deve ter ciclos=0, fontes ausentes=0 e violações de aumento=0. Resultado datado: scripts/arete/relatorios/20261003-evidencia-caminhos/RELATORIO.md.

### Datum comum v19 — NIV-DATUM-COMUM-20261003

Fundo resolvido por `standard_beam_top_principal_slab` com aviso `lower_adjacent_slab_closed_by_top_panel`: conferir que as fontes são a laje no datum + o datum do pavimento, que toda laje em `lower_contact_slabs` está abaixo do datum e que nenhuma laje acima toca o fundo (laje acima = abstenção obrigatória; só corte/hachura mudam a viga). Laje sem cota no DXF continua fraca e não é FAIL do motor. Resultado datado: scripts/arete/relatorios/20261003-faixas-sem-raiz/RELATORIO.md.

### Nível de laje em camadas v20 — NIV-LAJE-CAMADAS-20261003

Laje com `method` = `slab_neighbor_continuity_without_step_cut` (teto 85) ou `slab_neighbor_majority_vote` (teto 75): conferir em `neighbor_votes` que cada vizinha está do outro lado de uma viga real (seção de FV no corredor, não distância), que cada voto vem de origem CAD/humana distinta e que nenhum voto tem a própria laje alvo nas raízes (ciclicidade). Empate deve abster. Voto através de viga em `proven_step_lines` (pares CAD já diferem) deve estar em `withheld_votes`, nunca contado. Valor da camada diferente do SA aparece em `slab_level_layers.not_applied`, nunca aplicado. Aviso `drawn_wing_thickness_differs_from_declared_h`: o h declarado vence a asa desenhada; a asa só re-prova o valor que já existe. Não há hachura de laje como evidência. Regra: docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md, seção NIV-LAJE-CAMADAS-20261003.
