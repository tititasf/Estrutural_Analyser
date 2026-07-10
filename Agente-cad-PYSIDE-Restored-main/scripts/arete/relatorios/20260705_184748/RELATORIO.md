# ARETE — fechamento evolutivo LAJ 13_PAV

- Obra: `Obra_TREINO_1`
- Runtime: Python 3.12.2
- Escopo: somente LAJ / 13_PAV
- Resultado G2 numérico: **31/31 PASS**
- Resultado G2-V final: **30 PASS / 1 FAIL**

## Melhorias aplicadas

1. Hachura de apoio
   - Extração explícita do campo algorítmico `apoios_hachurados` no motor reverso.
   - Reprodução das `LINE` diagonais no gerador.
   - Filtro de apoios de lajes vizinhas fora da janela local.
   - Vinte achados antigos fechados no JSONL em modo append-only.

2. Legibilidade de cotas
   - L320 e L321: rótulo deslocado para célula com pelo menos 70 cm gráficos
     de distância do texto da cota vertical.
   - L326: cotas verticais de lajes rasas movidas para fora do contorno e
     escalonadas em colunas com 24 cm de separação.
   - Os três achados foram verificados e fechados no JSONL.

3. Infraestrutura
   - Configuração UTF-8 do gerador limitada à execução CLI, sem fechar `stdout`
     ao importar o módulo em testes.
   - Proveniência LAJ atualizada; N3 não recebe o novo campo de N2/N4.

## Evidências

- Regressão final: `scripts/arete/relatorios/20260705_184440/`
- G2-V completo: `scripts/arete/relatorios/g2v/20260705_184530/`
- Cards de cotagem: `scripts/arete/relatorios/g2v/20260705_184306/`
- Resultado focal de cotagem: 3/3 PASS.
- Resultado anterior ao patch: 10 PASS / 21 FAIL.
- Resultado final: 30 PASS / 1 FAIL.

## Não regressão

- G2 preservado em **31/31 PASS** após duas regressões integrais.
- G1: 30/31 PASS. O único FAIL é L318 por duas linhas verticais incompatíveis
  com a largura canônica atual; o campo novo de hachura fecha o round-trip.
- 27 testes LAJ relevantes: PASS.
- Compilação dos módulos alterados: PASS.
- JSONL: 118 linhas JSON válidas.
- Quatro DXFs originalmente read-only tiveram o atributo restaurado após cada
  regressão.
- Nenhum JSON de Fase-4 foi alterado.

## Único bloqueio restante

L318 permanece FAIL visual. A hachura foi corrigida, mas a projeção inferior
direita e o contorno dependem da decisão do dono. O golden histórico usava
largura 3275 cm; a fonte atual usa 2831,12 cm e ainda carrega fronteiras de painel
em 2814,9 e 2972,9 cm. Não foi feita correção heurística para evitar mascarar a
divergência humana.
