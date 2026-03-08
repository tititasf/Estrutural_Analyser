;-------------------------------------------------------------------------------
; Função: Abertura em pilar à esquerda da viga (Novo comando: abpe_novo)
; Arquivo: ABERTURA_PILAR_VIGA_ESQUERDA.LSP
;-------------------------------------------------------------------------------

(defun c:ABVETVINI ()
  (setvar "CMDECHO" 0)

  ; Solicita pontos para definir a área de seleção
  (setq p1 (getpoint "\nSelecione o primeiro ponto do retângulo: "))
  (setq p2 (getpoint p1 "\nSelecione o segundo ponto do retângulo: "))
  (setq p3 (getpoint "\nSelecione o terceiro ponto para definir a altura do retângulo adicional: "))
  
  ; Verifica se os pontos são válidos
  (if (and p1 p2 p3)
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

          ; Define o layer para "Painéis"
          (command "-layer" "m" "Painéis" "")
          
          ; Linhas de contorno da seleção removidas (serão geradas pelo script principal)

          ; Define o layer para "SARR_2_2x7"
          (command "-layer" "m" "SARR_2_2x7" "")
          
          ; Configura MLINE
          (setvar "CMLSCALE" 7.0)
          (setvar "CMLSTYLE" "SAR3")
          (setvar "CMLJUST" 0)

          ; Desenha linha vertical 7cm à direita da parede (Mline)
          (setq linha_direita_x direita_x)
          (command "zoom" "c" (list linha_direita_x (/ (+ fundo_y topo_y) 2.0)) 5)
          (command "mline" 
                  (list linha_direita_x fundo_y) 
                  (list linha_direita_x topo_y) 
                  "")
          
          ; Desenha continuação 7cm abaixo da linha vertical
          (command "zoom" "c" (list (/ (+ linha_direita_x (+ linha_direita_x 15)) 2.0) (/ (+ fundo_y (- fundo_y 2.2)) 2.0)) 5)
          (command "pline" 
                  (list (+ linha_direita_x 8) fundo_y) 
                  (list (+ linha_direita_x 8) (- fundo_y 2.2)) 
                  "")
          
          ; Desenha linha horizontal 15cm à direita do fundo
          (command "zoom" "c" (list (/ (+ direita_x (+ direita_x 15)) 2.0) fundo_y) 5)
          (command "pline" 
                  (list direita_x fundo_y) 
                  (list (+ direita_x 15) fundo_y) 
                  "")
          
          ; Configura MLINE
          (setvar "CMLSCALE" 2.2)
          (setvar "CMLSTYLE" "SAR3")
          (setvar "CMLJUST" 0) ; Top

          ; Desenha linha 2.2cm abaixo do fundo (Mline), alinhada ao retangulo (18.5)
          (command "zoom" "c" (list (/ (+ esquerda_x (+ direita_x 15)) 2.0) (- fundo_y 1.1)) 5)
          (command "mline" 
                  (list (+ esquerda_x 7) fundo_y) 
                  (list (+ direita_x 15.0) fundo_y) 
                  "")

          ; Zoom antes do TRIM
          ; Zoom antes do TRIM
          ; (command "zoom" "c" (list (/ (+ direita_x (+ direita_x 15)) 2.0) (- fundo_y 1.2)) 5)
          ; TRIM 1cm acima da linha do fundo do retângulo adicional
          ; (command "trim" "" "f" (list (+ esquerda_x 8) (- fundo_y 1.2)) (list (+ direita_x 1) (- fundo_y 1.2)) "" "" )

          ; Define o layer para "SARR_2_2x7"
          (command "-layer" "m" "MEIOPONTALETE" "")
          

          ; Desenha retângulo adicional a 15cm à direita da abertura (ajustado 3.5cm dir)
          (setq ret_x1 (+ direita_x 18.5))
          (setq ret_x2 (+ ret_x1 7)) ; Largura 7cm agora
          (setq ret_y1 (- topo_y 2.2))
          (setq ret_y2 (cadr p3))
          ; Garante que ret_y1 seja o topo e ret_y2 o fundo
          (if (< ret_y1 ret_y2)
              (progn (setq temp ret_y1) (setq ret_y1 ret_y2) (setq ret_y2 temp))
          )
          ; Zoom na região do retângulo
          (command "zoom" "c" (list (/ (+ ret_x1 ret_x2) 2.0) (/ (+ ret_y1 ret_y2) 2.0)) 5)
          
          ; Configura MLINE para o montante MeioPont
          (setvar "CMLSCALE" 7.0)
          (setvar "CMLSTYLE" "meiopont")
          (setvar "CMLJUST" 0)

          ; Desenha MLINE (Montante) - Ancora na esquerda (ret_x1) e desenha para Baixo (Expande Direita)
          (command "mline"
                  (list ret_x1 ret_y1) ; Topo
                  (list ret_x1 ret_y2) ; Fundo
                  ""
          )
          ; Define o layer para "SARR_2_2x7"
          (command "-layer" "m" "SARR_2_2x7" "")
          ; Linha vertical de 2.2cm acima da parede esquerda do retângulo
          (command "zoom" "c" (list ret_x1 (/ (+ ret_y1 ret_y2) 2.0)) 5)
          (command "pline"
                  (list ret_x1 ret_y1)
                  (list ret_x1 (+ ret_y1 2.2))
                  ""
          )
          ; Zoom antes do TRIM
          ; Zoom antes do TRIM
          ; (command "zoom" "c" (list (/ (+ ret_x1 (+ ret_x1 15)) 2.0) (- ret_y1 1.2)) 5)
          ; TRIM 1cm acima da linha do fundo do retângulo adicional
          ; (command "trim" "" "f" (list (- ret_x1 1) (+ ret_y1 1.2)) (list (- ret_x1 1) (- ret_y1 1.2)) "" "" )
          ; Zoom antes do TRIM
          ; Zoom antes do TRIM
          ; (command "zoom" "c" (list (/ (+ ret_x1 (+ ret_x1 15)) 2.0) (- ret_y1 1.2)) 5)
          ; TRIM 1cm acima da linha do fundo do retângulo adicional
          ; (command "trim" "" "f" (list (- ret_x1 9) (+ ret_y1 1.2)) (list (- ret_x1 9) (- ret_y1 1.2)) "" "" )
          ; Define o layer para "SARR_2_2x7"
          (command "-layer" "m" "Hachuracompleto" "")
          ; Linha horizontal do topo da linha vertical até o X do primeiro ponto
          (command "zoom" "c" (list (/ (+ ret_x1 (car p1)) 2.0) (+ ret_y1 2.2)) 5)
          (command "pline"
                  (list direita_x (+ ret_y1 2.2))
                  (list (car p1) (+ ret_y1 2.2))
                  ""
          )

          ; Linha vertical da parede removida conforme solicitado
      )
      (princ "\nPontos inválidos. O comando será cancelado.")
  )
  
  (princ)
) 