# Contrato Rigido do Motor LV N3/N4

Data: 2026-07-21  
Status: contrato arquitetural e comportamento executavel (`lv_draw_contract/v2`)

## 1. Decisao central

O motor de Laterais de Viga e uma maquina deterministica de desenho. Ele nao
interpreta CAD, nao procura uma forma visual parecida e nao corrige uma ficha
durante a geracao.

```text
N1 --interpretador SA--> ficha executiva LV --motor compartilhado--> N3
N2 --motor reverso-----> ficha executiva LV --motor compartilhado--> N4
```

N1 e N2 sao origens independentes. Eles podem produzir fichas com o mesmo
contrato de desenho, mas nenhum deles pode consultar ou completar o outro.

Consequencia operacional:

- elemento ausente na ficha (abertura, laje, painel, pilar) e falha de leitura;
- elemento presente e correto na ficha, mas desenhado em medida/layer/posicao
  incorreta, e falha do motor;
- ficha invalida nao gera um desenho aproximado: a geracao falha com o caminho
  exato do campo ausente;
- a mesma projecao de campos de desenho produz o mesmo `drawing_fingerprint`.

## 2. Evidencia do robo de Laterais

O pacote disponivel em `_ROBOS_ABAS/Robo_Laterais_de_Vigas` e uma distribuicao
PyInstaller/obfuscada, nao o fonte aberto. O `Analysis-00.toc` identifica os
modulos originais:

- `robo_laterais_viga_pyside.py`;
- `gerador_script_viga.py`;
- `gerador_script_combinados.py`;
- `Ordenador_VIGA.py`;
- `Combinador_VIGA.py`.

O arquivo preservado `dist/dados_vigas_ultima_sessao.json` confirma a ficha do
robo: viga, lado, continuacao, largura/altura total, fundo, ate oito paineis,
`width`, `height1`, `height2`, tipo Grade/Sarrafeado, alturas de grade, lajes,
quatro vazios, sarrafos de extremidade e pilares. Portanto, o comportamento
original tambem e ficha -> script; coordenadas do desenho de origem nao fazem
parte do contrato do gerador.

O motor Python atual implementa a anatomia SCR documentada no cabecalho de
`scripts/gerar_lv_dxf_stog.py`: distribuicao por altura, Grade, sarrafos,
visao-corte, layers e cotas. A reforma preserva essas regras e remove a
re-interpretacao silenciosa do caminho N4.

## 3. Fronteiras e responsabilidades

| Componente | Pode fazer | Nao pode fazer |
|---|---|---|
| Interpretador N1 | Ler SA, classificar A/B e Para/Passa, publicar ficha N3 | Consultar N2/N4 |
| Interpretador N2 | Ler recorte aprovado, extrair secoes, unidades, paineis e vazios | Alterar o gerador para esconder erro de leitura |
| Adaptador | Renomear campos e unidades sem perda semantica | Criar lado, painel, altura ou abertura inexistente |
| Validador | Normalizar tipos, exigir invariantes, calcular fingerprint | Inferir geometria |
| Motor N3/N4 | Aplicar regras SCR fixas aos campos validados | Reler recorte, copiar A para B, autodistribuir ficha incompleta |
| QA | Comparar ficha, inventario e entidades DXF | Aprovar somente por semelhanca global |

## 4. Unidade atomica de desenho

Uma viga possui uma ou mais `face_units`. Cada unidade representa um segmento
executivo individual, com lado A ou B e uma cadeia ordenada de paineis.

Campos obrigatorios da ficha N4 estrita:

- identificacao: `viga`;
- secao: `b_cm`, `h_cm`, `h_B_cm`, `section_views[].h_section`;
- unidade: `face_units[].side`, `h_body`, `segments`;
- painel: `largura_cm`, `height1`, `panel_type`;
- os dois lados A e B precisam existir explicitamente.

Campos condicionais sao comandos de desenho, nao pistas:

- `holes[]`: vazio real do painel;
- `laje_sup_local`, `laje_inf_local`, `slab_center`: faixas de laje;
- `grade_h1`, `grade_h2`: geometria da Grade;
- `sarrafos_horizontais`, `sarrafos_verticais`: replay explicito;
- `sarrafo_vertical_esquerdo/direito`: fechamento de extremidade;
- `reuse_regions`: classificacao/regiao, sem hatch de painel no N4;
- `suppress_auto_sarrafos`: suprime expressamente a regra SCR automatica.

