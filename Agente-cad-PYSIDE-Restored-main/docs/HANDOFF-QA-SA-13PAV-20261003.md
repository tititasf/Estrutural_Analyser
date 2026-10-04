# Handoff — QA agêntico SA, autoajuste e portal — 03/10/2026

Este documento transmite o contexto deste chat para outro executor. Substitui uma retomada por tentativa e erro, mas não substitui as instruções do repositório nem uma consulta ao estado vivo. Os resultados abaixo são os últimos comprovados no trabalho; filas e dados podem mudar depois. Não declarar conclusão de todas as classes a partir de um exemplo aprovado.

## 1. Último pedido e ponto de parada

O dono pediu, antes de solicitar este handoff:

> “ok entao prossiga, se tiver duvidas durante o caminho que ajude a reforçar conhecimento pergunte ok? obviamente; depois de vc terminar todos itens do 13pav com o qa aprovando todos sa ou alguma camada agentica e terminar ai eu vou olhar os que tiveram camadas agenticas e ver se valido seus qa, caso encontre erros do qa agentivo ai te apoonto ok. além disso quero que implemente ua funcao que quando eu aprovar uma camada 1 agentiva, o sa antigo e essa nova camada se tornem um apontamento la na lista ed apontamentos porfa. assim podemos aproveitar oque o agente sa descobriu para poder ajustar posteriormente tais erros que ele encontrou e solucionou”

Em seguida mudou a tarefa para **produzir este resumo e entregar o trabalho a outro agente**. Portanto não iniciar novas rodadas ou adotar camadas nesta entrega de contexto.

**Pendência nova ainda NÃO implementada:** criar automaticamente um apontamento quando o humano aprovar L1, preservando o SA anterior, a nova interpretação, evidências e correções. Já localizamos o fluxo de aprovação e o sistema de apontamentos; ainda não alteramos esse fluxo.

**Objetivo maior ainda NÃO concluído:** inventariar e revisar todos os itens reais do 13_PAV, de todas as classes, reforçando os gates e corrigindo candidatos até obter aprovação sustentada por evidências ou esclarecer bloqueios reais com o dono. Não converter incerteza em PASS para satisfazer a meta.

## 2. Decisões explícitas do dono

- QA é da **interpretação SA**, não um selo genérico de N3/STOG. Pode e deve reinterpretar todo o item: geometria, campos, tags, relações e interpretação.
- Correção nasce como **nova camada agêntica**, destacada como resultado mais atual. **SA só é substituído quando um humano valida essa camada**. Executor não pode clicar a validação em produção em nome do dono.
- L1 avalia SA. L2 avalia L1 e exige viewer L1 realmente populado. L3 segue a mesma cadeia. Se versão de origem muda, descendentes históricos devem expirar.
- Quando aprova sem encontrar melhoria necessária, QA pode manter a origem **sem fabricar viewer novo**. Quando reprova/encontra detalhe a corrigir, deve materializar a interpretação e viewer corrigidos e auditar o resultado.
- Opinião agêntica e confiança precisam ter base real e rastreável. Percentual declarado pelo modelo **não equivale a acurácia medida**.
- Usar RAG da Base Global, documentação de interpretação específica da classe e agente/auditoria de evidências; conferir que foram realmente fornecidos e lidos.
- Gemini foi solicitado como **primeiro na fila das CLIs**. A prova final P1 rodou Gemini na fila oficial. Revalidar configuração viva antes de afirmar ordem e disponibilidade de Gemini/Codex/Claude.
- **Esclarecimento posterior do dono, 03/10/2026:** manter `docs/CONHECIMENTO/APRESENTACAO-NUMERICA.md`: medidas com no máximo uma casa decimal, vírgula e omitir ,0 (147,98 → 148; 147,88 → 147,9); níveis absolutos em metros com exatamente duas casas (852,19). Este esclarecimento substitui o pedido anterior deste chat de uma casa fixa inclusive 148,0. Preservar precisão interna e unidades; não mostrar ruído como 0.00000 cm.
- Testar cada classe; implementação completa antes de alegar validação final. Depois o dono inspecionará candidatos e apontará erros.
- Perguntas de interpretação são bem-vindas quando necessárias. Primeiro consultar docs/RAG/desenho; perguntar com evidência visual e dúvida concreta.

## 3. Ambiente e regras para não perder trabalho

