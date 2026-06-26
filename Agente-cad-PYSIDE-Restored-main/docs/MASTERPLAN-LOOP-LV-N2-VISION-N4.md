# MASTERPLAN - Loop LV N2 Vision -> N4 DXF

Versao: 0.1  
Data: 2026-06-22  
Escopo: exclusivamente LV, laterais de vigas.  
Status: etapa de analise e documentacao do loop autonomo.

## 0. Decisoes Fechadas Pelo Dono

Estas decisoes passam a ser fonte de verdade para o loop LV:

1. A ficha LV canonica e uma unica ficha por viga, com subfichas internas:
   - `section_views`: visoes de corte;
   - `segments_A`: segmentos da lateral A;
   - `segments_B`: segmentos da lateral B.
2. Cada recorte N2 LV contem somente uma viga, podendo conter varios segmentos e varias visoes de corte.
3. A validacao e sempre viga a viga, comparando segmento por segmento e visao de corte por visao de corte.
4. No N4, a geracao dos DXFs dos segmentos e separada da geracao dos DXFs das visoes de corte.
5. A validacao do N4 precisa ocorrer nos dois caminhos:
   - via ficha: N2 aprovado -> ficha N4 -> roundtrip por vision;
   - via visual: render N2 vs render N4 de cada segmento e de cada visao de corte.
6. Vision oficial do loop: vision do proprio chat executor.
7. O primeiro piloto obrigatorio e `Obra_TREINO_1`, pavimento 13, item `V301`.
8. Vision pode preencher e corrigir fichas candidatas automaticamente, desde que registre fonte, confianca, diff e regressao.

## 1. Objetivo

Criar um loop autonomo, executavel por chat/agente headless, para transformar as fichas N2 de laterais de vigas em um gabarito de alta fidelidade antes de usar essas fichas como fonte para o N4.

O alvo nao e somente "gerar um DXF bonito". O alvo e provar, por recorte, que a ficha N2 descreve o que existe visualmente no STOG real:

- quantidade correta de visoes de corte;
- quantidade correta de segmentos lado A e lado B;
- dimensoes/cotas corretas;
- paineis, sarrafos, grades, aberturas e aberturas de pilares corretamente interpretados;
- referencias textuais e continuidade corretas;
- campos suficientes para alimentar o robo de laterais de vigas e gerar N4 coerente.

O loop deve subir a confianca e o percentual de validacao de LV sem depender da GUI e sem aplicar hardcode por viga, pavimento ou obra.

## 2. Estado Atual Observado

Arquivos relevantes ja existentes:

- Aprendizado vivo de interpretacao LV: `docs/LV-COMPREENDER-INTERPRETACAO-FICHAS-N2-N4.md`
- Extrator N2 LV: `scripts/motor_reverso_lv.py`
- Gerador N4/DXF LV: `scripts/gerar_lv_dxf_stog.py`
- Gerador N4 por ficha LV usado no Comparison Engine: `scripts/arete/gerar_lv_n4_fichas.py`
- Comparador visual parcial N2+vision: `scripts/arete/comparar_ficha_lv_vision.py`
- UI Comparison Engine: `src/ui/modules/comparison_engine.py`
- Schema documentado: `docs/SCHEMA-FICHA-GRANULAR.md`
- Spec FV/LV: `docs/SPEC-VIGA-SPLIT-FV-LV.md`
- Plano anterior LV: `docs/MASTERPLAN-ARETE-LATERAL-VIGA.md`

### 2.1 Infra Existente

O que ja existe e pode ser usado no primeiro runner:

- Localizacao de recortes N2 via `reverse_eng_fichas.recorte_path`, `reverse_eng_recortes` e busca em disco.
- Render DXF -> PNG reaproveitavel de `scripts/arete/comparar_ficha_lv_vision.py`.
- Extracao geometrica N2 LV via `extrair_ficha_lateral_viga(...)`.
- Campos extraidos pelo motor em `section_views`, `panels_A`, `panels_B`, `h_A`, `h_B`, `b_geom`, `laje_sup/inf`, `holes`, `pillar_left/right`.
- Geracao N4 LV por viga inteira via `scripts/arete/gerar_lv_n4_fichas.py`.
- Geracao DXF LV por viga inteira via `scripts/gerar_lv_dxf_stog.py --item`.
- Visualizacao no Comparison Engine separando zonas `Visao Corte` e `Lateral A-B` por bbox dentro do mesmo DXF.

