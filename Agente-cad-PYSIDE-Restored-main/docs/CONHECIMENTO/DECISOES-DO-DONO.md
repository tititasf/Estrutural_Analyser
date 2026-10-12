# Registro de decisões do dono

### N5-REVISAO-HUMANA-OPCIONAL-20261008

O dono desativou a exigência de validação humana para gerar N5. A geração geral, por classe e a sequência SA → N3 → N5 devem funcionar sem aceite humano prévio. Revisões existentes permanecem auditáveis e opcionais; nenhuma aprovação é fabricada. Completude dos N3, integridade automática, acesso à obra e recusa de configurações não implementadas permanecem obrigatórios. Esta decisão substitui o gate humano de geração previsto em DP-13; não certifica os motores. Evidência: `scripts/arete/relatorios/20261008_n3_n5_performance/RELATORIO.md`.

### LV-FORMASCIA-APROVADO-20261007

O dono aprovou integralmente as laterais Formascia, Para e Passa, sarrafeadas e gradeadas, e autorizou integrar/publicar N3 e N5 e gerar o 13_PAV da Obra_TREINO_1 no portal. Gradeadas têm painéis sem grades e grades soltas em famílias independentes, ambas com visão corte. Cortes sem preenchimento cinza dos painéis; sarrafeados sem parafuso do fundo e sem horizontal acima dos retângulos; gradeados sem cota inferior do fundo e com ferragens únicas. Grades soltas preservam numeração, quantidade, limites verdes, passo 30, cotas 2,2/vertical/altura total. Regras completas em [PADRAO-FORMASCIA-LATERAIS-APROVADO.md](../PADRAO-FORMASCIA-LATERAIS-APROVADO.md). Estado: design aprovado; validação publicada registrada separadamente no relatório da integração, sem aprovação implícita de outros modos/classes.

### APONTAMENTO-CONTEXTO-ESTRUTURAL-20261007

O apontamento automático de ajuste manual deve preservar o estrutural limpo e os elementos ao redor no antes/depois, na mesma região e escala. Na exclusão, o depois mantém o CAD original e marca a área do destaque removido; guardar apenas o desenho isolado não permite depurar relações com vigas, pilares e lajes. Congelar PNG no momento do evento, detalhe do item, comentário opcional, entidades antes/depois, vizinhos, enquadramento DXF, data UTC e hash da fonte no JSON. A fila de repetição reutiliza essa captura, sem reconstruir um passado com dados posteriores. Apontamentos antigos sem contexto permanecem históricos, sem fabricar retroativamente uma captura. Evidência: scripts/arete/relatorios/20261007_audit_structural_context/RELATORIO.md.

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| APONTAMENTO-CONTEXTO-ESTRUTURAL-20261007 | 2026-10-07 | Antes/depois automático inclui estrutural e entorno na mesma região/escala; exclusão mantém contexto e marca a área removida. Congelar PNG, detalhe, comentário, entidades e vizinhos JSON, bbox, UTC e SHA256. Retry reutiliza captura; antigos sem entorno ficam históricos. | Permitir depuração real das relações entre elementos. | Pedido do dono e CONSOLIDACAO-CORTES-INVERTIDAS-20261005.md. | Publicado; testes HTTP isolados e PNG real. |

### PREPROCESSAMENTO-CORTES-REVISAO-COMENTARIO-20261007

Pedido do dono: listar as Visões de Cortes Interpretados no Pré-processamento, correspondendo aos destaques do estrutural limpo, para revisar níveis antes do SA. Pré-processar pavimento coleta esses cortes no pacote `beam_sections`; coleta não valida automaticamente dados duvidosos. Validar promove apenas a referência local compatível; excluir remove destaque/referência e exclui o item da lista. Na confirmação de exclusão, oferecer comentário opcional e guardá-lo no apontamento existente, junto à imagem do desenho excluído e às entidades JSON. Publicado com 56 testes e verificação HTTP isolada no servidor. Evidência: `scripts/arete/relatorios/20261007_preprocess_cut_review/RELATORIO.md`.

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| CORTE-REJEICAO-NOVA-GERACAO-20261008 | 2026-10-08 | Exclusão rejeita ocorrência atual; próxima geração válida do mesmo escopo repopula sem restaurar validação humana, preservando apontamento. | Avaliar correção do motor após rejeição. | Pedido explícito do dono neste chat. | Implementado; relatório 20261008_cut_rejection_regeneration. |
| PREPROCESSAMENTO-CORTES-REVISAO-COMENTARIO-20261007 | 2026-10-07 | Listar cortes interpretados no Pré-processamento pelo inventário do estrutural limpo; Pré-processar coleta antes do SA, com validação humana local separada. Exclusão oferece comentário opcional salvo no apontamento com desenho excluído e JSON; itens excluídos saem da lista/contagem. | Revisar níveis antes do SA e depurar exclusões manuais. | Pedido explícito do dono; CONSOLIDACAO-CORTES-INVERTIDAS-20261005.md. | Publicado; 56 testes e HTTP isolado na VPS. |

### LV-NOVA-CORTE-SARRAFEADO-SEM-MADEIRA-PARAFUSO-20261005 — complemento obrigatório

No sarrafeado, a ausência de parafusos inclui retirar os pares de sarrafos extras associados às pontas dos antigos parafusos centrais. Não reaparecem por aumento de altura ou ativação das antigas faixas de parafusos. Preservar sarrafos regulares e garfos verdes. Fonte: correção explícita do dono e captura do corte alto neste chat. Experimento v13 corrige a omissão da v12 em cinco casos, preservando todas as demais entidades. Integração ao motor não executada.

### LV-NOVA-CORTE-SARRAFEADO-GARFOS-20261005 — aprovação com ajustes

O dono definiu que o corte sarrafeado não tem parafusos, inclusive no fundo: utiliza os garfos verdes externos já aprovados. Pediu somente retirar parafusos/ferragens, alinhar letras A/B e elevar C 1 cm, declarando o desenho correto com esses ajustes. Cinco exemplos v12 aplicam essas mudanças; comparação por entidade preserva garfos, sarrafos e demais geometria. Fonte: dono neste chat em 05/10/2026. Estado: design experimental aprovado com ajustes executados, não integração ao motor ou validação publicada. Evidência em `scripts/arete/relatorios/20261004_nova_lv_design_experimentos/dual_v12/`.

### LV-NOVA-CORTE-GRADEADO-APROVADO-20261005 — aprovação do experimento

O dono aprovou explicitamente o design experimental do corte gradeado NOVA e pediu deslocar a letra C 1 cm acima. Cinco DXFs v11 aplicam somente esse deslocamento sobre v09. Corte sarrafeado foi solicitado para comparação e permanece em avaliação. Fonte: dono neste chat em 05/10/2026. Evidência: `scripts/arete/relatorios/20261004_nova_lv_design_experimentos/dual_v11/`. Estado: aprovação visual do corte gradeado; integração ao motor e validação publicada ainda não executadas, sem aprovação implícita do AB ou do sarrafeado.

### LV-NOVA-AB-MONTAGEM-DISTINTA-20261005 — correção que substitui a regra v08

Decisão vigente do dono nesta revisão: sarrafeados têm sarrafo vertical de 7 cm apenas nas pontas; gradeados têm meios pontaletes verdes de 3,5 cm nas emendas e próximos das pontas, com primeira borda a 15 cm confirmada no original. O original tem dois meios adjacentes nas emendas, um por painel. Sarrafos de 7 e linhas de 2,2 do topo são laranja (camada SARR_2.2x7, cor 40); meios pontaletes são verdes (SARR_3.5x7, cor 81). Abertura de pilar tem meios pontaletes nas duas bordas externas e mantém sarrafo superior de 7 cm em ambos os tipos. Em abertura de viga gradeada: vertical de 3,5 até o fundo, travessa do fundo da abertura de 2,2 laranja; fechamento abaixo da abertura é vertical 7 laranja na ponta final ou 3,5 verde se há segmento seguinte. Fonte: correção explícita do dono neste chat em 05/10/2026. Substitui a generalização de ausência de montantes nos gradeados e a remoção do sarrafo superior de pilar registradas em LV-NOVA-AB-EXTREMIDADES-PILAR-20261005. Experimentos v10 gerados para revisão, não integração/aprovação final.

### LV-NOVA-CORTE-PONTAS-CENTRAIS-20261005 — retirar madeira extra

No corte gradeado NOVA das laterais Para/Passa, as pontas dos parafusos centrais são metálicas e não devem receber sarrafos adicionais acima/abaixo de cada ponta. Preservar o conjunto do parafuso do fundo, seus sarrafos e encaixes, explicitamente aprovados pelo dono. Reposicionar as letras dos componentes para não cruzar os eixos dos parafusos. Fonte: comentário e captura do dono em 05/10/2026. Evidência experimental: `scripts/arete/relatorios/20261004_nova_lv_design_experimentos/dual_v09/`. Estado: correção aplicada nos cinco experimentos gradeados, demais entidades preservadas; aprovação visual da nova posição das letras e integração ao motor pendentes.

### LV-NOVA-AB-EXTREMIDADES-PILAR-20261005 — revisão dos experimentos

**Registro histórico parcialmente substituído:** não aplicar aos gradeados a ausência de montantes nas emendas e não remover a travessa superior na passagem de pilar. A decisão vigente é LV-NOVA-AB-MONTAGEM-DISTINTA-20261005 acima.

Modo NOVA, laterais A/B Para e Passa: sarrafos verticais de extremidade somente nas duas pontas da lateral, não a cada divisão entre painéis ou segmento em sequência. A abertura geral de pilar interrompe todos os sarrafos da lateral, inclusive o superior, preservando o painel. O exemplo usado na v07, com sarrafo superior contínuo, foi identificado pelo dono como caso especial e não é regra geral. Aberturas de viga mantêm a proposta v07 nesta rodada. Fonte: correção explícita do dono neste chat em 05/10/2026; `docs/SA-ANALISE/CLASSES/LV.md`, seção de experimentos NOVA. Estado: regra definida; exemplos gradeados v08 para revisão, integração do motor ainda pendente.

### QA-SA-AUTOAJUSTE-ADOCAO-20261003 — interpretação e aprovação humana

| ID | Data do registro | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| QA-SA-AUTOAJUSTE-ADOCAO-20261003 | 2026-10-03 | global QA SA | QA pode refazer geometria, campos, tags e interpretação completa do item; nova camada é resultado agêntico mais atual, mas só substitui SA após validação humana. L1 avalia SA, L2 avalia L1 com viewer populado, L3 segue cadeia; aprovar sem melhoria necessária dispensa novo viewer. | Dono neste chat: “só substitui caso eu valide humanamente a camada tal” e “pode como deve” refazer interpretação; docs/QA-SA-AUTOAJUSTE-E-ADOCAO-HUMANA.md | requisito vigente; implementação e cobertura por classe exigem verificação |
| QA-SA-APONTAMENTO-ADOCAO-L1-20261003 | 2026-10-03 | portal/QA SA | Aprovação humana L1 cria apontamento preservando SA anterior e camada aprovada, para investigar erros descobertos/corrigidos e melhorar motor posteriormente. | Último pedido de execução do dono, transcrito em docs/HANDOFF-QA-SA-13PAV-20261003.md §1 | aprovado; implementação pendente, não alegar função entregue |
| NUMEROS-CONFIRMACAO-BASE-20261003 | 2026-10-03 | global | Manter regra atual da Base: omitir ,0 em medidas e exatamente duas casas para níveis absolutos em metros; substitui pedido anterior deste chat de uma casa fixa em tudo. | Dono respondeu à pergunta de harmonização: “Manter regra atual da Base: omitir ,0; níveis em metros com duas casas” | vigente; APRESENTACAO-NUMERICA.md preservado |


### NIVEIS-DUAS-CASAS-20261003 — exceção global em metros

Níveis absolutos em metros usam exatamente duas casas decimais, com vírgula,
incluindo ,00, em todas as classes, campos, etiquetas, SA, N3/N5 e evidências
dos agentes. Prevalece sobre NUMEROS-UMA-CASA-20261003. Outras medidas mantêm
no máximo uma casa e omitem ,0. Não converter unidades por magnitude nem alterar
geometria ou precisão persistida. Fonte: `APRESENTACAO-NUMERICA.md`.

### NUMEROS-UMA-CASA-20261003 — apresentação global

Medidas e valores decimais para humanos usam no máximo uma casa decimal e vírgula; omitir ,0 em todas
as classes, campos, SA, N3/N5 e evidências. Preservar precisão interna e valores
não editados; não modificar identificadores, contagens, datas ou fontes históricas.
Fonte: `docs/CONHECIMENTO/APRESENTACAO-NUMERICA.md`. Implementação ainda em revisão.

### LV-SUBABAS-CORTE-20261002 — Todos em SA/N3

O dono definiu: SA Todos mostra os cortes sobre o estrutural e dispensa uma segunda aba Todos no estrutural. N3 mantém ambas: Todos reúne os desenhos N3; Todos no estrutural permite consultar sua localização na planta. Fonte: `docs/SA-ANALISE/CLASSES/LV.md`, Subabas SA/N3.

### LV-CORTES-ESTRUTURAL-20261002 — desenhar seções sobre a viga

O dono esclareceu com exemplos que “Todos no estrutural” deve mostrar desenhos das seções transversais SA localizados e rotacionados sobre a viga, como os cortes identificados existentes, e remover os destaques de segmentos dessa vista. Substitui a representação visual de LV-MAPA-PARES-20261002. Fonte: `docs/SA-ANALISE/CLASSES/LV.md`, Cortes sobre o estrutural.

### LV-CONTRASTE-20261002 — reforço das etiquetas e linhas

O dono pediu maior espessura de linha/texto e cores mais claras, aproximadas ao branco, pois os destaques das laterais e do mapa estavam pouco visíveis. Mantido o tamanho reduzido das etiquetas, com reforço de peso, brilho e contornos. Fonte: `docs/SA-ANALISE/CLASSES/LV.md`, Contraste dos destaques.

### LV-MAPA-PARES-20261002 — localizar as Visões Corte no estrutural

Representação visual substituída por LV-CORTES-ESTRUTURAL-20261002; redução das etiquetas das laterais permanece vigente.

O dono pediu uma aba adicional em Visão Corte que mostre todos os segmentos A/B da viga e destaque os intervalos comuns que representam cada seção agrupada. A referência é a faixa dos pares, não as chamadas de corte identificadas no pré-processamento. Uma mesma VC pode ocupar vários trechos. Pediu também reduzir as etiquetas dos segmentos das laterais para um terço do tamanho. Fonte completa: `docs/SA-ANALISE/CLASSES/LV.md`, Mapa de pares no estrutural.

**Status:** canônico · **Criado:** 2026-09-25 · **Tier:** toda decisão aqui é **T1** (validada por humano)

Uma linha por decisão, com a fonte onde ela está escrita por extenso. **A fonte é a
autoridade**: esta linha só resume para achar. Caminhos relativos a
`Agente-cad-PYSIDE-Restored-main/`.

**Como manter:**
- Decisão nova → nova linha (ID seguinte) **e** texto completo no doc canônico do tema.
- Decisão que muda outra → a antiga ganha `revogada por D-xx` na coluna Estado; nunca apagar.
- Escopo `global` vale para toda obra; decisões de uma obra só levam `obra:<nome>`.
- Antes de perguntar ao dono, procurar aqui (e em `kb_query.py`). Pergunta repetida é custo.

## Processo, qualidade e visão

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| NIVEIS-DUAS-CASAS-20261003 | 2026-10-03 | global | Níveis absolutos em metros: exatamente duas casas decimais com vírgula, inclusive ,00, em campos, etiquetas, SA/N3/N5 e evidências de todas as classes; preservar precisão interna e verificar unidade de origem | `docs/CONHECIMENTO/APRESENTACAO-NUMERICA.md` | vigente; exceção à regra de uma casa |
| NUMEROS-UMA-CASA-20261003 | 2026-10-03 | global | Medidas apresentadas com no máximo uma casa decimal e vírgula; omitir ,0; exceto níveis em metros (duas casas); preservar precisão interna, IDs, contagens e fontes históricas | `docs/CONHECIMENTO/APRESENTACAO-NUMERICA.md` | vigente; implementação em revisão |
| D-01 | 2026-07-03 | global | G2 numérico sozinho não sela: selar exige veredito visual registrado (Nível 2) e o dono (Nível 3) | `docs/LOOPING-CANONICO.md` §1.5 | vigente |
| D-02 | 2026-07-03 | global | Nada de API de visão: veredito visual só pelo agente CLI; API exige ordem explícita + calibração | `docs/VISION-VALIDACAO-CAMINHOS.md` (Ordem do dono 03/07) | vigente |
| D-03 | 2026-09-25 | global | Evidência visual: fonte = SVG canônico da ficha; o agente lê o PNG rasterizado desse SVG, com `--zoom` vetorial em região densa | `docs/LOOPING-CANONICO.md` §1.5; `docs/QA-VISAO-EVIDENCIA-CANONICA.md` §2.4 | vigente |
| D-04 | 2026-07-13 | global | Selo laranja isolado: só acende com 100% dos campos obrigatórios de origem `qa_agente` (revogou a versão com mistura) | `docs/CONVENCAO-SELOS-VALIDACAO.md` | vigente |
| D-05 | 2026-07-03 | global | Loop canônico único; script fora da seção 1 não se usa sem ordem explícita | `docs/LOOPING-CANONICO.md` | vigente |
| D-06 | — | global | Escopo incremental rígido: 13_PAV 100% → Obra_TREINO_1 completa → outras obras, uma a uma | `CLAUDE.md` regra 6 | vigente |
| D-07 | — | global | Dúvida de interpretação vai ao dono como ficha visual, com uma pergunta respondível em uma frase; fato do desenho se mede, só convenção se pergunta | `CLAUDE.md` regra 5d | vigente |
| D-08 | 2026-09-29 | global | Jev é segunda leitura **opcional** de dúvidas SA/N1: deve somar CAD, visão, QA e revisão humana; não precisa superar cada comparador isolado para ser útil, nem escreve N1 por conta própria | `docs/SA-ANALISE/JEV-SEGUNDA-LEITURA-OPCIONAL.md` | vigente |

