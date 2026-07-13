# Fix requests gerados pelo Agente QA de Evidências

## LAJ-LEVEL-OUTLIER-CORRECTION

Itens observados: L303, L318

Investigue a causa geral e crie teste de regressão sem hardcode por item.

## LAJ-PILLAR-NOT-TOUCHING

Itens observados: L303, L318

Ajuste universal do detector de apoios LAJ: pilar de apoio exige nome canônico, geometria em contato com o contorno e face/lado determináveis. Pilares separados por viga/gap ou com touch_face/pillar_side NULO não podem entrar. A tolerância deve escalar com a laje; zero hardcode por item. Preserve vínculos humanos e adicione regressão cross-classe porque o tracer alimenta outros elementos.
