# Pré-processamento por pavimento e torre — plano de execução

Data: 2026-09-22. Estado: PLANEJADO, NÃO IMPLEMENTADO.
Última revisão de escopo: resultados INTERNOS; ler a seção 0 antes do restante.

## 0. Escopo vigente — substitui propostas visuais e integração opcional abaixo

O dono esclareceu durante o planejamento: não haverá páginas de resultados
visíveis na VPS nesta entrega. O botão permanece na seção Pré-processamento do
pavimento; gera resultados internos por torre e consolidados para que as análises
SA posteriores possam utilizá-los. A interface mostra apenas acionamento e status.
As páginas e revisões descritas em 3.1–3.3 e tarefas P18–P22 são FUTURAS, não executar.

**A entrega não estará funcionalmente completa apenas por gravar JSONs.** É
obrigatório comprovar consumo real pelo SA posterior. Preservar seus algoritmos
e schema N1; usar contrato de entrada existente por adapter de orquestração.
Se não houver entrada suficiente, documentar precisamente a interface mínima
necessária e a incompatibilidade com a restrição de não mexer no núcleo. Não
alterar o motor silenciosamente nem declarar um consumidor inexistente pronto.

### 0.1 Pacotes internos e consolidação

- Pacote de cada torre: inventário, convenções aplicáveis, cortes, níveis,
  evidências, hipóteses, conflitos e revisões das fontes.
- Consolidado do pavimento: referências aos pacotes por torre, cobertura,
  dependências compartilhadas e conflitos; nomes iguais permanecem separados.
- Índice geral da obra: referências versionadas aos pacotes atuais dos pavimentos.
  Rodar um pavimento atualiza apenas sua referência; outros permanecem intactos.
  Pavimentos ainda não processados constam como pendentes. Não rodar toda a obra
  nem inferir correspondência entre torres físicas sem vínculo explícito.
- Atualizar índices atomicamente com controle de concorrência para não perder
  referências. Não somar níveis nem achatar P1 de duas torres em um só objeto.
- Informações gerais servem para resolver o contexto; cada análise SA recebe
  exclusivamente seu subconjunto e as convenções com abrangência comprovada.

### 0.2 Ordem corrigida e tarefas adicionais obrigatórias

Ordem: P00 → P01 → P26 (investigação antecipada do consumidor) → P02–P17 →
P23 → P24 → P25 (camada interna) → P27 → P28 (consumo). P18–P22 estão adiadas.

Correções que prevalecem sobre o texto original das tarefas:

- P14 também publica consolidado por pavimento e índice geral da obra.
- P16 expõe apenas acionamento/status; leitor de resultados fica interno.
- P17 mantém o botão/status; não cria visualização dos dados interpretados.
- P23 registra divergências em relatório interno, sem página nova.
- P24 depende de P14–P17/P23, não das páginas adiadas. Prova isolamento e usa
  evidência geométrica interna; teste visual do portal se limita ao botão/status.
- P26 deixa de ser estudo opcional futuro: roda logo após P01. Identificar a
  entrada realmente consumida, formato, ordem de execução, cache, origem e
  comportamento na ausência de contexto. Especificar mapeamento campo a campo
  em `docs/preprocessamento/CONTRATO-CONSUMO-SA.md` antes de implementar adapters.

**P27 — Adapter de consumo na orquestração**

- Depende: P14/P23/P24/P26 com interface existente comprovada.
- Criar `context_resolver.py`; integração mínima no runner do portal, sem
  modificar algoritmos SA. Fixar run/revisão/torre antes do subprocesso.
- Traduzir somente campos aceitos semanticamente pelo contrato; registrar
  `context_run_id` e hash no manifesto da análise. Nunca sobrescrever JSONs
  globais legados como atalho de integração.
- Cache deve considerar dependências externas consumidas. Se o cache atual não
  comportar isso sem mudança proibida, registrar impedimento, não reaproveitar
  resultado stale nem monkeypatchar serviço/processo global.
- Aceite: fixture com evidência externa inequívoca prova que o SA a leu e usou.
  Carregar JSON em variável sem consumidor não passa. Contexto ausente, antigo
  ou conflitante conserva o comportamento anterior e registra a razão.

**P28 — Validação A/B do consumo e ativação controlada**

- Depende: P27. Executar em cópias SA sem contexto versus SA com contexto.
- Desligado/ausente exige igualdade semântica. Contexto válido pode alterar
  somente campos previstos, com evidência por item; os demais campos, vínculos,
  geometrias, validações e resultados N3/N5 devem passar regressão.
- Testar duas torres com P1 homônimo, dois pavimentos, fonte alterada durante job,
  inferência conflitante e ausência de convenção. Registrar revisão efetivamente usada.
- Flags separadas para gerar contexto e consumi-lo. Desativar consumo restaura
  caminho anterior; não apaga pacotes. Publicação futura segue P25.
- Se P26 não encontrar interface suficiente, P27/P28 ficam bloqueadas por contrato
  ausente, com proposta mínima documentada; não mudar o núcleo contra o pedido.

Esta revisão substitui expressamente qualquer afirmação abaixo de que viewers
fazem parte da primeira entrega ou de que consumo real é apenas opcional.

Pedido inicial (histórico): contexto, três páginas e botão. Pedido vigente:
contexto interno por torre, consolidado por pavimento/obra e consumo pelo SA;
botão por pavimento. As páginas ficam futuras. Preservar SA funcional.

### 0.3 Alinhamento SA, pré-interpretação e aprendizagem futura

Esclarecimento do dono: SA + SVG da interpretação e N3 + ficha N3 são
granularidade do **resultado estrutural por item**, não produtos obrigatórios
da pré-interpretação. Prioridade atual: VPS funcional. RAG e machine learning
continuam em desenvolvimento e não são dependências desta entrega.

- Pré-interpretação: fatos candidatos, fontes, hipóteses e conflitos, com
  identidade própria e revisão por torre. Pode referenciar entidades candidatas,
  mas não cria um resultado SA nem exige N3 para publicar contexto.
- Resultado estrutural: por item, vincular SA/dados + SVG da interpretação;
  N3/desenho + ficha N3 referenciam a revisão exata do SA que os originou.
  Preservar a distinção N2 (motor reverso) versus ficha N3: não são sinônimos.
