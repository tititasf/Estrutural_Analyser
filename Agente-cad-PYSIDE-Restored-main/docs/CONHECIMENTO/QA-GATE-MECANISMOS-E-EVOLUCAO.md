# QA Gate Pós-SA: Mecanismos de Funcionamento, Classes e Roteiro de Evolução

**Status:** canônico · **Criado:** 2026-10-09 · **Escopo:** global (todas as obras e pavimentos)  
**Autoridade:** Complementa [Mapa do Conhecimento](MAPA-DO-CONHECIMENTO.md), [Decisões do Dono](DECISOES-DO-DONO.md) e manuais de classe em `docs/SA-ANALISE/CLASSES/`.  
**Evidência Datada:** Relatório consolidado `scripts/arete/relatorios/20261004_qa_jev_fv_f0_f2/RELATORIO_FINAL_20261009_R1_R6.md` (pid 27236, 13_PAV, Obra_TREINO_1).

---

## 1. O que é o QA Gate e por que ele é Evolutivo

O **QA Gate** (`portal/app/qa_cad_gate.py`) é a camada de verificação e auditoria que atua **imediatamente após a interpretação do Structural Analyzer (SA)** e antes da consolidação final de fôrmas (N3/N5).

Historicamente, a revisão de divergências pós-SA dependia de filas lentas de CLIs agentivas ou inspeção humana manual, demorando minutos ou horas por pavimento. O QA Gate substitui essa dependência por uma arquitetura em duas camadas:
1. **Núcleo Determinístico (Alta Velocidade, Custo Zero)**: Varredura topológica no DXF bruto/recorte em milissegundos, aplicando regras matemáticas rígidas de contato, cotas e quiralidade.
2. **Camada de Raciocínio Delimitado (Opt-in, Apenas Resíduo)**: Para o resíduo onde há ambiguidade real de desenho, o gate formula perguntas de lista fechada com opções ancoradas em *handles* do DXF e controle de remoção negativo obrigatório.

### Por que o Gate é Evolutivo?
O gate não é estático nem depende de re-treinamento de redes neurais pesadas. Sua evolução segue o **ciclo Aretê**:
- Cada pavimento ou obra processada que gera resíduo não certificado ou dúvida humana tem sua geometria dissecada;
- A regra geométrica que resolve o caso é codificada no gate com teste de mutação;
- O percentual de cobertura automática aumenta progressivamente (de 80% para 95%+), mantendo **zero aprovações falsas**.

---

## 2. Princípios Norteadores Inegociáveis

1. **A Medida continua dona do número**: Se o algoritmo geométrico encontra uma cota ou geometria consistente no CAD, esse valor é soberano. Nenhuma LLM ou estimativa visual pode sobrescrever uma medida.
2. **Tolerância Zero a Aprovações Falsas**: Em fôrmas para concreto armado, validar uma dimensão errada causa fabricação de peça incorreta, montagem no vazio e colapso na concretagem. Uma única aprovação falsa elimina o caminho do modelo.
3. **Resíduo Não Certificado vs. Alucinação**: Se não há candidatos determinísticos no desenho, o veredito correto é `nao_certificado`, abrindo ficha técnica humana (HTML). Chutar respostas por proximidade é expressamente proibido.
4. **Isolamento de Produção**: O QA Gate audita o estado gerado pelo SA sem sobrescrever arquivos de projeto em `DADOS-OBRAS` até que haja validação formal.

---

## 3. Mecanismos de Funcionamento por Classe Estrutural

### 3.1 Fundo de Viga (FV)
No 13º pavimento (Obra_TREINO_1), o gate auditou 321 campos em **49,2 segundos**, atingindo **81,3% de resolução automática**:

* **Cotas de Nível**:
  * O gate extrai marcadores de cota de nível e datum na vizinhança imediata de cada trecho de viga (ex.: cotas de rebaixo BD1-BDA).
  * Regra: Se todas as cotas identificadas para o trecho forem coincidentes com handles válidos, o valor é certificado a 100% de confiança.
  * *Resultado comprovado*: O gate identificou com 100% de certeza que V301 (trechos 7, 8, 15, 16) e V306 (trecho 4) possuíam nível 852.16 (rebaixo de desnível), corrigindo o erro do SA que havia inferido 852.19.
