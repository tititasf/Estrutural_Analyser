# Prompts QA por classe — N1 em dois SVGs e microciclo rápido

Substitua `{OBRA}`, `{PAV}`, `{PROJECT_ID}` e `{ITENS}` antes de usar. Cada bloco é
independente e pode ser copiado para uma tarefa separada.

## 1. PIL — pilares

```text
Use [$qa-global-evidencias](C:\Users\Thierry\.codex\skills\qa-global-evidencias\SKILL.md).

Escopo exclusivo: obra {OBRA}, pavimento {PAV}, classe PIL, itens {ITENS},
project_id {PROJECT_ID}. Continue autonomamente item a item até existir algo visual
para eu revisar ou uma dúvida estrutural realmente ambígua. Não mexa em LAJ/FV/LV.

Antes de agir, leia CLAUDE.md do workspace e do repo, AGENTS.md e os documentos
obrigatórios da skill. Leia também docs/INTERPRETACAO-PILARES-ABCD.md e a cópia mais
recente de interpretacao_abcd.html, mas não altere nem regenere esse manual.

Objetivo 1 — consolidar os dois SVGs N1 que já foram criados no trabalho do P35 e
garantir que funcionem para todos os pilares:
- N1 próximo/local: contato real com o contorno, face tocada, seção, cota, chegada,
  passagem e interior;
- N1 distante/contextual: continuidade do eixo/segmento, identidade e dimensão cuja
  etiqueta nasce fora do recorte local;
- ambos vêm da mesma fonte DXF e preservam textos como <text> SVG, sem rasterizar;
- o distante nunca cria vínculo sozinho: identidade distante + contato local precisam
  ser compatíveis e a proveniência deve chegar ao link persistido;
- exatamente dois níveis de zoom. Não crie um terceiro zoom intermediário sem provar
  por caso real que ele resolve informação ausente nos outros dois.

Use o P35 como referência arquitetural, nunca como hardcode: face_beams deve preservar
nome, dimensão, canto/slot, behavior e evidence_segments do fundo de viga. Preserve
PARA e PASSA como contratos diferentes; CIMA é único; GRADES é parte segregada.

Objetivo 2 — aplicar o microciclo rápido desenvolvido no P35 ao lote PIL:
- o único entry point continua scripts/arete/headless_sa_analise.py, sempre --wait;
- para ajuste N1 por item, use o fast path sem instanciar MainWindow, mas execute os
  mesmos motores canônicos e produza snapshot semanticamente equivalente;
- cache deve ser content-addressed e invalidar por DXF, versão/schema e todos os
  arquivos reais dos motores dependentes;
- persistência parcial é upsert apenas dos itens pedidos, nunca delete, e precisa
  guardar vínculos/destaques geométricos no DB real;
- não rode headless para mudança somente N3: gere a variante individual, rode
  qa_n3_smoke.py e ficha_motor_item.py;
- antes de cada headless defina um predicado final. Um segundo headless só é permitido
  se houver nova causa reproduzível e teste barato verde.

Valide primeiro 1 pilar complexo e depois 3 pilares estruturalmente distintos. Para
cada item prove: cinco famílias de qa_pil_coverage.py; campos/links N1; dois SVGs;
contratos CIMA, ABCD_PARA, ABCD_PASSA, GRADES_PARA e GRADES_PASSA; payload/DXF/HTML;
ausência de contaminação GRADES→CIMA/ABCD. Rode testes focados, smoke de todas as
variantes geradas e N1-V/G5-V via g2v_harness.py --backend cli quando aplicável.
Nunca use API visual ou --permitir-api. Não declare Arete sem leitura visual.

Meça e registre tempo frio/quente e compare o snapshot rápido com uma referência
canônica: mesmas entidades, campos, links, geometria e diagnósticos no escopo. Ao
final, entregue ficha clicável, relatório, achados schema v2, correções gerais,
regressões e o próximo item. Se precisar editar pre_validation_dialog.py ou outro
arquivo compartilhado/protegido, confirme concorrência comigo antes.
```
## 2. LAJ — lajes