- Ligação entre camadas: registrar correspondência explícita entre candidato
  pré-interpretado e item SA; admitir não encontrado, ambíguo e múltiplos vínculos.
  Nunca unir entidades só pelo nome P1, V1 ou L1.
- Hierarquia de contexto: conhecimento global → obra → pavimento → torre →
  item/campo. É abrangência de aplicação, não autorização para misturar dados.
  Convenções compartilhadas têm vínculos explícitos; evidência local conflitante
  não é sobrescrita por regra global. Torre física entre andares exige identidade
  própria, não equivalência automática entre recortes chamados torre_1.

**Preparar agora, sem construir RAG/ML:** aproveitar manifests/sidecars da
orquestração para guardar IDs completos, classe/item quando identificável,
revisão da fonte, run_id, versão do produtor/contrato, referências e hashes dos
artefatos, dependências consumidas, origem e estado de validação. Não alterar
schema N1 nem duplicar blobs SVG/DXF em cada pacote de contexto. Artefato ausente
deve constar como ausente, nunca como gerado/validado. Referências obedecem às
mesmas permissões da obra, inclusive em futura recuperação RAG.

Histórico automático não equivale a exemplo aprovado. Preservar separadamente
resultado automático, hipótese, correção humana (antes/depois, campo, motivo,
autor e revisão quando disponíveis) e aprovação. Não inventar revisão humana
para dados legados. O contexto usado para inferir um resultado não pode usar esse
mesmo resultado como confirmação independente. Acerto local não promove regra
global automaticamente. Retenção histórica não autoriza ampliar a limpeza de
recortes ou reter dados excluídos contra a política da obra.

**Adições atômicas às tarefas existentes (sem expandir o caminho crítico):**

1. P01: documentar envelopes distintos de contexto e referência de resultado;
   fixture sem SA/N3 deve ser válida. Campos de proveniência desconhecidos são
   explícitos, não preenchidos artificialmente.
2. P02/P04: testar identidade e revisão estáveis, referências versionadas e
   isolamento de duas torres com item homônimo; não exigir banco vetorial.
3. P23: comparar apenas pares com identidade/revisão comprovadas; registrar
   ambiguidade, não criar vínculo por semelhança textual.
4. P26/P27: mapear o manifesto existente do SA e acrescentar vínculos externos
   apenas na orquestração. Registrar contexto efetivamente consumido; vínculo
   de N3/ficha só quando o artefato e sua origem forem comprováveis. Lacunas de
   rastreabilidade legada ficam documentadas, sem refatorar o SA neste escopo.
5. P24/P28: provar que pré-processar funciona sem RAG/ML, não produz SA/N3 por
   acidente, não mistura revisões e conserva comportamento sem contexto.

**Futuro, fora desta entrega:** auditar RAG/aprendizagem existentes antes de
escolher integração; indexação por escopo/revisão/permissão; curadoria de exemplos
validados; treino e avaliação separados por obra para evitar vazamento; promoção
de conhecimento somente após avaliação. Não adicionar embeddings, treinamento,
serviço novo ou páginas de aprendizagem agora. A preparação de contratos não
comprova RAG/ML funcional nem exige finalizar essa infraestrutura para publicar
a camada de pré-processamento. Permanecem os gates P24–P28 de consumo e regressão.

## 1. Decisão de arquitetura

Criar um pacote de contexto versionado por pavimento, com unidades isoladas
por torre e dependências explícitas das convenções e cortes. A camada lê os
desenhos e reaproveita algoritmos existentes; não grava nas tabelas estruturais
nem nos snapshots canônicos do SA. O pacote permite conferir pilares, cortes
e níveis antes de executar SA e, depois, comparar as duas interpretações.

Isso é útil para localizar omissões, vínculos ambíguos e níveis incompatíveis
antes da geração de desenhos. Não garante automaticamente uma interpretação
correta: a qualidade depende das fontes, da associação geométrica e da revisão.
Uma segunda execução do mesmo algoritmo sobre o mesmo texto não é evidência
independente nem aumenta a confiança.

Entregas:

1. **Contexto interno:** pré-processamento por torre e consolidados, antes do SA.
2. **Conferência interna:** comparação consultiva com SA, sem modificar seu resultado.
3. **Consumo comprovado:** adapter pela entrada existente após regressões;
   requisito final detalhado em P26–P28. Não autoriza reescrever algoritmos SA.

O botão não dispara SA, N3 ou N5. Detalhes gerais integra o inventário de fontes,
mas seu interpretador fica explicitamente como `not_supported` nesta versão.
Ler uma legenda delimitada dentro de Detalhes não significa interpretar o
documento inteiro de detalhes.

## 2. Evidência encontrada no código e na VPS

Levantamento direcionado aos componentes, consumidores e artefatos relacionados.
Os caminhos/linhas abaixo são do código inspecionado; localizar pelo símbolo
ao executar porque as linhas podem mudar.

