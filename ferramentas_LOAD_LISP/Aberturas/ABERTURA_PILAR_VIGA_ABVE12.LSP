;-------------------------------------------------------------------------------
; Função: Abertura em pilar à esquerda da viga (Novo comando: abpe_novo)
; Arquivo: ABERTURA_PILAR_VIGA_ESQUERDA.LSP
;-------------------------------------------------------------------------------

(defun c:abve12 ()
  (setvar "CMDECHO" 0)

  ; Solicita pontos para desenhar retângulo
  (setq p1 (getpoint "\nSelecione o primeiro ponto do retângulo: "))
  (setq p2 (getpoint p1 "\nSelecione o segundo ponto do retângulo: "))
  
  ; Cria as linhas com PLINE e layers específicos
  (criar_linhas_com_layers_abve12 p1 p2)
  
  ; Zoom focado na área de trabalho com margem
  (command "zoom" "c" (list (/ (+ (car p1) (car p2)) 2) (/ (+ (cadr p1) (cadr p2)) 2)) 5)
)

(defun criar_linhas_com_layers_abve12 (p1 p2 / p3 p4)
  ; Calcula os outros dois pontos do retângulo
  (setq p3 (list (car p2) (cadr p1)))
  (setq p4 (list (car p1) (cadr p2)))
  
  ; Não cria retângulo nem trim, apenas linhas
  ; Zoom center antes de desenhar a parede esquerda
  (command "zoom" "c" (list (/ (+ (car p1) (car p4)) 2) (/ (+ (cadr p1) (cadr p4)) 2)) 5)
  (command "layer" "s" "cota" "")
  (command "pline" p1 p4 "")
  
  ; Zoom center antes de desenhar o topo
  (command "zoom" "c" (list (/ (+ (car p1) (car p3)) 2) (/ (+ (cadr p1) (cadr p3)) 2)) 5)
  (command "pline" p1 p3 "")
  
  ; Zoom center antes de desenhar o fundo
  (command "zoom" "c" (list (/ (+ (car p4) (car p2)) 2) (/ (+ (cadr p4) (cadr p2)) 2)) 5)
  (command "layer" "s" "Painéis" "")
  (command "pline" p4 p2 "")
  
  ; Zoom center antes de desenhar a direita
  (command "zoom" "c" (list (/ (+ (car p3) (car p2)) 2) (/ (+ (cadr p3) (cadr p2)) 2)) 5)
  (command "pline" p3 p2 "")
  (princ)
)