## Produto e entrega

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| D-88/Portal-N3 | 2026-10-01 | global | Selecionar INI, NOVA, Base 1, Base 2 ou Base 3 em radios acima do N3 de todas as classes e do comando todas as classes, antes de gerar | `docs/CONFIGURACAO-MODOS-N3.md` §Seleção antes de gerar; pedidos deste chat | vigente |
| D-89/Vigas-Pav | 2026-10-01 | global | Gradeadas/Sarrafeadas e garfos Sim/Não passam da obra ao pavimento, em radios acima do N3 granular e unificado. Padrões Sarrafeadas e Não, sem Não informado | `docs/CONFIGURACAO-MODOS-N3.md` §Seleção antes de gerar; apontamentos deste chat | vigente; geometria de garfos Sim aguarda regra do dono |
| D-10 | 2026-07-03 | global | DP-1: sem distribuição de binário | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | vigente |
| D-11 | 2026-07-03 | global | DP-2: servidor = workstation do dono + VPN | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | **revogada por D-19** |
| D-12 | 2026-07-03 | global | DP-3: equipe usa portal web com login por membro; a app PySide é do dono | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | vigente |
| D-13 | 2026-07-03 | global | DP-5: SCR não é entregável; AutoCAD sai do produto (entrada DWG→DXF via ODA) | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | vigente |
| D-14 | 2026-07-03 | global | DP-6: embeddings continuam NVIDIA NIM (dependência externa aceita). Nota 2026-09-26: o modelo `nv-embed-v1` está em fim de vida (HTTP 410); a KB usa `nemotron-3-embed-1b`, escolhido por medição (D-22) | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | vigente |
| D-15 | 2026-07-03 | global | DP-7: quantitativos só depois da estabilidade de qualidade | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | superada por D-66 (28/09) |
| D-16 | 2026-07-03 | global | DP-9: Arete é o trabalho principal; em conflito, qualidade vence prazo | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | vigente |
| D-17 | — | global | DP-10 a DP-14: obras chegam pelo Google Drive (1 pasta por usuário, polling); N5 = 1 DXF por classe+pavimento; liberação do N5 é self-service após validar N1+N3; fluxo de 6 etapas | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | vigente |
| D-18 | 2026-07-30 | global | Definição de pronto: entregável = N5; as 4 classes juntas; web é o produto, PySide vira laboratório; erro do motor → escape hatch (operador desenha no viewer web) | `docs/MASTERPLAN-CONSOLIDACAO-ENTREGA.md` §1 | vigente |
| D-19 | 2026-08-10 | global | A VPS Hetzner vira o servidor principal de tudo, com acesso público (substitui DP-2) | `docs/HANDOFF-DEVOPS-VPS-HETZNER.md` §0 | vigente |
| D-20 | — | global | Sem sincronização campo a campo web ↔ app: a app é só treino/validação interna | `docs/MASTERPLAN-OBRAS-DRIVE.md` (Fora de escopo) | vigente |
| D-21 | — | global | Generalização para as outras obras saiu da fila; volta quando o dono decidir | `docs/MASTERPLAN-CONSOLIDACAO-ENTREGA.md` (tabela final) | vigente |
| D-22 | 2026-09-26 | global | Embedder da KB = "o mais eficiente e disponível", decidido por medição (`kb_eval.py`), não por marca; hoje NIM `nemotron-3-embed-1b`, com busca só por texto como reserva | `docs/CONHECIMENTO/PLANO-HARMONIZACAO.md` §3 | vigente |

## PIL — pilar

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| D-30 | 2026-07-16 | global | Hachura de vazio no topo do painel: N3 **e** N4 devem ter; N4 já selados não são regenerados | `docs/SA-ANALISE/CLASSES/PIL.md` §5.1 | vigente |
| D-31 | 2026-08-20 | global | R1: o vão entre o fim da viga desenhada e a face do pilar é continuação da viga | `docs/INTERPRETACAO-VIGA-CHEGA-VAO-E-FACE.md` R1 | vigente |
| D-32 | 2026-08-20 | global | R2: viga mais estreita que a face → `chega`; do tamanho da face → `interior` | idem R2 | vigente |
| D-33 | 2026-08-21 | global | R3: pilar mais largo que o corredor → a viga atravessa; mesma largura + outra viga do outro lado → morre; mesma largura + a própria viga do outro lado → atravessa | idem R3 | vigente |
| D-34 | 2026-08-22 | global | R4: chegada na esquina é chegada **e** passagem (duas informações, duas faces) | idem R4 | vigente |
| D-35 | 2026-08-19 | global | Invariante de face: viga chega no meio da face → duas lajes, uma em cada canto; chega num canto → uma laje só, no canto oposto; nenhuma chegando → uma laje cobrindo a face. Checagem só expõe a incoerência, não decide quem errou | `docs/INTERPRETACAO-VIGA-CHEGA-VAO-E-FACE.md` §"Como isso se encaixa no invariante de face"; `validate_face_slab_beam_invariant` | vigente |

## LV — lateral de viga

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| D-40 | 2026-09-11 | global | Visão de corte: o N4 replica a geometria medida do recorte N2; o N3 continua proibido de ler N2 | `docs/CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md` (emenda 2026-09-11) | vigente |
| D-41 | 2026-09-13 | global | Abertura de VIGA recorta painel e sarrafo; abertura de PILAR não altera o painel, só recorta o sarrafo | idem §5.2.1 | vigente |
| D-42 | 2026-09-14 | global | Abertura de viga separa segmentos — a separação vem da interpretação, para o N3 reproduzir o que o N4 copia | idem §5.2.3 | vigente |
| D-43 | 2026-09-17 | global | Cota nas pontas: esquerda ≠ direita (laje ou painel) → cota nos dois lados, laje e painel; iguais → uma só, à direita | idem §5.2.6 | vigente |
| D-44 | 2026-09-19 | global | Fator de repetição "NX": começa no 2º painel; só painéis completos (244) e iguais; 1º e último nunca entram; menos de 2 → sem fator | idem §5.2.8 | vigente |
| D-45 | — | global | G3: altura da face = seção + 4 cm (contra a altura total da lateral) | idem §6.1 | vigente |
| D-46 | — | global | G7: no encontro entre vigas decide a profundidade — menos profunda: a lateral passa por baixo até a face oposta; mais profunda: termina na primeira face | idem §6.1 | vigente |
| D-47 | 2026-09-20 | global | G9: o recuo de 11 é do `Para`; o `Passa` não recua | idem §6.1 | vigente |
| D-48 | — | global | G10: lados A e B decidem Para/Passa caso a caso; faces C e D do pilar são sempre `Passa` | idem §6.1 | vigente |
| D-49 | 2026-09-25 | global | O fundo (FV) é referência e comparação para a lateral, nunca lei | `docs/SA-ANALISE/CLASSES/LV.md`; contrato §6.1.1 | vigente |
| D-50 | 2026-09-25 | global | Questionário Q1–Q7: troca de seção abre segmento; mesma profundidade = abertura; Passa = pilar inteiro num segmento com início/fim; pilar e viga coincidentes = ambos; −11 só no N3; contagem do N4 não é referência; autonomia do SA com revisão do dono no front-end | `docs/QUESTIONARIO-LV-SA-2026-09-25.md` | vigente |

## Decisões de 2026-09-26 sobre nível de laje

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| D-36 | 2026-09-26 | global | Nível de laje não é regra fixa: nasce da **conjunção de evidências** (cota contida — que pode ser de uma parte da laje —, vizinhas, pilares, vigas, cortes), como soma de pontos | `docs/PROPOSTA-NIVEL-LAJE-POR-EVIDENCIAS.md` (desenho aguardando respostas) | vigente (princípio) |
| D-37 | 2026-09-26 | global | Inferência automática passa por **portões de coerência** (vários), nunca por uma decisão só; corrigido o bug cm×m do delta de corte | `scripts/arete/relatorios/20260926_correcao_nivel_laje/RELATORIO.md` | vigente |
| D-38 | 2026-09-26 | obra:Obra_TREINO_1 | Dados do 13_PAV com o bug corrigidos pelo agente (4 lajes, 7 pilares, 24 vigas); L318 e 16 segmentos estimados ficam para revisão | idem | vigente |

| D-51 | 2026-09-26 | global | Evidência E9: texto de rebaixo ("−30" etc.) próximo à cota vale; sem cota na laje, texto de rebaixo dentro dela provavelmente se refere a ela (ainda sem exemplos no corpus) | `docs/PROPOSTA-NIVEL-LAJE-POR-EVIDENCIAS.md` §Respostas | vigente |
| D-52 | 2026-09-26 | global | Trecho demarcado com espessura/nível diferente: se **nível − espessura** (fundo) for igual nos trechos → **1 laje só**; se os fundos diferirem → **2 lajes separadas** (marcos à parte). No 13_PAV os fundos eram iguais (1 laje) | idem | vigente |
| D-53 | 2026-09-26 | global | Validação humana é **voto muito forte**, não âncora absoluta: evidência contrária forte abre revisão (nunca muda sozinha) — serve para achar onde sistema e dono discordam | idem | vigente |
| D-54 | 2026-09-26 | obra:Obra_TREINO_1 | Pesos da soma de evidências calibrados contra as lajes validadas do 13_PAV antes de ligar | idem | vigente |
| D-55 | 2026-09-26 | global | Área sem laje costuma ser marcada por **X vermelho**; segmento de viga sem laje encostada pode ser isso (não é necessariamente erro) | idem | vigente (informativa) |
| D-56 | 2026-09-26 | LAJ | L318 **não tem** delta de −30 no corte: o −30 vinha da direção do corte calculada pelo centro da laje longa (corte da V314 lido no eixo errado, contra a L319) — corrigido em 2026-09-27: direção pela borda da laje; L318 = 852.19 | revisão das fotos pelo dono (2026-09-26) | vigente (bug resolvido) |
| D-57 | 2026-09-26 | LV/FV | Segmento de viga que **toca só em parte** uma laje usa o nível dessa laje (ex.: V308 lado B via L325) | idem | vigente |
| D-58 | 2026-09-26 | global | **Quadradinhos** hachurados = rampa (não é laje); somado ao X vermelho (D-55), lado sem laje não tem nível e não é erro | idem | nível: substituída por D-61 (resto vigente) |
| D-59 | 2026-09-26 | LAJ | **L316** é o exemplo canônico de D-52: partes com nível/espessura diferentes e mesmo fundo → uma laje só | idem | vigente (exemplo) |
| D-60 | 2026-09-26 | FV | Segmento de fundo de viga **não pode** ter linhas fora das linhas originais do estrutural (como já vale para LV). V308/V331/V332/VF203/VF301 do 13_PAV estão com segmento FV desalinhado | idem | vigente — implementada: gate `fundo_viga_linhas.py` (repara no par de paredes / largura declarada / laterais da própria viga, apara, ou anula; feedback em `fv_line_gate`) |
| D-61 | 2026-09-27 | global | Segmento de viga **sem laje encostada** recebe nível **estimado**, marcado como tal (nunca vira nível medido; não é erro): "sempre melhor estimado que não ter informação". Ordem: laje encostada (medido) → **outro segmento da mesma viga** com laje encostada → laje com nível mais próxima. Corrige D-58 no ponto do nível. Marca: `nivel_viga_estimado` na viga (origem, laje/segmento de onde veio) | chat 2026-09-27 | vigente |

## Pendente de decisão do dono

- Segmentos estimados do 13_PAV — veredito do dono (2026-09-26): V308 A fora da torre (sem nível), B = nível da L325; V327 sem laje nos dois lados (rampa/X); V328 sem laje (correto); V332 A dentro tem laje, B à direita é exterior. Aplicado em 2026-09-27: geometria FV corrigida pelo gate D-60 (V327 voltou às laterais próprias); faces sem laje encostada (V308 A, V327, V328, V332 B) recebem nível estimado e marcado por D-61 (`nivel_viga_estimado`); V308 B medido na L325.

## Decisões de 2026-09-28 sobre LV (SA)

| ID | Data | Classe | Decisão | Fonte | Estado |
|----|------|--------|---------|-------|--------|
| D-62 | 2026-09-28 | LV | Quando a continuação é **outra viga** (o nome muda), a viga para na **própria delimitação** (pilar) e o trecho seguinte é da outra, seja em L ou reto. Caso: V309 × V307 no P25 — trecho P25→canto (30,71 A / 22,53 B) é da V307; V309 = só 320 | chat 2026-09-28 | vigente — `_corner_stubs_beyond_pillar` + corte no pilar entre rótulos colineares (`lv_beam_scene.py`) |
| D-63 | 2026-09-28 | LV | Passa: pilar entre duas vigas colineares, cada uma encostando de um lado → só a **mais profunda** engloba o pilar (inteiro, inclusive pilar oco em peças, P27); a outra para na face. Mesma altura: as duas englobam | chat 2026-09-28 | Profundidades diferentes vigente; alturas iguais substituídas por LV-PILAR-ALTURAS-IGUAIS-DONO-UNICO-20261010 |
| D-64 | 2026-09-28 | LV | Reafirma D-48/G10 ("bug gravíssimo"): lateral **Para nunca para nas faces C/D** (curtas) do pilar — só nas A/B/E/F/G/H; na face curta o pilar é tratado como Passa (englobado). **A letra é a da face do pilar por onde a lateral CORRE** (paralela à viga), não a da face onde bate de frente: pilar colinear corre pela A/B → Para para (V309 320, V329 141); passa só ao lado de face curta C/D de pilar retangular (VF301 B nos P2–P8, V302 A no P12); pilar em L: E..H → para. A 1ª leitura (face de frente) fez o Para agir como Passa e foi corrigida no mesmo dia | chat 2026-09-28 | vigente — `_side_face_is_short` (`lv_beam_scene.py`) + `segment_cell`. Auditoria no mesmo dia achou mais 2 regras abandonadas no motor de células e implementou: **D-61** (nível estimado marcado, `estimate_missing_cell_levels`) e **G9/D-47** nas pontas (Para recua 11 também no pilar de apoio da extremidade) |
| D-65 | 2026-09-28 | FV | Pilar que **nasce** no pavimento (símbolo da convenção de pilares; no 13_PAV = X) é ignorado pelo fundo: parede interrompida pelo X não é limite, o fundo **segue até topar a viga** seguinte. Corte por viga mais funda é feito nas **paredes** dela, nunca no rótulo. Caso: V301 S2 × P42 × V312 (1603,4, não 1590,1). | dono, chat 28/09 | vigente |
| D-66 | 2026-09-28 | global | Quantitativo entra no portal (aba "Materiais e Construção"): peças **medidas no N3 desenhado** + material de compra. Estoque: chapa **244 × 122**; sarrafo **2,2 × 7 × 3 m** (variantes 2,2 × 10 e 2,2 × 5); grades de viga/pilar em **meio pontalete de 3 m**. Não quantifica: Cima do pilar, Corte da LV (só perspectiva); laje = só painéis. Supera D-15 | chat 2026-09-28 | vigente — `docs/MATERIAIS-E-CONSTRUCAO.md` |
| D-67 | 2026-09-28 | PIL | **Sarrafo de pressão** (layer "Sarrafo de Pressão", linha HIDDEN, desenhado só pelo eixo) é **2,2 × 7**, cortado da barra de 3 m. Responde Q3 | chat 2026-09-28 | vigente — `plano_de_corte.material_da_bitola` |
| D-68 | 2026-09-28 | Materiais | **Por enquanto nenhuma sobra é descarte**: toda sobra de chapa e de barra entra na lista rastreável (sem tamanho mínimo). Responde Q9 | chat 2026-09-28 | vigente — `plano_de_corte.compra_de_grupos` |
| D-69 | 2026-09-28 | Materiais | **Recorte de painel é sobra**: o pedaço que sai do retângulo (entalhe/abertura/viga) entra na lista rastreável e no encaixe — peça que cabe nele (sozinho ou somado à sobra vizinha) é cortada ali | chat 2026-09-28 | vigente — `plano_de_corte._empacotar` / `_regioes_livres` |
| D-70 | 2026-09-29 | Materiais | **Reaproveitamento entre pavimentos em etapas**, cada uma para todos os itens da classe antes da próxima: 1 próprio item (medida idêntica) → 1.5 próprio item (outra medida, cortando) → lista temporária dos montados não usados → 2 outros itens (idêntica) → 2.5 outros itens (cortando) → 3 sobras de chapa/recortes (na medida) → 3.5 sobras cortadas → 4 estoque acumulado antigo → material novo só do que falta. Responde Q8 | chat 2026-09-29 | vigente — `docs/MATERIAIS-E-CONSTRUCAO.md` §12 |
| D-71 | 2026-09-29 | Materiais | **Regras de corte no reaproveitamento** (sarrafo corta junto com o painel): **LV** mesmo tipo (gradeado/sarrafeado), comprimento **igual**, match dos sarrafos/grades de extremidade (esq./dir./nenhum), só a altura varia cortando **embaixo**; **PIL** largura igual, só a altura cortando **em cima**; **FV** largura igual (espessura não se corta), só o **comprimento**, com match dos sarrafos de extremidade; **LAJ** tira de escoramento nunca, painel comum corta em qualquer direção. **Nunca entre classes** | chat 2026-09-29 | vigente — `docs/MATERIAIS-E-CONSTRUCAO.md` §12.3 |
| D-72 | 2026-09-29 | Materiais | **Estoque acumula e se gasta** ao subir a obra, rastreado pelos IDs de painel e sobra; o estoque de pavimentos mais antigos entra como etapa 4. Par "próprio item" por nome/número (V301↔V401), sem exigir mesma posição | chat 2026-09-29 | vigente — `docs/MATERIAIS-E-CONSTRUCAO.md` §12 |
| D-73 | 2026-09-29 | Portal | "Material de compra" vira **"Material necessário, preparação e reaproveitamento"** com 3 sub-abas: Preparação com Materiais Novos / Preparação com Materiais Reaproveitados e Novos / Materiais Disponíveis dos Pavimentos Anteriores (sobras juntas sem proveniência; montados por item da classe) | chat 2026-09-29 | vigente, implementado 29/09 — `docs/MATERIAIS-E-CONSTRUCAO.md` §12.6 |
| D-74 | 2026-09-29 | Materiais | **Sequência dos pavimentos = a ordem de todos os pavimentos da obra** (subsolos, térreo, 1º, tipo 2–10 como um pavimento só, 11º, 12º, cobertura, deck…): pavimento sem dados não quebra a sequência; o estoque só começa do zero no primeiro pavimento. O portal guarda anterior/próximo e a faixa do TIPO; cada repetição do TIPO alimenta a seguinte e a última alimenta o próximo pavimento | chat 2026-09-29 | vigente, implementado 29/09 — `portal_obra_pavimentos`, `GET/PUT /obras/{obra_id}/pavimentos/ordem`; consulta usa a ordem cadastrada e expande a faixa TIPO somente no cálculo, com fallback por nome em obras ainda não configuradas |
| D-75 | 2026-09-29 | Materiais | **Sobra limpa de chapa pode ir para outra classe** (só recorte puro de painel/chapa, sem sarrafo); painel montado e retalho com sarrafo continuam só na própria classe. Mantém ID e registro de proveniência e de fornecimento | chat 2026-09-29 | vigente — implementado 29/09 (`docs/MATERIAIS-E-CONSTRUCAO.md` §12.6) |
| D-77 | 2026-09-29 | Materiais | **Sobras: máximo aproveitamento, peças grandes primeiro** — não há ordem de classes; os painéis maiores de todas as classes do pavimento escolhem primeiro a sobra (a menor que serve) | chat 2026-09-29 | vigente — `docs/MATERIAIS-E-CONSTRUCAO.md` §12.6 |
| D-78 | 2026-09-29 | Materiais/Portal | **Reaproveitamento em 2 frentes: Para e Passa**, calculadas e listadas separadas (pilares e laterais de cada modo); fundo e laje entram igualmente nos dois, sem citar Para/Passa. A obra tem o campo **comportamento Para / Passa / Misto** (Misto = hoje, as 2 listas); a consulta exibe só a lista do modo da obra | chat 2026-09-29 | vigente, implementado 29/09 — `portal_obras.comportamento`, filtro de rotas internas e códigos públicos, payload público da obra/pavimento |
| D-76 | 2026-09-29 | FV | **Laterais servem de ajuda ao fundo, não de regra rígida** (espelho de o FV ser referência da LV): o fundo deve ficar tão completo quanto as laterais — trecho com as duas paredes reais e sem fundo ganha painel; painel na faixa de outra viga volta para a dona. Sempre com prova local do DXF (linha real, fora de cota, pilar sólido/hachura fora); fundo validado não muda | chat 2026-09-29 (apontamento 9cf6beac) | vigente, implementado 29/09 — `docs/SA-ANALISE/CLASSES/FV.md` §1, `src/core/beam_interpreters/fundo_viga_lateral_ref.py` |
| D-79 | 2026-09-29 | FV | **Cruzamento de fundos tem um único dono**, inclusive em chanfros e diagonais: contorno humano vence; entre automáticos decide por painel a maior profundidade, depois largura, continuidade e desempate determinístico. O perdedor é recortado pelo polígono real, sem retangularizar. Dois contornos humanos conflitantes são reportados e preservados para revisão | chat 2026-09-29 | vigente, implementado 29/09 — `docs/SA-ANALISE/CLASSES/FV.md` §1, `fundo_viga_lateral_ref.resolve_automatic_overlaps_all` |
| D-80 | 2026-09-29 | FV | **Fundo não tem comprimento mínimo**: havendo área positiva e duas faces reais, cria-se o painel mesmo isolado e mesmo com 1 cm. Comprimento nunca decide descarte. O L é preferido quando uma pequena cauda ortogonal termina na face do corpo longitudinal adjacente e o corpo é claramente dominante (no N4: V303 = 418 cm com caudas de 10/30 cm); sem dominância, cada trecho continua como painel próprio (V304×V329 = 199×141 cm). Essa relação decide apenas **unir ou separar**, nunca apagar. Trecho isolado sem ligação também não some por tamanho | chat 2026-09-29; engenharia reversa N4 do 13_PAV (V303 e contraste V304×V329) | vigente, implementado 29/09 — `docs/SA-ANALISE/CLASSES/FV.md` §1, `beam_tracer._separate_one_sided_l_extensions`, `fundo_viga_lateral_ref.py` |
| D-81 | 2026-09-30 | FV | **P13 do 13_PAV é sólido até a região apontada; ali são dois segmentos, não um fundo unido.** Um símbolo NASCE de outro pilar sobreposto e paredes contínuas não anulam seção sólida, nem exclusão de pilar com classificação incerta. Isso não reintroduz limite mínimo de fundo | dono, correção do apontamento P13 no chat 30/09 | vigente — `docs/SA-ANALISE/CLASSES/FV.md` §1, `fundo_viga_lateral_ref._bottom_scene` |
| D-82 | 2026-09-30 | FV | **L de 90 graus = dois painéis; L angulado = um painel único cortado no ângulo, sem divisão no nascimento do L.** Não decide pela dominância relativa da perna. Usar também os robôs, a lógica N4 e desenhos de referência para validar reprodução e interpretação, sem copiar geometria N4 para N1. Substitui a parte de D-80 que unia caudas ortogonais; mantém a ausência de comprimento mínimo | dono, chat 30/09 | vigente; união ortogonal removida, 59 testes focados passaram; selo N3/N4 ainda não emitido — `docs/SA-ANALISE/CLASSES/FV.md` §1 |
| D-83 | 2026-09-30 | FV | **Não criar costura artificial entre trechos contíguos da mesma faixa/seção.** No cruzamento, privilegiar continuidade física, não soma de vãos interrompidos nem orientação vertical/horizontal; incidentes terminam nas faces da viga que atravessa. Profundidade/largura e validação humana mantêm precedência. Hipótese operacional: maior painel/desenvolvimento total após D-60, com desenvolvimento como desempate. Não une pilares, mudanças de seção, chanfros ou L de 90 graus | dono, apontamento 30/09 12:29:43; fórmula de desempate é implementação testada, não regra universal ditada pelo dono | 62 testes focados; replay 13/14 sem conflitos ou lacunas medidas; gates N3/N4 não certificadas |

