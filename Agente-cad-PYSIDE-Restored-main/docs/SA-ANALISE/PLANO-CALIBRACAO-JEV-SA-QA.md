# Plano de calibração Jev × SA/QA — conflitos CAD por classe

> **v6 wall-level set (30/09, dry-run).** Comparação por parede (conjuntos), sem API. 876 paredes; comparáveis 9 (5 equal / 4 diverge); fila Jev 4; API 0/8. V420 `2F8` A = SET_EQUAL. Métricas N1 por extremo do v5 **não** reutilizadas. [`20260930_jev_lv_wall_level_calibration_v6/RELATORIO.md`](../../scripts/arete/relatorios/20260930_jev_lv_wall_level_calibration_v6/RELATORIO.md).

> **v5 blinded single-outcome (30/09).** n=4, API Jev 8/8. Jev=CAD 3/4; controlo INSUFFICIENT 4/4; PNG UNVERIFIED; benefício false. [`20260930_jev_lv_blinded_single_outcome_v5/RELATORIO.md`](../../scripts/arete/relatorios/20260930_jev_lv_blinded_single_outcome_v5/RELATORIO.md).

> **Catalog v3 LV source-first — packed 0 (Stage 1, 29/09).** Inventário DXF + sidecar N1; sem API Jev nesse stage. [`20260929_jev_catalog_v3_lv_source_encounter/RELATORIO.md`](../../scripts/arete/relatorios/20260929_jev_catalog_v3_lv_source_encounter/RELATORIO.md). Capacidades: [`JEV-CAPACIDADES-E-REGISTRO-DE-MEDICAO.md`](JEV-CAPACIDADES-E-REGISTRO-DE-MEDICAO.md).

> **Catalog v2 LV 14_PAV — packed 0 (final).** Os 13 pacotes `N1_DECISION_RELEVANT` da fábrica `0.5.0` estão **WITHDRAWN**. Fábrica vigente `0.5.1-lv-cell-encounter-failclosed`. Dry-run corrigido: scanned 30 / packed **0** / `N1_DECISION_RELEVANT` **0**. Relatório original (histórico): [`20260929_jev_calibracao_catalog_v2_lv_cell/RELATORIO.md`](../../scripts/arete/relatorios/20260929_jev_calibracao_catalog_v2_lv_cell/RELATORIO.md) + [`STATUS.json`](../../scripts/arete/relatorios/20260929_jev_calibracao_catalog_v2_lv_cell/STATUS.json). Auditoria: [`20260929_jev_catalog_v2_lv_independent_audit/RELATORIO.md`](../../scripts/arete/relatorios/20260929_jev_catalog_v2_lv_independent_audit/RELATORIO.md). G4 `NOT_RUN`. Não promover catálogo v1 nem v2 a “calibrado”.

**Estado:** plano de execução, 29/09/2026. Fase 1 (G0 + fábrica PIL/LAJ) em [JEV-CALIBRACAO-FASE1.md](JEV-CALIBRACAO-FASE1.md) e `scripts/arete/jev_calibration_cli.py`. **Escopo:** interpretação N1 do DXF estrutural, PIL, LV, FV e LAJ. Jev é segunda leitura opcional; SA, CAD determinístico, visão da planta e QA continuam operando normalmente. Este plano detalha a próxima etapa do [masterplan Jev](../MASTERPLAN-JEV-SA-EXPLORACAO.md) e do [manual operacional](JEV-SEGUNDA-LEITURA-OPCIONAL.md). Referência independente = fonte+PNG agentico, regra determinística ou abstenção. Não autoriza alterar schema N1, persistir proposta Jev no N1 ou usar N2/N4 como prova N1.

## Estado de execução — 2026-09-29 (cobertura closeout)

Fonte canônica dos números: [`scripts/arete/relatorios/20260929_jev_calibracao_cobertura_closeout/RELATORIO.md`](../../scripts/arete/relatorios/20260929_jev_calibracao_cobertura_closeout/RELATORIO.md). Fábrica `0.4.0-g3-lv-polygon-context`, catálogo `v1-2026-09-29-g3-lv-polygon-context`. Sem chamada Jev. 14_PAV = regressão congelada.

