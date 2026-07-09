# Proveniência de Campos — LAJ

**Status:** pré-requisito do Gate G4 para LAJ  
**Escopo:** Obra_TREINO_1 / 13_PAV, com regra válida para qualquer obra  
**Regra central:** N2 é gabarito externo de validação. N3 recebe somente N1 bruto da tabela `slabs` e regras algorítmicas gerais; `slab_elements`, N2 e N4 são fontes proibidas.

## Categorias G4

- **(a) extraível do N1:** existe no Structural Analyzer ou deriva diretamente de sua geometria/vínculos.
- **(b) algorítmico:** calculado por regra geral a partir de (a), sem consultar N2/N4.
- **(c) só-no-N2 / convenção humana:** escolha de apresentação ou estilo; diferença não prova bug de interpretação.
- **(d) teto estrutural:** informação que não existe no DXF estrutural de origem. Só pode ser excluída com evidência por obra e aprovação humana.

## Contrato principal da ficha do robô LAJ

| Campo | Cat. | Fonte N1 ou regra | Uso e critério de G4 | Evidência no código |
|---|---:|---|---|---|
| `nome` | a | `slabs.name` / rótulo interpretado | igualdade textual | `src/core/laje_n1_to_robot_ficha.py:192-195,247` |
| `numero` | a | dígitos de `nome` | igualdade exata | `src/core/laje_n1_to_robot_ficha.py:21-23,248` |
| `coordenadas` | a | `points_json` ou vínculo `laje_outline_segs.contour` | mesmo polígono após translação e rotação 0/90/180/270; escala não normaliza | `src/core/laje_n1_to_robot_ficha.py:47-69,197-203`; `scripts/arete/conversao_n1_diff.py:70-118,164-221` |
| `comprimento` | a | bbox do contorno N1 quando não vier explícito | delta ≤ 0,5 cm | `src/core/laje_n1_to_robot_ficha.py:205-208,249` |
| `largura` | a | bbox do contorno N1 quando não vier explícito | delta ≤ 0,5 cm | mesmas referências de `comprimento` |
| `area_cm2` | a | área do polígono N1; fallback `comprimento × largura` | delta ≤ 1 cm² | `src/core/laje_n1_to_robot_ficha.py:210-214,250` |
| `linhas_verticais` | b | `smart_panner.distribute_panels` ou regra N1 explícita validada | posições e `is_union` dentro de 0,5 cm | `src/core/laje_n1_to_robot_ficha.py:220-241,253`; `scripts/arete/conversao_n1_diff.py:45,282-286` |
| `linhas_horizontais` | b | mesma regra da grade vertical | posições e `is_union` dentro de 0,5 cm | mesmas referências de `linhas_verticais` |
| `modo_selecionado` | b | orientação derivada da quantidade de linhas da grade, salvo modo N1 explícito | igualdade exata | `src/core/laje_n1_to_robot_ficha.py:216-218,243-245,252` |
| `obstaculos` | b | interseções/vínculos estruturais N1 filtrados pelo contorno da laje | igualdade canônica; qualquer valor deve nascer do N1 | `src/core/laje_n1_to_robot_ficha.py:230-234,255`; `scripts/motor_reverso_laj.py:870-915` |
| `apoios_hachurados` | b | N4: sequências de `LINE` diagonais da layer estrutural `3`, normalizadas pelo contorno; N3: somente interpretação equivalente originada no N1 | igualdade geométrica e G2-V/G5-V; nunca herdar de N2/N4 no N3 | `scripts/motor_reverso_laj.py::_extract_support_hatch_lines`; `scripts/gerar_lj_dxf_stog.py::draw_laje_planta` |
| `unioes_nos_bordes` | b | derivado da grade e da regra geral de montagem | comparação booleana; `[]` e `false` equivalem | `src/core/laje_n1_to_robot_ficha.py:260`; `scripts/arete/conversao_n1_diff.py:284-288` |
| `pontaletes` | b | cálculo de montagem quando aplicável | igualdade canônica; ausência atual é `{}`, não autorização para copiar N2 | `scripts/arete/conversao_n1_diff.py:50,288-290`; `scripts/motor_reverso_laj.py:1201` |
| `cotas_paineis` | c | posição, rotação, altura e texto como convenção gráfica do projetista | não bloqueia G4. Os **valores** de cota devem ser regeneráveis pela geometria/grade (b); a posição visual é julgada em G5‑V pelo dono/agente | `scripts/gerar_lj_dxf_stog.py:864-881`; `scripts/arete/conversao_n1_diff.py:51` |
| `observacoes` | c | anotação livre do fluxo humano | não bloqueia G4; nunca copiar por item para fazer N3 “bater” | `src/core/laje_n1_to_robot_ficha.py:261`; `scripts/arete/conversao_n1_diff.py:52` |

