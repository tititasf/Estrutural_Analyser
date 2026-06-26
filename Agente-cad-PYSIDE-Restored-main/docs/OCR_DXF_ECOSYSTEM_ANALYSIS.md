# Análise do Ecossistema OCR/DXF vs. Nosso Pipeline

**Data:** 2026-05-17  
**Escopo:** Comparativo honesto entre tecnologias da pesquisa e nosso sistema atual

---

## TL;DR — Diagnóstico em 3 linhas

Nosso pipeline **não tem um problema de OCR** — e isso é uma boa notícia. Nosso gargalo real
está na **compreensão semântica estrutural** (rule-based regex vs. ML) e na **dependência de
API externa** para validação visual. As tecnologias da pesquisa são relevantes em 2 pontos
específicos, não em 10.

---

## O Que Nosso Sistema Realmente Faz

### Fase-1: Parsing Vetorial Nativo (`dxf_loader.py`)
```
DXF → ezdxf → {lines, polylines, texts, circles, arcs, ellipses, splines, hatches}
```
- Extrai primitivas geométricas **diretamente do formato vetorial**
- SEM rasterização, SEM OCR
- Textos são lidos como objetos `TEXT`/`MTEXT` nativos — já são strings Unicode
- **Veredicto: correto. Não precisa de OCR aqui.**

### Fase-3: Extração Semântica (`engenharia_reversa_dxf.py`)
```
DXF → streaming parser → regex patterns → {pilar_data, viga_data, pe_direito}
```
- Parser próprio sem ezdxf completo (streaming line-by-line para economizar RAM)
- Extrai IDs de pilares/vigas via **regex + layer name matching** (`NOMENCLATURA`, `TEXTO_SE`)
- Confidence explicitada no código:
  - Nomes/IDs: ALTA (extraído de MTEXT labels)
  - Pé-direito: MÉDIA (DIMENSION com texto "Pé DIREITO")
  - B e H: BAIXA (`confidence=0.3` — parsing espacial não implementado)
- **Veredicto: funcional mas limitado. O gargalo real está aqui.**

### Fase-8: Validação Visual (`validar_visual_dxf.py`)
```
DXF → ezdxf + MatplotlibBackend → PNG 150DPI → NVIDIA NIM (Llama 3.2 90B Vision) → JSON scores
```
- Rasteriza para grid de tiles NxN
- Envia para API externa de visão computacional
- Retorna score estruturado: geometria, dimensões, labels, layout
- **Veredicto: funciona bem mas tem 2 riscos: dependência de API + custo por chamada.**

---

## Comparativo com as Tecnologias da Pesquisa

### O que a pesquisa cobre que NÃO é nosso problema

| Tecnologia | Proposta | Por que não precisamos |
|-----------|----------|----------------------|
| OCR em plantas escaneadas (Tesseract, PaddleOCR) | Ler texto de imagens rasterizadas | Nossos DXFs são **vetoriais nativos com TEXT/MTEXT** — não precisamos de OCR |
| Scan2CAD / DARE ONE | Converter plantas físicas escaneadas para DXF | Trabalhamos com DXFs digitais de origem, não scans |
| shxparser | Reconstituir texto "explodido" de fontes SHX | Nossos DXFs STOG têm texto nativo; não há texto explodido |
| PDFSHXTEXT (AutoCAD) | Recuperar texto de PDFs com fontes SHX | Não usamos PDFs como fonte primária |
| Pipeline raster: ezdxf → OpenCV → Tesseract | 5 passos para extrair texto de imagem | Nosso texto já é vetorial — skip desnecessário |

### O que a pesquisa cobre que É relevante para nós

| Tecnologia | Relevância | Impacto Estimado |
|-----------|-----------|-----------------|
| **YOLaT** (grafos vetoriais sem rasterização) | ALTA | Alto |
| **wenzel-lab/dxf-fix** (KD-Tree cleanup) | MÉDIA | Médio |
| **Local Vision Model** (alternativa ao NVIDIA NIM) | ALTA | Alto |
| **ezdxf.addons.drawing** em alta resolução | BAIXA | Já usamos |

---

## Análise de Cada Tecnologia Relevante

### 1. YOLaT — Reconhecimento Vetorial Sem Rasterização (GitHub: pesquisa NeurIPS)

