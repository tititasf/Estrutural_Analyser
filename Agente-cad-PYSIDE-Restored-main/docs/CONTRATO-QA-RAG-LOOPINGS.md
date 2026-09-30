# Contrato QA ↔ RAG ↔ Loopings Arete

**Status:** contrato operacional da Fase 2 LAJ.  
**Agentes:** um Agente QA Global (auditor/executor assistido) e o RAG da aplicação (memória consultiva).

## 1. Objetivo

O QA executa o looping canônico com disciplina de evidência; o RAG preserva e
recupera conhecimento curado. Eles convergem para reduzir repetição de análise,
não para aumentar automaticamente a autoridade do QA.

Microciclos iterativos persistem em `qa_loop_executor.py`. Uma resposta humana a
uma dúvida estrutural é registrada por `teach` com regra, exemplos, exceções, escopo
e evidência. Isso cria material candidato T1, ainda sem promoção: primeiro a regra
deve ser codificada como fórmula geral, testada e reverificada no artefato/visão.

```text
QA lê item atual + evidências CAD/DB/HTML/visual
  → consulta RAG particionado e citado
  → decide: confirmar / pendente / corrigir / revisar humano
  → executa microciclo canônico de reverificação quando há causa
  → humano confirma resultado e promove conhecimento
  → RAG disponibiliza T1/T2 a futuras sessões QA
```

## 2. Responsabilidades

| Parte | Pode | Não pode |
|---|---|---|
| QA | investigar campo/vínculo, comparar fontes, abrir achado, propor fix universal, solicitar/rerodar microciclo, medir confiança | usar RAG como prova única, editar N2/Fase-4, selar por semelhança |
| RAG | recuperar regras, exemplos, antipadrões e decisões curadas por escopo | inferir dado do item atual, aplicar alteração, emitir selo |
| Dono | aprovar regra, exceção e promoção de evidência; dar veredito visual final | ser substituído por score ou consenso estatístico |
| Motor/executor | corrigir causa geral e produzir nova geração | fazer hardcode por item/obra/pavimento |

## 3. Protocolo de consulta

Antes de qualquer decisão não trivial, o QA monta a consulta com:

```json
{
  "classe": "LAJ|FV|PIL|LV",
  "subclasse": "familia_de_campo",
  "campo": "identificador do campo",
  "obra": "contexto da obra",
  "pavimento": "contexto do pavimento",
  "item": "alvo atual",
  "pergunta": "hipótese a verificar, não conclusão",
  "fontes_locais": ["N1 persistido", "DXF", "ficha HTML", "N1-V/G2-V"]
}
```

O RAG deve responder somente entradas compatíveis com classe/campo e anexar:
`tier`, `fonte`, `obra_contexto`, `confianca`, `regra_semantica` e identificação
da entrada. A tabela atual `semantic_rag_kb` contém a memória semântica; a
validação de artefatos é rastreada em `rag_artifact_validations`; decisões humanas
podem ser promovidas por eventos em `human_event_logs`.

Se a entrada RAG divergir do CAD/ficha do item atual, o QA registra conflito e
o item permanece pendente. RAG não desempata coordenada, nível ou geometria.

Na implementação atual, o QA consulta `semantic_rag_kb` com
`review --rag-evidence auto` e grava as entradas efetivamente consultadas em
`rag_consultas.jsonl` no dossiê da sessão. `--rag-evidence required` falha
fechado se a classe não tiver memória; a ausência de `tier` no schema atual faz
com que toda entrada permaneça apenas contextual até a curadoria T1/T2.

## 4. Protocolo de devolução para o RAG

O QA não escreve conhecimento diretamente no tier confiável. Ao fechar uma
sessão, ele produz um **candidato de curadoria** com:

```json
{
  "classe": "LAJ",
  "familia": "laje_visao_corte",
  "campo": "neighbor_dist_bottom",
  "regra_proposta": "texto universal sem ID de item",
  "evidencias": ["caminho+hash de DXF/HTML/PNG", "decisão QA"],
  "resultado_visual": "pass|fail|na",
  "escopo": {"obra": "...", "pavimento": "...", "itens": ["..."]},
  "confianca": 0.0,
  "tier_candidato": "T1|T2|T3",
  "requer_aprovacao_humana": true
}
```

Regras de promoção:

- **T1:** decisão/evidência humana explícita e rastreável;
- **T2:** regra determinística reproduzida com golden e regressão;
- **T3:** hipótese/achado útil, nunca usado para confirmar campo;
- revogação humana ou regressão remove a entrada da consulta confirmatória e
  preserva seu histórico.

## 5. Autoridade progressiva do QA

O QA só pode preparar/aplicar validação de um campo quando todos forem verdade:

1. contrato de proveniência da família existe;
2. o item atual tem evidência local independente;
3. não há divergência N1/N2/N3/N4 aplicável, nem conflito com RAG T1/T2;
4. o microciclo e N1-V/G2-V exigidos passaram;
5. score da sessão é alto e a regra já foi aprovada em casos representativos;
6. a classe/adaptador foi promovido explicitamente e o humano autorizou o `apply`.

Uma dessas condições ausente rebaixa a decisão para `PENDENTE`, `CORRIGIR` ou
`REVISAR_HUMANO`. O QA nunca transforma volume de confirmações em autoridade.

## 6. Fase 2 LAJ — primeira convergência

1. QA revisa pendências LAJ, começando por visão de corte, níveis, apoios e vizinhos.
2. Para cada achado, abre causa universal e usa o microciclo por item/conjunto.
3. Após correção, registra antes/depois, render N1-V e resultado de cálculo.
4. Dono confirma a regra e o caso; o QA prepara candidato T1/T2 com hashes.
5. Curador RAG aprova/rejeita o candidato; o QA passa a citá-lo em casos futuros.
6. Nova obra/pavimento prova generalização. Falha reabre a regra e pode revogá-la.

Os documentos de execução são `LOOPING-CANONICO.md` e
`ARETE-LOOP-PROCEDIMENTO-GERAL.md`; este contrato não cria outro entry point.
