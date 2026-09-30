# Jev como segunda leitura opcional do SA/N1

**Decisão operacional — 2026-09-29.** Jev é uma ferramenta consultiva para dúvidas **específicas** de interpretação do DXF estrutural. O objetivo é somar SA, geometria CAD, contexto textual, visão do agente e QA. Jev não precisa superar cada uma dessas fontes isoladamente para ser útil: uma confirmação independente, uma abstenção correta ou uma pergunta que exponha evidência faltante já pode melhorar a triagem. Sua saída não é veredito de N1, selo Arete nem autorização para gravar o banco.

Este procedimento acompanha o **Eixo B (qualidade de interpretação N1)** do [loop canônico](../LOOPING-CANONICO.md). Não cria outro headless, QA, scorer ou pipeline. O SA continua produzindo N1; o QA canônico e o PNG da fonte sustentam o veredito. N2/N4 servem só para comparação e nunca são entrada para inferir N1. Para visão, o agente lê PNG; ficha persistida/app/portal usa SVG com pan/zoom por `viewBox` conforme [QA visual](../QA-VISAO-EVIDENCIA-CANONICA.md).

Para uso por agentes, a skill local [cad-jev-sa](../../.agents/skills/cad-jev-sa/SKILL.md) aplica este manual ao fluxo diário. Ela complementa a [skill oficial TypeSafe](https://github.com/typesafe-ai/skills/tree/main/skills/typesafe-ai), instalada no ambiente de desenvolvimento; a documentação viva da TypeSafe governa detalhes de API e primitivas.

## O que a investigação mostrou

O [masterplan e os pilotos](../MASTERPLAN-JEV-SA-EXPLORACAO.md) cobrem PIL, FV, LV e LAJ no 13_PAV e no 14_PAV. O [registro de capacidades e medição](JEV-CAPACIDADES-E-REGISTRO-DE-MEDICAO.md) lista o que se extrai, mede e avalia; o Stage 1 LV fonte-primeiro está em [`20260929_jev_catalog_v3_lv_source_encounter/RELATORIO.md`](../../scripts/arete/relatorios/20260929_jev_catalog_v3_lv_source_encounter/RELATORIO.md) (packed 0). A comparação N1 por extremo foi retirada no v5; o [v6 wall-level](../../scripts/arete/relatorios/20260930_jev_lv_wall_level_calibration_v6/RELATORIO.md) compara conjuntos na parede (dry-run, API 0). A comparação confiável do 14_PAV usa a fonte e o N1 da VPS congelados em 25/09, não a cópia local anterior. O [relatório por classe](../../scripts/arete/relatorios/20260924_jev_14pav/vps_parity/RELATORIO.md) contém denominadores e artefatos.

| Situação observada | Contribuição de Jev | Limite prático |
|---|---|---|
| PIL retangular simples: 31 dimensões corretas no N1 produtivo | Confirma 31/31 escolhas com JSON de candidatos | Nos dez controles sem o texto correto, escolheu opção errada 10/10; não preencher sozinho. |
| LAJ L410: dois níveis textuais dentro do mesmo polígono N1, em regiões gráficas distintas | Com `L410 h=14`, `h=11`, handles e região CAD, escolheu `DC7/855.25`; sem o marcador-alvo se absteve | A convenção de desnível ainda não foi comprovada pela fonte; até lá o veredito fica indeterminado. A regra CAD contextual também chega à mesma hipótese. |
| LV V419/V420: células laterais distantes do FV próprio nos contratos produtivos | Em duas consultas dirigidas classificou remoto; V411 correto foi controle, e sem coordenadas houve abstenção | O detector CAD já sinaliza a distância. O valor de Jev é segunda leitura do conflito, não medir coordenadas. |
| FV V414/VF402: contagem de interferência repetida por segmento sem prova local | Absteve-se em 8/8 perguntas de aprovação local | Não inferir zero aberturas; recuperar contorno/handle por segmento e revisar a origem da contagem. |

O piloto mediu utilidade como **complemento de QA**. Não demonstrou melhora geral de acurácia do motor ao chamar Jev em todo item, nem justifica trocar o SA, usar Rust para um DXF que abriu em ~0,2 s, ou treinar um modelo com respostas Jev como rótulos. O SDK usado é `jev-1.13.0`; a inferência sai pela API TypeSafe, enquanto recorte, comparação e relatório rodam localmente.

**Atualidade:** após esse snapshot foi criado `lateral_viga_cells.py`, e houve rodadas LV do 14_PAV em 26/09. Em 29/09, a leitura read-only das linhas V411/V419/V420 do **mesmo projeto produtivo congelado** ainda reproduziu os contratos antigos, mas isso não certifica o efeito do motor novo em uma recomputação completa. Antes de corrigir ou declarar o estado atual de outra execução, fixar projeto, manifesto, hash do DXF e versão do código e rodar o microciclo canônico.

**Pacotes LV (29/09, fábrica `0.4.0-g3-lv-polygon-context`):** candidatos próximos trazem geometria de fonte completa ou classificação `closed_polygon_edge` (`closed`, `vertex_count`, `selected_edge`, `bbox`, contorno). Arestas de polígono fechado (ex. retângulo de laje 9C0/C59 colinear com a parede 315 em V411) não entram como opções `LINE_*` equivalentes. Duplicatas de contorno entre layers colapsam com proveniência. A adjacência geométrica de parede aberta é uma pergunta distinta do ownership N1 da célula. L410 permanece `CONVENCAO_INDETERMINADA` no nível do item. G1 de V411 **não** tem consenso (revisões cegas do piloto G3/G4 discordam; a fonte DXF distingue parede de laje). O closeout de cobertura **não** adicionou G1. G4 A/B N1 significativo permanece `NOT_RUN`; G5 fechado. Jev continua consultivo.

## Quando acionar

Acione Jev depois de o QA ou um desenvolvedor formular **uma** dúvida por item, campo, lado, aresta ou segmento, com candidatos reais e evidência mínima da fonte:

1. Duas leituras plausíveis divergem, como nível de laje em regiões anotadas diferentes.
2. O SA e uma verificação CAD/QA discordam sobre atribuição de face, célula, apoio ou exceção.
3. Uma regra geométrica localizou o problema, mas uma segunda leitura semântica pode ajudar a decidir **qual evidência pedir ou revisar**.
4. Há dúvida se uma contagem ou anotação é global da viga ou local de um segmento.

Poupe consultas para casos simples já resolvidos por geometria exata e para pacotes sem candidato da fonte. O resultado `INSUFFICIENT` é útil quando revela contexto insuficiente. Não envie o DXF inteiro, ficha SVG com texto convertido em paths ou resultado N1 como se fosse fonte. Use texto/JSON do DXF original com handle, layer, coordenada, contorno, transformação e vizinhança necessária. SVG textual do **DXF fonte** é uma variante experimental; o agente inspeciona o PNG correspondente. Se o segmento excede o limite, divida **por segmento/célula/aresta com contexto de borda**, nunca em blocos cegos de bytes.

## Uso diário hoje: CLI opcional

O helper [jev_sa_second_read.py](../../scripts/arete/jev_sa_second_read.py) aceita um pacote JSON de evidência preparada. O [exemplo L410](../../scripts/arete/examples/jev_sa_second_read_l410.json) demonstra a pergunta fechada e o controle de retirada do marcador. `baseline_sa` fica fora do estado enviado ao Jev; a saída registra a escolha, confiança, hashes, tokens, latência e comportamento do controle. Limites atuais: 16 KB por estado, até quatro controles, opção `INSUFFICIENT` obrigatória. A consulta é **opt-in** com `--execute`; sem essa flag ocorre apenas validação local. Usa Python 3.12 da `.venv` e `TYPESAFE_API_KEY` do ambiente/`.env`, sem gravar a chave no relatório.

```powershell
..\.venv\Scripts\python.exe scripts/arete/jev_sa_second_read.py --request scripts/arete/examples/jev_sa_second_read_l410.json
..\.venv\Scripts\python.exe scripts/arete/jev_sa_second_read.py --request scripts/arete/examples/jev_sa_second_read_l410.json --execute --output scripts/arete/relatorios/MEU_RUN/jev_L410_nivel.json
```

Na prova executada em 29/09, o helper escolheu `DC7_855_25` no pacote completo e `INSUFFICIENT` ao retirar `DC7`; [saída registrada](../../scripts/arete/relatorios/20260929_jev_optional_review_l410.json). A confiança da escolha completa foi 0,87 nesta formulação, contra ~0,29 no probe enriquecido anterior: **confiança é sensível à pergunta e não é probabilidade calibrada de acerto físico**. É uma resposta coerente com a evidência, não aprovação do nível L410. Cada consulta cria arquivo novo; não sobrescreve rodada anterior.

Sequência de desenvolvimento recomendada:

1. Congelar `project_id`, pavimento, hash do DXF e snapshot N1. Rodar `qa_evidence_auditor.py review --project-id ... --classe ... --item ...` ou um probe de campo canônico; anotar a pergunta exata. Para evidência espacial, `qa_session_index.py` pode recuperar textos/entidades do DXF.
2. Construir JSON pequeno com candidatos e handles **sem resposta SA nem gabarito** no campo `evidence`. Colocar SA em `baseline_sa` para comparar **depois**. Criar pelo menos um controle de evidência retirada, com expectativa registrada fora do estado Jev.
3. Validar pacote localmente; executar Jev só se a consulta puder mudar a revisão. Conferir o resultado e o controle. Discordância, abstenção ou falha técnica viram achado, não correção automática.
4. Abrir o PNG full-layer da fonte e, se for uma convenção não decidível por medida, gerar a ficha visual de dúvida de `gerar_duvida_html.py` conforme `CLAUDE.md` regra 5d. Para fix de extração/associação, seguir `headless_sa_analise.py --secao --item --wait`, QA e regressão do loop canônico.

## Integração experimental no QA (29/09)

`qa_evidence_auditor.py review` agora aceita `--jev-request` (repetível),
`--jev-source-dxf` e `--jev-execute`. O pacote por campo conserva o contrato do
helper e acrescenta `use_context` (`SA_POST_EXTRACT`, `QA_B1`, `QA_B2` ou `QA_B3`),
`qa_snapshot_sha256` igual ao `manifesto.json` da revisão e, opcionalmente,
`presence_question_id`. O bridge confere projeto, classe, item, campo realmente
revisado, hash do snapshot e SHA-256 do DXF N1 original antes da chamada. Sem
`--jev-execute` valida e registra somente o pacote. Respostas ficam em
`jev_consultas.jsonl`, `jev_resumo.md` e `jev_XX_result.json`, no mesmo diretório da
rodada. Falha do SDK/API vira `TECHNICAL_ERROR` nesse sidecar; as decisões e
`scores_itens.jsonl` canônicos permanecem iguais.

```powershell
..\.venv\Scripts\python.exe scripts/arete/qa_evidence_auditor.py review `
  --project-id <ID> --classe LAJ --item L410 --rag-evidence off `
  --jev-request <pacote.json> --jev-source-dxf <DXF_Fase-1_original> `
  --jev-execute --out-dir <nova_pasta_de_rodada>
```

O mesmo helper `jev_sa_second_read.py` serve de ponto de consulta **após a
extração do SA**, antes da revisão, com `use_context=SA_POST_EXTRACT` e
`--source-dxf` para conferir o hash da planta; ele não é chamado dentro dos extratores. B1
fornece uma regra citada, B2 identifica conflito no snapshot e B3 fornece
candidatos CAD; cada consulta Jev recebe a fatia que responde à pergunta, com
evidência original separada do valor SA. `Choice` seleciona candidato,
`Noul` pode verificar uma proposição local, e `Score` pode graduar **uma dimensão
de evidência com níveis descritos**. Seu score não substitui a nota do auditor.
Perguntas independentes usam uma chamada por estado, e o controle de retirada
repete o pacote com a evidência-chave removida.

O ensaio integrado local de L410 está em
`scripts/arete/relatorios/20260929_jev_qa_bridge_l410_integrated_v2/`.
O Choice selecionou `193E/855.25`; sem esse marcador retornou
`INSUFFICIENT`. O Noul de presença deu 0,36 para “sim” no pacote completo:
**sinais contraditórios**, agora classificados `CONTRADICTORY_SIGNALS` pelo
resumo consultivo. Esse Noul e o Score ainda não foram calibrados por classe;
não geram aprovação. O N1 local do L410 tinha nível vazio neste snapshot,
enquanto o piloto VPS anterior tinha `855.22`; portanto são execuções distintas.
Nenhum veredito visual PNG foi feito nesta integração e nenhum nível foi
gravado.

## Onde ampliar, sem criar outro motor

O bridge atual usa pacotes preparados. O próximo passo é propor pacotes automaticamente
para conflitos elegíveis usando `qa_session_index.py`/parser DXF, sem enviar
DXF inteiro e sem confundir B1/B2 com prova da fonte. A interface futura pode
mostrar lado a lado SA, CAD, Jev e PNG, com `INSUFFICIENT`, falha de controle e
contradição destacados. A integração direta em `BeamTracer`,
`FundoVigaInterpreter`, `lateral_viga_cells.py`, `slab_tracer.py` ou
`pipeline_runner.py` exigirá ablação por classe e caminho de degradação quando a
API falhar; o SA deve continuar funcionando sem serviço externo.

Roteamento inicial sugerido:

| Classe | Gatilho no dossiê | Pergunta pequena | Gate de interpretação |
|---|---|---|---|
| PIL | face/viga ambígua após topologia ou dimensão especial | vínculo/face de candidatos identificados | polígono, contato e PNG da face; nunca aceitar texto incompatível com geometria |
| LV | célula fora da faixa da própria viga ou orientação/apoio conflitante | a célula pertence à ocorrência/face informada? | quatro contratos, geometria local, PNG; não confiar no flag isolado |
| FV | abertura/apoio/altura sem proveniência local por segmento | há evidência **neste segmento**? | contorno, handle, interseção e apoio local; contagem global não prova |
| LAJ | níveis/`h=` competidores ou aresta de apoio ambígua | qual marcador/apoio pertence à região? | contorno, região preenchida, corte quando necessário e PNG |

Se for desejado uso no portal, apresentar a segunda leitura como painel **opcional de revisão**, com fonte e abstenção explícitas; não preencher campo N1 automaticamente. Erro/timeout da API mantém o SA e a fila QA normais. Uma integração automática somente poderá sugerir ou priorizar revisão após regressão em outro pavimento permitido pelo escopo, nunca substituir o veredito visual ou decisão de convenção. A política de custo pode limitar chamadas por item e usar cache pela tupla hash da evidência + pergunta + modelo + parser; não reutilizar cache quando a fonte muda.

## Aprendizagem e critério de valor

O protocolo executável da próxima rodada — referência CAD/PNG adjudicada por agentes independentes, fábrica automática de pacotes CAD, perguntas e controles por classe e ensaio pareado do fluxo com/sem Jev — está em [PLANO-CALIBRACAO-JEV-SA-QA.md](PLANO-CALIBRACAO-JEV-SA-QA.md). Ele governa a promoção dos gatilhos; este manual continua a governar o uso opcional atual. Nenhuma decisão manual do usuário é requisito dessa avaliação.

Registrar em cada caso: hipótese SA, evidência CAD, resposta Jev/controle, PNG revisado, decisões agenticas independentes, tempo de análise e causa-raiz. A utilidade se mede por conflitos melhor priorizados, erros que deixaram de passar, perguntas que expuseram falta de evidência, abstenções apropriadas, tempo de análise e custo — **não** por “Jev vencer CAD”. Exemplos repetidos de confirmação podem justificar sua permanência como segunda leitura opcional; respostas redundantes em casos triviais justificam desligá-lo naquele gatilho. Treino local futuro usa apenas referências com prova CAD/PNG e consenso agentico, exclui casos indeterminados, faz split por desenho/obra e compara o sistema combinado com e sem a feature Jev. Saída Jev nunca é ground truth.

## Fronteiras documentais

- Este arquivo é o **manual de uso opcional**; [MASTERPLAN-JEV-SA-EXPLORACAO.md](../MASTERPLAN-JEV-SA-EXPLORACAO.md) guarda hipóteses, pilotos e próximos experimentos.
- [LOOPING-CANONICO.md](../LOOPING-CANONICO.md) registra o helper como companheiro do Eixo B, sem legitimá-lo como gate próprio.
- Os manuais [PIL](CLASSES/PIL.md), [LV](CLASSES/LV.md), [FV](CLASSES/FV.md) e [LAJ](CLASSES/LAJ.md) apontam os gatilhos por classe; a regra de interpretação continua no manual de cada classe.
- [MAPA-DO-CONHECIMENTO.md](../CONHECIMENTO/MAPA-DO-CONHECIMENTO.md) aponta este manual; a [decisão do dono](../CONHECIMENTO/DECISOES-DO-DONO.md) registra que a ferramenta soma forças e permanece opcional.


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