### 2.2 Infra Nova A Implementar

O que este masterplan exige, mas ainda nao existe como interface pronta:

- Runner headless `scripts/lv_n2_vision_loop_runner.py`.
- Runner headless `scripts/lv_n4_roundtrip_loop_runner.py`.
- Contrato canonico de ficha LV com adapter explicito:
  - canonico: `section_views`, `segments_A`, `segments_B`;
  - extrator atual: `section_views`, `panels_A`, `panels_B`;
  - N4 v2 atual: `segmentos`, `segmentos_B`;
  - gerador atual: `panels` em JSON `_A.json` / `_B.json`.
- Split fisico de N4 por unidade:
  - DXF de cada visao de corte;
  - DXF de cada segmento A;
  - DXF de cada segmento B.
- Scorer numerico dos estagios 40/60/80/90/95/100.
- Workflow conduzido por agente CLI com vision do proprio chat:
  - o runner gera PNGs, JSONs, diffs e comandos de reproducao;
  - o agente CLI inspeciona visualmente as imagens, raciocina sobre a causa, executa testes, edita motor/prompt/adapter/gerador quando necessario e roda nova iteracao;
  - `vision_ficha.json` e `roundtrip_ficha_from_n4.json` sao outputs estruturados desse raciocinio visual do agente, nao simples OCR/API;
  - uma API de vision pura pode ajudar no futuro, mas nao substitui o agente executor, porque o objetivo e interpretar, decidir, ajustar e revalidar.

Tabelas reais do banco `D:/Agente-cad-PYSIDE/project_data.vision`:

- `reverse_eng_fichas`: guarda fichas N2/F5. Tem 902 registros no banco atual.
- `reverse_eng_recortes`: guarda recortes de engenharia reversa. Tem 779 registros no banco atual.
- `beam_elements`: guarda elementos FV/LV derivados do N1. Tem 273 registros no banco atual.

Campos LV ja conhecidos no N2:

- Identificacao: `number`, `name`, `floor`, `side`
- Dimensoes globais: `total_width`, `total_height`, `h_A`, `h_B`, `b_geom`, `h_section`
- Lajes/VC: `laje_sup_A`, `laje_inf_A`, `laje_sup_B`, `laje_inf_B`, `section_views`
- Segmentos: `panels`, `panels_A`, `panels_B`
- Detalhes: `holes`, `pillar_left`, `pillar_right`, `sarrafo_left_id`, `sarrafo_right_id`
- Contexto: `tipo_viga`, `continuation`, `text_left`, `text_right`, `_er_meta`

Problema central atual: o extrator ja tenta ler os elementos, mas ainda erra o numero de visoes de corte, a quantidade de segmentos A/B e varios campos de detalhe. Portanto, N2-LV ainda nao pode ser tratado como gabarito firme para N4 sem antes passar por validacao visual.

## 3. Principios do Loop

1. LV somente. Este plano nao altera PIL, FV ou LAJ.
2. Headless. O loop roda sem PySide/GUI.
3. Ficha N2 versionada. O loop pode gerar candidatas e diffs, mas nao deve sobrescrever uma ficha validada por humano sem versionamento/backup.
4. Vision e juiz, nao unico autor. Vision pode preencher ou corrigir campos, mas precisa ser comparada com geometria extraida e com invariantes de dominio.
5. Um fix por causa. Cada iteracao deve registrar qual causa foi atacada: contagem VC, segmentacao A/B, cotas, sarrafos, grades, aberturas, pilares, render, prompt, etc.
6. Zero hardcode por item. Regras novas precisam ser geometricas, semanticas ou parametrizadas.
7. Promocao gated. Uma melhoria so vira regra geral quando melhora ou preserva o lote de regressao.

## 3.1 Papel Do Agente CLI Com Vision

O "vision do chat" neste plano nao e um servico passivo de OCR. E um workflow ativo conduzido por um agente CLI com capacidade visual e acesso ao workspace.

Responsabilidades do agente:

