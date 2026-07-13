---
task: resolve-scope
agent: aegis
inputs: [project_id_or_obra_pav, classe, item, nivel, parte, variante]
outputs: [scope.json]
mutates: false
---

# Resolver escopo

1. Preferir `project_id`; falhar se obra/pavimento resolver mais de um processamento.
2. Normalizar classe para `PIL|LAJ|FV|LV` e nível para `N1|N3|N4`.
3. Exigir parte e variante quando o motor possuir saídas distintas, como PIL PARA/PASSA.
4. Registrar DB real, Python 3.12, commit/versão disponível e caminhos canônicos.

Aceite: `scope.json` inequívoco e nenhuma leitura fora do escopo necessária.
