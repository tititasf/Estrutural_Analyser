# Arete — Arquitetura de Validação: Problema Atual e Alvo

## Problema atual (2026-06-24)

O Arete runner e o Comparison Engine usam pipelines **desacoplados**:

```
CE (app):
  recorte DXF → motor_reverso (dinâmico) → ficha N2 (RAM) → gerador STOG → N4 em Fase-6/n4/

Arete runner (headless):
  ficha N2 (do DB, estática) → gerador STOG → N4 em TMP_DIR → comparar vs recorte
```

### Consequências do desacoplamento

1. **O Arete não mede o que o usuário vê.** O N4 exibido na CE vem de `Fase-6_Execucao_CAD/n4/`; o N4 que o Arete compara vem de um diretório temporário próprio.
2. **A ficha N2 pode estar desatualizada no DB.** Se o motor reverso for corrigido após a última carga do DB, o Arete continua medindo a versão antiga da ficha.
3. **Melhorias no motor_reverso não se refletem automaticamente no score.** Um ciclo de fix → re-score só funciona se o DB for repopulado manualmente.

---

## Arquitetura alvo

O loop de validação headless deve usar **exatamente o mesmo motor ativado ao selecionar um item no Comparison Engine**:

```
Arete runner (alvo):
  recorte DXF
    → motor_reverso (dinâmico, mesmo código da CE)
    → ficha N2 (gerada na hora, não lida do DB)
    → gerador STOG
    → N4 DXF (gerado na hora)
    → comparar vs recorte DXF
    → score G1 + G2
```

### Por que isso é crítico

- Qualquer melhoria no **motor reverso** (extrator de ficha N2) é **imediatamente** refletida no score na próxima rodada do Arete — sem precisar repopular DB.
- Qualquer melhoria no **gerador STOG** também propaga automaticamente.
- O score do Arete passa a ser **verdade sobre o que o usuário vê na app**, não sobre um snapshot estático.
- O ciclo de evolução fica: ajusta motor → roda Arete → vê melhoria real → commit.

---

## O que precisa ser mudado no Arete runner

### 1. `ficha_adapter.py` — `materializar_item()`

Hoje: lê `campos_json` da tabela `reverse_eng_fichas` do DB.

Alvo: chamar o mesmo motor reverso que a CE usa, passando o path do recorte DXF:

```python
# Hoje (estático):
campos = json.loads(row["campos_json"])

# Alvo (dinâmico):
from scripts.motor_reverso_pil import extrair_ficha_de_recorte
campos = extrair_ficha_de_recorte(recorte_path)
```

Cada classe tem seu motor:

| Classe | Motor dinâmico |
|--------|---------------|
| PIL | `scripts/motor_reverso_pil.py` |
| LV  | `scripts/motor_reverso_lv.py`  |
| FV  | `scripts/motor_reverso_fv.py`  |
| LAJ | `scripts/motor_reverso_laj.py` |

### 2. Path do N4 gerado

Hoje: gerado em `TMP_DIR` (fora da obra).

Alvo: gerado em `Fase-6_Execucao_CAD/n4/` — mesmo path que a CE lê — para que o arquivo em disco seja exatamente o que o usuário vê.

```python
# Alvo:
n4_out = obra_dir / "Fase-6_Execucao_CAD" / "n4" / f"{prefix}{elemento_id}.dxf"
```

### 3. G1 (roundtrip de campos)

Hoje: compara ficha do DB com ficha re-extraída do N4 gerado.

Alvo: compara ficha gerada dinamicamente pelo motor com ficha re-extraída do N4.

---

## O que NÃO muda

- Os comparadores canônicos (`forma_canonica_pil.py`, `partes_pil.py`, etc.) — já corretos.
- O gerador STOG — já correto.
- O golden set — continua selando o N4 gerado dinamicamente.

---

## Estado de implementação

- [ ] Refatorar `ficha_adapter.materializar_item()` para chamar motor dinâmico por classe
- [ ] Redirecionar output do gerador para `Fase-6_Execucao_CAD/n4/` no Arete
- [ ] Ajustar G1 para usar ficha dinâmica como referência
- [ ] Revalidar 124 itens (13_PAV) com pipeline dinâmico
- [ ] Atualizar golden set com hashes dos novos N4

## Prioridade

Alta — sem isso, melhorias no motor reverso não são detectáveis automaticamente pelo Arete,
e o score reportado não corresponde ao que o engenheiro vê na interface.