| Gate | Resultado nesta data |
|---|---|
| G0 | Manifestos e hashes gravados; `parity_claimed=false`. 14_PAV DXF/estado MATCH às cópias VPS 25/09; código SA local diverge dessas cópias. |
| G2 | 13_PAV 149 varridos / 11 packed / 47 unpackable / 91 discarded. 14_PAV 117 / 15 / 58 / 44. 26 JSON validam. PIL=0 FV=0 packed. |
| G3 | Pacotes no contrato `jev_sa_second_read_request/1` com `INSUFFICIENT` e controles de retirada. O closeout só validou JSON (sem API). **Fato histórico:** o piloto G3/G4 já executou Choice+controle em V420/V411 (e V411 revisado). |
| G1 | Parcial no piloto G3/G4: segundo revisor cego existe; **sem consenso** em V411 nem em ownership N1. L410/L309/L319 ficam `CONVENCAO_INDETERMINADA`. O closeout de cobertura **não** adicionou G1 (sem `g1-render`/PNG novo nessa pasta). |
| G4 | A/B N1 significativo **NOT_RUN**. Pacotes do closeout não sustentam A/B de campo N1 (LV = paralelo CAD; LAJ = convenção ou handle duplicado). O piloto G3/G4 tem só diagnóstico `g4_formal: NOT_RUN`. |
| G5 | Fechado (opt-in). Nenhum gatilho promovido. |

Matriz `usar / opcional / abster` no closeout. Experimento `catalog-v2-lv-cell-ownership-source`: artefatos originais em [`20260929_jev_calibracao_catalog_v2_lv_cell/RELATORIO.md`](../../scripts/arete/relatorios/20260929_jev_calibracao_catalog_v2_lv_cell/RELATORIO.md); auditoria independente retirou os 13 `N1_DECISION_RELEVANT` ([`20260929_jev_catalog_v2_lv_independent_audit/RELATORIO.md`](../../scripts/arete/relatorios/20260929_jev_catalog_v2_lv_independent_audit/RELATORIO.md)). Dry-run corrigido packed 0. V419 não forçado, G1 sem consenso, G4 `NOT_RUN`. Não promover catálogo v1 nem v2 a “calibrado”.

## Decisão que o experimento precisa produzir

Para **cada tipo de conflito**, responder: (1) qual evidência original é necessária; (2) qual pergunta fechada e qual controle fazem Jev ajudar ou abster-se; (3) se adicionar Jev ao fluxo SA + CAD + PNG + QA encontra erro real, reduz trabalho de revisão agentica ou melhora a priorização sem criar falso aceite; (4) em qual contexto vale pagar latência e tokens. O resultado será uma matriz de gatilhos `usar / manter opcional / desativar`, com evidência por caso. Não é uma competição Jev versus SA isolado. **A execução e a avaliação não dependem de decisões manuais do usuário.**

O primeiro produto é um **gerador determinístico de pacotes de dúvida**, não uma mudança no motor. Cada pacote refere uma unidade física (face, célula, segmento ou região), inclui candidatos CAD rastreáveis e sai separado do snapshot SA e do gabarito. O bridge atual (`jev_sa_second_read.py`, `jev_qa_bridge.py`, `qa_evidence_auditor.py review --jev-request`) continua a executar e registrar respostas consultivas. A automação de pacotes deve usar o índice de sessão `qa_session_index.py` e o DXF Fase-1 verificado, sem enviar o arquivo inteiro à API.

## Fontes, versões e separação de conjuntos