1. Rodar o runner headless e gerar artefatos.
2. Abrir/inspecionar renders N2 e N4.
3. Interpretar visualmente segmentos, visoes de corte, cotas, sarrafos, grades, aberturas, pilares e hachuras.
4. Comparar a interpretacao visual com a ficha extraida pelo motor.
5. Diagnosticar a causa: motor, prompt/schema, adapter, render, gerador ou ambiguidade do STOG.
6. Editar o sistema quando for seguro: extrator, adapter, gerador, prompt/schema ou scorer.
7. Reexecutar a rodada e verificar se houve melhoria.
8. Registrar a decisao e o novo estagio de similaridade.
9. Perguntar ao dono apenas quando o dado visual ou a regra de dominio for ambigua.

Portanto, `vision_ficha.json` nao e "saida de API". E a ficha estruturada que o agente produz apos raciocinar sobre a imagem, podendo usar sua visao, ferramentas locais, testes e comparacoes.

## 4. Artefatos Por Iteracao

Cada execucao do loop deve gerar uma pasta isolada:

`sandbox_lv_loop/runs/{timestamp}/{obra}/{pav}/{viga}/`

Conteudo minimo:

- `n2_recorte.dxf`: recorte LV original.
- `n2_recorte.png`: render do recorte N2.
- `extractor_ficha.json`: ficha extraida pelo motor.
- `vision_ficha.json`: ficha interpretada/preenchida por vision.
- `merged_ficha_candidate.json`: ficha candidata apos reconciliacao.
- `diff_extractor_vs_vision.json`: divergencias campo a campo.
- `decision_log.md`: decisao da rodada e causa atacada.
- `metrics.json`: score por grupo de campos.
- `n4_ficha.json`: ficha convertida para o formato consumido pelo gerador N4.
- `n4_composto.dxf`: DXF gerado da viga inteira, opcional e compativel com o gerador atual.
- `n4_composto.png`: render do DXF composto.
- `n4/vc/{idx}.dxf` e `n4/vc/{idx}.png`: visoes de corte separadas, infra nova.
- `n4/seg_A/{idx}.dxf` e `n4/seg_A/{idx}.png`: segmentos A separados, infra nova.
- `n4/seg_B/{idx}.dxf` e `n4/seg_B/{idx}.png`: segmentos B separados, infra nova.
- `roundtrip_ficha_from_n4.json`: ficha extraida por vision/geometria do DXF gerado.
- `visual_diff_n2_vs_n4.json`: diferencas visuais entre render N2 e render N4.
- `human_questions.md`: perguntas feitas ao dono e respostas recebidas.
- `similarity_stage.json`: estagio de similaridade atual e criterios faltantes.

## 4.1 Contrato De Adapter LV

Para evitar ambiguidade entre os nomes usados por cada parte do sistema, o loop deve normalizar tudo para uma ficha canonica antes de comparar ou gerar N4.

Ficha canonica LV:

```json
{
  "viga": "V301",
  "section_views": [],
  "segments_A": [],
  "segments_B": [],
  "metadata": {}
}
```

Mapeamentos obrigatorios:

| Origem/Destino | Campos |
|----------------|--------|
| Motor N2 atual | `panels_A` -> `segments_A`, `panels_B` -> `segments_B`, `section_views` preservado |
| Vision ficha | deve devolver diretamente `section_views`, `segments_A`, `segments_B` |
| N4 v2 atual | `segments_A` -> `segmentos`, `segments_B` -> `segmentos_B` |
| Gerador atual | `segments_A/B` -> `panels` nos JSONs `_A.json` e `_B.json` |

Nenhum comparador deve ler diretamente campos de um formato legado sem passar por este adapter. Isso impede que um score misture `panels_A`, `segmentos` e `segments_A` como se fossem entidades diferentes.

## 5. Etapa 1 - Loop N2 LV Comprovado Por Vision

### 5.1 Entrada

Entrada de uma iteracao:

- obra;
- pavimento;
- item LV, exemplo `V301`;
- caminho do recorte N2;
- ficha N2 atual se existir em `reverse_eng_fichas`;
- versao atual do extrator `motor_reverso_lv.py`;
- prompt/schema vision LV.

### 5.2 Pipeline

Para cada recorte LV:

1. Localizar o recorte N2.
   - Fonte preferida: `reverse_eng_fichas.recorte_path` filtrado por `obra_name`, `pavimento`, `classe='LV'`, `elemento_id`.
   - Fallback: `reverse_eng_recortes`.
   - Fallback final: busca em disco nos recortes `LV_*_motor_*.dxf`.

2. Renderizar o recorte N2 para PNG.
   - Render com crop por bbox real.
   - Render preservando cores/layers quando possivel.
   - Render alternativo de alto contraste para leitura OCR/vision.

