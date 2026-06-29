# MASTERPLAN — Cérebro RAG Multimodal + Curadoria Redesign
## Vision-Estrutural AI — Segundo Cérebro para Compreensão Estrutural
**Versão:** 3.1 (observabilidade, retrieval local e plugins)
**Data:** 2026-06-26
**Orquestração:** Athena (CEO-Planejamento)
**Status:** EXECUÇÃO CONTROLADA — infraestrutura avançada; promoção depende de validação humana
**Mudança v1.0 → v2.0:** O RAG **não é mais alimentado por bulk dump** das fichas em
desenvolvimento. Passa a crescer **por evento de validação humana** (gated). Adicionada
Política de Confiança (§3), distinção Regra vs Instância (§4), EPICs reordenados (§9).
**Mudança v2.0 → v2.1:** Adicionado contrato de execução para modelo menor (§0.1),
mapa de impacto por aba/botão (§2.1), squads responsáveis (§10.1), caminhos reais de
documentação (§12) e Definition of Done final (§15).
**Mudança v2.1 → v2.2:** Adicionada política de desvalidação humana (§3.6): informação
validada pode ser revogada, deixa de participar do RAG imediatamente e só volta como nova
versão após nova validação humana.
**Mudança v2.2 → v2.3:** Separado o aprendizado de recorte do aprendizado de ficha/N4
(§3.7). Aprovar recorte no fluxo reverso valida somente a geometria/classificação do
recorte e treina o motor de recorte por classe; não promove F5/N2, não valida campos e
não valida N4.
**Mudança v2.3 → v2.4:** Executado RAG-1.1 com gate aprovado: `semantic_rag_kb`
populada com 109 regras vindas de `domain_knowledge:field_semantics`
(PIL=10, LV=43, FV=43, LAJ=13), mantendo `reverse_eng_fichas.rag_indexed=0` e
`fase3_fichas.revisado=0`.

**Mudança v2.4 → v2.5:** Auditado o EPIC RAG-3. O recorte aprovado ensina apenas
o motor de crop; exclusão/desvalidação revoga os exemplos associados sem apagar
o histórico. Comparison Engine exige `validation_origin='human_ui'`; origens
sintéticas permanecem em quarentena. RAG-3.1b, indexação específica por artefato
do RAG-3.2 e promoção T1→T2 continuam pendentes.

**Mudança v2.5 → v2.6:** A seleção de obra passou a atualizar silenciosamente o
snapshot RAG local via `QProcess`, com fila para trocas rápidas de obra. O processo
escreve somente `DADOS-OBRAS/{obra}/obra_rag/manifest.json`; não promove tiers e
não toca os índices globais.

**Mudança v2.6 → v2.7:** O botão antes reservado no Structural Analyzer virou
`Consultar Contexto RAG`. Ele consulta regras e exemplos T1/T2 para o item atual,
ou resume PL/LV/FV/LJ quando não há item, sem executar Análise Geral, alterar
fichas ou gerar DXF.

**Mudança v2.7 → v2.8:** A aba `Fichas Granulares [F5]` recebeu validação e
revogação humanas explícitas. F5 aprovada é imutável; correção exige
revogar → reextrair → revisar → revalidar. Vetores usam `source_id` versionado
pelo conteúdo, impedindo que revalidação de uma nova versão reative a antiga.

**Mudança v2.8 → v2.9:** Validações N3/N4 no Comparison Engine passaram a
materializar `rag_artifact_validations` com hash SHA-256 do DXF, proveniência,
nível e estado validado/revogado. Curadoria mostra a contagem separada. Loopers
sem origem humana não criam registros nesta memória.

**Mudança v2.9 → v3.0:** Artefatos N3/N4 validados agora geram render canônico
`dxf-canonical-v1`: PNG 1024x768, fundo CAD escuro, todas as layers visíveis,
manifesto e hashes do DXF/PNG. Curadoria mostra `renders prontos / validados`.
Ainda não há embedding visual nem backfill de validações antigas.

**Mudança v3.0 → v3.1:** Curadoria ganhou galeria e histórico read-only dos renders
N3/N4. O snapshot por obra ganhou retrieval lexical determinístico explicitamente
local (`is_global_truth=false`). Foram adicionados health check, export auditável com
hashes e registros plugáveis para extratores/robôs. Nenhuma dessas rotinas promove T0.

---

## 0. COMO LER E EXECUTAR ESTE DOCUMENTO

> **Para o modelo/agente executor:** este plano é mastigado de propósito. Cada story tem
> **Arquivo · Ação · Entrada · Saída · Gate · NÃO-FAZER**. Execute uma story por vez, na
> ordem da §9. Nunca pule o NÃO-FAZER — ele existe para impedir contaminação do cérebro.
> Ao terminar uma story, confira o Gate antes de seguir. Se um Gate falhar, **pare e reporte**.

> **Regra de honestidade:** a compreensão por classe **não está consolidada**. Nenhuma spec
> de classe (PIL/LV/FV/LAJ) deste ou de outro doc é verdade absoluta. Antes de fixar regra
> semântica de classe, **valide contra o N2 real da obra** e confirme com o dono.

### 0.1 Contrato de Execução para Modelo Menor / Squad Executor

Este documento **não manda executar tudo de uma vez**. Ele é um contrato para dividir o
trabalho em stories pequenas, sempre com rollback conceitual simples.

**Antes de qualquer story, o executor deve:**
- Ler este masterplan inteiro.
- Ler a Política de Confiança (§3) novamente antes de tocar qualquer script RAG.
- Localizar os arquivos reais com `rg`/`rg --files`; não assumir caminho se houver
  duplicatas entre raiz e `Agente-cad-PYSIDE-Restored-main/`.
- Abrir a story atual e confirmar: Arquivo, Ação, Entrada, Saída, Gate e NÃO-FAZER.

**Regra de execução:**
- Uma story por vez.
- Um PR/commit por story ou por lote mínimo coerente.
- Nenhum bulk index das fichas em desenvolvimento.
- Nenhuma escrita no RAG global sem `is_indexable(row) == true`.
- Nenhuma mudança no schema N1/F5 sem aprovação explícita do dono.
- Se um Gate falhar, parar e reportar com evidência.

**Validação mínima por story:**
- Selftest do script alterado/criado.
- Teste relevante existente quando houver (`tests/test_comparison_*`,
  `tests/test_diagnostic_reverse_viewer.py`, ou teste novo focado).
- Smoke manual da aba afetada quando a story tocar UI PySide.

### 0.2 Convenção de Caminhos

Há mais de uma árvore de código. Para evitar duplicação e drift:

| Tipo | Caminho observado | Regra |
|------|-------------------|-------|
| App/source PySide principal | `D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\src\...` | Preferir para UI, Comparison Engine, Diagnostic Hub e testes da app. |
| Scripts RAG legados/atuais | `D:\Agente-cad-PYSIDE\scripts\rag_*.py` | `rag_ingestor.py`, `rag_query.py` e afins foram encontrados aqui; editar aqui se este for o script realmente chamado. |
| Scripts RAG por-obra | `D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\obra_rag_pipeline.py` | Usar para RAG por-obra, salvo se a app chamar outro entrypoint. |
| Docs históricos e técnicos | `D:\Agente-cad-PYSIDE\...` e `D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\docs\...` | Harmonizar por nota de reconciliação, não mover em massa. |

Quando a story citar `scripts/foo.py`, o executor deve primeiro rodar `rg --files | rg
"foo.py"` e editar o arquivo que já é usado pelo fluxo real. **Não criar duplicata com
o mesmo nome em outra árvore sem justificar.**

---

## 1. VISÃO ESTRATÉGICA (Uma Frase)

> Construir o **segundo cérebro** do CAD-Analyzer: um RAG multimodal que compreende cada
> classe estrutural em 8 dimensões, **cresce conforme o humano valida** (nunca por dados
> em rascunho), e é navegável pela aba **Curadoria** como um mapa mental vivo — para
> **acelerar o aprendizado** com **garantia de que só conhecimento correto entra**.

---

## 2. O PROBLEMA QUE ESTE PLANO RESOLVE (e o erro que evita)

**Contexto real (dono, 2026-06-26):** o sistema está **em desenvolvimento ativo** —
fichas, recortes e itens N1/N2/N3/N4 ainda estão sendo ajustados e validados. Não estão
corretos ainda.

**Erro a evitar (era o RAG-1 da v1.0):** indexar agora as 902 fichas F5 + 405 fichas F7
contaminaria o cérebro com **899 hipóteses não confirmadas** (765 draft + 137 extracted;
só **3 aprovadas por humano**: P1, P101, L308). RAG dilui o erro e o torna invisível →
o sistema passaria a sugerir o errado com cara de inteligência.