1. Criar um `run_manifest.json` imutável por rodada: projeto/obra/pavimento, SHA-256 do DXF Fase-1 e de eventual SVG **derivado dele**, snapshot SQLite N1 e hash do manifesto QA, hashes dos módulos SA/QA/parsers efetivamente executados, revisão do catálogo de perguntas, versão do modelo Jev, versão do extrator e do renderizador, data, unidade CAD e convenção geométrica. Guardar o comando e a configuração de cada braço. Erro de hash ou falta de arquivo cancela o caso antes da API. Não presumir que a cópia local seja igual à VPS.
2. **13_PAV:** desenvolvimento do gerador, taxonomia, prompts e controles. Casos já conhecidos (PIL, L410 etc.) são regressões e não contam como confirmação independente. **14_PAV:** repetir na fonte produtiva congelada, não na cópia local divergente. Como L410, V419/V420, V414/VF402 e outros itens já foram estudados, tratá-los como regressão conhecida. Separar previamente itens ainda não adjudicados para teste de generalização restrito; não chamá-los de holdout cego se alguém viu o resultado. Antes de alegar efeito robusto em produção, fazer avaliação prospectiva em outro desenho/obra permitido pelo escopo, com prompts e limiares congelados.
3. Congelar lista de casos e braços antes de abrir respostas Jev. Registrar inclusive conflitos que não geraram pacote, para medir o recall do roteador. Amostrar itens sem conflito como controles de especificidade e auditar uma amostra dos descartados. Particionar por **desenho/obra** quando houver dados suficientes; nunca colocar segmentos da mesma viga ou lajes vizinhas em treino e teste separados.
4. API externa só recebe fragmentos mínimos de geometria e texto necessários à pergunta; nenhum segredo, caminho local, rótulo de referência, score QA, valor SA ou `expected_choice` entra em `evidence`. O valor SA fica em `baseline_sa`, fora do estado enviado, para comparação posterior. Não usar uma ficha derivada do SA como fonte independente; SVG semântico só vale se reconstruído do mesmo DXF Fase-1 e com transformação/handles auditáveis. Para veredito visual, o agente examina PNG full-layer canônico; o SVG serve para navegação e conferência textual.

## Contrato do caso e gabarito

Persistir três registros separados, vinculados por `case_id` e hashes:

| Registro | Conteúdo mínimo | Quem pode vê-lo |
|---|---|---|
| `source_packet` | Identidade, classe, item, unidade física, bbox e transformação, handles/layers/posições/textos DXF, candidatos geométricos, recorte com margem e contexto de continuidade, pergunta, opções reais, `NONE` quando se comprova ausência e `INSUFFICIENT` quando a fonte é insuficiente, controles e hashes | Jev recebe somente a parte `evidence`/pergunta sem SA, QA ou gabarito |
| `baseline` | Valor/relacionamento SA, decisão e score QA, gatilho do roteador, regras CAD, custo do braço sem Jev | Benchmark e agente avaliador do braço A, nunca o Jev |
| `adjudication` | Resposta correta ou indeterminável, handles e recorte PNG que a sustentam, convenção aplicável, gravidade, decisões agenticas independentes, causa-raiz, agentes/data, status de consenso | Avaliador após congelar respostas; não entra no pacote |

Etiquetas `CORRETO`, `INCORRETO`, `INDETERMINADO_POR_FONTE` e `CONVENCAO_INDETERMINADA` são distintas. Um agente visual lê o PNG, cita handles e registra observações; outro agente, cego ao Jev e à primeira resposta, tenta refutar a conclusão com a fonte e as regras documentadas. O consenso só vira referência quando a prova é verificável. Discordância, fonte insuficiente ou convenção física não dedutível dos documentos → `INDETERMINADO`, fora da métrica de acerto e dentro da métrica de cobertura/abstenção. Adjudicação atual e futura: fonte+PNG agentico, regra determinística ou abstenção. O QA atual é uma triagem e não vira gabarito automaticamente. Uma referência geométrica determinística também não prova relações ou convenções que excedem sua regra.

## Fábrica automática de pacotes CAD

