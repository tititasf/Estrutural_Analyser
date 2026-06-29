# Governança dos artefatos N3/N4

## Regra obrigatória

Um N3 ou N4 marcado como **Validado humano** no Comparison Engine é
imutável. Nenhum motor pode publicar por cima desse artefato enquanto a
validação permanecer marcada.

Ao validar:

1. A política é registrada em `artifact_validation_policies`.
2. Cada DXF oficial do item recebe snapshot por SHA-256.
3. O DXF oficial e o snapshot ficam somente leitura.
4. O estado é registrado em `protected_artifacts`.

Ao desmarcar:

1. A política deixa de bloquear publicação.
2. Os DXFs oficiais voltam a ser graváveis.
3. Os snapshots e o histórico permanecem para auditoria.

## Execuções de motores

Os motores compartilhados por N3/N4 são identificados por:

- `ROBOT_PL_N3_N4`
- `ROBOT_LV_N3_N4`
- `ROBOT_FV_N3_N4`
- `ROBOT_LJ_N3_N4`

A versão é o hash do manifesto dos arquivos-fonte do motor. Cada execução é
registrada em `motor_runs`, incluindo versão, classe, item, escopo, hashes,
efeito e resultado dos testes.

Quando o destino está protegido, a nova geração é salva em:

```text
Fase-6_Execucao_CAD/.motor_versions/candidates/
```

O DXF oficial não é alterado.

## Testes headless

Defina a variável abaixo antes de executar um motor:

```powershell
$env:CAD_MOTOR_HEADLESS='1'
```

Nesse modo nenhuma geração é publicada, mesmo quando o item não está
validado. O resultado fica como candidato versionado com status
`candidate_pending_test`. Após a comparação, o teste deve registrar suas
métricas com `record_motor_test_result`.

## Consulta do histórico

```powershell
python scripts/motor_version_report.py --limit 50
python scripts/motor_version_report.py --motor ROBOT_FV_N3_N4 --json
```
