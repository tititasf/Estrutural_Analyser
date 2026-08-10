# LV — manual granular de interpretação, validação e evolução

## 1. Contrato: quatro interpretações, não uma lateral genérica

LV é a matriz fechada **lado A/B × comportamento PARA/PASSA**. Cada célula tem
seleção, segmentos, ajustes, painéis e prova próprios. O corte é contexto comum,
mas nunca autorização para espelhar dado. `BeamTracer` fornece topologia bruta;
`src/core/beam_interpreters/lateral_viga.py` é dono da semântica; o contrato N3 é
`src/core/lv_generation_contract.py`.

| Contrato | Significado | Saída exclusiva | Invariante |
|---|---|---|---|
| A_PARA | lado A termina no encontro | slots A/PARA | não recebe dados B/PASSA |
| B_PARA | lado B termina no encontro | slots B/PARA | não recebe dados A/PASSA |
| A_PASSA | lado A continua pelo encontro | slots A/PASSA | não recebe dados B/PARA |
| B_PASSA | lado B continua pelo encontro | slots B/PASSA | não recebe dados A/PARA |

FV não pode fornecer dimensão, painel, apoio nem fallback semântico a LV. A presença
de `_sa_meta.fv_dimension_fallback` é FAIL de isolamento, não conveniência.

## 2. Ficha e matriz de campos N1

A ficha `laterais_viga/` deve separar explicitamente lista PARA/PASSA e face A/B.
Ler SVG local antes de contexto/corte: o local decide segmento e extremidade; o
corte só contextualiza altura e sequência. Conferir todos os quatro contratos mesmo
quando um esteja N/A; ausência justificada não é célula copiada.

| Família | N1/contrato | O que provar no SVG e DB | Falha que o número não vê |
|---|---|---|---|
| identidade | `fields.nome`, `fields.dimensao`, versão | viga certa e seção correta | campo de viga vizinha |
| lado A | `viga_a_seg_N_*`, links A | contorno, ordem, largura/altura e apoio A | A desenhado na posição B |
| lado B | `viga_b_seg_N_*`, links B | idem para B | espelhamento silencioso |
| comportamento | `lv_generation_contracts.{Para,Passa}.{A,B}` | `contract_id`, `side`, `behavior`, readiness | PARA reaproveitado como PASSA |
| origem | `structural_segments.*.source_key/source_slot` | cada painel aponta ao segmento N1 correto | origem agregada sem painel |
| exceção | pilar, laje, pontalete, grade, endpoint event | evento pertence à célula certa | evento aplicado ao lado oposto |

O probe `four_contracts_and_support` verifica contrato, isolamento, source key/slot,
readiness e apoio. É a primeira consulta para item persistido. Não use uma dimensão
de corte ou de FV para “consertar” uma lateral.

## 3. Diagnóstico, score N1×N2 e visual CLI

`diagnostico_lv_n1_n2.py` é principalmente comparador de dimensões/segmentos por
lado. Ele não prova comportamento PARA/PASSA, ajuste, grade, abertura, pontalete ou
espelhamento; estes entram obrigatoriamente na matriz S5 e no SVG. Pontuar por célula:

1. identificar a parte N2 equivalente (A/B, PARA/PASSA, corte quando aplicável);
2. comparar nome, lado, comportamento, quantidade/ordem, altura, comprimento,
   ajuste inicial/final, apoio e exceções;
3. registrar match/mismatch/N/A e score; N/A só com fonte;
4. sem divergência não triada nos campos extraíveis/algorítmicos (0,05), liberar N3.

```powershell
# DB/probe: segundos, sem headless
python scripts/arete/qa_evidence_auditor.py review --project-id <ID> --classe LV --include-sealed
python scripts/arete/qa_profile_probe.py --classe LV --probe four_contracts_and_support `
  --item V328 --project-id <ID>

# mudança de interpretação somente aqui
python scripts/arete/headless_sa_analise.py --obra <OBRA> --pav <PAV> `
  --secao laterais_viga --item V328 --wait
python scripts/arete/g2v_harness.py --classe LV --pav <PAV> --par n1xn2 `
  --item V328 --backend cli --lista-lv passa