```text
Use [$qa-global-evidencias](C:\Users\Thierry\.codex\skills\qa-global-evidencias\SKILL.md).

Escopo exclusivo: obra {OBRA}, pavimento {PAV}, classe LAJ, itens {ITENS},
project_id {PROJECT_ID}. Continue autonomamente item a item. Não altere PIL/FV/LV,
exceto leitura cross-classe necessária para provar apoios.

Leia primeiro as regras obrigatórias do repo/skill, depois
docs/QA-PERFIS-CLASSES-SA-N1-N3.md, perfil laj.json,
docs/MASTERPLAN-INTERPRETACAO-VALIDACAO.md e preficha_laje_html.py. N2/N4 são apenas
comparadores: nunca copie contorno, obstáculo, união ou paginação para N1/N3.

Implemente na ficha LAJ exatamente dois SVGs N1, oriundos do mesmo DXF:
- N1 próximo/local: contorno completo e seus degraus/chanfros, dimensão/nível,
  interseção real dos apoios, face/lado tocado, obstáculos e uniões no bordo;
- N1 distante/contextual: lajes vizinhas, níveis vizinhos, visões de corte, eixos,
  pilares/vigas de apoio e etiquetas que expliquem a topologia local;
- preserve texto SVG real e destaque com legenda a entidade-alvo e as evidências;
- contexto distante não autoriza apoio por proximidade: apoio exige identidade e
  contato/interseção provados no zoom próximo e nos links persistidos;
- não adicione zoom intermediário sem evidência de necessidade.

Transfira a arquitetura de performance do P35, não sua semântica:
- mantenha headless_sa_analise.py como único headless e use --wait;
- crie/complete o fast path LAJ sem MainWindow somente se executar SlabTracer e todas
  as dependências que materializam contorno, nível, corte, apoios, vizinhança,
  obstáculos e uniões com resultado equivalente ao caminho canônico;
- cache content-addressed deve invalidar pelo DXF e por cada motor LAJ/cross-classe
  realmente consumido;
- grave no DB real points_json, links e geometrias/destaques de origem; persistência
  parcial é somente upsert dos itens solicitados;
- regra já persistida usa qa_profile_probe.py/qa_n1_field_probe.py sem headless;
- mudança apenas N3 usa gerador individual + qa_n3_smoke.py + ficha_motor_item.py.

Defina predicado final antes de rodar. Valide 1 laje complexa e depois 3 casos
distintos (simples, contorno recortado/obstáculo, união/apoios múltiplos), escolhidos
pelos dados e não hardcoded. Prove famílias identity, geometry, supports e context;
depois prove contratos N3 PAINEIS, OBSTACULOS e UNIOES, contorno/área, rastreabilidade
das linhas e ausência de invenção de exceções. Compare fast path e referência por
campos, links, geometria, contagens e diagnósticos. Registre tempos frio/quente,
testes, smoke e veredito visual CLI quando aplicável. Sem API visual, sem selar golden
com FAIL e sem declarar Arete só por score.

Entregue ficha clicável, relatório schema v2, causa/fix universal, regressões e o
próximo item. Confirme concorrência antes de editar qualquer UI compartilhada.
```

## 3. FV — fundos de viga

```text
Use [$qa-global-evidencias](C:\Users\Thierry\.codex\skills\qa-global-evidencias\SKILL.md).

Escopo exclusivo: obra {OBRA}, pavimento {PAV}, classe FV, itens {ITENS},
project_id {PROJECT_ID}. Continue item a item. PIL pode ser lido para provar apoios;
LV não pode alimentar nem completar FV.

Leia as regras do repo/skill e, em seguida,
docs/ARQUITETURA-INTERPRETADORES-VIGA-N1-ISOLADOS.md, perfil fv.json,
preficha_fundo_html.py, beam_interpreters/fundo_viga.py e fv_generation_contract.py.
Preserve a separação dos interpretadores: nenhum campo LV é fallback semântico FV.

Implemente exatamente dois SVGs N1 na ficha FV:
- N1 próximo/local: cada segmento de fundo selecionado, dimensão isolada do segmento,
  extremidades, apoio inicial/final daquele segmento, furos e recortes em contato;
- N1 distante/contextual: eixo e continuidade da viga completa, nome e dimensão que
  possam estar fora do recorte, pilares/apoios globais e transições entre segmentos;
- textos permanecem <text> SVG e cada destaque identifica o source segment;
- o distante resolve identidade/continuidade, mas nunca cria segmento ou apoio sem
  correspondência geométrica local;
- links persistidos devem carregar points/evidence_segments e distinguir apoio do
  segmento de limite global da viga;
- não crie terceiro zoom sem caso real que demonstre a lacuna.

Adapte o fast path do P35 para FV sem copiar regras de face:
- único headless: headless_sa_analise.py --secao fundos_viga --item ... --wait;
- caminho rápido sem MainWindow deve usar BeamTracer e o interpretador fundo_viga
  canônicos, preservando todos os segmentos e exceções;
- cache content-addressed invalida por DXF, BeamTracer, interpretador FV, contrato e
  dependências comuns reais;
- persistência parcial faz upsert dos itens e conserva campos, links, geometria e
  destaques no DB;
- campo já persistido: probe sem headless; desenho N3: gerador individual, smoke e
  ficha de motor sem headless.

Valide 1 viga multi-segmento e depois 3 casos distintos, escolhidos no DB: simples,
multi-segmento/apoios diferentes e com furo/recorte. Prove identity, segments,
supports e exceptions; confirme dimensão por segmento, ordem e identidade dos
apoios. No N3 FUNDO_C prove nome Vxxx.C, ordem/quantidade dos painéis, dimensões,
apoios e exceções. Compare fast path e referência canônica por snapshot, geometria,
contagens e diagnóstico. Registre benchmark frio/quente, testes, qa_n3_smoke e
veredito visual CLI aplicável. Nunca use API visual, N2/N4 como entrada ou score
numérico como Arete.

Entregue ficha clicável, relatório e triagem schema v2, fixes universais, regressão e
próximo item. Confirme concorrência antes de tocar UI/motores compartilhados.
```