| Fonte verificada | O que existe | Consequência para o plano |
|---|---|---|
| `src/ui/modules/diagnostic_hub.py:94`, `PreProcessAllWorker` | Batch de torres aprovadas; DXFLoader, SpatialIndex, BeamTracer, SlabTracer e helpers; agrega por pavimento e salva pilares/vigas/lajes no DB | Não chamar esse worker no portal: tem efeitos colaterais e mistura torres |
| Mesmo arquivo, `_process`, cerca de 508 | `pre_processamento_estado.json`, variantes context/engrev, resumo por pavimento | Importar como histórico somente; não reutilizar como verdade atual |
| `scripts/arete/headless_sa_analise.py`, `_run_legacy_analysis` | Monta `pavimento_pillar_report` e `pavimento_nivel_report`, inferências e cortes antes/durante análise | Sim, SA já possui etapas de pré-interpretação; não criar substituto do motor |
| Mesmo arquivo, `_fast_context_cache_path` | Cache por hash do DXF e arquivos de motor | Padrão útil; não assumir que inclui novas convenções externas ou revisões humanas |
| `main.py:5653`, `_parse_pillar_convention` | Detecta cabeçalho, texto e assinaturas CROSS/DIAG/EMPTY | Reaproveitamento exige isolamento e teste de associação símbolo↔rótulo |
| `main.py:15035`, `_build_complete_pillar_report` | Inventário P# por texto, geometria e vínculos | Fonte para candidatos, inclusive sem geometria resolvida |
| `main.py:15381`, `_build_nivel_report` | Níveis de lajes com origem/confiança; pilares derivados de lajes adjacentes | Não trata todos os itens como leitura direta; vigas precisam de contrato próprio |
| `src/core/slab_level_inference.py` | Seleção conservadora de nível, consenso e deltas de cortes | Reusar funções puras sem alterar regras do SA |
| `src/core/niveis_extractor.py` | Elevação típica e mapa de cotas por pavimento | Wrapper novo deve resolver fonte explicitamente; helper antigo varre arquivos e toma o primeiro |
| `src/ui/widgets/pre_validation_dialog.py:454` | NASCE, MORRE, CONTINUA, SEGUE, PASSA; rejeições e geometria errada | Preservar semântica e classes adicionais; não reduzir a três categorias |
| Mesmo arquivo, `_build_initial_term_map` | Fallback EMPTY→visual_only, comentário “nasce” | Não generalizar convenções; imagem atual mostra NASCE com X e MORRE vazio |
| Mesmo arquivo, linhas 3226 e 4764 | 95% fixo quando classificação não é indeterminada | Não apresentar como probabilidade medida |
| `portal/app/ficha_reader.py:453` | Convenções retornadas como entradas sintéticas; cortes vêm do estado SA | Falta um leitor real do pacote pré-SA |
| `docs/MASTERPLAN-OBRAS-DRIVE.md`, Fase 12 | Registra que os HTMLs esperados de convenções não tinham produtor | Implementar páginas reais, não apenas apontar para HTML inexistente |
| `portal/app/static/drill_grade.js`, hub | Pré-processamento já está entre Recortes e Detalhamento; convenções abrem recortes | Ponto exato do botão e da nova navegação |
| `portal/db/repository.py`, `enfileirar_job_unico_por_meta` | Deduplicação transacional de jobs | Reusar para o novo tipo de job |
| `portal/app/jobs.py`, `JobWorker` | Worker FIFO único e roteamento por metadados | Adicionar ramo isolado; não cair no fluxo que atualiza estado SA/obra |

### 2.1 Constatações de produção em leitura

- VPS `/opt/cad-analyzer`, obra UUID `781becd6-b113-4bec-8d5a-2027f10a65a8`:
  `DADOS-OBRAS/thierry/TMC-EST-PE-7000-14P-R03` tem `torre_1.dxf` e
  `detalhes.dxf` no diretório de recortes inspecionado.
- Não encontrados na raiz dessa obra os JSONs de pré-processamento/convenção
  pesquisados. Isso não equivale a afirmar que nunca houve uma análise histórica.
- `Obra_TREINO_1` possui `pre_processamento_estado.json` de 2026-06-07 e
  `convencao_pilares.json` de 2026-06-29. São históricos e pertencem a outra obra.
- JSON de convenções contém `term_map` e `term_examples`; não é inventário completo
  de todos os pilares de cada torre.
- Tabela `pre_processing` no DB SA de produção tinha **0 linhas**; sua existência
  no schema não comprova que o fluxo atual a utiliza.
- Foram comparados SHA-256 de nove arquivos locais/VPS. Oito coincidiram:
  main, niveis_extractor, diagnostic_hub, headless, ficha_reader, jobs,
  pipeline_runner e drill_grade. `pre_validation_dialog.py` divergiu; os trechos
  de categorias, carregamento de convenção e confiança fixa foram conferidos
  diretamente na VPS. A causa da diferença completa não foi investigada.
- Não sincronizar esse widget por cópia durante a implementação: há trabalho
  paralelo e a versão publicada deve ser preservada.
- Nenhum motor foi executado e nenhuma fonte ou base produtiva foi alterada
  nesta análise. Não se está certificando a precisão dos detectores.

## 3. Escopo de produto e navegação

No hub de cada pavimento:

```text
Recortes do Estrutural · 14 Pavimento
  Bruto / Torre 1 / Torre 2 / Detalhes / Convenções...
Pré-processamento · 14 Pavimento
  [Pré-processar pavimento]
  status, etapa atual e unidades concluídas
  Torre: [Todas | Torre 1 | Torre 2]
  Visão de Cortes
  Convenção de Pilares
  Convenção de Níveis
Detalhamento de Etapas · 14 Pavimento
  Torre 1 / Torre 2...
```

O botão principal cobre todas as torres elegíveis do pavimento e as fontes
que as atendem. Ações secundárias permitem reprocessar uma torre ou somente
unidades desatualizadas. Convenções compartilhadas são processadas uma vez por
revisão e têm resultados aplicados por vínculo explícito. “Todas” agrega tabelas;
o viewer mantém uma torre ativa, sem sobrepor sistemas de coordenadas diferentes.

Confirmar o escopo antes de enfileirar: pavimento, torres e fontes incluídas,
recortes pendentes e módulos sem suporte. Ausência de convenção não bloqueia
o SA atual; o pré-processamento mostra cobertura parcial e itens indeterminados.
O lote usa recortes validados para contexto confiável; uma opção explícita de
prévia em recortes pendentes gera apenas resultados provisórios.

### 3.1 FUTURO: página Convenção de Pilares

- Área direita: tabela acima do estrutural limpo da torre ativa.
- Colunas: pilar, classificação, origem/evidência, índice de confiança quando
  disponível, revisão humana e pendência geométrica.
- Subabas/filtros: Todos, Nascem, Seguem/Continuam, Morrem, Indeterminados,
  Rejeitados/Geometria pendente; filtros adicionais para termos reais da legenda.
- Manter `SEGUE`, `CONTINUA` e `PASSA` como termos originais; agrupar visualmente
  apenas com mapeamento explícito. Forma L/T/U é atributo distinto do ciclo de vida.
- Clique na linha realça/enquadra o pilar. Cores e pequenos rótulos devem acompanhar
  texto/ícone, sem depender somente da cor.
