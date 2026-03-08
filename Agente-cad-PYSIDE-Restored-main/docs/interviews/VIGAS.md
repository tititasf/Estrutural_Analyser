# Entrevista: Sistema de Vigas

## Objetivo
Documentar requisitos detalhados para o processamento de vigas (laterais e fundos) no AgenteCAD.

---

## Perguntas e Respostas

### 1. Identificacao de Vigas

**P: Como identificar uma viga no DXF estrutural?**
R: [RESPONDER]
- Padroes geometricos?
- Textos associados (V1, V-1, VIGA1)?
- Relacao com pilares?

**P: Como diferenciar viga de outros elementos lineares?**
R: [RESPONDER]

---

### 2. Estrutura de Lados

**P: Como determinar lado A e lado B de uma viga?**
R: [RESPONDER]
- Lado A sempre esquerda/baixo?
- Lado B sempre direita/cima?
- Depende da orientacao?

**P: As vigas sempre tem 2 lados?**
R: [RESPONDER]

---

### 3. Segmentos e Conflitos

**P: O que e um segmento de viga?**
R: [RESPONDER]
- Trecho entre conflitos?
- Como medir?

**P: O que sao conflitos?**
R: 
- [ ] Pilares que a viga atravessa
- [ ] Outras vigas que cruzam
- [ ] Fim da viga
- [ ] Outros?

**P: Como desenhar as linhas de segmentos no canvas?**
R: [RESPONDER]
- Por cima das linhas originais?
- Cores especificas?

**P: Como medir distancias de conflitos?**
R: [RESPONDER]

---

### 4. Dados Necessarios por Lado

**P: Quais dados sao necessarios para cada lado de viga?**
R: [RESPONDER]

- [ ] Local inicial (pilar, parede, viga)
- [ ] Local final
- [ ] Dimensao do corte
- [ ] Nivel
- [ ] Lajes associadas
- [ ] Lista de segmentos com:
  - Nome do conflito
  - Tipo do conflito
  - Distancia ate o conflito
  - Tamanho do conflito
  - Distancia apos conflito

---

### 5. Laterais de Vigas

**P: Como calcular a lateral de uma viga?**
R: [RESPONDER]
- Altura x comprimento?
- Recortes para pilares?

**P: Quais recortes sao necessarios?**
R: [RESPONDER]
- Recorte no encontro com pilar?
- Dimensoes dos recortes?

---

### 6. Fundos de Vigas

**P: Como calcular o fundo de uma viga?**
R: [RESPONDER]
- Largura x comprimento?
- Sarrafos transversais?

**P: Como posicionar sarrafos no fundo?**
R: [RESPONDER]
- Espacamento padrao?
- Alinhamento?

---

### 7. Outputs Esperados

**P: Qual formato do SCR de lateral?**
R: [RESPONDER]

**P: Qual formato do SCR de fundo?**
R: [RESPONDER]

**P: Qual formato do JSON de configuracao?**
R: [RESPONDER]

---

### 8. Exemplos

**P: Pode fornecer exemplo de viga simples (2 segmentos)?**
R: [FORNECER EXEMPLO]

**P: Pode fornecer exemplo de viga complexa (multiplos conflitos)?**
R: [FORNECER EXEMPLO]

---

## Notas Adicionais

[ADICIONAR NOTAS]

---

## Arquivos de Referencia

- [ ] Exemplo de DXF estrutural com vigas
- [ ] Exemplo de lateral gerada
- [ ] Exemplo de fundo gerado
- [ ] Exemplo de SCR
- [ ] Exemplo de JSON

---

## Status

- [ ] Entrevista inicial
- [ ] Revisao
- [ ] Validado
