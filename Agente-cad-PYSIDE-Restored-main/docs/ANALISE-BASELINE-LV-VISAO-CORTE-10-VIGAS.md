# Baseline LV - Visao Corte N2 x N4

Data: 2026-06-22

## Escopo

- Classe exclusiva: Laterais de Viga (LV).
- Amostra: V301, V302, V305, V308, V310, V311, V322, V327, V330 e V331.
- Recortes: registros oficiais aprovados de `reverse_eng_recortes`.
- Resultado: 10 vigas e 13 visoes de corte comparadas.
- Artefatos: `sandbox_lv_loop/section_visual_10`.

## Baseline

| Indicador | Resultado |
|---|---:|
| Vigas | 10 |
| Pares N2/N4 | 13 |
| Cobertura media do contrato da ficha | 35,5% |
| Similaridade visual automatica preliminar | 10,8% |
| Menor / maior similaridade preliminar | 5,2% / 22,6% |
| Vigas em Arete | 0/10 |

A metrica visual automatica e apenas triagem de mascara normalizada. A inspecao
visual do agente confirmou o diagnostico: a fidelidade atual esta na faixa
critica e nao e um falso negativo causado somente pelo enquadramento.

## Contrato encontrado no Robo LV

O SCR e a ficha de engenharia trabalham com informacoes que ultrapassam
largura e altura:

- Identidade e contexto: lado, continuidade, apoios e textos de extremidade.
- Geometria: BxH, H1/H2, alturas dos lados A/B, niveis, fundo e lajes superior,
  central e inferior.
- Paineis: larguras, alturas, tipo H1/H2, modo Sarrafo/Garfo/Grade e medida da
  grade.
- Montagem: sarrafos verticais e de pressao por lado/faixa, barrote, tensor,
  presilhas, barras de ancoragem, parafusos/blocos e pontalete.
- Interferencias: pilares e aberturas de pilar/viga.
- Representacao: contorno do concreto, extensoes laterais, hatch, layers,
  cotas, textos e escala.

## Cobertura atual

O extrator de visao corte fornece principalmente:

`label`, `b`, `h_section`, `h_A`, `h_B`, `h_body_A`, `h_body_B` e quatro
espessuras de laje.

O gerador N4 consome somente:

`label`, `b`, `h_section`, `h_A` e `h_B`.

Portanto, mesmo os campos ja extraidos de corpo e laje nao comandam a
reproducao. A cobertura aparente do pequeno metodo do gerador e 100%, mas a
cobertura do contrato necessario e somente 35,5%.

## Gaps criticos

1. `draw_section_detail` deriva quase toda a secao de um unico molde V22.
2. O concreto e sempre desenhado com topologia em L, mesmo nos cortes U retos.
3. Barrote, tensor, presilhas, ancoragens, blocos, hatch e pontalete sao
   sintetizados sem evidencia individual da ficha.
4. Extensoes de laje esquerda/direita e fundo largo nao possuem parametros
   geometricos suficientes.
5. A associacao de cotas usa uma janela ampla; V322, por exemplo, recebe lajes
   de 13 cm que nao sao confirmadas visualmente no corte isolado.
6. Textos e cotas do N4 tem escala e posicionamento muito diferentes do N2.
7. Nao existe gate que impeca a geracao quando a ficha e incompleta ou
   contraditoria.

## Ataque

### Gate 40%

- Contagem de visoes correta nas 10 vigas.
- B, H e alturas A/B corretas.
- Classificacao de topologia: U reto, extensao esquerda, extensao direita,
  bilateral e fundo largo.
- Nenhum elemento estrutural inventado.

### Gate 60%

- Extrair extensoes e espessuras por lado.
- Extrair fundo, painel A/B/C e contorno do concreto.
- Gerador totalmente parametrico para as cinco topologias observadas.

### Gate 80%

- Modos Sarrafo/Garfo/Grade, sarrafos, ancoragens e demais componentes
  condicionados por evidencia.
- Layers, hatch e blocos coerentes com o N2.
- Cotas e textos com escala relativa correta.

### Gate 90%

- Ficha N2 e ficha N4 semanticamente equivalentes.
- Reextracao do DXF N4 recompõe a mesma ficha sem divergencia critica.
- Similaridade visual por corte >= 90% nas 10 vigas.

### Gate 95% - Arete automatico

- Todos os cortes das 10 vigas >= 95%.
- Cobertura de campos obrigatorios >= 95%.
- Zero alucinacao de topologia ou componente.
- Contagem, dimensoes, layers e elementos obrigatorios aprovados.

### Gate 100% - Arete certificado

- Gate 95% atendido.
- Inspecao visual humana aprova todos os pares sem ressalva.
- Hashes, fichas, imagens e vereditos ficam congelados como regressao.

## Ordem de implementacao

1. Criar `SectionViewFichaV2` com evidencia, confianca e campos opcionais.
2. Extrair topologia e extensoes diretamente dos componentes geometricos do
   corte, usando as cotas apenas como confirmacao.
3. Substituir o molde fixo por montagem parametrica e condicional.
4. Reexecutar as 10 vigas em cada alteracao e bloquear regressao por viga.
5. So promover para producao depois do gate 95% e da validacao humana.

## Iteracao 1

- O extrator passou a registrar o perfil estruturado do layer `CONCRETO`.
- Novos campos: `topology`, `body_width_cm`, `extension_left_cm`,
  `extension_right_cm`, `concrete_profiles`, `concrete_segments` e
  `profile_source`.
- As 13 visoes foram classificadas nas topologias observadas: U reto, extensao
  direita, bilateral e fundo largo.
- Um gerador experimental no sandbox substituiu o molde fixo pela forma
  extraida e suprimiu componentes sem evidencia.
- Similaridade automatica media: 10,8% -> 23,0%.
- Faixa da iteracao: 10,8% -> 35,4%.
- Resultado humano: topologia principal aprovada em 13/13; acabamento,
  componentes, cotas e escala ainda reprovados.
- Situacao: ganho aceito no sandbox, ainda nao promovido para a interface.

## Iteracoes 2 a 5

- A ficha passou a carregar primitivas visuais normalizadas por layer:
  linhas, polilinhas, textos e hachuras.
- O N4 experimental reconstrói essas primitivas a partir do JSON, sem consultar
  novamente o DXF N2.
- Foram reproduzidos `CONCRETO`, `Paineis`, `Madeira`, `Hachura`,
  `SARR_3.5x7`, cotas de secao e textos de detalhes.
- A comparação foi separada em componente e contexto. O contexto original
  permanece contaminado por desenhos vizinhos em algumas vigas e nao pode ser
  usado sozinho como score de fidelidade do corte.
- Inspecao do agente sobre o componente: media 85,8%, minimo 80%, maximo 95%.
- Resultado do gate 70: 13/13 cortes e 10/10 vigas aprovados.
- Roundtrip N4: 13/13 DXFs retornaram uma ficha com B, H e topologia identicos.
- O extrator agora aceita DXF contendo somente visao corte, sem exigir as faces
  laterais A/B no mesmo arquivo.
- Situacao: gate visual 70 atingido no sandbox. Ainda nao e Arete 95 e ainda nao
  foi conectado a interface de producao.