- A legenda original fica acessível como evidência em subaba/painel “Convenção
  de origem”. Sua geometria não deve ser desenhada como se fosse um pilar da torre.
- A mesma fonte aparece em Recortes; ali abre o documento bruto recortado,
  enquanto em Pré-processamento abre a interpretação no estrutural limpo.
- Não mostrar ações SA/N3/N5 nessa página.

### 3.2 FUTURO: página Visão de Cortes

- Sidebar contém somente lista de cortes, seleção da torre e retorno ao hub.
- À direita, estrutural limpo com destaque dos cortes e seleção sincronizada.
- Exibir identificação, viga/lajes vinculadas e pendências do corte selecionado.
- Cortes que ficam fora do DXF limpo não podem ganhar posição inventada:
  destacar a linha/marcador correspondente na planta quando houver vínculo;
  disponibilizar a vista do corte em painel secundário na sua fonte original.
- Geometria de seção e posição da chamada na planta são dois objetos diferentes.
- Sem botões de SA, N3, N5 ou painel de classe estrutural.

### 3.3 FUTURO: página Convenção de Níveis

- Tabela acima do viewer: item, classe, tipo de nível, valor/unidade/referência,
  origem, confiança, hipótese/inferência, conflito e validação humana.
- Filtros: Todos, Lajes, Vigas, Pilares; Diretos, Derivados, Supostos,
  Desconhecidos, Conflitantes, Revisados.
- Laje: cota da face definida pela fonte. Viga: níveis separados quando houver
  face superior/fundo/lado A/B; não condensar valores distintos em um só.
- Pilar: base e topo quando comprovados; nível de laje adjacente é evidência
  contextual e não prova automaticamente ambos os extremos do pilar.
- Tags pequenas por item, seleção realçada, prevenção de sobreposição e ocultação
  progressiva de tags distantes. Mostrar valor desconhecido como “?”; zero é válido.
- Uma hipótese deve ter indicação visual e motivo, mesmo quando acompanhada de %.
- SVG real, transformada CAD↔SVG registrada e zoom apenas por `viewBox`.

## 4. Modelo de dados proposto — independente de N1

Não modificar schema N1 nem as tabelas `pillars`, `beams`, `slabs`, `projects`
ou `pre_processing` do SA. Usar diretório novo de pacotes e metadados próprios
no portal. Os nomes abaixo são propostas, não arquivos já implementados.

```text
<obra_dir>/preprocessamento/v1/<pavimento-id>/<run-id>/
  manifest.json
  fontes.json
  convencoes/pilares.json
  convencoes/niveis.json
  torres/<recorte-id-opaco>/inventario.json
  torres/<recorte-id-opaco>/pilares.json
  torres/<recorte-id-opaco>/cortes.json
  torres/<recorte-id-opaco>/niveis.json
  torres/<recorte-id-opaco>/conflitos.json
  progresso.json
```

IDs de path são gerados/validados pelo servidor; nunca usar diretamente query
string como caminho. `recorte-id-opaco` representa obra+pavimento+bruto+item,
não apenas o nome `torre_1`. Uma revisão é hash de conteúdo, não nome de arquivo.

Envelope mínimo:

```json
{
  "schema_version": 1,
  "run_id": "uuid",
  "obra_id": "uuid",
  "pavimento_id": "id-estavel",
  "recorte_id": "id-opaco",
  "source_revision": "sha256",
  "dependency_revisions": [],
  "engine_versions": {},
  "status": "complete|partial|failed|stale",
  "created_at": "UTC ISO8601",
  "items": []
}
```

Cada item/fato inclui:

- `item_id` estável dentro do escopo/revisão e `display_name` (P1 não é chave global);
- `geometry_ref`, `coordinate_system`, `source_entity_handles` quando disponíveis;
- `field`, `value`, `unit`, `datum_id`, `raw_text`, `level_kind` para níveis;
- `classification_raw`, `classification_normalized`, `physical_type` para pilares;
- `evidence_ids`, `method`, `derived_from`, `independence_group`, `warnings`;
- `confidence.value` opcional, escala 0..1, `kind=heuristic|calibrated`, versão
  da regra e componentes; sem score disponível usar null, não 95% inventado;
- `review.status=unreviewed|confirmed|rejected`, autor/data/revisão da fonte;
- `alternatives` e `conflicts` separados do valor escolhido.

“Confirmado pelo usuário” não equivale a probabilidade estatística de 100%.
Percentual do job e índice de confiança são campos e componentes diferentes.
Não criar uma fórmula arbitrária de score nesta etapa: primeiro preservar os
scores existentes com sua origem; novos scores só com regra documentada e corpus
rotulado. O nome mostrado será “Confiança da leitura (índice)” quando heurístico.

### 4.1 Persistência e publicação

Índice novo `portal_preprocess_runs` proposto: run_id, obra_id, pavimento_id,
job_id, input_manifest_hash, schema_version, engine_version, status,
manifest_relative_path, started_at, finished_at. Tabela opcional de revisões
humanas separada e append-only, sem sobrescrever resultado automático.

O pacote é escrito em staging próprio, validado e publicado por rename atômico.
O índice só aponta para um pacote completo e legível. Recuperação trata os dois
casos de crash entre filesystem e DB. Último pacote bom continua consultável;
um pacote parcial tem cobertura explícita por torre/módulo e nunca é “tudo pronto”.

## 5. Pipeline proposto

1. Resolver obra/pavimento/recortes autorizados pelo cadastro atual do portal.
2. Congelar inventário, hashes, escopo e vínculos de fontes no início do job.
3. Ler convenções explicitamente relacionadas ao pavimento/torres.
4. Para cada torre, montar inventário e interpretar candidatos de pilares/cortes/níveis.
5. Cruzar evidências e registrar concordâncias/divergências com rastreabilidade.
6. Validar contrato, identidade, coordenadas, unidades e integridade.
7. Conferir hashes de entrada novamente e publicar pacote/índice.

Se uma fonte mudar durante a execução, não publicar seu resultado como atual.
Falha em uma torre deixa as outras consultáveis com status parcial; tentativa
posterior reusa unidades cujo conjunto de dependências permaneceu idêntico.

### 5.1 Reaproveitamento sem reescrever SA