Entrada: manifesto congelado, snapshot QA/N1 e `SessionIndex` fresco (B1 regras de consulta, B2 N1, B3 DXF). Descoberta de conflitos fica em adaptadores por classe, cada um retornando `ConflictCandidate` com `case_id` estável, tipo, unidade física, gatilho, severidade, alternativas CAD e evidência faltante. A fábrica pode ler B2 para **detectar discordância**, mas candidatos e prova do pacote vêm de B3/parser DXF; B1 informa apenas a formulação de uma regra e nunca confirma um fato da mesma origem. Validar explicitamente classe + item, pois busca por nome isolado pode ser ambígua.

Pipeline proposto: `discover → normalize geometry → collect source handles → bound semantic context → build candidate set → formulate question/control → validate anti-leakage/freshness → emit JSON + audit trail`. Ordem e IDs dos candidatos devem ser estáveis; opção sem evidência não deve ser inventada. Registrar entidades incluídas, excluídas e a razão, transformações, margem do recorte e cobertura do trecho. Se houver interseção, apoio ou continuação fora do recorte, ampliar o contexto **por unidade física**; nunca cortar bytes arbitrariamente. Com o limite atual de 16 KB por estado, fracionar em face/célula/segmento/região com sobreposição e um índice de continuidade, preservando todos os candidatos relevantes. Se não couber ou não houver fonte decisiva, emitir `UNPACKABLE/NEEDS_SOURCE` auditável e não chamar Jev.

Cada pacote contém pelo menos um controle de **retirada da evidência decisiva**, cuja expectativa é abstenção ou mudança justificada; adicionar controles de vizinho parecido, ordem dos candidatos invertida e transformação quando relevantes. O controle é uma nova pergunta sobre estado alterado, não uma prova automática de acerto. Validador local bloqueia resposta SA/gabarito em qualquer chave ou texto do estado, handles inexistentes, geometria sem referencial, IDs duplicados, fonte não Fase-1, pacote acima do limite e `INSUFFICIENT` ausente. Cache por hash de DXF + pacote normalizado + pergunta + controle + versão do modelo; alterar qualquer componente invalida cache.

## Catálogo inicial de conflitos e perguntas

As perguntas abaixo são **hipóteses a calibrar**, não prompts finais. Resposta sempre referencia um candidato/handle ou `INSUFFICIENT`; `NONE` só quando a evidência completa permite afirmar ausência. `Choice` resolve alternativas; `Noul` testa uma proposição inequívoca; `Score` gradua uma única qualidade de prova com níveis ancorados. Não somar os três como votos, nem interpretar confiança Jev como probabilidade de verdade antes da calibração.

| Classe/unidade | Gatilho determinístico e candidatos do DXF | Pergunta focal e controle | Prova externa / erro crítico |
|---|---|---|---|
| **PIL / face ou contato** | Polígono e seção incompatíveis, texto da viga vizinha, mais de um contato/face, dimensão especial | “Qual candidato pertence a esta face/contorno?”; retirar marcador próprio ou substituir por texto de viga vizinha | Polígono, cotas, contatos e PNG; atribuir texto de outra entidade ou aprovar dimensão sem contorno é crítico |
| **LV / célula lateral × trecho** | Célula fora da faixa da própria viga, face/orientação/apoio conflitante, contrato A/B divergente | “Esta célula pertence a este trecho e lado?” ou Choice de ocorrência; retirar continuidade/limites | Quatro contratos LV/FV pertinentes, geometria de eixo/faixa, PNG; célula remota aceita como pronta é crítico |
| **FV / segmento** | Abertura, apoio, altura ou largura repetida sem origem local; soma global replicada por segmento | “Há prova local desta abertura/medida neste segmento?”; retirar handle local e deixar só soma global | Interseção e limites do segmento, handle de detalhe, PNG; contagem global tomada como local é crítico |
| **LAJ / região/aresta** | Níveis ou `h=` concorrentes, texto em área vizinha, desnível/apoio ambíguo | “Qual marcador pertence à região principal?”; retirar marcador próprio e manter concorrente | Contorno, preenchimento, marcador `h=`, corte/convenção documentada quando disponível, PNG; convenção não comprovada fica indeterminada |