- Workspace Windows: `D:\Agente-cad-PYSIDE`.
- Código: `D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main`.
- Python oficial 3.12: `D:\Agente-cad-PYSIDE\.venv\Scripts\python.exe`. Não usar Python 3.13/3.14.
- DB de produção local: `D:\Agente-cad-PYSIDE\project_data.vision`; DB dentro do repo é stale.
- Dados: `D:\Agente-cad-PYSIDE\DADOS-OBRAS`; Base Global: `D:\Agente-cad-PYSIDE\KB-GLOBAL`.
- Portal real: https://cad-analyzer.duckdns.org ; VPS: `root@62.238.111.147`, checkout `/opt/cad-analyzer`, serviço `cad-portal`, SQLite `portal_data.db`.
- Obra usada: `5aecf77e-e593-485f-8f8e-7244799fc3e8`, Obra_TREINO_1, 13_PAV.
- **Não usar comandos Git sem autorização explícita.** Há alterações não versionadas de outros agentes. Não resetar, limpar ou trocar checkout.
- Não sobrescrever/deletar DXF original, JSON Fase-4 ou históricos. Nunca matar processamento existente para conseguir publicar.
- Ler `CLAUDE.md` da raiz; no repo ler `CLAUDE.md`, `AGENTS.md`/`.agents/AGENTS.md` aplicável. Precedência: instrução atual do dono; regras do repo; regras do workspace.
- Sem autorização de delegação/subagentes nesta execução. Troca de executor pedida agora não autoriza disparar chats ou mensagens adicionais.
- Agente lê **PNG real**. Portal persiste/apresenta **SVG**, pan/zoom via **viewBox**, não CSS scale.
- Publicação: `docs/HANDOFF-DEVOPS-VPS-HETZNER.md`, especialmente §10.6. Fix só local não entrega ao dono. Usar patches ancorados, backups e restart apenas com fila ociosa.
- Headless canônico se necessário: `scripts/arete/headless_sa_analise.py --wait`; conferir `docs/LOOPING-CANONICO.md`. Não usar geradores legados por conveniência.
- Não aceitar contagem histórica “124 itens” como inventário vivo: houve mudanças/itens manuais. Precisamos enumeração real + set-diff por unidade.

Documentação de retomada: `docs/HANDOFF-ARETE-EXECUTOR.md`, `MASTERPLAN-ARETE-QUALITY-GATES.md`, `ARETE-LOOP-PROCEDIMENTO-GERAL.md`, `MASTERPLAN-PRODUCAO-SOBERANIA.md`, `MASTERPLAN-CONSOLIDACAO-ENTREGA.md`, `REGRA-ENTREGA-E2E-QUALIDADE-MAXIMA.md`, `QA-VISAO-EVIDENCIA-CANONICA.md`, `DECISOES-DO-DONO.md`.

## 4. Histórico de produto pedido neste chat

Estes requisitos são parte do contexto e precisam entrar no checklist de fechamento. Algumas telas posteriores já demonstravam mudanças implantadas; **não há comprovação de E2E de todos os requisitos nesta retomada**. Inspecionar código e portal antes de reimplementar ou afirmar que estão completos.

### Edição/criação estrutural

1. Renomear área para “Criar ou editar item no estrutural”.
2. Combo de classe + combo de itens existentes filtrados por classe, ao lado do nome. Para fundos/laterais, combo de segmento à direita.
3. “Redesenhar item”, “Excluir Item”; vigas também “Excluir Segmento”. Sincronizar painel esquerdo, fichas, seleção e viewer.
4. Reusar o fluxo existente de editar/refazer/excluir segmentos FV/LV, sem criar implementação divergente.
5. Cabeçalho FV e LV: excluir viga inteira e todos seus segmentos, mesma função da área criar/editar.
6. Pilar: edição manual geometria N1 no estrutural limpo; remover botão antigo “Invalidar e Regenerar Geometria”.
7. Pilar: interpretação SA granular somente do item, regenerando N1 com tag a partir da geometria manualmente selecionada.
8. Laje: “Editar” abre estrutural limpo para redesenhar item.
9. FV: tabela de segmentos dentro do card do viewer, abaixo das abas; mostrar selecionado ou todos. Mesmo padrão LV, sem card independente acima.

### Interface e apontamentos

