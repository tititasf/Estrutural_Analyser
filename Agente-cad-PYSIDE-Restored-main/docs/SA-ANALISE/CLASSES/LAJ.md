# LAJ — manual granular de interpretação, validação e evolução

## 1. Ordem de verdade: contorno antes de painel

N1 de laje é uma entidade de contorno, nível, apoios, corte, vizinhança, obstáculos e
uniões. `src/core/slab_tracer.py` captura/interpreta; a ficha é
`src/ui/widgets/preficha_laje_html.py`. O N3 nasce do contorno N1, não de um padrão
N2/N4. A ordem é imutável: **identidade → contorno/área → apoios → contexto/exceções
→ panelização → desenho**.

**Jev opcional:** em nível/espessura ou apoio por aresta com marcadores
concorrentes, enviar handles, região física, `h=` e contorno; se a convenção do
desnível permanecer ambígua, usar ficha visual para decisão humana. Ver
[segunda leitura do SA](../JEV-SEGUNDA-LEITURA-OPCIONAL.md).

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

### Contato ausente no resultado não prova ausência na fonte — 09/10/2026

Antes de interpretar uma faixa FV/LV como sem laje, conferir o contorno LAJ e
suas regiões no DXF original. O diagnóstico de contato opera sobre os polígonos
coletados: um contorno incompleto pode perder tanto o apoio quanto a marca de
nível regional. `slab_steps=[]` é resultado de coleta, não prova física de que
não existe degrau. Não corrigir esse caso só aumentando confiança ou mudando o
nível da viga; recuperar a geometria/região e repetir a correspondência local.

A inspeção fonte+PNG do 14_PAV encontrou região junto à V410 ausente do
contorno persistido de L405 e contatos junto à V420 que os polígonos coletados
não reproduzem. Evidências e limites no
[dossiê da inspeção](../../../scripts/arete/relatorios/20261009_continuacao_niveis_14pav/inspecao_niveis/RELATORIO.md).
É diagnóstico local para reparo do coletor, sem alteração de dados/decisão do
dono e sem aprovação de níveis ou regiões ainda não reprocessados.

### 1.1 Visão canónica (obrigatória em N1-V / G2-V / G5-V)

Documento mestre: [`docs/QA-VISAO-EVIDENCIA-CANONICA.md`](../../QA-VISAO-EVIDENCIA-CANONICA.md).

Gates visuais de LAJ: conteúdo full layers (hatch, cotas). **Agente = PNG**;
**persist/app/portal = SVG**. Headless sem persist = imagem só. Score/bbox sem
vision = **ruído**. g2v_harness.py --backend cli + inventário.
docs/QA-VISAO-EVIDENCIA-CANONICA.md.

## 2. Diagnóstico e S5: o que o automatismo não fecha

### Degraus internos e cortes de laje (2026-10-01)

O dono pediu destaque amarelo dos trechos internos demarcados com `h=` diferente,
inclusive sem símbolo de corte. A região vem do contorno interno real do DXF,
contido na laje, com espessuras explícitas dentro e fora. A cota interna pertence
ao trecho: não vira automaticamente o nível de toda a laje. Comparar os fundos
em metros, `nível − h/100`, conforme D-52: iguais mantêm uma laje; diferentes
comprovados recebem vermelho no destaque das lajes e indicação de separação.
Uma cota ausente permanece pendente, sinalizada em amarelo. Diferença só de h, sem cota nesse trecho e sem visão de corte nessa área indicando o nível, não é degrau de nível diferente: o nível permanece o da laje e o fundo não é declarado diferente. Degrau de nível diferente continua exigindo cota no trecho ou visão de corte nessa área (NIV-DEGRAU-H-E-VOTO-20261004).

Cortes próprios de laje entram em Visão de Cortes com o nome da laje e amarelo,
sem associação FV/LV nem identidade de viga. Reconhecimento exige seção estreita
atravessando a região interna, duas larguras compatíveis com os `h=` e uma borda
contínua; se apenas uma cota estiver presente, essa continuidade do fundo permite
transportar o desnível. Seção T de viga não é corte de laje. Cada resultado conserva
handles, cotas, espessuras, método e pendências. O contorno principal e os dados
humanamente validados permanecem preservados. Implementação: `src/core/slab_steps.py`.

### Referências FV/LV na ficha de Visão de Cortes (2026-09-30)

