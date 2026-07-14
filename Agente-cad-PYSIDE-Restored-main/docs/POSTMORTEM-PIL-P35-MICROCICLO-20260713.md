# Pós-mortem — PIL P35 / vínculo V308 em A-B — 2026-07-13

## Resultado honesto

O objetivo funcional não foi atingido. A ficha N1 final continuou sem viga nas
faces A e B do P35. Houve uma correção real da dimensão canônica da V308 para
`19/55`, mas ela não satisfaz o aceite do item.

Aceite correto do microciclo:

1. P35 face A contém V308 como viga que passa/para;
2. P35 face B contém V308 como viga que passa/para;
3. V308 conserva dimensão `19/55`;
4. a topologia da V308 conserva o vão que alcança o P35;
5. o contrato PARA/PASSA e o HTML refletem esses vínculos.

A probe executável desse aceite é
`scripts/arete/qa_requests/examples/pil_p35_v308_ab_acceptance.json`.

## Custo observado

Foram executados seis headless completos para o mesmo item/hipótese:

| Execução | Duração |
|---|---:|
| `headless` | 180,4 s |
| `headless_v308_fix` | 176,4 s |
| `headless_v308_reconcile` | 180,0 s |
| `headless_v308_label_fallback` | 189,2 s |
| `headless_v308_effective_route` | 181,7 s |
| `headless_v308_dependency_persist` | 181,0 s |
| **Total** | **1.088,7 s (18,1 min)** |

O custo não inclui leitura, edição, testes e conferência manual entre execuções.

## O que a evidência prova

Snapshot persistido após a última execução:

- P35: A e B sem slots de viga; D contém somente V328 `19/55`;
- V308: dimensão `19/55`, mas somente um `seg_bottom`;
- vão persistido da V308: x=`3888,3825..4141,3825`, terminando em P34;
- P35 começa em x=`4492,3825`; portanto não há contato geométrico.

Um contrato N1→LV gerado antes da regressão ainda registra dois vãos da V308:

- segmento 1: x=`3888,3825..4141,3825`;
- segmento 2: x=`4201,3825..4492,3825`, alcançando P35.

Esse contrato é evidência comparativa/histórica, não fonte autorizada para
repopular N1. A restauração deve vir do DXF e do extrator N1.

A probe barata, executada em 24 ms, retornou:

- `v308_dimension_is_19x55`: `PASS`;
- `face_a_has_beam`: `FAIL`;
- `face_b_has_beam`: `FAIL`;
- `v308_keeps_two_bottom_spans`: `FAIL`;
- `second_span_reaches_p35`: `PENDENTE` por ausência do segundo vão.

Resultado em
`scripts/arete/relatorios/qa_loop_runs/20260713_193413_c8b7fbb0/probes/p35_v308_ab_acceptance.json`.

## Por que demorou

### 1. O predicado de aceite ficou implícito

O ciclo mediu “a dimensão da V308 foi corrigida” em vez de medir “P35 A/B mudou”.
Uma prova intermediária foi tratada como aproximação do objetivo final.

### 2. O sintoma foi atacado antes da cadeia geométrica

A investigação priorizou nome/dimensão, embora a relação PIL↔viga dependa primeiro
da continuidade e do contato dos segmentos. Uma dimensão perfeita não cria um
vínculo quando o trecho geométrico foi perdido.

### 3. Headless foi usado como depurador

Cada hipótese pequena foi testada com uma execução de aproximadamente três minutos.
Deveriam ter sido usados, nesta ordem: snapshot/probe, teste puro do adaptador,
inspeção da coleção em memória e apenas então um headless de materialização.

### 4. Houve confusão entre caminhos de execução

Algumas correções atingiram funções auxiliares antes de alcançar a rota efetiva do
CLI. Faltou uma prova simples de que o hot path alterado foi realmente percorrido.

### 5. A persistência parcial ampliou o escopo silenciosamente

O microciclo PIL passou a persistir vigas reconciliadas como dependências. O conjunto
era inferido por metadado de fonte e podia incluir vigas semanticamente inalteradas.
Pior: uma dependência podia ser persistida mesmo quando o candidato tinha menos
segmentos que o snapshot anterior.

### 6. Não existia gate de não regressão da dependência

A V308 foi gravada com um único vão. A perda do segundo vão não bloqueou o commit.
Isso eliminou o contato com P35 e tornou impossível materializar A/B.

### 7. O ciclo repetiu sem mudança de estratégia

Após cada headless, não houve comparação imediata contra um aceite executável. A
ausência de A/B deveria ter interrompido a repetição e reaberto a causa geométrica.

### 8. O estado humano ficou órfão

O executor terminou em `WAITING_HUMAN_RULE`, embora o dono já tivesse informado
V308, sua direção e o comportamento esperado. A pergunta pedia ao humano parte do
diagnóstico que as fontes locais e a topologia deveriam resolver.

## Correções de processo implementadas

1. Probe de aceite localizada P35/V308, sem headless.
2. Persistência parcial limita dependências a mudanças semânticas reais; metadado de
   proveniência isolado não autoriza escrita.
3. Uma dependência é recusada quando o candidato perde quantidade de segmentos ou
   cobertura axial em relação ao snapshot anterior.
4. Testes automatizados cobrem tanto o filtro semântico quanto a perda do segundo vão.
5. A skill QA passa a exigir predicado de aceite, prova barata e limite de repetição.
6. O perfil PIL deixou de testar apenas `seg_bottom.0`: contato agora é avaliado
   contra qualquer segmento, sem fechar artificialmente o vazio entre vãos.

Essas proteções evitam nova perda; elas não reconstroem o segundo vão já ausente.

## Rota eficiente obrigatória daqui em diante

1. Escrever o aceite por campo/vínculo antes de editar código.
2. Rodar a probe persistida; guardar o antes.
3. Localizar o primeiro elo quebrado na cadeia fonte→segmento→face→contrato→HTML.
4. Reproduzir a causa em teste puro ou overlay sem DB.
5. Corrigir fórmula geral e deixar o teste puro verde.
6. Executar no máximo um headless para materializar aquela hipótese.
7. Rodar imediatamente a mesma probe de aceite.
8. Se o aceite não mudou, proibir novo headless da mesma hipótese; registrar a
   divergência e mudar a investigação para o elo anterior.

Uma segunda execução cara exige simultaneamente: nova causa comprovada, teste/probe
barato verde e explicação do que será diferente no próximo materializado.

## Próxima causa técnica

Rastrear no DXF por que o agrupamento da V308 conserva apenas o vão V323→P34 e
descarta o vão P34→P35. A correção deve reconstruir todos os runs colineares da mesma
identidade de viga sem unir vigas distintas. Só depois disso cabe um novo headless e
a probe deve provar A/B, dois vãos e contato com P35.

Classificação atual: `extractor_bug` na continuidade/agrupamento da viga, agravado
por `orchestration_bug` na persistência parcial. Nenhum veredito visual ou Arete foi
registrado para P35.