10. Pavimento selecionado como tag abaixo do título da obra no painel esquerdo. Screenshots posteriores já mostram 13_PAV ali.
11. Padronizar botões marcados no tamanho/estilo pequeno de “Editar Campos da Interpretação SA”: solicitar interpretação, salvar campos SA, editar geometria N1.
12. “Editar geometria N1” abaixo do título “N1 próximo sem tag”, **somente nessa subaba**, não na barra de abas. Screenshot posterior já mostra essa posição.
13. Corrigir scroll do painel esquerdo voltando ao topo sozinho ao navegar/atualizar.
14. Apontamento: subir arquivos, incluindo DXF/fotos; paste de printscreen dentro do ponto, persistir no rascunho e apontamento salvo.
15. Remover “Adicionar nova página”: minimizar e navegar já cobre isso. Preservar captura de vários pontos/páginas pelo fluxo de navegação.

### Painel QA

16. Padronizar em todas as classes o painel “QA agentivo e Humano” do fundo de viga, juntando solicitar revisões e opiniões humanas por SA/C1/C2/C3/N3 conforme aplicável.
17. Laje precisava botões solicitar camadas; pilar precisava opiniões humanas como laje.
18. Abaixo da opinião humana, opinião agêntica com mesmo formato/tamanho, mostrando avaliação da versão anterior, confiança e fundamentação.
19. Cadeia/gates e regras de adoção descritas na seção 2. Robustização e testes reais viraram o foco principal do trabalho recente.

## 5. O que está implementado e comprovado no QA recente

Camada comum publicada: documentos por classe, RAG Base Global, auditoria de evidências, recibos de leitura, provas localizadas, ledger por unidade, hashes da origem, aplicação de patches de campos/geometria, materialização do candidato e auditoria posterior, adoção do SA somente por validação humana.

Problema real encontrado: um candidato de P1 recebeu PASS alegando VF301 seção 19/66 e distância 47,0 cm. As paredes originais comprovam **14/55 e 52,0 cm**. Esse falso PASS motivou gate independente, e permanece registrado como histórico rejeitado — não reescrever história para parecer sucesso.

Gate `qa_cad_gate.py`: lê DXF original read-only, valida hash, contorno fechado do pilar, associação única a paredes retas e texto da própria viga; confronta seção/distâncias. Rejeita PASS falso por unidade mesmo quando o resumo global é FAIL. Reavalia candidatos históricos para bloquear adoção inválida.

**Limitação crítica:** gate independente cobre pilares retangulares alinhados e contatos retos. Não certifica pilares especiais/curvas e **não foi generalizado geometricamente a LAJ/FV/LV**. Sem prova ou com ambiguidade, resultado deve ser inconclusivo. Ordem dos cantos e semânticas restantes dependem de auditoria visual/documentação.

Regressão recente: **119 testes passaram** na seleção conjunta de `qa_cad_gate`, `qa_review_contract`, `qa_versions`, `qa_post_diagnostics`, `qa_interpretation`, `pil_level_tag_units`, `decimal_display`. Não somar contagens de suítes históricas para inventar cobertura maior.

Publicação inicial: `/opt/cad-analyzer/backups/decimal-display-20261003-194618` (3 arquivos). Extensão final: `/opt/cad-analyzer/backups/decimal-display-20261003-201733` (2 arquivos). Esperamos terminar N3 ativo antes de reiniciar; portal ativo depois. Manifestos antigos não devem ser reaplicados às cegas.

## 6. Último resultado real por classe — NÃO é fechamento do pavimento

### PIL P1 / L1 — prova mais forte e candidata pronta para humano

- Rodada: `eb6f501b-27ae-46e2-b665-52665d0af7cb`.
- Job: `4f382c30-3be6-4ffd-9801-a4cab60a0de1`.
- Gemini, fila oficial serial, P1/L1. Auditou SA: 3 PASS / 5 FAIL, propôs 14 patches.
- Primeira auditoria posterior rejeitada por provas/resoluções insuficientes; após reparo: **8 PASS / 0 FAIL / 0 incertos**, 21 recibos de leitura.
- Confiança 98% é **declarada pelo agente**, não acurácia calibrada.
- Candidato: VF301 19/66 → 14/55; distância esquerda 47,0 → 52,0 cm; L301 BB → BD; topo 852,2 m e remoção de cm em nível absoluto.
- Prova original: contorno handle `245`, paredes `235/28E`, rótulo `101F`; SHA256 DXF `e5f6dabf3054027e7a37e7921db3dd62cf392e3e5bdac3075f8c376cc1280251`.
- Verificação VPS final: `promotion_ready=true`, `promotion_blockers=[]`, `post_status=completed`, `post_assessment=pass`, **`human_validated=false`**.
- SA original SVG e campos continuam com hashes iguais à origem congelada. Candidato visível no portal. Não adotamos.
- L2 histórica expirada porque L1 de origem mudou; comportamento esperado.

