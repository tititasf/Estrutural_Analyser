# Masterplan — QA por Jev + travas CAD (sem Grok, sem humano no laço)

Criado 2026-10-04. Decisão do dono: o QA agêntico por CLI (Grok/Gemini, 15–40 min
por item) está **reprovado por performance**; a fila foi parada. O dono delegou as
decisões deste plano ("confio em você, você decide").

## 1. Princípio

Cada campo da interpretação SA de cada classe vira **uma pergunta atômica**, e cada
pergunta tem um único dono:

| Tipo | Quem responde | Saída |
|---|---|---|
| **MEDIDA** | código sobre o DXF original (`portal/app/qa_cad_gate.py`) | valor + handles; divergência = FAIL |
| **SEMÂNTICA** | Jev (`jev-1.13.0`, TypeSafe), escolha fechada entre candidatos já extraídos | opção ou `INSUFFICIENT` |
| **CONVENÇÃO** | regra codificada a partir de `DECISOES-DO-DONO.md` / manual da classe | regra aplicada |

Regra dura (lição v9, `JEV-CAPACIDADES-E-REGISTRO-DE-MEDICAO.md`): **Jev nunca calcula**
distância, contato, coordenada ou soma. Errou contato a 5 unidades com confiança 0,76 e
mudou de resposta só por translação. Matemática é do código.

## 2. "Visão" do Jev = cena geométrica canônica

Sem imagem. Para cada pergunta, um JSON local (≤ 16 KB):

