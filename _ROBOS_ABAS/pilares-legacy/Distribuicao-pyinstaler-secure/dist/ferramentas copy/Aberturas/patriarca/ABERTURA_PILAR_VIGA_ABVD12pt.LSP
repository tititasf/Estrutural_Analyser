;-------------------------------------------------------------------------------
; Função: Abertura em pilar à esquerda da viga (Novo comando: abpe_novo)
; Arquivo: ABERTURA_PILAR_VIGA_ESQUERDA.LSP
;-------------------------------------------------------------------------------

(defun c:abvd12pt ()
  (setvar "CMDECHO" 0)

  ; Solicita pontos para desenhar retângulo
  (setq p1 (getpoint "\nSelecione o primeiro ponto do retângulo: "))
  (setq p2 (getpoint p1 "\nSelecione o segundo ponto do retângulo: "))
  
  ; Cria as linhas com layers específicos
  (criar_linhas_com_layers_abvd12pt p1 p2)
  
  ; Zoom focado na área de trabalho com margem
  (command "zoom" "c" (list (/ (+ (car p1) (car p2)) 2) (/ (+ (cadr p1) (cadr p2)) 2)) 5)
)

(defun criar_linhas_com_layers_abvd12pt (p1 p2 / p3 p4)
  ; Calcula os outros dois pontos do retângulo
  (setq p3 (list (car p2) (cadr p1)))
  (setq p4 (list (car p1) (cadr p2)))
  
  ; Não cria retângulo nem trim, apenas linhas
  ; Zoom center antes de desenhar a parede esquerda
  (command "zoom" "c" (list (/ (+ (car p1) (car p4)) 2) 
                          (/ (+ (cadr p1) (cadr p4)) 2)) "50")
  (command "layer" "s" "Painéis" "")
  (command "line" p1 p4 "")
  (command "layer" "s" "concreto" "")
  
  ; Zoom center antes de desenhar o topo
  (command "zoom" "c" (list (/ (+ (car p1) (car p3)) 2) 
                          (/ (+ (cadr p1) (cadr p3)) 2)) "50")
  (command "-linetype" "s" "HIDDEN" "")  ; Define estilo HIDDEN
  (command "line" p1 p3 "")
  (command "-linetype" "s" "CONTINUOUS" "")  ; Restaura para CONTINUOUS
  
  ; Zoom center antes de desenhar o fundo
  (command "zoom" "c" (list (/ (+ (car p4) (car p2)) 2) 
                          (/ (+ (cadr p4) (cadr p2)) 2)) "50")
  (command "layer" "s" "Painéis" "")
  (command "line" p4 p2 "")
  (command "layer" "s" "concreto" "")
  
  ; Zoom center antes de desenhar a direita
  (command "zoom" "c" (list (/ (+ (car p3) (car p2)) 2) 
                          (/ (+ (cadr p3) (cadr p2)) 2)) "50")
  (command "-linetype" "s" "HIDDEN" "")  ; Define estilo HIDDEN
  (command "line" p3 p2 "")
  (command "-linetype" "s" "CONTINUOUS" "")  ; Restaura para CONTINUOUS
  (princ)
)