### LAJ L301 — ainda inconclusiva

- Rodada `8b5ee6cf-c935-448b-afe7-13f1e0c7b32d`: Gemini 7 PASS / 0 FAIL / 1 incerto, 24 recibos, ação `revisar_humano`.
- Incerteza: nível absoluto 852,12 m sem âncora direta independente no recorte de L301. Não inventar correção.
- Teste geométrico controlado anterior (01/10): erro de borda 46,4 → 0,0 cm; IoU 88,5% → 100,0%. Isso prova correção no caso controlado, **não conclusão da interpretação real nem benchmark humano**.
- Falta fechamento da correção real pelo pipeline publicado e auditoria posterior.

### FV V301 — nova rodada cancelada, pendente

- Rodada `560c2c8b-6802-4669-888e-76cc05b2c18b`; job `5a1a28e5-8fda-48bf-9764-49ded0527ee3`.
- Cancelada pelo operador em 03/10 14:32:36 UTC; round failed, item queued sem tentativa nessa rodada. Não chamar de aprovação.
- V5 anterior: 112 PASS / 16 incertos, portanto também sem fechamento.
- Pedido atual reautoriza continuar escopo, mas respeitar cancelamentos novos; usar fila oficial e estado fresco.

### LV Para V301 — amostra com PASS do agente

- Rodada `63d55b55-8b5e-47d3-9158-6f4395d0f058`; job prefixo `953e` (consultar ID completo vivo).
- Gemini: 32 unidades / 256 critérios PASS, 23 recibos, ação `manter`, sem viewer novo desnecessário.
- Não equivale a gate geométrico independente completo de toda classe.

### LV Passa V301 — amostra com PASS do agente

- Rodada `8f18edec-3f9b-49aa-a6e7-77b666755f40`; job prefixo `96d` (consultar ID completo vivo).
- Gemini: 32 unidades / 256 PASS, 21 recibos, ação `manter`.
- Aprendizados revisados: níveis lado A 852,19 m e lado B 852,12 m; L306 h10, L310 h12 após resposta V6 equivocada.
- Sem generalização para todas as vigas/unidades.

**Não existe conjunto humano independente suficiente para declarar uma taxa estatística de acurácia.** Medir exige referências humanas, critérios/unidades, amostragem/holdout e métricas separadas de confiança do modelo. Não afirmar que “98%” resolve isso.

## 7. Arquivos de código e fluxo de adoção localizado

Principais módulos no repo:

- `portal/app/qa_jobs.py`: execução/filas de QA.
- `portal/app/qa_versions.py`: rodadas, fontes congeladas, versões e candidatos.
- `portal/app/qa_review_contract.py`: contrato, ledger, evidências e bloqueios.
- `portal/app/qa_cad_gate.py`: prova geométrica independente PIL.
- `portal/app/qa_interpretation.py`: snapshot, patches, candidato, promoção/rollback.
- `portal/app/qa_measurement.py`, `qa_human_notes.py`.
- `portal/app/routers/qa_routes.py`: APIs QA, especialmente validação humana.
- `portal/db/repository.py`: repositório correto dos apontamentos (**não `repo.py`**).
- `portal/app/routers/comentarios_routes.py`: API `/apontamentos-ui`.
- `portal/app/static/human_qa.js`, `ui_feedback.js`: confirmar paths com `rg --files` antes de editar.

Endpoint de aprovação:

`POST /obras/{obra_id}/qa-camadas/{classe}/{item}/validar`

Valida contexto/acesso, layer L1/L2/L3; chama `qa_interpretation.promote(...)` com obra_dir, pavimento, classe, item, behavior, layer, round_id, candidate_sha256, membro_id e acknowledge_pending. ValueError/LookupError → HTTP409.

`promote` usa lock de mutação + lock do manifesto; verifica rodada atual não stale, readiness, token/hash, auditoria posterior ou reconhecimento humano explícito; compara fingerprint do SA efetivo com origem congelada; valida candidato e hash SVG. Grava item adotado e evento histórico em manifesto atomicamente. Evento contém UUID, ação promote, membro, data, identidade, versão anterior de override, rodada, hash e reconhecimento. Retorna effective/event_id.

