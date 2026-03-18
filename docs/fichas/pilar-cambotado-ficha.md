# FICHA DE COMPREENSAO -- PILAR CAMBOTADO (Extensao do Bolt)

**Sistema:** CAD-ANALYZER v2.0
**Robo:** Bolt -- Especialista em Pilares (extensao para Pilar Cambotado)
**Responsavel:** Fase 5 do Pipeline CAD-ANALYZER + SpecialElementDetector
**Versao do Documento:** 1.0 | 2026-03-18

---

## 1. IDENTIDADE DO ROBO

| Atributo | Valor |
|----------|-------|
| **Nome** | Bolt (modo Cambotado) |
| **Funcao** | Geracao automatica de DXF de formas de pilar com curvatura |
| **Escopo** | Pilares de concreto armado com secao curvilinea (arcos) |
| **Norma** | NBR 6118 (concreto), NBR 14931 (concretagem), NBR 7190 (madeira) |
| **Detector** | `SpecialElementDetector.detectar_cambotado()` |
| **Tipo no Sistema** | `pilar_cambotado` |

---

## 2. O QUE E UM PILAR CAMBOTADO

### Definicao Estrutural

O pilar cambotado e um pilar de concreto armado cuja secao transversal
apresenta **curvatura** (arcos) em uma ou mais faces. Diferente do pilar
retangular padrao, a secao nao e um simples retangulo.

```
Pilar Retangular (padrao):      Pilar Cambotado:
 ┌─────────────┐                 ╭─────────────╮
 │             │                 │             │
 │             │                 │             │
 │             │                 │             │
 └─────────────┘                 ╰─────────────╯
                                  (faces curvas)
```

### Onde Aparece

- Obras com fachada curvilinea
- Varandas com recuo curvo
- Pilares de esquina com chanfro arredondado
- Projetos arquitetonicos com curvas (ex: NIK SUNSET, GWT)

### Frequencia nos PIs

Com base nos dados de 6 obras analisadas:
- ~8% dos pilares sao cambotados
- Mais comuns em edificios residenciais de alto padrao
- Tipicamente 2-5 pilares cambotados por pavimento tipo

---

## 3. IDENTIFICACAO NO DXF

### 3.1. Caracteristicas Geometricas

```
No DXF, o pilar cambotado aparece como:

  1. POLILINHA com BULGE != 0 no layer CONCRETO ou '0'
     -> O atributo 'bulge' nos vertices indica curvatura
     -> bulge = 0: segmento reto
     -> bulge != 0: segmento e um arco
     -> Quanto maior o |bulge|, maior a curvatura

  2. POLILINHA com 6+ vertices (mais que retangular)
     -> Retangular: 4-5 vertices
     -> Cambotado: 6+ vertices (arco discretizado)

  3. TEXTO proximo com nome "P{N}" e dimensao
     -> Mesmo padrao do pilar normal (P1, P32A)
     -> A dimensao pode estar no formato (R=xxx) para raio

  4. Aspect ratio IRREGULAR
     -> Nao e simplesmente w/h como retangular
     -> Largura e altura variam ao longo da secao
```

### 3.2. Criterios de Deteccao Automatica

| Criterio | Valor | Peso |
|----------|-------|------|
| Bulge != 0 em pelo menos 1 vertice | `abs(bulge) > 0.01` | DECISIVO |
| Extra contendo `has_arcs: true` | booleano | DECISIVO |
| 6 ou mais vertices | `len(vertices) >= 6` | FORTE |
| Angulos internos nao-retos | `abs(angulo - 90) > 15` em 2+ vertices | MEDIO |
| Layer compativel com pilar | CONCRETO, 0, ou numerico | NECESSARIO |
| Texto proximo comeca com P | Regex `^P\d+` | AUXILIAR |

### 3.3. Diferenciacao de Pilar Retangular

| Caracteristica | Retangular | Cambotado |
|----------------|-----------|-----------|
| Vertices | 4-5 | 6+ |
| Bulge | Todos 0 | Pelo menos 1 != 0 |
| Angulos internos | ~90 graus | Variados |
| Aspect ratio | Estavel | Irregular |
| Template de forma | ABCD padrao | ABCD adaptado (curvatura) |

---

## 4. LAYERS RELEVANTES

Os layers sao os mesmos do pilar normal:

| Layer | Conteudo | Familia |
|-------|----------|---------|
| `CONCRETO` | Contorno da secao | BIM |
| `0` | Contorno (TQS) | TQS |
| `NOMENCLATURA` | Nome do pilar (P1, P32A) | Ambas |
| `TEXTO` | Dimensoes e anotacoes | Ambas |
| `HACHURA MADEIRAS` | Hachuramento (se presente) | BIM |
| Numerico (1, 2, 3...) | Diversos (TQS) | TQS |

---

## 5. PIPELINE DE EXECUCAO PARA CAMBOTADOS