| D-83 | 2026-09-30 | PIL/Portal | Convenção colore também os boxes: SEGUE azul, MORRE amarelo, NASCE vermelho. NASCE no próximo pavimento permanece acessível no SA e fica excluído dos motores N3/N5; correção manual da classificação reativa ambos. Orientação, classificação, níveis e pé-direito editáveis com salvar na ficha SA | dono, apontamentos deste chat | vigente — `src/core/pillar_sa_review.py`, rotas SA, materialização N3 e montagem N5 |

| D-84 | 2026-09-30 | Portal/Pré-processamento | Convenção de Níveis em abas por classe, uma linha por item, todas as partes em colunas/detalhes, nível obtido e confiança com cores para dúvidas/conflitos. Agrupamento visual por nome/classe/torre preserva todos os registros de origem. Percentual ausente aparece como Não calculada | dono, apontamento em `documento=preproc:niveis` | vigente — `docs/PLANO-PREPROCESSAMENTO-PAVIMENTO-TORRES.md`, relatório `20260930-niveis-abas` |

| D-84 | 2026-09-30 | PIL/Portal | N5 de pilares dividido em dois arquivos e subabas: PARA (Cima, ABCD Para, Grade Para) e PASSA (Cima, ABCD Passa, Grade Passa). Cima universal compartilhada em ambos; carregar apenas conjunto ativo para reduzir peso | dono, pedido deste chat | vigente — montagem N5, pipeline, rotas e viewer web |

| LV-colunas-20260930 | 2026-09-30 | LV/Portal | Preencher aberturas de viga por segmento, com posição esquerda/direita; nova coluna Passa por pilares: Para sempre Não, Passa só faces A/B/E/F/G/H, ignorar C/D, distância esquerda + comprimento físico do pilar no segmento + distância direita | dono, chat Investigue e corrija apontamento | vigente — docs/SA-ANALISE/CLASSES/LV.md |

| D-85/FV | 2026-09-30 | FV | **Encontros angulados preferem chanfros retos completos, não recortes em degrau ou L diagonal desnecessário.** Distinguir chegada/cruzamento de vigas distintas de dobra contínua da mesma viga. L legítimo segue D-82; vigas distintas conservam donos separados. Redistribuir a área comprovada sem modificar cobertura externa, pilares, profundidades distintas ou geometria humana. Não ignorar peças pequenas | dono, `fundos` 15:12:21 e `fundos2` 15:13:38, esclarecimento no chat 30/09 | vigente — `docs/SA-ANALISE/CLASSES/FV.md` §1; relatório `20260930_fv_chanfros`; selo N3/N4 não emitido |
| D-85/FV-adendo-20261001 | 2026-10-01 | FV | **Encontro triplo: substituir a ponta com dois chanfros por uma única reta de parede a parede**, redistribuindo a ponta entre os dois fundos vizinhos, sem apagar área ou unir donos. Caso aprovado V307/V306/VF202; preservar VF202/VF203. Regra geométrica para chegadas distintas de igual profundidade, fora de sólidos e contornos humanos; não converter cruzamento passante ou dobra da mesma viga | dono, comentário "dois chanfros na V306 desnecessário" e confirmação "simmm" à proposta de redistribuição entre três | vigente — FV.md §1, `_single_cut_triple_junctions`; testes/replay em `20261001_fv_chanfro_unico`; não é selo N3/N4 |

| D-86/Pré-SA | 2026-09-30 | Pré-processamento/SA | **Pré-processar deve coletar o necessário para preencher ao máximo a Convenção de Níveis antes do SA, inclusive executando coleta canônica SA parcial/completa.** Preservar todos os níveis por segmento/parte, origem e dúvidas; o SA deve consumir a informação comprovada na interpretação. Coleta isolada não equivale a certificação QA nem atualização dos resultados SA já publicados | dono, pedido explícito neste chat | vigente — `docs/PLANO-PREPROCESSAMENTO-PAVIMENTO-TORRES.md`; evidência e consumo real em relatório `20260930-niveis-sa-evidencias` |
| D-87/LV | 2026-09-30 | LV/Visão Corte | **Agrupar pares A/B com a mesma seção**, preservando os trechos de origem. A lista deve reunir também cortes identificados no SA e no pré-processamento, com origem e associação verificáveis | dono, resposta textual neste chat: “Agrupar pares com a mesma seção” | vigente — `docs/SA-ANALISE/CLASSES/LV.md`; inventário derivado, sem mudança do N1 |
| PIL-modos-20260930 | 2026-09-30 | PIL/Portal | Nova e Ini abaixo de Para/Passa, fora do viewer e com o mesmo design. Troca exibe N5 existente; sem N3 do modo ou sem N5 apenas avisa. Motores N3/N5 perguntam estilo; N5 oferece somente modo alimentado por N3 completo correspondente | dono, apontamento deste chat | publicado; 54 testes Python e 6 cenários JS; clique real pendente por falha da conexão de automação |
| N3-modos-20260930 | 2026-09-30 | Portal/N3 | Todos os viewers N3 que possuem Nova/Ini devem exibir esses controles fora do desenho, como subabas no padrão das subabas finais N3/N5 | dono, pedido deste chat | `docs/PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md` §7 |
| N3-config-modos-20261001 | 2026-10-01 | Portal/N3 | Configuração de Modos após Ver apontamentos, Ini/Nova e cinco classes com LV Para/Passa independentes. Ajustes influenciam novas gerações N3. Preservar desenho atual como padrão; legado orienta a semântica, sem restaurar algoritmos antigos | dono, pedido e esclarecimento neste chat | publicado e testado; controles efetivos e limites em docs/CONFIGURACAO-MODOS-N3.md |

## Convenção por segmento e face — decisão do dono, 2026-10-01

Vigas têm uma linha por item, com uma linha de texto por segmento FV em Nível obtido.
Nível Segmentos Laterais discrimina A/B Para/Passa e seus trechos: o vínculo com FV
é espacial, nunca por igualdade de índice. FV usa cortes; LV usa cortes/lajes e pode
completar FV sem evidência suficiente. O retorno FV→LV conserva a origem independente
e não cria confirmação circular. Pilar exibe o nível final do contato mais alto com
laje/viga e a face correspondente; base permanece na própria coluna.

Implementação v6: sementes LV independentes congeladas; cobertura única mínima de 80%
para completar FV, sem somar Para/Passa duplicadas. LV recebe intervalos geométricos
por sobreposição, podendo conter vários níveis no mesmo segmento; não há média.
Cortes com duas marcas vermelhas paralelas de interrupção não permitem converter
a altura desenhada em desnível absoluto. No 13_PAV, sete cortes foram rejeitados
por esse motivo (PNG L316 no relatório).

Confiança é suporte de evidência rastreável, não probabilidade calibrada. Origem CAD
95; referência geral 25; estimativa 30; inferência 55 ou 65 conforme método; demais
evidências 75. Pendências de origem recebem descontos explícitos. Cada transferência
usa a fonte mais fraca e fator espacial <=1. Ausência de nível tem 0; níveis por
trecho conservam seus escores individuais. Campos automáticos sem origem
independente ficam limitados a 30. Os pesos E1–E9 ainda aguardam a calibração prevista.

QA: 92 testes na rodada principal, 16 reexecutados após o ajuste final; nova coleta
na fila oficial concluída em 13_PAV, 478 geometrias preservadas frente à versão
anterior, 668 fatos com cálculo de confiança, proveniência sem ciclos. Browser:
46 pilares, 36 vigas, 31 lajes sem repetição; 86 linhas FV e 541 trechos LV.
30 dos 35 pilares existentes têm topo associado; P9/P10/P25/P34/P35 pendentes.
Persistem fontes fracas, níveis múltiplos e conflitos, expressos na ficha. Não há
validação humana de todos os fatos nem selo Arete integral. Relatório:
`scripts/arete/relatorios/20261001-niveis-segmentos/RELATORIO.md`.

## N3-config-subabas-moldura-20261001

O dono pediu agrupar configurações similares em subabas dentro de cada classe,
com uma subaba Moldura para enviar DXF e visualizar o documento. A finalidade
na geração será explicada depois: nesta etapa o arquivo é referência, sem
interferir em N3/N5. Armazenamento separado por modo/classe. Publicado na VPS
após terminar a fila existente; upload/renderização, zoom/reset, isolamento e
preservação do rascunho entre subabas foram validados. Dez testes focados passaram.
Referência: docs/CONFIGURACAO-MODOS-N3.md.


## LAJ-degraus-cortes-amarelos-20261001

O dono pediu reconhecer trechos internos com diferença de espessura mesmo sem corte de laje. Destaques amarelos notificam degraus; diferenças comprovadas de fundo (nível − espessura) em relação à laje dona ficam vermelhas no destaque de lajes. Cortes próprios de laje devem entrar em Visão de Cortes identificados pelo nome da laje e destacados em amarelo, separadamente dos cortes de viga. Preservar D-52: fundo igual significa uma laje; diferente indica separação. Ausência de cota permanece explícita, sem supor fundo igual. Ver docs/SA-ANALISE/CLASSES/LAJ.md e src/core/slab_steps.py.

## Configuração granular de modos — 01/10/2026

O dono pediu retirar Blocos, separar textos/hachuras/cotas por função real e componentes por vista, incluir Exemplos (dez DXFs por modo/classe) e Detalhes especiais com anotações. Modo Molde 1, 2 e 3 são cópias independentes de Nova; rótulos Modo iNI e Modo Nova. Preservar a qualidade do gerador atual. Moldura e Exemplos apenas armazenam referências nesta etapa. Implementação/testes locais concluídos; publicação pendente de término do job ativo na VPS. Referência: docs/CONFIGURACAO-MODOS-N3.md e scripts/arete/relatorios/20261001_config_granular/RELATORIO.md.

Atualização da entrega granular: publicado na VPS em 01/10/2026 às 19:19 UTC e confirmado no navegador de produção; os bloqueios de publicação anteriores foram resolvidos preservando alterações dos demais agentes.

## LV-abertura-nao-acrescenta-corte-20261002

Decisão do dono neste chat: **“Abertura somente nas laterais; não acrescenta Visão Corte”**.
Excluir do pareamento para seções comuns apenas a faixa física comprovada da abertura
de viga, projetada no eixo e no sentido original de leitura de cada segmento A/B.
Preservar a abertura na ficha lateral e registrar a exclusão na proveniência.
Ausência real de laje fora dessa faixa continua sendo uma seção válida.
Não reduzir por nome, tamanho do trecho ou pela contagem do N4.

## LV-corte-sarrafos-ferragens-20261001

O dono confirmou que os sarrafos da Visão Corte LV seguem fielmente os N3
respectivos de cada lado. Parafusos têm regra por medida; centrais têm mínimo
cujo valor ainda deve ser recuperado do legado. Montagem inferior sempre
presente; não recorda mínimo inferior. Regras exclusivas da seção/laterais de
viga, sem transferir Visão Cima de pilares. Fonte: conversa de 01/10/2026.
Referência: docs/CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md, seção Ferragens.

Correção confirmada pelo dono após leitura do histórico: existe a exceção de
laje inferior em qualquer lado, que suprime fixações inferiores e centrais.
Sem LI, inferior não tem mínimo; centrais usam H1 > 40 / > 90 nos DOIS lados,
eixos 25 / 75 cm. A confirmação de LI substitui a afirmação anterior de inferior
sempre presente. Consulta Git autorizada apenas para leitura; nenhuma restauração.

## SA granular na edição manual — 01/10/2026

| Decisão | Regra | Fonte |
|---|---|---|
| SA-MANUAL-GRANULAR-20261001 | Reconhecer campos/níveis apenas do segmento FV/LV salvo ou item PIL/LAJ, preservando contorno e vizinhos. Sem SA completo de viga, sem aprovação automática; atualizar destaque/lista/ficha N1 dinamicamente e deixar falta de evidência pendente. | Pedido do dono em 01/10/2026; docs/PROVENIENCIA-CAMPOS-FV.md |

O dono determinou que novos/editados passem pelo reconhecimento de campos e
níveis durante o salvamento. Para vigas/laterais/fundos, somente o segmento;
para pilares/lajes, somente o item. Não executar SA completo da viga nem mudar
o contorno manual. Atualizar destaque, lista esquerda e ficha SA/N1 sem refresh,
com feedback de etapas e desempenho medido. Valores sem evidência permanecem
pendentes; reconhecimento automático não sela aprovação humana. Implementação
publicada na VPS após esvaziar a fila, com backup e preservação de alterações
concorrentes. 23 testes focados passaram. Ciclo real de criação/redesenho/exclusão
validado pelo navegador no 13_PAV com laje e segmento de fundo temporários;
ficha/lista/destaque atualizam sem refresh ao salvar. Campos sem evidência continuam
pendentes; não equivale a certificação Arete. Anotações de nomes manuais só aceitam
identidade segura pertencente a item manual existente.
Complemento de 02/10/2026: excluir também deve atualizar destaque, lista N1,
seleção e próximo segmento sem recarregar a página nem sair do estrutural.
Feedback em etapas reais: 25% requisição, 75% atualização visual, 100% concluído.
Se a exclusão já persistiu e a atualização visual falhar, repetir somente a
atualização, nunca a exclusão. Criação/edição/exclusão no estrutural não devem
abrir automaticamente a ficha de outra viga. Reteste real de S7 temporário
na V306 passou; os 91 fundos originais permaneceram integralmente iguais.
Complemento de seleção de 02/10/2026: clicar em um destaque do estrutural
preenche o editor com a classe, item e segmento exatos, incluindo o lado A/B.
Com Desenhar no SVG ativo, a seleção por clique fica desabilitada. Arrastar
para navegar não seleciona; selecionar não salva, exclui ou inicia redesenho.
Validado no navegador para FV, PIL, LAJ e LV A/B, sem alteração persistida.
OSNAP (02/10/2026): dono especificou atração apenas para pontas, encontros
literais/cruzamentos e vértices de mudança de direção; não para a extensão
da linha nem meios artificiais. Gravidade aprovada 24 px; bolinha ampliada.
Referência: docs/PROVENIENCIA-CAMPOS-FV.md e
scripts/arete/relatorios/20261001_manual_sa_granular/RELATORIO.md.

## FV-VISAO-CORTE-T-20261004

O dono, com a ficha `scripts/arete/relatorios/20261004_qa_jev_fv_f0_f2/DUVIDA-T-PREENCHIDO-12CM.html` aberta, definiu que esse T preenchido é uma visão corte, não uma viga. A haste mede 12 cm, o conjunto mede 55 cm e o texto 55 está ao lado. O desenho não abre o fundo e não cria outra viga; o fundo segue contínuo por baixo. Vale para as oito repetições do 13_PAV (V301 trechos 5 e 12, V302 trechos 3 e 6, V303 trechos 3 e 6, V306 trechos 3 e 6).

