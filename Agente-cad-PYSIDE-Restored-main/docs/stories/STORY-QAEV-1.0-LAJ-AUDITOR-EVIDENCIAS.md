# STORY QAEV-1.0 — Auditor de Evidências para LAJ

**Status:** Ready for Review

## Story

Como dono do CAD-ANALYZER, quero um agente CLI que audite cada campo e vínculo de
LAJ com evidência rastreável, elimine vínculos inferidos objetivamente falsos,
gere instruções de correção para o motor e aplique somente decisões de alta
confiança, para consolidar as lajes como ground truth azul sem alucinação.

## Acceptance Criteria

1. Existe CLI read-only que seleciona obra/pavimento/classe/itens e emite uma
   decisão por campo pendente.
2. As decisões possíveis são `CONFIRMAR`, `N/A_CONFIRMADO`, `PENDENTE`,
   `CORRIGIR` e `REVISAR_HUMANO`, sempre com motivo e evidência.
3. Números de dimensões não podem ser aceitos como níveis por coincidência
   numérica; nível vizinho precisa coincidir com fonte semanticamente válida.
4. Visão de corte e apoio de pilar não são confirmados apenas por proximidade;
   geometrias ambíguas geram achado/pergunta.
5. O CLI gera `manifesto.json`, `decisoes.jsonl`, `achados.jsonl`,
   `perguntas.jsonl`, `fix_requests.md` e `resumo.md`, append-only por `run_id`.
6. Existe modo `apply` transacional, limitado ao projeto do snapshot, que rejeita
   snapshot alterado e só aplica decisões explicitamente aprovadas.
7. Remoção automática é permitida apenas para vínculos inferidos, nunca para
   vínculo humano ou selo existente, e fica registrada no relatório.
8. O agente só grava `is_validated` com a opção explícita `--seal-complete`, após
   comprovar os oito campos obrigatórios; sem essa opção, preserva o selo.
9. Testes cobrem nível contaminado, vínculo humano preservado, snapshot obsoleto,
   visão de corte ambígua, apoio distante e geração de fix request.
10. O piloto audita todas as LAJ restantes de 13_PAV e aplica somente o conjunto
    de alta confiança; dúvidas permanecem abertas para o dono.

## Tasks / Subtasks

- [x] Implementar núcleo CLI e contratos append-only. (AC: 1, 2, 5)
- [x] Implementar adaptador LAJ e regras conservadoras dos oito campos. (AC: 3, 4)
- [x] Implementar gerador de achados, perguntas e prompts de correção. (AC: 5)
- [x] Implementar aplicação transacional com snapshot/allowlist. (AC: 6, 7, 8)
- [x] Criar testes unitários e de integração SQLite temporário. (AC: 9)
- [x] Executar piloto LAJ 13_PAV, revisar evidências e aplicar alta confiança. (AC: 10)
- [x] Rodar regressões relevantes e atualizar documentação/relatório. (AC: 1-10)

## Dev Notes

- DB real: `D:/Agente-cad-PYSIDE/project_data.vision`.
- Schema N1 é imutável; reutilizar `validated_fields_json`, `na_fields_json`,
  `validated_link_classes_json`, `na_reasons_json` e `links_json`.
- N2/N4 são somente evidência comparativa; N3 nunca recebe dado N2/N4.
- Backend visual permitido: `g2v_harness.py --backend cli`.
- Fonte arquitetural: `docs/MASTERPLAN-AGENTE-QA-EVIDENCIAS.md`.
- Fonte de proveniência LAJ: `docs/PROVENIENCIA-CAMPOS-LAJ.md`.
- Não editar gerador/motor/tracer sem causa comprovada e autorização específica.

## Testing

```powershell
D:\Agente-cad-PYSIDE\.venv\Scripts\python.exe -m pytest tests\test_qa_evidence_auditor.py -q
D:\Agente-cad-PYSIDE\.venv\Scripts\python.exe -m py_compile scripts\arete\qa_evidence_auditor.py
```

## CodeRabbit Integration

- Tipo primário: arquitetura/integração de dados; complexidade alta.
- Pre-commit: verificar mutação acidental de selos, SQL sem escopo de projeto,
  sobrescrita de vínculo humano, paths de DB e vazamento N2/N4.
- Self-healing: somente CRITICAL, máximo de duas iterações.

## Dev Agent Record

### Agent Model Used

- Codex / GPT-5

### Debug Log References

- `scripts/arete/relatorios/qa_evidencias/20260711_laj_remaining_apply_candidate/`
- `scripts/arete/relatorios/qa_evidencias/20260711_laj_all_postfix_audit/`
- `scripts/arete/relatorios/qa_evidencias/20260711_laj_remaining_apply_candidate/g2v/relatorio.json`
- `pytest`: 10 testes aprovados em 6,97 s.

### Completion Notes

- CLI implementado com auditoria read-only, aplicação transacional, rejeição de
  snapshot obsoleto e rollback integral.
- Piloto L319–L331 aplicado; banco terminou com 31/31 LAJ seladas.
- G2-V CLI dos 13 itens: 13 PASS visual, sem pendência.
- Pós-auditoria preservou seis dúvidas humanas ligadas a L303, L314/L306/L313/L315
  e L318; nenhum conflito selado foi alterado automaticamente.
- Headless direcionado exportou os 13 HTMLs, mas uma rodada falhou após a
  exportação por alteração concorrente do próprio script e duas ficaram na fila
  de outro `--persist-db`. O gate não foi declarado PASS por inferência.

### File List

- `docs/MASTERPLAN-AGENTE-QA-EVIDENCIAS.md`
- `docs/QA-EVIDENCIAS-LAJ-13PAV-20260711.md`
- `docs/stories/STORY-QAEV-1.0-LAJ-AUDITOR-EVIDENCIAS.md`
- `scripts/arete/qa_evidence_auditor.py`
- `tests/test_qa_evidence_auditor.py`
- `tests/test_slab_boundary_linking.py`
- `main.py` (regras gerais de nível, vizinhança, corte e apoio de pilar)

### Change Log

- 2026-07-11: story criada e aprovada para desenvolvimento pelo pedido explícito do dono.
- 2026-07-11: implementação e piloto LAJ concluídos; enviada para revisão com dúvidas conservadoras abertas.

## QA Results

- Gate: **CONCERNS**.
- PASS: 10/10 testes; `py_compile`; 31/31 LAJ azuis; G2-V CLI 13/13 PASS.
- CONCERNS: seis perguntas humanas de nível/vizinhança continuam abertas; o
  headless direcionado não obteve código zero por concorrência externa.
- Integridade: vínculos humanos e conflitos selados foram preservados; rollback
  do lote aplicado permanece disponível no diretório da execução.

### Reavaliação QA — 2026-07-12

- PASS: a regra geral de outlier corrigiu L303 (`845.19 → 852.19`) e L318
  (`822.19 → 852.19`) somente com root+rótulo concordantes e cluster de 12
  lajes corroborando o nível proposto; ambos preservaram o selo azul e rollback.
- PASS: perguntas agora expõem observação, tentativas, hipóteses rejeitadas,
  impasse e a regra geral solicitada. Vizinhas dependentes não duplicam a
  pergunta-raiz.
- PASS: 14 testes aprovados; `py_compile` aprovado.
- CONCERN: L314 continua a única pergunta humana: campo `852.12` e root
  `852.19` pertencem a clusters reais, sem rótulo CAD próprio para desempate;
  L306/L313/L315 dependem dessa resposta.
