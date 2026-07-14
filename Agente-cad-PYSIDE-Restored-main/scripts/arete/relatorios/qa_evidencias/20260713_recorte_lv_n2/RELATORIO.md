# Refinamento rápido — recortes N2 de laterais de viga

## Causa

LV usava o frame `9999999999` inteiro como recorte. Quando duas laterais
independentes estavam no mesmo frame, ambas recebiam a mesma folha completa.

## Regra implementada

Dentro de um frame compartilhado, o motor reúne os grupos de nomenclatura e
particiona pelo eixo dominante de sua distribuição: X para desenhos lado a lado,
Y para desenhos empilhados. Os limites ficam nos pontos médios entre grupos, com
18 unidades de margem para manter contornos e cotas de borda. Frames com uma
única lateral não mudam. Não há regra por ID, pavimento ou obra.

## Evidência seca — 14º pavimento

- `V413`: frame `6351..7721` → `6351..6839`;
- `V414`: frame `6351..7721` → `6803..7721`;
- `V415`: frame `7936..9306` → `7936..8377`;
- `V416`: frame `7936..9306` → `8341..9306`.

Os pares deixam de receber a folha inteira. Nenhum DXF aprovado nem banco foi
alterado. Compilação passou; testes relacionados: `6 passed`.