No mesmo dia, com `DUVIDAS-ABERTURAS-FV.html`, o dono disse que todos aqueles desenhos são visão corte e não influenciam o fundo. Entram o T de 120 (V312, V325, V309A e o T da V330), o T de um lado só com 7 e 48 (VF203 e VF301, trechos 3 e 6), o T da V302 trecho 1 com o 52, o T da V332 e o preenchimento largo à esquerda do T na V330. A cota e o lado da haste não decidem. A forma é a já usada nas outras classes: alma e braços, em T, L, retângulo ou escalonada (`docs/MASTERPLAN-ARETE-FUNDO-VIGA.md`, Visão Corte de Vigas). A V330 trecho 1 segue sem certificar por quatro traços fora desse desenho (295, 442, 443 e 445). A conta PASS 19 / NC 65 / FAIL 12 não foi recontada.


### MODE-DEFAULTS-CURRENT-20261001

O dono determinou que os valores da Configuração de Modos sejam obtidos dos geradores N3 atuais por classe e modo, sem importar predefinições do legado. Valores variáveis permanecem preservados, com as variações reais visíveis; configurações existentes não são sobrescritas. Fonte canônica: docs/CONFIGURACAO-MODOS-N3.md.


### D64 — 2026-10-01 — continuidade do fundo nas regiões do 13_PAV
O dono confirmou explicitamente a pergunta sobre L313, L320, L321, L322, L323 e L324: fundo contínuo; trechos h=10 em 852,16 m e h=13 em 852,19 m. Decisão limitada aos seis contornos e à revisão DXF examinada; não é regra universal para qualquer degrau. Persistir como revisão derivada com UID do contorno e SHA do DXF.
L317: o dono indicou que o corte atravessa uma região com cota da L316; calcular pelo contato real, não perguntar um nível que pode ser medido. Conferência geométrica: região interna L316 852,16 m, aba L317 +3 cm, portanto 852,19 m. Interrupção no fuste não invalida o delta local entre abas.


### NIV-SEM-LAJE-20261002 — nível de saída em escadas, rampas e vazios

Dono, comentários visuais de 02/10/2026: escada, rampa e X de ausência não são lajes. Vigas e pilares nesses lugares usam o nível base de saída do pavimento, obtido da convenção ou, na ausência dela, do nível mais comum das lajes. Exigir reconhecimento geométrico da ausência; não inventar laje. Preservar evidência específica de nível diferente. Substitui D-61 para ausência comprovada, mantendo-a onde falta evidência. Regra geral sem nomes/cotas fixos; motor e QA no manual `INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md` §9.

### N3-CARDS-20261002 — seleção visual dos cinco modos

O dono pediu substituir os círculos dos modos por cards compactos semelhantes aos botões QA e à lista de itens. Todos os modos não selecionados ficam com fundo azul; somente o selecionado fica verde. Preservar escolha única antes de gerar, em todas as classes e no painel de todas as classes. Complementa a decisão de pré-seleção dos modos de 01/10/2026. Fonte canônica: docs/CONFIGURACAO-MODOS-N3.md.

Complemento: aplicar também a Gradeadas/Sarrafeadas e Garfos Sim/Não. Os cinco modos devem dividir a largura disponível em uma única linha horizontal, com quebra do texto dentro dos cards e crescimento vertical apenas quando necessário. Economia de altura é prioritária para o dono.

Complemento de espaço vertical: remover a legenda permanente “Opções deste pavimento”. Preservar somente mensagens temporárias de salvamento e erros.

### Consolidação de níveis — 2026-10-01

As linhas abaixo registram instruções desta conversa, sem criar cotas universais. O identificador local D64-20261001-user-confirmation não renumera nem revoga D-64 do catálogo LV.

| Decisão | Escopo e regra | Fonte |
|---|---|---|
| NIV-REGIOES-20261001 | LAJ: medir nível e h por região; fundo = nível − h/100. Fundo igual mantém uma laje; diferente comprovado destaca vermelho. Degraus/cortes de laje amarelos na Visão de Cortes. | Dono, comentários e instruções desta conversa de 01/10; D-52 preservada |
| NIV-SEGMENTOS-20261001 | FV/LV: níveis e confiança por segmento; match espacial de fundos/laterais com faixas quando necessário; suporte independente nos dois sentidos sem ciclo. | Dono, pedido de níveis segmentados nesta conversa |
| NIV-PIL-FINAL-20261001 | PIL: nível final da face em contato com a laje/região/viga mais alta; base separada. | Dono, instrução sobre nível final dos pilares nesta conversa |
| NIV-PREPROCESS-20261001 | Coletar análise SA necessária para preencher a convenção com qualidade antes do consumo; confiança realmente calculada e QA por unidade. | Dono, instruções de pré-processamento e QA nesta conversa |
| NIV-FUNDO-CONTINUO-13PAV-20261001 | Somente L313/BD3, L320/BD6, L321/BD7, L322/BD8, L323/BD9, L324/BDA da revisão examinada: h10 = 852,16 e h13 = 852,19, fundo contínuo. | Dono confirmou explicitamente em 01/10; arquivo derivado com SHA e UID |
| NIV-CORTE-CONTATO-20261001 | Antes de perguntar cota, medir corte em contato real; L317 resolvida por L316/BD4 +3 cm. O exemplo não é hardcode. | Dono indicou o corte; prova geométrica em RESOLUCAO-L317-D64.md |


### NIV-LV-CONTINUIDADE-20261002 — passagem sobre pilar não muda nível

Dono confirmou em 02/10: a parte da lateral que passa pelo pilar não afeta o nível do segmento; conserva a definição de lajes, fundo e Visão de Corte já estabelecida para ele. Ausência local de fundo desenhado não implica mudança de cota. Mudança real deve ser tratada na segmentação/evidência, sem unificar fontes divergentes. Manual integrado §10.

### FV-REFERENCIA-MANUAL-20261002 — repartição do encontro angulado

O dono desenhou V307/V306/VF202/VF203 no 13_PAV e pediu ao motor chegar dinamicamente à mesma interpretação. A referência corrige a repartição anterior por metades: no caso de duas continuações colineares com larguras distintas e terceiro braço angulado, a continuação estreita termina na parede do braço; a larga e o braço têm uma interface única entre suas paredes reais. Geometria humana protegida, sem nomes/coordenadas especiais nem consumo de N2/N4 pelo N1. Hipótese geométrica implementada e validada por testes/replay, com tolerâncias residuais medidas; não constitui aprovação humana automática de todo o pavimento. Ver FV.md §1 e relatório `20261002_fv_stepped_junction`.

Achado técnico da validação sem cache: contatos arredondados entre vértices e
arestas impediam o preenchimento inicial de um triângulo do encontro. A correção
fica limitada à célula comprovada e à tolerância numérica de 0,05 cm, preservando
material existente. Não é limite mínimo de fundo nem autorização para unir
separações reais; ver FV.md §1. Não é uma nova convenção atribuída ao dono.


### NIV-LV-DEGRAUS-20261002 — laterais Para/Passa nos degraus das lajes

O dono confirmou que os degraus reconhecidos pelo SA das lajes devem seccionar as laterais de viga Para e Passa que os tocam. No N3, os segmentos seguem encostados em sequência, com as aberturas. A passagem sobre pilar não muda nível. V329 possui fundo e usa L318/852,19 à esquerda e vazio à direita; a maior profundidade da V329 (19/60) lhe dá passagem no P27 frente à V328 (19/55). V309A B exemplifica a divisão por regiões da L309. Motor aplica geometria e regiões dinamicamente, sem exceção por nome. Regra integrada: manual de níveis §11; QA e limitações no relatório 20261002-lv-degraus-continuidade.

### NIV-VIGA-LAJE-PAINEL-20261003 — degrau da laje não muda a viga

O dono esclareceu: mudança de nível da viga exige Visão de Corte ou mudança do hatch/preenchimento da própria viga. Degrau da laje, sozinho, não determina mudança da viga. Na ausência dessa evidência, manter a referência da viga, desenhar a laje na cota regional e um painel acima para fechar a diferença (3 cm no exemplo). A divisão das laterais Para/Passa permanece, sem confundir segmentação executiva com mudança da cota da viga. O motor deve publicar essa distinção na ficha para o N3; não consultar N2/N4 como fonte N1. Ver manual de níveis §13. O reconhecimento completo de mudanças de hatch/preenchimento ainda requer QA geométrico próprio; esta decisão não certifica automaticamente fontes estimadas.

### FV-PILAR-SOLIDO-20261002 — proteção de fundos herdados e reconstruídos

O dono apontou invasões de P19 por V303 e de P18 por V330 no 13_PAV e pediu correção preventiva. Achado técnico: os pilares já eram reconhecidos como sólidos, mas a exclusão alcançava a recuperação de trechos novos, não todos os contornos herdados/reconstruídos. A proteção deve reaplicar a diferença geométrica com os sólidos antes da recuperação e depois da resolução de encontros/prolongamentos. NASCE e pilares explicitamente ignorados não bloqueiam; nenhum limite mínimo de comprimento é introduzido. Fragmentos positivos e cortes internos são preservados sem preencher o sólido. Geometrias manuais/validadas não são alteradas silenciosamente; conflitos são registrados para revisão. Regra geral sem nomes/coordenadas especiais; FV.md §1 e relatório técnico 20261002_fv_stepped_junction. Não implica certificação Arete global.


### N3-NOVA-PIL-ESPECIAL-CIMA-20261003 — padrão aprovado do L

O dono aprovou a prévia L v26 do CIMA especial Nova e pediu sua generalização dinâmica a partir do SA para U/T, com faces A–H. A aprovação cobre o L; U/T são propostas para avaliação própria. Regras consolidadas de painéis vermelhos, encontros internos/externos, grades sem sobreposição, parafusos, hachuras, letras e cotas: [PADRAO-NOVA-PILARES-ESPECIAIS-CIMA.md](../PADRAO-NOVA-PILARES-ESPECIAIS-CIMA.md). Preservar ABCD; desenho de grades aprovado separadamente. Não confundir aprovação visual do experimento com integração no motor de produção.

### N3-NOVA-CIMA-T-FACES-PERFIS-20261003

Na proposta CIMA do T, o dono pediu trocar A com H e C com E; perfil metálico
somente nas laterais, sem fechar as três pontas livres. Correção aplicada na
prévia T_v2; não constitui aprovação geral do T nem integração em produção.
Correspondência física documentada em PADRAO-NOVA-PILARES-ESPECIAIS-CIMA.md.

### FV-MODULACAO-244-20261003 — chapa limitada sem cortar a dobra angular

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| FV-MODULACAO-244-20261003 | 2026-10-03 | global | Limite normal de chapa de 244 cm independente da dobra angular; emendar na parte reta, nunca no nascimento do L. Preservar a dobra inteira e todos os pedaços positivos; L a 90° mantém regra própria | `docs/SA-ANALISE/CLASSES/FV.md` §1 | vigente |

O dono esclareceu que o limite normal de 244 cm também vale no fundo angular.
Não é uma divisão causada pela dobra: a emenda deve ocorrer na parte reta,
mantendo a dobra inteira no painel terminal. O L a 90° continua sujeito à sua
regra própria de dois painéis. Não generalizar uma regra como substituta da outra.
Detalhar cotas da dobra e do chanfro pelos vértices; N2/N4 são comparação QA,
nunca fonte de geometria do SA. Preservar todos os pedaços positivos, inclusive
1 cm. Aplicação dinâmica sem exceção por viga ou pavimento em FV.md §1; evidência
e limites em `scripts/arete/relatorios/20261003_v307_modulacao/`.


### NIV-CORTE-CONTINUIDADE-20261003 — operacionalização geométrica

A regra do dono sobre corte/hatch e continuidade de viga é operacionalizada com haste do corte medida, aba da laje conferida e mesma seção espacial. Dimensão próxima de pilar não vale como altura FV quando a largura diverge. Degrau de laje continua separado da referência de viga. Não promover inferência a medição: preservar conflitos, fontes e score limitado. Critérios, tolerâncias e limitações estão no manual de níveis §14; exemplos VF203/VF301 são evidência de QA, nunca exceções por nome.

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| NIV-CORTE-CONTINUIDADE-20261003 | 2026-10-03 | global | Corte medido compatível com largura FV, profundidade e aba da laje pode ancorar mesma seção espacial; preservar score, fontes e conflitos. Rejeitar B/H de pilar incompatível; altura FV pode vir de seção lateral coincidente e única. Bloquear preenchimento não revisado e DXF ausente. | docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md §14 | vigente |
| NIV-VIGA-LAJE-PAINEL-20261003 | 2026-10-03 | global | Mudança de nível da viga exige corte ou transição de hatch/preenchimento; degrau de laje secciona lateral mas conserva referência da viga quando não há mudança comprovada, com painel superior para diferença. | docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md §13 | vigente |


| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| NIV-PADRAO-EXCECAO-20261003 | 2026-10-03 | global | Topo da viga no nível principal da laje ou base de saída do pavimento na ausência de laje; aplicar padrão quando não houver indicação diferente. Exceções por hatch/corte prevalecem. Lajes/vigas definem seus níveis; pilares acompanham contatos. Interpretação de vigas em níveis diferentes por hatch/corte pendente de treino com futuros exemplos reais. | Dono, resposta explícita nesta conversa; manual de níveis, seção Referência padrão e exceções explícitas | vigente; integração dinâmica e QA do motor precisam ser verificados |

### CORTE-CAUDA-LOCALIZACAO-20261003 — cortes interpretados no estrutural

O dono pediu centralizar os cortes nos respectivos segmentos de viga, evitando pilares e sobreposição. O limiar inicial de cauda maior que 80 cm foi substituído nesta conversa pelo orçamento de 50 cm de desenho total (CORTE-COMPRESSAO-50-FINAL-20261005 abaixo). Região com lajes sem compressão, cota física correta e símbolo distinto da inversão permanecem obrigatórios. Não autoriza inventar lajes, níveis ou dimensões ausentes. Implementação inicial e limites de QA: `scripts/arete/relatorios/20261003_cut_slab_contact_placement/RELATORIO.md`; decisão final: `docs/CONHECIMENTO/CONSOLIDACAO-CORTES-INVERTIDAS-20261005.md`.

### FV-DECIMAL-CHANFRO-20261003 — comprimentos e continuidade SA→N3

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| FV-DECIMAL-CHANFRO-20261003 | 2026-10-03 | global FV | Comprimentos em campos e cotas N3 com uma casa decimal e vírgula; preservar precisão geométrica e reproduzir chanfros do contorno SA efetivo, sem confundir ponta convexa e dobra em L. | Dono nesta conversa; docs/SA-ANALISE/CLASSES/FV.md, Apresentação decimal e ponta chanfrada | vigente; validado V306 e testes rotacionados |

O dono exige comprimentos com uma casa decimal nos campos e no desenho N3
(417,98 → 418,0; 417,88 → 417,9), além do reconhecimento e reprodução dos
chanfros do SA. A precisão geométrica/persistida permanece intacta: arredondar
somente a apresentação. Implementação dinâmica sem nomes de vigas fixos;
quadrilátero chanfrado é distinto de dobra em L. Fonte canônica:
`docs/SA-ANALISE/CLASSES/FV.md`, Apresentação decimal e ponta chanfrada.


### Harmonia e transparência da confiança — NIV-HARMONIA-GATES-20261003

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| NIV-HARMONIA-GATES-20261003 | 2026-10-03 | global LAJ/FV/LV/PIL | Cruzar fontes e cortes LV por região/segmento/face, com gates de origem, associação, interpretação, exceções e concordância; evitar confirmação circular e porcentagens exageradas. | Dono, pedido de planejamento e aprovação do plano nesta conversa; manual integrado de níveis | plano aprovado; implementação nova delegada, não certificada por este registro |
| NIV-CONFIANCA-EXPLICADA-20261003 | 2026-10-03 | portal/QA | Mostrar percentual com explicação na ficha: fontes, cálculo, confirmações independentes, limitações e gates por unidade. | Dono, escolha explícita “% com explicação” na pergunta desta conversa | requisito aprovado; conferir implementação e consumo |

O plano aprovado começa com regras determinísticas e suporte reproduzível, sem bônus arbitrário nem aprendizado por reforço nesta etapa. Corte CAD e seção reconstruída são origens distintas. A mesma fonte atravessando classes não gera votos novos. Calibração probabilística futura precisa de validação independente. Regras anteriores do dono sobre padrão/exceções, degraus, ausência de laje e pilares continuam vigentes; detalhes canônicos no manual integrado.
| 2026-10-03 | PIL / NOVA / N5 | Conferir todas as faces existentes A–H por pilar e variante; C/D só têm grade com largura >40 cm, e H do T também. Agrupar peças idênticas preservando todos os nomes e a quantidade de ocorrências; bloquear N5 se faltar grade obrigatória. Continuações do índice imediatamente após o índice, deslocando e renumerando todas as demais folhas. | Dono, portal 13_PAV | Ativa |


### NIV-INVERTIDA-LOCAL-20261003 — referência padrão das invertidas

O dono confirmou: a viga invertida sobe altura da viga menos espessura da laje acima do nível da laje respectiva do trecho. Pediu aplicar como padrão das invertidas. Topo = nível da laje + (altura − espessura)/100; base = nível da laje − espessura/100. Referência local, sem impor base contínua entre trechos. Exceção explícita do corte prevalece; inversão precisa de evidência própria. Fonte: confirmação nesta conversa, trecho V330 71/L308. Regra canônica: docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md §4. Estado inicial histórico: implementação local. A integração SA e o destaque foram publicados e conferidos posteriormente; N3 teve gerações isoladas, sem certificação global. Estado final e pendências: docs/CONHECIMENTO/CONSOLIDACAO-CORTES-INVERTIDAS-20261005.md.

### TAMPA-INVERTIDA-ENCONTROS-20261004 — montagem entre faces

O dono confirmou na ficha V330_duvida_tampa_encontros.html: a tampa para nas faces das vigas incidentes, mesmo estando acima delas. Caso medido V330: P18→V301 = 311 cm e V301→VF301 = 183 cm, total 494 cm; excluir os 19 cm da V301 e os 14 cm da VF301 do comprimento de montagem. É regra de divisão das tampas, independente do contato vertical das laterais. Não alterar o concreto ou os níveis para forçar essa divisão. Fonte: resposta explícita nesta conversa em 2026-10-04. Conversão deve conservar o inventário dos encontros excluídos; não eliminar trechos sem evidência geométrica identificada.

### NIV-LAJE-CAMADAS-20261003 — nível de laje sem cota por camadas de confiança

O dono decidiu, para laje sem cota escrita:

1. As vizinhas através de viga que concordam provam o nível, se nenhuma contradiz.
2. Havendo contradição, verificam-se as visões de corte (as desenhadas e as interpretadas).
3. Persistindo a dúvida, vence o nível mais frequente entre vizinhas e segmentos que tocam a laje.

Muitas contradições baixam o percentual; muitas fontes concordantes sobem. A votação tem teto de 75%. A concordância só sobe entre origens independentes, e um segmento derivado da própria laje não vota ("para evitar confirmação por ciclicidade").

