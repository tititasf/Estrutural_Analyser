# MASTERPLAN ARETE - PILAR

## Status
Versao: 0.2 - arquitetura N1 isolada registrada em 2026-07-05.

Este documento nao e verdade absoluta da classe PIL. Ele organiza o que ja existe para
execucao correta dos ciclos CROP, A, B e C. Qualquer regra de campo so vira conhecimento
global depois de validacao humana e, quando aplicavel, consolidacao em mais de uma obra.

## Fontes harmonizadas
- `docs/SEMANTICA-PILAR-NOVA.md`
- `GOLDEN/Obra_TREINO_1/*/PIL`
- `scripts/motor_reverso_pil.py`
- `scripts/motor_reverso_pil_zones.py`
- `scripts/gerar_dxf_pilares.py`
- `scripts/gerar_scr_pilares.py`
- `scripts/run_pil_batch.py`
- `scripts/fidelidade_pilares.py`
- `scripts/arete/forma_canonica_pil.py`
- `scripts/arete/partes_pil.py`
- `scripts/arete/propagar_subtipo_pil.py`
- `tests/test_ce_n4_pil_cima.py`
- `tests/test_ce_n4_pil_cima_universal.py`

## Contrato anti-contaminacao
CLI, loopers, scripts e agentes podem:
- gerar candidatos;
- produzir DXF/PNG/JSON;
- medir score;
- explicar divergencias;
- registrar evento tecnico em quarentena.

CLI, loopers, scripts e agentes nao podem:
- marcar T1/T2;
- indexar no RAG global como professor;
- tombstonar/desvalidar como humano;
- copiar N2/N4 para gerar N3;
- tratar score sintetico como aprovacao humana.

Promocao efetiva exige `validation_origin="human_ui"`.

## Ciclo CROP - aprender recorte PIL
Professor: recorte aprovado pelo humano.

Valida apenas:
- janela/bbox/poligono contem o pilar inteiro;
- recorte nao mistura pilar vizinho;
- classe PIL esta correta;
- contexto de pavimento/layer esta correto.

Treina:
- detector de recorte por classe;
- margem por face;
- layers relevantes para CIMA, GRADES e ABCD;
- falsos positivos e padroes por pavimento.

Nao valida:
- F5/N2;
- N4;
- equivalencia visual do robo.

Persistencia:
- `crop_learning_events`;
- exemplos visuais locais;
- status CROP-T1 na Curadoria.

## Ciclo A - N2 para N4
Professor/juiz: STOG humano + F5/N2 validado.

Objetivo:
- extrair corretamente campos PIL do desenho humano;
- gerar N4 equivalente ao STOG por partes CIMA, GRADES e ABCD.

Motores envolvidos:
- `motor_reverso_pil.py`;
- `motor_reverso_pil_zones.py`;
- `gerar_dxf_pilares.py`;
- `gerar_scr_pilares.py`.

Gate:
- campos F5 conferidos por humano;
- N4 passa no Comparison Engine;
- testes CIMA continuam verdes;
- divergencias viram `training_events` com proveniencia.

Nao fazer:
- usar N4 para corrigir N2 automaticamente;
- promover ficha extraida sem clique humano;
- usar N4 como entrada de N1/N3.

## Ciclo B - N2 com N1
Professor externo: N2/F5 validado.

Objetivo:
- treinar o Structural Analyzer para interpretar PIL no estrutural limpo;
- aproximar F7/N1 de F5/N2 por campo;
- derivar equivalencia de vocabulario N1 <-> N2.

### Contrato arquitetural N1 de PIL (ativo desde 2026-07-05)

**Persistência N1 granular:** geometria, nome, dimensão, níveis, relações com
lajes/vigas e demais campos mantêm validações independentes. A reanálise preserva
somente campo/slot/vínculo validado e substitui o restante. Validar `pilar_segs`
também preserva a geometria raiz `points`. Ver `PERSISTENCIA-HEADLESS-SA.md`.

As relações entre pilar e viga são interpretadas por dois contratos independentes e
mutuamente exclusivos:

- `PilarComVigaParaInterpreter` escreve somente em `viga_que_para` quando uma
  extremidade do eixo termina no volume do pilar;
- `PilarComVigaPassaInterpreter` escreve somente em `viga_que_passa` quando o eixo
  continua além das duas faces do pilar.

`BeamTracer` fornece bbox, eixo, orientação e continuidade bruta; não decide o slot
PIL final. Toda evolução deve testar também a negação do contrato oposto para impedir
dupla classificação. A fonte de verdade compartilhada com FV e LV é
`ARQUITETURA-INTERPRETADORES-VIGA-N1-ISOLADOS.md`.

Campos e partes criticas:
- nome do pilar;
- dimensoes;
- face A/B longa e C/D curta;
- CIMA;
- GRADES;
- ABCD;
- posicoes de laje;
- alturas e offsets.

Gate:
- F7/N1 converge para F5/N2 sem sobrescrever o gabarito;
- `viga_que_para` e `viga_que_passa` permanecem exclusivos por relação geométrica;
- divergencias recebem aprovacao, rejeicao, N/A ou nota humana;
- regra global so nasce depois de evidencia T1/T2.

Nao fazer:
- usar N2 como input de geracao N3;
- transformar nota humana isolada em regra global;
- treinar com T0.

## Ciclo C - N1 para N3
Juiz externo: N4 validado.

Objetivo:
- N1 gera N3 sozinho;
- robos de Pilar recebem dados vindos do N1;
- N3 se aproxima de N4 sem vazamento de gabarito.

Gate:
- N3 ~= N4 no Comparison Engine;
- score visual/semantico atinge gate da classe;
- campos divergentes viram eventos auditaveis;
- regressao garante que N3 nao recebeu campos de N2/N4.

Nao fazer:
- copiar F5/N2 para preencher robo N3;
- considerar score sintetico como validacao humana;
- indexar N3 nao validado no RAG global.

## Riscos conhecidos
- Inversao A/B/C/D ainda precisa auditoria visual por item.
- Lajes e interferencias podem estar incompletas em alguns casos.
- Alturas, offsets e grades precisam de consenso por obra antes de virar regra.
- Artefatos de looper em `scripts/arete/tmp` sao evidencia tecnica, nao aprovacao.

## Como usar este plano
1. Rode ou analise um looper PIL em escopo pequeno.
2. Compare artefatos no Comparison Engine.
3. Use notas humanas para marcar duvidas e atencoes.
4. Valide pela UI quando estiver correto.
5. So entao o evento pode virar T1 e alimentar RAG global.
6. Repita em outra obra antes de promover regra para T2/default.