* **Lajes Adjacentes de Topo**:
  * O gate verifica o contato geométrico das lajes vizinhas no nível exato de apoio da viga.
  * *Resultado comprovado*: Corrigiu lajes atribuídas incorretamente pelo SA fora da zona de contato em V302 (trechos 4 e 8), V303 (t4), V315 (t2), V317 (t2) e V318 (t1).
* **Seção Transversal**:
  * Compara a anotação de texto (ex.: `19/55`) com a largura medida entre os contornos de fundo.
* **Visão de Corte vs. Abertura no Fundo**:
  * Peças locais com vão próprio $\le 100\text{ cm}$ e saída $\le 50\text{ cm}$, agrupadas por distância $\le 4\text{ cm}$ e com preenchimento interno residual $\le 1\text{ cm}^2$ são **visão de corte**, nunca furos ou aberturas no fundo da viga. Não segmentam o fundo.

### 3.2 Pilar (PIL)
Auditado em **0,7 segundos** (85 campos no corpus):

* **Geometria de Seção**:
  * Valida contornos poligonais retangulares e polilinhas (`LWPOLYLINE`), verificando fechamento geométrico real mesmo quando a flag nativa do DXF indica `Closed=false`.
* **Quiralidade Orientada (`dist_esq` e `dist_dir`)**:
  * O gate corrigiu a limitação da lista ordenada cega `[0, 52]`, que destruía a orientação física da peça de fôrma.
  * O modelo formal agora utiliza o vetor orientador ao longo do eixo da viga de apoio:
    $$\text{P1 Face B / VF301}: \quad \text{dist\_esq} = 52.0\text{ cm}, \quad \text{dist\_dir} = 0.0\text{ cm}, \quad \text{espessura} = 14.0\text{ cm}$$
* **Regra Anti-Proximidade**:
  * É proibido atribuir posições ou recuos de pilares por mera proximidade euclidiana de textos de chamada. A associação exige correspondência vetorial com a parede de contato.
* **Estado verificado em 2026-10-10 (publicado na VPS, ledger `e11ef77`):**
  * A comparação de distâncias com o SA é **sem orientação** (`sorted`): `dist_esq_cm`/`dist_dir_cm` são gravados no relatório, mas a convenção esq/dir por face ainda não foi conferida contra o SA, então não bloqueiam.
  * Parede que **atravessa** a face conta (viga com a largura do pilar, P42/P46/P48/P51 no 13_PAV); só o trecho externo vale para achar o rótulo. Com dois rótulos na parede contínua, vale o do **primeiro vão** até a primeira parede perpendicular que encosta no corredor.
  * Face sem parede que chegue ou atravesse **não é link fantasma**: fica `uncertain` com `ghost_suspect` (bloqueia a promoção até conferência). Nada é removido do snapshot. Motivo: no 13_PAV, 11 dos 13 "fantasmas" do desenho anterior eram vigas reais.

### 3.3 Extensões em Planejamento: Lateral de Viga (LV) e Lajes (LAJ)

* **Lateral de Viga (LV)**:
  * Verificação de sarrafos e garfos conforme padrão STOG/Formascia.
  * Validação de desconto de altura útil da lateral com base na espessura $h$ da laje de apoio adjacente.
  * Aplicação do contrato de cortes interpretados (eliminar duplicatas de símbolos de corte).
  * **Fora do gate de adoção (2026-10-10):** `measure_lateral_beams` existe e tem testes, mas `for_snapshot` não despacha LV. Pendências para religar: trocar o regex de nome de layer (CORTE/COTA/DIM) por `cad_object_recognition.section_layer`; usar a laje **da face** e o perfil por região (`slab_steps`, desníveis) em vez de `slabs[0]` e `h_viga − h_laje`; tirar a seção do primeiro texto `b/h` num raio de 150 cm (proximidade).
* **Lajes (LAJ)**:
  * Cruzamento da espessura anotada (ex.: `L309 h=13`) com polígonos fechados de contorno.
  * Tratamento de múltiplos marcadores de nível dentro do mesmo pano de laje (ex.: 852.19 e 852.16 em regiões com rebaixo para impermeabilização/área molhada).

---

## 4. Integração Delimitada de Raciocínio LLM (Jev / NVIDIA)