Sobre a asa: asa de corte ≠ h é erro de desenho humano, e o h declarado vence.

O consenso de vizinhas através de viga não é associação por proximidade. Não há hachura de laje neste desenho.

Complemento aprovado (v21): uma viga através da qual lajes com nível próprio já diferem é linha de degrau provada; ali o voto de continuidade não atravessa. Fonte: conversa de 03/10/2026. O "ali" é o trecho em que essas duas lajes se encaram, conforme o complemento de 04/10 abaixo. Regra canônica: docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md, seção NIV-LAJE-CAMADAS-20261003.

### NIV-DEGRAU-H-E-VOTO-20261004 — h sem corte não é degrau de nível; degrau que não toca não vota

O dono, no 14_PAV:

1. Trecho interno só com diferença de altura (h), sem cota nesse trecho e sem visão de corte nessa área indicando o nível, não é degrau de nível diferente. O nível permanece o da laje. A L415 fica 855,25. As vigas ao redor não mudam por causa desse trecho. O padrão de fundo do L410–L412 (rebaixo 855,22) não se aplica aqui.
2. A vizinha que tem nível vota com a região que encara o alvo. O degrau da L410 não toca a L417, então não retém nem troca esse voto: a L417 fica 855,25, o nível da L410. Uma diferença já provada mais adiante na mesma viga não segura esse voto quando o alvo ficaria sem nenhum. Se o alvo já tem outro voto, o contato fora do trecho continua retido, para não baixar uma continuidade unânime.

Um degrau de nível diferente continua exigindo cota no trecho ou visão de corte nessa área indicando o nível. L410–L412 permanecem nesse caso. Fonte: resposta do dono em 04/10/2026.

### N3-NOVA-ABCD-COTAS-FURACAO-20261004

O dono pediu trocar a altura da cadeia horizontal dos parafusos com a cota total da largura do painel no ABCD: cadeia acima, total abaixo. Medidas e furações permanecem iguais. Regra canônica: `docs/SEMANTICA-PILAR-NOVA.md`, seção 9.

### FV-T-MESMA-ALTURA-20261004 (D-90/FV)

| D-90/FV | 2026-10-04 | FV | **T de vigas de mesma altura: a viga que chega atravessa a outra e a outra é dividida nela.** Caso V303 × viga vertical 19/55 do P23 (13_PAV): a V303 não toca o P23 e segue reta; como o toco entre a V303 e o P23 é pequeno (10 cm), o fundo da viga que chega passa pela faixa da V303 (fica 29 cm) e a V303 para nas paredes dela (seg 5 fim / seg 6 início). Critério do dono: evitar segmento minúsculo. T com alturas diferentes segue "viga mais funda cruza" (FV.md §4) | dono, chat 04/10 com print do P23 | vigente — trava QA de chegada lateral implementada 04/10 (`qa_cad_gate.measure_beams`, não publicada) |
| D-91/LV | 2026-10-10 | LV | **Para e Passa têm laje igualmente, inclusive no trecho que passa pelo pilar.** Passar pelo pilar não impede laje encostando na face: o segmento Passa sobre o pilar deve declarar a laje que encosta, como qualquer outro. Casos 13_PAV: V309A B Passa seg 1 (L319) e V330 A Passa seg 4-A (L318), onde o SA declara nenhuma | dono, chat 10/10 (“mesmo no caso de passaram pelo pilar essa parte que passou tem laje também”) | vigente — o gate CAD LV (`measure_lateral_beams`, laje da face) já diverge nesses casos; correção do SA pendente |
| D-92/QA | 2026-10-10 | QA/Visão Corte | **O gate CAD pós-SA deve revisar também as Visões Corte, originais e interpretadas,** como um gate de níveis e dimensões das lajes e de cada segmento de viga, incluindo degraus de laje e de viga. Divergência na Visão Corte indica erro de nível, que é grave | dono, chat 10/10 (“o gate-pós-sa poderia revisar também os visão corte? é fundamental”; “visão cortes originais e visão cortes interpretados, incluindo degraus de lajes ou de vigas”) | implementado 10/10 (classe VC do gate, `qa_cad_gate_cortes.py`) — QA-GATE-MECANISMOS-E-EVOLUCAO.md §5 |

### FV-NORMAL-CRUZA-INVERTIDA-FACE-B-20261004

O dono determinou que V301 SEG 16, normal para baixo, atravesse a faixa da V330 invertida e chegue à parede direita B, como no DXF, em vez de parar em A. Ambas as paredes estruturais chegam a B; o fundo está abaixo da base da invertida. Aplicar por níveis absolutos e cobertura confirmada, conservando geometrias humanas, IDs e quantidade. A chegada a B vale para este encontro com P49, cujo contorno em planta termina na mesma face. Fonte: comentário do dono em SA/fundo, 04/10/2026. Regra canônica: docs/SA-ANALISE/CLASSES/FV.md, seção 1.

### FV-UNIAO-SOB-INVERTIDA-20261004

O dono determinou que VF301 fundos 8 e 9 sejam um único segmento: a V330
invertida não deve ser considerada colisão para o fundo normal que passa abaixo.
Aplicar dinamicamente pela geometria e níveis, sem regra por nome de viga.
Conferência do DXF: total 405,5 cm incluindo os 19 cm da travessia. Regra
canônica: `docs/SA-ANALISE/CLASSES/FV.md`, seção Fundo normal contínuo sob invertida.


### LV-INVERTIDAS-DESTAQUE-COLISAO-20261004

O dono pediu vermelho/branco nas laterais invertidas e continuidade das laterais normais quando os painéis ocupam níveis diferentes. Implementação usa geometria e intervalos verticais locais; a laje comum não cria uma colisão de painel. Pilares reais permanecem obstáculos. V301 encontra P49; VF301 Passa une a travessia livre. Contrato e evidências em docs/SA-ANALISE/CLASSES/LV.md e scripts/arete/relatorios/20261004_lv_inverted_crossings/RELATORIO.md.


### LV-INVERTIDAS-CORES-SOLIDAS-20261004

Vermelho/branco significa alternar cores sólidas entre segmentos de laterais invertidas, como as demais laterais. Não usar contorno listrado ou tracejado. Partições locais de um mesmo segmento mantêm a mesma cor.


### FORMASCIA-PL-CIMA-APROVADO-20261004

O dono validou a visão cima Formascia/MOLDE_1 dos pilares: retangular v01, U/T v01 e L corrigido v02. O L corrigido distingue hachuras de sarrafo vermelhas de chapas verdes, apesar da camada compartilhada da referência. Aprovação do desenho experimental; integração N3/N5 e validação publicada pendentes. Pediu em seguida as vistas ABCD, ainda em revisão. Regra e evidências: `docs/PADRAO-FORMASCIA-PILARES.md`.

### FORMASCIA-PL-NIVEIS-CABECALHO-20261004

O dono determinou que os marcadores de nível Formascia exibam o nome real do pavimento, não “chegada/saída”, e que as cores das setas reproduzam o original. O cabeçalho branco acima das vistas (PD e níveis) é exclusivo do Modo Nova e deve ser omitido em Formascia. Nomes individuais das faces permanecem. Não inferir nomes de pavimentos ausentes nem tratar esta determinação parcial como aprovação de todo ABCD. Regra e fonte: `docs/PADRAO-FORMASCIA-PILARES.md`, seção “Convenções determinadas pelo dono em 2026-10-04”. Integração e validação publicada pendentes.


### LV-V330-SEGMENTOS-LOGICOS-20261004

O dono corrigiu a segmentação: V330 deve ter três laterais A (71, 120 antes e depois do degrau) e duas B (120 e 71). Só A possui degrau. A invertida acima da laje não deve ser dividida pelas vigas normais V301/VF301 abaixo, quando não há colisão vertical. Aplicar em Para e Passa dinamicamente por geometria, níveis e cobertura confirmada, sem exceção por nome. Preservar aberturas reais dos pilares e perfis locais do N3. Destaque sólido vermelho/branco alterna por segmento lógico.

### LV-V330-LIMITE-71-120-20261004

O dono apontou que a linha de mudança para 71 está acima da divisão mostrada. Usar a linha transversal real do desenho como referência de mudança de altura; não usar ponto médio entre rótulos quando existe divisor estrutural medido. V330: limite Y=3095,038, faixa 71 com 112 cm, sem mudar a quantidade lógica 3A/2B. Regra dinâmica e evidência em docs/SA-ANALISE/CLASSES/LV.md.

## FORMASCIA-PL-FOLGA-CD30-TRIANGULOS-20261004

Decisão direta do dono: grades usam triângulos com a mesma proporção e tamanho dos originais; vistas ABCD incluem a nuvem de 2 cm FOLGA; C/D com largura >= 30 cm usam somente sarrafos horizontais nas extremidades, em MLINE. O limite de 30 cm é inclusivo. Não aplicar a outros modos/classes.

Fonte canônica: docs/PADRAO-FORMASCIA-PILARES.md, seção Folga ABCD, limite C/D e reforços das grades. Experimentos: ABCD v06 (P1 C/D 19 e variação demonstrativa C/D 40) e grades v02. Regras determinadas; revisão visual dos novos exemplos pendente, sem integração/publicação.

### FORMASCIA-PL-GRADES-TOPO-DISTRIBUICAO-20261004

O dono pediu horizontal no topo das grades, exceto uma ponta única isolada na extremidade, e configuração da distribuição observada. Medição de 40 conjuntos no original: faces inferiores regulares a 50/120/180 cm acima da madeira da base; espessura 10 cm; topo calculado pela altura real do patamar. Configuração das posições salva na VPS apenas em MOLDE_1/PL (revisão 4), demais perfis preservados. Regra dinâmica de topo ainda experimental, sem integração ao motor. Ponta isolada interna de P1.B em consulta. Fonte e evidências: docs/PADRAO-FORMASCIA-PILARES.md, seção Grades: distribuição e fechamento superior.

### FORMASCIA-PL-TODOS-EXPERIMENTOS-APROVADOS-20261004

O dono aprovou todos os pilares Formascia após visualizar a grade v06 sem degrau e triângulos com contorno branco/hatch cinza. Aprovação do conjunto experimental; integração e validação publicada N3/N5 permanecem pendentes. Solicitou passar às lajes Formascia. Fonte: docs/PADRAO-FORMASCIA-PILARES.md, seção Aprovação completa dos experimentos.

### FORMASCIA-LJ-LINHAS-VERDES-APROVADO-20261005

O dono aprovou a proposta v01 das lajes Formascia: contorno e divisões de painéis verdes ACI 3, geometria e demais elementos preservados. Pediu passar aos fundos de viga. Aprovação experimental; integração/configuração publicada e validação N3/N5 pendentes. Fonte: docs/PADRAO-FORMASCIA-LAJES.md.


### LV-CHEGADA-REGENERACAO-DATA-20261004

O dono confirmou que V301 A16/B1 deve atravessar a invertida até sua face B e que VF301 removida para teste deve reaparecer numa nova análise SA. Mostrar data/hora da última geração concluída por classe, pavimento e obra junto ao motor. Implementação dinâmica com comparação vertical e faces medidas; restauração somente de segmentos presentes no novo snapshot válido. Canônico: docs/SA-ANALISE/CLASSES/LV.md, seção LV: chegada à face B e regeneração SA.

### LV-VF301-UNIAO-AB-INVERTIDA-20261005

O dono determinou que as laterais do topo da VF301 atravessem a invertida sem divisão: A8+A9 devem ser A8 único, B1+B2 devem ser B1 inteiro. Regra geral de continuidade por níveis pareados e travessia comprovada, aplicada em Para/Passa. Preservar degraus reais e informações locais de nível. Canônico: docs/SA-ANALISE/CLASSES/LV.md, seção VF301: continuidade lógica e datum pareado.

### Fechamento cortes/invertidas — decisões finais indexáveis (05/10/2026)

As linhas abaixo consolidam determinações anteriores desta conversa, sem criar aprovação global de engenharia.

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| CORTE-COMPRESSAO-50-FINAL-20261005 | 2026-10-05 | global LV/FV | Substitui limiar de 80 cm: desenho acima de 50 cm comprime só cauda reta para total 50 cm, preservando lajes e cotas físicas; texto no tamanho anterior, título com (largura/altura); interrupção retangular COMP./COMP. MAX distinta do símbolo invertido. Região com lajes maior que orçamento não deve ser deformada. | `docs/CONHECIMENTO/CONSOLIDACAO-CORTES-INVERTIDAS-20261005.md`; decisão final do dono nesta conversa | vigente; código conferido, limite de sobreposição global documentado |
| CORTE-COBERTURA-FUNDO-20261005 | 2026-10-05 | global FV/LV | Destaque SA cobre cada segmento de fundo, inclusive repetições; corte original suficiente dispensa interpretado. Deduplicação de fabricação somente N3; inventário visual não apaga cobertura física. | `docs/CONHECIMENTO/CONSOLIDACAO-CORTES-INVERTIDAS-20261005.md`; dono nesta conversa | vigente; cobertura total atual requer auditoria por intervalo |
| INVERTIDA-LOCAL-CONSOLIDADA-20261005 | 2026-10-05 | global LV/FV | Base = nível local da laje menos espessura; topo = nível local mais altura menos espessura. Exceção explícita prevalece. Tampa superior LISO sem sarrafo; divisão de montagem entre faces não cria mudança de seção estrutural. | `docs/CONHECIMENTO/CONSOLIDACAO-CORTES-INVERTIDAS-20261005.md`; dono nesta conversa | SA publicado; N3 isolado validado, certificação global pendente |
| INVERTIDA-DESTAQUE-SEGMENTOS-20261005 | 2026-10-05 | global LV/FV | Vermelho/branco sólido alterna segmentos lógicos de laterais invertidas, sem listras; tampas vermelhas com legenda. V330 3A/2B e duas alturas 120/71; limite transversal medido prevalece sobre midpoint entre textos. | `docs/SA-ANALISE/CLASSES/LV.md`; dono nesta conversa | publicado e conferido |
| LV-VF301-CONTINUIDADE-FINAL-20261005 | 2026-10-05 | global LV/FV | Cruzamento sem colisão vertical comprovada permite continuidade; VF301 A8+A9→A8 e B1+B2→B1 Para/Passa. Diferença escalar estimada não impede datum pareado contínuo; preservar níveis locais, UIDs, pilares, degraus e níveis explícitos. | `docs/SA-ANALISE/CLASSES/LV.md`; `scripts/arete/relatorios/20261004_lv_regeneration/RELATORIO-VF301.md` | 51 testes; SA regenerado 05/10/2026 10:18:54 Brasília; N3 final não regenerado |
| SA-REGENERACAO-DATA-GRANULAR-20261005 | 2026-10-05 | portal LV/FV | Geração válida recupera removidos apenas do escopo regenerado preservando manuais; data da última conclusão por obra/pavimento/classe/motor SA/N3/N5, excluindo falhas e item isolado. | `docs/SA-ANALISE/CLASSES/LV.md`; dono nesta conversa | publicado e conferido; SA não equivale a N3 |

### LV-NOVA-AB-PILAR-E-EXTREMIDADES-20261005
Correção vigente do dono: nos AB sarrafeados, abertura de pilar não recebe montantes verdes de 3,5 cm; somente fechar as paredes dos sarrafos horizontais interrompidos pela abertura. Nos gradeados, os meios pontaletes externos à abertura sobem até 2,2 cm abaixo do topo, encostando no sarrafo superior de 2,2 cm. Em ambos os tipos, a borda interior laranja do sarrafo vertical de 7 cm nas extremidades deve ser uma linha reta contínua do fundo ao topo (limitada pelo vazio quando há abertura de viga na própria ponta). Travessa superior da abertura de pilar preservada. Experimentos dual_v14: 12 DXFs sintéticos com auditoria sem erros; renders lidos. Ainda não integrado ao motor nem publicado. Esta decisão substitui a regra v10 que incluía meios pontaletes nas aberturas de pilar sarrafeadas e limitava os dos gradeados a 7 cm abaixo do topo.

### LV-NOVA-AB-TRAVESSAS-E-ABERTURAS-20261005
Correção vigente: sarrafo de 2,2 cm somente no topo dos AB gradeados, terminando nos montantes de 7 cm das extremidades; não atravessar esses montantes até a parede externa. Não existe essa travessa de 2,2 cm no topo dos sarrafeados nem no fundo dos gradeados. Travessas locais de aberturas gradeadas aprovadas permanecem. Em abertura de viga sarrafeada, jambas e travessa inferior têm 7 cm; ambas paredes da jamba são completas, descendo 7 cm abaixo da abertura com fechamento inferior; a travessa inferior nasce desse encontro. Experimentos dual_v15: 12 DXFs sintéticos auditados; dimensões, hachuras, painéis, textos e meios pontaletes gradeados preservados por comparação de entidades. Renders examinados; integração ao motor e VPS pendente. Substitui as regras anteriores de travessa 2,2 no topo sarrafeado e fundo gradeado.


### CORTE-LOCAL-DEGRAU-DATUM-CORES-20261005

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| CORTE-LOCAL-DEGRAU-DATUM-CORES-20261005 | 2026-10-05 | global LV/FV | Cortes no intervalo local sem setinhas; perfil próprio para degrau e altura distinta; original dispensa só equivalente. Azul claro alta confiança, laranja revisar, vermelho invertida. Datum da viga separado do nível regional da laje e ancorado em evidência original única. | `docs/CONHECIMENTO/CONSOLIDACAO-CORTES-INVERTIDAS-20261005.md` | publicado SA; VF202 e carregamento frio permanecem em revisão |

Decisão final do dono: sem setinhas; mesmo em espaço pequeno, desenhar o corte interpretado no segmento local. Cada mudança de altura ou degrau exige perfil próprio, inclusive 71 invertido onde outro original expressa 120. Original dispensa apenas perfil equivalente no mesmo fundo. Interpretados: azul claro para alta confiança, laranja para dúvida, vermelho para invertida, com legenda explícita. Laje rebaixada não deve aparecer alinhada ao topo da viga: distinguir referências verticais e usar evidência cotada dos originais; não inventar datum ausente. Fonte: `docs/CONHECIMENTO/CONSOLIDACAO-CORTES-INVERTIDAS-20261005.md`, seção Revisão final dos destaques. Publicado em SA; 99 testes; VF202 sem datum original segue em revisão; primeira leitura fria do viewer ainda lenta.

### LV-NOVA-AB-CONTAGEM-PONTALETES-20261005
Texto de pontaletes somente em painéis AB gradeados: quantidade = arredondamento ao inteiro mais próximo de (comprimento do painel menos extensão das aberturas dentro desse painel) / 30. Exemplos do dono: 244 cm → 8 pontaletes; 122 → 4; 145 → 5; painel 244 com abertura 40 → comprimento útil 204 → 7. Descontar a interseção de cada abertura com o painel respectivo, unindo intervalos sobrepostos para evitar desconto duplicado. Não usar texto fixo 8 1/2pont. Texto individual por painel; sem indicação nos sarrafeados. Experimentos dual_v16: 12 DXFs auditados e demais entidades preservadas; integração ao motor/VPS pendente. Convenção para empate exato .5 adotada no experimento: arredondar para cima.