Pedido do dono: fundos e laterais ajudam a identificar o nome e os segmentos
representados pelo corte, como referência e nunca como regra rígida. A associação
anterior usa o texto de viga mais próximo do símbolo e pode escolher outra viga.
O portal compara o polígono reconhecido com as geometrias dos segmentos do SA,
sem filtrar pelo nome atual. Exibe nome sugerido, divergência/concordância e os
IDs/índices reais de fundo e de laterais A/B × Para/Passa, com links às fichas.

A hipótese exige contato com fundo e lateral do mesmo nome no entorno local,
sem nome concorrente. Só fundo, só lateral, proximidade sem contato de fundo,
ausência de fonte ou nomes concorrentes permanecem pendentes. A largura da faixa
delimita a busca; não impõe altura, número ou comprimento ao símbolo da seção.
Não se escolhe uma viga distante só por ser a mais próxima, nem se contam as
variantes Para/Passa como votos independentes. FV/LV derivam do mesmo SA e podem
compartilhar um erro: concordância não substitui conferência do rótulo e da posição
no DXF. Os campos derivados são referências de leitura, sem selo de validação;
os dados originais no arquivo SA permanecem intactos. Implementação:
`portal/app/corte_references.py`, integração em `ficha_reader.listar_itens_n1`.

Atualização por orientação do dono (2026-09-30): a associação FV/LV única e
consistente agora define o nome do corte no portal: campo Viga, título da ficha,
lista e rótulo do destaque estrutural. O nome anterior fica somente no campo
“Nome anterior · diagnóstico”. Sem associação suficiente ou com nomes
concorrentes, o nome fica “Pendente”; não se reutiliza o nome antigo como verdade.
Os arquivos SA e a geometria reconhecida não são sobrescritos. O critério local
de associação permanece o mesmo; FV/LV não impõem dimensão ou formato ao corte.

### Diagnóstico canônico

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


### Consolidação de níveis — 2026-10-01

Regra integrada: `docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md` (canônico). Cotas pertencem à região interna ou principal, não ao contorno inteiro. Comparar fundos em metros. Delta entre abas intactas de um corte pode resolver laje sem cota mesmo com haste interrompida, após conferir espessuras e contato real. L317 é prova local (L316/BD4 852,16 + 3 cm = 852,19); não hardcode. Revisões de fundo contínuo exigem UID e SHA do DXF; conflito CAD não é sobrescrito. A ficha lista principal e cada degrau separadamente.


### Referência padrão e treino de exceções — NIV-PADRAO-EXCECAO-20261003

Aplicar o contrato global em `docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md`, seção Referência padrão e exceções explícitas. O padrão confirmado é topo da viga no nível principal da laje ou base de saída do pavimento quando não há laje, salvo indicação explícita diferente. Ausência de corte não torna esse padrão uma estimativa por si só. Preservar regiões de laje, datum da viga, contato por face do pilar e fontes independentes. QA distingue convenção de medida e verifica qualidade/cobertura da leitura antes de confirmar; não elevar score apenas renomeando status. Interpretação de vigas em níveis diferentes por hatch/corte está pendente de treino com exemplos reais futuros; não foi certificada neste caso.


## Apresentação N3/N5 por modo — 07/10/2026

INI, NOVA e Formascia têm padrões de desenho distintos sobre o mesmo contrato estrutural. Consultar a [matriz canônica de desenho](../../PADROES-DESENHO-N3-N5.md) e o [padrão INI aprovado](../../PADRAO-INI-APROVADO.md). A aprovação visual não altera os dados SA nem certifica automaticamente todos os itens. LAJ INI compartilha o N3/perfil NOVA; os compositores N5 continuam separados.

## Lajes sem rótulos e faixas listradas — 08/10/2026

Pedido do dono: interpretar a região interna entre faces de vigas e pilares, conferindo as classes em conjunto contra o CAD. Linhas estruturais não podem atravessar o interior da laje. Cotas, strokes de hatch e cortes não fecham contornos. Retornos estruturais curtos continuam sendo paredes; precisão de 0,001 cm resolve diferenças micrométricas de endpoints, sem fechar lacunas reais. Linha estrutural pendurada dentro de uma célula impede sua aceitação. Contornos de pilares fechados junto à borda recortam a laje.

Faixas com traços paralelos repetidos e delimitadores CAD reais sinalizam possível mudança de espessura ou nível. Seus h= pertencem à região interna; o h= exterior pertence à região principal. Hatch sozinho não confirma degrau, fundo contínuo ou diferença de nível. Sem prova de altitude/corte, a região mantém `status=unknown`. Espessuras diferentes sem separação geométrica continuam pendentes.

