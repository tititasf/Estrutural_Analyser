# Formascia — laterais de viga (LV)

**Histórico experimental anterior. Substituído pelo [padrão aprovado](PADRAO-FORMASCIA-LATERAIS-APROVADO.md) em 07/10/2026.**
As tabelas abaixo descrevem a tentativa local anterior; não certificam fidelidade
à referência nem integração publicada. Para e Passa têm configurações independentes,
cada uma com montagem sarrafeada ou gradeada. Nas gradeadas, o DXF unificado precisa
conter famílias separadas de painéis sem grades e grades soltas, ambas com todos os
mesmos cortes completos, cotas e identificação pertinentes.

Estudo e evidências: `scripts/arete/relatorios/20261007_formascia_lv_estudo_v01/RELATORIO.md`.
A paginação proposta usa unidades granulares já existentes, corte 2x com legenda
`CORTE — ESC. 1:25`, elevações 1x, margem livre de 50 desde a parede interna,
25 entre unidades da mesma viga, 60 entre vigas no mesmo eixo com separador tracejado,
e 45 entre linhas. Essas regras vieram da solicitação do usuário; o desenho
e a composição experimental ainda precisam da revisão visual prevista no procedimento.

Escopo desta especificação: MOLDE_1 / LV (Laterais Para e Laterais Passa).
Design baseado nos arquivos de referência originais em `D:/Agente-cad-PYSIDE/Exemplos Modos/FORMASCIA/`:
- `LATERAIS DE VIGA PAINEIS A B FORMASCIA.dxf`
- `LATERAIS DE VIGA GRADES SOLTAS FORMASCIA.dxf`
- `LATERAIS DE VIGA VISAO CORTE FORMASCIA.dxf`
- `MOLDURA ABCD LATERIAS DE VIGA OFRSMACIA.dxf`
- `MOLDURA GRADES SOLTAS LATERIAS DE VIGA OFRSMACIA.dxf`

A geometria e a segmentação de montagem seguem os contratos do Structural Analyzer (SA), inspirando-se no motor de produção NOVA para garantir exatidão estrutural sem alucinação de medidas.

## 1. Paleta e Camadas (N3)

| Componente | Camada | Cor ACI | Detalhes |
|---|---|---|---|
| Contorno de Painéis | `VIGAS` | 3 (Verde) | Retângulos e limites de chapa compensada |
| Sarrafos Horizontais (Sarrafeadas) | `ACABAMENTO` | 1 (Vermelho) | MLINE nativa estilo `EEEEEEEE` (seção 7 cm, escala 1.0, preenchimento BYLAYER) |
| Sarrafos Verticais / Bordas | `ACABAMENTO` | 1 (Vermelho) | MLINE nativa estilo `EEEEEEEE` (seção 7 cm) nos topos, fundos e extremidades |
| Grades: Travessas Horizontais | `Sarrafos` | 1 (Vermelho) | Barras horizontais superior e inferior (2,2 cm) |
| Grades: Pernas / Pontaletes | `Meio_pont.` | 43 (ou 2) | Montantes verticais seção 3,5 cm espaçados a cada ~30 cm |
| Numeração de Chapas | `NUMERAÇÃO DAS CHAPAS` | Círculo: 1 (Vermelho)<br>Texto: 7 (Branco) | Círculo raio 10 cm centrado no painel com texto altura 12 cm |
| Cotas | `cotas` | 4 (Ciano) | Dimstyle `FORMASCIA-PAINEL` com setas oblíquas `_Oblique`, texto altura 10 cm, linhas ciano |
| Títulos e Textos | `BNC_TEXTO` | 7 (Branco) | Nomes de vigas (altura 16,5 cm) e referências de pilares (altura 10 cm) |
| Vazios / Aberturas / Rebaixos | `BNC_HACHURA DE CONCRETO` | 8 (Cinza) | Hachura `AR-CONC` (concreto) escala 1.0, delimitada por contorno ciano |
| Sarrafos de Pressão (se houver) | `Sarrafo de pressão` | 1 (Vermelho) | Linha pontilhada (linetype `HIDDEN`) |

## 2. Visão de Corte

- Seção de concreto da viga em `VIGAS` (ACI 3) com hachura `AR-CONC` (ACI 8).
- Compensado lateral (espessura 2 cm) em `BNC_COMPENSADO` (ACI 7) ou `Painéis` (ACI 3).
- Madeiras e sarrafos em corte em `BNC_HACHURA MADEIRAS` / `ACABAMENTO` (ACI 1).
- Pernas de grade / pontaletes em `Meio_pont.` (ACI 43).
- Cotas em `cotas` (ACI 4) com estilo `SECAO` / `FORMASCIA-PAINEL`.
- Títulos e referências em `BNC_TEXTO` (ACI 7).

## 3. Comportamento e Variantes

- **Comportamentos:** `Passa` (prioritário) e `Para`.
- **Montagens:** `sarrafeadas` (com sarrafos corridos em MLINE) e `gradeadas` (com pontaletes verticais).