**Importante:** `event.previous` guarda override anterior e pode ser nulo; isso **não é automaticamente o snapshot completo do SA anterior**. Novo apontamento precisa congelar antes/depois reais e evidências antes de perdê-los no estado efetivo. Ler artefatos de fonte em `qa_versions.prepare` e candidato antes de implementar.

Rollback restaura override anterior/remove override; mantém histórico. Apontamento de aprovação deve sobreviver como registro histórico, sem fingir que rollback nunca ocorreu.

Sistema existente:

- `/apontamentos-ui/sessoes` POST normaliza páginas/pontos; total ≤40 pontos; capturas+anexos ≤25 MB; chama `repository.inserir_sessao_apontamento_ui`.
- GET sessões/lista inclui anexos, capturas e dados do elemento; downloads com autenticação.
- Ponto tem texto, URL/título, seletor/metadados, captura PNG/JPG e anexos. Normalização valida URLs e limites.
- Migrations `012_ui_feedback.sql`, `013_ui_feedback_sessions.sql`, `018_ui_feedback_attachments.sql`.
- Testes `portal/tests/test_portal_ui_feedback.py`, `test_ui_feedback_clipboard.py`.

## 8. Nova função de apontamento — plano e riscos concretos

Ainda é desenho de implementação, não código entregue:

1. No evento de aprovação humana L1, criar sessão/apontamento associado à obra/item/pavimento e humano que aprovou.
2. Guardar **SA anterior efetivo** e **L1 aprovada** em snapshots imutáveis, com PNGs comparativos de fontes reais/SVGs congelados e delta dos campos/geometria/tags. Não depender só de URLs que futuramente mudam.
3. Incluir veredito inicial/posterior, achados resolvidos, evidências, identidade do agente, rodada, hashes e autoria/data humana, para alimentar investigação e melhoria posterior do SA.
4. Reusar lista e permissões atuais. Título/texto legíveis e números com uma casa decimal. Não expor segredos/logs indiscriminadamente.
5. **Idempotência e consistência:** evitar apontamento duplicado ao repetir request e adoção concluída sem apontamento silenciosamente perdido. Manifesto em arquivo + SQLite não têm transação comum. Examinar commits do repository e decidir mecanismo recuperável (por exemplo outbox no mesmo evento atômico + importação idempotente por event_id). Isto é sugestão, não decisão já implementada.
6. Falhas/retries devem ter teste; não criar “aprovado” antes da validação real nem perder origem em retries. Preservar histórico se houver rollback.
7. Testar com fixtures/obra isolada: **não aprovar P1 de produção como teste**. Somente o dono adota as candidatas reais.

## 9. Artefatos e ferramentas de retomada

Relatórios no repo:

- `scripts/arete/relatorios/qa-sa-cad-wall-gate-20261003/RELATORIO.md` — prova final mais forte, lida nesta entrega.
- `scripts/arete/relatorios/qa-sa-validacao-20261003-1535/RELATORIO.md`.
- `scripts/arete/relatorios/qa-sa-decimal-20261003/RELATORIO.md` — histórico, inclui tentativas anteriores; não confundir com final.

Pasta de trabalho: `D:\Agente-cad-PYSIDE\geometry-review` (confirmar presença antes de usar):

- `PIL-cad-gate-result.json`, `PIL-cad-gate-independent.json`, `PIL-cad-gate-candidate-fields.json`, `PIL-cad-gate-candidate-measurement.json`.
- `PIL-cad-gate-post-rejected.json`, `PIL-original-gate-result.json` — falhas históricas importantes.
- `PIL-cad-gate-candidate.png`, `PIL-cad-gate-portal.png` — imagens reais já examinadas.
- `LAJ-real-correction-result.json`, `LAJ-candidate-live-fields.json`, `LV-para-retry-result.json`, `FV-retry-result.json` — interpretar contexto antes de usar.
- `qa_pil_gate_verify.py`, `check_pil_current_hash.py`: verificações de gate/hash.
- `qa_gate_queue_read.py`, `qa_gate_active_meta.py`, `qa_gate_active_log_read.py`: estado vivo sem interromper.
- `qa_receipts_v7_live_status.py`; VPS `/tmp/qa_receipts_v7_live_status.py`, manifesto `/tmp/qa-receipts-v7-live-rounds-20261003.json`.
- `qa_pil_cad_gate_live.py`: helper de rodada real com manifesto `/tmp/qa-pil-cad-gate-live-20261003.json`. **Não rerodar às cegas**, pode disparar processamento; conferir resume/idempotência.
- `qa_v3_*`, `qa_live.py`, `qa_unit_live_rounds.py`, `qa_units_v2_live_rounds.py`, `qa_adoption_*`: helpers de iterações antigas, ler antes de executar. Especialmente adoption pode alterar dados.
- `deploy_decimal.py`, VPS `/tmp/deploy_decimal.py`: patch manifest de triples relative/before/after, ancoragem única, backup, fila vazia sob SQLite BEGIN IMMEDIATE, troca atômica. Não reaplicar manifest antigo `cad_gate_unit_patch.json`.

