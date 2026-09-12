# Nível por segmento de fundo de viga

Cada segmento FV (`S1`, `S2`, …) possui uma cota própria. A derivação usa a
mesma convenção estrutural das laterais: **o nível da viga é a maior cota das
lajes que efetivamente tocam o trecho**.

## Ordem de decisão

1. Cota explícita válida do segmento, das laterais correspondentes ou da viga.
2. Maior `laje_nivel` entre as lajes comprovadamente adjacentes à geometria do
   segmento, amostrando o eixo longitudinal nos dois lados.
3. Para vigas de borda sem contato direto, a laje **cotada** cujo contorno real
   estiver geometricamente mais próximo (`nearest_levelled_slab`). Em empate de
   até 0,01 cm, prevalece a maior cota, conservando a regra das laterais.
4. Sem qualquer laje cotada no pavimento: nível vazio,
   `level_source=unresolved`. Não se copia o nível geral do pavimento por nome,
   ordem ou maioria.

O snapshot SA persiste `level`, `level_source`, `level_slabs` e
`level_distance_cm` (zero quando há contato). O contrato N3 transporta os mesmos
dados como `nivel`, `nivel_origem`, `nivel_lajes` e `nivel_distancia_cm`, sem
alterar a geometria ou a segmentação. Snapshots anteriores são enriquecidos em
leitura pelo portal com a mesma função, permitindo exibir a cota sem inventar
uma migração destrutiva dos dados existentes.