- Reusar `DXFLoader`, extratores puros e funções conservadoras já existentes.
- Adapters novos recebem cópias dos dados: helpers podem mutar seus argumentos.
- Não instanciar `PreProcessAllWorker` nem chamar `_save_batch`.
- Para rotinas ligadas ao headless/MainWindow, primeira tarefa é provar um modo
  isolado de chamada em subprocesso com workspace temporário, fontes somente
  leitura, DB snapshot consistente e todos os outputs/cache redirecionados.
- `build_html=False` sozinho não é prova de ausência de efeitos colaterais.
- Não fazer monkeypatch global do serviço web, não importar dialog Qt para extrair
  constantes, não chamar `run_analysis`/N3/N5 como atalho.
- Se o reaproveitamento de um método exigir editar SA, marcar aquela capacidade
  como pendente; publicar apenas o que os adapters independentes comprovam.
  Não duplicar milhares de linhas do SA para contornar a restrição.
- Um adapter novo pode usar algoritmos já existentes para inventário independente;
  seus resultados são candidatos de contexto, não substitutos da interpretação N1.

### 5.2 Seleção das fontes

Prioridade de resolução: vínculo explícito por torre → por pavimento → convenção
compartilhada da mesma obra com abrangência confirmada. Nunca buscar de outra obra
por nome semelhante. Múltiplas fontes incompatíveis geram conflito, não “primeiro
arquivo encontrado”. Histórico `.historico_recortes` não participa da descoberta.

Para legenda dentro de `detalhes.dxf`: admitir apenas região explicitamente
identificada/delimitada para a convenção. Pode gerar candidato automático que
aparece para revisão. Sem delimitação inequívoca, pedir fonte dedicada pelo UI
existente de recortes. A interpretação genérica de notas/detalhes fica futura.

Não inferir continuidade vertical entre pavimentos só porque ambos têm `torre_1`;
é necessário vínculo físico explícito entre torres e referências de nível.

### 5.3 Cruzamentos úteis e limites

| Cruzamento | Utilidade | Limite |
|---|---|---|
| P# da planta × geometria × símbolo da legenda | Identificar pilar existente e sua classe | Nome sem geometria continua pendente; símbolo precisa ser local à legenda |
| Cota textual × polígono de laje | Associar nível ao item certo | Não confundir dimensão, altura e nível |
| Elevação típica × pavimento | Estabelecer referência/faixa de cotas | Registrar datum e unidade; não excluir automaticamente rebaixos |
| Corte × viga × lajes em cada lado | Explicar diferenças de nível e apoio | Vista separada precisa de chamada/vínculo, não proximidade de coordenadas |
| Pilar × lajes adjacentes | Identificar cotas de contato | Não prova base/topo do pilar |
| Pré-contexto × resultado SA | Mostrar omissões e divergências ao operador | Mesma fonte não é confirmação independente |

Inferência em cadeia deve carregar os ancestrais e evitar ciclos. Duas leituras
derivadas do mesmo texto não contam como duas fontes. Conflito entre evidências
diretas fica aberto mesmo se uma tiver score maior. Metros/centímetros só são
convertidos após identificação de unidade; registrar texto original e datum.

## 6. Invalidação sem apagar resultados estruturais

| Evento | Pré-processamento afetado | SA/N3/N5 |
|---|---|---|
| Refazer Torre 1 | Inventário e derivados dessa revisão da torre | Mantém política existente de confirmação/limpeza da própria torre; este projeto não a amplia |
| Refazer convenção de pilares | Classificações/contexto que dependem dela | Preservados; marcar contexto usado como desatualizado |
| Refazer convenção de níveis | Fatos de nível e dependentes daquela fonte | Preservados; revisão/reexecução é explícita |
| Refazer Detalhes usado como fonte de legenda | Apenas fatos que referenciam essa revisão | Preservados |
| Refazer Detalhes sem consumidor | Inventário da fonte apenas | Preservados |
| Adicionar Torre 2 | Nova unidade e cobertura do lote | Torre 1 preservada |
| Falha/cancelamento de pré-processamento | Run incompleta; último pacote bom acessível | Preservados |

Detectar obsolescência por hashes na leitura e antes do consumo, mesmo que o
frontend não tenha enviado evento. Nunca mudar validações humanas antigas para
“válidas na nova revisão” silenciosamente.

## 7. Job, API e progresso

Reusar a fila FIFO do portal; novo `meta.etapa=preprocessamento` com pavimento,
escopo, revisão das fontes e versão do interpretador. Não adicionar fila externa.
Deduplicação atômica por obra+escopo+manifesto+versão. O plano de torres/módulos é
congelado na entrada. Pedidos novos sobre escopos sobrepostos são serializados.

Novo ramo no worker deve retornar antes das transições genéricas de SA:
pré-processar não torna a obra “SA concluído”, não dispara N3 nem auto-publicação
de resultado estrutural. Reutilizar auth/acesso do portal em todas as rotas.

Rotas propostas:

- `POST /obras/{id}/preprocessamento/jobs`: pavimento, recorte_ids opcionais,
  modo `stale_only|full`, preview opcional; responde 202 job_id/run_id.
- `GET /obras/{id}/preprocessamento? pavimento=...`: status, cobertura, run atual.
- `GET /obras/{id}/preprocessamento/runs/{run}/torres/{recorte}/pilares|cortes|niveis`.
- `GET .../fontes/{source_id}`: metadados e preview autorizado, nunca path arbitrário.
- Revisão futura: `POST .../reviews` com expected_revision; 409 se fonte mudou.
- Estado do job reaproveita endpoint atual `/jobs`; não criar polling duplicado.

Progresso: publicar etapa, unidade ativa, concluídas/total e heartbeat. Se a
unidade não oferece progresso mensurável, usar indicador indeterminado nela.
Percentual geral representa unidades concluídas do plano, não tempo restante.
Reserva explícita de unidade final para validação/publicação; 100% só após commit.
Não avançar por relógio até 95%. Mostrar “2 de 5 unidades concluídas”.

## 8. Integração futura com SA — critérios de passagem

Primeira versão não muda decisões do SA. Produz contexto e um comparador
read-only capaz de registrar por item: concorda, diverge, ausente no contexto,
ausente no SA, identidade ambígua, revisão incompatível.

