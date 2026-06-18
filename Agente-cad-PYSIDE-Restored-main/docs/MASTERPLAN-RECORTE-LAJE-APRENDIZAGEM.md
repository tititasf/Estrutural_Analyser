# MASTERPLAN - Recorte LAJ: Aprendizagem por Aprovacoes Humanas

**Versao:** 0.1
**Data:** 2026-06-16
**Status:** PROPOSTA CONTROLADA - nao substitui o motor atual
**Escopo inicial:** LAJ, Obra_TREINO_1, pavimentos aprovados pelo humano
**Complementa:** `MASTERPLAN-ARETE-LAJE.md` e `MASTERPLAN-ARETE-QUALITY-GATES.md`

---

## 0. Regra de Ouro

Tudo continua sendo motor universal. Zero hardcode por laje, pavimento ou obra.

O aprendizado nao pode virar caixa-preta que "parece bom". Em CAD estrutural, a saida precisa
ser auditavel, versionada e reversivel. Toda melhoria aprendida deve ser expressa como:

- parametro calibrado;
- regra geometrica geral;
- limiar de confianca;
- diagnostico de falha.

Nada aprendido de recorte `motor` ou `auto_aprovado` entra como verdade. Apenas `aprovado`
humano pode alimentar treino.

---

## 1. Objetivo

Criar um ciclo seguro onde cada recorte LAJ aprovado pelo humano melhora gradualmente:

- eficacia do motor de recorte;
- fechamento do marco fisico da laje;
- nao captura de laje vizinha;
- sinceridade da porcentagem de confianca;
- priorizacao de revisao humana.

O motor atual permanece como baseline. A aprendizagem entra primeiro como observacao e
relatorio. So depois de validada por regressao ela pode calibrar o motor.

---

## 2. Principio de Integridade Atual

Durante a fase inicial, o sistema nao deve quebrar o fluxo que hoje funciona:

1. Recortes `aprovado` nunca sao sobrescritos.
2. Recortes `motor` podem ser regenerados, mas sempre com backup e path novo.
3. `auto_aprovado` nao treina.
4. Se o calibrador tiver duvida, ele reduz confianca em vez de aprovar.
5. Todo ajuste aprendido precisa ser reprodutivel a partir do DB e dos DXFs.
6. O app deve conseguir abrir os recortes atuais mesmo se o modulo de aprendizagem estiver
   desativado.

Regra operacional: feature flag `RECORTE_LEARNING_ENABLED=false` por padrao ate a primeira
rodada de regressao verde.

---

## 3. Dados que Precisam Ser Versionados

Banco especifico desta frente:

```text
D:/Agente-cad-PYSIDE/engrev_laj_recorte_learning.vision
```

Este DB e exclusivo para aprendizagem/versionamento dos **recortes de lajes da engenharia
reversa**. O DB principal `project_data.vision` continua sendo a fonte dos recortes atuais
(`reverse_eng_recortes`) e das fichas; ele nao deve receber tabelas de aprendizagem LAJ.
Quando existirem outras partes/classes, cada uma deve ter nome de DB e tabelas igualmente
explicitos para evitar mistura de datasets.

### 3.1 Tabela: `engrev_laj_recorte_learning_events`

Registra cada evento humano ou de motor.

Campos sugeridos:

```sql
CREATE TABLE engrev_laj_recorte_learning_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    obra_name TEXT NOT NULL,
    pavimento TEXT,
    classe TEXT NOT NULL,
    elemento_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source_recorte_path TEXT,
    approved_recorte_path TEXT,
    motor_version TEXT,
    calibrator_version TEXT,
    operator TEXT,
    notes TEXT,
    source_hash TEXT,
    approved_hash TEXT
);
```

`event_type`:

- `motor_generated`
- `human_saved`
- `human_approved`
- `calibrator_suggested`
- `calibrator_applied`
- `regression_failed`
- `regression_passed`

### 3.2 Tabela: `engrev_laj_recorte_learning_features`

Armazena features geometricas extraidas dos pares motor/aprovado.

```sql
CREATE TABLE engrev_laj_recorte_learning_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    obra_name TEXT NOT NULL,
    pavimento TEXT,
    classe TEXT NOT NULL,
    elemento_id TEXT NOT NULL,
    bbox_motor_json TEXT,
    bbox_aprovado_json TEXT,
    delta_left REAL,
    delta_right REAL,
    delta_bottom REAL,
    delta_top REAL,
    entity_count_motor INTEGER,
    entity_count_aprovado INTEGER,
    own_label_count INTEGER,
    neighbor_label_count INTEGER,
    dimension_text_count INTEGER,
    panel_line_count INTEGER,
    contour_closure_score REAL,
    neighbor_capture_score REAL,
    confidence_before REAL,
    confidence_after REAL,
    features_json TEXT,
    FOREIGN KEY(event_id) REFERENCES engrev_laj_recorte_learning_events(id)
);
```

### 3.3 Tabela: `engrev_laj_recorte_calibrator_versions`

Cada calibracao vira uma versao auditavel.

