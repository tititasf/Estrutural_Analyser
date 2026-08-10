# LAJ — manual granular de interpretação, validação e evolução

## 1. Ordem de verdade: contorno antes de painel

N1 de laje é uma entidade de contorno, nível, apoios, corte, vizinhança, obstáculos e
uniões. `src/core/slab_tracer.py` captura/interpreta; a ficha é
`src/ui/widgets/preficha_laje_html.py`. O N3 nasce do contorno N1, não de um padrão
N2/N4. A ordem é imutável: **identidade → contorno/área → apoios → contexto/exceções
→ panelização → desenho**.

| Família | Campos/prova | Aceite | Anti-padrão |
|---|---|---|---|
| identidade | `name.label`, `laje_dim.label`, `laje_nivel.label` | nome, espessura e nível do mesmo item | nível copiado de vizinha |
| contorno | `points_json`, `laje_outline_segs.contour` | fechado, área/bbox, chanfros/degraus corretos | painéis “bons” sobre contorno errado |
| apoios | `laje_pilares_apoio.pillar_geom`, `touch_face`, hatch | pilar identificado toca a face real | apoio por proximidade de bbox |
| corte/contexto | `laje_visao_corte`, vizinhas, níveis/eixos | explica transição sem alterar contorno | corte usado como geometria fonte |
| exceções | obstáculos, `unioes_nos_bordes` | cada item tem origem e contato | obstáculo/união inventado |
| painéis | linhas verticais/horizontais | cada linha rastreável no contorno aceito | contagem substitui posição |

Cada ficha contém SVG local (contorno, degraus/chanfros, nível e contato real) e SVG
contextual (vizinhas, corte, pilares/vigas/eixos). Contexto explica topologia; nunca
prova apoio por si só.

### 1.1 Visão canónica (obrigatória em N1-V / G2-V / G5-V)

Documento mestre: [`docs/QA-VISAO-EVIDENCIA-CANONICA.md`](../../QA-VISAO-EVIDENCIA-CANONICA.md).

Gates visuais de LAJ: conteúdo full layers (hatch, cotas). **Agente = PNG**;
**persist/app/portal = SVG**. Headless sem persist = imagem só. Score/bbox sem
vision = **ruído**. g2v_harness.py --backend cli + inventário.
docs/QA-VISAO-EVIDENCIA-CANONICA.md.

## 2. Diagnóstico e S5: o que o automatismo não fecha

`diagnostico_laj_n1_n2.py` alerta comparabilidade/dimensão; não dá veredito de
polígono, hachura de apoio, posição de cota, obstáculo ou linha de painel. Para S5,
matriz N1×N2 por item: nome, nível, contorno, área, cada apoio e face de contato,
corte, vizinha, obstáculo, união e linha de painel. Valor tolerado é 0,05 quando
comparável; forma/contato/exceção dependem da leitura SVG pelo modelo/agente CLI.
Registrar **score** de concordância, match/mismatch/N/A e causa provável; score sem
prova visual não libera N3.

```powershell
python scripts/arete/qa_evidence_auditor.py review --project-id <ID> --classe LAJ --include-sealed
python scripts/arete/qa_profile_probe.py --classe LAJ --probe support_identity_and_contact `
  --item L318 --project-id <ID>
python scripts/arete/headless_sa_analise.py --obra <OBRA> --pav <PAV> --secao lajes --item L318 --wait
# Comparação diagnóstica N1×N2; não substitui o N1-V/G4-V N1-only.
python scripts/arete/g2v_harness.py --classe LAJ --pav <PAV> --par n1xn2 --item L318 --backend cli
```

N2 é referência de comparação e diagnóstico; não preenche coordenada, apoio ou padrão
N1. Campos só-N2/teto estrutural viram N/A justificado, não match artificial.

## 3. Roteamento de casos complexos

| Caso | Verificação | Dono provável | Regressão mínima |
|---|---|---|---|
| contorno em L/chanfro/degrau | vértices, fechamento, área e SVG local | `slab_tracer` | caso retangular + irregular |
| apoio de pilar | identidade PIL, bbox/face e contato | relação LAJ↔PIL | apoio central e borda |
| obstáculo interno | entidade/origem, vazio e posição | `slab_tracer` | laje sem obstáculo |
| união no bordo | continuidade e borda específica | `slab_tracer`/contrato | união ausente e presente |
| corte/vizinhança | nível/transição, sem reescrever contorno | contexto LAJ | mesma laje sem vizinha |
| painel torto/deslocado | contorno aceito, depois linha/offset | gerador N3 | painel interior e borda |

## 4. N3 e persistência

Contrato N3: coordenadas, dimensões/área, `linhas_verticais`,
`linhas_horizontais`, `obstaculos`, `unioes_nos_bordes`, observações e proveniência.
Gerar N3 individual, rodar smoke, abrir ficha do motor e então G5-V
(paridade final N3×N4) por SVG/CLI. Smoke não aprova vazio, união ou equivalência
geométrica.

Se `laje_outline_segs` foi validado, contorno e `points` não são substituídos pela
reanálise; dimensão, nível, pilares e corte não validados continuam evoluindo. Mudança
em `slab_tracer` exige microciclo + diagnóstico LAJ + N1-V e regressão da classe;
registrar `HISTORICO/LAJ.md`.

## 5. Autoevolução e candidato RAG LAJ

Cada BLUE/laranja de LAJ acrescenta contorno, apoio/face de contato, nível, obstáculo,
união, corte/vizinhança e contraexemplo à documentação e ao diário. O candidato RAG
multimodal preserva HTML/SVG, polígonos, hashes, matriz N1×N2 e decisão humana; não
transforma padrão N2/N4 em geometria N1. Todos os laranjas LAJ do pavimento geram
pacote consolidado e pedido de validação humana para curadoria RAG LAJ.

## 6. Quadro read-only por pavimento

`scripts/arete/qa_laj_quadro_pavimento.py` é a projeção operacional de LAJ por
obra/pavimento. Recebe `--project-id`, `--obra`, `--pav` e `--output-dir` e gera
`QUADRO-LAJ-PAVIMENTO.html`, JSON, CSV, Markdown, SVGs de `points_json` e um
manifesto de hashes **sem escrever no DB**. O quadro é regenerado após qualquer
microciclo que leia ou produza evidência persistida; a regeneração nunca executa
headless, gerador, gate ou selo.

```powershell
D:\Agente-cad-PYSIDE\.venv\Scripts\python.exe -X utf8 scripts/arete/qa_laj_quadro_pavimento.py `
  --project-id <ID> --obra Obra_TREINO_1 --pav 13_PAV `
  --output-dir scripts/arete/relatorios/qa_laj_quadro_pavimento/<run>