3. Extrair ficha pelo motor.
   - Chamar `extrair_ficha_lateral_viga(recorte_path, elemento_id, obra_root=...)`.
   - Persistir como `extractor_ficha.json`.

4. Interpretar por vision.
   - Enviar imagem N2 e schema esperado LV.
   - Vision deve retornar ficha estruturada, nao texto solto.
   - Campos obrigatorios por grupo:
     - VC: `section_views`, `h_A`, `h_B`, `b_geom`, `h_section`, `laje_sup_A/B`, `laje_inf_A/B`, `tipo_viga`.
     - Segmentos A/B: contagem, larguras, alturas, lajes locais, tipo do painel.
     - Detalhes: sarrafos, grades, aberturas, aberturas de pilares, referencias laterais.

5. Comparar motor vs vision.
   - Comparacao por grupos, nao apenas score unico.
   - Deltas tolerados:
     - medidas em cm: inicialmente +/- 0,5 cm para cotas legiveis, +/- 2 cm quando vision marcar baixa confianca;
     - contagens: tolerancia zero para `n_section_views`, `n_segments_A`, `n_segments_B`;
     - booleanos/ativos: tolerancia zero quando visualmente claro.
   - A comparacao deve ser hierarquica:
     - viga;
     - lista de visoes de corte;
     - cada visao de corte por indice/label;
     - lista de segmentos A;
     - cada segmento A por ordem e largura;
     - lista de segmentos B;
     - cada segmento B por ordem e largura.

6. Reconciliar ficha candidata.
   - Se motor e vision concordam: campo aprovado.
   - Se divergem e vision tem alta confianca visual: propor `vision_ficha` como correcao candidata.
   - Se divergem e geometria do DXF e objetiva: preferir motor, mas registrar ajuste de prompt/vision.
   - Se ambos sao inconclusivos: marcar campo como `needs_human` e perguntar ao dono uma microdecisao objetiva.

7. Diagnosticar causa.
   - `extractor_bug`: geometria extraivel, motor errou.
   - `vision_prompt_bug`: imagem contem dado, vision nao leu direito.
   - `render_bug`: PNG nao mostra dado suficiente.
   - `schema_gap`: campo existe no desenho mas nao no schema.
   - `ambiguous_stog`: desenho humano ambigua ou incompleto.
   - `n2_current_cache_stale`: ficha salva nao corresponde ao recorte atual.

8. Ajustar.
   - Ajuste de motor: alterar formula/heuristica no extrator.
   - Ajuste de prompt/schema: melhorar instrucao vision ou normalizacao.
   - Ajuste de ficha candidata: preencher campo com provenance `vision_confirmed` ou `geometry_confirmed`.
   - Ajuste de render: melhorar crop/resolucao/layers.

9. Reexecutar o mesmo recorte.
   - A rodada so conta como melhoria se o score sobe sem piorar campos ja aprovados.

10. Registrar aprendizado.
   - Nunca como hardcode silencioso.
   - Registrar causa, campos afetados, antes/depois e exemplos.

11. Classificar estagio de similaridade.
   - O loop nao usa apenas aprovado/reprovado.
   - Cada rodada deve cair em um estagio: 40%, 60%, 80%, 90%, 95% ou 100%.
   - O estagio decide se o chat pode continuar sozinho, se deve ajustar motor/prompt/gerador, ou se deve perguntar ao dono.

### 5.3 Score da Etapa 1

Score por recorte LV:

- `VC_COUNT`: quantidade de visoes de corte correta.
- `VC_FIELDS`: campos de cada visao de corte corretos.
- `SEG_A_COUNT`: quantidade de segmentos A correta.
- `SEG_B_COUNT`: quantidade de segmentos B correta.
- `SEG_A_FIELDS`: larguras, alturas, tipo, lajes locais de A.
- `SEG_B_FIELDS`: larguras, alturas, tipo, lajes locais de B.
- `DETAILS`: sarrafos, grades, aberturas, pilares, referencias.
- `CONFIDENCE_TRACE`: cada campo tem fonte e confianca.

Gate minimo para um recorte virar N2 aprovado por vision:

- `VC_COUNT = 100%`
- `SEG_A_COUNT = 100%`
- `SEG_B_COUNT = 100%`
- campos dimensionais principais >= 95%
- detalhes >= 90% ou marcados como `not_visible/needs_human` com justificativa
- nenhuma regressao em campos previamente aprovados

