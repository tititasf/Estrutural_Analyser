# ARETE — fechamento LAJ 13_PAV

- Data: 2026-07-05
- Escopo: `Obra_TREINO_1` / `LAJ` / `13_PAV`
- Runtime de validação final: Python 3.12.2
- Estado inicial: G2 numérico 31/31 PASS; nenhum veredito visual válido.
- Resultado global: **FAIL**. O G2 numérico não representa aprovação visual.

## Fase 1 — G2-V N2×N4

- Evidência: `scripts/arete/relatorios/g2v/20260705_113311/`
- Resultado: **10 PASS / 21 FAIL / 0 SUSPEITO**
- PASS: L301–L308, L312 e L314.
- Em 20 itens FAIL falta a hachura diagonal de apoio no N4.
- L318 também contém projeção retangular extra.
- L320 e L321 têm colisão entre cota e rótulo.
- L326 tem cotas sobrepostas e ilegíveis.
- Os achados foram registrados no log schema v2 em modo append-only.

## Fase 2 — N1-V dos 14 `n1_overlap_viga`

- Evidência: `scripts/arete/relatorios/g2v/20260705_114144/`
- Resultado para a causa histórica específica: **14/14 PASS visual**.
- Itens: L303, L308, L310, L317, L321–L325 e L327–L331.
- Foram anexados 14 eventos `status: verificado` ao log schema v2. Isso fecha apenas
  `n1_overlap_viga`; não anula deltas posteriores de G4.

## Fase 3 — proveniência, G4, N1-V e G5

### Proveniência e G4

- Tabela pré-requisito: `docs/PROVENIENCIA-CAMPOS-LAJ.md`.
- A hachura de apoio foi classificada como campo algorítmico (b), mas ainda não
  possui campo explícito no núcleo da ficha.
- Evidência G4: `scripts/arete/relatorios/convergencia_laj/Obra_TREINO_1/13_PAV/20260705_114749/`
- G4 N1×N2: **15 PASS / 16 FAIL / 0 BLOCKED**; campos (a)+(b): 324 PASS / 48 FAIL.
- N1-V adicional de L318, L319 e L320:
  **0 PASS / 0 FAIL / 3 SUSPEITO**. Os cards permitem avaliar a forma global, mas
  não fecham os deltas finos de grade, coordenadas, largura e área.

### G5 e G5-V

- Evidência G5: `scripts/arete/relatorios/paridade_n3_n4_laj/Obra_TREINO_1/13_PAV/20260705_114942/`
- G5 N3×N4: **14 PASS / 17 FAIL / 0 BLOCKED**.
- Vazamento de gabarito detectado: **0**.
- A primeira ficha G5-V apontava para HTML antigo sem `n3_path` e foi preservada
  como **31 SUSPEITO**, sem uso como prova.
- Evidência G5-V válida, renderizada diretamente dos DXFs N3 frescos e N4:
  `scripts/arete/relatorios/g2v/20260705_131114/`.
- G5-V válido: **15 PASS / 15 FAIL / 1 SUSPEITO**.
- Divergência geométrica visível: L303, L317–L325 e L327–L331.
- L304 coincide visualmente, mas permanece FAIL no G5 por
  `linhas_horizontais`, `cotas_valor` e `modo_selecionado`.
- L306 renderiza apenas o rótulo nos dois lados, sem geometria suficiente:
  G5-V SUSPEITO e G5 numérico FAIL.

## Ajustes de infraestrutura de validação

- `g2v_harness.py`: suporte aditivo a `--n3-dir` e render direto DXF para G5-V,
  incluindo `n3_path` na proveniência.
- `paridade_visual.py`: rótulos configuráveis N3/N4 e exclusão de moldura/carimbo
  administrativo e sentinelas em `x < -5000`.
- Nenhum dado de N2/N4 foi fornecido ao N3.
- Não foram alterados `slab_tracer.py`, `motor_reverso_laj.py`,
  `gerar_lj_dxf_stog.py` ou `main.py`.

## Validação técnica

- `py -3.12 -m py_compile scripts/arete/g2v_harness.py scripts/arete/paridade_visual.py`: PASS.
- `py -3.12 -m pytest tests/test_paridade_n3_n4_laj.py -q`: 2 PASS.
- Todos os seis relatórios JSON desta rodada e as 95 linhas do JSONL de triagem:
  JSON válido; resumo G5-V consistente.
- `tests/test_arete_lj_13pav_n4_visual.py` falha em itens golden atuais, inclusive
  L301/L302/L305. Conforme o protocolo de ferramentas antigas, essa régua é de
  geração anterior à paridade canônica v1.2 e não foi usada como veredito.

## Próxima correção

O maior defeito comum é a ausência da hachura de apoio no N4 (20/31 itens
reprovados visualmente). A correção provável alcança `gerar_lj_dxf_stog.py`,
arquivo protegido por confirmação de concorrência. Depois dela, executar
`arete_runner --classe LAJ --pav 13_PAV`, revalidar os 31 goldens e repetir G2-V.
As colisões de cota de L320/L321/L326 devem ser tratadas em seguida.
