# Fix requests gerados pelo Agente QA de Evidências

## LAJ-CUT-DISTANT

Itens observados: L319, L321, L324

Ajuste universal do detector LAJ: uma geometria de visão de corte só pode ser vinculada se tocar/intersectar o contorno da laje dentro de tolerância escalada pela dimensão local. Não use IDs de item/obra. Remova vínculos inferidos distantes, preserve vínculos humanos e crie regressão com casos de corte composto e geometrias de pilares próximas.

## LAJ-LEVEL-MISMATCH

Itens observados: L324

Ajuste universal de nível LAJ: não permita que field, root e label divirjam silenciosamente. Inferências precisam de âncora direta, delta explícito ou consenso geométrico rastreável. Em conflito, falhe fechado e gere pergunta; nunca faça média.

## LAJ-NEIGHBOR-LEVEL-CONTAMINATION

Itens observados: L323, L325, L331

Ajuste universal de vizinhos LAJ: nível vizinho deve vir do campo/rótulo semanticamente confiável da laje-fonte e estar no mesmo slot da identidade. Números de cotas/dimensões não provam nível. Remova apenas inferências contaminadas, preserve decisões humanas e teste valores de nível e dimensões numericamente parecidos.

## LAJ-PILLAR-NOT-TOUCHING

Itens observados: L319, L320, L321, L322, L323, L324

Ajuste universal do detector de apoios LAJ: pilar de apoio exige nome canônico, geometria em contato com o contorno e face/lado determináveis. Pilares separados por viga/gap ou com touch_face/pillar_side NULO não podem entrar. A tolerância deve escalar com a laje; zero hardcode por item. Preserve vínculos humanos e adicione regressão cross-classe porque o tracer alimenta outros elementos.