Testes de gate: `portal/tests/test_qa_cad_gate.py` (12 testes no conjunto recente). Use diretório temporário novo sob geometry-review para pytest; já houve DB temporário preso por outro processo. Não limpar diretórios antigos à força.

Browser no executor anterior: cua_repl `qaTab`, browser 2/tab 1; estado não é portável a outro agente. Usar inicialização documentada e ler documentação; não acessar APIs invisíveis da página. URL atual do dono termina `classe=pilares&item=P1&subvista=L1`. Preservar validação humana desmarcada.

## 10. Pendências e ordem sugerida para concluir com precisão

1. Revalidar estado vivo, filas, código publicado e inventário real completo 13_PAV: PIL normais/especiais, LAJ, FV por viga/segmento, LV Para e Passa por lado/segmento. Contar e manter ledger/set-diff, sem omissões/duplicidades.
2. Implementar e testar apontamento automático de aprovação L1; publicar com fila ociosa. Não exigir adoção real pelo executor para provar o fluxo.
3. Completar gates independentes por classe e limites explícitos: geometria/contorno, medidas/unidades, níveis, seções, contatos, segmentação, lados/cantos, vínculos e tags conforme documentação. Não copiar gate PIL como se bastasse a todas.
4. Resolver LAJ L301 inconclusiva e reexecutar FV V301 pendente. Fazer caso real de correção+post por classe, além de manter corretamente os casos sem correção.
5. Revisar todas as unidades reais, serialmente pela fila oficial e com retomada. Confirmar prompt efetivo, RAG/documentos/PNG realmente acessados, agente real e evidências por unidade. Testes locais não substituem execução viva.
6. Candidato corrigido só pronto se auditoria posterior + gates passam, source/hash não mudou, SVG/PNG corresponde aos campos e todos achados necessários foram resolvidos. Verificar bloqueios no endpoint, não apenas etiqueta UI.
7. Se interpretação não pode ser decidida com material atual, consultar dono com PNG e comparação concreta. Usar `scripts/arete/gerar_duvida_html.py` conforme regras, ler imagem antes de perguntar. Não repetir rodadas indefinidamente só para obter aprovação do modelo.
8. Preparar benchmark humano independente para acurácia medida/calibração. Até existir, apresentar métricas geométricas verificáveis, cobertura e confiança declarativa separadamente.
9. Auditar checklist UI da seção 4 para pendências esquecidas; não ampliar escopo para geração STOG/N3 sem necessidade do SA.
10. Entregar ao dono lista de todos SA mantidos/aprovados, candidatos mais atuais aguardando humano, itens inconclusivos/falhos e apontamentos gerados por aprovações humanas. Ele revisará camadas agênticas.

Definição de pronto: evidência por unidade, nenhum falso PASS, cobertura enumerada e conferida; origem preservada; cadeia de versões correta; correções materiais verificadas; humano controla adoção; histórico/apontamentos comparativos persistidos; código publicado; limitações e dúvidas expostas. **No ponto deste handoff ainda não chegamos a esse fechamento global.**

## 11. Consolidação posterior na Base Global

Ao revisar a harmonia do conhecimento neste mesmo chat, consolidamos regras reutilizáveis em `docs/QA-SA-AUTOAJUSTE-E-ADOCAO-HUMANA.md`, registramos decisões de adoção e apontamento em `docs/CONHECIMENTO/DECISOES-DO-DONO.md` e corrigimos o mapa que ainda atribuía autoridade a STATUS.md desconectado. O dono resolveu a divergência numérica mantendo a convenção atual da Base. Relatório documental: `scripts/arete/relatorios/20261003-harmonia-qa-sa-chat/RELATORIO.md`. Essas edições documentais não implementam as pendências de produto nem certificam todas as classes.
