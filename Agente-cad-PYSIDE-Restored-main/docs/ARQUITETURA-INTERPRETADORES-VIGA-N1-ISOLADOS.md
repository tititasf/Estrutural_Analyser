# Arquitetura N1 — Interpretadores de viga isolados

**Versão:** 1.0.0
**Última atualização:** 2026-07-05
**Status:** ATIVO — fonte de verdade da separação FV/LV/PIL no N1

---

## Objetivo

Impedir que uma correção de interpretação de fundo de viga altere silenciosamente
laterais ou relações pilar-viga. A arquitetura mantém uma captura geométrica comum e
separa as decisões semânticas em sete contratos com saídas exclusivas.

Esta decisão vale para a evolução N1 das classes FV, LV e PIL. Os procedimentos de
gate continuam definidos em `LOOPING-CANONICO.md`; este documento define onde cada
regra de interpretação deve viver.

## Decisão arquitetural

`BeamTracer` é o detector compartilhado de geometria e topologia bruta. Ele pode
identificar ocorrências, orientação, intervalos, linhas laterais e relações espaciais,
mas não deve concentrar regras finais específicas de FV, LV ou PIL.

As decisões semânticas são delegadas aos sete interpretadores registrados em
`src/core/beam_interpreters/`:

| Contrato | Classe dona | Saída exclusiva | Responsabilidade |
|---|---|---|---|
| `fundo_viga` | FV | `seg_bottom` | Segmentos físicos do fundo da viga |
| `lateral_viga_a_para` | LV | lado A / `comprimento_total` | Lateral A que termina no encontro |
| `lateral_viga_b_para` | LV | lado B / `comprimento_total` | Lateral B que termina no encontro |
| `lateral_viga_a_passa` | LV | lado A / `comp_total_passa` | Lateral A que continua pelo encontro |
| `lateral_viga_b_passa` | LV | lado B / `comp_total_passa` | Lateral B que continua pelo encontro |
| `pilar_com_viga_para` | PIL | `viga_que_para` | Eixo da viga termina no volume do pilar |
| `pilar_com_viga_passa` | PIL | `viga_que_passa` | Eixo da viga ultrapassa as duas faces do pilar |

O registro é fechado: deve conter exatamente esses sete contratos. As relações
`PILAR ... PARA` e `PILAR ... PASSA` são mutuamente exclusivas para a mesma relação
geométrica.

## Limites de responsabilidade

### Topologia compartilhada — `BeamTracer`

Pode evoluir quando o dado bruto está incorreto antes de chegar a dois ou mais
interpretadores, por exemplo:

- orientação por ocorrência;
- suporte a trechos da mesma viga em orientações diferentes;
- intervalos e linhas capturados do DXF;
- dimensão estrutural associada à ocorrência;
- bbox e continuidade do eixo nos encontros.

Não deve decidir que um encontro é painel FV, lateral A/B ou relação PIL
`para/passa`. Se o problema existe em apenas um contrato, o fix pertence ao
interpretador dono.

### FV — `FundoVigaInterpreter`

É o único dono da consolidação de segmentos de fundo. Intervalos vizinhos não podem
ser unidos apenas por proximidade depois que a fronteira física do encontro estiver
classificada. Duplicatas da mesma captura podem ser desduplicadas.

Estado atual: o modo conservador permanece ativo enquanto a topologia ainda não
classifica todos os cinco tipos de encontro do guia FV. Os métodos atômicos já estão
isolados, mas sua ativação depende dessa classificação geral. A subsegmentação da
V301 continua sendo caso de prova aberto, não exceção codificada.

### LV — quatro contratos independentes

Lado A e lado B não compartilham slot de saída. Dentro de cada lado, `Para` e
`Passa` também não compartilham a chave de comprimento. Utilitários geométricos
podem ser comuns, mas seleção, escrita e teste permanecem por contrato.

Dimensões laterais podem ser propagadas apenas entre vínculos LV da mesma viga. Uma
ficha FV nunca é fallback de dimensão lateral.

### PIL — dois contratos independentes

`PilarComVigaParaInterpreter` reconhece uma extremidade do eixo dentro do volume do
pilar, com continuidade em somente um lado. `PilarComVigaPassaInterpreter` exige
continuidade além das duas faces. Cada um escreve exclusivamente em seu slot.

## Regra para evolução harmonizada

Toda correção N1 em FV, LV ou PIL deve seguir esta ordem:

1. Demonstrar o erro no diagnóstico N1×N2 e no N1-V.
2. Identificar o dono do dado: topologia bruta compartilhada ou um dos sete contratos.
3. Corrigir somente o dono. Não copiar regra entre slots nem usar N2/N4 como entrada.
4. Adicionar teste do contrato e teste negativo provando que os outros contratos não
   receberam a saída.
5. Regenerar pelo headless canônico e executar o veredito visual obrigatório.
6. Se `BeamTracer` mudou, rodar headless completo das quatro classes e comparar as
   contagens de alerta; alerta novo fora da classe-alvo é regressão.

O schema público N1 continua imutável. A separação é uma organização interna da
interpretação e dos vínculos já consumidos pelo pipeline; não autoriza renomear,
remover ou preencher campos N1 com dados do gabarito.

Na persistência headless, as quatro topologias LV (A/B × Para/Passa) também são
congeladas independentemente. Validar um segmento de um contrato não impede que
outro contrato ainda não validado seja recalculado. FV segue a mesma regra em seu
contrato único. Campos internos não validados dos segmentos preservados continuam
evoluindo. O contrato transacional completo está em
`docs/PERSISTENCIA-HEADLESS-SA.md`.

## Gate mínimo por classe

| Classe | Teste arquitetural | Gate de interpretação |
|---|---|---|
| FV | somente `FundoVigaInterpreter` escreve `seg_bottom` | diagnóstico FV N1×N2 + N1-V |
| LV | A/B e Para/Passa escrevem somente seus quatro slots | diagnóstico LV N1×N2 + N1-V |
| PIL | Para/Passa exclusivos e sem dupla classificação | diagnóstico PIL N1×N2 + N1-V |

Para mudança em `BeamTracer`, a matriz obrigatória inclui também LAJ, porque a análise
compartilhada pode afetar obstáculos e enriquecimentos consumidos pelas quatro
classes.

## Evidência inicial — 2026-07-05

- Registro fechado dos sete contratos implementado em `src/core/beam_interpreters/`.
- Testes arquiteturais e de integração focados: 32 aprovados na rodada.
- Regressão headless completa: FV 34→30 alertas; LV 20→17; PIL 24→24; LAJ 4→4.
- Nenhum alerta novo em classe não alvo nessa rodada.
- Fechamentos numéricos observados: FV V308, V320, V321 e V325; LV V302, V304 e V322.
- N1 FV ainda não convergiu: V301 permanece subsegmentada e exige evolução geral da
  classificação de encontros.

Esses números são fotografia da rodada, não fonte de status atual. Para estado vivo,
sempre executar `python scripts/arete/gerar_status.py` e consultar o relatório mais
recente.

## Referências

- `docs/LOOPING-CANONICO.md`
- `docs/MASTERPLAN-ARETE-FUNDO-VIGA.md`
- `docs/MASTERPLAN-ARETE-LATERAL-VIGA.md`
- `docs/MASTERPLAN-ARETE-PILAR.md`
- `docs/PERSISTENCIA-HEADLESS-SA.md`
- `src/core/beam_interpreters/contracts.py`
- `src/core/beam_interpreters/registry.py`
- `tests/test_beam_interpreters_architecture.py`

---

_Última atualização: 2026-07-05 | Arquitetura N1 FV/LV/PIL_