### 5.4 Estagios De Similaridade Da Etapa 1

Os estagios sao metas operacionais do chat executor. Eles tambem definem quando perguntar ao dono.

Formula minima do score N2:

- 25% contagem e pareamento de `section_views`;
- 25% contagem e pareamento de `segments_A`;
- 25% contagem e pareamento de `segments_B`;
- 15% cotas/dimensoes principais;
- 10% detalhes e provenance.

O estagio da viga e o menor entre o score ponderado e o menor score individual bloqueante de VC/segmento. Assim uma viga nao pode chegar a 95% se uma VC ou um segmento estiver abaixo de 90%.

| Estagio | Significado | Acao do chat |
|---------|-------------|--------------|
| 40% | Le a viga certa, mas erra estrutura principal. Contagem de VC ou segmentos ainda instavel. | Nao mexer em N4. Corrigir render, prompt e extrator de contagem. |
| 60% | Contagens principais quase fechadas, mas campos dimensionais ou lados A/B ainda divergem. | Atacar segmentacao, cotas e pareamento A/B. |
| 80% | VC e segmentos estao coerentes, mas detalhes tecnicos ainda falham: sarrafos, grades, aberturas, pilares ou lajes locais. | Atacar campos detalhados e schema. Perguntar ao dono se houver ambiguidade visual. |
| 90% | Ficha N2 e tecnicamente usavel para gerar N4, com poucos detalhes pendentes. | Rodar Etapa 2 em modo experimental. Nao selar golden ainda. |
| 95% | Ficha N2 passa como gabarito operacional. N4 deve reproduzir ficha e visual sem falha semantica. | Permitir escrita candidata/versionada e regressao em lote. |
| 100% | Segmentos, VCs, campos e detalhes batem sem divergencia relevante. | Selar recorte como aprovado pelo loop, mantendo provenance. |

Perguntas humanas entram quando:

- o chat fica duas rodadas no mesmo estagio sem melhoria;
- vision e geometria discordam sobre um campo bloqueante;
- o recorte tem convencao STOG que nao esta no schema;
- a diferenca visual N2 vs N4 parece aceitavel, mas o criterio de aceitacao depende do dono.

## 6. Etapa 2 - Validacao N2 -> N4 -> DXF -> Vision

Esta etapa so roda quando a Etapa 1 do item tiver passado ou estiver explicitamente liberada para teste.

### 6.1 Pipeline

1. Converter ficha N2 aprovada para ficha N4.
   - Usar adaptador LV existente ou criar adaptador headless.
   - Entrada: `merged_ficha_candidate.json`.
   - Saida: `n4_ficha.json`.

2. Comparar ficha N4 contra ficha N2.
   - Verificar se nenhum campo obrigatorio foi perdido.
   - Verificar normalizacao de nomes: `b_geom` vs `b_cm`, `h_A/h_B`, `panels_A/B`, `section_views`.
   - Verificar se a estrutura final respeita o contrato: LV = uma ficha por viga, com subfichas internas de segmentos A, segmentos B e VCs.
   - Validar separadamente:
     - ficha N4 de cada visao de corte;
     - ficha N4 de cada segmento A;
     - ficha N4 de cada segmento B.

3. Gerar DXF N4.
   - Modo atual: gerar `n4_composto.dxf` da viga inteira com o gerador existente.
   - Modo alvo: gerar DXFs de visoes de corte separados dos DXFs de segmentos.
   - Usar `scripts/arete/gerar_lv_n4_fichas.py` ou `scripts/gerar_lv_dxf_stog.py`, conforme o caminho mais estavel.
   - Salvar DXF em pasta da rodada, sem poluir a pasta oficial ate passar no gate.
   - Saidas esperadas por item:
     - `n4_composto.dxf` no modo atual;
     - `n4_vc_{idx}.dxf` para cada visao de corte;
     - `n4_seg_A_{idx}.dxf` para cada segmento A;
     - `n4_seg_B_{idx}.dxf` para cada segmento B;
     - os arquivos unitarios sao infra nova, mesmo quando derivados inicialmente por crop/bbox do composto.

4. Renderizar DXF N4.
   - Gerar PNG com mesmo padrao de crop usado no N2.
   - Renderizar cada VC e cada segmento separadamente.

