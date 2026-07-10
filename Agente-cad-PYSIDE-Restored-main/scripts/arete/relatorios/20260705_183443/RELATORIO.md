# ARETE — correção evolutiva da hachura de apoio LAJ

- Obra/pavimento: `Obra_TREINO_1` / `13_PAV`
- Runtime: Python 3.12.2
- Escopo alterado: somente LAJ.
- Resultado da correção: **melhora visual confirmada sem perda de G2**.

## Implementação

- `motor_reverso_laj.py` agora extrai as sequências de `LINE` diagonais a 45°
  da layer estrutural `3` para o campo algorítmico `apoios_hachurados`.
- Linhas de apoios vizinhos além da janela local da laje são descartadas.
- `gerar_lj_dxf_stog.py` reproduz exatamente as primitivas locais extraídas;
  não adiciona apoio por heurística.
- A inicialização de UTF-8 do gerador foi restringida à execução CLI, evitando
  fechar `stdout` quando o módulo é importado pelos testes.
- A tabela `docs/PROVENIENCIA-CAMPOS-LAJ.md` foi atualizada. O campo é categoria
  (b); no N3 ele só pode nascer do N1, nunca ser herdado de N2/N4.

## Gates

- Arete completo: `scripts/arete/relatorios/20260705_182424/`.
- G2 numérico: **31/31 PASS**, igual ao baseline.
- G1: **30/31 PASS**.
- O único G1 FAIL é L318 em `linhas_verticais` (14 no N2 versus 12 no N2′).
  O novo campo `apoios_hachurados` fecha o round-trip de L318 corretamente.
- A divergência de `linhas_verticais` não foi criada pelo patch de hachura:
  o N2 atual tem linhas 2814,9 e 2972,9 além da largura canônica efetiva de
  2831,12 cm; o N2′ elimina essas fronteiras de painel inválidas/próximas ao
  corte. O problema fica aberto junto à geometria/projeção de L318.

`docs/STATUS.md` sinaliza 30/31 como regressão contra o golden histórico, pois o
golden L318 de `20260703_171707` foi selado com largura 3275 cm, enquanto a fonte
atual usa 2831,12 cm. Não houve rollback da hachura porque ele não elimina esse
delta anterior e perderia a melhora visual comprovada.

## G2-V pós-fix

- Evidência válida: `scripts/arete/relatorios/g2v/20260705_182537/`.
- Fonte: render direto dos DXFs, `g2v_harness --backend cli
  --fonte-imagem dxf`.
- Antes: **10 PASS / 21 FAIL**.
- Depois: **27 PASS / 4 FAIL**.
- As 20 ocorrências abertas de `n4_hachura_apoio_ausente` foram verificadas e
  fechadas no JSONL em modo append-only.
- L312, L314 e L326 também possuem apoios legítimos que o card HTML anterior
  ocultava por recortar geometria externa; o render direto confirma a reprodução.

Falhas restantes:

- L318: projeção/contorno ainda depende da validação do dono.
- L320 e L321: colisão entre cota e rótulo.
- L326: cotas verticais sobrepostas e ilegíveis.

## Validação de não regressão

- 23 testes LAJ relevantes: **PASS**.
- `py_compile` de motor, gerador e harnesses: **PASS**.
- JSONL: 115 linhas válidas; 20 novos fechamentos de hachura.
- Relatório G2-V: 31 itens e resumo 27/4/0 consistentes.
- Atributo read-only de L304, L306, L312 e L323 foi temporariamente removido
  apenas durante a regeneração e restaurado ao final.
- Nenhum JSON de Fase-4 foi alterado.