**O que é:** Modelo que processa geometria DXF como grafo (nós = pontos, arestas = linhas)
em vez de converter para pixels. Detecta textos, dimensões e elementos diretamente nas
coordenadas matemáticas.

**Onde nos ajudaria:** Na extração B×H dos pilares e dimensões das vigas (nossa Fase-3
com `confidence=0.3`). Em vez de regex em texto livre, processar o **relacionamento espacial**
entre a cota e o elemento que ela dimensiona.

**Exemplo do nosso problema atual:**
```
# engenharia_reversa_dxf.py — confidence=0.3
# "requer parsing espacial complexo"
# B e H: BAIXA
```
Um modelo de grafos geométricos saberia que o MTEXT "30x50" posicionado a 12mm de uma
linha de pilar com a layer `TEXTO_SE` é a seção transversal daquele pilar.

**Estado open-source:** Apenas paper NeurIPS — sem repositório GitHub público com implementação
completa. Mas os ingredientes estão disponíveis: `ezdxf` (grafo de entidades) + `torch-geometric`
(Graph Neural Networks).

**Esforço para adotar:** Alto (seria necessário treinar o modelo com nossos DXFs STOG).
**Impacto:** Elevaria B×H confidence de 0.3 → ~0.8.

---

### 2. wenzel-lab/dxf-fix — KD-Tree Spatial Cleanup

**GitHub:** `https://github.com/wenzel-lab/dxf-fix`  
**O que é:** Script Python que usa `scipy.spatial.KDTree` para conectar extremidades de linhas
quebradas, remover duplicados e fechar polígonos em DXFs de fabricação.

**Onde nos ajudaria:** Nos DXFs gerados pelos nossos Robôs (PL/LV/FV/LJ), especialmente
nas linhas de hachura de concreto e nas polígonos dos pilares. Atualmente alguns DXFs gerados
têm microgaps entre segmentos que causam falhas visuais no comparativo.

**Implementação:** Muito simples — é um script de 200 linhas. Poderia ser integrado como
pós-processamento opcional nos 4 robôs:
```python
# Pós-processamento pós-geração de SCR
from scripts.dxf_cleanup import fix_gaps  # versão adaptada do wenzel-lab
fix_gaps(output_dxf, tolerance=0.1)  # 0.1mm tolerance
```

**Esforço:** Baixo (copiar, adaptar para nossas tolerâncias).  
**Impacto:** Reduziria falsos negativos na validação visual (score ≥+5% nos tiles com hachura).

---

### 3. Local Vision Model — Alternativa ao NVIDIA NIM

**O que é:** Substituir a chamada a `integrate.api.nvidia.com` por um modelo de visão local.

**Problema atual:**
```python
# validar_visual_dxf.py
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"  # API externa
NVIDIA_MODEL_DEF = "meta/llama-3.2-90b-vision-instruct"  # 90B — pesado
```
- Requer internet durante validação
- Latência de rede (cada tile = 1 chamada API)
- Custo por token na API da NVIDIA NIM
- Falha em ambiente offline (canteiro de obras, VPN restrita)

**Alternativas open-source viáveis:**

| Modelo | Parâmetros | VRAM Mín. | Qualidade em Eng. | GitHub |
|--------|-----------|-----------|-------------------|--------|
| **LLaVA-1.6 (Mistral 7B)** | 7B | 8GB | Boa | `haotian-liu/LLaVA` |
| **moondream2** | 1.8B | 4GB | Média | `vikhyatk/moondream2` |
| **Phi-3.5-vision** | 4B | 6GB | Boa | `microsoft/Phi-3.5-vision-instruct` |
| **InternVL2-4B** | 4B | 6GB | Muito boa | `OpenGVLab/InternVL` |

**Stack de integração local:**
```python
# via Ollama (simplest path)
import requests
response = requests.post("http://localhost:11434/api/generate", json={
    "model": "llava:7b",
    "prompt": PROMPT_TILE,
    "images": [base64_tile],
    "stream": False
})
```

**Esforço:** Médio (instalar Ollama + baixar modelo + adaptar chamada API).  
**Impacto:** Operação 100% offline + sem custo por chamada + latência de rede zero.

---