**Solução (v2.0):** o RAG cresce **por ato de validação humana**, item a item, com
camadas de confiança. Começa pequeno e **correto** (golden seed = os 3 aprovados) e
ganha inércia a cada validação. O valor imediato vem das **regras** (que o dono conhece),
não das instâncias (que o motor ainda erra).

### 2.1 Onde Impacta na App (abas e botões)

| Aba / área | Botão / ação | O que muda | O que NÃO muda |
|------------|--------------|------------|----------------|
| **Diagnostic Reverse Hub** | Aprovar/validar recorte | Valida somente o recorte: bbox/polígono, classe, pavimento, origem DXF/layer e contexto visual. Registra evento de aprendizado de recorte para melhorar o recortador por classe. | Não valida campos F5/N2. Não valida N4. Não promove a ficha para T1. Não indexa a instância no RAG global de fichas. |
| **Structural Analyzer** | Iniciar Análise Geral | Continua motor puro. É a linha base que precisa aprender sem gabarito. | Não consulta RAG e não recebe sugestão automática. |
| **Structural Analyzer** | Análise com Eng. Reversa / com Contexto | Consulta RAG por-obra + RAG global T1+ para sugerir campos, similares e evidências. | Não preenche sozinho sem confirmação humana. Não gera DXF. |
| **Comparison Engine** | Selecionar N1/N2/N3/N4 | Continua central para comparação visual e validação humana. | Não vira fonte automática de verdade sem aprovação. |
| **Comparison Engine** | Aprovar match/score/diff | Cria `training_event`, vincula N1↔N2 e indexa só o item validado. | N3 nunca recebe campos de N2/N4. N2/N4 continuam gabarito, não input do N3. |
| **Comparison Engine** | Desvalidar match/score/diff | Marca o conhecimento como revogado, cria evento de invalidação e remove o item das consultas RAG. | Não apaga o histórico humano; não sobrescreve silenciosamente o vetor antigo. |
| **Curadoria** | Mapa RAG / Enciclopédia / Cobertura | Mostra o cérebro, tiers, lacunas, cobertura e fluxo mental. Começa como observador. | Não edita fichas e não indexa T0. |
| **Curadoria** | Indexar Validados Pendentes | Só habilita após RAG-0 e RAG-1. Indexa T1 pendente, nunca T0. | Não existe botão "indexar tudo". |
| **Curadoria** | Popular Regras Agora | Pode popular `semantic_rag_kb` a partir de `domain_knowledge`, porque é REGRA, não instância. | Não inventa semântica; só espelha/organiza regra existente e validável. |
| **Robôs N3/N4** | Gerar DXF | Continuam co-protagonistas para fechar o loop visual. | Geradores certificados não devem ser refatorados fora do escopo da story. |
| **Top bar Obra/Pavimento** | Troca de obra/pavimento | Pode disparar carregamento do RAG por-obra e sincronizar abas. | Não promove dados locais ao global automaticamente. |

**Conselho arquitetural:** o primeiro valor para o dono não é "RAG respondendo muito";
é **Curadoria mostrando com clareza o que é confiável, o que está em quarentena e qual
validação humana acelera mais o aprendizado**.

---

## 3. POLÍTICA DE CONFIANÇA / ANTI-CONTAMINAÇÃO (NÚCLEO DO PLANO)

> Esta seção tem **prioridade sobre qualquer outra**. Toda escrita no RAG passa por aqui.

### 3.1 As 3 Camadas de Confiança (tiers)

Todo dado indexável carrega um campo `tier` (ou `confianca`). O RAG global só serve
como "verdade/professor" o que estiver em tier ≥ VALIDADO.

| Tier | Nome | Quem produz | Entra no RAG global? | Papel |
|------|------|-------------|----------------------|-------|
| **T0** | QUARENTENA | Motor (draft/extracted) | ❌ NÃO (fica isolado) | Hipótese em desenvolvimento |
| **T1** | VALIDADO | Humano aprova (1 obra) | ✅ SIM (como professor) | Verdade confirmada |
| **T2** | CONSOLIDADO | Validado em ≥ 2 obras | ✅ SIM (vira default/regra) | Padrão generalizável |

**Mapeamento para o banco real (não criar coluna duplicada — usar o que existe):**
- T0 = `reverse_eng_fichas.status IN ('draft','extracted')` · `fase3_fichas.revisado=0`
- T1 = `status='aprovado'` OU `is_validated=1` OU `validated_fields_json` preenchido
- T2 = marca derivada: campo presente em T1 de ≥ 2 obras distintas (calculado, não digitado)

### 3.2 Gatilho de Indexação = Ato de Validação Humana

```
Item em T0 (draft)  ─────────────────────►  NÃO indexa. Fica em quarentena.
                                                    │
   humano clica "aprovar/validar" o item ───────────┤
                                                    ▼
Item vira T1  ───────────────────────────►  indexa AGORA esse item no RAG global
                                                    │
   campo validado em ≥ 2 obras ─────────────────────┤
                                                    ▼
Item/campo vira T2  ──────────────────────►  candidata a default/regra global
```

**Indexação é incremental e event-driven — NUNCA batch das fichas em desenvolvimento.**

### 3.2b Trava Anti-Validação Sintética / CLI

Nenhum looper, script, agente, batch, headless run ou validação sintética pode promover
T1/T2, indexar RAG global ou escrever "validação humana" por conta própria.

**Permitido ao CLI automático:**
- gerar candidato;
- calcular score;
- comparar N2/N4 ou N3/N4;
- gravar evento `machine_candidate`/`quarantine`;
- sugerir ação para o operador.

**Proibido ao CLI automático:**
- setar `status='aprovado'` como verdade;
- setar `is_validated=1`;
- chamar indexação global;
- desvalidar/tombstonar como humano;
- passar dado para o RAG global como professor.

Promoção efetiva exige proveniência explícita:

```
validation_origin = "human_ui"
```

Se a origem for ausente, `cli`, `script`, `looper`, `agent`, `auto`, `batch`,
`headless`, `synthetic` ou equivalente, o item permanece **T0/quarentena** mesmo que
o payload diga "aprovado". A regra é aplicada em `scripts/rag_tier.py`.

### 3.3 Distinção crítica: REGRA vs INSTÂNCIA

| Tipo | Exemplo | Pode entrar AGORA? | Onde mora |
|------|---------|---------------------|-----------|
| **REGRA / semântica** | `grade_1 = comprimento + 22`; "pilar cambotado é..." | ✅ SIM | `domain_knowledge` (LanceDB) + `semantic_rag_kb` |
| **INSTÂNCIA / ficha** | "P305 da obra X tem comp=240" | ❌ Só se T1+ | FAISS + Chroma (fichas) |

Regra é conhecimento que o **dono define e confirma** → estável → pode popular já.
Instância é **palpite do motor** → incerto → só entra após validação humana.

### 3.4 Consulta com filtro de tier

Durante o desenvolvimento, toda consulta ao RAG **filtra por `tier >= T1`**. O motor
nunca "aprende" de quarentena. Quarentena serve só para a Curadoria mostrar "o que está
pendente de validação" — é visibilidade, não conhecimento.

### 3.5 Regras de imutabilidade (herdadas dos masterplans existentes)

- `reverse_eng_fichas` (F5/N2) são **imutáveis**. Reextração → versiona via `status`,
  nunca sobrescreve. (Loop de Treino, Princípio 1)
- Dado humano validado **nunca é sobrescrito, apagado ou rebaixado**. (Princípio 7)
- N3 **nunca** é alimentado por N2/N4 (proibido vazamento de gabarito). (Princípio 9)
- Aprendizado grava em `engrev_*_learning.vision` / `training_events`, **nunca** em cima
  do gabarito.

### 3.6 Desvalidação Humana / Revogação de Conhecimento

Humano também pode dizer: "isso que estava validado não vale mais". Esse ato tem prioridade
máxima sobre o RAG.

**Recomendação:** não sobrescrever nem apagar silenciosamente. Usar **revogação lógica +
versionamento**, com limpeza física posterior.

| Estado | Significado | Consulta RAG global | Histórico |
|--------|-------------|---------------------|-----------|
| **TX / REVOGADO** | Era T1/T2, mas o humano desvalidou | ❌ Excluído imediatamente | Mantido para auditoria |
| **T0 / QUARENTENA** | Nova hipótese ainda não validada | ❌ Excluído | Mantido como hipótese |
| **T1 / VALIDADO** | Nova versão aprovada por humano | ✅ Incluído | Mantido como versão atual |