### LV-NOVA-AB-MEIO-PONTALETE-ABERTURA-20261005
Na parede da abertura AB gradeada, o meio pontalete verde de 3,5 cm começa abaixo do sarrafo superior de 2,2 cm e segue para baixo; seu fechamento superior encosta na face inferior desse sarrafo, sem atravessar a travessa. Corrigidos apenas endpoints/fechamentos das jambas gradeadas em dual_v17; demais entidades e textos de contagem v16 preservados. Doze DXFs experimentais auditados, render das aberturas lido; integração ao motor/VPS pendente.

### LV-NOVA-AB-INTERSECCOES-SOB-ABERTURA-20261005
A regra de não atravessar sarrafo de 2,2 cm também vale para meios pontaletes sob a abertura gradeada, inclusive nas interseções/emendas de painéis e segmentos. A ponta e seu fechamento superior devem encostar na face inferior da travessa local de 2,2 cm. Experimento dual_v18: linhas verdes desses encontros corrigidas; outras entidades preservadas e 12 DXFs auditados. Render examinado; motor/VPS pendentes.

### LV-NOVA-AB-PAINEL-MINIMO-60-20261005
Decisão do dono para ambos os AB: lateral até 244 cm sempre usa um painel único, podendo ter menos de 60 cm. Nas laterais acima de 244 cm, não admitir painel inferior a 60 cm. Quando a sobra após a divisão em 244 for menor que 60, substituir o painel anterior de 244 por 122 e somar os outros 122 à sobra no painel final. Ex.: 260 → 122+138; 300 → 122+178; 500 → 244+122+134. Sobra exata de 60 permanece: 304 → 244+60. Recalcular paredes, cotas, meios pontaletes das emendas e textos de contagem conforme comprimento útil de cada painel. Experimentos dual_v19: 12 DXFs auditados, cotas confrontadas com a divisão calculada. Fórmula verificada em 30000 comprimentos de 0,1 a 3000 cm: soma preservada, máximo 244, mínimo 60 exceto painel único. Não integrado ao motor/VPS.

### LV-NOVA-AB-CONTINUACAO-APOS-ABERTURA-20261005
Somente nos sarrafeados: quando a abertura direita chega ao fim de um segmento e há segmento seguinte encostado, esse seguinte recebe sarrafo vertical de 7 cm à esquerda, de fundo a topo. Seus horizontais começam na face interna desse montante. É exceção à ausência de montante em emenda comum sarrafeada; não aplicar às emendas sem abertura nem aos gradeados. Experimento dual_v20: AB04 corrigido, demais 11 DXFs preservados byte a byte em relação a v19; entidades fora das linhas afetadas preservadas, 12 auditorias sem erro e render examinado. Integração ao motor/VPS pendente.

### LV-NOVA-DESIGN-APROVADO-INTEGRACAO-20261005

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| LV-NOVA-DESIGN-APROVADO-INTEGRACAO-20261005 | 2026-10-05 | NOVA LV Para/Passa | AB dual_v20, corte gradeado dual_v11 e sarrafeado dual_v13 aprovados. Duas montagens conservadas; SA fornece dimensões locais. Padrão visual comum, configurações independentes. | `docs/PADRAO-NOVA-LATERAIS-APROVADO.md` | integrado e validado na VPS; perfil de configuração formalizado em 06/10 |
| LV-NOVA-AB-DIVISAO-FINAL-20261005 | 2026-10-05 | NOVA LV AB ambas | Até 244 cm painel único, inclusive menor que 60. Acima disso nenhum menor que 60: sobra curta redistribuída em 122 + restante; 260=122+138, 300=122+178, 500=244+122+134. | `docs/PADRAO-NOVA-LATERAIS-APROVADO.md` | aprovado |
| LV-NOVA-AB-EMENDAS-FINAL-20261005 | 2026-10-05 | NOVA LV AB | Sarrafeados sem montante nas emendas comuns; após abertura direita no fim do segmento, continuação recebe vertical esquerda 7. Gradeados têm meios pontaletes verdes 3,5 nas emendas. | `docs/PADRAO-NOVA-LATERAIS-APROVADO.md` | aprovado; substitui generalização anterior |
| LV-NOVA-AB-TRAVESSAS-FINAL-20261005 | 2026-10-05 | NOVA LV AB | Travessa 2,2 laranja somente topo gradeado, sem atravessar montante externo 7; sem travessa global de fundo nem topo sarrafeado. Pilar conserva superior 7; meio pontalete externo ao vazio só gradeado. | `docs/PADRAO-NOVA-LATERAIS-APROVADO.md` | aprovado |
| LV-NOVA-AB-PONTALETES-FINAL-20261005 | 2026-10-05 | NOVA LV gradeado | Contagem por painel: inteiro mais próximo de comprimento útil /30, empate .5 para cima, descontando união das aberturas. Sem texto nos sarrafeados. | `docs/PADRAO-NOVA-LATERAIS-APROVADO.md` | aprovado |
| LV-NOVA-CORTE-FERRAGENS-FINAL-20261005 | 2026-10-05 | NOVA LV corte | Gradeado mantém ferragens inferiores e centrais sem sarrafos espúrios nas pontas centrais. Sarrafeado conserva garfos e não tem parafusos nem madeiras remanescentes deles. Todas as lajes locais; C elevada 1 cm; guia cinza pontilhada. | `docs/PADRAO-NOVA-LATERAIS-APROVADO.md` | aprovado |

O dono aprovou explicitamente todo o design experimental das laterais de viga NOVA, AB e Visão Corte, gradeadas e sarrafeadas, compartilhado visualmente por Para/Passa com configurações independentes. Referência final AB: dual_v20, seis casos por montagem. Corte gradeado: dual_v11, cinco casos. Corte sarrafeado: dual_v13, cinco casos. Todas as correções posteriores substituem as convenções anteriores no mesmo ponto; em especial a ausência de montante em emendas sarrafeadas admite a exceção da continuação após abertura. O padrão foi integrado ao N3 dinâmico de origem SA, publicado e conferido no N5 NOVA, incluindo o encaixe V301/V304. A rodada operacional integral permanece uma verificação de produção, não uma reabertura da aprovação de design. Plano e critérios: `docs/PLANO-LV-NOVA-SA-N3-N5-20261005.md`.

### NOVA-LV-CONFIGURACAO-APROVADA-20261006

Os perfis **Modo Nova / Laterais Para** e **Modo Nova / Laterais Passa** são independentes e compartilham o mesmo desenho aprovado. Ambos mantêm ativos os componentes AB e Visão Corte, textos, cotas, metal e hachuras de lajes, aberturas e painéis. As cores, layers, tipos de linha e estilos DIMENSION permanecem preservados pelo motor para reproduzir as referências, sem uma conversão genérica que descaracterize o DXF. As anotações humanas de cada perfil apontam a especificação canônica e resumem as regras obrigatórias. As referências gradeada e sarrafeada são cadastradas nas duas classes; moldura e índice próprios já permanecem separados por comportamento. Fonte: aprovação explícita do dono nesta conversa em 06/10/2026; `docs/PADRAO-NOVA-LATERAIS-APROVADO.md`. Estado: configuração registrada no portal; gerações futuras usam o padrão N3/N5 publicado.


### Datum VF202 confirmado pelo dono (05/10/2026)

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| VF202-DATUM-CONTINUIDADE-20261005 | 2026-10-05 | VF202 deve ter a laje no mesmo nível do VC3 da VF203: 852,12 m, 7 cm abaixo do topo 852,19 m. Usar referência medida da vizinha diretamente conectada apenas com largura, espessura e nível locais compatíveis, referência única e sem original próprio prevalecente. | Confirmação explícita do dono e conferência dos contatos; preservar inventário físico de colisões. | `docs/CONHECIMENTO/CONSOLIDACAO-CORTES-INVERTIDAS-20261005.md`; `scripts/arete/relatorios/20261005_vf202_datum/RELATORIO.md` | Implementado e conferido no servidor; rebaixo 7 cm |


## 2026-10-05 — Fundos Formascia aprovados e integração autorizada

O dono aprovou a v06 dos fundos: letras A/B, montantes diagonais no chanfro, conjuntos nas extremidades L, aberturas nas esquinas, horizontal extra curto de 30 cm e vertical prolongado 7 cm para encaixe. Vazio central deve resultar em dois segmentos complementares com recortes em L. Autorizou integrar/publicar PL, LJ e FV no N3/N5 da VPS, atualizar as configurações dessas classes e gerar pelo portal para conferir molduras, índices e qualidade. Laterais Para/Passa permanecem pendentes. A aprovação do design não substitui validação publicada. Fonte: `docs/PADRAO-FORMASCIA-FUNDOS.md`.


### Cortes de degrau sem original (05/10/2026)

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| CORTE-DEGRAU-AMARELO-20261005 | 2026-10-05; corrigido 2026-10-06 | Desenhar o próprio corte interpretado de degrau de laje sem original, em amarelo, no limite interno real e com níveis/espessuras regionais confirmados. Legenda: Visão corte degrau de laje. Não basta colorir o corte de viga próximo; este conserva azul/laranja por confiança ou vermelho para invertida. L322/L323 sem original, L309/L312 com original. | Corrigir ausência do desenho interpretado da transição e preservar classificação local. | `docs/CONHECIMENTO/CONSOLIDACAO-CORTES-INVERTIDAS-20261005.md` | Regra corrigida pelo dono; validação nesta rodada |
## 2026-10-06 — Encaixe dos parafusos CIMA Formascia

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| FORMASCIA-PL-PARAFUSOS-CONTATO-20261006 | 2026-10-06 | Na visão CIMA dos pilares Formascia, as pontas dos parafusos devem encostar no perfil metálico. Calcular o contato a partir dos perfis reais perpendiculares à haste, incluindo parafusos horizontais e verticais; preservar os desenhos nativos e as cores aprovadas. | Eliminar o afastamento visível entre ponta e perfil. | Instrução direta do dono; docs/PADRAO-FORMASCIA-PILARES.md | Regra confirmada; motor publicado, 314 grupos verificados nos DXFs publicados |


## Formascia PL — montagem v04 (2026-10-06)

FORMASCIA-PL-FOLHA-V04-20261006: aprovação explícita no chat seguida de pedido de integração N3/N5. CIMA 2× centralizado no topo e desenhado para baixo; ABCD e grades 1×, baixados 30 unidades em relação à v03, ancorados pela base e desenhados para cima. Linhas de nível até as paredes da moldura, também nas grades; grades lado a lado alinhadas no nível. Fonte: pedido do dono «ta agora garanta que n3 e n5 gerem assim». Escopo apenas MOLDE_1/PL; sem rodada completa N3/N5 nesta etapa. Detalhes em PADRAO-FORMASCIA-PILARES.md.

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| FORMASCIA-PL-FOLHA-V04-20261006 | 2026-10-06 | CIMA 2× no topo centralizado; ABCD e grades 1× pela base, margem inferior 55 e superior CIMA 85. Níveis de parede a parede; grades lado a lado alinhadas. | Aprovação da folha v04 e autorização de integração N3/N5. | Chat do dono; docs/PADRAO-FORMASCIA-PILARES.md | Design aprovado; validação granular de integração, sem rodada completa |

## 2026-10-06 — Textos e sarrafos dos pilares Formascia

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| FORMASCIA-PL-COR-ROTULOS-20261006 | 2026-10-06 | Retirar títulos técnicos P1 — Para/Passa e legendas CIMA/ABCD/GRADES das células. Sarrafos de topo e abertura ABCD cinza explícito em MLINE própria; preservar nomes de faces, índice e demais cores aprovadas. | AutoCAD mostrou preenchimento vermelho herdado da camada N5. | Solicitação e imagem do dono neste chat. | Aprovado pelo dono |

## 2026-10-06 — Painel superior da laje Formascia

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| FORMASCIA-PL-PAINEL-LAJE-20261006 | 2026-10-06 | Contar e numerar separadamente o painel acima da laje (7 cm no exemplo, altura dinâmica pelo SA). Vazios AR-CONC com Pattern Scale 0,1. | Faixa superior sem número e ajuste visual da hachura solicitado. | Dono neste chat, corrigindo a altura inicial de 3 para 7 cm. | Aprovado pelo dono |

## 2026-10-06 — Coerência do hatch Formascia

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| FORMASCIA-PL-HATCH-COERENCIA-20261006 | 2026-10-06 | Manter AR-CONC 0,1 coerente entre propriedade e linhas do padrão nos vazios das folhas e unificado N5. | Dono relatou mudança do padrão somente ao selecionar/editar; redução indevida na transformação confirmada no arquivo. | Dono e investigação nativa AutoCAD neste chat. | Correção solicitada |

## 2026-10-06 — Cota total das grades Formascia

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| FORMASCIA-PL-GRADES-TOTAL-20261006 | 2026-10-06 | Cota total somente à direita da última grade; omitir cota do sarrafo quando repetir o total. | Completar dimensionamento sem redundância. | Pedido explícito do dono no chat. | Solicitado |

## 2026-10-06 — Cadeia vertical Formascia

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| FORMASCIA-PL-GRADES-CADEIA-20261006 | 2026-10-06 | Cotas verticais dos horizontais devem acompanhar os sarrafos efetivamente desenhados, incluindo fechamento superior. | Cadeia antiga divergia da distribuição aprovada. | Imagem e apontamento do dono no chat. | Correção solicitada |

## 2026-10-06 — NOVA laterais: conjuntos e cotas

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| NOVA-LV-CONTIGUOS-20261006 | 2026-10-06 | Alinhar cotas granulares; total único por conjunto encostado; nome apenas inicial e Cont. VIGA.A/B nas continuações; unir vazios e contornos rosinha; preencher espaço N5 em limites reais de painel. | Legibilidade, continuidade e aproveitamento de folhas. | Pedido explícito do dono neste chat. | Implementação em validação V301/V304 |

| NOVA-LV-CORTE-UNICO-20261006 | 2026-10-06 | NOVA/LV N5: visual V301/V304 aprovado; não repetir cortes nem como contexto dentro da mesma viga. Correção explícita: NUNCA unir cortes de vigas diferentes, mesmo com geometria e anotações idênticas. Cada viga mantém seus cortes e vínculos próprios. | PADRAO-NOVA-LATERAIS-APROVADO.md | Integração e validação granular |
| NOVA-LV-ENCAIXE-CORTES-20261006 | 2026-10-06 | Preencher primeira linha de cada folha com máximo de cortes pendentes da viga; não esperar associação aos AB. Acabados os cortes, usar área inteira para AB. Próxima viga pode começar na área livre à direita se couber seu primeiro corte, com separador vertical ciano; senão nova folha. | PADRAO-NOVA-LATERAIS-APROVADO.md | Integração e validação granular |
## 2026-10-06 — Revisão manual dos destaques estruturais

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| CORTES-REVISAO-HUMANA-20261006 | 2026-10-06 | Cortes originais selecionáveis e editáveis. Cortes interpretados selecionáveis apenas para validar ou excluir. Validação é referência local de alta confiança de nível no SA; exclusão remove o destaque e sua referência humana. Toda edição/exclusão estrutural gera apontamento com desenho anterior e posterior, dados, autor, obra e pavimento. | Corrigir reconhecimento e conservar evidência para depuração. | Pedido explícito do dono neste chat. | Publicado; 38 testes; cliques visuais pendentes pela indisponibilidade do navegador de automação. |


## 2026-10-06 — Formascia fundos: folha compacta

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| FORMASCIA-FV-FOLHA-COMPACTA-20261006 | 2026-10-06 | Remover título interno acima dos fundos, manter nome normal do N3; iniciar no canto superior esquerdo e distribuir à direita até não caber, depois na linha inferior, com intervalos curtos e respeito à legenda/carimbo. | Aproveitamento da folha e eliminação de textos internos dos robôs. | Pedido explícito do dono neste chat; PADRAO-FORMASCIA-FUNDOS.md. | Integrado no compositor N5 da VPS e validado nos três DXFs N5 de V303/V308/V322: AutoCAD AUDIT zero; `20261006_formascia_fv_compacto_integracao/RELATORIO.md`. |

## 2026-10-07 — iNi: parafusos dos pilares especiais

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| INI-PL-ESPECIAIS-PARAFUSOS-20261007 | 2026-10-07 | Mesmo SA deve gerar quantidade e posicionamento de parafusos iguais aos do Nova na visão cima dos pilares especiais; conservar apresentação iNi. | O caminho antigo duplicava hastes de faces opostas e usava estações diferentes. | Pedido explícito de Thierry neste chat; PADRAO-INI-BASE-INICIAL.md. | Comparação P26/P27 Para/Passa: nove hastes com coordenadas idênticas; pontas também comparadas. Evidências em `20261007_ini_parafusos_especiais`. |


## 2026-10-07 — iNi: aprovação dos exemplos e afastamento corrigido

O dono aprovou os três exemplos anteriores («ta perfeito aprovado os 3») e corrigiu o afastamento do parafuso externo com perfil lateral, para espessura a partir de 40 cm, de 4,5 para **3,5 cm**. Portanto o primeiro furo interno do exemplo fica em **69 − 3,5 = 65,5 cm**. Abaixo de 40 cm conserva-se 1 cm. Manter equivalência CIMA/ABCD pelos eixos reais. Grades v05: pontas rebaixadas sem travessa de topo; completar horizontais intermediárias onde os montantes as suportam; preservar cotas de vão físico e remover fragmentos de borda. Fonte: correções/aprovação explícitas do dono neste chat; regra em PADRAO-INI-BASE-INICIAL.md. Estado: aprovação visual dos exemplos, integração destes ajustes ainda pendente. Novo exemplo em L solicitado para revisão, sem aprovação antecipada.

## 2026-10-07 — iNi: encontros C/D e alinhamento das cotas de grades

Pedido do dono: alinhar cotas dos vãos entre grades com as cotas totais de largura; retirar montante central de grades C/D de 30 cm, mantendo intermediários apenas acima de 30 cm; posicionar quadradinhos das grades do CIMA em L na faixa externa correta; garantir contato dos sarrafos com os painéis C/D no CIMA comum. Regras em PADRAO-INI-BASE-INICIAL.md. Experimentos corrigidos em `20261007_ini_encontros_v03`: dez contatos e quatro alinhamentos conferidos, cinco DXFs auditados no AutoCAD sem erros. Estado: proposta visual entregue, integração N3/N5 e aceite destes novos exemplos pendentes.


## 2026-10-07 — iNi pilares: aprovação final e produção N3

O dono aprovou os refinamentos finais e pediu que o N3 gere conforme combinado. Integração dos adaptadores nativos CIMA retangular/L, ABCD e grades publicada na VPS. Regras canônicas na seção «Aprovação final e integração N3 dos pilares» de PADRAO-INI-BASE-INICIAL.md. O serviço normal do portal gerou seis vistas de P1/P26; 19 vistas locais auditadas sem reparos, P26 CIMA/grades publicados com AutoCAD AUDIT zero. Gerador STOG e modos Nova/Formascia preservados; sem regeneração integral do pavimento. Evidência: `20261007_ini_pilares_aprovados_integracao`. Este estado substitui as pendências de integração N3 das revisões anteriores de pilares.