Sem nomes observados, usar `L1`, `L2`, `L3` etc., por filas da esquerda para a direita e de cima para baixo. Pedido posterior do dono em 08/10 removeu o sufixo do pavimento. Nome legível e identidade geométrica são campos diferentes. Não renomear rótulos existentes. Evidência inicial: `scripts/arete/relatorios/20261008_lajes_tipo_contexto/RELATORIO.md`; correção posterior: `scripts/arete/relatorios/20261008_lajes_cortes_callouts/RELATORIO.md`.

### Símbolos de corte e referências externas — correção 08/10/2026

Um retângulo perto de texto P12 não prova pilar. Reconhecer as peças de visão de corte pelo CAD original e pela composição do objeto antes de recortar a laje. As peças reconhecidas e as camadas semânticas de corte ficam fora do recorte por pilar; contornos reais de pilares permanecem bloqueios estruturais. Não usar o próprio resultado LAJ como prova independente de outra classe.

Uma espessura h= junto a chamada de bloco BL pode apontar por seta para outra região. A referência explícita do líder deve prevalecer sobre a posição do texto; chamada comprovada de bloco não vira espessura da laje que contém o texto. Polilinha simples, proximidade ou seta ambígua não autorizam realocação. Biblioteca e limites: [BIBLIOTECA-OBJETOS-CAD.md](../../CONHECIMENTO/BIBLIOTECA-OBJETOS-CAD.md).

## ESTILO-INTEGRADO-20261008 — harmonização entre classes

Síntese vigente, convenções recorrentes, contraprovas e pendências: [Estilos estruturais — interpretação integrada](../../CONHECIMENTO/ESTILOS-ESTRUTURAIS-INTERPRETACAO-INTEGRADA.md). Consultar a evidência local antes de aplicar a regra a outra obra; cooperação entre classes não constitui prova circular nem aprovação automática.

## Refinação de lajes nomeadas por cotas — evidência técnica de 09/10/2026

O ramo de lajes com rótulos L ainda usa a cascata de contornos; a rede de lajes
sem rótulos não certifica esse ramo. Uma medida numérica compatível não estabelece
parede física. A refinação por cotas deve usar candidatos estruturais preferidos
e suporte nas quatro bordas; o motor exige cobertura de pelo menos 95% de cada
borda candidata. Uma pequena linha de chamada no mesmo eixo não permite estendê-lo
para fechar a laje. Sem suporte, preservar o contorno anterior dessa etapa.

No 14_PAV, a etapa `_outline_from_local_dimension_texts` reduzia os contornos
completos de L405–L408 para retângulos internos definidos por linhas de cotagem.
A perda impedia o vínculo da região 96A/E11/E12 com L405 e o contato das lajes
inferiores com V420. O reparo recupera a região 96A com nível 855,22 m, h=12 cm
e fundo contínuo 855,10 m; esses valores pertencem ao exemplo, não à regra.
Coleta canônica isolada: 71→20 faixas abaixo de 60% de suporte. Controle 13_PAV:
31 lajes com saídas geométricas completas idênticas. Cinco falhas da suíte
preexistem no motor instalado; não interpretar essa medição como aprovação geral.
Relatório reproduzível e limites de publicação:
[Reparo dos contornos do 14_PAV](../../../scripts/arete/relatorios/20261009_reparo_contornos_14pav/RELATORIO.md).

## Preservar vértices, parcelas e papéis dos cortes — 10/10/2026

A limpeza de vértices colineares deve primeiro remover apenas pontos consecutivos
coincidentes na precisão de noding. Dois pontos separados por cerca de 0,0000005 cm
podiam fazer a limpeza simultânea apagar um canto legítimo. O contorno final de
uma laje nomeada deve conter seu próprio rótulo original. O reparo da L409 esquerda
recuperou o retângulo no replay; não autoriza seu nível nem confirma suas bordas.

Nomes repetidos não provam nem união nem separação física. Preservar a proveniência
dos rótulos durante a interpretação e decidir a identidade pelo contorno original.
A seleção de uma candidata apenas por nome pode descartar informação; separar
cegamente por rótulo também pode inventar parcelas. Níveis e contatos devem estar
vinculados à face física comprovada, nunca somente ao nome.

