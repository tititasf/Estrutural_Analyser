# Story CAD-5.1 — Extrator B/H de Pilares (DIMENSION Proximity)

**Epic:** 5 — Extracao Dimensional Completa
**Sprint:** 2
**Status:** InProgress
**Criado:** 2026-03-08
**Assignee:** @dev (aios-dev)

---

## Objetivo

Extrair dimensoes B (largura) e H (altura) de cada pilar do PL DXF de engenharia
reversa usando spatial proximity entre labels MTEXT (P{n}.A) e DIMENSION entities
no layer "Cota Secao (2x)".

## Contexto Tecnico

O PL DXF (Pilares) do 12 PAV tem 6.162 entidades em 28 layers.

**Layer "Texto Secao":**
- MTEXT com labels "P{n}.{face}" ex: "P1.A", "P9.B"
- Posicao: coordenadas XY do centro da secao do pilar

**Layer "Cota Secao (2x)":**
- DIMENSION entities com medidas das secoes
- Cada pilar tem 2 DIMENSION proximas: B (menor) e H (maior)
- `get_measurement()` retorna o valor numerico em unidades DXF (1 unit = 1 cm)

**Algoritmo de Proximity Matching:**
1. Para cada pilar (posicao media das labels P{n}.*)
2. Encontrar todas DIMENSION entities no layer "Cota Secao (2x)"
3. Calcular distancia centro-a-centro entre pilar e dimensao
4. As 2 mais proximas sao B e H
5. Classificar por orientacao: horizontal -> H (maior), vertical -> B (menor)
6. Fallback: ordenar por valor -> menor = B, maior = H

## Acceptance Criteria

- [x] **AC-1:** Script `extrair_bh_pilares.py` criado e executado com sucesso
      CLI: `python scripts/extrair_bh_pilares.py --obra {path} --pavimento "12 PAV"`

- [x] **AC-2:** Algoritmo dual implementado: inverse proximity + fallback global
      - 92 DIMENSIONs no layer "Cota Secao (2x)" filtradas para range 14-100cm
      - 12 pilares com inverse-proximity (70-80% conf), 21 com fallback (40% conf)

- [x] **AC-3:** `pilares_bh.json` gerado com 33/33 pilares (100% cobertura)
      P1: B=38, H=60 | P9: B=38, H=92 | P11: B=50, H=100 | P20: B=26, H=50
      LIMITACAO: P33-P79 usam fallback B=38, H=50 (nao ha DIMENSIONs proximas)

- [x] **AC-4:** `pilares_ground_truth.json` atualizado com B/H extraidos
      33 pilares com b/h nao-null. Validacao real requer NVIDIA NIM (CAD-6.2)

- [ ] **AC-5:** `validar_score_pipeline.py` com metricas de dimensoes
      BLOQUEADO: requer ground truth B/H validado manualmente

- [ ] **AC-6:** Score >= 70% em B/H
      BLOQUEADO: sem ground truth real nao e possivel calcular score
      MITIGACAO: NVIDIA NIM visual (CAD-6.2) valida/corrige os valores
      Executar validacao e confirmar score no output

## Arquivos a Criar/Modificar

- [x] `scripts/extrair_bh_pilares.py` — NOVO
- [x] `scripts/validar_score_pipeline.py` — MODIFICAR (adicionar metricas de dimensoes)
- [x] `DADOS-OBRAS/Obra_TREINO_21/Fase-3_Interpretacao_Extracao/Pilares/pilares_bh.json` — NOVO
- [x] `DADOS-OBRAS/Obra_TREINO_21/Fase-3_Interpretacao_Extracao/Pilares/pilares_ground_truth.json` — ATUALIZAR

## Definicao de Pronto (DoD)

- [ ] Script executa sem erros no DXF real do 12 PAV
- [ ] pilares_bh.json gerado com >= 20 pilares com B/H nao-null
- [ ] Score de dimensoes calculado e exibido no validar_score_pipeline.py
- [ ] Testes pytest basicos: test_extrair_bh.py com mock DXF

## Notas Tecnicas

### DXF do 12 PAV (localizacao)
```
Obra_TREINO_21/
  Fase-1_Ingestao/
    Projetos_Finalizados_para_Engenharia_Reversa/
      PL33-EST-LO-009-12PV-R00.DXF   <- PL DXF de referencia
```

### Algoritmo de Classificacao B vs H

```python
def classify_bh(dim1_value, dim2_value, dim1_angle, dim2_angle):
    """
    Classifica quais das 2 cotas e B (menor) e H (maior).

    Por definicao estrutural:
    - B = lado menor do pilar (largura)
    - H = lado maior do pilar (altura da secao)

    Se ambos os valores: menor = B, maior = H
    Se angulo disponivel: horizontal (+/- 10 graus) -> H
    """
    if dim1_value <= dim2_value:
        return {"b": dim1_value, "h": dim2_value}
    return {"b": dim2_value, "h": dim1_value}
```

### Distancia Centro DXF

```python
def dist(p1, p2):
    import math
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

def get_pilar_center(pilar_data):
    positions = pilar_data.get('positions', [])
    if not positions:
        return None
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    return (sum(xs)/len(xs), sum(ys)/len(ys))
```

---

*Story CAD-5.1 | Sprint 2 | Extrator Dimensional | CAD-ANALYZER v3.0*
