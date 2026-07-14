# QA por classe — compreensão SA N1 e validação N3

## Objetivo e limite

Este documento é a premissa operacional do Agente QA Global para `PIL`, `LAJ`,
`FV` e `LV`. Os perfis executáveis ficam em
`squads/qa-global-evidencias/data/class_profiles/`.

Há quatro perguntas diferentes e elas não podem compartilhar um PASS:

| Pergunta | Ferramenta mínima | O que o PASS autoriza |
|---|---|---|
| O campo persistido e seu vínculo localizado são coerentes? | `qa_profile_probe.py` ou `qa_n1_field_probe.py` | somente os checks declarados |
| Uma mudança de extrator realmente materializou N1? | headless canônico, único, granular e `--wait`, seguido do probe | o snapshot novo nos checks declarados |
| O contrato N3 chegou ao DXF da variante? | `qa_n3_smoke.py` | identidade, texto e camadas mínimas |
| O desenho está correto e equivalente? | ficha individual e gate visual canônico | somente o veredito visual registrado |

`PENDENTE` retorna código 2. Escopo de projeto nunca é inferido do exemplo do
perfil; use `--project-id`, `--obra`+`--pav` ou, conscientemente,
`--use-profile-sample`.

## Caminho rápido comum

1. Fixar projeto, classe, item, família, campo e variante.
2. Ler o perfil da classe e a ficha manual indicada nele.
3. Executar o menor probe que consiga refutar a hipótese.
4. Se o valor já está no DB, não rodar headless.
5. Se a regra N1/extrator mudou, rodar um único headless com `--wait` e repetir o probe.
6. Para N3, gerar somente o item/variante, executar o smoke e montar a ficha.
7. Para equivalência geométrica, ler o artefato visual; smoke não fecha o gate.
8. Guardar hashes e classificar o achado sem promover automaticamente ao RAG.

Os adaptadores de `FV` e `LV` leem a mesma tabela `beams`, mas possuem allowlists
de paths distintas. Um request `FV` não pode consultar `lv_generation_contracts`;
um request `LV` não pode consultar `viga_fundo_*`. Geometria bruta compartilhada
é contexto, nunca licença para copiar semântica.

## PIL — pilares

### Premissa N1

Pilar é uma entidade geométrica com identidade, dimensão, nível e faces localizadas.
Faces A/B são longas e C/D curtas no retangular; pilares especiais ampliam para
E/F/G/H. Cada relação precisa conservar face, canto, entidade, dimensão e origem.

| Família | Campos/fontes | Pergunta correta |
|---|---|---|
| identidade/geometria | `name.label`, `points_json`, `pilar_segs`, dimensão extra | nome, bbox e dimensão descrevem a mesma entidade? |
| faces | `p_s{face}_l1_n`, `p_s{face}_v_passa_*`, `p_s{face}_v_chega_*` | a entidade toca/corre/chega na face declarada? |
| PARA | vazio de topo, abertura de viga que para, abertura de chegada, níveis | o contrato PARA aplica a regra do canto/centro correto? |
| PASSA | viga mais profunda, vazio, neutralização de chegadas | a seleção dominante e a neutralização são justificadas? |
| montagem | grades, parafusos, espaçamentos e sarrafos | o contrato separa CIMA, ABCD e GRADES? |

O probe `face_beam_identity_dimension_contact` testa uma face de cada vez. Um PASS
na face D não aprova A/B/C, PARA/PASSA, vazio, abertura, grade ou altura.

O adaptador de cobertura `qa_pil_coverage.py` percorre todas as faces A-D e os
slots `passa_esq`, `passa_dir`, `ch1..ch3`, exige as cinco famílias acima e roda
probes cross-classe por vínculo materializado. Ele detecta conflitos como nome de
viga gravado no slot de dimensão. Seu estado é `coverage_ready`, mas a autoridade de
escrita permanece `diagnostic_only` até cobertura completa, regressão, visão e QG7
humano. Cobertura não equivale a interpretação correta.

### Premissa N3

Variantes: `CIMA`, `ABCD_PARA`, `ABCD_PASSA`, `GRADES_PARA` e `GRADES_PASSA`.
`CIMA` é único; PARA/PASSA não podem compartilhar silenciosamente os contratos de
ABCD/GRADES. As famílias de saída são:

- base: nome, comprimento, largura, altura e níveis;
- faces: `h1_X..h5_X`, `larg1_X..larg3_X`, laje, vazio e aberturas;
- montagem: grades, distâncias e parafusos;
- proveniência: `_sa_meta`, `_sa_mode_contract`, `_sa_mode_variant` e intervalos.

O smoke confirma nome/camadas. Aberturas, vazios, segregação GRADES e anticolisão
precisam de metadado específico ou leitura visual.

Referência manual protegida: `interpretacao_abcd.html`; nunca regenerar nem editar.

## LAJ — lajes

### Premissa N1

Laje é interpretada por identidade, dimensão/nível, contorno, corte, apoios,
vizinhança, obstáculos e uniões. O contorno N1 é fonte do N3. Padrão aprendido
pode orientar fórmula, mas não copiar geometria N2/N4.

| Família | Campos/fontes | Validação localizada |
|---|---|---|
| identidade | `name.label`, `laje_dim.label`, `laje_nivel.label` | nome, espessura e nível presentes |
| contorno | `points_json`, `laje_outline_segs.contour` | bbox/área/fechamento coerentes |
| apoios | `laje_pilares_apoio.pillar_geom`, lado e touch | suporte existe e intersecta/toca o contorno |
| contexto | corte, vizinhas, obstáculos, uniões | cada exceção possui entidade de origem |

O probe `support_identity_and_contact` prova um apoio específico e seu contato. Não
aprova todo o contorno, todos os apoios nem a divisão em painéis.

### Premissa N3

O contrato contém coordenadas, comprimento/largura/área, linhas verticais e
horizontais, obstáculos, uniões e `_sa_meta`. Antes de julgar painéis, provar o
contorno; depois linhas; por fim exceções. O smoke só confirma que a identidade
chegou ao DXF e que `NOMENCLATURA`/`PAINEIS` existem.

Qualquer resultado “perfeito” vindo de N2/N4 é vazamento, não sucesso.

## FV — fundos de viga

### Premissa N1

FV é contrato isolado de segmentos de fundo. Cada segmento tem geometria, dimensão
e apoios locais. `fields.viga_fundo_seg_N_local_ini/fim` são apoios do segmento;
`links.apoios.inicio/fim` são limites globais da viga. Eles podem ser entidades
diferentes e não devem ser comparados como sinônimos.

| Família | Campos/fontes | Validação localizada |
|---|---|---|
| identidade | `fields.nome/numero/dimensao` | a ficha pertence à viga pedida |
| segmento | `seg_bottom`, `viga_fundo_seg_N_exists/dim` | geometria e dimensão daquele segmento existem |
| apoio local | `viga_fundo_seg_N_local_ini/fim` | apoio existe na classe indicada e é rastreável |
| limite global | `links.apoios.inicio/fim` | limite da viga existe, sem equipará-lo ao apoio local |
| exceções | furos, cortes e recortes | exceção possui fonte e pertence ao segmento correto |

O probe `first_segment_support_and_dimension` cobre somente o primeiro segmento.
FV nunca usa LV como fallback semântico.

### Premissa N3

Variante `FUNDO_C`, motor `ROBOT_FV_N3_N4`. O contrato conserva ordem dos painéis,
largura, dimensão isolada, altura total, textos de apoio, quebras e exceções. A
dimensão global não substitui a dimensão de cada segmento. Furos/recortes requerem
metadado ou inspeção visual.

## LV — laterais de viga

### Premissa N1

LV é a matriz `lado A/B × comportamento PARA/PASSA`. São quatro contratos
independentes; o corte é contexto comum, não autorização para espelhar dados.

| Família | Campos/fontes | Validação localizada |
|---|---|---|
| identidade | `fields.nome/dimensao`, versão do interpretador | item e dimensão base |
| lado A | `viga_a_seg_N_*` e links correspondentes | seleção/segmentos do lado A |
| lado B | `viga_b_seg_N_*` e links correspondentes | seleção/segmentos do lado B |
| contratos | `lv_generation_contracts.{Para,Passa}.{A,B}` | id, side, behavior e readiness de cada célula |
| exceções | pilares, lajes, pontaletes, grades e eventos | evento pertence ao lado/comportamento correto |

O probe `four_contracts_and_support` percorre os `structural_segments` dos quatro
contratos. Ele valida o padrão de cada `source_key`, exige `source_slot` coerente
com A/B, comprova que as origens PARA/PASSA são disjuntas, lê
`_sa_meta.behavior_isolated=true`, veta `_sa_meta.fv_dimension_fallback` e ainda
confere readiness e um apoio/contato. A origem é por segmento, não no topo do
contrato, pois uma lateral pode conter múltiplos segmentos.