Correção do dono e inspeção original em 11/10/2026: os pequenos retângulos atribuídos
à L409 eram fechados artificialmente por cotas/cortes. Os rótulos D62 e D63 estão
na mesma face ampla de 51,2702 m², fechada exatamente por limites de vigas e pilares,
sem snapping ou buffer. A marca D83, 855,25 m, está dentro dessa face. Esta prova
invalida a hipótese anterior de duas lajes físicas; ainda exige correção geral do
tracer, nova rodada SA + QA e revisão dos contatos. Camadas numéricas 3/7 deste
exemplo não constituem regra universal: identificar papéis estruturais na fonte.
O nível 855,22 junto ao P14 fica fora dessa face, na região de rebaixo da L407;
não deve migrar para a L409 por proximidade. A marca própria D83 permanece
evidência de nível da L409. O contorno amplo não certifica por si só altitude
uniforme: rebaixos e espessuras internas exigem seus vínculos originais.
Prova reproduzível e PNG inspecionado:
`scripts/arete/relatorios/20261010_encontros_niveis_14pav/desenvolvimento_rapido/integracao_v408_identidade/l409_full_physical_face_receipt.json`.

## Contorno físico por paredes e apoios originais — 11/10/2026

O candidato geral do tracer constrói faces usando pares de paredes vinculados
a rótulos e seções originais de vigas, mais contornos fechados positivamente
associados a pilares. Estilo/camada apenas selecionam candidatos; não provam
papel estrutural. Cotas, molduras e cortes não podem fechar uma face por cor.
Não inventar segmentos, snapping ou buffer para fechar lacunas.

A medida de um pilar próximo pode estar mais perto do nome da viga do que a
seção dessa viga. A busca deve verificar os candidatos numéricos contra o par
de paredes no próprio rótulo, preservando o alcance espacial existente.
Uma dimensão próxima incompatível não deve impedir uma seção compatível mais
distante. Escrita horizontal/vertical ordena hipóteses; as paredes as comprovam.

O candidato final é aplicado após as heurísticas de normalização, para que
uma correção não altere indiretamente as lajes vizinhas durante a cascata.
Rótulos distintos dentro da mesma face indicam possível limite ausente e
impedem união automática; rótulos repetidos conservam a proveniência original.

Replay original sem teacher: 23 rótulos no14 e31 no13, todos cobertos. Foram
revistos 12 contornos alterados no14 e14 no13. A L416 preserva a parede da V421
e exclui a escada. Tempos locais do tracer:14 13,03→19,57 s;13 17,88→25,59 s.
Patches instalados com guarda de concorrência; ciclos frescos pré→SA→pós-QA
14/13 concluíram com isolamento e código estáveis. Os contornos atuais igualam
exatamente o replay original revisto em PNG. Onze diffs LAJ no14 e14 no13 foram
aprovados apenas quanto ao contorno em recibos de revisão exata por hash;
contatos e níveis regionais continuam independentes. O dono confirmou em11/10
a região h10 daL414/972: topo855,22, mesmo fundo855,12 da principalh13/topo855,25.
Revisão humana derivada por hashDXF/UID; não inferir essa regra só pela espessura.
Reconhecimento e prova local do contato físico P22 B passaram: um intervalo
de67cm, h10/topo855,22. A principal permaneceh13/topo855,25. Recibo
`integracao_v408_identidade/l414_p22_contact_proof.json`. O ciclo fresco14
`root-regional-v2-20261011` confirmou esse consumo com código/isolamento
aprovados: contato P22 B h10/855,22 por67cm; principalh13/855,25 preservada.
Isso aprova essa leitura específica, sem aprovar demais níveis ou a missão.

Três falhas universais de consumo foram corrigidas no lote de11/10:
os caminhos PIL devem receber `slab_regions_map`; snapshots devem conservar
`slab_steps`; o reconhecimento de polilinha original fechada deve emitir esse
fato em `closed_cad_boundary`, exigido pelo consumidor. Uma decisão humana
validada por revisão de fonte/UID pode apoiar o nível local sem ser apresentada
como cota CAD. Contradições, regiões sem nível e contatos mistos não recebem
o escalar principal. A tolerância normal à face não pode estender o contato
além do contorno original e criar uma falsa faixa de espessura principal.
Evidências: `integracao_v408_identidade/root_section_pair_review/receipt.json`
e respectivos PNGs; 51 testes de contornos/FV passaram.

Um perfil de corte com fundo contínuo, dois patamares e uma cota original do degrau
com eixo e dois ticks pode provar seu papel de anotação. O adapter
`dimensioned_section_profiles.py` registra contorno e handles independentes da
dimensão. A integração exige correspondência exata de contorno e handle antes de
retirar a hipótese de pilar. Ela não atribui dono, altitude ou espessura à planta.
No exemplo do 14º, quatro candidatos eram perfis 13/10 cotados com diferença 3 cm;
as anotações h=12/15 continuam independentes. Testes locais passaram; integração
e ciclo completo pós-deploy permanecem pendentes. Candidatos sem papel positivo
comprovado continuam em revisão.