Em PIL, começar por casos ambíguos: a regra CAD já empatou com Jev na dimensão simples e os dez controles negativos anteriores expuseram falso aceite. Em LAJ, L410 é teste de regressão da distinção região principal versus área cinza, porém a convenção do desnível continua pendente. Em LV, V419/V420 testam a célula remota e V411 controla caso coerente. Em FV, V414/VF402 testam proveniência por segmento. Esses nomes não entram nas instruções Jev como pistas de resposta.

Para cada classe, montar casos positivos, negativos verdadeiros, vizinhos difíceis, fonte insuficiente e conflito de convenção. Calibrar **uma pergunta por hipótese**; só manter `Noul` ou `Score` se acrescentarem diagnóstico em relação a Choice e ao CAD. O piloto L410 teve Choice e controle coerentes, mas `Noul` de presença contraditório (0,36): isso exige reescrever a proposição e comparar com rótulos independentes, não elevar score QA. Perguntas numericamente sensíveis usam valores já calculados pelo CAD; Jev não conta aberturas nem calcula distância ou interseção.

## Protocolo de calibração e aprendizagem

**Fase D — desenvolvimento (13_PAV).** Montar casos com adjudicação agentica fonte+PNG (ou regra determinística), medir cobertura da fábrica e erros de extração, comparar formatos DXF→JSON e SVG semântico→JSON **com os mesmos handles/candidatos**, testar formulações e controles. Guardar cada variante com ID e sem sobrescrever resultados. Escolher catálogo, roteador e limiares somente aqui. Estratificar por classe × tipo de conflito × gravidade × suficiência de evidência. Se a amostra for pequena, reportar contagens e intervalos, sem fingir precisão estatística. Casos sem consenso permanecem indeterminados.

**Fase F — congelamento.** Publicar catálogo v1, hash do código e do modelo, limite de chamadas, política de falha/abstenção, lista de casos/estratos e regra de promoção antes de rodar 14_PAV. Qualquer ajuste após ver um resultado cria v2 e invalida a avaliação cega daquele conjunto.

**Fase V — verificação.** Rodar regressões conhecidas do 14_PAV, depois itens previamente reservados e, quando disponível, outra planta independente. Medir separadamente: exatidão condicional das sugestões, falso aceite crítico, abstenção correta quando falta prova, cobertura do roteador (inclusive auditoria dos descartados), calibração de confiança por bins/Brier se houver volume, risco versus cobertura ao variar limiar, estabilidade à ordem e controles, taxa de erro técnico, tokens/latência/custo por conflito útil. Intervalos devem agrupar por desenho/viga/região para não contar segmentos correlatos como observações independentes.

**Aprendizagem local.** Guardar decisões agenticas independentes apoiadas em prova CAD/PNG, causas-raiz e features do conflito em corpus versionado; treinar primeiro um **roteador/calibrador** supervisionado local que prediga quando consultar Jev e quando enviar diretamente à revisão agentica, comparado à regra determinística. Excluir rótulos indeterminados do treino supervisionado e mantê-los no teste de abstenção. Não treinar com outputs Jev como rótulos. Separar treino/teste por desenho ou obra; pequena amostra favorece limiares explícitos e análise de erro em vez de modelo complexo. O modelo só pode alterar prioridade consultiva após teste prospectivo; jamais aprovar N1.

## Ensaio pareado do fluxo completo

Para cada caso elegível congelado, gerar os **mesmos** SA, CAD, PNG e QA. Braço A: fluxo atual sem Jev. Braço B: mesmos artefatos + sidecar Jev/controles. Medir o **resultado agentico final**, e não somente concordância entre máquinas. Agentes avaliadores recebem casos em ordem aleatória e braços cegos; agentes distintos avaliam A e B do mesmo caso. Um terceiro processo de referência, cego aos resultados dos braços e de Jev, usa CAD original, PNG e regras documentadas para adjudicar acerto ou indeterminação. Registrar momento em que o erro foi encontrado, mudança de decisão, razão citada, tempo de revisão agentica e custo API. Casos sem pacote ou com falha API continuam no denominador B, com fallback ao A.

