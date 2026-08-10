---
task: resolve-scope
agent: aegis
inputs: [project_id_or_obra_pav, classe, item, nivel, parte, variante]
outputs: [scope.json]
mutates: false
scripts:
  - scripts/arete/qa_evidence_auditor.py
---

# Resolver escopo

1. Preferir `project_id`; falhar se obra/pavimento resolver mais de um processamento.
2. Normalizar classe para `PIL|LAJ|FV|LV` e nível para `N1|N3|N4`.
3. Exigir parte e variante quando o motor possuir saídas distintas, como PIL PARA/PASSA.
4. Registrar DB real, Python 3.12, commit/versão disponível e caminhos canônicos.
5. Carregar `data/authority_matrix.json` para a classe (modo de validação).

## Aceite positivo

- `scope.json` inequívoco e nenhuma leitura fora do escopo necessária.

## Aceite negativo

- Não inferir `project_id` do sample do perfil sem `--use-profile-sample`.
- Não continuar com múltiplos processamentos resolvidos por obra/pav.