```

O quadro mostra quatro cards em dois recortes: **todos os tempos** e o
**pavimento atual**. A tabela é uma linha por laje e segue exatamente
`N2 → N4 → N1/SA → Campos N1 → N1-V CLI → N1×N2 → N3 → N3-V → N3×N4 → N3×N2 → RAG T1 por item`.
N4 só apresenta os selos azul humano e laranja QA; N1 e N3 apresentam os quatro
selos de item. G2 e G2-V são evidências dentro de N4, nunca cards independentes.

As famílias LAJ permanecem independentes: polígono/contorno; dimensões e
espessura; níveis; furos/recortes; visão de corte; pilares/vigas de apoio; e
interferências/continuidade. Na tabela elas são condensadas na coluna **Campos
N1**, que conta os oito campos obrigatórios do contrato LAJ por origem de selo
(`azul/laranja/rosa`, por exemplo `laranja 5/8`); o detalhamento por família fica
preservado em `detalhe_campos_n1` no JSON. Relação de vizinhança ou proximidade é
contexto e nunca substitui a prova geométrica isolada nem o contato de um apoio.
Os campos N1 exibem apenas `points_json` e os paths permitidos pelo perfil LAJ;
N2/N4 são comparadores e não completam campos N1/N3.

O SVG local é uma visualização do `points_json` persistido, com hash e vínculo
ao item. Ele não é veredito. **N1-V/G4-V lê somente os SVGs N1 próximo/local e
distante/contextual contra o DXF original**: não abre nem usa N2. N1×N2 é uma
coluna diagnóstica separada, nunca entrada ou referência visual do N1-V. Um
estado visual só é mostrado como decidido quando há resultado persistido de
`g2v_harness.py --backend cli` com fonte `html_svg_vetorial`; API visual e PNG
não são fontes de decisão.

> **Contrato N1-V/G4-V N1-only:** a evidência obrigatória é SVG N1
> próximo/local + SVG N1 distante/contextual + DXF original. O par legado
> `g2v_harness --par n1xn2` é comparação N1×N2 e fica restrito à coluna
> diagnóstica S5; ele não pode acender N1-V no quadro. Até o harness canônico
> materializar esse par N1-only, N1-V permanece `PENDENTE` de modo explícito.

**N3-V** é outro veredito visual, independente: lê somente o SVG vetorial N3 e
verifica cotas, linhas de painel verticais/horizontais, recortes, uniões e
distribuição de painéis. Ele não cria nem reescreve N3 e não usa N2/N4 como
entrada; paridades N3×N4 e N3×N2 continuam diagnósticos posteriores separados.

A coluna final **RAG T1 por item** registra a ingestão pós-QA, não uma hipótese:
só mostra `INGERIDO` quando há regra T1 em `semantic_rag_kb` e evento humano
`APPROVED` em `human_event_logs` para o mesmo `candidate_id`. Ela lista os campos
do próprio item que foram alimentados e a data da última aprovação. Candidato
materializado, `rag_indexed` de ficha N2, ou consulta de RAG não acendem a coluna.
O RAG continua consultivo e nunca substitui a evidência geométrica local.

### Limitações declaradas

- Um registro legado de `slabs` cujo `extra_data_json` contenha coordenadas,
  linhas de painel ou dimensões, mas cujo `points_json` esteja vazio e cujos
  links N1 estejam vazios, **não é N1 materializado**: aqueles dados podem ser
  resíduo de painel/robô e não provam contorno, apoio, nível ou corte. O
  quadro deve manter S3/S4 pendentes e a rota correta é
  `headless_sa_analise.py --secao lajes --item ... --persist-db --wait`, usando
  somente os itens da classe; nunca copiar a geometria legada para `points_json`;

- recorte/furo sem payload estrutural próprio permanece `TRILHA_N1_OBSERVADA`
  ou `PENDENTE`; vértice adicional do contorno apenas sinaliza recorte, não prova
  semântica de furo;
- apoio só sobe de estado com identidade, geometria e contato/face no payload;
  o quadro não calcula contato por bbox de vizinhos;
- fichas N2 legadas podem não carregar `projeto_id`; no quadro elas são lidas
  apenas pelo escopo explícito obra+pavimento+classe e identificadas como
  comparação histórica;
- smoke N3 e diagnóstico numérico não criam selo nem substituem G2-V/N1-V/G5-V.
