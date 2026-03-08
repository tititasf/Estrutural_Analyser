# Entrevista: Sistema de Pilares

## Objetivo
Documentar requisitos detalhados para o processamento de pilares no AgenteCAD.

---

## Perguntas e Respostas

### 1. Identificacao de Pilares

**P: Como identificar um pilar no DXF estrutural?**
R: [RESPONDER]
- Padroes geometricos?
- Layers especificos?
- Textos associados (P-1, P1, PILAR1)?
- Blocos especificos?

**P: Quais formatos de pilar existem?**
R: 
- [ ] RETANGULAR (4 lados)
- [ ] CIRCULAR
- [ ] L (6 lados)
- [ ] T (8 lados)
- [ ] U (8 lados)
- [ ] Outros?

**P: Como determinar o formato de um pilar?**
R: [RESPONDER]
- Pela quantidade de vertices?
- Pelo aspect ratio?
- Por texto associado?

---

### 2. Faces do Pilar

**P: Qual a regra de orientacao das faces?**
R: [RESPONDER]

RETANGULAR:
- A: ?
- B: ?
- C: ?
- D: ?

L:
- A-F: ?

T:
- A-H: ?

U:
- A-H: ?

**P: Como determinar qual face e qual baseado na rotacao?**
R: [RESPONDER]

---

### 3. Dados Necessarios por Face

**P: Quais dados sao necessarios para cada face?**
R: [RESPONDER]

- [ ] Laje 1: nome, nivel, posicao, altura h
- [ ] Laje 2: nome, nivel, posicao, altura h
- [ ] Viga lateral esquerda: nome, dimensao, abertura
- [ ] Viga lateral direita: nome, dimensao, abertura
- [ ] Vigas frontais (ate 4): nome, dimensao, abertura, diferenca nivel
- [ ] Outros campos?

**P: Como determinar a posicao da laje (TOPO/FUNDO/CENTRO)?**
R: [RESPONDER]
- Comparar niveis?
- Regra especifica?

---

### 4. Producao de Grades

**P: Como calcular a quantidade de sarrafos?**
R: [RESPONDER]
- Formula?
- Espacamento padrao?

**P: Onde ficam as aberturas?**
R: [RESPONDER]
- Regra de posicionamento?
- Dimensoes das aberturas?

**P: Como calcular parafusos?**
R: [RESPONDER]
- Quantidade por face?
- Posicionamento?

---

### 5. Outputs Esperados

**P: Qual formato do SCR de pilar?**
R: [RESPONDER]
- Comandos AutoCAD usados?
- Ordem das operacoes?

**P: Qual formato do DXF produto?**
R: [RESPONDER]
- Layers?
- Entidades?

**P: Qual formato do JSON de configuracao?**
R: [RESPONDER]
- Schema completo?
- Campos obrigatorios?

---

### 6. Exemplos

**P: Pode fornecer exemplo de pilar simples RETANGULAR?**
R: [FORNECER EXEMPLO]

**P: Pode fornecer exemplo de pilar complexo (L, T, U)?**
R: [FORNECER EXEMPLO]

---

## Notas Adicionais

[ADICIONAR NOTAS]

---

## Arquivos de Referencia

- [ ] Exemplo de DXF estrutural com pilares
- [ ] Exemplo de grade gerada (DXF produto)
- [ ] Exemplo de SCR
- [ ] Exemplo de JSON

---

## Status

- [ ] Entrevista inicial
- [ ] Revisao
- [ ] Validado