Um resultado SA só pode ser comparado se seu manifesto `source_dxf`/hash e
escopo baterem com a torre. Não ler `estado_<pav>.json` como se fosse de qualquer
torre do pavimento. O runner atual ainda tem caminhos que procuram `torre_1`,
e snapshots por pavimento: a granularidade ponta a ponta não está certificada
por esta inspeção. Se não houver fonte inequívoca, comparação indisponível.

Para alimentar o SA depois: inventariar entradas existentes, provar consumo
na ordem correta, preservar schema e validações, fixar a revisão do pacote na
rodada e incluir dependências em qualquer cache. Não escrever diretamente
`convencao_pilares.json` da raiz como “integração” sem provar seu consumidor;
o headless inicia `convention={}` e há carregamento posterior em dialog.

Se não houver extensão pública suficiente sem editar o núcleo SA, registrar
impedimento de contrato em P26 e a interface mínima proposta. A camada interna
pode ser desenvolvida, mas a funcionalidade de consumo não pode ser declarada
concluída. P27/P28 comprovam a integração quando houver entrada compatível.

## 9. Backlog atômico para executor de menor porte

Executar em ordem de dependência. Cada tarefa é uma rodada com testes e relatório.
Não marcar tarefa pronta só porque o arquivo existe. Arquivos novos abaixo são
propostos; não sobrescrever implementações existentes com o mesmo nome.

### P00 — Fixar baseline e inventário de efeitos colaterais

- Depende: nada. Ler as evidências da seção 2 e instruções do repo.
- Criar `docs/preprocessamento/BASELINE.md` com hashes local/VPS e mapa de chamadas.
- Enumerar gravações de cada rotina candidata, paths globais, caches e DBs.
- Saída: allowlist de funções reutilizáveis e lista proibida; nada executado em produção.
- Aceite: diferenças local/VPS registradas; nenhum pacote legado declarado atual.

### P01 — Criar contrato de pacote e fixtures mínimas

- Depende: P00. Novo `portal/app/preprocessamento/contracts.py` e testes isolados.
- Definir envelopes/fatos/status da seção 4; enums de origem, tipo de nível e revisão.
- Fixtures: duas torres com P1/L1 repetidos, nível zero, fonte sem unidade e conflito.
- Aceite: contrato rejeita valores não finitos, escopo ausente e geometria sem referencial;
  preserva desconhecido/null e zero como casos diferentes.

### P02 — Resolver identidade e inventário de recortes

- Depende: P01. Novo `sources.py`; ler `torre_crop.py` e cadastro documental.
- Resolver IDs completos por obra/pavimento/bruto/item e conteúdo hash.
- Excluir históricos; preservar documentos de origem; não inferir torre física entre andares.
- Aceite: recortes homônimos de duas obras/torres nunca colidem; path traversal rejeitado.

### P03 — Resolver vínculos de convenções

- Depende: P02. Estender `sources.py` com bindings explícitos e abrangência.
- Implementar precedência por torre/pavimento/obra da seção 5.2.
- Aceite: múltiplas fontes conflitantes são retornadas; nenhuma seleção por ordem de disco.

### P04 — Criar armazenamento atômico e leitor

- Depende: P01. Novo `store.py`, índice/migração portal após última migration vigente.
- Staging, validação, rename, índice transacional e recuperação de crash.
- Aceite: interrupção em cada fronteira mantém pacote anterior legível; teste usa tmp_path.

### P05 — Provar execução isolada dos adapters

- Depende: P00–P04. Novo runner/CLI `scripts/preprocessamento_pavimento.py`.
- Flags: obra-id, pavimento, recorte-id repetível, manifest, output-dir, preview.
- Para rotinas ligadas ao SA, executar prova em sandbox de cópias, DB snapshot consistente,
  runtime Python 3.12 e paths explicitamente configurados; auditar arquivos gravados.
- Aceite: nenhum write fora do output/cache isolado e nenhuma alteração N1/N3/N5.
- Se a prova falhar, restringir adapter a funções puras e registrar capacidade pendente.

### P06 — Extrair legenda de pilares

- Depende: P03/P05. Novo `adapters/pillar_convention.py`.
- Extrair texto/símbolo/posição/handles e candidatos de associação dentro da região da legenda.
- Guardar termo original e mapa físico; não aplicar EMPTY→NASCE universal.
- Aceite: fixtures com X=NASCE e vazio=MORRE, legenda invertida, símbolo ambíguo e sem título;
  casos não resolvidos permanecem indeterminados. Nenhuma escrita no JSON legado.

### P07 — Inventariar pilares por torre

- Depende: P05/P06. Novo `adapters/pillars.py`.
- Reusar detecção/inventário permitido; ligar P# à geometria e à legenda por evidência.
- Aceite: incluir P# sem geometria como pendente, preservar classes da seção 3.1 e
  não propagar rejeição/validação entre revisões ou torres.

### P08 — Extrair referência de níveis

- Depende: P03/P05. Novo `adapters/level_convention.py`.
- Chamar funções puras de `niveis_extractor` com textos da fonte escolhida.
- Registrar unidades, datum, rótulo do pavimento e campos de chegada/saída com semântica.
- Aceite: cota zero, negativa, vírgula decimal, metros vs cm e ambiguidade de piso;
  sem fallback silencioso de pé-direito ou escolha do primeiro arquivo.

### P09 — Inventariar lajes e vigas para contexto

- Depende: P05/P08. Novo `adapters/inventory.py`.
- Reusar loaders/tracers/helpers aceitos sobre cópias; produzir nomes/geometrias/evidências.
- Aceite: não salvar entidades em DB SA e não gerar N3; nome duplicado gera ambiguidade.

### P10 — Interpretar e vincular visão de cortes

- Depende: P07/P09. Novo `adapters/cuts.py`.
- Reusar lógica acessível comprovada; separar geometria de seção e chamada na planta.
- Registrar direção, viga, laje própria/vizinha, cotas e alternativas.
- Aceite: corte fora da torre mantém fonte original; múltiplos cortes/laje; sem vínculo
  não inventa associação. Se reutilização exigir alterar SA, marcar gap explícito.

