# Entrevista: Sistema de Lajes

## Objetivo
Documentar requisitos detalhados para o processamento de lajes no AgenteCAD.

---

## Perguntas e Respostas

### 1. Identificacao de Lajes

**P: Como identificar uma laje no DXF estrutural?**
R: [RESPONDER]
- Texto com circulo?
- Apenas texto (L1, LAJE1)?
- Formato h=12, h:12?
- Hatch?

**P: Quais variacoes de nome de laje existem?**
R:
- [ ] L1, L2, L3...
- [ ] LAJE1, LAJE2...
- [ ] Apenas numero (12)
- [ ] Outros?

---

### 2. Marco da Laje

**P: Como definir o marco (contorno) de uma laje?**
R: [RESPONDER]
- Linhas que definem o perimetro?
- Vigas + pilares + paredes?

**P: Por que usar linhas e nao "balde de tinta"?**
R: [RESPONDER]
- Linhas nao tocam?
- Maior precisao?

**P: Precisa registrar coordenadas absolutas?**
R: [RESPONDER]

---

### 3. Dados Necessarios

**P: Quais dados sao necessarios para uma laje?**
R: [RESPONDER]

- [ ] Nome (L1)
- [ ] Altura h (12, 15, 20cm)
- [ ] Nivel (+3.00)
- [ ] Coordenadas do marco
- [ ] Area calculada
- [ ] Vigas adjacentes
- [ ] Pilares adjacentes

---

### 4. Divisao em Paineis

**P: Como dividir a laje em paineis?**
R: [RESPONDER]
- Linhas verticais + horizontais?
- Distancias acumulativas?

**P: Quais modos de calculo existem?**
R:
- [ ] Modo 1: ?
- [ ] Modo 2: ?
- [ ] Outros?

**P: Como classificar paineis?**
R:
- [ ] Sem deformidade (retangulo perfeito)
- [ ] Com deformidade (outros formatos)

**P: Como agrupar paineis iguais?**
R: [RESPONDER]
- Mesmas dimensoes?
- Tolerancia?

---

### 5. Aprendizado de Layouts

**P: Como funciona o sistema de aprendizado?**
R: [RESPONDER]
- KNN baseado em features geometricas?
- Features usadas: area, perimetro, aspect ratio, solidez?

**P: Como o usuario valida um layout como treino?**
R: [RESPONDER]

**P: Como o sistema sugere layouts para novas lajes?**
R: [RESPONDER]

---

### 6. Outputs Esperados

**P: Qual formato do SCR de laje/paineis?**
R: [RESPONDER]
- Marco?
- Linhas de divisao?
- Cotas?
- Tabela de resumo?

**P: Qual formato do JSON de configuracao?**
R: [RESPONDER]

---

### 7. Exemplos

**P: Pode fornecer exemplo de laje retangular simples?**
R: [FORNECER EXEMPLO]

**P: Pode fornecer exemplo de laje com formato complexo (L, recortes)?**
R: [FORNECER EXEMPLO]

---

## Notas Adicionais

[ADICIONAR NOTAS]

---

## Arquivos de Referencia

- [ ] Exemplo de DXF estrutural com lajes
- [ ] Exemplo de paineis gerados
- [ ] Exemplo de SCR
- [ ] Exemplo de JSON

---

## Status

- [ ] Entrevista inicial
- [ ] Revisao
- [ ] Validado