`bbox`, coordenadas absolutas e confianca pertencem a rastreabilidade do
interpretador. Eles nao mudam o desenho nem o fingerprint.

## 5. Regras fixas do motor

### 5.1 Paineis e sarrafos

- A ordem e a largura dos paineis sao exatamente as da ficha.
- Um painel nao nasce de linha de cota, sarrafo ou borda de abertura.
- Sem replay explicito de sarrafos, aplica-se a tabela SCR por altura do
  painel: `<15`, `15-30`, `30-80` e `>=80`.
- Painel de degrau continua recebendo sarrafos dentro da sua altura real.
- A supressao so ocorre por `suppress_auto_sarrafos=true`.

### 5.2 Degrau, abertura e cota interna

- `height1 < h_body` define o perfil de degrau e alinha o painel pelo topo.
- O ombro e geometria de `Painéis`; a cota do ombro e entidade `DIMENSION` em
  `COTA`.
- A cota interna de 65 cm e mantida quando o ombro mede 65 cm.
- A linha de extensao da cota nunca vira divisor vertical em `Painéis`.
- `holes[]` pertence ao painel que o declarou; o motor posiciona o vazio pelo
  `corner`, `width`, `height` e `position`, relativo a esse painel.

### 5.3 Hachuras N4

- painel nao recebe hatch;
- reaproveitamento nao recebe hatch;
- laje/perfil nao recebe hatch de painel;
- somente vazio/abertura explicito recebe `HATCH` na layer `Hachura`;
- a geometria de corte possui regras proprias e nao autoriza transportar
  primitivas do recorte N2 para as laterais.

### 5.4 Nomenclatura e layout

- cada `face_unit` e desenhada separadamente;
- o layout limpo pode reposicionar unidades, sem alterar sua geometria;
- a apresentacao/QA nomeia cada unidade como `SEGMENTO 1A`, `SEGMENTO 1B`,
  `SEGMENTO 2A` etc.; o identificador original permanece nos metadados;
- N2 e N4 de uma unidade devem ser comparados lado a lado; unidades sucessivas
  aparecem em linhas sucessivas.

## 6. Caminhos N3 e N4

### N3

`src/core/lv_generation_contract.py` converte os vinculos canonicos SA em
quatro fichas isoladas: A/B x Para/Passa. A conversao define paineis executivos
e publica `generation_ready`. O gerador recebe `--behavior` e nao carrega
`fichas_lv_v2.json`.

### N4

`scripts/motor_reverso_lv.py` extrai a ficha N2. Em seguida:

1. `validate_n4_ficha` valida e normaliza a ficha;
2. `gerar_lv_n4_fichas.py` materializa o mesmo formato consumido pelo motor;
3. `gerar_lv_dxf_stog.py --strict-contract` desenha;
4. a ficha fornecida e autoritativa.

Reextrair o recorte e uma nova operacao do interpretador. Ela so ocorre com
`--refresh-from-recorte`; nunca como fallback escondido durante a geracao.

## 7. Invariantes verificaveis

- ficha sem A ou B: erro, nunca copia do outro lado;
- largura/altura zero: erro com caminho do campo;
- mudar somente `bbox` ou confianca: mesmo fingerprint;
- mudar largura, altura, painel, vazio ou sarrafo: novo fingerprint;
- degrau 109/44: cota interna 65 em `COTA`;
- no mesmo degrau, nenhuma vertical baixa indevida em `Painéis`;
- lateral sem vazio: zero HATCH;
- lateral com um vazio: exatamente o hatch desse vazio.

## 8. Regra para evolucao

Uma correcao no motor precisa ser expressa como regra universal de ficha e ter
teste positivo e de controle. Condicao pelo nome `V301`, coordenada do recorte
ou score visual nao e regra de motor. Se a informacao necessaria nao existe na
ficha, primeiro corrige-se o interpretador/contrato; so depois o motor aplica o
campo de forma deterministica.

