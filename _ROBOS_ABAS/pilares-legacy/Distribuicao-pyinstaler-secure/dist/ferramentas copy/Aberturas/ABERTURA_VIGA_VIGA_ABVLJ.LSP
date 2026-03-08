;-------------------------------------------------------------------------------
; Função: Abertura entre vigas (Novo comando: abv)
; Arquivo: ABERTURA_VIGA_VIGA.LSP
;-------------------------------------------------------------------------------

(defun c:abvlj ()
  (setvar "CMDECHO" 0)

  ;Solicita pontos para desenhar retângulo
  (setq p1 (getpoint "\nSelecione o primeiro ponto do retângulo: "))
  (setq p2 (getpoint p1 "\nSelecione o segundo ponto do retângulo: "))
  
  ;Verifica se os pontos são válidos antes de criar o retângulo
  (if (and p1 p2)
      (progn
          ;Organiza os pontos para garantir consistência independente da direção
          (setq x1 (min (car p1) (car p2)))
          (setq x2 (max (car p1) (car p2)))
          (setq y1 (min (cadr p1) (cadr p2)))
          (setq y2 (max (cadr p1) (cadr p2)))
          
          ;Define os 4 vértices do retângulo
          (setq pt1 (list x1 y1))  ; inferior esquerdo
          (setq pt2 (list x2 y1))  ; inferior direito
          (setq pt3 (list x2 y2))  ; superior direito
          (setq pt4 (list x1 y2))  ; superior esquerdo
          
          ; Zoom focado antes de desenhar o retângulo
          (command "zoom" "c" (polar pt1 (angle pt1 pt3) (/ (distance pt1 pt3) 2)) 5)
          
          ;Cria as linhas horizontais (layer: Painéis)
          (command "layer" "m" "Painéis" "")
          (command "line" pt1 pt2 "")  ; linha inferior
          (command "line" pt4 pt3 "")  ; linha superior
          
          ;Cria as linhas verticais (layer: COTA)
          (command "layer" "m" "COTA" "")
          (command "line" pt1 pt4 "")  ; linha esquerda
          (command "line" pt2 pt3 "")  ; linha direita
          
          ;Cria linha horizontal adicional 7cm abaixo (layer: SARR_2.2X7)
          (setq y_adicional (- (cadr pt1) 7.0))  ; 7cm abaixo da linha inferior
          (setq pt_adicional1 (list x1 y_adicional))
          (setq pt_adicional2 (list x2 y_adicional))
          (command "layer" "m" "SARR_2.2X7" "")
          (command "line" pt_adicional1 pt_adicional2 "")
      )
      (princ "\nPontos inválidos. O comando será cancelado.")
  )
  (princ)
)