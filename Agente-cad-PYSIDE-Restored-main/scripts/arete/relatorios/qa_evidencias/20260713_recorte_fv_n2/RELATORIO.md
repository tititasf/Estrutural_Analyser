# Refinamento rápido — recortes N2 de fundos de viga

## Causa confirmada

`RecorteMotor._discover_fv()` aplicava uma largura fixa de 1.500 unidades à
direita de toda nomenclatura FV. Em fileiras com dois fundos lado a lado, o
primeiro recorte inevitavelmente atravessava o fundo seguinte.

## Correção geral

Para cada label FV, o limite direito agora é o ponto médio para a próxima
nomenclatura da mesma fileira (tolerância vertical de 65 unidades), com margem
de 20 unidades. Sem vizinho horizontal, mantém a janela histórica; portanto não
reduz fundos isolados nem usa IDs, pavimentos ou medidas hardcoded.

## Evidência seca — 2º PAV FV

| Item | Antes | Depois |
|---|---:|---:|
| V54 | 1530 × 180 | 494 × 180 |
| V61 | 1530 × 180 | 308 × 180 |

Os dois recortes agora param antes do label/perfil vizinho. Nenhum DXF humano ou
registro do banco foi alterado.

## Verificação

- Compilação de `src/core/recorte_motor.py`: OK.
- Testes de recorte e motores LAJ relacionados: `16 passed`.

## Próximo passo humano

No Diagnostic Reverse Hub, reprocessar apenas os FV ainda não aprovados e revisar
o primeiro item de cada fileira dupla. Os recortes aprovados continuam preservados.
