# Manuais granulares por classe — Structural Analyzer

Estes manuais são a camada específica de `SA-ANALISE-PROGRESSO-POR-ITEM.md`.
O processo geral, os gates e a regra anti-vazamento continuam únicos; cada manual
define como interpretar, evidenciar, diagnosticar e evoluir uma classe sem copiar
semântica de outra.

| Classe | Manual | Objeto de verdade N1 | Maior risco |
|---|---|---|---|
| PIL | [PIL.md](PIL.md) | pilar, contorno e faces A–H | confundir PARA, PASSA, chegada e montagem |
| LAJ | [LAJ.md](LAJ.md) | contorno de laje, apoios e exceções | panelizar antes de provar contorno/apoio |
| FV | [FV.md](FV.md) | segmentos físicos de fundo | unir/perder segmentos ou confundir apoio local/global |
| LV | [LV.md](LV.md) | A/B × PARA/PASSA | espelhar lado/comportamento ou usar fallback FV |

## Regras comuns, sem exceção

1. N1 vem apenas do DXF estrutural e das relações N1 autorizadas. N2/N4 servem
   para comparar e diagnosticar; nunca preenchem N1/N3.
2. Campo persistido: primeiro `qa_evidence_auditor review`,
   `qa_n1_field_probe.py` ou `qa_profile_probe.py`. Headless não é consulta.
3. Mudança de interpretação: somente
   `headless_sa_analise.py --secao <classe> --item <item> --wait`; um microciclo
   é read-only por padrão. Com `--persist-db`, o upsert permanece granular:
   PIL/FV/LV reservam `headless_sa_beams` por compartilharem `beams.data_json`,
   LAJ continua independente, e o SQLite é exclusivo apenas no
   `headless_sa_db_commit` curto.
4. Visão dual-mode (`docs/QA-VISAO-EVIDENCIA-CANONICA.md`): conteúdo = DXF full
   layers (CE). **Agente CLI** lê **PNG** (vision). **SVG** no HTML com
   `--persist-db` / app / portal web. Headless sem persist = só imagem (dinâmico).
   G2-V / N1-V / G5-V via `g2v_harness.py --backend cli`. Plot LINE-only ≠ N2.
   Validação rasa = ruído + inventário mínimo.
5. Antes de N3, S5 registra matriz N1×N2, score, match/mismatch/N/A e causa
   provável. Campos extraíveis/algorítmicos obedecem tolerância de **0,05**.
6. Cada tentativa e hipótese rejeitada entra em
   `docs/SA-ANALISE/HISTORICO/<CLASSE>.md` e em triagem schema v2. Estes manuais
   não substituem o diário append-only.

## Como escolher a rota rápida

```text
campo/ligação já no DB?     → review/probe, sem headless
contrato/DXF N3 em dúvida?  → gerador individual + qa_n3_smoke + ficha_motor_item
geometria N1 em dúvida?     → headless granular + mesmo probe antes/depois
diferença de desenho?       → SVGs-fonte + g2v_harness --backend cli
falha em mais de uma classe?→ provar BeamTracer/shared seam e regressão completa
```

Use o manual da classe antes de editar interpretador, contrato, ficha ou gerador.
Ele declara o dono do campo, os contraexemplos e a regressão mínima.

## Autoevolução e RAG granular

O agente atualiza este índice, o manual da classe e seu diário quando descobre regra,
contraexemplo, caso BLUE, lacuna de campo, caminho rápido ou regressão. Ele pode
programar ajuste universal dentro do escopo provado e testá-lo; não pode promover esse
aprendizado a RAG sozinho. Cada item validado produz candidato multimodal composto por
HTML, SVGs, manifesto, hashes, vínculo/coordenação, matriz N1×N2, score e decisão.

Ao completar os selos laranja de uma classe em um pavimento, consolidar a evidência e
solicitar ao humano validação para curadoria RAG daquela classe/pavimento. Ao completar
a obra, consolidar a compreensão transversal das quatro classes e pedir validação humana
da obra antes de propor conhecimento RAG geral.