**Fluxo correto:**

```
Item T1/T2 validado ── humano desvalida ──► TX / REVOGADO
                                             │
                                             ├─ query global ignora imediatamente
                                             ├─ training_event registra motivo/proveniência
                                             ├─ filhos derivados viram "suspeitos" ou T0
                                             ▼
Nova correção humana ───────────────────► novo registro/versão T1
                                             │
                                             ▼
Indexa novo vetor; antigo continua revogado para auditoria
```

**Por que não sobrescrever direto?**
- Sobrescrever apaga a trilha de aprendizado e dificulta entender por que o motor errou.
- Vetores antigos podem existir em FAISS/Chroma; sem tombstone, podem continuar retornando.
- Auditoria humana precisa saber: quem validou, quem desvalidou, por quê, em qual obra/pav/item.

**Implementação recomendada:**
- Criar metadados/campos lógicos: `revoked_at`, `revoked_by`, `revoked_reason`,
  `superseded_by_id`, `version`.
- Criar tabela/evento: `rag_validation_events` ou usar `training_events` com tipo
  `human_invalidated`.
- Criar denylist/tombstone consultada por `rag_query.py`: se `id` está revogado, não retorna.
- Para Chroma, apagar/atualizar vetor se a API permitir, mas manter auditoria no SQLite.
- Para FAISS, não depender de delete in-place; usar tombstone na query e rebuild periódico
  dos índices para limpeza física.

**Regra de ouro:** desvalidar remove do RAG ativo imediatamente; corrigir cria nova versão
validada. Não existe "editar por cima" sem histórico.

### 3.7 Aprendizado de Recorte no Fluxo Reverso (separado de F5/N4)

No fluxo reverso, **aprovar manualmente um recorte valida somente o recorte**. Essa
validação é importante e deve ensinar o sistema a recortar melhor, mas ela **não** valida
a ficha extraída e **não** valida o DXF N4 gerado depois.

**O que a aprovação do recorte valida:**
- Geometria do recorte: bbox/polígono, escala, posição e margem.
- Classe do recorte: PIL/LV/FV/LAJ ou classe futura registrada.
- Contexto de origem: obra, pavimento, arquivo DXF, layer, cor, bloco/textos próximos.
- Qualidade visual: se o recorte contém o item inteiro e não mistura itens vizinhos.
- Perfil de recorte por classe: padrões de margem, vizinhança, layers relevantes e ruídos.

**O que ela NÃO valida:**
- Campos F5/N2 extraídos do recorte.
- Fórmulas, dimensões, nomes, grades ou dados semânticos.
- N4 gerado pelo robô reverso.
- Equivalência N2↔N4 ou N1↔N2.

**Fluxo correto:**

```
Recorte candidato T0 ── humano aprova recorte ──► CROP-T1 (recorte validado)
                                                   │
                                                   ├─ grava crop_learning_event
                                                   ├─ atualiza memória/modelo de recorte por classe
                                                   ├─ melhora sugestão de próximos recortes similares
                                                   └─ mantém F5/N2 como T0 até validação própria

F5/N2 extraída ── validação de campos ───────────► T1 de ficha/campos
N4 gerado ───── validação visual no CE ──────────► T1 de desenho robô reverso
```

**Implementação recomendada:**
- Criar/usar storage lógico `crop_learning_events` com: `obra`, `pavimento`, `classe`,
  `source_dxf`, `source_layer`, `source_color`, `bbox_json`, `polygon_json`,
  `margin_profile_json`, `nearby_entities_json`, `approved_by`, `approved_at`,
  `method_version`, `status`.
- O recortador deve consultar exemplos `CROP-T1` da mesma classe antes de sugerir novos
  recortes. Para classe nova, começa com perfil genérico e aprende conforme aprovações.
- A Curadoria deve mostrar "Memória de Recortes" separada de "Fichas Validadas": quantidade
  de recortes aprovados por classe, taxa de aceitação, rejeições, ajustes médios de margem
  e exemplos visuais.
- A desvalidação de um recorte aprovado deve revogar o `crop_learning_event` ativo via
  tombstone, exatamente como §3.6, sem apagar histórico.

**Regra de ouro:** recorte aprovado ensina **onde e como recortar**. Ficha/N2 aprovada
ensina **o que aquele item significa**. N4 aprovado ensina **se o robô desenhou certo**.
Misturar essas três validações contamina o aprendizado.

---

## 4. AS 8 DIMENSÕES DE COMPREENSÃO POR CLASSE

Para cada classe (PIL / LV / FV / LAJ — e futuras), o Cérebro RAG mantém compreensão em
8 dimensões. **Cada dimensão respeita a Política de Confiança (§3):** regras entram já;
instâncias só após validação.

```
CLASSE (ex: PIL — Pilar)
│
├── DIM-1: VISUAL ESTRUTURAL LIMPA       (N1/F7 canvas)          [instância: gated]
├── DIM-2: DESENHO DOS ROBÔS             (N3 de N1 / N4 de N2)   [instância: gated]
├── DIM-3: DADOS / FICHAS / CAMPOS       (F5=N2, F7=N1)          [instância: gated]
├── DIM-4: DESCRIÇÃO TEXTUAL/GEO/LÓGICA  (domain_knowledge)      [REGRA: já]
├── DIM-5: CONTEXTO OBRA/PAV/ITEM        (F1/F2/F3/F4)           [misto]
├── DIM-6: ENGENHARIA REVERSA            (N2/F5, motor_reverso)  [instância: gated]
├── DIM-7: VISUAL DXFs LAYERS/CORES      (stog_kbs)              [REGRA+inventário: já]
└── DIM-8: CORPUS GLOBAL TODAS AS OBRAS  (FAISS + knowledge_base)[só T1+ acumulado]
```

**Expansão:** nova classe (ex: Fundação, Escada) cria 8 dimensões idênticas — só o
conteúdo muda. O schema é fixo (ver EPIC RAG-6).

---

## 5. ARQUITETURA DO RAG — DOIS CONTEXTOS

### 5.1 RAG Global (Principal) — acumula só T1+

```
RAG GLOBAL  (serve apenas tier >= VALIDADO)
│
├── Store A: FAISS (corpus estrutural)        data/vectors/faiss/
│     all-MiniLM-L6-v2 (384-dim) · ~832 vetores atuais
│     Papel: similaridade textual de instâncias VALIDADAS
│
├── Store B: domain_knowledge (LanceDB)        DADOS-OBRAS/stog_rag_db/  ★ FONTE SEMÂNTICA
│     nv-embed-v1 (4096-dim) · 217 chunks (field_semantics=66)
│     Papel: REGRAS/fórmulas/significado → pode crescer AGORA
│
├── Store C: stog_kbs (LanceDB)                mesma instância
│     2179 rows (header/inventory/semantics/nomenclaturas)
│     Papel: inventário STOG por DXF (DIM-7) → factual, pode crescer
│
├── Store D: Chroma                            Restored-main/vector_memory/chroma.sqlite3
│     2282 embeddings · Python 3.12 FUNCIONA
│     Collections: adaptive_learning · structural_elements · training_samples
│     Papel: geometria espacial + learned_dx/dy → só de itens T1+
│
└── Bridge: semantic_rag_kb (SQLite)           project_data.vision · 0 rows ⚠️
      Papel: materializar semantic_ref por classe a partir do domain_knowledge
      É REGRA → pode (deve) popular AGORA
```

**Notas de harmonização (decisões a confirmar — §11):**
- ChromaDB **não** está morto: o doc RAG-VECTORIZACAO reportou falha no Python 3.14, mas
  a app roda em **3.12** e o Chroma tem 2282 embeddings vivos. **Manter** FAISS + Chroma
  (papéis complementares: FAISS=texto, Chroma=geometria).
- Dois modelos de embedding coexistem por design: nv-embed-v1 (regras) e MiniLM (fichas).

### 5.2 RAG por-Obra (Dinâmico, gerado ao abrir a obra)

Ajuda a **interpretar aquela obra específica**. Distinto do global. Pode incluir T0 da
**própria obra** (porque é contexto local de trabalho, não verdade global) — mas marcado
como local, e **nunca promovido ao global sem validação**.

```
RAG POR-OBRA  (escopo = 1 obra · script: scripts/obra_rag_pipeline.py)
├── F1 metadados · F2 pavimentos · F3 obra-global
├── N2/F5 dessa obra (gabarito local) · recortes visuais
└── stog_kbs dessa obra
```

