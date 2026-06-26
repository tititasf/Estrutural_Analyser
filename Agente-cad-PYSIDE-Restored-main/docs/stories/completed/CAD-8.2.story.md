# CAD-8.2 — motor_fase4.py Multi-Pavimento

**Epic:** CAD-8 — Multi-Pavimento + Multi-Obra Automation
**Status:** Done
**Dependências:** CAD-8.1 (dxf_discovery.json)
**Data:** 2026-03-08

---

## Objetivo

Adicionar flag `--all-pavimentos` ao `motor_fase4.py` que lê `dxf_discovery.json`
e processa TODOS os pavimentos de uma obra de forma sequencial.

---

## Contexto

Hoje:
```bash
python scripts/motor_fase4.py --obra DADOS-OBRAS/Obra_TREINO_21 --pavimento "12 PAV"
```

Meta:
```bash
python scripts/motor_fase4.py --obra DADOS-OBRAS/Obra_TREINO_21 --all-pavimentos
# processa todos os pav descobertos em dxf_discovery.json
```

Saída por pavimento: `Fase-4_Sincronizacao/{pav}/JSON_Pilares/`, etc.

---

## Acceptance Criteria

- [ ] AC-1: `--all-pavimentos` lê `DADOS-OBRAS/dxf_discovery.json` e itera por pav
- [ ] AC-2: Saída em `Fase-4_Sincronizacao/{pav}/` (subpasta por pav)
- [ ] AC-3: Se pav não tem DXF PL → skip com warning, não falha
- [ ] AC-4: Compatibilidade retroativa: `--pavimento "12 PAV"` continua funcionando
- [ ] AC-5: Relatório final: N pavimentos processados, X falhas

---

## Mudanças em motor_fase4.py

```python
# Novo argumento
parser.add_argument('--all-pavimentos', action='store_true')

# Em run():
if args.all_pavimentos:
    discovery = load_discovery(args.obra)
    for pav, dxfs in discovery.items():
        if dxfs.get('PL'):
            run_single(obra=args.obra, pav=pav, dxfs=dxfs)
        else:
            log.warning(f"Skipping {pav}: sem DXF PL")
```

---

## File List

- [ ] `scripts/motor_fase4.py` (MODIFICAR — adicionar --all-pavimentos)

---

*CAD-8.2 Backlog | Sprint 5 | 2026-03-08*
