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

## QA do pré-processamento em 2026-09-30

Rodada rastreável: `scripts/arete/relatorios/20260930-niveis-qa-v2/`.
O pré-processamento executa coleta canônica nova e conserva o JSON bruto por SHA,
com chamadas reais do consumidor de convenções e cotas. Não reaproveita snapshot SA antigo.

Correções de causa: tolerância de consenso em metros (0,0025 m = 0,25 cm);
contato parcial do fundo com contorno da laje; campos automáticos de laterais tratados
como estimativas, preservando campos humanos; transferência de nível pelo mesmo corte
aplica `nível_vizinho + (dist_topo_vizinho − dist_topo_própria)/100`, com nomes dos dois
lados e ambas as distâncias explícitas. Compartilhar corte não implica igualdade de nível.
As inferências continuam sujeitas a revisão, sem promoção a cota humana.

PNG do estrutural confirmou o degrau de 7 cm nos casos L303 e L328. A correção geral
resultou em 852,12 m, enquanto L314 passou a 852,19 m. L317 e L320 continuam pendentes;
L319 tem múltiplas cotas contidas e inferência conflitante. Candidatos rejeitados permanecem
visíveis e não entram no contexto escalar seguro enviado ao SA. L309/L319 conservam cotas
por parte. Referência de pavimento em pilares não equivale a medição individual.

O percentual do relatório canônico é um escore de evidência, não probabilidade calibrada.
Os pesos E1–E9 ainda exigem a calibração humana prevista acima. Nenhum selo Arete integral
foi emitido: a matriz de campos mantém pendências e nove diferenças geométricas de FV
exigem revisão visual própria. Os 17 segmentos a menos que o snapshot anterior são
unificações com cobertura preservada, não desaparecimento de peças.

## Convenção por segmento e face — decisão do dono, 2026-10-01

Vigas têm uma linha por item, com uma linha de texto por segmento FV em Nível obtido.
Nível Segmentos Laterais discrimina A/B Para/Passa e seus trechos: o vínculo com FV
é espacial, nunca por igualdade de índice. FV usa cortes; LV usa cortes/lajes e pode
completar FV sem evidência suficiente. O retorno FV→LV conserva a origem independente
e não cria confirmação circular. Pilar exibe o nível final do contato mais alto com
laje/viga e a face correspondente; base permanece na própria coluna.

Implementação v6: sementes LV independentes congeladas; cobertura única mínima de 80%
para completar FV, sem somar Para/Passa duplicadas. LV recebe intervalos geométricos
por sobreposição, podendo conter vários níveis no mesmo segmento; não há média.
Cortes com duas marcas vermelhas paralelas de interrupção não permitem converter
a altura desenhada em desnível absoluto. No 13_PAV, sete cortes foram rejeitados
por esse motivo (PNG L316 no relatório).

Confiança é suporte de evidência rastreável, não probabilidade calibrada. Origem CAD
95; referência geral 25; estimativa 30; inferência 55 ou 65 conforme método; demais
evidências 75. Pendências de origem recebem descontos explícitos. Cada transferência
usa a fonte mais fraca e fator espacial <=1. Ausência de nível tem 0; níveis por
trecho conservam seus escores individuais. Campos automáticos sem origem
independente ficam limitados a 30. Os pesos E1–E9 ainda aguardam a calibração prevista.

QA: 92 testes na rodada principal, 16 reexecutados após o ajuste final; nova coleta
na fila oficial concluída em 13_PAV, 478 geometrias preservadas frente à versão
anterior, 668 fatos com cálculo de confiança, proveniência sem ciclos. Browser:
46 pilares, 36 vigas, 31 lajes sem repetição; 86 linhas FV e 541 trechos LV.
30 dos 35 pilares existentes têm topo associado; P9/P10/P25/P34/P35 pendentes.
Persistem fontes fracas, níveis múltiplos e conflitos, expressos na ficha. Não há
validação humana de todos os fatos nem selo Arete integral. Relatório:
`scripts/arete/relatorios/20261001-niveis-segmentos/RELATORIO.md`.

## Investigação de contato fraco de pilar — 2026-10-01

Um limiar de confiança não deve apagar contato geométrico com nível apoiado em fontes independentes completas e concordantes. Conservar o valor como inferência com escore reduzido; não converter referência de pavimento ou escalar de laje multiparte em altitude comprovada. Relatório: `scripts/arete/relatorios/20261001-pilares-niveis/RELATORIO.md`. P10/P25 expõem a necessidade de sub-regiões L309/L319; P35 evidencia o risco de preencher nível no entorno da escada/vazio por fallback.
### QA de regiões multipartes e escadas — 2026-10-01

Na investigação de P10/P25 do 13_PAV, L309/L319 possuem cotas 852,16 e 852,19 dentro de um mesmo polígono. Linhas internas longas do layer de cotagem não constituem limites de parte. Antes de poligonizar uma região, verificar a semântica da entidade; dimensão atravessando a laje não prova descontinuidade de nível. Os degraus de 3 cm dos cortes exigem associação da posição e do sentido da seção à parte tocada pela face do pilar. Não tomar a cota maior do polígono inteiro nem proximidade isolada como resolução.

No contorno de escada/vazio (P35), continuidade em planta de uma viga e igualdade de seção não demonstram continuidade de altitude. Sem cota/corte ou referência independente vinculada ao trecho, manter pendência; não promover estimativa automática sem origem. A rodada oficial `f290601f-0580-4caa-86ef-077995c8402b` confirmou P9/P34 como inferidos (25,6%/34,2%) e preservou essas três pendências. Evidências e auditoria em `scripts/arete/relatorios/20261001-pilares-niveis/RELATORIO.md`.