### 4. ezdxf.addons já disponíveis (já temos, pouco usados)

A pesquisa menciona módulos do `ezdxf` que já temos instalado mas não aproveitamos:

| Módulo | O que faz | Uso atual |
|--------|-----------|-----------|
| `ezdxf.addons.drawing` | Renderiza DXF para PNG/PDF | ✅ Usado no validar_visual_dxf.py (150 DPI) |
| `ezdxf.addons.text2path` | Converte TEXT/MTEXT em caminhos vetoriais | ❌ Não usado |
| `ezdxf.addons.MTextExplode` | Decompõe MTEXT em primitivas | ❌ Não usado |

**`ezdxf.addons.MTextExplode`** poderia ajudar na Fase-3: analisar MTEXT complexos
com formatação `{\fRomans|b0|i0;\H0.7x;P1}` que nosso parser de streaming perde:
```python
# Exemplo de MTEXT com formatação inline que nosso regex ignora:
# {\fRomans|b0;P1\pxi0;{30}}  ← "P1" + seção "30" em bloco
from ezdxf.addons.mtext_explode import MTextExplode
```

---

## Resumo Executivo — Onde Realmente Estamos

```
SISTEMA ATUAL — ANÁLISE HONESTA

✅ O QUE ESTÁ BOM:
  - Parsing vetorial nativo (sem OCR desnecessário)
  - Extração semântica de IDs funcionando (Fase-3 para PL/LV/LJ)
  - Validação visual com LLM de visão funcionando
  - Pipeline completo F1→F8 operacional

⚠️ GAPS REAIS (por ordem de impacto):
  1. B×H de pilares: confidence=0.3 — o dado mais crítico para obra
     → Fix: parsing espacial (distância MTEXT→linha pilar)
     → Upgrade: Graph Neural Network (YOLaT-style)

  2. Dependência API externa para visão (NVIDIA NIM)
     → Fix: Ollama + LLaVA ou InternVL2 local (4-8GB VRAM)

  3. DXFs gerados com microgaps em polígonos/hachuras
     → Fix: wenzel-lab/dxf-fix KD-Tree (200 linhas, baixo esforço)

  4. MTEXT com formatação inline perdida no streaming parser
     → Fix: ezdxf.addons.MTextExplode (já instalado, não usado)

❌ O QUE NÃO PRECISAMOS (contrário à intuição):
  - OCR em imagens (nosso texto é vetorial nativo)
  - Scan2CAD / DARE ONE (para scans — não é nosso caso)
  - shxparser (sem texto SHX explodido nos nossos DXFs)
  - Pipeline OpenCV+Tesseract para extrair texto de DXF
```

---

## Roadmap de Upgrades Recomendados (Só Open-Source)

| Prioridade | Upgrade | Biblioteca | Esforço | Impacto |
|-----------|---------|-----------|---------|---------|
| **P0** | Parsing espacial B×H (distância geométrica MTEXT→entidade) | `ezdxf` + `scipy.spatial` | 2-3 dias | confidence 0.3→0.7 |
| **P1** | MTEXT formatting parser com `MTextExplode` | `ezdxf.addons.mtext_explode` | 1 dia | +10% texto extraído |
| **P1** | DXF cleanup KD-Tree pós-geração | `scipy` (wenzel-lab/dxf-fix adaptado) | 1 dia | score visual +5% |
| **P2** | Local vision model via Ollama | `requests` + Ollama | 2 dias | Offline + sem custo API |
| **P3** | GNN para relação geométrica semântica | `torch-geometric` + `ezdxf` | 2-4 semanas | Precisão estrutural total |

---

## Conclusão

Nosso sistema está bem para o estágio atual. Não estamos no caminho errado. O que a pesquisa
chama de "OCR para DXF" não se aplica diretamente ao nosso caso porque trabalhamos com
DXFs vetoriais nativos — o problema de OCR (reconhecer texto em imagens) simplesmente
não existe na nossa pipeline.

Os dois upgrades de maior ROI são:
1. **Parsing espacial B×H** — resolve o dado com menor confiança, usa só `scipy` (já instalado)  
2. **Vision model local via Ollama** — elimina dependência de internet e custo por validação

Ambos são realizáveis com código Python puro e bibliotecas open-source sem mudança de
arquitetura.