```sql
CREATE TABLE engrev_laj_recorte_calibrator_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    classe TEXT NOT NULL,
    version_name TEXT NOT NULL,
    training_set_hash TEXT NOT NULL,
    sample_count INTEGER NOT NULL,
    params_json TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'candidate'
);
```

`status`:

- `candidate`
- `active`
- `rejected`
- `rollback`

---

## 4. O Que Aprender Primeiro

Nao comecar com rede neural. Comecar com calibrador deterministico.

### 4.1 Margens por lado

Para cada recorte aprovado, medir:

- quanto o humano expandiu ou contraiu esquerda/direita/cima/baixo;
- se o motor cortou marco;
- se o motor capturou vizinho;
- se o humano precisou incluir cotas externas;
- se a laje e de borda, miolo, deformada, estreita ou alongada.

Saida aprendida:

```json
{
  "bbox_margin": {
    "left_p50": 12.0,
    "right_p50": 14.0,
    "bottom_p50": 10.0,
    "top_p50": 18.0,
    "left_p90": 40.0,
    "right_p90": 45.0
  }
}
```

### 4.2 Fechamento de marco

Medir se o recorte contem linhas suficientes para fechar o contorno fisico:

- evidencias de borda esquerda;
- borda direita;
- borda inferior;
- borda superior;
- segmentos de `Paineis` que cercam a label;
- contorno inferido pelo `motor_reverso_laj`.

Saida aprendida:

```json
{
  "closure_thresholds": {
    "min_side_evidence": 3,
    "min_panel_segments": 8,
    "max_open_side_count_for_high_confidence": 0
  }
}
```

### 4.3 Anti-vizinho

Aprender quando a expansao pegou outra laje:

- outro label `Lxxx` dentro do bbox;
- texto/cota pertencente a outra laje;
- bbox muito maior que o padrao dos aprovados;
- relacao largura/altura fora do cluster dos aprovados;
- excesso de linhas/cotas em comparacao ao aprovado.

Saida aprendida:

```json
{
  "neighbor_guard": {
    "label_clearance_cm": 5.0,
    "max_bbox_width_p95": 900.0,
    "max_bbox_height_p95": 700.0,
    "entity_count_high_outlier_factor": 1.6
  }
}
```

### 4.4 Confianca sincera

Confianca alta so quando:

- marco fecha;
- label propria existe;
- nenhum label vizinho foi capturado;
- cotas principais existem;
- bbox esta dentro do padrao aprendido;
- extracao N2 consegue reconhecer contorno e linhas internas.

Regra inicial:

- `>=95`: pode ser candidato a autoaprovado LAJ;
- `80-94`: motor utilizavel, mas requer revisao;
- `<80`: suspeito, priorizar revisao.

---

## 5. Pipeline Proposto

### Fase R-LJ-0 - Instrumentacao sem alterar comportamento

Entrega:

- criar tabelas de eventos/features/versoes;
- registrar hash dos DXFs;
- registrar bbox e contagens do motor;
- registrar evento quando humano salva/aprova;
- gerar relatorio por pavimento.

Criterio:

- app continua funcionando igual;
- nenhum recorte aprovado e sobrescrito;
- relatorio mostra motor vs aprovado quando existir par.

### Fase R-LJ-1 - Auditor de recorte LAJ

Entrega:

- funcao `audit_laj_recorte(recorte_path, elemento_id)`;
- retorna scores:
  - `closure_score`;
  - `neighbor_capture_score`;
  - `dimension_score`;
  - `extractability_score`;
  - `confidence_suggested`.

Criterio:

- auditor reprova os casos que o humano nao aprovou no 13_PAV;
- auditor nao reprova os aprovados sem causa clara;
- relatorio visual mostra motivo por item.

### Fase R-LJ-2 - Calibrador candidato

Entrega:

- script `scripts/engrev_laj_recorte_learning/train_engrev_laj_recorte_calibrator.py`;
- le somente recortes `aprovado`;
- calcula parametros robustos por percentil, nao por media simples;
- salva versao `candidate` em `engrev_laj_recorte_calibrator_versions`.

Criterio:

- nao altera motor;
- gera diff: parametros atuais vs parametros aprendidos;
- mostra impacto previsto nos pendentes.

### Fase R-LJ-3 - Simulacao em shadow mode

Entrega:

- motor atual gera recorte real;
- calibrador gera bbox sugerido em paralelo;
- ambos sao renderizados em contact sheet:
  - atual;
  - sugerido;
  - aprovado humano, quando existir.

Criterio:

- humano consegue comparar;
- nenhuma publicacao automatica;
- metricas mostram ganho sem regressao.

### Fase R-LJ-4 - Aplicacao controlada

Entrega:

- feature flag `RECORTE_LEARNING_ENABLED=true`;
- calibrador ativo apenas para LAJ;
- se auditor detectar risco, reduz confianca e nao autoaprova.

Criterio:

- regressao verde em todos os aprovados da TREINO_1;
- nenhum aprovado humano e sobrescrito;
- todos os pendentes continuam revisaveis.

### Fase R-LJ-5 - Aprendizagem continua

Entrega:

- a cada `human_approved`, criar novo evento e features;
- se acumular N novos aprovados, treinar nova versao candidata;
- nova versao so vira `active` apos regressao.