## 2026-10-07 — NIV-CONFIRMACAO-INDEPENDENTE-CICLICA

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| NIV-CONFIRMACAO-INDEPENDENTE-CICLICA | 2026-10-07 | LAJ/FV/LV/PIL, cortes interpretados e fichas SA cooperam iterativamente, confrontando a mesma grandeza/região/segmento/unidade/datum; cada confirmação exige origem independente e atual. Ciclos ou retransmissões da mesma marca CAD não aumentam suporte; divergências reais ficam explícitas, sem forçar igualdade. | Descobrir e conferir níveis sem fabricar certeza circular. | Pedido explícito do dono neste chat; INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md. | Auditoria reforçada e cache por rodada publicados; evidências em 20261007_sa_performance. Não é certificação integral dos itens. |

O dono pediu que leituras repetidas e classes se ajudem a descobrir e conferir os níveis, inclusive entre Visão de Cortes Interpretados e fichas SA por item. A cooperação pode ser iterativa, mas uma derivação circular não constitui evidência nova: cada confirmação deve chegar a uma origem independente, identificável no CAD ou em decisão humana com escopo. Reutilizar o mesmo fato em outra classe/rodada não aumenta seu suporte. Conferir mesma grandeza física, região/segmento, unidade e datum; diferenças legítimas de topo/fundo ou degrau não são conflito por mera diferença numérica. Divergências reais ficam explícitas, sem alterar números só para obter concordância. Fontes/revisões atuais devem ser verificadas antes de reutilizar resultados entre rodadas. Implementação e evidência: relatório `20261007_sa_performance`; não equivale a certificar todos os itens.


## 2026-10-07 — consolidação final INI/NOVA e documentação

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| INI-DESIGN-APROVADO-4CLASSES | 2026-10-07 | Pilares, laterais e fundos INI aprovados; lajes INI iguais ao NOVA, usando perfil NOVA/LJ. | Consolidar os ajustes finais por classe. | Aprovações explícitas neste chat; PADRAO-INI-APROVADO.md. | N3 integrado/publicado e testes granulares; paginação N5 PL ainda diverge da regra de nove células/três colunas. |
| LV-NOMES-FACES-INI-NOVA | 2026-10-07 | Primeiro segmento VIGA.A e VIGA.B; Cont. somente nas continuações da mesma face. Corte sarrafeado com fechamento 2,2 cm acima dos verticais A/B. | B não é continuação de A. | Pedido explícito e exemplos aprovados; PADROES-DESENHO-N3-N5.md. | Regras nos adaptadores; evidência 20261007_ini_lv_sarrafeadas. |
| INI-FV-BRANCO-APOIOS | 2026-10-07 | Painéis brancos; pressão vermelha tracejada; apoios cianos 6 cm exteriores. | Reproduzir o fundo original e afastar apoios mais 3 cm. | Aprovação explícita; PADRAO-INI-APROVADO.md. | Publicado; V301 granular real na VPS, 20261007_ini_fv_comparacao. |

O aceite final substitui pendências anteriores do desenho N3; não apaga o histórico nem certifica toda a produção N5. Correção posterior autorizada por “oque sao as pendencias, podemos fazer?”: nove células, especiais em três células, atlas de três colunas e agrupamento de conjuntos equivalentes de grades por face. Testes granulares local/VPS em `20261007_ini_pendencias`; a publicação depende de não haver motores ativos. A matriz canônica registra os limites, inclusive ausência de deduplicação de peças isoladas entre conjuntos diferentes.

## 2026-10-08 — falta de dados isolada por item

O dono determinou neste chat que um item sem dados não deve parar a produção dos demais: registrar motivo e identificação para avaliação posterior. No portal SA/N3/N5, pendências por item seguem no recibo e no log; N5 pode publicar os itens válidos com indicação explícita de resultado parcial. A cadeia continua as classes e pavimentos seguintes. Nenhum nível, dimensão ou desenho faltante é inventado. Falha de integridade da rodada ou de infraestrutura continua sendo erro. Uma classe inteiramente pendente não publica DXF vazio nem substitui uma publicação anterior. As verificações estritas continuam disponíveis para auditoria. Evidências: `scripts/arete/relatorios/20261008_item_pending/RELATORIO.md`.

### 2026-10-08 — Seleção de pavimento na cadeia completa
A cadeia SA → N3 → N5 da ficha da obra deve permitir escolher um pavimento ou todos, para testar um pavimento por vez. Triagem + Recortes permanece global. Seleção inválida não pode ampliar o escopo; a rodada congela os pavimentos escolhidos. Evidência: scripts/arete/relatorios/20261008_cadeia_pavimento/.

### 2026-10-08 — Pré-processamento antes do SA na cadeia completa
O dono determinou que a cadeia da ficha da obra execute Pré-processamento → SA → N3 → N5 para cada pavimento selecionado, após Triagem + Recortes. A revisão humana é opcional também no pré-processamento; não fabricar `validated=true`. Revisões das fontes e escopo permanecem congelados e verificados. Ausência de referência absoluta não deve impedir a coleta de segmentos e cortes; cotas sem prova continuam desconhecidas. Evidência de execução e desempenho: `scripts/arete/relatorios/20261008_tipo_fullpipeline/`.


### CORTE-REJEICAO-NOVA-GERACAO-20261008

Correção de política solicitada pelo dono: excluir um corte interpretado rejeita a ocorrência atual, preservando o apontamento com comentário, desenho anterior e contexto estrutural. Não é uma proibição permanente de interpretar aquela viga. A próxima publicação válida do pré-processamento ou SA de laterais/fundos do mesmo escopo permite repopular a interpretação, inclusive quando o perfil foi corrigido pelo motor. Apenas recarregar o viewer, gerar outra classe ou falhar no processamento não libera a rejeição. Uma exclusão feita durante uma rodada permanece vigente para evitar que o job em curso a desfaça.

O histórico local conserva a evidência rejeitada e o evento de auditoria. A nova ocorrência nunca recupera a antiga validação humana nem a confiança de nível atribuída por ela; requer nova revisão. Evidências CAD independentes continuam válidas. A regra também atende exclusões de teste antigas sem apagar seus apontamentos. Esta decisão substitui qualquer leitura anterior de exclusão permanente de cortes interpretados.

### LAJ-CONTORNO-HATCH-NOMES-20261008

O dono pediu melhorar as lajes de TIPO_TESTE: usar a área interna entre faces reais de vigas e pilares e conferir as classes em conjunto contra o CAD. Lajes não atravessam faces de vigas/pilares; cotas, hatch, cortes e limites internos de mudança de espessura/nível não são automaticamente apoios. Hatch listrado sinaliza atenção para possível degrau, nível ou espessura diferente, sem provar sozinho qual situação ocorreu. h= de cada região fica separado do principal. Quando não houver nomes escritos, gerar L1_TIPO_TESTE, L2_TIPO_TESTE etc., da esquerda para a direita e de cima para baixo, adaptando o sufixo ao pavimento. Regras gerais e evidência: docs/SA-ANALISE/CLASSES/LAJ.md e scripts/arete/relatorios/20261008_lajes_tipo_contexto/RELATORIO.md.

### LAJ-OBJETOS-NOMES-REV2-20261008

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| LAJ-OBJETOS-NOMES-REV2-20261008 | 2026-10-08 | Lajes sem rótulo recebem apenas L1, L2, L3, em filas esquerda-direita/cima-baixo; remover o pavimento do nome. Reconhecer visões de corte antes de recortar a laje, recuperar áreas ausentes e registrar novos objetos CAD na biblioteca global/RAG com evidência independente. | Cinco apontamentos do dono revelaram área ausente e cortes gráficos confundidos com pilares. | Pedido posterior neste chat e comentários 1–5 de TIPO_TESTE. | Substitui somente a regra anterior de sufixo; motor e evidência em 20261008_lajes_cortes_callouts. |

Aprendizado documentado não equivale a confirmação humana de todas as geometrias nem a selo RAG T1 por item. A biblioteca registra padrões comprovados e limites; estilos desconhecidos precisam de nova evidência e regressão.


### 08/10/2026 — fundos: paredes, apoios, cortes e cruzamentos sem divisória

Pedido do dono: corrigir VF3, VF4/VF1, V513, cauda de V514/P18, V524/V526 sobre cortes, V525/V508 e V504/V506/V507/P8; regra universal, sem nomes ou coordenadas no motor.

A faixa pertence ao intervalo axial das duas paredes junto ao rótulo; um par remoto não vence pela proximidade transversal. Fundos automáticos retangulares deslocados são reconstruídos nas paredes medidas. Apoio automático pode ser reassociado somente com identificação e dimensão independentes do DXF; manter decisões humanas. A cauda além de apoio exige duas paredes e chamada de seção compatível entrando nela, conservando o pilar.

Esclarecimento posterior do dono: visão de corte é anotação, nunca obstáculo físico. Não exclui área nem segmenta fundos, mesmo com contorno confirmado no DXF. Cruzamento ortogonal sem divisória pode trocar a ocupação para reduzir painéis, preservando área, alturas locais, apoios e geometrias humanas. Risco físico na divisória atual ou proposta veta a troca. Divisória física real permanece; símbolo de visão de corte não provoca divisão.

Validação e recibos: `scripts/arete/relatorios/20261008_fv_missing_crossings/`. Aprovação global G2-V e N3/N5 não são inferidas dos testes do SA.


### PIL-CONVENCAO-CIRCULAR-20261008

| ID | Data | Decisão | Motivo | Fonte | Status |
|---|---|---|---|---|---|
| PIL-CONVENCAO-CIRCULAR-20261008 | 2026-10-08 | Revisar associação de pilares em segunda passada usando convenções recorrentes e evidência independente; excluir geometrias comprovadas de outras classes, preservar formas minoritárias e reconhecer U completo. Manter circular no SA com medidas e contatos; ignorar N3/N5 circular até existir método próprio, sem bloquear outros itens. | Nove comentários humanos de TIPO_TESTE mostram confusão entre pilar, viga e corte; P12 é U e P21 circular está livre no bloco. | Pedido deste chat, comentários 1–9. | Motor e evidência em 20261008_pilares_associacao; não certifica toda a ficha nem estilos desconhecidos. |


### FV-CONTINUIDADE-SOB-VISAO-CORTE-20261008 — esclarecimento do dono

“não é sobre, é segmentação de fundos por culpa de visão corte não deve ocorrer”.
A visão de corte é anotação: não remover sua área dos fundos nem utilizá-la como
apoio, parede ou veto de união. Fundos continuam por baixo dela quando as paredes
físicas são contínuas. Preservar pilares, divisórias e mudanças físicas reais,
seções/níveis distintos e edição humana. Esta clarificação corrige a interpretação
de 08/10 que tratou o contorno de corte como sólido e reafirma FV-VISAO-CORTE-T-20261004.


### LV-VISAO-CORTE-NAO-SECCIONA-20261008

Visão de corte é anotação: seus traços transversais, diagonais, polilinhas e setas não delimitam banda nem seccionam lateral. Reconhecer a camada fonte antes de converter entidades em coordenadas sem semântica; excluir somente a entidade reconhecida, preservando linhas estruturais independentes mesmo quando coincidentes. Aplicar o mesmo filtro à leitura DXF de divisores usada pelo portal. Não mascarar uma região inteira em torno do símbolo: isso apagaria encontros reais de vigas/pilares.

Causa comprovada na Obra_TREINO_1/TIPO_TESTE: múltiplos divisores gráficos da visão de corte tornavam ambígua a busca e mantinham uma fronteira antiga. V501 tinha trecho falso de aproximadamente 102,44 cm. Depois do filtro, A Para/Passa passou de quatro para três segmentos; o encontro real com V523 foi preservado. Coordenadas observadas são evidência, nunca constantes do motor. Implementação: lv_beam_scene._line_segments/build_scene_runs e fv_inverted_crossings.structural_lines_from_dxf, com reconhecedor compartilhado cad_object_recognition.section_layer. Proveniência registra entidades_visao_corte_excluidas.

Contraprovas: divisor estrutural coincidente permanece; mudança real de altura permanece; polilinha fechada de corte não produz banda; orientações horizontal/vertical e translações têm regressão. Testes: test_lv_section_symbol_exclusion.py. Fonte torre_1.dxf SHA256 80b45ff3e024ebe037fe6e6e52829216120f006c55f6b60f79adb1df2dc65641. SA publicado em produção, recibo e comparação no relatório 20261008_lv_corte_seccionamento. Esta validação de interpretação não certifica N3/N5 nem estilos ainda não observados.


<!-- LV-PASSA-ENCONTRO-APOS-PILAR-20261008 -->
Decisão do dono (2026-10-08): Passa pode percorrer a parede do pilar, mas para ao encontrar uma viga de mesma profundidade; não a atravessa. Ver LV.md, seção "Passa: encontro depois de percorrer a parede do pilar".
| LV-LAJE-DEGRAU-VAZIO-20261008 | 2026-10-08 | Laterais de viga | Laje ou degrau para vazio também secciona a lateral Para/Passa, com trechos encostados e numerados; V519 SEG4-B deve separar vazio e laje/degrau. | docs/SA-ANALISE/CLASSES/LV.md |

| LV-CANTO-EXTERNO-20261008 | 2026-10-08 | Laterais de viga | Nos cantos em L, laterais externas completam a parede ate o canto externo. | docs/SA-ANALISE/CLASSES/LV.md |

| VC-TEXT-COTAS-20261008 | 2026-10-08 | Visão de cortes | Rotacionar títulos conforme o corte e cotar paredes acima e abaixo das lajes pela fonte. | docs/SA-ANALISE/CLASSES/LV.md |

| VC-COTAS-UTEIS-20261008 | 2026-10-08 | Visão de cortes | Não cotar extensão do símbolo de laje; cotar espessura das lajes, paredes e fundo da viga. | docs/SA-ANALISE/CLASSES/LV.md |

| VC-COTAS-PROXIMAS-20261008 | 2026-10-08 | Visão de cortes | Cotas de parede próximas da face física correspondente, independentes da extensão da laje. | docs/SA-ANALISE/CLASSES/LV.md |

| VC-TOTAL-EXTERNA-20261008 | 2026-10-08 | Visão de cortes | Cota total em linha externa, 4 cm além da linha da laje/granulares. | docs/SA-ANALISE/CLASSES/LV.md |

## ESTILO-INTEGRADO-20261008 — harmonização entre classes

| ID | Data | Decisão | Fonte |
|---|---|---|---|
| PIL-MULTILAJES-POR-FACE-20261009 | 2026-10-09 | Cada face admite vários contatos de laje/região, com início/fim, distâncias aos cantos, espessura e nível próprios para reprodução N3; viga central pode separar contatos. Não limitar cardinalidade nem misturar dados entre trechos. | Reforço explícito do dono neste chat; docs/SA-ANALISE/CLASSES/PIL.md |
| NIV-CORTES-RETROALIMENTACAO-20261009 | 2026-10-09 | Pré-interpretação e SA revisam vínculos mutuamente; cortes locais apoiam níveis de lajes/degraus/vigas e, por contato, pilares. Preservar raiz CAD e escopo; repetição circular não acrescenta prova. | Reforço explícito do dono neste chat; docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md |

Síntese vigente, convenções recorrentes, contraprovas e pendências: [Estilos estruturais — interpretação integrada](ESTILOS-ESTRUTURAIS-INTERPRETACAO-INTEGRADA.md). Consultar a evidência local antes de aplicar a regra a outra obra; cooperação entre classes não constitui prova circular nem aprovação automática.

| ID | Data | Decisão | Fonte |
|---|---|---|---|
| ESTILO-KB-HARMONIA-20261008 | 2026-10-08 | Consolidar todos os aprendizados do estilo TIPO_TESTE nas fontes canônicas e biblioteca global, alimentar o RAG e preservar limites/pendências. Nomes LAJ sem sufixo; corte é anotação, cotas de braço de laje não são medidas úteis. | Pedido do dono neste chat; ESTILOS-ESTRUTURAIS-INTERPRETACAO-INTEGRADA.md |

A regra inicial de L1_TIPO_TESTE é histórica e foi substituída por LAJ-OBJETOS-NOMES-REV2-20261008 (apenas L1/L2/L3). As orientações antigas sobre extensão de braços gráficos de laje são substituídas por VC-COTAS-UTEIS-20261008. Relatórios antigos preservam sua data e não são instrução vigente.

## LV-AJUSTES-PONTAS-20261008 — decisões do dono neste chat

| ID | Data | Decisão vigente | Fonte |
|---|---|---|---|
| LV-AJUSTES-PONTAS-20261008 | 2026-10-08 | Exibir duas tags de ajuste em cada segmento Para/Passa A/B para revisar a interpretação. Valores em cm; manter origem SA separada de ajuste posterior N3. | Pedido deste chat; docs/SA-ANALISE/CLASSES/LV.md |
| LV-TAGS-COMPACTAS-20261008 | 2026-10-08 | Apenas Ajuste, discreto e no estilo do nome; não escrever ponta esquerda/direita. Preservar associação local aprovada pelo dono. | Pedido deste chat; docs/SA-ANALISE/CLASSES/LV.md |
| LV-TAGS-SINAL-ALINHAMENTO-20261008 | 2026-10-08 | Mostrar explicitamente (-) ou (+); alinhar ajuste ao nome e a meia distância entre nome/extremidade, com conector diagonal na respectiva ponta. Zero é neutro; ausência não é zero. | Pedido deste chat; docs/SA-ANALISE/CLASSES/LV.md |
| LV-TAGS-CURTAS-EMPILHADAS-20261008 | 2026-10-08 | Em pouco espaço: esquerdo acima do nome e direito acima do esquerdo, na orientação do texto. Substitui alinhamento obrigatório nos trechos curtos e a disposição inicial perto das pontas. | Último comentário visual deste chat; docs/SA-ANALISE/CLASSES/LV.md |

O pedido de corrigir VF3 foi retirado pelo dono por chat errado; não incorporá-lo como decisão adicional. Documentar/indexar estes aprendizados não aprova itens pendentes nem promove automaticamente candidatos em semantic_rag_kb.

## CHAT-CONSOLIDACAO-20261008 — integridade e desempenho

Complemento vigente: [Aprendizados do portal — integridade, interpretação e desempenho](APRENDIZADOS-PORTAL-INTEGRIDADE-PERFORMANCE.md). Inclui recorte sem perda, cotas explodidas, corte não segmentando FV/LV, listas sem duplicação, cadeia com pendências por item e viewer integral sem pop-in. Evidências e limites acompanham cada tema; manter os contratos e pendências das classes.

| ID | Data | Decisão | Fonte |
|---|---|---|---|
| CHAT-CONSOLIDACAO-20261008 | 2026-10-08 | Harmonizar todos os aprendizados deste chat na Base Global e RAG para novas obras; preservar entidades, qualidade SA, OSNAP e funcionalidades. Compartilhar evidências entre classes sem prova circular; cotas e vistas não são limites físicos de vigas. | Pedido do dono; APRENDIZADOS-PORTAL-INTEGRIDADE-PERFORMANCE.md |


