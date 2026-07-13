# Contrato QA ↔ Arete ↔ RAG

O contrato canônico permanece em `docs/CONTRATO-QA-RAG-LOOPINGS.md`. Esta squad:

1. consome snapshot N1, CAD local, contratos e artefatos com hash;
2. chama somente os entry points canônicos do repo;
3. produz dossiê append-only, decisões e candidatos de curadoria;
4. nunca promove RAG nem grava N1 sem autoridade explícita;
5. falha fechado quando tier, campo, proveniência ou veredito visual não existem.

## Decisão de integração

- **MCP:** adiado até adaptadores PIL/FV/LV e RAG tipado passarem QG1–QG6.
- **Hooks automáticos:** não usados; o roteamento depende do tipo de mudança e pode
  envolver trava global/headless. Automatizar sem contexto aumenta risco e latência.
- **Cache:** permitido somente por hash de todos os inputs e versão do adaptador.
