# Status — Loop LAJ · Pré-Ficha Visão de Cortes
**Data:** 2026-06-22  
**Branch:** etapa1-fichas-botoes  
**Scope:** 13º PAV · Obra_TREINO_1 · 31 lajes · 47 CVs

---

## O que foi entregue nesta sessão

### UI — Pré-ficha Visão de Cortes (pre_validation_dialog.py)
| Item | Estado |
|------|--------|
| Colunas renomeadas "Laje 1/2" → **"Laje A / Laje B"** | ✅ |
| Formato multi-linha (7 campos por laje) | ✅ |
| Separação: "Posicao da viga: no Norte" ≠ "Classificacao vertical: topo" | ✅ |
| Colunas Lado A/B com largura +20% | ✅ |
| Altura de linha: 310px (7 linhas) | ✅ |

### UI — Pré-ficha Pilares
| Item | Estado |
|------|--------|
| Formato multi-linha Laje:/Altura:/Nivel: nas células Lado A–D | ✅ |
| `_build_slab_nivel_map` via nivel_report['lajes'] | ✅ |
| Estratégia 4: projeção perpendicular para C/D → reduz nulos falsos | ✅ |
| Coluna Override +20% (150→180px) | ✅ |

### Qualidade geométrica dos cortes (headless — 4 lajes testadas)
| Métrica | Resultado |
|---------|-----------|
| Fórmula `dist_fundo + slab_h + dist_topo = beam_height` | **100% (11/11)** |
| Vizinhos detectados | **7/11 (63.6%)** |
| NULOs falsos | **0** — todos os 4 NULOs são bordas reais confirmadas por mapa |

---

## Estado do DB

- `slab_elements.campos_json['cut_views'][i]['ficha']` → **vazio** em todos os 47 CVs
- Correto: fichas são calculadas 100% em **runtime** no diálogo, não persistidas
- O DB guarda apenas: polígono (`coordenadas`), bbox, e pontos brutos dos CVs (`points`)

---

## O que FALTA para 100% LAJ no 13º PAV

### Campos da pré-ficha ainda não preenchidos dinamicamente
| Campo | Fonte necessária | Estado |
|-------|-----------------|--------|
| `Nivel da laje:` | `nivel_report['lajes']` via `_slab_nivel_map` | ✅ implementado — qualidade depende do nivel_report |
| `Distancia do topo/fundo da viga:` | `_parse_cut_poly_sections` runtime | ✅ funciona para os 4 slabs testados |
| `Classificacao vertical:` | `_infer_slab_position` runtime | ✅ retorna topo/centro/fundo |
| Vizinhos (Laje A/B) para os 24 slabs não testados | `_orthogonal_neighbor_slabs` | ⚠️ não testado — prováveis novos NULOs de borda |

### Loop N1→N2 não executado ainda
- `autovalidate_v3` não foi rodado para LAJ neste ciclo
- Campos N2 (`comprimento`, `largura`, `linhas_verticais/horizontais`, `obstaculos`) não comparados
- Nenhum `training_event` gerado nesta sessão
- 0 `calibrator_versions` promovidos (estado persistente desde sessões anteriores)

---

## Próximos passos recomendados (em ordem)

### Passo 1 — Validação humana na app (VOCÊ)
1. Abrir SA com 13º PAV carregado
2. Rodar Análise Geral
3. Entrar na pré-validação (aba "Visão de Cortes")
4. Para cada CV que parecer correto → confirmar Status "Válido"
5. Para os incorretos → anotar o que diverge

### Passo 2 — Nova sessão de loop LAJ (AGENTE)
Ao dar OK, o agente irá:
1. Ler todas as validações humanas registradas no DB (`training_events` + `is_validated`)
2. Rodar `autovalidate_v3` N1→N2 para LAJ (13º PAV)
3. Montar tabela de hit-rate por campo: N1 detectado vs N2 gabarito
4. Classificar cada divergência (parâmetro de motor / regra semântica / gabarito inconsistente)
5. Propor ajustes no motor — sem hardcode, via `transformation_rules` + `engrev_laj_*`
6. Iterar até convergência nos 31 slabs do 13º PAV

### Passo 3 — Gates sequenciais (LONGO PRAZO)
```
13º PAV LAJ 100%
  → Obra_TREINO_1 todos pavimentos LAJ 100%
    → Outras obras treino LAJ 100%
      → Promoção de parâmetros ao default global (≥ 2 obras, princípio #4)
        → Repetir para FV → LV → PIL
```

---

## Critério de "motor LAJ confiável"

> Motor só é considerado confiável quando capaz de resolver **todos os casos do treino** sem hardcode — para todos os pavimentos de Obra_TREINO_1 primeiro, depois para todas as obras-treino. Validações humanas são fonte de verdade; o motor converge para elas, nunca o contrário.

---

## Commits desta sessão
| Hash | Descrição |
|------|-----------|
| `40b731cf6` | 3 bug fixes geometria visão de corte |
| `e5ec3ddf1` | Lado A/B + referência geográfica |
| `94945dec3` | Pré-ficha pilares: multi-linha + fix C/D + nivel |
| `09d3dade3` | Override +20% |
| `dd34b57ac` | Colunas Laje A/B + formato 7 linhas |
| `226748911` | Separa posição geográfica da classificação vertical |

**Aguardando:** OK do usuário para iniciar Passo 2.
