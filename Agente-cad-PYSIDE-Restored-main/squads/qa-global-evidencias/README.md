# QA Global de Evidências

Squad AIOS do QA Arete. O orquestrador escolhe o microciclo por nível e delega a
semântica a adaptadores de classe. A implementação operacional continua nos scripts
canônicos do repo; esta squad formaliza roteamento, gates, dossiês e autoridade.

Ativação: `/CAD:QAGlobalEvidencias-AIOS *loop --obra ... --pav ... --classe ... --nivel ...`

Arquitetura: uma squad, um orquestrador, tasks determinísticas e zero entry point
alternativo para headless, geração ou visão.

Fast paths v1.1: probe N1 limitado a campos/checks com cruzamento entre classes,
paridade declarativa contrato→payload→DXF→HTML, render cacheado por conteúdo e
RAG particionado com degradação explícita. Esses caminhos aceleram diagnóstico;
não aprovam ficha/item nem substituem gate visual.