Resultados primários por classe/tipo: erros reais adicionais detectados e **corrigidos com prova**, erros críticos perdidos ou introduzidos, e tempo de revisão agentica por decisão correta. Secundários: precisão dos alertas, completude de campos N1 elegíveis, cobertura, chamadas/custo e latência p50/p95. Reportar diferenças pareadas por caso e intervalos; não misturar melhorias de nova regra CAD com efeito Jev. Acrescentar braço diagnóstico `SA + CAD/QA + controle sem Jev` quando uma mudança de extrator ocorrer durante a rodada. Comparar opções Choice-only, Choice+controle, Choice+Noul e Choice+Score no desenvolvimento; no benchmark só entra a opção congelada.

## Gates, critérios de promoção e falha segura

| Gate | Entrega verificável | Condição para avançar |
|---|---|---|
| G0 — identidade | Manifesto de fonte/SA/QA e auditoria local versus VPS | Hashes, projeto e desenho coerentes; discrepância bloqueia comparação |
| G1 — referência | Corpus com handles, PNG e decisões agenticas independentes | Casos resolúveis adjudicados com prova; convenção indeterminada fica fora da métrica de acerto |
| G2 — pacotes | Fábrica por classe, rastreio de incluídos/excluídos e suíte de anti-vazamento | Nenhum pacote inválido chama API; casos não geráveis registrados; controles negativos exercitam abstenção |
| G3 — perguntas | Catálogo v1 e análise Choice/Noul/Score por estrato | Pergunta estável, com `INSUFFICIENT` correto; contradição e controle falho vão à revisão |
| G4 — valor incremental | A/B pareado e relatório por classe/tipo | Evidência de benefício prático no fluxo completo, sem novo falso aceite crítico; custo e tempo explicitados |
| G5 — adoção | QA em modo sombra/opt-in, documentação e rollback | SA funciona sem API; sidecar nunca muda score/decisão N1; monitorar drift e desligar gatilho que falha |

Para promover **um gatilho específico** ao uso consultivo padrão, exigir ao menos um ganho confirmado na referência independente ou redução consistente do tempo de revisão agentica, controles satisfatórios e nenhum falso aceite crítico observado; o tamanho amostral e a incerteza ficam explícitos. “Zero observado” em amostra pequena **não** prova segurança para automação. Qualquer uso que mude N1 automaticamente exige novo protocolo prospectivo; este plano só promove consultas e alertas consultivos. O modo opcional de desenvolvimento pode permanecer mesmo que o gate G4 não passe para um gatilho automático.

Quando Jev discorda do CAD/PNG, o controle falha, Choice e Noul se contradizem, ou a evidência está incompleta: `REVIEW`, nunca confirmação. Timeout/API indisponível: seguir A e registrar `TECHNICAL_ERROR`. Mudança do DXF, versão SA, catálogo, parser, modelo ou snapshot QA: invalidar cache e revalidar pacotes. O score QA canônico não incorpora confiança, Noul ou Score Jev nesta etapa.

## Backlog de implementação, na ordem