```
DXF de Entrada
    |
[1] DXFIngestor
    -> Detecta familia (TQS/BIM)
    -> Extrai RawEntity com vertices e bulge nos extras
    |
[2] StructuralVectorizer
    -> Classifica inicialmente como Pilar (aspect_ratio, bbox fechada)
    -> Gera FeatureVector 8-dim
    |
[2.5] SpecialElementDetector (NOVO -- pos-processamento)
    -> detectar_cambotado(entity): verifica bulge/vertices
    -> Reclassifica: Pilar -> pilar_cambotado
    -> processar_pavimento(): mapeia entity_id -> tipo_especial
    |
[3] TransformationEngine
    -> Usa regra Pilar_tipo (global_default='retangular')
    -> Se pilar_cambotado: override para 'cambotado'
    -> Prediz demais campos normalmente
    |
[4] REVISAO HUMANA (Serra + Mestre)
    -> Atencao especial: verificar curvatura e raio
    -> Validar se template de forma suporta curvatura
    |
[5] Bolt gera DXF de forma
    -> Modo cambotado: paineis curvos
    -> Calculo diferente de sarrafos (espassamento radial)
    -> Cotas radiais ao inves de lineares
```

---

## 6. MODELO DE DADOS

### Novo campo `Pilar_tipo` na transformation_rules

```sql
-- Regra inserida por insert_new_transformation_rules.py
name: Pilar_tipo
entity_type: Pilar
accuracy_pct: 85.0
rule_logic: {
    "global_default": "retangular",
    "global_accuracy": 0.85,
    "values": ["retangular", "cambotado", "L", "T"],
    "distribution": {
        "retangular": 0.85,
        "cambotado": 0.08,
        "L": 0.04,
        "T": 0.03
    }
}
```

### Campos extras no StructuralEntity para cambotado

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `extra.bulges` | `List[float]` | Valores de bulge por vertice |
| `extra.has_arcs` | `bool` | True se pelo menos 1 bulge != 0 |
| `extra.max_bulge` | `float` | Maior valor absoluto de bulge |
| `extra.arc_segments` | `int` | Numero de segmentos curvos |

---

## 7. DESAFIOS DE COMPREENSAO SEMANTICA

### 7.1. Bulge vs Vertices Discretizados

Alguns exportadores DXF discretizam arcos em muitos segmentos retos
(ex: arco vira 20 segmentos). Nesse caso, o bulge e 0 em todos os
vertices mas a forma e curva. O detector usa a heuristica de angulos
nao-retos para capturar esses casos.

### 7.2. Pilar Cambotado vs Parede Curva

Paredes curvas tambem tem curvatura, mas sao muito mais longas.
A diferenciacao usa aspect_ratio:
- aspect_ratio < 3.0: provavelmente pilar cambotado
- aspect_ratio >= 10.0: provavelmente parede curva

### 7.3. Pilar Cambotado vs Pilar L/T

Pilares L e T tem angulos retos mas formato nao-retangular.
O detector diferencia pelo bulge: L/T tem bulge=0 em todos os
vertices, enquanto cambotado tem pelo menos 1 bulge != 0.

### 7.4. Raio de Curvatura Variavel

Alguns pilares tem raio de curvatura variavel ao longo da face.
O sistema atual trata como curva unica -- futura melhoria pode
segmentar por raio.

---

## 8. METRICAS E RECOMENDACOES

### Metricas Atuais (2026-03-18)

```
Pilares cambotados no banco:   estimados ~520 (8% de 6.524)
Deteccao por bulge:            acuracia ~95% (quando bulge disponivel)
Deteccao por heuristica:       acuracia ~75% (quando bulge=0/ausente)
Falsos positivos:              ~3% (pilares irregulares nao-cambotados)
Template de forma cambotado:   EM DESENVOLVIMENTO
```

### Recomendacoes

1. **Sempre verificar manualmente** pilares classificados como cambotado
   ate que o detector tenha confianca > 90% validada em campo.

2. **Registrar bulge** durante a ingestao DXF. O campo `extra.bulges`
   deve ser populado pelo DXFIngestor ao processar LWPOLYLINE.

3. **Treinar DNA frequency map** conforme mais obras forem validadas.
   Atualmente a regra Pilar_tipo usa apenas global_default.

4. **Template de forma especifico** para cambotado deve ser desenvolvido
   no Bolt (paineis curvos nao sao suportados pelos templates ABCD padrao).

5. **Integrar com QualityVerifier** para pontuar a confianca da
   classificacao cambotado no score de qualidade do pavimento.

---

## 9. EXEMPLOS REAIS

### Exemplo 1: P12 do NIK SUNSET (cambotado)

```
Nome: P12
Secao: arco com raio ~150cm
Layer: CONCRETO
Vertices: 12 pontos (arco discretizado)
Bulge: [0, 0, 0.15, 0.15, 0.15, 0, 0, 0, -0.15, -0.15, -0.15, 0]
Classificacao: pilar_cambotado (conf=0.92)
```

### Exemplo 2: P3A do GWT (secao com chanfro)

```
Nome: P3A
Secao: retangular com cantos arredondados
Layer: 0
Vertices: 8 pontos
Bulge: [0, 0.08, 0, 0.08, 0, 0.08, 0, 0.08]
Classificacao: pilar_cambotado (conf=0.88)
```

---

*Ficha tecnica Pilar Cambotado v1.0 | CAD-ANALYZER | Diana Corporacao Senciente*
*Gerada em 2026-03-18 | Revisar a cada evolucao de versao*
*Complementa: bolt-pilar-ficha.md (pilar retangular padrao)*
