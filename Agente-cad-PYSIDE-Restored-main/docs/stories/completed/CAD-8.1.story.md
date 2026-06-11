# CAD-8.1 — Discovery de DXFs por Obra/Pavimento

**Epic:** CAD-8 — Multi-Pavimento + Multi-Obra Automation
**Status:** Done
**Data:** 2026-03-08
**Autor:** CEO-PLANEJAMENTO (Athena)

---

## Objetivo

Criar script `descobrir_obras.py` que faz scan automático de `DADOS-OBRAS/` e mapeia
quais DXFs existem por obra e por pavimento, produzindo `dxf_discovery.json`.

Este script desbloqueia todo o pipeline multi-pav/multi-obra.

---

## Contexto

O pipeline atual hardcoda `--obra DADOS-OBRAS/Obra_TREINO_21 --pavimento "12 PAV"`.
Para escalar para N obras × N pavimentos, precisamos de descoberta automática.

### Estrutura típica de DADOS-OBRAS/

```
DADOS-OBRAS/
  Obra_TREINO_21/
    Fase-1_Ingestao/
      Projetos_Finalizados_para_Engenharia_Reversa/
        12 PAV - PL.dxf          ← pilares planta
        12 PAV - LV.dxf          ← laterais vigas
        12 PAV - FV.dxf          ← fundos vigas
        12 PAV - LJ.dxf          ← lajes
        12 PAV - EVG.dxf         ← esforços vigas (garfos)
        2 PAV - PL.dxf           ← outro pavimento
        ...
```

### Heurística de nomes (case-insensitive)

| Substring | Tipo DXF |
|-----------|----------|
| `PL` | pilares planta (planta de fôrma) |
| `LV` | laterais de vigas |
| `FV` ou `FD` | fundos de vigas |
| `LJ` | lajes |
| `EVG` | esforços de vigas (garfos) |

O prefixo antes do ` - ` ou `_` é o nome do pavimento (ex: "12 PAV", "2 PAV", "TERREO").

---

## Acceptance Criteria

- [x] AC-1: Script `scripts/descobrir_obras.py` criado
- [x] AC-2: Descobre automaticamente todos os DXFs em `Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa/`
- [x] AC-3: Produz `dxf_discovery.json` com formato correto (18 obras, 135 pav, 59 completos)
- [x] AC-4: Gera relatório de DXFs faltantes por obra/pav (!! PARCIAL / XX SEM PL)
- [x] AC-5: CLI: `python scripts/descobrir_obras.py --data-dir DADOS-OBRAS/`
- [x] AC-6: Salva `dxf_discovery.json` em `DADOS-OBRAS/dxf_discovery.json` (nível raiz)

**Resultado validado (2026-03-08):** 18 obras | 135 pavimentos | 59 completos (PL+LV+FV+LJ)

---

## Approach Técnico

```python
import os, json, re
from pathlib import Path

DXF_TYPES = {
    'PL': ['PL'],
    'LV': ['LV'],
    'FV': ['FV', 'FD'],
    'LJ': ['LJ'],
    'EVG': ['EVG'],
}

def descobrir_obra(obra_path: Path) -> dict:
    target = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    if not target.exists():
        return {}

    pavs = {}
    for dxf in target.glob("*.dxf"):
        # Parse nome: "12 PAV - PL.dxf" → pav="12 PAV", tipo="PL"
        nome = dxf.stem  # "12 PAV - PL"
        match = re.match(r'^(.+?)\s*[-_]\s*([A-Z]+)$', nome, re.IGNORECASE)
        if not match:
            continue
        pav_nome = match.group(1).strip()
        tipo_raw = match.group(2).upper()

        tipo = None
        for t, aliases in DXF_TYPES.items():
            if tipo_raw in aliases:
                tipo = t
                break
        if tipo is None:
            continue

        if pav_nome not in pavs:
            pavs[pav_nome] = {t: None for t in DXF_TYPES}
        pavs[pav_nome][tipo] = str(dxf.resolve())

    return pavs
```

---

## CLI

```bash
# Descobrir todas as obras em DADOS-OBRAS/
python scripts/descobrir_obras.py --data-dir DADOS-OBRAS/

# Descobrir obra específica
python scripts/descobrir_obras.py --data-dir DADOS-OBRAS/ --obra Obra_TREINO_21

# Output em local específico
python scripts/descobrir_obras.py --data-dir DADOS-OBRAS/ --output minha_discovery.json
```

---

## File List

- [ ] `scripts/descobrir_obras.py` (CRIAR)
- [ ] `DADOS-OBRAS/dxf_discovery.json` (GERADO pelo script)

---

*CAD-8.1 Ready | Sprint 5 | 2026-03-08*
