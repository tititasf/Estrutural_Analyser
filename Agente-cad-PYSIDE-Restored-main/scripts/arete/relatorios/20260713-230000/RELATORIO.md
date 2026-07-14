# Ciclo de refinamento N2 — recortes LAJ pendentes (Obra_TREINO_1)

Data: 2026-07-13

## Objetivo

Reduzir contaminação entre recortes de lajes ainda não aprovados, sem alterar
recortes humanos, banco de produção ou DXFs N2 existentes.

## Alterações no motor

1. A expansão por malha de painéis agora parte apenas do componente geométrico
   conectado à janela do rótulo. Antes, qualquer segmento próximo entrava no
   mesmo `min/max`, permitindo que uma laje vizinha puxasse o recorte.
2. Foi acrescentada uma barreira geométrica entre células de rótulos próximos.
   Ela age quando a bbox já atravessou a bissetriz em direção ao vizinho,
   inclusive para uma laje estreita cujo rótulo vizinho está um pouco acima ou
   abaixo da faixa.
3. Quando uma cadeia ortogonal de cotas STOG fecha uma janela local mais
   compacta que o span estrutural, ela recebe preferência, desde que mantenha
   evidência geométrica mínima. Nenhum dado N1 é usado nessa decisão.

## Evidência e validação

- Testes unitários focados: `7 passed`
  - `tests/test_recorte_motor_laj_stog_dimensions.py`
- Compilação: `python -m py_compile src/core/recorte_motor.py` — PASS.
- Extração seca de todos os 20 itens LAJ ainda não humanos/pendentes da
  Obra_TREINO_1: PASS, sem `db_path`, portanto sem escrita em produção.
- Contato visual da saída seca:
  `scripts/arete/tmp/laj_pending_after_component/contact.png`.

## Resultado observável

- L59 deixa de avançar até a célula de L60.
- L504 deixa de absorver a faixa lateral de L503.
- L513 deixa de assumir uma faixa contínua de múltiplos painéis; o componente
  parte do marco local.
- Casos de geometria especial (degraus, pilares e faixas estreitas) permanecem
  para veredito humano antes de qualquer aprovação. O motor não promoveu nem
  sobrescreveu status algum.

## Próximo microciclo

No Diagnostic Reverse Hub, regenerar somente os itens LAJ ainda pendentes e
comparar com o contato seco. Se um contorno especial ainda divergir, registrar
o item e a borda concreta que falta/sobra para que a próxima regra seja por
topologia geométrica, não por ID ou pavimento.