Criterio:

- melhoria incremental rastreavel;
- rollback simples para a versao anterior;
- relatorio indica qual versao gerou cada recorte.

---

## 6. Arquivos Sugeridos

```text
scripts/engrev_laj_recorte_learning/
  audit_engrev_laj_recorte.py
  extract_engrev_laj_recorte_features.py
  train_engrev_laj_recorte_calibrator.py
  simulate_engrev_laj_recorte_calibrator.py
  publish_engrev_laj_recorte_calibrator.py

src/core/
  engrev_laj_recorte_calibrator.py
  engrev_laj_recorte_learning_store.py

docs/
  MASTERPLAN-RECORTE-LAJE-APRENDIZAGEM.md
```

Integracao minima no app:

- `diagnostic_reverse_hub.py` registra eventos de salvar/aprovar;
- `RecorteMotor` recebe calibrador opcional;
- se calibrador desligado, comportamento atual permanece identico.

---

## 7. Quality Gates do Aprendizado

### RG0 - Sem perda de integridade

- DB backup antes de migracao;
- schema novo e aditivo;
- app abre recortes antigos;
- aprovados humanos preservados.

### RG1 - Reprodutibilidade

- todo recorte tem:
  - path;
  - hash;
  - versao do motor;
  - versao do calibrador;
  - timestamp.

### RG2 - Regressao contra aprovados

Para cada recorte `aprovado`:

- calibrador nao pode sugerir bbox pior;
- auditor deve reconhecer como alta qualidade;
- N2 precisa extrair contorno e linhas.

### RG3 - Sinceridade

Um recorte ruim nao pode receber confianca alta.

Regras:

- se marco nao fecha, confianca maxima 79;
- se captura label vizinho, confianca maxima 69;
- se N2 nao extrai contorno, confianca maxima 74;
- se bbox e outlier extremo, confianca maxima 84.

### RG4 - Publicacao controlada

Versao candidata so vira ativa se:

- regressao verde;
- contact sheet revisada;
- nenhum aprovado humano piorou;
- changelog do calibrador gerado.

---

## 8. Como Uma Aprovacao Humana Melhora o Sistema

Fluxo desejado:

1. Motor gera `LAJ_Lxxx_motor_*.dxf`.
2. Auditor calcula features e confianca.
3. Humano edita e salva, se necessario.
4. Humano aprova.
5. Sistema registra `human_approved`.
6. Sistema compara motor vs aprovado.
7. Sistema extrai deltas e features.
8. Quando houver volume suficiente, treina versao candidata.
9. Candidate roda em shadow mode.
10. Se passar regressao, vira active.

Nada e aplicado no motor no momento da aprovacao. A aprovacao alimenta o dataset; a melhoria
entra apenas por versao candidata validada.

---

## 9. Metricas Minimas por Pavimento

Relatorio por pavimento:

```text
Pavimento: 13_PAV
Classe: LAJ

total_recortes: 31
aprovados_humano: 20
motor_pendente: 11
auto_aprovados: 0

motor_high_conf_wrong: 0
motor_cut_frame: N
motor_neighbor_capture: N
avg_human_delta_left: ...
avg_human_delta_right: ...
closure_pass_rate: ...
extractability_pass_rate: ...
```

Objetivo inicial:

- reduzir `motor_high_conf_wrong` para zero;
- aumentar `closure_pass_rate`;
- manter `neighbor_capture` baixo;
- nunca aumentar autoaprovacao sem qualidade real.

---

## 10. Riscos e Mitigacoes

| Risco | Mitigacao |
|---|---|
| Aprender com recorte ruim | Apenas `aprovado` humano entra no treino |
| Overfit na Obra_TREINO_1 | Parametros por percentil + regressao em multiplos pavimentos |
| Caixa-preta sem explicacao | Comecar com calibrador deterministico e features legiveis |
| Sobrescrever aprovado humano | Queries preservam `status='aprovado'`; paths novos para motor |
| App aberto sobrescrever com codigo antigo | registrar `motor_version` e `calibrator_version`; reinicio exigido apos atualizacao |
| Confianca voltar a mentir | RG3 limita teto de confianca por falha objetiva |

---

## 11. Definition of Done da Fase Inicial

Fase inicial pronta quando:

- tabelas novas existem e sao aditivas;
- eventos de salvar/aprovar sao registrados;
- features de recorte LAJ sao extraidas;
- relatorio do 13_PAV mostra motor vs aprovado;
- calibrador ainda em shadow mode;
- motor atual continua funcionando sem flag de aprendizagem;
- nenhum recorte aprovado foi alterado.

So depois disso iniciar aplicacao controlada.

---

## 12. Decisao Arquitetural Recomendada

Implementar primeiro:

1. versionamento de eventos;
2. extracao de features;
3. auditor deterministico;
4. relatorio por pavimento.

Nao implementar ainda:

- rede neural;
- autoajuste imediato no clique de aprovar;
- autoaprovacao baseada em ML;
- alteracao destrutiva dos recortes aprovados.

Esse caminho cria aprendizagem real, auditavel e reversivel, mantendo a integridade atual.