5. Extrair ficha do DXF N4 gerado.
   - Rodar vision no render do N4.
   - Rodar tambem o extrator geometrico quando o DXF gerado for compativel.
   - Gerar `roundtrip_ficha_from_n4.json`.
   - Comparar roundtrip por unidade:
     - N2.VC[i] vs N4.VC[i];
     - N2.A[i] vs N4.A[i];
     - N2.B[i] vs N4.B[i].

6. Comparar N2 aprovado vs ficha extraida do N4.
   - Se o N4 foi gerado corretamente, vision deve conseguir preencher a mesma ficha a partir do DXF gerado.
   - Divergencias indicam perda de informacao no adaptador, no gerador ou no render.

7. Comparar visualmente N2 vs N4.
   - Comparar por zonas:
     - `Visao Corte`;
     - `Lateral A-B`.
   - Verificar diferencas de cor, layers visuais, linhas, hachuras, cotas, textos, sarrafos, grades, aberturas e proporcoes.
   - Classificar diferencas:
     - `semantic_fail`: conteudo tecnico errado.
     - `style_fail`: conteudo certo, estilo/cor/layer diferente.
     - `render_artifact`: diferenca causada pelo render.
     - `acceptable_delta`: diferenca toleravel e justificada.

8. Ajustar e repetir.
   - Se ficha N4 perde dados: corrigir adaptador.
   - Se DXF nao expressa a ficha: corrigir gerador.
   - Se vision nao le o N4 mas le o N2: corrigir estilo/render do N4 ou prompt especifico.
   - Se N4 visual diverge do N2: corrigir desenho, layers ou posicionamento.

### 6.2 Gates da Etapa 2

Um recorte LV passa na Etapa 2 quando:

- N4 ficha contem 100% dos campos obrigatorios do N2 aprovado.
- DXF N4 e gerado sem erro.
- Vision no N4 reconstroi a ficha com score >= 95% nos campos principais.
- Comparacao visual N2 vs N4 nao tem `semantic_fail`.
- `style_fail` restante esta documentado e nao afeta interpretacao tecnica.

### 6.3 Estagios De Similaridade Visual N4

A similaridade visual deve ser medida para cada unidade gerada:

- cada `VC`;
- cada segmento `A`;
- cada segmento `B`;
- opcionalmente o composto completo.

Enquanto o split fisico ainda nao existir, o runner pode derivar imagens unitarias por crop/bbox do `n4_composto.dxf`. Isso vale como transicao, mas o gate final de 95%/100% exige DXF unitario ou prova equivalente de que o composto contem a unidade isolavel sem perda visual.

Formula minima do score visual por unidade:

- 30% geometria/proporcao;
- 20% cotas e textos;
- 20% elementos internos: sarrafos, grades, aberturas, pilares;
- 15% layers/cores/hachuras relevantes;
- 15% roundtrip vision reextraindo a mesma ficha.

| Estagio | Criterio visual | Acao |
|---------|-----------------|------|
| 40% | A unidade existe, mas proporcao, elementos ou pose estao claramente errados. | Corrigir geracao basica e bbox/render. |
| 60% | Geometria principal aparece, mas cotas, textos ou elementos internos estao incompletos. | Corrigir adaptador ficha->N4 e desenho dos elementos principais. |
| 80% | Conteudo tecnico quase todo presente, mas faltam detalhes: hachura, sarrafo, grade, abertura, cor/layer importante. | Corrigir detalhes do gerador e layers. |
| 90% | Visual aprovado tecnicamente, com diferencas pequenas de estilo. | Rodar roundtrip vision e regressao. |
| 95% | Similaridade alta; vision reextrai ficha equivalente e nao ha falha semantica. | Candidato a aprovado. |
| 100% | Igualdade visual operacional: ficha, roundtrip e imagem sem divergencia relevante. | Selar unidade e depois a viga inteira. |

Gate da viga inteira:

- todos os segmentos A >= 95%;
- todos os segmentos B >= 95%;
- todas as VCs >= 95%;
- nenhum item individual abaixo de 90%;
- media ponderada da viga >= 95%;
- para 100%, todos os itens individuais precisam estar em 100%.

## 7. Loop Autonomo Do Chat Executor

O chat executor deve seguir esta ordem:

1. Selecionar lote piloto pequeno.
   - Comecar obrigatoriamente por `Obra_TREINO_1`, pavimento 13, item `V301`.
   - Depois incluir uma viga com continuacao, uma com VC multipla, uma com grade e uma com abertura/pilar.

2. Rodar baseline.
   - Extrator atual.
   - Vision atual.
   - N4 atual.
   - Salvar scores.

3. Escolher uma causa principal.
   - Atacar primeiro contagens: VC, A, B.
   - Depois cotas e dimensoes.
   - Depois detalhes.
   - Depois estilo visual do N4.

4. Aplicar uma mudanca pequena.
   - Codigo, prompt, schema, render ou adaptador.

5. Reexecutar mesmo item e lote de regressao.
   - A melhoria precisa subir o item alvo sem reduzir score dos itens ja melhores.

6. Registrar resultado.
   - Atualizar `decision_log.md`.
   - Atualizar metricas agregadas.
   - Marcar campos `approved`, `needs_human`, `blocked` ou `regressed`.
   - Atualizar estagio de similaridade 40/60/80/90/95/100 por VC, por segmento e por viga.

7. Expandir lote.
   - 1 item -> 5 itens -> pavimento completo -> outra obra.

## 8. Perguntas Fechadas E Perguntas Ainda Abertas

Perguntas ja respondidas pelo dono:

1. Ficha LV canonica: uma ficha por viga com subfichas internas.
2. Unidade de validacao: uma viga por recorte, comparando segmento por segmento e VC por VC.
3. Vision pode preencher/corrigir automaticamente, com o chat buscando a melhor rota para similaridade Arete.
4. Vision oficial: vision do proprio chat.
5. Piloto inicial: `V301`.

Perguntas ainda abertas para execucao fina:

1. Quais detalhes sao bloqueantes para 95% em cada unidade?
   - sarrafos;
   - grades;
   - aberturas;
   - aberturas de pilares;
   - hachuras;
   - textos de referencia;
   - cores/layers.

2. Quando o N4 atinge 90% visual mas nao 95%, o chat pode seguir ajustando sozinho por quantas rodadas antes de perguntar?

3. Onde guardar fichas corrigidas automaticamente pelo loop:
   - apenas em `sandbox_lv_loop` ate aprovar;
   - como versao candidata em banco paralelo;
   - ou em `reverse_eng_fichas` com status/versionamento.

4. O chat pode alterar `motor_reverso_lv.py` e geradores durante o loop, ou a primeira rodada deve produzir somente relatorios/fichas candidatas?

## 9. Primeiro Incremento Recomendado

Criar um runner headless novo:

`scripts/lv_n2_vision_loop_runner.py`

Responsabilidades iniciais:

- localizar recorte LV por obra/pav/item;
- renderizar N2;
- chamar `extrair_ficha_lateral_viga`;
- gerar pacote de trabalho para o agente CLI: PNG, schema LV completo, ficha extraida, comandos de reproducao e diff inicial;
- receber/importar `vision_ficha.json` produzido pelo agente apos inspecao visual e raciocinio;
- comparar `extractor_ficha` vs `vision_ficha`;
- gerar relatorio e score;
- opcionalmente gerar `merged_ficha_candidate.json`;
- nao escrever em `reverse_eng_fichas` na primeira versao, exceto com flag explicita.

Depois criar o segundo runner:

`scripts/lv_n4_roundtrip_loop_runner.py`

Responsabilidades:

- receber ficha N2 aprovada/candidata;
- gerar ficha N4 por VC e por segmento;
- gerar `n4_composto.dxf` com a infra atual;
- gerar ou derivar DXFs/imagens separados de VCs e segmentos como infra alvo;
- renderizar N4 por unidade;
- gerar pacote de trabalho para o agente CLI comparar N2 vs N4 por vision;
- receber/importar `roundtrip_ficha_from_n4.json` produzido pelo agente apos inspecao visual, testes e raciocinio;
- comparar N2 vs N4 por campos, por unidade e por imagem;
- classificar similaridade 40/60/80/90/95/100.

## 10. Criterio De Pronto Desta Etapa De Planejamento

Esta etapa esta pronta quando:

- o loop Etapa 1 esta documentado;
- o loop Etapa 2 esta documentado;
- os artefatos e gates estao definidos;
- as perguntas de decisao estao explicitas;
- nenhuma implementacao destrutiva foi feita no banco ou nas fichas reais.
