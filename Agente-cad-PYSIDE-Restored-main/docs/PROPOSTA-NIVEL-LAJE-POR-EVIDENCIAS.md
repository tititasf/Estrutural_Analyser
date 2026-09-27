# Proposta — nível de laje por soma de evidências

**Status:** aprovada com ajustes (respostas 2026-09-26), a implementar · **Criado:** 2026-09-26 · **Classe:** LAJ (usada por PIL, LV, FV)

## Por que

Direção do dono (2026-09-26): o nível não sai de uma regra fixa. A cota escrita dentro da
laje pode ser o nível dela **ou de uma parte dela**; a verdade aparece quando várias
informações concordam — vizinhas, pilares, vigas, cortes — como uma soma de pontos.

Hoje o código decide por **hierarquia** (cota contida > ambígua > proximidade > delta de
corte > consenso de vizinhas): a primeira fonte que responde vence e as outras nem são
ouvidas. Foi assim que um delta errado (bug cm×m) virou nível "validado" em 4 lajes sem
que a cota da planta (852.19, na L324) o contradissesse.

## Como funcionaria

Cada evidência vira um **voto** num valor candidato, com peso e escopo:

| # | Evidência | Peso inicial | Observação |
|---|---|---|---|
| E1 | cota escrita **contida** no contorno | alto | se estiver cercada por linha/hachura de rebaixo, o escopo é a **sub-região**, não a laje inteira |
| E2 | várias cotas contidas | médio cada | cada uma candidata a uma sub-região diferente |
| E3 | visão de corte: vizinha com nível conhecido + delta (cm → m) | médio; alto se a vizinha é humana | já com os portões P2/P3/P4 |
| E4 | vizinhas sem corte com o mesmo nível | baixo | consenso, nunca sozinho |
| E5 | vigas de borda: segmento = maior cota das lajes que o tocam | coerência | viga que "não fecha" com a laje é voto contra |
| E6 | pilares: topo do pilar apoiado na laje | coerência | idem |
| E7 | referência do pavimento + pé-direito | **veto** | fora da janela = candidato eliminado |
| E8 | validação humana | **âncora** | ver pergunta 3 |

Decisão:
1. Juntar os candidatos distintos (com tolerância de 1 cm).
2. Pontuar = soma dos pesos a favor − penalidade das evidências que contradizem.
3. Aceitar o 1º quando passa um mínimo **e** tem margem sobre o 2º; senão `needs_review`,
   com a lista de quem votou em quê (vira a ficha de dúvida visual do dono).
4. Registrar sempre o placar em `level_inference.evidencias` — explicável e auditável.

Pesos iniciais são chute. **Calibração obrigatória** contra as lajes já validadas pelo dono
no 13_PAV: medir acerto (como o `kb_eval.py` faz para a busca) e só então ligar.

## Caso real que já cabe aqui: L318

| Evidência | Valor |
|---|---|
| rótulo pareado com L311 pelo mesmo corte, validado | 852.19 |
| delta do corte vindo da L319 (−30 cm, fonte não humana) | 851.89 |

Hoje: vence o validado e o conflito fica anotado. Com a soma: se a L318 tiver linha de
rebaixo no desenho, as duas estão certas — 852.19 para a laje e 851.89 para a parte
rebaixada (E1 com escopo de sub-região). É exatamente o "pode representar uma parte dela".

## Perguntas ao dono

1. A lista E1–E8 cobre as fontes que você usa de cabeça? Falta alguma (ex.: texto de
   rebaixo "−30", hachura, espessura)?
2. Sub-região: um nível parcial deve virar **campo novo** da laje (ex. `laje_niveis_parciais`)
   ou a laje deve ser partida em duas?
3. Validação humana é **âncora absoluta** (nada a muda) ou **voto muito forte** (evidência
   contrária forte abre revisão)? O caso L318 mostra por que a segunda opção protege mais.
4. Posso calibrar os pesos contra as lajes validadas do 13_PAV antes de ligar?

## Respostas do dono (2026-09-26) — D-51..D-55

1. **Evidências:** entra **E9 — texto de rebaixo** ("−30") perto da cota; sem cota na laje,
   o texto de rebaixo dentro dela provavelmente é dela. Ainda sem exemplos no corpus.
2. **Sub-região:** decide pelo **fundo** (nível − espessura). Fundos iguais → 1 laje (o
   nível parcial vira campo da mesma laje); fundos diferentes → **2 lajes separadas**.
   Logo a espessura por trecho passa a ser evidência necessária.
3. **Validação humana = voto muito forte.** Contradição forte abre `needs_review` com o
   placar — é a ferramenta para achar onde sistema e dono discordam.
4. **Calibrar** contra as lajes validadas do 13_PAV antes de ligar: sim.
5. Informação extra: área sem laje costuma ter **X vermelho** — vira evidência "sem laje"
   para os segmentos de viga que não encostam em laje.