### P11 — Consolidar níveis por item

- Depende: P07–P10. Novo `adapters/levels.py`.
- Preservar proveniência dos helpers e funções de `slab_level_inference`.
- Separar cotas de laje, faces de viga e base/topo de pilar; registrar desconhecidos.
- Aceite: inferência não vira leitura direta; nível adjacente não vira altura de pilar;
  nenhum preenchimento por mera proximidade atravessa torre ou referencial.

### P12 — Detectar conflitos e ciclos de evidência

- Depende: P11. Novo `crosscheck.py`.
- Detectar unidades/datum incompatíveis, níveis divergentes, fonte duplicada e ciclos.
- Aceite: duas derivações do mesmo texto não contam como consenso; conflito preserva alternativas.

### P13 — Registrar invalidação seletiva

- Depende: P04/P12. Novo `freshness.py`.
- Comparar revisão das fontes e dependências por fato/módulo/torre; não apagar SA.
- Aceite: refazer convenção compartilhada marca somente seus consumidores; refazer
  detalhes sem consumidor não invalida torres; pacote anterior fica consultável como antigo.

### P14 — Orquestrar lote por pavimento via CLI

- Depende: P06–P13. Novo `service.py`, completar CLI de P05.
- Congelar plano, executar unidades em sequência e publicar cobertura por unidade.
- Aceite: falha da Torre 2 não declara sucesso total nem perde Torre 1; fontes mudadas
  durante execução impedem publicação como atual; retry reutiliza unidades compatíveis.

### P15 — Integrar fila e progresso persistente

- Depende: P14. Novo `preprocess_runner.py`, ramo pequeno em `jobs.py` e metadados.
- Reusar `enfileirar_job_unico_por_meta`; etapas/contadores/heartbeat reais.
- Aceite: dois cliques criam um job; reinício recupera estado; cancelamento respeita checkpoints;
  não altera estado SA da obra nem dispara pós-processamentos existentes.

### P16 — Expor API autorizada

- Depende: P04/P15. Novo `routers/preprocessamento_routes.py`, registro no app.
- Implementar rotas da seção 7, paginação e limite de payload/escopo no servidor.
- Aceite: usuário de outra obra recebe 403/404; source_id não expõe path;
  run parcial/desatualizada aparece corretamente e não é servida como atual.

### P17 — Botão no hub e acompanhamento

- Depende: P16. `drill_grade.js`, módulo novo `preprocessamento.js`, CSS restrito.
- Inserir botão abaixo do título indicado; escopo todas as torres do pavimento;
  opção secundária por torre/desatualizadas; confirmação contextual única.
- Aceite visual: posição entre Recortes e Detalhamento, fila/progresso persistentes,
  sem percentual por tempo nem contagem de Detalhes como torre processada.

### P18 — Viewer compartilhado e transformação

ADIADA. Fora do escopo vigente de processamento interno.

- Depende: P16. Novo componente reaproveitando `dxf_preview` e pan/zoom canônico.
- Base sempre torre ativa; overlays em coordenadas verificadas; seleção linha↔geometria.
- Aceite: pan/zoom/reset mantêm alinhamento, troca de torre limpa overlay anterior,
  resposta assíncrona antiga não troca resultado da seleção nova.

### P19 — Página Convenção de Pilares

ADIADA. Fora do escopo vigente de processamento interno.

- Depende: P17/P18. Implementar seção 3.1 integralmente.
- Aceite: tabela acima, filtros completos, todos/nascem/seguem/morrem,
  termo original e evidência de legenda acessível; sem motores de classe.

### P20 — Página Visão de Cortes

ADIADA. Fora do escopo vigente de processamento interno.

- Depende: P17/P18. Implementar seção 3.2.
- Aceite: sidebar simples, cortes destacados, fonte externa disponível quando necessária,
  nenhuma função SA/N3/N5; seleção e retorno conservam pavimento/torre.

### P21 — Página Convenção de Níveis

ADIADA. Fora do escopo vigente de processamento interno.

- Depende: P17/P18. Implementar seção 3.3.
- Aceite: cada nível exibe tipo/unidade/origem, hipóteses distintas, índices identificados;
  tags legíveis sem colisão relevante e ligação correta com o item.

### P22 — Histórico de revisão contextual

ADIADA na interface. Preservar revisões existentes, sem criar novo fluxo visual.

- Depende: P19–P21. Revisões no pacote/índice novo, com optimistic concurrency.
- Permitir confirmar/rejeitar leitura contextual e registrar motivo, sem escrever em SA.
- Aceite: edição sobre fonte antiga retorna 409; resultado automático permanece auditável;
  UI explica que revisar contexto não recalcula SA existente.

### P23 — Comparador consultivo com SA

- Depende: P12/P16. Novo `sa_comparison.py`.
- Resolver resultado SA somente por fonte/revisão/torre inequívocas e comparar por item/campo.
- Aceite: snapshot de outro recorte nunca é comparado; conflitos e ausências são visíveis;
  comparar não altera arquivo/tabela/selo do SA. Sem fonte exata, declarar indisponível.

### P24 — Evidência de não regressão e isolamento

- Depende: P14–P17/P23. P18–P22 estão adiadas. Testes em fixtures/cópias isoladas.
- Tirar snapshot lógico de tabelas SA e hashes de artefatos antes/depois do pré-processamento.
- Comparar SA baseline com a camada desabilitada/habilitada em modo consultivo:
  inventário, campos, vínculos, geometrias, validações e artefatos devem ser idênticos.
- Aceite: zero escrita ou mudança semântica atribuível ao pré-processamento; nenhuma
  aprovação de precisão só por contagem. Validar geometria interna em PNG e
  fixtures de duas torres; no portal validar somente acionamento/status.

### P25 — Publicação controlada da camada independente

- Depende: P24. Preparar release revisável, migração aditiva e feature flag desligada.
- Ativar primeiro em uma cópia de obra/pavimento; medir duração, memória e filas.
- Aceite: versões Linux/Windows funcionam; rollback desativa flag sem apagar pacotes/dados;
  só declarar publicado após health check e verificação visual. A execução deste plano
  é futura; este documento não representa deploy realizado.

