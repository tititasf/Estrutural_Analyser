;-------------------------------------------------------------------------------
; Função: Abertura em pilar à esquerda da viga (Novo comando: abpe_novo)
; Arquivo: ABERTURA_PILAR_VIGA_ESQUERDA.LSP
;-------------------------------------------------------------------------------

(defun c:TRIM2()
  (setvar "CMDECHO" 0)

  ; Solicita pontos para definir a área de seleção
  (setq p1 (getpoint "\nSelecione o primeiro ponto do retângulo: "))
  (setq p2 (getpoint p1 "\nSelecione o segundo ponto do retângulo: "))
  
  ; Verifica se os pontos são válidos
  (if (and p1 p2)
      (progn
          ; Organiza os pontos para garantir consistência
          (setq x1 (min (car p1) (car p2)))
          (setq x2 (max (car p1) (car p2)))
          (setq y1 (min (cadr p1) (cadr p2)))
          (setq y2 (max (cadr p1) (cadr p2)))
          
          ; Define coordenadas base
          (setq fundo_y y1)  ; Y do fundo
          (setq topo_y y2)   ; Y do topo
          (setq esquerda_x x1) ; X da esquerda
          (setq direita_x x2)  ; X da direita

          ; Zoom antes do TRIM
          (command "zoom" "c" (list (/ (+ direita_x esquerda_x) 2.0) (/ (+ topo_y fundo_y) 2.0)) 5)
          ; TRIM 1cm acima da linha do topo do retângulo
          (command "trim" "" "f" (list esquerda_x (+ topo_y 0.1)) (list direita_x (+ topo_y 0.1)) "" "" )

      )
      (princ "\nPontos inválidos. O comando será cancelado.")
  )
  
  (princ)
) 