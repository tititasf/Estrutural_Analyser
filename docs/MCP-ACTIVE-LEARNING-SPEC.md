# MCP Active Learning - Contrato Seguro

## Princípio

`Edição humana != validação humana`.

O MCP transporta contexto para agentes e preserva eventos. Ele não decide verdade,
não promove tiers e não altera motores automaticamente.

## Estados

```text
CAPTURED/T0 -> PROPOSING/T0 -> PROPOSED/T0
                                  |
                    decisão humana explícita
                       |                    |
                  APPROVED/T1          REJECTED/TX
                       |
                  INDEXED/T1
```

- `FAILED` é reprocessável até cinco tentativas.
- `TEST_QUARANTINED` nunca é elegível.
- Conteúdo antes/depois do evento é imutável; somente estado operacional muda.

## Stores

- `active_learning/candidates`: hipóteses T0 para CLI e Curadoria.
- `active_learning/approved`: lições T1/T2 consultáveis.
- `data/vectors/faiss/estruturais.index`: não é modificado pelo pipeline MCP.

Cada store usa gerações imutáveis e `CURRENT.json` atômico com hashes.

## Botões

| Botão | Efeito |
|---|---|
| Salvar no SA/Reverse Hub/Robô | Persiste a edição e registra evidência T0. |
| Validar F5 | Gate humano da ficha N2; fluxo independente do MCP. |
| Validado Humano N1/N2/N3/N4 | Gate do artefato/nível selecionado. |
| Gerar propostas T0 | Converte eventos CAPTURED em hipóteses explicáveis. |
| Analisar padrões | Agrupa recorrências por classe/fase/campo; permanece T0. |
| Atualizar índice candidato | Materializa somente PROPOSED/T0 no store candidato. |
| Aprovar proposta | Exige justificativa e promove somente a proposta selecionada. |
| Rejeitar proposta | Preserva histórico como TX. |
| Indexar aprovadas T1 | Materializa somente APPROVED/T1 no store aprovado. |

## MCP

- `stdio`: transporte preferido para CLI local.
- SSE: somente `127.0.0.1`, portas `21300-21399`.
- Ferramentas de escrita exigem `CAD_MCP_WRITE_TOKEN`.
- Ferramentas dos loops 3-6 continuam marcadas `PENDENTE_INTEGRACAO`.

## Consumo pelos robôs

Robôs não recebem valores diretamente de vetores. A consulta retorna contexto e
proveniência para sugestão ou para o looper. Alteração de extrator/gerador exige:

1. proposta aprovada;
2. mudança de regra/configuração/código;
3. testes ARETE da classe;
4. comparação N2→N4 ou N1→N3;
5. nova decisão humana.