**Persistência (recomendado):** `DADOS-OBRAS/{obra}/obra_rag/` para não recriar a cada
sessão. Recriar só quando a obra muda.

---

## 6. MAPEAMENTO RAG ↔ FICHAS F1–F9 (chave de tradução canônica)

| Ficha | Nível N | Dimensão | Store | Tier atual | Pode indexar agora? |
|-------|---------|----------|-------|-----------|---------------------|
| F1 Pré-Obra | — | DIM-5 | semantic_rag_kb | misto | regra: sim |
| F2 Pré-Pav | — | DIM-5 | semantic_rag_kb | misto | regra: sim |
| F3 Obra-Global | — | DIM-5/8 | FAISS | T0 (em dev) | não |
| F4 Pav×Classe | N4 cons. | DIM-6 | RAG por-obra | T0 | não |
| **F5 Granular ER** | **N2 GABARITO** | DIM-6/3 | Chroma+FAISS | **902: 765 draft + 137 extr + 3 aprov** | **só os 3 T1** |
| F6 Obra ER | N2 cons. | DIM-6 | RAG por-obra | T0 | não |
| **F7 Structural** | **N1 MOTOR** | DIM-1/3 | Chroma+FAISS | **405: 0 revisados** | **não** |
| F8 N3 (robô N1) | N3 | DIM-2 | FAISS+diff | T0 | não |
| F9 N4 (robô N2) | N4 | DIM-2 | FAISS+diff | T0 | não |

**Conclusão operacional:** hoje só **3 instâncias** podem entrar (golden seed). Tudo mais
espera validação. Mas **regras** (`domain_knowledge`/`semantic_rag_kb`) entram já.

---

## 7. REDESIGN DA ABA CURADORIA

A Curadoria é o **mapa mental vivo** do cérebro. **Começa read-only (observador)** — ela
**não escreve no RAG** → zero risco de contaminação. Conforme você valida nas outras abas,
você **vê o cérebro crescer** aqui.

**Faseamento obrigatório da Curadoria:**
- **Curadoria 2A — Observador:** todas as sub-abas leem dados e mostram tiers. Botões de
  escrita aparecem desabilitados ou como "requer RAG-0/RAG-1".
- **Curadoria 2B — Operações seguras:** depois de RAG-0/RAG-1 passarem nos gates, habilitar
  apenas ações seguras: [Popular Regras Agora] e [Indexar Validados Pendentes].
- **Curadoria 2C — Curadoria ativa:** só depois de RAG-3, pode mostrar ações de validação
  assistida; mesmo assim, validação humana continua sendo o gatilho.

### 7.1 Sub-abas (9 — pode criar mais)

```
CURADORIA
├── [1] Mapa RAG            ← pipeline visual do cérebro (read-only)
├── [2] Enciclopédia        ← 8 dimensões por classe (coração) (read-only)
├── [3] Corpus & Cobertura  ← heatmap F1-F9 + status de tier (read-only)
├── [4] Pendências          ← fila determinística de validação/harmonização (read-only)
├── [5] Memória de Recortes ← crop learning por classe, aceitação, rejeição e exemplos
├── [6] Aprendizado         ← convergência N1→N2, training_events, accuracy
├── [7] Pipelines de Treino ← ciclos CROP, N2→N4, N2↔N1 e N1→N3 por classe
├── [8] Memória Vetorial    ← status dos 4 stores + operações de manutenção
└── [9] Banco de Dados      ← tabelas SQLite + alertas (melhora do atual)
```

### 7.2 Sub-aba 1: MAPA RAG
Diagrama de pipeline interativo (QPainter/QSvgWidget). Nós clicáveis → painel com
nome/tecnologia/rows-vetores/última-atualização. Saúde por cor (verde/amarelo/vermelho).
**Mostra explicitamente a barreira de tier:** o que está em quarentena vs no cérebro.

```
DXF BRUTO → Structural Analyzer (N1/F7) ─┐
STOG Humano → Motor Reverso (N2/F5) ─────┤
                                          ▼
                              [ BARREIRA DE VALIDAÇÃO ]  ← só T1+ passa
                                          ▼
                   FAISS · Chroma · domain_knowledge · stog_kbs (RAG GLOBAL)
                                          ▼
                          RAG por-obra (ao abrir obra)
```

### 7.3 Sub-aba 2: ENCICLOPÉDIA DE CLASSES (coração)
Para cada classe, layout das 8 dimensões (ver §4). Seletor de classe + "+ Nova Classe".
Cada dimensão clicável abre detalhe. **Cada item exibido mostra seu tier** (badge:
quarentena/validado/consolidado). Score por classe = cobertura × qualidade das 8 dims.

```
┌─ CLASSE: PIL — Pilar ───────────────────────────[Score 72%]─┐
│ DIM-1 Visual N1 │ DIM-2 Visual Robô │ DIM-3 Campos da Ficha  │
│ [DXF canvas]    │ [N3/N4 PNG]       │ comp, larg, grade_1... │
│ DIM-4 Regras    │ DIM-5 Contexto    │ DIM-6 Eng.Reversa      │
│ grade_1=comp+22 │ 23 obras/92 pav   │ N2:225·aprov:3 [T1]    │
│ DIM-7 Layers STOG (CIMA/ABCD/GRADES)│ DIM-8 Corpus [histos]  │
└──────────────────────────────────────────────────────────────┘
```

### 7.4 Sub-aba 3: CORPUS & COBERTURA
Heatmap obras × fichas (F1/F2/F3/F5/F7/F8/F9), cor = % VALIDADO+indexado.
Painel de métricas com **separação por tier** (ex: "F5: 3 validados / 899 quarentena").
Botão **"Indexar Validados Pendentes"** → indexa só itens já T1 ainda não no RAG (seguro).
**NÃO** ter botão que indexe quarentena.

Estado inicial recomendado: botão visível, porém desabilitado até RAG-0 passar. Tooltip:
"Disponível após política de confiança e guarda de indexação".

### 7.5 Sub-aba 5: MEMÓRIA DE RECORTES
Dashboard específico do aprendizado de recorte, separado do RAG de fichas. Mostra, por
classe e por obra: recortes aprovados, rejeitados, revogados, taxa de aceitação, ajuste
médio de margem, layers mais úteis, falsos positivos frequentes e galeria visual de
exemplos CROP-T1. Deve permitir busca/inspeção, mas não promover ficha/campo.

### 7.6 Sub-aba 6: APRENDIZADO
Curva de convergência hit-rate N1 vs N2 por classe ao longo do tempo. Painel
`training_events` (901) por tipo/campo. Tabela `transformation_rules` com accuracy
(destacar LAJ=6.9%, PIL=32.8% em vermelho). Timeline de aprovações humanas.

### 7.7 Sub-aba 7: PIPELINES DE TREINO
Mapa mental visual dos procedimentos que levam uma classe ao estado ARETE. Esta aba é
read-only e mostra **como treinar**, não executa treino sozinha.

**Ciclos obrigatórios:**
- **CROP — recorte:** recorte aprovado alimenta `crop_learning_events` e melhora o
  detector/perfil de recorte por classe. Não valida F5/N2 nem N4.
- **A — N2 → N4:** F5/N2 validado + STOG humano são professor/juiz para motor reverso e
  gerador N4. Melhora extrator reverso, leitura de layers/campos e desenho N4.
- **B — N2 ↔ N1:** N2/F5 validado atua como professor externo do Structural Analyzer.
  Melhora interpretação N1 e conversão N1→ficha de robô.
- **C — N1 → N3:** N1 gera N3 sozinho. N4 validado julga o resultado. N3 nunca recebe
  dados de N2/N4 como entrada.
- **Notas humanas:** atenção, rejeição e decisão do operador viram memória auditável.
  Só viram regra global depois de validação/consenso.

**Conexão com RAG:** RAG não é o treinador. RAG é memória consultável e auditável:
regras, exemplos T1/T2, notas humanas, scores e histórico. Os loopers escrevem eventos
e evidências; consultas RAG leem apenas tiers confiáveis. T0 fica em quarentena; TX fica
revogado.

**Por classe:** LAJ/LV/FV já têm masterplans Arete documentados. PIL tem scripts/testes e
semântica, mas precisa consolidar `MASTERPLAN-ARETE-PILAR.md`. Classe nova só nasce
corretamente quando tiver CROP + A + B + C definidos antes de generalizar.

### 7.8 Sub-aba 8: MEMÓRIA VETORIAL
Card por store (FAISS/domain_knowledge/Chroma/semantic_rag_kb) com status, modelo,
contagem, última atualização, e ações: [Reindexar T1+] [Busca Manual] [Ver Vizinhos].
Card semantic_rag_kb destaca "0 rows — POPULAR" com botão [Popular Regras Agora].

