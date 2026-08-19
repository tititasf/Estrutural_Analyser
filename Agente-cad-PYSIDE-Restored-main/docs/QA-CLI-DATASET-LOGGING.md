# Logs e dataset candidato do QA por CLIs

Cada item processado pelo fallback Claude → Codex → Antigravity produz três
representações complementares:

1. SQLite (`portal_qa_*`): consulta operacional por rodada, item e tentativa.
2. `job_<id>.log`: dossiê JSON final da rodada.
3. `job_<id>.events.jsonl`: ledger append-only, uma amostra por item.

## Proveniência gravada

- obra, pavimento, classe, item, camada e `round_id`;
- prompt completo e SHA-256;
- agente, modelo pedido/relatado, esforço e versão da CLI;
- duração, resultado ou categoria da falha técnica;
- resposta bruta sanitizada e SHA-256 da resposta original;
- caminhos, tamanho, papel, autoridade e SHA-256 de HTML, PNG, notas e regras;
- veredito, nota e sugestão estruturada;
- versão do adaptador e estado de autoridade.

Identificadores de sessão/conversa são redigidos dos textos armazenados. O hash é
mantido para deduplicação e auditoria sem transformar o conteúdo em prova.

## Curadoria e treinamento

Toda amostra nasce com:

```json
{
  "decision_authority": "PENDENTE",
  "training_eligible": false,
  "tier_candidate": "T3",
  "requires_human_approval": true
}
```

Portanto, volume ou concordância entre modelos não promove ground truth. T1 exige
decisão humana rastreável; T2 exige regra determinística aprovada, golden e
regressão. O exportador exclui candidatos não promovidos por padrão.

```bash
python scripts/arete/qa_export_training.py --out dataset.jsonl
python scripts/arete/qa_export_training.py --out auditoria.jsonl --include-candidates
```

Antes de usar um export em treinamento externo, revisar dados pessoais, licenças e
política do provedor. N2/N4 permanecem comparadores e nunca podem alimentar N1/N3.
