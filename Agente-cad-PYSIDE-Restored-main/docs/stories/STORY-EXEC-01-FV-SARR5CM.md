# STORY-EXEC-01 — FV 13_PAV: corrigir causa `SARR_5CM` (6 itens FAIL)

**Pré-requisito:** leia `docs/HANDOFF-PRODUCAO-EXECUTOR.md` primeiro. Escopo = SÓ esta story.

## Contexto (tudo que você precisa saber)

FV do 13_PAV estava 26/26 PASS (golden selado 25/06). A rodada `20260629_120812`
REABRIU 6 itens com **uma única causa**: layer `SARR_5CM`, entidades `LINE` que o N4
emite e o recorte de referência NÃO tem (`ref=0` vs `n4=2` a `12`).

Itens: **V310, V327, V331, VF202, VF203, VF301** (os outros 20 passam).
Relatório: `scripts/arete/relatorios/20260629_120812/RELATORIO.md`.

## Leia antes (só isto)

1. `scripts/arete/relatorios/20260629_120812/RELATORIO.md` — os 6 FAILs
2. `scripts/arete/relatorios/triagem_erros/` — se houver JSONL de FV, ler ANTES de
   formular hipótese (regra do procedimento geral §4.1)
3. `docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md` §0 e §5 — o ciclo corrigir→reverificar→fechar

## Arquivos que PODE tocar (se a causa comprovada estiver neles)

- `scripts/gerar_fv_dxf_stog.py` (gerador FV)
- `scripts/motor_reverso_fv.py` (extrator FV)
- `scripts/arete/` (harness, comparador)

## PROIBIDO nesta story

- Tocar em qualquer outra classe (PIL/LV/LAJ), outro pavimento, UI, DB (escrita).
- Fix por item — a causa é UMA (`SARR_5CM`); UM fix deve resolver os 6 itens.
- Deletar/editar recortes ou fichas para "fazer passar".

## Passos

1. Gerar o N4 de UM item FAIL (ex.: V310) e renderizar PNG lado a lado com o recorte
   (o harness já faz: `arete_runner.py` ou `paridade_visual.py`). **LER a imagem.**
2. Responder com evidência: de ONDE vêm as linhas `SARR_5CM` extras no N4?
   Hipóteses a verificar (não conclusões): (a) gerador emite sarrafo por fórmula em caso
   onde o STOG humano não emite; (b) mudança recente no gerador/motor entre 25/06 e 29/06
   (ver `git log -- scripts/gerar_fv_dxf_stog.py scripts/motor_reverso_fv.py`);
   (c) comparador mudou de régua. A resposta certa depende da evidência, não do palpite.
3. Se a causa for legítima divergência (conteúdo que não é do elemento): NÃO decidir —
   parar e perguntar ao dono com PNGs + contagens.
4. Fix por fórmula geral no arquivo responsável.
5. Rerodar FV completo: `arete_runner.py --classe FV` (13_PAV) → meta 26/26.
6. **Regressão obrigatória:** rerodar PIL/LV/LAJ do 13_PAV (golden) — nenhum score regride.
7. Selar golden FV, atualizar JSONL de triagem se existir entrada, rodar
   `python scripts/arete/gerar_status.py`.

## PASS da story

- FV 13_PAV = 26/26 PASS no relatório novo.
- Regressão 13_PAV verde (PIL 35, LV 32, LAJ 31 continuam PASS).
- `docs/STATUS.md` regenerado sem o alerta de regressão FV.
- Relatório final: causa nomeada + arquivo/linhas do fix + comandos que provam.