### P26 — Estudo de consumo assistido (não habilitar automaticamente)

OBRIGATÓRIA e antecipada após P01, conforme seção 0. Não depende de publicação.

- Depende: P00/P01; documento `CONTRATO-CONSUMO-SA.md` antes dos adapters.
- Mapear ponto existente de consumo, ordem de leitura, cache e preservação de validações.
- Propor somente fatos revisados/sem conflito/com fonte atual; desconhecidos não preenchem N1.
- Aceite: matriz item↔campo↔origem↔efeito, regressão por classe, plano de rollback;
  se exigir editar SA, registrar como nova decisão de escopo, não executar sob este plano.

## 10. Matriz mínima de aceitação

| Caso | Resultado obrigatório |
|---|---|
| Duas torres P1/L1 no mesmo pavimento | Identidades e resultados separados |
| Mesmos nomes em obras diferentes | Nenhum cruzamento |
| Convenção local contradiz padrão antigo | Preservar convenção real e sinalizar conflito |
| Sem recorte de convenção | Parcial/indeterminado, sem certeza artificial |
| Legenda dentro de Detalhes | Somente região delimitada, origem rastreável |
| Detalhes gerais sem motor | Não suportado, fora do total de unidades interpretáveis |
| Cota 0 / negativa / m / cm | Valores preservados e unidade explícita |
| Nível suposto e cadeia de inferências | Hipótese visível, dependências sem ciclos |
| Base/topo do pilar não comprovados | Desconhecidos; não inventar altura |
| Corte fora da planta limpa | Não posicionar sua seção arbitrariamente sobre a torre |
| Refazer fonte durante job | Resultado não publicado como atual |
| Refazer Detalhes/Convenções | SA/N3/N5 preservados |
| Fila, duplo clique, refresh, restart | Job único, progresso consistente e recuperável |
| Falha de uma torre | Parcial com cobertura explícita |
| Nova camada desligada | Comportamento SA anterior preservado |
| Nova camada consultiva ligada | Mesmo N1/N3/N5, mais contexto e divergências visíveis |

## 11. Prompt de execução para modelo menor

> Leia este plano, as instruções do workspace/repo e a última nota de execução.
> Siga a ordem vigente da seção 0; pule P18–P22 e inclua P27/P28. Execute apenas
> a próxima tarefa Pxx cujas dependências estão comprovadamente
> concluídas. Declare os arquivos que pretende alterar. Não use comandos git sem
> autorização explícita. Não edite main.py, headless_sa_analise.py, geradores,
> motores, diagnostic_hub.py ou pre_validation_dialog.py. Não rode processamento
> em dados de produção. Use Python 3.12 e fixtures/cópias isoladas. Preserve todas
> as alterações locais existentes. Faça a alteração mínima nos arquivos permitidos
> pela tarefa, valide seus critérios e grave relatório com evidência e próximos
> passos. Se o contrato existente não permitir reutilização sem mudar o SA, documente
> o impedimento e avance somente nas tarefas independentes; não crie fallback que
> finja interpretação ou confiança. Uma tarefa só fica pronta quando seus critérios
> de aceitação passam. Não execute P26 como modificação automática do motor.

Checkpoint por tarefa: ID, dependências, arquivos alterados, teste/comando e resultado,
evidência visual quando aplicável, limitações e próxima tarefa. Toda a lista P00–P26
está pendente de implementação no momento da criação deste documento.

## Atualização do dono — 2026-09-30: listagem da Convenção de Níveis

O apontamento do dono na página `documento=preproc:niveis` autoriza a apresentação
dos resultados em abas Pilares, Vigas e Lajes, com uma linha por nome/classe dentro
de cada torre. Base/topo, níveis distintos das partes, segmentos, cruzamentos e
evidências permanecem acessíveis em colunas e detalhes expansíveis. O agrupamento
é apenas visual: preserva as identidades de origem e não altera os fatos nem o SA.

### Atualização posterior do dono: coleta pré-SA efetiva (D-86/Pré-SA)

O dono autoriza o pré-processamento a executar a coleta necessária, inclusive SA
canônico completo ou parcial, para obter níveis antes da interpretação SA de produção.
Esta autorização atualiza as restrições históricas consultivas/P26 e o prompt da
seção 11 quanto às mudanças necessárias no consumidor SA e à execução solicitada.

Implementação: pacote v4 por torre/revisão; reaproveitamento de snapshot somente
quando escopo/hash conferem e as cotas contidas nas lajes não divergem. Caso contrário,
coleta canônica em processo e SQLite temporários, sem publicar SA/N3/N5. Preservar
referências FV e quatro famílias LV por segmento; FV referência superior e fundo
físico derivado apenas da altura do próprio segmento. Referências de pavimento para
pilares não se apresentam como medidas individuais; NASCE fica não aplicável ao
pavimento atual. Lajes com cotas distintas preservam todas as partes e exigem revisão.

Consumidor SA recebe somente cotas únicas observadas dentro da geometria atual,
fixadas por hash de fonte/contexto; protege validação humana, desativa cache e relata
chamadas reais por item/campo. Confiança de geometria não substitui confiança de nível;
score heurístico não significa probabilidade calibrada. Estimativas permanecem explícitas.

13_PAV publicado: 113 itens únicos, 102 com informação de nível e 11 não aplicáveis;
31 lajes com informação, 478 segmentos de 36 vigas, 17 cotas únicas efetivamente
consumidas em replay isolado do SA. L313/L318 = 852,19 m. Ainda existem 94 fatos
estimados e 12 lajes inferidas, além de duas lajes com múltiplas cotas. Sem selo QA.
Relatório: `scripts/arete/relatorios/20260930-niveis-sa-evidencias/RELATORIO.md`.

Mostrar nível obtido, confiança percentual quando fornecida pela origem, e estados
com cores e texto: observado, revisar/duvidoso, pendente e conflito. O inventário
atual não fornece percentual de confiança; nesse caso mostrar `Não calculada`,
sem converter proximidade de laje ou status em certeza numérica. Essa solicitação
atualiza a restrição histórica sobre telas de resultados da seção 0.

Implementação/evidência: `scripts/arete/relatorios/20260930-niveis-abas/RELATORIO.md`.
