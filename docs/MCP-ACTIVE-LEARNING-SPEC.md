# MCP Active Learning - Contrato Seguro

> **Status (2026-07-02): CAPTURA T0 ATIVA; SERVIDOR E PROMOÇÃO INATIVOS.**
> Os hooks da UI já gravam edições em `human_event_logs` como `CAPTURED/T0`
> (159 eventos reais e 1 `TEST_QUARANTINED/T0` no snapshot auditado). Isso é
> captura auditável, não validação nem aprendizado aprovado. O servidor MCP
> ainda **não está registrado/conectado em nenhuma sessão de agente** (sem
> `mcpServers` em config), e geração de propostas, aprovação T1 e indexação
> nunca foram exercitadas ponta a ponta com dado real. Loops 3-6 e o disparo
> de pipeline continuam stubs `PENDENTE_INTEGRACAO`.
>
> O loop de qualidade que está rodando de fato hoje (Arete, por classe:
> PIL/FV/LV/LAJ) usa um caminho **paralelo e desconectado** deste: fichas
> HTML headless + log de triagem em JSONL (`scripts/arete/relatorios/
> triagem_erros/*.jsonl`), sem tocar nesta tabela/pipeline MCP. Ver
> `Agente-cad-PYSIDE-Restored-main/docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md`
> para o procedimento em uso.
>
> **Gatilho pra ativar servidor/promoção MCP** (decisão do dono): (1) existir
> orquestração autônoma entre agentes, sem relay manual; (2) a UI precisar
> operar a triagem; ou (3) obra nova sem N2 precisar consultar conhecimento já
> aprovado. Até lá, o JSONL Arete é o registro operacional dos achados. Ele
> **não** deve ser sincronizado integralmente por `save_n4_feedback`, pois essa
> tabela representa apenas o subconjunto N4. A futura integração seguirá o
> modelo amplo de achados definido no contrato de harmonização.

> **Contrato de harmonização:** ver
> `Agente-cad-PYSIDE-Restored-main/docs/ARETE-MCP-RAG-HARMONIZACAO.md` para a separação
> entre achado Arete, evento MCP, evidência T0 e conhecimento RAG T1/T2.
>
> **Não é multiagente hoje:** o dono opera múltiplas sessões de IA manualmente
> (Claude Code, agente RAG, etc.), relayando contexto entre elas — não existe
> orquestração autônoma. Ver `ARETE-MCP-RAG-HARMONIZACAO.md` §1.1 antes de
> interpretar "múltiplos agentes/sessões concorrentes" como gatilho já atingido.
> Essas sessões manuais ainda podem concorrer por arquivos/SQLite; idempotência,
> transações e escrita atômica continuam obrigatórias como segurança operacional,
> sem implicar desenho multiagente.

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