## 4. LV — laterais de viga

```text
Use [$qa-global-evidencias](C:\Users\Thierry\.codex\skills\qa-global-evidencias\SKILL.md).

Escopo exclusivo: obra {OBRA}, pavimento {PAV}, classe LV, itens {ITENS},
project_id {PROJECT_ID}. Continue item a item. PIL/LAJ podem ser lidos para provar
apoios e lajes; FV jamais pode preencher dimensão ou lacuna LV.

Leia as regras do repo/skill e depois docs/LV-COMPREENDER-INTERPRETACAO-FICHAS-N2-N4.md,
docs/MASTERPLAN-ARETE-LATERAL-VIGA.md, perfil lv.json, a cópia mais recente de
interpretacao_laterais.html (somente leitura), preficha_lateral_html.py e
lv_generation_contract.py. Preserve quatro contratos independentes: A_PARA,
B_PARA, A_PASSA e B_PASSA. CORTE é contexto comum, não autorização para espelhar A/B.

Implemente exatamente dois SVGs N1 na ficha LV:
- N1 próximo/local: segmentos do lado A e B isolados, seção, alturas, ajustes de
  início/fim, endpoint events, pilares, aberturas, lajes, pontaletes e grades em contato;
- N1 distante/contextual: eixo/nome/dimensão da viga, continuidade completa, apoios,
  níveis e entidades que explicam eventos nas extremidades fora do recorte;
- preserve <text> SVG, legenda por lado/comportamento e destaque dos source_key/
  source_slot realmente usados;
- contexto distante não pode espelhar A↔B nem PARA↔PASSA e não cria evento sem prova
  local; não adicione terceiro zoom sem caso real.

Transfira o fast path do P35 com equivalência rigorosa:
- único headless: headless_sa_analise.py --secao laterais_viga --item ... --wait;
- o caminho rápido sem MainWindow deve executar BeamTracer + interpretador lateral +
  contratos canônicos e produzir os quatro contratos com behavior_isolated=true;
- cache content-addressed invalida por DXF e todos os motores LV/comuns consumidos;
- persistência parcial é upsert e conserva source_key, source_slot, geometria,
  endpoint_events e destaques no DB real;
- regra/campo persistido usa probe sem headless; mudança só no desenho usa gerador
  individual + qa_n3_smoke.py + ficha_motor_item.py.

Valide 1 LV complexa e depois 3 casos distintos escolhidos pelos dados. Execute a
probe four_contracts_and_support e prove: identidade/dimensão A/B; quatro contract_id;
side e behavior corretos; generation_ready; source_key PARA e PASSA disjuntos;
source_slot correto; behavior_isolated; fv_dimension_fallback=false; apoio e contato.
No N3 valide A_PARA, B_PARA, A_PASSA, B_PASSA, CORTE_PARA e CORTE_PASSA: soma dos
painéis=total_length, eventos/ajustes preservados e igualdade entre variantes somente
quando os fatos forem realmente iguais. Compare fast path e referência por snapshot,
geometria, contagens e diagnósticos; registre tempo frio/quente, testes, smoke e visão
CLI. Nunca use API visual, não toque no manual e não declare Arete por score.

Entregue ficha clicável, relatório/triagem schema v2, fixes universais, regressão e o
próximo item. Confirme concorrência antes de editar UI ou motor compartilhado.
```