1. **Corpus/manifesto.** Esquema JSONL para `source_packet`, `baseline` e `adjudication`; captura de hashes e checklist de proveniência VPS/local; importação read-only dos relatórios conhecidos. Aceite: o mesmo caso é reproduzível e não há rótulo/SA no payload Jev.
2. **Fábrica PIL e LAJ.** Adaptadores de contorno/região e controles de fonte retirada; CLI `dry-run` com validação, contagem de elegíveis e motivos de descarte. Aceite: regressões negativas PIL abstêm ou são retidas pelo gate; L410 fica `CONVENCAO_INDETERMINADA` se a convenção não puder ser provada pelos documentos.
3. **Fábrica LV e FV.** Unidade de célula/trecho e segmento, expansão de continuidade, quatro contratos e proveniência local. Aceite: V419/V420, V411 e V414/VF402 geram dossiês rastreáveis; contagem global não prova segmento.
4. **Runner e catálogo.** Reusar helper/bridge existentes para Choice e controles; adicionar variantes Noul/Score somente com semântica separada, cache, limite de chamadas e relatório de contradições. Aceite: erro técnico e controle falho não alteram QA nem N1.
5. **Adjudicação e benchmark.** Fila de PNG/handles para julgamento agentico cego e independente, comparação pareada com/sem Jev e métricas por estrato. Aceite: cada conclusão aponta casos, fonte, custo e efeito incremental; itens descartados auditados.
6. **Modo sombra e documentação.** Atualizar manual Jev, manuais de classe e mapa do conhecimento **após** o catálogo calibrado; registrar perguntas aprovadas/desativadas e limites. Aceite: qualquer desenvolvedor reproduz um pacote e sabe quando não usar Jev.

Implementar em scripts/relatórios laterais de `scripts/arete/` e `docs/SA-ANALISE/`, sem tocar extratores SA ou UI compartilhada nesta fase. O QA canônico e o loop único de `docs/LOOPING-CANONICO.md` continuam a definir revisão e regressão. Antes de qualquer fix real de SA, aplicar o microciclo canônico e validação visual PNG exigida por `CLAUDE.md`.

## Saída esperada desta etapa

Entregar um corpus versionado de casos e decisões; gerador auditável que produza pacotes compactos ou explique por que não pôde produzi-los; catálogo de perguntas e controles por classe; matriz A/B com métricas, custo e limites de inferência; e decisão operacional por gatilho. A conclusão pode ser “usar Jev só em conflitos LAJ e LV” ou “nenhum gatilho automático por enquanto”; ambos são resultados úteis se o ensaio mostrar a razão com fonte independente.


## Rodada LV v7 — 30/09/2026

[Conclusão, evidência visual e recomendação consultiva](../../scripts/arete/relatorios/20260930_jev_lv_hybrid_adviser_v7/ANALISE.md).
Quatro chamadas reais em duas vigas do 14_PAV: concordância com a hipótese
geométrica em 2/2 e abstenção com retirada de evidência em 2/2; 4792 tokens
de entrada, mediana de latência por chamada 0,282 s. Não demonstra erro do SA
ou melhoria do fluxo. A agregação v6 por parede perde identidade do encontro;
as divergências são candidatas de investigação, nunca correções automáticas.
Manter segunda leitura opcional no QA/Eixo B e medir a ablação por encontro
antes de promover score ou integração no motor. Sem alteração N1, robôs ou VPS.


## Rodada LV v8 — correspondência por encontro

[Auditoria, revisão e próxima execução](../../scripts/arete/relatorios/20260930_jev_lv_encounter_v8/REVISAO.md). Adaptador e auditor
read-only implementados; 47 testes passaram. A amostra contém 96 encontros
fonte e um registro de ausência de encontro. Zero pacotes elegíveis: 80
encontros retidos por identidade de projeto, 17 registros por identidade
de fonte. Zero novas chamadas Jev. Estes são impedimentos de comparação,
não erros do SA. O gate recomputa o hash do inventário e verifica a fonte
do baseline local; project_id igual não basta. A etapa seguinte exige
fonte e execução SA verificadas juntas, com apoios/face curta/miolo por
encontro. Paridade VPS atual e ganho do fluxo híbrido continuam não medidos.


## Rodada v9 — identidade VPS e baseline isolado

[Registro e artefatos](../../scripts/arete/relatorios/jev_vps_identity_v9_20260930T140535Z/RELATORIO.md).
Fonte 14_PAV da VPS coincide com o freeze; codigo local difere. Snapshot remoto isolado, sem sobrescrita da aplicacao. 80 encontros receberam geometria fonte; 120 fragmentos conservam toda evidencia. Baseline canonical via Grok, estado em BASELINE-STATUS.json. Face curta/miolo/cessao ainda requerem evidencia por encontro. Zero novas chamadas Jev nesta preparacao; ganho hibrido nao demonstrado. VPS e banco de producao sem alteracoes.