Estado inicial recomendado: [Busca Manual] liberado; [Reindexar T1+] bloqueado até RAG-0;
[Popular Regras Agora] liberado após confirmação de que a origem é `domain_knowledge`.

### 7.9 Sub-aba 9: BANCO DE DADOS
Tabelas do `project_data.vision` com row counts ao vivo + alertas de integridade:
`semantic_rag_kb=0`, `cache_fichas=0`, `reverse_eng_fichas.rag_indexed=0`, accuracy baixa.
Preview top-10 por tabela. Export CSV/JSON.

---

## 8. FLUXO RETROALIMENTADO (com barreira de tier)

```
INGESTÃO → Structural Analyzer → N1/F7 ─┐
                                         ▼
                            COMPARISON ENGINE (N1 vs N2)
STOG → Motor Reverso → N2/F5 ────────────┘   │ sinal de treino → training_events
                                             │
                  [humano valida item] ──────┤
                                             ▼
                         BARREIRA DE TIER (só T1+)
                                             ▼
              INDEXA item no RAG GLOBAL (FAISS/Chroma) + regra no domain_knowledge
                                             ▼
       PRÓXIMO item similar → RAG sugere (consulta T1+) → humano confirma 1-clique
                                             ▼
                          aprendizado acelera (volante ganha inércia)
```

O fluxo reverso tem uma trilha adicional antes da ficha:

```
DXF humano/STOG → sugestão de recorte → HUMANO APROVA RECORTE
                                      │
                                      ├─ aprende crop por classe (CROP-T1)
                                      └─ F5/N2 continua T0 até validação de campos

F5/N2 validada por campos → T1 de ficha/campo → RAG global de instâncias
N4 validado no Comparison → T1 visual/robô reverso → memória de desenho gerado
```

Loop fecha quando **N1→N3 ≈ N4** sem usar N2 como input (só gabarito de validação).

---

## 9. EPICS — ORDEM REVISADA (v2.1)

> Ordem pensada para **risco crescente**: primeiro o que é seguro e dá visibilidade,
> por último o que toca o motor. Cada story: Arquivo · Ação · Entrada · Saída · Gate · NÃO-FAZER.

### EPIC RAG-0: Fundação de Confiança (P0 — primeiro de tudo)
**Objetivo:** instalar a Política de Confiança no código antes de indexar qualquer coisa.

- **RAG-0.1 — Helper de tier**
  - Arquivo: `scripts/rag_tier.py` (criar)
  - Ação: função `get_tier(ficha_row) -> 'T0'|'T1'|'T2'` lendo `status`/`is_validated`/
    `validated_fields_json` conforme §3.1. Função `is_indexable(row) -> bool` (T1+).
  - Saída: módulo importável por todos os scripts de indexação.
  - Gate: `python scripts/rag_tier.py --selftest` classifica corretamente os 3 aprovados
    (P1/P101/L308 = T1) e amostras draft (= T0).
  - NÃO-FAZER: não inventar coluna nova; derivar tier do que já existe no banco.

- **RAG-0.2 — Guarda de indexação**
  - Arquivo: `scripts/rag_ingestor.py` (editar — já existe)
  - Ação: toda função de ingestão chama `is_indexable()` antes de inserir. Se T0 → recusa
    e loga "QUARENTENA: {id} não indexável (tier T0)".
  - Gate: tentar indexar uma ficha draft → recusada com log; indexar P101 → aceita.
  - NÃO-FAZER: nenhum caminho de código pode inserir T0 no RAG global.

- **RAG-0.3 — Consulta filtrada por tier**
  - Arquivo: `scripts/rag_query.py` (editar)
  - Ação: parâmetro `min_tier='T1'` default em todas as queries do global.
  - Gate: query retorna só itens T1+.
  - NÃO-FAZER: não permitir query global sem filtro de tier.

- **RAG-0.4 — Tombstone / revogação humana**
  - Arquivo: `scripts/rag_tier.py`, `scripts/rag_query.py` e storage SQLite de eventos.
  - Ação: implementar estado `TX/REVOGADO`; toda query global deve excluir IDs revogados,
    mesmo que ainda existam vetores no FAISS/Chroma.
  - Gate: desvalidar P101 em ambiente de teste → query não retorna P101; evento
    `human_invalidated` fica registrado; revalidar nova versão cria novo ID/versão.
  - NÃO-FAZER: não sobrescrever o registro antigo sem `revoked_at`/evento; não confiar em
    delete físico do vector store como única proteção.

### EPIC RAG-1: Regras Semânticas Agora (P0 — seguro, valor imediato)
**Objetivo:** popular o que é REGRA (não instância) — destrava valor sem risco.

- **RAG-1.1 — Popular semantic_rag_kb a partir do domain_knowledge**
  - Status: **CONCLUÍDO em 2026-06-27** — 109 regras materializadas
    (`PIL=10`, `LV=43`, `FV=43`, `LAJ=13`).
  - Arquivo: `scripts/populate_semantic_rag_kb.py` (criado)
  - Ação: ler os 66 chunks `field_semantics` do `domain_knowledge` (LanceDB) e materializar
    em `semantic_rag_kb` (cols `classe/regra_semantica/obra_contexto/confianca`).
  - Entrada: `DADOS-OBRAS/stog_rag_db` · Saída: `semantic_rag_kb` ≥ 60 rows.
  - Gate: **PASSOU** — `SELECT COUNT(*) FROM semantic_rag_kb` = 109; consulta por classe
    retorna regras. Conferido que `reverse_eng_fichas.rag_indexed=0` e
    `fase3_fichas.revisado=0`.
  - NÃO-FAZER: não inventar regras; só espelhar o que está no domain_knowledge.

- **RAG-1.2 — Indexar golden seed (os 3 itens T1)**
  - Status: **AUDITADO em 2026-06-27 — sem candidatos T1/T2 pendentes**.
    `scripts/indexar_validados.py --dry-run` retornou 0 candidatos e
    `approved_unindexed=0`. Não aplicar `--apply` até nova validação humana criar item T1
    pendente de indexação.
  - Arquivo: `scripts/indexar_validados.py` (criar)
  - Ação: indexar SOMENTE itens T1 (hoje P1, P101, L308) no FAISS + Chroma, setar
    `rag_indexed=1` neles.
  - Gate: FAISS ganha exatamente os itens T1; nenhum T0 entra.
  - NÃO-FAZER: **não** iterar todas as 902; filtrar por `is_indexable()`.

### EPIC RAG-2: Curadoria-Observador (P0 — paralelo, read-only)
**Objetivo:** painel do cérebro sem escrever nada. Dá visibilidade do estado real.
**Status:** **BASE READ-ONLY VALIDADA em 2026-06-27** — métricas da Curadoria passam em
`tests/test_curadoria_rag_metrics.py`, sem escrita no DB; `project_manager.py` compila.
Fallback de `classe_registry` ajustado para suportar classe nova em registry de obra/teste.

> Arquivo da Curadoria: módulo da aba "Gerenciar Projetos" → seção CURADORIA em
> `Agente-cad-PYSIDE-Restored-main/src/ui/widgets/project_manager.py`.
> Todas as stories abaixo são **read-only sobre o DB**.

- **RAG-2.1** Sub-aba Mapa RAG (diagrama + barreira de tier visível). Gate: abre, mostra
  contagens reais por store. NÃO-FAZER: sem botão de escrita aqui.
- **RAG-2.2** Sub-aba Enciclopédia (8 dims por classe, badge de tier por item). Gate:
  exibe ≥ 1 classe com dados reais. NÃO-FAZER: não editar fichas a partir daqui.
