# Fix requests gerados pelo Agente QA de Evidências

## LAJ-CUT-CALC-INCONSISTENT

Itens observados: L318

Investigue a causa geral e crie teste de regressão sem hardcode por item.

## LAJ-NEIGHBOR-LEVEL-CONTAMINATION

Itens observados: L306, L312, L313, L315

Ajuste universal de vizinhos LAJ: nível vizinho deve vir do campo/rótulo semanticamente confiável da laje-fonte e estar no mesmo slot da identidade. Números de cotas/dimensões não provam nível. Remova apenas inferências contaminadas, preserve decisões humanas e teste valores de nível e dimensões numericamente parecidos.

## LAJ-PILLAR-NOT-TOUCHING

Itens observados: L301, L302, L304, L305, L306, L307, L308, L309, L316, L317

Ajuste universal do detector de apoios LAJ: pilar de apoio exige nome canônico, geometria em contato com o contorno e face/lado determináveis. Pilares separados por viga/gap ou com touch_face/pillar_side NULO não podem entrar. A tolerância deve escalar com a laje; zero hardcode por item. Preserve vínculos humanos e adicione regressão cross-classe porque o tracer alimenta outros elementos.
