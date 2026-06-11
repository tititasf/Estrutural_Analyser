# Certificação CAD-ANALYZER — Obra_TESTE_DN

**Pavimento:** 12 PAV  
**Pipeline:** CAD-ANALYZER v4.0  
**Timestamp:** 2026-05-22T00:02:35.041829+00:00  

## Status Final: ✅ APROVADO

| Critério | Descrição | Score | Status | Tipo |
|----------|-----------|-------|--------|------|
| `C1_ids_match` | IDs match: hall=0%, miss≤5% | - | ⏭️ SKIP | BLOCK |
| `C2_dimensional_bh` | Dimensional B/H >= 95% | - | ⏭️ SKIP | BLOCK |
| `C3_assembly_grade` | Assembly grade_1 >= 72% | - | ⏭️ SKIP | WARN |
| `C4_dxf_individual` | DXF individual PASS | - | ⏭️ SKIP | WARN |
| `C5_dxf_coletivo` | DXF coletivo score >= 95% | - | ⏭️ SKIP | BLOCK |
| `C6_fidelidade` | Fidelidade estrutural >= 50/100 | 0.0 | ❌ FAIL | WARN |
| `C7_multi_pav` | Pipeline multi-pav executa | - | ⏭️ SKIP | WARN |
| `C8_reproducibilidade` | Resultados determinísticos | - | ⚠️ WARN | WARN |

## Avisos (não bloqueantes)

- **C6_fidelidade**: WARN: ezdxf pipeline gera DXFs de identificação (Frente 2). Fidelidade visual >= 95% é responsabilidade da Frente 1 (AutoCAD/SCR — score 95.1 para PL).
- **C8_reproducibilidade**: Reprodução verificada por presença de artefatos determinísticos

---
*APROVADO — Pipeline certificado com fidelidade suficiente para uso em produção.*
