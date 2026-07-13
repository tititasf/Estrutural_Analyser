# Fix requests gerados pelo Agente QA de Evidências

## LAJ-CUT-DISTANT

Itens observados: L319, L321, L324

Ajuste universal do detector LAJ: uma geometria de visão de corte só pode ser vinculada se tocar/intersectar o contorno da laje dentro de tolerância escalada pela dimensão local. Não use IDs de item/obra. Remova vínculos inferidos distantes, preserve vínculos humanos e crie regressão com casos de corte composto e geometrias de pilares próximas.

## LAJ-PILLAR-NOT-TOUCHING

Itens observados: L319, L320, L321, L322, L323, L324

Ajuste universal do detector de apoios LAJ: pilar de apoio exige nome canônico, geometria em contato com o contorno e face/lado determináveis. Pilares separados por viga/gap ou com touch_face/pillar_side NULO não podem entrar. A tolerância deve escalar com a laje; zero hardcode por item. Preserve vínculos humanos e adicione regressão cross-classe porque o tracer alimenta outros elementos.