Atualização v9 executada: baseline N1 fresco com código capturado da VPS (33 vigas/35 pilares/23 lajes, 52,431 s), sem cache e sem vazamento para código local. 12 chamadas Jev reais: contato/separação original 4/4; controles originais 4/4 abstenção; mesma geometria transladada 1/2 correto +2/2 controles abstiveram. Um erro TOUCH com confiança 0,76 em linha separada por 5 unidades. Não substituir validação geométrica determinística por confiança Jev. Registrar variantes equivalentes e divergências, sem votar até obter resposta desejada. 57 testes de regressão passaram. Ganho ponta a ponta ainda não demonstrado; baseline concluído tecnicamente não certifica interpretação.


## v9 — rastreabilidade e trava do conselheiro (30/09/2026)

Auditoria orquestrada com Grok, conferida e executada pelo Codex. A sessão de
proveniência do Grok atingiu o limite de turnos; seu código corrigido foi executado
depois pelo orquestrador. Artefatos em
`scripts/arete/relatorios/jev_vps_identity_v9_20260930T140535Z/`.

Nos alvos V409/V420 do 14_PAV, 14 segmentos de origem correspondem a 14 publicados
por chave, slot, índice, contrato e coordenadas, sem duplicatas ou contradições.
A auditoria explicita campos derivados da nomenclatura dos links; não certifica
identidade física a partir deles. Os 14 `lv_cell` disponíveis na origem são
omitidos pela publicação e não chegam ao adaptador experimental v8. Preservá-los
como N1_ORIGIN é útil para diagnosticar o SA; não são gabarito independente e não
devem entrar como verdade na pergunta ao Jev. As cenas medidas foram exportadas
usando o snapshot capturado da VPS, sem importação dos motores locais.

O arredondamento transversal do SA explica uma diferença de 0,01 nas duas vigas.
Há 50 alinhamentos transversais candidatos entre 80 eventos, mas nenhum vínculo
exato de extremo no diagnóstico. Alinhamento e grupos de paredes no mesmo eixo
não provam posse, apoio, face curta, miolo ou PARA/PASSA. O adaptador v8 permanece
inalterado: a auditoria não relaxou tolerâncias para forçar elegibilidade.

As 12 consultas reais de contato já realizadas foram reutilizadas offline.
`scripts/arete/jev_contact_advisor_v9.py` vincula resposta ao hash da pergunta,
identidade, modelo e hash da evidência, verifica retirada da geometria, confronta
distância calculada e exige consistência da representação traduzida. No replay
dos quatro casos originais: três sugestões retidas e uma ADVISORY_ONLY. Duas
foram retidas por ausência de consulta equivalente; a terceira por instabilidade
e contradição na equivalente. A sugestão restante nunca escreve N1, aprova QA ou
infere PARA/PASSA. Nenhuma chamada adicional; 65 testes passaram.

Esta trava é restrita ao experimento de contato por segmentos retos. Não é gate
de produção, validador de toda geometria CAD ou calibração estatística do Jev.
Uma resposta mudou de correta para errada apenas com translação, apesar de
aumentar sua confiança. Confiança isolada e controle de retirada aprovado não
bastam. Não repetir consultas até obter a resposta desejada.

Recomendação: matemática de contato fica no verificador determinístico; Jev fica
como opção para dúvidas semânticas com evidência rastreável, retirada de evidência
e verificações equivalentes. Próximo ensaio: montar automaticamente evidência
independente dos apoios/face curta/miolo nos encontros, preservando hipóteses do
SA fora do estado Jev; então comparar SA e SA+conselheiro nos mesmos casos
congelados. Medir correções, regressões, abstenções, custo e latência. Ainda não
há ganho de qualidade ponta a ponta demonstrado nem conclusão para todas as
classes. Sem alterações em motores, robôs, banco real ou VPS.