```

N1-V/G4-V (interpretação N1×N2) e G5-V (paridade final N3×N4) são SVG-only:
`g2v_harness.py --backend cli`, lido pelo modelo/agente CLI, sem API visual.

### 3.0 Visão canónica (obrigatória — senão é ruído)

Documento mestre: [`docs/QA-VISAO-EVIDENCIA-CANONICA.md`](../../QA-VISAO-EVIDENCIA-CANONICA.md).

| Etapa vision | Evidência N2 | Evidência N3/N4 |
|--------------|--------------|-----------------|
| G2-V N2×N4 | DXF `recorte_path` → **SVG full layers** (como CE) | `VIEW_A`/`VIEW_B`/`CORTE` → SVG |
| N1-V / G4-V | recorte se existir + SVG ficha | SVG N1 da ficha |
| G5-V N3×N4 | — | SVGs N3 e N4 da ficha granular |

- **N2 no CE** = recorte full layers — autoridade visual humana.
- **Agente** julga em **PNG** full-render; **SVG** no HTML persistido/portal.
- Headless **sem** `--persist-db` = imagem dinâmica; **com** persist = SVG no HTML.
- Plot LINE-only = audit interno; **não** se chama “N2” sozinho.
- Botão **Passa** no CE = Para/Passa estrutural; **não** é PASS visual.
- Mecanismo: `g2v_harness.py --backend cli` + inventário + pack PNG vision.

### 3.1 Inventário mínimo (obrigatório para PASS visual N2×N4)

**Proibido** aprovar LV por contagem de entidades, score de imagem ou “parece
igual”. Antes do veredito visual:

0. SVG canónico N2 (recorte CE) e N4 (VIEW_*) — §3.0.
1. Extrair inventário N2 face (e B/corte se no par): cada `LINE` Painéis+SARR
   com coords relativas, cada cota, cada texto de identidade.
2. Match N2→N4 com status `MATCH|NEAR|MISSING_N4|EXTRA_N4|N2_VOID_JUNK…`.
3. Anexar path no veredito (`inventario.path`) e marcar checklist
   `inventario_minimo_extraido`, `linhas_estruturais_rastreadas`,
   `cotas_valores_rastreados`, `textos_identidade_rastreados`,
   `sem_aprovacao_por_contagem`.

**Contrato de cotas:** N2 LV usa `TEXT` numérico (muitas vezes layer `Painéis`);
N4 usa `DIMENSION` dimstyle `PAINEL`. Match por **valor + posição**, não por
tipo de entidade.

Protocolo: [`docs/QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md`](../../QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md).  
Exemplo ouro V301: `scripts/arete/relatorios/g2v/v301_arete_review/` (SVG).

## 4. Casos difíceis e roteamento de correção

| Sintoma | Hipótese/refutação | Dono do fix | Não fazer |
|---|---|---|---|
| A e B iguais sem origem equivalente | verificar `source_slot`, geometria local e eventos | contrato lateral do lado afetado | copiar A→B |
| PARA e PASSA iguais | só aceitar se ajustes/eventos também coincidem | contrato do comportamento | assumir igualdade pela dimensão |
| comprimento certo, painel errado | conferir soma de painéis, ordem e offsets | contrato/gerador LV | fechar por bbox total |
| abertura em lado errado | provar contato do pilar/laje e extremidade | lateral + relação contextual | espelhar exceção |
| corte correto, faces erradas | corte é contexto, não fonte de face | interpretador lateral | usar corte como preenchimento |
| quatro contratos falham a partir do eixo | provar defeito bruto multi-contrato | `BeamTracer` | corrigir cada slot com hack |

## 5. N3, variantes e não regressão

Gerar variante individual (`A_PARA`, `B_PARA`, `A_PASSA`, `B_PASSA`) sem headless;
depois `qa_n3_smoke.py` e `ficha_motor_item.py`. O smoke prova identidade/texto/camadas
e contrato; a leitura SVG prova painel, ajuste, abertura, grade e posição. G5
(paridade final N3×N4) não pode ser “por construção”, e match por herança N2/N4 é
`vazamento_gabarito`.

Validação congela topologia apenas na célula correspondente: validar A_PARA não
congela B_PARA/A_PASSA/B_PASSA. Campos e vínculos ainda não validados continuam
recalculáveis. Depois de tocar `lateral_viga.py`/contrato LV: teste da célula, teste
negativo das três células, microciclo e diagnóstico LV. Se tocar `BeamTracer`, aplicar
regressão das quatro classes e registrar em `HISTORICO/LV.md`.

## 6. Autoevolução e candidato RAG LV

Toda descoberta BLUE/laranja registra lado, comportamento, `source_key/source_slot`,
ajustes, evento e contraexemplo A/B×PARA/PASSA. Atualizar o manual somente depois de
prova e teste negativo das três células vizinhas. O HTML/SVG aprovado vira candidato
RAG multimodal por contrato, nunca por “viga lateral genérica”. Ao fechar os laranjas
LV do pavimento, pedir validação humana do pacote para futura curadoria RAG LV.

## 7. Quadro QA read-only por pavimento

`scripts/arete/qa_lv_quadro_pavimento.py` projeta somente evidência já persistida
no DB e artefatos canônicos em `QUADRO-LV-PAVIMENTO.{html,json,csv,md}`. Ele nunca
executa headless, gate, gerador ou escrita no DB; portanto não cria N1/N3, não altera
N2/N4/DXF/JSON Fase-4 e não concede selos.

O HTML possui duas tabelas independentes, **PARA** e **PASSA**; cada uma tem uma
linha por viga/comportamento e conserva seus dois contratos explícitos (`A_PARA` /
`B_PARA` ou `A_PASSA` / `B_PASSA`) dentro das etapas N1/SA e N3. Para cada uma o quadro mostra
`contract_id`, readiness, segmentos/painéis, dimensão, apoio inicial/final, ajustes,
eventos de extremidade/recortes, `source_key/source_slot`, `behavior_isolated` e o
veto `fv_dimension_fallback=false`. O corte aparece somente como contexto comum; não
duplica nem espelha face ou comportamento.

As colunas seguem: etapa/próximo passo → N2 → N4 → N1/SA → N1-V CLI → N1×N2 → N3
→ N3×N4 → N3×N2 → S8/RAG HTML pós-QA. A coluna S8 lê exclusivamente
`rag_artifact_validations`: só mostra ingestão quando o registro é HTML, ativo, não
revogado e tem `validation_origin` QA. A geração de uma ficha HTML nunca promove o
item automaticamente para RAG. G2 e G2-V ficam dentro de N4; N4 admite exclusivamente selo azul
humano e laranja QA. N1/N3 exibem quatro selos, sempre como estado lido e nunca
inferido. Evidência visual é SVG de relatório do `g2v_harness.py --backend cli`;
ausência de veredito fica “não registrado”, sem virar aprovação ou FAIL.

O quadro também pode ler, sem alterar nada, o último pacote completo de
`html_fichas/..._laterais_viga_*` e os DXFs `LV_preview_*.dxf` N4. Esses artefatos
recebem o símbolo de realização (✓) somente como evidência de execução/materialização;
eles não viram selo e não substituem contrato persistido. Em especial, um pacote
headless sem `--persist-db` é snapshot para revisão humana: deve ser exibido como tal,
sem alegar que atualizou o DB. O DXF N4 existente é referência do fluxo N2/PASSA e
nunca preenche ou valida a linha PARA.

```powershell
D:\Agente-cad-PYSIDE\.venv\Scripts\python.exe -X utf8 scripts/arete/qa_lv_quadro_pavimento.py `
  --project-id dd238e47-1dc6-4f63-a760-4e7ce19a7386 --obra Obra_TREINO_1 --pav 13_PAV `
  --output-dir scripts/arete/relatorios/qa_quadro_lv/Obra_TREINO_1/13_PAV/<timestamp>
```