- entidades do DXF Fase-1 próximas (LINE/LWPOLYLINE/TEXT/contornos) com handle;
- coordenadas **normalizadas**: origem no item, eixo da viga = +x, cm, arredondadas a 0,1;
- relações já computadas pelo código como FACT (ex.: "parede h2F8 perpendicular ao eixo
  em x=0, cobre a faixa inteira"), para o Jev julgar significado, não geometria;
- a hipótese SA **fica fora** da cena (pergunta cega); a comparação com SA é posterior.

## 3. Confiabilidade sem humano

1. **Mutações plantadas** (resposta conhecida por construção): deslocar contorno uma
   largura, trocar largura/rótulo/nível, apagar parede de apoio, inverter face. Gera
   negativos ilimitados.
2. **Positivos medidos**: unidades em que todas as travas mediram concordância, mais o
   golden selado.
3. **Controles metamórficos**: translação, rotação 90°, espelho, ordem dos candidatos
   permutada; retirada da evidência decisiva tem de dar `INSUFFICIENT`.
4. **Licença por tipo de pergunta**: só entra no QA o tipo com **zero falsa aprovação**
   na amostra fixa (positivos + mutações) e estabilidade 100% nas variantes
   equivalentes. Sem licença = a pergunta não é feita (campo fica não certificado).
5. **Produção**: 3 variantes equivalentes por pergunta; unânimes valem, senão
   `INSUFFICIENT`. Proibido repetir até obter a resposta desejada.

## 4. Veredito por item

- **FAIL**: qualquer MEDIDA divergente ou SEMÂNTICA licenciada contrária ao SA.
- **PASS**: todos os campos cobertos (trava ou pergunta licenciada) e concordantes.
- **NÃO CERTIFICADO**: algum campo sem cobertura ou `INSUFFICIENT`. Mostrado como tal;
  nunca vira PASS nem vai para Grok/humano automaticamente.

O QA continua avaliando o SA; correção nasce como camada e só substitui o SA por
validação humana (regra vigente, inalterada).

## 5. Fases

| Fase | Entrega | Tokens Jev |
|---|---|---|
| F0 | Matriz campo × tipo × pergunta por classe (§6) | 0 |
| F1 | Montador de cena canônica + variantes metamórficas | 0 |
| F2 | Travas MEDIDA completas por classe | 0 |
| F3 | Banco de casos: positivos medidos + mutações | 0 |
| F4 | Calibração e licença por tipo de pergunta | poucos (≈1 k tokens/chamada, ~0,3 s) |
| F5 | Orquestrador QA-Jev no portal em modo sombra (substitui a fila CLI) | produção |
| F6 | Prova: 13_PAV × achados Grok já registrados; 14_PAV como teste cego | produção |

Ordem das classes: **FV → LAJ → PIL → LV** (geometria mais simples primeiro; LV por
último por ser a mais difícil, apesar de ter mais pesquisa Jev acumulada).

Infra: SDK `typesafe_sdk` e `TYPESAFE_API_KEY` existem só na máquina local; a VPS não
tem nenhum dos dois. Até F5 tudo roda local/read-only; instalar na VPS é passo de F5.

Meta de desempenho: < 1 min por item; 124 itens do 13_PAV em minutos.

## 6. F0 — matriz FV (snapshot `cad.qa_interpretation/v1`, coleção `fundo`)

| Campo | Família (manual FV §2) | Tipo | Pergunta / medida | Estado |
|---|---|---|---|---|
| `points` | geometria | MEDIDA | arestas longas sobre paredes originais colineares (≥50%); aresta sem traço = deslocado | trava pronta (33 vigas: 0 erro; mutação 65/65) |
| `width` | comprimento/largura | MEDIDA | bw único escrito na faixa da viga = `width`; largura do retângulo = bw | trava pronta (58 medidos; mutação 58/58) |
| `beam_name` | identidade | MEDIDA | único rótulo `V…` na faixa = `beam_name` | trava pronta (dentro de `seção`) |
| `length` / extremos | comprimento + apoios locais | MEDIDA | cada extremo coincide com traço perpendicular original (parede de viga que cruza, face de pilar, fim de viga) cobrindo a faixa | **a fazer (F2)** |
| ordem/quantidade | ordem/quantidade | MEDIDA | segmentos da mesma viga não se sobrepõem e não deixam vão na faixa contínua | **a fazer (F2)** |
| natureza do limite | apoios locais | SEMÂNTICA | "o que encerra este extremo?" {pilar sólido, viga que cruza, fim da viga, pilar NASCE, INSUFFICIENT} com candidatos extraídos | F1/F4 — 04/10: pergunta dos 7 extremos "só de um lado" **reprovada** (0 acerto, 21 erros, retirada falhou) → trava de chegada lateral (D-90/FV §4) feita 04/10: 6/7 medidos; extremo na face distante de elemento atravessado = NC (7) até provar pelo fundo da outra viga |
| pilar NASCE | exceção (D-65) | CONVENÇÃO + MEDIDA | símbolo X da convenção do pavimento dentro do contorno do pilar → não pode limitar o fundo | **feito 04/10**: só contorno fechado reconhecido NASCE vira nota "pilar que nasce"; sem convenção → NC |
| `level` / `level_slabs` | nível | MEDIDA + CONVENÇÃO | lajes que tocam o segmento e cota escrita em cada; por região (degrau com cota própria segue a principal). Laje sem cota = padrão do pavimento só com ausência de HATCH/SOLID provada no original e vizinhas concordantes. Marca de corte: a trava lê a elevação (`_section_level`); plano no datum não bloqueia; degrau desenhado ou nível ≠ datum não certifica e não atribui o valor | 5ª passada 04/10: nível medido 54/75, 0 divergência com o SA. B-B do 13_PAV plano em 852,19 (não resolve 3 cm). A-A sem sentido |
| tags / líderes | apresentação | MEDIDA | transformação DXF→SVG medida; cada S# uma vez, marcador na âncora do renderer (≤0,5 cm) | Rodada 04/10 pid 27236: 92 medidos, 0 erro, 4 sem transformação (V324, V326, V327, V329). Os 35 erros da 5ª passada eram SVG de agosto |
| aberturas/furos | exceções | SEMÂNTICA | exceção só se intersecta o polígono local (piloto `jev_fv_scope_audit.py`) | trava 04/10: interior vazio ou só anotação (cota, tracejado passante, NASCE, visão corte desenhada na planta) e sem outro preenchimento no original = medida. A visão corte é alma e braços, forma livre, de um lado ou dos dois; a cota não decide (FV-VISAO-CORTE-T-20261004). Não abre o fundo. Outro traço ou preenchimento no miolo continua NC. No pid 27236, `probe_aberturas_nc.json` ficou só com a V330 trecho 1 (traços 295, 442, 443, 445). A conta 43 medidas / 22 NC é anterior; o veredito dos 96 não foi recontado |
| `status`/`atencao` | consistência | CONVENÇÃO | coerência com os resultados acima | F5 |
| contorno inclinado (V302 s9, V306 s1, V307, V314, V316, V319–V322) | geometria | MEDIDA | hoje `uncertain` (só eixos x/y); generalizar para eixo rotacionado | F2 |

Estado FV 13_PAV, 8 critérios, fim da 5ª passada (overlay `/tmp/ovl`, SVG de agosto): **PASS 20 / NC 20 / FAIL 35**. Nível medido 54, sem divergência com o SA. Os 35 FAIL eram tags fora da âncora.

Rodada do SA atual (04/10, pid 27236, quatro classes, banco em leitura, pack em `scripts/arete/html_fichas/Obra_TREINO_1/`): **96 trechos, PASS 19 / NC 65 / FAIL 12**. Tags 92/0/4. Os 12 FAIL são medida contra o SA desta rodada (5 níveis 852,16×852,19, 6 lajes do nível, VF301 trecho 8 com bw 19×largura 14). Mutações dos 19 PASS: 0 falsa aprovação. Detalhe no RELATORIO da pasta `20261004_qa_jev_fv_f0_f2`. Não promovido para `DADOS-OBRAS` nem publicado na VPS. A regra da visão corte entrou depois dessa conta e, no mesmo dia, passou a cobrir o desenho inteiro da ficha `DUVIDAS-ABERTURAS-FV.html`, sem exigir cota nem haste dos dois lados. O veredito PASS/NC/FAIL dos 96 não foi recontado. No critério de aberturas, o pid 27236 ficou sem certificar só a V330 trecho 1, pelos traços 295, 442, 443 e 445. Os 12 FAIL de nível e de seção não mudaram.

## 7. Registro

Cada rodada grava `scripts/arete/relatorios/<timestamp>_qa_jev_<classe>_<fase>/RELATORIO.md`
com denominadores, hashes e o próximo FAIL.

## 8. Plano realista, classe por classe (dono, 04/10)

Regras acertadas com o dono em 04/10:
- **Iterar o desenho da pergunta é livre** (representação, instrução, opções); licença só
  com itens que não entraram no ajuste (divisão desenvolvimento × validação) + mutações.
  Repetir a mesma pergunta no mesmo item até obter a resposta desejada continua proibido.
- Zero falsa aprovação mantido: a qualidade do SA não pode cair.
- Classe por classe: FV até o fim; o aprendizado decide como abrir LAJ → PIL → LV.

Referência externa (TypeSafe): Jev não recebe imagem; contexto 32 K; Choice devolve
probabilidade de cada opção, Noul é sim/não com probabilidade; recomendação do
fabricante = **perguntas atômicas e independentes**, combinadas no código.

Hipóteses a validar na FV, cada uma com medição própria:
1. **Leitura geométrica** (ideia do dono): perguntas atômicas sobre a cena ("o fundo vai
   de A a B?", "há traço atravessando o caminho entre A e B?"), com gabarito calculado
   pelo código (respostas conhecidas por construção, ilimitadas via mutação). Comparar
   representações: R1 entidades cruas normalizadas; R2 trilha linear de eventos ao longo
   do eixo; R3 mapa em texto (raster ASCII). Se nenhuma passar, conclusão registrada:
   geometria fica só no código.
2. **Confirmação cega de afirmação do SA**: a afirmação vai misturada a alternativas
   falsas (nunca "isto é verdade?"), com mutações; mede viés para o "sim".
3. **Significado**: só onde o código não decide (associação texto↔elemento, símbolo).

Saída por classe: para cada campo — trava (código), convenção (dono), pergunta Jev
licenciada, ou NÃO CERTIFICADO — com números.