## TIPO-PRIMEIRO-PISO-20261009 — referência do pavimento tipo

| ID | Data | Decisão vigente | Fonte |
|---|---|---|---|
| TIPO-PRIMEIRO-PISO-20261009 | 2026-10-09 | Produzir o tipo uma vez usando os níveis do primeiro piso real representado no Assunto; conferir alturas na convenção, preservar faixas descontínuas e exceções. Folha/revisão não são pavimentos; altura igual não prova materiais ou comportamento idênticos. Não replicar sua cota absoluta nos outros pisos. | Instrução explícita do dono neste chat; docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md; carimbo e convenção EST-PE-007-TIPO-R01. |

### LV-PILAR-ALTURAS-IGUAIS-DONO-UNICO-20261010

O dono determinou: «quando é identico as alturas se escolhe1 por conveniencia apenas» e confirmou o ajuste **+11 cm além da face oposta do pilar** para o escolhido e **−11 cm antes da face de entrada** para o outro. Em V408/P33, confirmou o trecho **19/55** como Passa; o outro é 14/55. Reforçou que estes são os ajustes de destaque das laterais.

Escopo: encontro colinear conectado de trechos de mesma altura, inclusive trechos da mesma viga com larguras diferentes, resolvido por parede física coincidente. Substitui somente a parte de D-63 que deixava ambos englobarem em alturas iguais; alturas diferentes conservam a preferência pela mais profunda. A escolha geral usa maior largura e, em empate, identidade/geometria estável. Preservar a exceção C/D e o comportamento Para de D-64/G10. Alturas e níveis próprios não se alteram. Registrar os sinais em `lv_cell.adjustment_start/end`, preservar as coordenadas estruturais e aplicar o ajuste executivo uma única vez. Fonte: confirmação direta do dono no chat desta missão; regra em `docs/SA-ANALISE/CLASSES/LV.md`. Estado: implementação local e validação rápida; aprovação de ciclo completo/publicação ainda não declarada por este registro.

Esta decisão resolve a escolha de referência do alias TIPO quando o escopo e a compatibilidade estão comprovados; substitui a proposta anterior de sempre pedir ao usuário que escolha um andar. Não elimina pendências de leitura da convenção nem conflitos de variantes.

## NIV-ALTURA-NUMERICA-VINCULADA-20261010 — altura declarada da viga

| ID | Data | Decisão vigente | Fonte |
|---|---|---|---|
| NIV-ALTURA-NUMERICA-VINCULADA-20261010 | 2026-10-10 | A altura numérica definida da viga, quando vinculada corretamente à sua seção, prevalece sobre a altura medida na vista de corte original ou interpretada. Cortes podem conter defeitos de desenho ou cotas. No caso apresentado de V408, a altura correta é 55 cm. Preservar a geometria original e a discrepância como evidência; não aceitar número próximo sem vínculo comprovado. | Resposta explícita do dono à ficha duvida_L419_55_60.html neste chat; docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md |

A decisão resolve a pendência de interpretação 55/60 das fichas apresentadas. Não transforma a cota parcial 53 em altura total, não altera o DXF original e não aprova automaticamente os níveis, a continuidade ou os gates visuais ainda pendentes.

## NIV-REFERENCIA-SA-14PAV-20261010 — escopo da validação desta missão

| ID | Data | Decisão vigente | Fonte |
|---|---|---|---|
| NIV-REFERENCIA-SA-14PAV-20261010 | 2026-10-10 | Para terminar esta missão de níveis do14_PAV, interpretar e validar o SA contra o desenho estrutural limpo. Os documentos de engenharia reversa não são mais a referência exigida neste escopo. Dúvidas reais de interpretação devem ser apresentadas ao dono em ficha visual contextual, como a altura55/60. | Resposta explícita neste chat à pergunta sobre a referência humana FV14. |

Esta decisão delimita a conclusão da missão de interpretação SA do14_PAV. Não declara paridade N2×N4, certificação de geradores ou entrega N5; esses resultados não devem ser inferidos da validação SA.

## LAJ-LIMITES-FISICOS-ROTULOS-REPETIDOS-20261011

| ID | Data | Decisão vigente | Fonte |
|---|---|---|---|
| LAJ-LIMITES-FISICOS-ROTULOS-REPETIDOS-20261011 | 2026-10-11 | A área da laje deve ser reconhecida pelos limites físicos do estrutural limpo; linhas de cota ou visão de corte não são bordas. Na L409, a pequena área azul estava incorreta e a laje é ampla; verificar os vários cortes de vigas vinculados antes de concluir seu nível. Preservar rótulos repetidos como evidências, sem presumir parcelas distintas. | Correção explícita do dono neste chat; docs/SA-ANALISE/CLASSES/LAJ.md. |

## LAJ-L414-FUNDO-CONTINUO-20261011

O dono respondeu à ficha visual da região h=10 junto ao P22: **«855,22 m — mesmo fundo»**. A principal h=13 tem topo 855,25 m; ambas têm fundo 855,12 m. Decisão local exclusiva da região `slab-step:L414:972`, handles originais 972/E1F/E1D/D68, DXF SHA-256 `76144cb3c77586684c8db76311fe1ef3cadeef6389e003b948ac7c57c41e2e27`. Persistir pelo mecanismo `<recorte>.slab-region-review.json`, sem alterar o DXF ou criar regra por nome no motor. Espessura diferente, sozinha, continua sem provar qual superfície muda. Esta resposta resolve a convenção apresentada; contatos, regressão e demais QA dependem de novo ciclo completo.

## PIL-ESCADA-PAREDE-3DC-20261011 e LAJ-L406-REGIAO-96B-C0B-20261011

| ID | Data | Decisão vigente | Fonte |
|---|---|---|---|
| PIL-ESCADA-PAREDE-3DC-20261011 | 2026-10-11 | O handle 3DC representa a parede central entre degraus e corrimões da escada; não é pilar e está fora do escopo PIL. Preservar a entidade; revisar por SHA/handle/contorno, sem regra por nome P26. | Resposta direta do dono à ficha duvida_3DC_escada.html neste chat. |
| LAJ-L406-REGIAO-96B-C0B-20261011 | 2026-10-11 | Os contornos coincidentes 96B/C0B pertencem à região da laje L406; não são outro P14. A confirmação define identidade e proprietário, sem autorizar nível, espessura ou continuidade do fundo. | Resposta direta do dono à ficha duvida_96B_regiao.html neste chat. |

O dono esclareceu nas fichas da escada e da região à esquerda do P14: o centro entre os degraus e corrimões é uma parede, não um pilar, fora do nosso escopo de pilares; o retângulo pertence à laje L406. A primeira decisão vincula exclusivamente o handle `3DC`; a segunda vincula os contornos coincidentes `96B/C0B`. Fonte DXF SHA-256 `76144cb3c77586684c8db76311fe1ef3cadeef6389e003b948ac7c57c41e2e27`.

Persistir como `<recorte>.source-role-review.json`, com autoridade humana, decisão, handles e contorno original comprovados. Preservar todas as entidades e a geometria regional; impedir que o rótulo próximo P26/P14 transforme esses contornos em pilares. Pilares canônicos com geometria coincidente têm prioridade e não podem ser excluídos por essa decisão. A região confirmada da L406 deve permanecer disponível à pré-interpretação e ao SA, mas esta resposta **não define espessura, nível ou continuidade do fundo**. Provas de identidade não autorizam transferência de altitude nem aprovação dos demais gates. Validação: replay do inventário PRE real e testes locais; instalação e novo ciclo devem ter recibos próprios.

## SA-CICLO-RAPIDO-ANTES-PUBLICACAO-20261010

| ID | Data | Decisão vigente | Fonte |
|---|---|---|---|
| SA-CICLO-RAPIDO-ANTES-PUBLICACAO-20261010 | 2026-10-10 | Após cada ajuste, repetir e aprovar o ciclo completo pré-interpretação → SA → novo QA Gate pós-SA sem renderização ou publicação. Resolver as pendências ciclo após ciclo; só então publicar e realizar a conferência visual final. Erro encontrado na conferência volta ao desenvolvimento e exige nova aprovação rápida antes de republicar. | Pedido e reforço explícitos do dono neste chat; docs/SA-DESENVOLVIMENTO-CICLO-RAPIDO.md. |

Registrar procedimento e evidências não aprova itens pendentes. O ciclo rápido usa
o motor canônico e não substitui o veredito visual final.
<!-- Decisão acrescentada em 2026-10-10: correspondência de faces U. -->

## PIL-V301-13P-LIMITE-100-20261012 — fronteira local confirmada

O dono confirmou «Sim: mudança na divisória de 100 cm» na ficha original da
V301 entre P46 e P47. O trecho 19/120 termina na divisória original `414`,
alinhada à cota de 100 cm; daí até P47, a seção é 19/55. Os números originais
são `E83` (19/120) e `102A` (19/55). Fonte exclusiva: recorte estrutural do
13º SHA-256 `e5f6dabf3054027e7a37e7921db3dd62cf392e3e5bdac3075f8c376cc1280251`.
Resposta humana neste chat em 12/10/2026 à ficha `duvida_v301_p46_p47.html`.

É autoridade humana localizada, não regra por nome V301 nem critério universal
para escolher qualquer divisória. Registrar como revisão de fronteira com
hash da fonte e handles originais; validar parede completa, números de ambos
os lados e ausência de conflito antes de consumir. Não aprova distâncias,
geometria, identidade, pavimento, N3 ou publicação. Recibo da decisão em
`scripts/arete/relatorios/20261011_pil_continuacao/v301_human_boundary_receipt.json`.

## V514-TIPO-BORDA-FAIXA-H10-20261012

| ID | Data | Decisão vigente | Fonte |
|---|---|---|---|
| V514-TIPO-BORDA-FAIXA-H10-20261012 | 2026-10-12 | V514/TIPO: 19/48 dentro da faixa hachurada h=10; 19/50 depois da borda direita. Revisão vinculada à fonte aplicada e dois contatos PIL adicionais comprovados nas candidatas 28/30; publicação permanece bloqueada pelas demais pendências. | Resposta explícita neste chat à ficha duvida_v514_original.html; current_30_completed_receipt.json em 20261011_pil_continuacao. |

O dono confirmou neste chat: «Sim: 48 dentro, 50 depois da borda».
Na V514/TIPO, a seção 19/48 vale dentro da faixa hachurada h=10;
depois da borda direita dessa faixa, a seção é 19/50. A resposta confirma
a fronteira da mudança, não aprova os demais contatos, níveis ou gates.
Ficha original: `scripts/arete/relatorios/20261011_pil_continuacao/duvida_v514_original.html`.
Fonte estrutural SHA-256 `80b45ff3e024ebe037fe6e6e52829216120f006c55f6b60f79adb1df2dc65641`.
O vínculo aos handles e a aplicação no leitor ainda precisam de validação;
esta decisão não autoriza regra fixa por nome de viga. A decisão sobre
qual seção do P14 vale no encontro com V511 permanece aberta: o dono
solicitou reabrir a ficha para avaliar, sem escolher uma seção.

## PIL-P14-TIPO-SECOES-PENDENCIA-HUMANA-FUTURA-20261012

| ID | Data | Decisão vigente | Fonte |
|---|---|---|---|
| PIL-P14-TIPO-SECOES-PENDENCIA-HUMANA-FUTURA-20261012 | 2026-10-12 | P14/TIPO × V511: comportamento ideal ainda não compreendido; manter pendência humana futura, sem escolher 22/180-M ou 19/140-S, ajustar por suposição ou aprovar o contato. Seguir com casos independentes; não repetir a pergunta sem nova informação ou retomada humana. | Pedido explícito do dono neste chat; ficha duvida_p14_secoes_original.html e p14_future_human_pending_receipt.json. |

O dono não definiu qual seção do P14 vale no encontro com V511 e pediu
explicitamente manter o caso como **comportamento ideal ainda não
compreendido; pendência humana futura**. Não escolher entre 22/180-M e
19/140-S por conveniência, não presumir o significado dos sufixos e não
remover contatos como fantasmas para fechar o gate. Preservar a evidência
original e o estado incerto; seguir com os casos independentes sem repetir
a mesma pergunta até nova informação ou retomada humana deste caso.

Fonte SHA-256 `80b45ff3e024ebe037fe6e6e52829216120f006c55f6b60f79adb1df2dc65641`;
ficha `scripts/arete/relatorios/20261011_pil_continuacao/duvida_p14_secoes_original.html`.
Esta classificação não aprova o contato nem o pavimento e não resolve a
interpretação das demais projeções do desenho.

## Pilar em U: oito faces — 2026-10-10

| ID | Data | Decisão vigente | Fonte |
|---|---|---|---|
| PIL-U-OITO-FACES-20261010 | 2026-10-10 | A/B são o fundo do U; E/F uma pata e G/H a outra. C/D são as pontas livres do padrão U. A identidade acompanha a topologia da seção girada, sem depender da ordem dos vértices. Tags circulares aguardam definição do dono. | Resposta explícita sobre o P12 neste chat; docs/PADRAO-TAGS-DESTAQUE-AGENTICO-PIL.md §5.3. |

O dono definiu: A/B são o fundo do U; E/F são uma pata e G/H a outra. C/D continuam sendo as pontas livres conforme o padrão U. A identidade deve acompanhar a topologia quando a seção gira, sem depender do primeiro vértice ou sentido do DXF. A separação exterior/interior está explicitada no padrão de tags para revisão geométrica. Tags de pilares circulares ficam pendentes até o dono explicar sua convenção; não extrapolar A–H para círculos.

## PIL-P16-V420-SEM-MUDANCA-SECAO-20261012

O dono respondeu à ficha 01 da revisão humana do 14º: **não há mudança de
seção na V420 dos dois lados do P16**. A leitura atual 19/55 é compatível
com essa resposta. Fonte: resposta explícita neste chat em 2026-10-12;
`scripts/arete/relatorios/20261011_pil_continuacao/revisao_humana_01/01.html`
e `manifest.json`. A resposta resolve a dúvida de interpretação desse
encontro; não aprova automaticamente o QA, a continuidade dos fundos ou
o pavimento. O consumo da evidência pelo leitor deve ser validado sem
introduzir regra fixa por nome de viga/pilar. As fichas 02–06 continuam
sem resposta humana: o dono informou falta de fidelidade no SVG anterior.



## PIL-P28-CHEGADAS-VF403-V412-20261012

O dono definiu na ficha 02 do 14º: **VF403 chega às faces A e B do P28;
V412 chega à face C**. Fonte: resposta explícita neste chat em 2026-10-12;
`scripts/arete/relatorios/20261011_pil_continuacao/p28_human_arrival_receipt_20261012.json`.
Esta resposta decide identidade de chegada; não decide Passa/Para,
deslocamentos de 11 cm nem as faces não mencionadas. O snapshot atual
já contém esses nomes, mas também associa VF402 em A/B/C e V407 em C.
Revisar geometricamente essas associações adicionais antes de removê-las
ou aprovar o QA; não introduzir regra fixa por nome de item.


## FV-PONTAS-CHANFRO-SIMPLES-PRIORIDADE-20261012

| ID | Data | Decisão vigente | Fonte |
|---|---|---|---|
| FV-PONTAS-CHANFRO-SIMPLES-PRIORIDADE-20261012 | 2026-10-12 | Priorizar chanfros simples nas pontas das vigas de um encontro, harmonizando a repartição entre todos os fundos. Ponta complexa somente com necessidade explícita. V406/14º da ficha 03 está incorreta. | Resposta e desenho anotado do dono neste chat; v406_human_chamfer_receipt_20261012.json. |

A simplificação deve considerar todas as vigas do nó, preservando cobertura
da união externa, exclusividade por dono e apoios reais. Não basta reduzir
vértices de uma viga isoladamente. A resposta trata da ponta no encontro,
sem reprovar a dobra real junto ao P25 nem fornecer coordenadas universais.
Reforça D-85/FV; necessidade de geometria complexa deve ser explícita,
documentada e demonstrada antes de mantê-la. Correção geral, regressão e
QA do caso ainda pendentes; nenhuma geometria foi aprovada neste registro.


## FV-ALTURA-SEGMENTACAO-DESEMPATE-20261012

| ID | Data | Decisão vigente | Fonte |
|---|---|---|---|
| FV-ALTURA-SEGMENTACAO-DESEMPATE-20261012 | 2026-10-12 | Alturas diferentes: a mais profunda sempre passa e a menos profunda sempre para. Apenas em alturas iguais, priorizar menos segmentos e tentar evitar trechos menores que 60 cm quando possível. Trechos menores necessários devem ser mantidos. Na ficha 04, V407 para e V413 passa para evitar um segmento pequeno desnecessário na V413. | Resposta explícita do dono neste chat; v407_v413_human_junction_receipt_20261012.json. |

Os 60 cm são preferência para escolher quem passa/para, nunca mínimo
obrigatório, descarte de painel ou motivo para alterar alturas e apoios.
Comparar alternativas fisicamente válidas do encontro completo, preservando
área, donos e ausência de sobreposição/lacuna. Esta decisão refina a escolha
por conveniência em alturas iguais e o critério de D-90/FV: o formato T,
sozinho, não substitui a avaliação das alternativas. A regra de altura
vence qualquer ganho em número/comprimento de segmentos. Não extrapolar
o limiar para modulação executiva de laterais ou aplicar nomes fixos.
Correção e validação do SA/QA permanecem pendentes.


## FV-VF405-REVISAO-VISUAL-CORRETA-20261012

| ID | Data | Decisão vigente | Fonte |
|---|---|---|---|
| FV-VF405-REVISAO-VISUAL-CORRETA-20261012 | 2026-10-12 | VF405 está correta no trecho mostrado na ficha 05: contorno, largura e limites confirmados pelo dono. | Resposta explícita neste chat; vf405_human_review_receipt_20261012.json e revisao_humana_01/05.html. |

A confirmação é localizada ao trecho mostrado, não aprova automaticamente
QA, níveis, N3/N5 ou o pavimento. Preservar a geometria confirmada enquanto
se revisa a falta de comprovação do par de paredes/seção pelo QA; não
alterar o fundo somente para eliminar o aviso. A evidência original e os
vínculos ainda devem ser verificados no ciclo rápido.


## FV-V402-P18-SEGMENTO-CORRETO-20261012

| ID | Data | Decisão vigente | Fonte |
|---|---|---|---|
| FV-V402-P18-SEGMENTO-CORRETO-20261012 | 2026-10-12 | O segmento da V402 junto ao P18 mostrado na ficha 06 está correto; preservar essa geometria. | Resposta explícita neste chat; v402_p18_human_review_receipt_20261012.json e revisao_humana_01/06.html. |

Confirmação localizada ao segmento mostrado, não à viga inteira ou ao
inventário global. A comprovação pelo QA ainda precisa ser validada; não
alterar a geometria confirmada só para eliminar um aviso de inventário.
As seis fichas estão respondidas; isso não aprova o pavimento nem substitui
as correções de V406, do encontro V407/V413 e a revisão dos vínculos de P28.
