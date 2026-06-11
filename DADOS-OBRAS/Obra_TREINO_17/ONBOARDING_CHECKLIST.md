# Checklist de Onboarding — Obra_TREINO_17

**Criado em:** 2026-04-30T18:15:38.851349+00:00
**Obra path:** D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_17

## 1. DXFs (verificação automática)

| Tipo | Arquivo | Status |
|------|---------|--------|
| PL | NOVA-UNITÁ-METROCASA9 DE JULHO-1PV-PL-R00_R2018_ASCII_ODA.dxf | ✅ |
| LV | NOVA-UNITÁ-METROCASA9 DE JULHO-1PV-LV-R00_R2018_ASCII_ODA.dxf | ✅ |
| FV | NOVA-UNITÁ-METROCASA9 DE JULHO-1PV-FV-R00_R2018_ASCII_ODA.dxf | ✅ |
| LJ | — | ❌ AUSENTE |
| EVG | — | ⏭️ opcional |

## 2. Verificação Manual (obrigatória antes de processar)

- [ ] DXFs abrem no AutoCAD/DXF viewer sem erros
- [ ] Layer 'Texto Seção' ou 'NOMENCLATURA' contém IDs P{n}/V{n}/L{n}
- [ ] Layer 'Cota Seção (2x)' ou 'COTA' contém dimensões B/H
- [ ] Pavimento(s) claramente identificáveis pelo nome do DXF
- [ ] Sem DXFs corrompidos ou com encoding incompatível

## 3. Próximos Passos

```bash
# Processar obra completa
python scripts/cad_pipeline_cli.py run --obra DADOS-OBRAS/Obra_TREINO_17

# Verificar status após processamento
python scripts/cad_pipeline_cli.py status
```

## 4. Gaps Conhecidos a Verificar

- Pilares com IDs em layer '0' ou compound (P1-P2-P3): ok — suportado
- Vigas compostas tipo '(VA2+V16).A': ok — suportado
- Lajes tipo 'L-N' (só espessura h=10): extraídas como GT=0, skip no score
- P2-P8 (pilares especiais): podem estar no PAV TIPO DXF, não no pavimento principal
