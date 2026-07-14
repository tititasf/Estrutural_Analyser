# QA Global de Evidências

Squad AIOS do QA Arete. O orquestrador escolhe o microciclo por nível e delega a
semântica a adaptadores de classe. A implementação operacional continua nos scripts
canônicos do repo; esta squad formaliza roteamento, gates, dossiês e autoridade.

Ativação: `/CAD:QAGlobalEvidencias-AIOS *loop --obra ... --pav ... --classe ... --nivel ...`

Arquitetura: uma squad, um orquestrador, tasks determinísticas e zero entry point
alternativo para headless, geração ou visão.

Fast paths v1.2: perfis executáveis por classe, probe N1 limitado a campos/checks,
allowlists semânticas FV/LV, smoke N3 por contrato/variante,
paridade declarativa contrato→payload→DXF→HTML, render cacheado por conteúdo e
RAG particionado com degradação explícita. Esses caminhos aceleram diagnóstico;
não aprovam ficha/item nem substituem gate visual.

Retomada operacional: `scripts/arete/qa_loop_executor.py`. Para PIL, cobertura por
famílias e probes cross-classe: `scripts/arete/qa_pil_coverage.py`. O executor avança
passos seguros, persiste a próxima ação e pede ensino humano somente para regra
ambígua, visão, QG7 ou promoção RAG.

Premissa detalhada por classe: `docs/QA-PERFIS-CLASSES-SA-N1-N3.md`.