- **RAG-2.3** Sub-aba Corpus & Cobertura (heatmap + métricas por tier + botão "Indexar
  Validados Pendentes" que chama RAG-1.2 só para T1). Gate: heatmap reflete DB.
  NÃO-FAZER: nenhum botão que indexe T0.
- **RAG-2.4** Sub-aba Pendências (classes sem T1/T2, taxonomias não canônicas,
  dimensões ausentes e memória legada T0). Gate: achados são derivados de dados reais.
  NÃO-FAZER: não corrigir, promover ou indexar automaticamente a partir desta fila.
- **RAG-2.5** Sub-aba Aprendizado (training_events + accuracy + convergência). Gate:
  a contagem exibida coincide com `SELECT COUNT(*) FROM training_events`.
- **RAG-2.6** Sub-aba Pipelines de Treino (CROP, A: N2→N4, B: N2↔N1, C: N1→N3,
  notas humanas e cobertura por classe). Gate: mostra ciclos e docs/scripts reais sem
  executar treino. NÃƒO-FAZER: nenhum botão que rode looper, promova regra ou indexe dado.
- **RAG-2.7** Sub-aba Memória Vetorial (cards + [Reindexar T1+] + [Popular Regras]). Gate:
  cards mostram contagem viva dos 4 stores.
- **RAG-2.8** Sub-aba Banco de Dados (tabelas + alertas). Gate: alertas disparam nos casos
  reais (semantic_rag_kb=0 antes de RAG-1.1, etc.).

### EPIC RAG-3: Indexação por Validação — Event-Driven (P1)
**Objetivo:** ligar gatilhos humanos corretos, separando recorte, ficha/campo e desenho.
Cada validação alimenta somente o canal que ela realmente valida.

**Status auditado em 2026-06-27:** infraestrutura humana/anti-sintética operacional,
com 20 testes focados aprovados (6 no app + 14 no RAG raiz). O EPIC permanece
**PARCIAL** porque validação granular F5/N2, indexação por artefato N1/N3/N4 e
promoção T1→T2 ainda não estão completas.

- **RAG-3.1 — Hook de aprendizado de recorte no Diagnostic Reverse Hub**
  - Status: **BACKEND CONCLUÍDO; smoke visual pendente.**
  - Arquivo: `src/ui/modules/diagnostic_reverse_hub.py`
  - Ação: ao aprovar/validar recorte → registrar `crop_learning_event` com bbox/polígono,
    classe, obra/pavimento, DXF/layer/cor de origem, entidades próximas, margem e versão
    do método de recorte. Atualizar memória/modelo de recorte por classe.
  - Gate: aprovar 1 recorte → evento de recorte gravado, exemplo aparece na Curadoria,
    próxima sugestão da mesma classe consegue consultar esse exemplo.
  - NÃO-FAZER: não chamar `indexar_validados.py` para a F5 por causa do recorte. Não
    promover F5/N2 para T1. Não validar N4. Não reindexar obra inteira.
  - Revogação: excluir/desvalidar o recorte chama
    `revoke_crop_learning_events_for_recorte()`. O exemplo deixa de ser ativo,
    permanece auditável como `revoked` e não ensina mais o detector.

- **RAG-3.1b — Validação explícita de campos F5/N2**
  - Status: **FICHA COMPLETA CONCLUÍDA; CAMPO A CAMPO PENDENTE.** Não confundir
    com o botão de aprovar recorte. A aba F5 mostra T0/T1/TX e exige confirmação
    explícita em `Validar F5`. `Revogar F5` exige motivo humano.
  - Arquivo: `src/ui/modules/diagnostic_reverse_hub.py` e/ou tela granular F5.
  - Ação: somente quando o humano validar os campos da ficha N2/F5, marcar campos/versão
    como T1 e então chamar `indexar_validados.py` para aquela ficha/campos.
  - Gate: aprovar campo/ficha F5 → item/campo entra no RAG global; aprovar apenas recorte
    não altera tier da F5.
  - NÃO-FAZER: não inferir validação de campo a partir de recorte aprovado.
  - Integridade: F5 T1 é imutável. Reextração só altera ficha draft/revogada e
    sempre redefine `rag_indexed=0`. A nova versão recebe ID vetorial derivado
    do conteúdo; tombstones da versão antiga permanecem ativos.

- **RAG-3.2 — Hook de validação no Comparison Engine**
  - Status: **MEMÓRIA, RENDER, GALERIA E HISTÓRICO N3/N4 CONCLUÍDOS; EMBEDDINGS PENDENTES.**
    Evento humano e proveniência estão conectados. N3/N4 são registrados em
    `rag_artifact_validations` pelo hash da versão do DXF. Falta gerar embeddings
    visuais e formalizar memória equivalente para N1/N2 campo a campo.
  - Render: `scripts/dxf_artifact_renderer.py` gera PNG fixo 1024x768 e manifesto
    em `data/artifact_memory/{scope}/{classe}/{hash[:2]}/{hash}.png|json`.
  - Curadoria: `Pipelines de Treino` exibe miniaturas validadas e histórico
    validado/revogado; duplo clique apenas abre o render e não altera o RAG.
  - Arquivo: `src/ui/modules/comparison_engine.py`
  - Ação: aprovar match/score N1 vs N2, N3 ou N4 → `training_event` específico do nível
    validado e indexação somente do artefato validado.
  - Gate: aprovação N3 alimenta memória visual/robô N3; aprovação N4 alimenta memória
    visual/robô reversa; aprovação N1↔N2 alimenta equivalência/campo. Cada evento preserva
    proveniência.
  - NÃO-FAZER: N3 nunca recebe campos de N2/N4 (Princípio 9, anti-vazamento).
  - Revogação: desmarcar validação atualiza apenas a versão/hash carregada,
    cria tombstone e preserva a linha auditável como `revoked`.

- **RAG-3.2b — Hook de desvalidação humana**
  - Status: **OPERACIONAL PARA COMPARISON, RECORTE E F5 COMPLETA.** Comparison
    gera TX/tombstone do evento validado, recortes revogam seus exemplos e F5
    completa pode ser revogada com motivo. Revogação campo a campo permanece
    dependente do schema canônico por classe.
  - Arquivo: `src/ui/modules/comparison_engine.py` e
    `src/ui/modules/diagnostic_reverse_hub.py`
  - Ação: botão/ação "Desvalidar" em item T1/T2 marca TX, registra motivo, remove da
    elegibilidade de query RAG e dispara atualização da Curadoria.
  - Gate: item desvalidado some de buscas globais e aparece na Curadoria como revogado.
  - NÃO-FAZER: não apagar histórico; não rebaixar silenciosamente para draft sem evento.

- **RAG-3.3 — Promoção T1 → T2**
  - Status: **PENDENTE.**
  - Arquivo: `scripts/promover_consolidado.py` (criar)
  - Ação: campo/padrão validado em ≥ 2 obras → marca T2 → candidata a default global.
  - Gate: padrão presente em 2 obras T1 vira T2; em 1 obra permanece T1.
  - NÃO-FAZER: não promover com 1 obra só (Princípio 4 — generalização gated).

### EPIC RAG-4: RAG Consulta no Structural Analyzer (P1 — o acelerador)
**Objetivo:** o RAG passa a SUGERIR durante a interpretação (read-only, filtrado T1+).

- **RAG-4.1 — "Análise com Eng. Reversa" consulta RAG por-obra + global**
  - Status: **CONSULTA GLOBAL E LOCAL READ-ONLY CONCLUÍDA; SUGESTÃO ASSISTIDA PENDENTE.**
    `rag_context_service.py` consulta regras e exemplos globais T1/T2 em modo
    read-only e `obra_rag_query.py` consulta o manifest local com ranking lexical
    determinístico. Resultados locais, inclusive T0, são rotulados `obra_local` e
    `is_global_truth=false`. A aplicação de sugestões com confirmação humana
    continua pendente.
  - Arquivo: localizar pontos reais com `rg "Análise Geral|Structural Analyzer"`; hoje os
    pontos principais estão em `Agente-cad-PYSIDE-Restored-main/src/ui/modules/comparison_engine.py`,
    `Agente-cad-PYSIDE-Restored-main/src/ui/modules/diagnostic_hub.py` e helpers em
    `Agente-cad-PYSIDE-Restored-main/src/core/analysis_helpers.py`. Integrar também
    `Agente-cad-PYSIDE-Restored-main/scripts/obra_rag_pipeline.py`.
  - Ação: botão consulta gabarito N2 da obra + similares T1 do global; exibe sugestão
    de campos com nível de confiança. Nunca escreve, nunca gera DXF.
  - Gate: selecionar item → painel mostra "similar a P101 (T1, 94%)" + campos sugeridos.
  - NÃO-FAZER: não autocompletar sem confirmação humana; "Análise Geral" não muda.

- **RAG-4.2 — RAG por-obra automático ao abrir obra**
  - Status: **SNAPSHOT E RETRIEVAL LEXICAL LOCAL CONCLUÍDOS; EMBEDDING LOCAL OPCIONAL PENDENTE.**
    O botão `Atualizar Obra (DB + RAG Local)`
    executa `scripts/obra_rag_pipeline.py` em background e grava
    `DADOS-OBRAS/{obra}/obra_rag/manifest.json`. O snapshot admite T0 apenas
    como contexto local e declara `promotion_policy=never_auto_global`.
    A seleção de obra também atualiza esse manifest silenciosamente via
    `QProcess`. `scripts/obra_rag_query.py` já torna o manifest consultável sem
    escrita; retrieval vetorial local fica como otimização futura, não bloqueio.
  - Arquivo: `scripts/obra_rag_pipeline.py` + signal de obra no `main.py`
  - Ação: selecionar obra no top bar → gera/carrega `DADOS-OBRAS/{obra}/obra_rag/`.
  - Gate: log "RAG por-obra carregado em Xms"; indicador na top bar.
  - NÃO-FAZER: por-obra não promove nada ao global automaticamente.
  - Evidência 2026-06-27: `Obra_TREINO_3` materializada com 1 projeto,
    391 documentos, 2 recortes de engenharia reversa, 2 recortes de obra,
    109 regras semânticas e 0 fichas F5; nenhum tier global foi criado.

### EPIC RAG-5: Loop de Treino fecha (P1 — depois de RAG-3)
**Objetivo:** divergências viram aprendizado; accuracy sobe.

- **RAG-5.1** Mapa de Equivalência de Vocabulário N1↔N2 **derivado do domain_knowledge**
  (resolve GAP #V do Loop de Treino). Arquivo: `scripts/vocab_equivalence.py` (criar).
  Gate: mapeia ≥ 90% dos campos PIL/LV/FV/LAJ. NÃO-FAZER: não hardcodar à mão.
- **RAG-5.2** Retraining de `transformation_rules` com os 901 `training_events` (só T1+).
  Gate: accuracy ≥ 70% em PIL/LV/FV/LAJ. NÃO-FAZER: não treinar com T0.
- **RAG-5.3** Sub-aba Aprendizado mostra a curva subindo em tempo real.

### EPIC RAG-6: Expansão para Novas Classes (P2 — futuro, deixar preparado)
**Objetivo:** plugar nova classe sem mexer no código central.

- **Status:** **INFRAESTRUTURA PLUGÁVEL CONCLUÍDA; PRIMEIRA NOVA CLASSE AGUARDA DEFINIÇÃO HUMANA.**
- **RAG-6.1** `data/classe_registry.json` declarativo (metadados + 8 dims template),
  validado por `scripts/classe_registry.py`.
- **RAG-6.2** Enciclopédia lê do registry (nova classe sem recompilar).
- **RAG-6.3** `scripts/motor_reverso_base.py` obriga toda extração nova a nascer T0.
- **RAG-6.4** `data/robo_registry.json` + `scripts/robo_registry.py` mapeiam e auditam
  extratores e robôs de PIL/LV/FV/LAJ sem executá-los.
- Gate: adicionar "Fundação" sem alterar PIL/LV/FV/LAJ. NÃO-FAZER: não acoplar classes.

### Operação segura do RAG

- `scripts/rag_health.py`: diagnóstico read-only de banco, stores FAISS, snapshots
  locais e memória visual.
- `scripts/rag_export.py`: exporta tabelas de conhecimento/eventos, manifests,
  tombstones e registros com SHA-256. O pacote declara `is_global_truth=false`.
- Essas ferramentas não indexam, promovem, treinam nem desvalidam informações.

---

## 10. SEQUÊNCIA DE EXECUÇÃO (risco crescente)

```
1º  RAG-0 (fundação de confiança)        ← protege tudo. NÃO indexa nada ainda.
2º  RAG-1 (regras agora)                 ← seguro, valor imediato (sem instâncias)
3º  RAG-2 (Curadoria observador)         ← read-only, visibilidade do estado
        │ (a partir daqui você VÊ o cérebro e pode validar com confiança)
4º  RAG-3 (indexação por validação)      ← liga o gatilho event-driven
5º  RAG-4 (consulta no Structural)       ← o acelerador (sugestão durante trabalho)
6º  RAG-5 (loop de treino fecha)         ← convergência N1→N2, accuracy sobe
7º  RAG-6 (novas classes)                ← futuro
```

### 10.1 Squads / Donos por Frente

| Frente | Dono institucional | Responsabilidade |
|--------|--------------------|------------------|
| Planejamento e gates | `CEO-PLANEJAMENTO` / Athena | Manter este masterplan, qualidade, sequência e critérios de aceite. |
| Dados / pipelines / métricas | `CEO-DATA`, `DadosSquad-AIOS`, `DataEngineer-AIOS` | Tiers, ingestão, contagens, qualidade de dados, scripts de materialização. |
| RAG / embeddings / retrieval | `RAGForge-AIOS`, `CeoData-AIOS` | FAISS, Chroma, LanceDB, `semantic_rag_kb`, filtros de tier e queries. |
| CAD Analyzer / app PySide | `CEO-CAD-ANALYZER`, `Dev-AIOS` | Integração nas abas, signals, botões, UX operacional, não quebrar fluxo existente. |
| Compreensão de desenhos estruturais | `Architect-AIOS`, `Analyst-AIOS`, especialistas ARETE por classe | Harmonizar N1/N2/N3/N4, regras por classe, validação contra N2 real e robôs. |
| QA / evidência | `QA-AIOS` | Testes, smoke da UI, regressão de Comparison Engine, Diagnostic Hub e robôs. |
| DevOps / ambiente | `DevOps-AIOS` | Dependências Python, stores vetoriais, scripts reprodutíveis, caminhos e variáveis. |

**Handoff correto:** este plano sai de Athena para `@po/@sm` quebrar em stories formais,
depois `@dev` implementa, `@qa` valida e `@devops` publica/automatiza. Não pular PO/SM.

---

## 11. DECISÕES PENDENTES (VALIDAR COM O DONO ANTES DE EXECUTAR)

1. **RAG por-obra pode incluir T0 da própria obra?** Recomendação: sim, mas marcado
   "local", nunca promovido ao global sem validação. Confirmar.
2. **Persistir RAG por-obra** em `DADOS-OBRAS/{obra}/obra_rag/`? Recomendação: sim.
3. **Manter FAISS + Chroma** (papéis distintos)? Recomendação: manter ambos.
4. **Dois modelos de embedding** (nv-embed-v1 regras / MiniLM fichas)? Recomendação: manter.
5. **F5 com comp/larg inconsistentes (LAJ 5/98):** coordenada vence (Princípio 2). Confirmar.
6. **Enciclopédia exibe T0?** Recomendação: sim, com badge "quarentena" — visibilidade
   não é contaminação (não entra no global). Confirmar.

---

## 12. DOCUMENTAÇÕES — ALINHAR / HARMONIZAR / CRIAR

### 12.1 Alinhar (estão certas, citar como fonte — não reescrever)
| Doc | Papel |
|-----|-------|
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-FICHAS-F1-F9-HARMONIZACAO.md` | Schema canônico F1-F9 + banco real |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-LOOP-TREINO-MOTOR.md` | Princípios inegociáveis 1-10 (base da §3.5) |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-ENGENHARIA-REVERSA.md` | Definição N1/N2/N3/N4 + EPICs ER |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-ARETE-QUALITY-GATES.md` | Regra de Ouro (motor universal) + gates |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-ARETE-LAJE.md` | Ciclos ARETE da Laje: N2→N4, N2↔N1 e N1→N3. |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-ARETE-LATERAL-VIGA.md` | Ciclos ARETE da Lateral de Viga, incluindo VC/lados A/B e subdivisões visuais. |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-ARETE-FUNDO-VIGA.md` | Ciclos ARETE do Fundo de Viga, render/loop e validação visual. |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-LOOP-LV-N2-VISION-N4.md` | Looper específico LV N2→visão→N4; alinhar com a aba Pipelines de Treino. |
| `Agente-cad-PYSIDE-Restored-main/docs/LV-COMPREENDER-INTERPRETACAO-FICHAS-N2-N4.md` | Exemplo vivo de compreensão por classe; usar como referência de formato, não como verdade universal. |
| `Agente-cad-PYSIDE-Restored-main/docs/DESIGN-SYSTEM-PYSIDE.md` | Base visual para Curadoria, Comparison Engine e Structural Analyzer. |

### 12.2 Harmonizar (têm conflito/desatualização — ajustar nota de reconciliação)
| Doc | Ajuste necessário |
|-----|-------------------|
| `docs/MASTERPLAN-RAG-VECTORIZACAO.md` | Corrigir "ChromaDB abandonado": vale p/ Py3.14; em Py3.12 está vivo (2282 emb). Adicionar nota. |
| `docs/MASTERPLAN-RAG-INTEGRACAO-COMPLETA.md` | As 8 frentes assumem indexação ampla — adicionar que toda frente respeita barreira de tier (§3). |
| `MASTERPLAN-SEMANTICO-v1.0.md` | Sprint B (KB global) e Sprint C (accuracy) devem usar só T1+ — alinhar com §3. |
| `MASTERPLAN-GERENCIAR-PROJETOS-v5.0.md` | Seção Curadoria estava ausente/obsoleta — referenciar este doc para o redesign (§7) e mapear a aba real em `Agente-cad-PYSIDE-Restored-main/src/ui/widgets/project_manager.py`. |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-CAD-ANALYZER.md` | Já fala de RAG global/por-obra e Comparison Engine; adicionar nota de que retroalimentação global só ocorre por validação humana T1+. |
| `Agente-cad-PYSIDE-Restored-main/CLAUDE.md` | Ajustar nota de ChromaDB: incompatibilidade com Python 3.14 não significa remover Chroma da app em Python 3.12. |

### 12.3 Criar (novos — parte da execução)
| Doc a criar | Conteúdo | Quando |
|-------------|----------|--------|
| `Agente-cad-PYSIDE-Restored-main/docs/POLITICA-CONFIANCA-RAG.md` | Extrair §3 deste plano como doc autônomo de referência | EPIC RAG-0 |
| `Agente-cad-PYSIDE-Restored-main/docs/SEMANTICA-CANONICA-PIL.md` | Regras de campo do Pilar validadas com o dono | EPIC RAG-4/5 |
| `Agente-cad-PYSIDE-Restored-main/docs/SEMANTICA-CANONICA-LV.md` | Idem Lateral de Viga; pode partir do doc LV existente, mas só após validação. | idem |
| `Agente-cad-PYSIDE-Restored-main/docs/SEMANTICA-CANONICA-FV.md` | Idem Fundo de Viga | idem |
| `Agente-cad-PYSIDE-Restored-main/docs/SEMANTICA-CANONICA-LAJ.md` | Idem Laje | idem |
| `Agente-cad-PYSIDE-Restored-main/docs/ENCICLOPEDIA-SCHEMA.md` | Schema das 8 dimensões + template de nova classe | EPIC RAG-2.2 / RAG-6 |
| `Agente-cad-PYSIDE-Restored-main/docs/CURADORIA-UI-SPEC.md` | Spec detalhada das 9 sub-abas (wireframes + dados) | EPIC RAG-2 |
| `Agente-cad-PYSIDE-Restored-main/docs/TRAINING-PIPELINES-SPEC.md` | Contrato visual/operacional da aba Pipelines de Treino: CROP, A, B, C, notas humanas e gates. | EPIC RAG-2.6 |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-ARETE-PILAR.md` | Consolidar o loop PIL em documento canônico A/B/C; hoje está espalhado em semântica, testes e scripts. | Antes de escalar PIL |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-ARETE-NOVA-CLASSE-TEMPLATE.md` | Template para atingir ARETE com classe nova: registry, recorte, N2→N4, N2↔N1, N1→N3, gates e anti-vazamento. | EPIC RAG-6 |
| `Agente-cad-PYSIDE-Restored-main/docs/CROP-LEARNING-SPEC.md` | Contrato do aprendizado de recorte: CROP-T1, eventos, métricas, revogação e separação de F5/N4. | EPIC RAG-3.1 |
| `Agente-cad-PYSIDE-Restored-main/docs/RAG-POR-OBRA-SPEC.md` | Contrato entre RAG global e RAG por-obra, persistência, T0 local e promoção bloqueada. | EPIC RAG-4.2 |
| `Agente-cad-PYSIDE-Restored-main/docs/RAG-REVOGACAO-HUMANA-SPEC.md` | Desvalidação humana, tombstones, versionamento, limpeza física e rebuild FAISS/Chroma. | EPIC RAG-0.4 / RAG-3.2b |
| `Agente-cad-PYSIDE-Restored-main/docs/HANDOFF-CEREBRO-RAG-MULTIMODAL.md` | Resumo executivo para @dev/@qa com ordem de stories, gates e NÃO-FAZER. | Antes da execução |

### 12.4 Nota de harmonização documental

Não apagar nem reescrever masterplans antigos em massa. Cada documento harmonizado deve
receber no topo uma nota curta:

> "Este documento é preservado como fonte histórica/técnica. Para política de confiança,
> anti-contaminação e ordem de execução do Cérebro RAG Multimodal, prevalece
> `MASTERPLAN-CEREBRO-RAG-MULTIMODAL-v1.0.md` v2.3."

---

## 13. MÉTRICAS DE SAÚDE (com tier)

| Métrica | Atual | Meta | Observação |
|---------|-------|------|------------|
| Instâncias T1 indexadas | 0 | cresce por validação | auditoria real em 2026-06-27; não presumir golden seed |
| semantic_rag_kb (regras) | 109 | ≥ 60 | RAG-1.1 concluído em 2026-06-27; só regras, sem instâncias |
| Itens em quarentena (T0) | 1649 | diminui ao validar | F5/N2=906 + F7/N1=743 |
| Itens revogados (TX) | 0 | auditável | não retornam no RAG ativo |
| Recortes CROP-T1 | 0 | cresce por aprovação | aprende a recortar por classe, sem validar F5 |
| Taxa de aceite de recortes | não medida | subir por classe | qualidade do crop detector |
| FAISS vetores visíveis (T1+) | 0 | cresce gated | 747 metadados legados estão T0 |
| Chroma embeddings elegíveis T1+ | não auditado | cresce gated | legado não pode responder como professor sem proveniência |
| Accuracy PIL / LAJ | 32.8% / 6.9% | ≥ 70% | RAG-5.2, só T1 |
| Hit-rate N1 vs N2 | não medido | ≥ 95% | Comparison Engine |
| RAG por-obra gerado | 2 | sob demanda | RAG-4.2; snapshots locais válidos em 2026-06-27 |
| Artefatos N3/N4 humanos | 0 | cresce por validação | correto: sem backfill sintético |
| Health RAG | OK | OK | diagnóstico read-only em 2026-06-27 |

---

## 14. O QUE NÃO MUDAR (PROTEGIDO)

| Protegido | Por quê |
|-----------|---------|
| Schema N1 (Structural Analyzer) | Decisão inegociável (ARETE doc) |
| Fichas F5 (`reverse_eng_fichas`) | Gabarito imutável — versionar por status |
| Validações humanas (`is_validated=1`) | Princípio 7 |
| N3 isolado de N2/N4 | Princípio 9 (anti-vazamento) |
| Geradores STOG (PL/LV/FV/LJ) | 23 obras certificadas |
| domain_knowledge LanceDB | Fonte semântica — expandir, nunca substituir |
| "Análise Geral" (motor puro) | Tem que aprender sozinho — não recebe sugestão do RAG |

---

## 15. DEFINITION OF DONE DO PLANO

Este masterplan está pronto para execução quando:

- A política de confiança (§3) estiver extraída para doc próprio e citada pelos docs RAG.
- RAG-0 estiver implementado e testado antes de qualquer indexação de instâncias.
- Curadoria 2A abrir como observador e mostrar tiers/contagens reais sem escrever no RAG.
- `semantic_rag_kb` estiver populada a partir de regras, não de fichas draft.
- Golden seed T1 (P1/P101/L308) estiver indexado com evidência de que nenhum T0 entrou.
- Aprovação humana em Diagnostic Reverse Hub e Comparison Engine gerar evento e indexação
  incremental de um único item.
- Aprovação de recorte no Diagnostic Reverse Hub gerar `crop_learning_event` e alimentar
  memória de recortes, sem promover F5/N2, sem validar campos e sem validar N4.
- Structural Analyzer tiver consulta assistida por RAG em modo sugestão, sem alterar
  "Análise Geral".
- QA tiver smoke das abas afetadas e teste automatizado mínimo para `rag_tier`,
  `rag_ingestor`, `rag_query` e hooks de validação.
- Nenhum executor conseguir encontrar caminho de código que insira T0 no RAG global.
- Nenhum item revogado (`TX`) retornar em consulta RAG global, mesmo antes da limpeza física
  dos índices vetoriais.

**Scorecard Athena estimado do plano:** Segurança 9, UX 8, Performance 7, Escalabilidade 8,
Manutenibilidade 8, Testabilidade 8, Time-to-market 7, Custo 7. Média ponderada ≥ 7.0.

---

*MASTERPLAN-CEREBRO-RAG-MULTIMODAL v2.3 — anti-contaminação · RAG gated por validação · crop learning*
*Athena (CEO-Planejamento) × Diana Corporação Senciente × 2026-06-26*