O QA Gate **não delega cálculos numéricos nem medições a modelos de IA**. A IA é utilizada estritamente como juiz auxiliar em dúvidas de classificação fechada do resíduo, sob regras formais:

```
                  ┌─────────────────────────────────────────┐
                  │          ESTADO BRUTO PÓS-SA            │
                  └────────────────────┬────────────────────┘
                                       │
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │    MEDIÇÃO DETERMINÍSTICA NO DXF        │
                  │        (portal/app/qa_cad_gate.py)      │
                  └────────────┬───────────────────────┬────┘
                               │                       │
                     [Valor Encontrado]       [Ambiguidade / Resíduo]
                               │                       │
                               ▼                       ▼
                  ┌─────────────────────────┐ ┌─────────────────────────┐
                  │   VEREDITO DO GATE      │ │ PERGUNTA LISTA FECHADA  │
                  │  - Acordo (medido)      │ │  (schema v1 + handles)  │
                  │  - Divergente (aplicar) │ └────────────┬────────────┘
                  └─────────────────────────┘              │
                                                           ▼
                                              ┌─────────────────────────┐
                                              │   CONTROLE DE REMOÇÃO   │
                                              │   (Evidência suprimida) │
                                              └────────────┬────────────┘
                                                           │
                                                [Retornou INSUFFICIENT?]
                                                    │             │
                                                  (Sim)         (Não)
                                                    │             │
                                                    ▼             ▼
                                              ┌──────────┐  ┌───────────┐
                                              │ Consulta │  │ Descarte  │
                                              │ Jev/LLM  │  │ Sumário   │
                                              └──────────┘  │ (Ficha)   │
                                                            └───────────┘
```

### Regras do Pacote de Consulta:
1. **Schema Obrigatório**: `cad.qa_pergunta_residuo/v1`.
2. **Alternativas Ancoradas**: Cada opção deve referenciar entidades explícitas com *handles* do DXF.
3. **Opção `INSUFFICIENT`**: Obrigatória em todas as perguntas.
4. **Controle Negativo de Remoção**: A pergunta é duplicada sem a evidência textual/vetorial. Se o modelo não responder `INSUFFICIENT` no controle, o modelo falhou e a pergunta é descartada para evitar alucinação.
5. **Confiança Probabilística**: Confiança de modelo só pode ser expressa após calibração em conjunto disjunto (ex.: 14_PAV cego). Declarações em texto ("tenho 95% de certeza") têm valor nulo.

---

## 5. Roteiro de Progressão e Evolução Contínua (Roadmap Aretê)

| Fase | Escopo | Mecanismo de Avanço | Meta de Cobertura | Status |
|:---:|---|---|:---:|:---:|
| **Fase 1** | FV Nível, Seção e Lajes + PIL básico | Medição algorítmica no DXF (`qa_cad_gate.py`) | 80%+ automático | **Concluído (13_PAV)** |
| **Fase 2** | Quiralidade de PIL (`dist_esq`/`dist_dir`) e paredes paralelas | Vetores direcionais e desempate geométrico | 90%+ em PIL | Em implementação |
| **Fase 3** | LV (Laterais de Viga) e Encontros | Integração do filtro de visão de corte com N3/N5 | 85%+ em LV | Planejado |
| **Fase 4** | LAJ (Lajes, espessuras e rebaixos) | Extração de contornos e marcadores múltiplos | 90%+ em LAJ | Planejado |
| **Fase 5** | Pós-SA Integrado no Portal | Execução automática pós-análise; fichas HTML apenas para resíduo $\le 5\%$ | **100% Aretê** | Planejado |

---

## 6. Governança e Salvaguardas no Portal

- **Não alteração da VPS em experimentação**: Nenhuma rotina de teste deve ser publicada na VPS sem overlay `/tmp/ovl` e sem validação prévia em testes locais (mínimo de 72 testes verdes no gate).
- **RAG e Base Global**: Este documento serve como fonte canônica de recuperação pelo RAG. O RAG recupera os contratos, mas quem executa o teste é o script determinístico local.
- **Transparência de Divergências**: Toda divergência encontrada pelo gate deve registrar o valor antigo do SA, o valor medido no CAD, os handles de prova e a causa-raiz física.