### Premissa N3

Variantes principais: `A_PARA`, `B_PARA`, `A_PASSA`, `B_PASSA`; cortes PARA/PASSA
são contexto. Cada contrato contém `beam_name`, lado, comportamento, segmentos,
ajustes inicial/final, painéis, alturas, grades e eventos. A soma dos painéis deve
reproduzir `total_length`; igualdade PARA/PASSA só é aceitável quando eventos e
ajustes também forem iguais. LV nunca usa dimensão FV como fallback.

## Comandos operacionais

```powershell
# Catálogo de perfis
py -3.12 -X utf8 scripts/arete/qa_profile_probe.py --list

# Probe N1 por perfil; escopo é obrigatório
py -3.12 -X utf8 scripts/arete/qa_profile_probe.py `
  --classe PIL --probe face_beam_identity_dimension_contact `
  --item P35 --var face=D --project-id <ID>

# Smoke N3 de duas variantes, sem DB/headless
py -3.12 -X utf8 scripts/arete/qa_n3_smoke.py `
  --classe PIL --item P35 `
  --contract ABCD_PARA=<para.json> --dxf ABCD_PARA=<para.dxf> `
  --contract ABCD_PASSA=<passa.json> --dxf ABCD_PASSA=<passa.dxf>

# Ficha visual individual depois do smoke
py -3.12 -X utf8 scripts/arete/ficha_motor_item.py `
  --classe PIL --item P35 --nivel N3 `
  --artefato ABCD_PARA=<para.dxf> --contract ABCD_PARA=<para.json>
```

## Provas reais de referência — 13_PAV

Estas provas são exemplos de funcionamento dos adaptadores, não ground truth das
fichas completas:

| Classe | N1 localizado | Resultado | N3 estrutural | Resultado |
|---|---|---:|---|---:|
| PIL | P35, face D, 7 campos/4 checks | PASS | P35 ABCD_PARA+ABCD_PASSA, 10/10 | PASS |
| LAJ | L318, apoio, 8 campos/6 checks | PASS | L318, 5/5 | PASS |
| FV | V301, segmento 1, 7 campos/6 checks | PASS | V301 FUNDO_C, 5/5 | PASS |
| LV | V328, 40 campos/39 checks | PASS | V301 A_PARA+A_PASSA, 10/10 | PASS |

O exemplar N1 LV é V328; o smoke N3 usa o artefato V301 já disponível. São duas
provas independentes do caminho técnico e não uma alegação de paridade V328↔V301.

Relatórios:

- `scripts/arete/relatorios/qa_profile_probes/real_13pav_*_v2.json` e LV `*_v4.json`;
- `scripts/arete/relatorios/qa_n3_smoke/real_13pav_*.json`.

O primeiro perfil FV gerou FAIL ao comparar apoio local P1 com limite global
V309A. O relatório antigo foi preservado; o perfil foi corrigido para representar
as duas semânticas separadamente.

## Decisão sobre tool, hook e MCP

Foi adotado um tool CLI explícito, versionado e testável:

- `qa_profile_probe.py`: leitura ultrafina N1 por perfil;
- `qa_n3_smoke.py`: contrato/DXF por variante;
- `ficha_motor_item.py`: materialização visual sem DB;
- `qa_artifact_parity.py`: specs livres para cadeias adicionais.

Não há hook automático de headless nem MCP de escrita. Um hook implícito poderia
disputar a trava, testar projeto errado ou promover evidência parcial. O único hook
seguro recomendado hoje é CI local para validar JSON dos perfis e os testes dos
tools; ele não acessa DB nem gera artefato. MCP só deve ser reavaliado quando houver
schema estável, operações read-only separadas e autenticação/escopo fail-closed.

## Como ampliar um perfil

1. Adicionar família e probe com pergunta estreita.
2. Declarar cada campo com classe, item, source, path e transform.
3. Declarar checks refutáveis; nunca usar `present` como prova geométrica.
4. Adicionar teste sintético e um exemplar real.
5. Preservar FAIL histórico que motivou o refinamento.
6. Documentar o que o probe não prova.
7. Só então atualizar a rota do agente e considerar o conhecimento para RAG.