## Campos auxiliares e metadados

| Campo | Cat. | Tratamento |
|---|---:|---|
| `_stog_pose` | a (derivado) | âncora absoluta obtida do contorno N1; não é conteúdo do gabarito. `apply_n1_outline_anchor` mantém a geometria local e grava a pose (`src/core/laje_n1_to_robot_ficha.py:72-103`). |
| `_sa_meta` | a (proveniência) | metadado de auditoria do caminho N1. Em G5 deve declarar `n3_teacher: null` e `gabarito_patterns_allowed: false` (`scripts/arete/paridade_n3_n4_laj.py:42-57`). |
| `_hlaz` | b | representação auxiliar da faixa de união. Semanticamente nasce de linhas com `is_union`; não deve ser copiada do N2. O comparador também pode derivá-la da geometria (`scripts/arete_lj_canonico.py:215-223`). |
| `_panel_vertical_segments` / `segments` nas linhas | b | recortes locais da grade para contornos complexos, calculados pela geometria; o gerador preserva os segmentos (`scripts/gerar_lj_dxf_stog.py:784-797`). |
| `_forma_canonica` | — | artefato de validação produzido pelo motor reverso; não é entrada autorizada do N3 (`scripts/motor_reverso_laj.py:1202-1208`). |
| `_confianca` | — | metadado do extrator N2; não é campo de robô nem fonte do N3 (`scripts/motor_reverso_laj.py:1226-1261`). |
| `reaproveitamento_dados`, `sobras_recebidas` | d, fora do G4 atual | estado operacional externo, lido opcionalmente pelo gerador, mas ausente do contrato G4 e do DXF estrutural (`scripts/gerar_lj_dxf_stog.py:694-695`). Não pode contar como PASS/FAIL de interpretação sem uma fonte externa aprovada. |

## Semânticas visuais ainda sem campo explícito

| Semântica | Cat. | Estado e consequência |
|---|---:|---|
| Hachura de apoio | b | Deve ser derivada dos apoios/vínculos N1 (pilares e vigas de borda). Hoje não existe campo explícito na ficha principal e o G2 numérico não a mede. O G2‑V de 05/07/2026 encontrou a hachura do N2 ausente no N4 em 20 itens; isso é gap real do gerador/contrato, não categoria (c). Evidência: `scripts/arete/relatorios/g2v/20260705_113311/relatorio.json`. |
| HLAZ | b | Representada por `is_union` e, auxiliarmente, `_hlaz`. Não confundir faixa HLAZ do próprio painel com hachura de apoio nem com hachura de laje vizinha. |
| Legibilidade/posição de cotas | c com regra de qualidade | A posição exata é estilo, mas sobreposição e ilegibilidade são FAIL visual. L320, L321 e L326 falharam por colisão/sobreposição no G2‑V de 05/07. |
| Rótulos de vizinhança | a, contexto | Identificadores V###/P## vêm dos vínculos N1; devem ser tratados como contexto estrutural, sem usar textos do N2 como entrada do N3. |

## Regra anti-vazamento

1. Fonte permitida para N1: tabela `slabs` do projeto SA resolvido para obra/pavimento.
2. Fonte proibida: `slab_elements.campos_json`, pois pode conter ficha N3 enriquecida.
3. Padrões com origem iniciada por `N4_DXF:`, `N2/N4:` ou `N2/N4_validated` são proibidos no N3.
4. Qualquer referência proibida torna o item `FAIL vazamento_gabarito`, mesmo quando N3 e N4 são visualmente iguais.
5. Não há campo principal LAJ classificado como (d) no G4 atual. Nova exclusão (d) exige prova no DXF de origem e aprovação humana.

## Consequência para os gates

- G4 bloqueia apenas divergências de (a) e (b); (c) é relatado separadamente.
- G4 numérico não substitui N1‑V.
- G5 deve gerar N3 e N4 de verdade para 100% dos itens na primeira rodada.
- G5‑V continua obrigatório; igualdade por herança é vazamento, não sucesso.
