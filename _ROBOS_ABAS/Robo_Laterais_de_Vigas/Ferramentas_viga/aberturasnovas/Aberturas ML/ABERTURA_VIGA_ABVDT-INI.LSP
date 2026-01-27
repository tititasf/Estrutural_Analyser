;-------------------------------------------------------------------------------
; Função: Abertura em pilar à direita da viga (Espelhado de ABVET-INI)
; Arquivo: ABERTURA_PILAR_VIGA_DIREITA.LSP
;-------------------------------------------------------------------------------

(defun c:ABVDTINI (/ p1 p2 p3 x1 x2 y1 y2 fundo_y topo_y esquerda_x direita_x linha_esquerda_x ret_x1 ret_x2 ret_y1 ret_y2 temp)
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

          ; Desenha linha vertical 7cm à esquerda da parede (Mline)
          ; No ABVET (Dir) desenha Baixo->Cima. Aqui (Esq) desenha Cima->Baixo p/ manter offset interno
          (setq linha_esquerda_x esquerda_x)
          (command "zoom" "c" (list linha_esquerda_x (/ (+ fundo_y topo_y) 2.0)) 5)
          (command "mline" 
                  (list linha_esquerda_x topo_y) 
                  (list linha_esquerda_x fundo_y) 
                  "")
          
          ; [REMOVIDO] Linha vertical de 2.2cm que existia aqui foi eliminada a pedido.
          
          ; Desenha linha horizontal 15cm à ESQUERDA do fundo
          (command "zoom" "c" (list (/ (+ esquerda_x (- esquerda_x 15)) 2.0) fundo_y) 5)
          (command "pline" 
                  (list esquerda_x fundo_y) 
                  (list (- esquerda_x 15) fundo_y) 
                  "")
          
          ; Configura MLINE
          (setvar "CMLSCALE" 2.2)
          (setvar "CMLSTYLE" "SAR3")
          (setvar "CMLJUST" 0) ; Top

          ; Desenha linha MLINE horizontal inferior
          ; Ajuste 1: Posição Y movida 2.2cm para baixo (- fundo_y 2.2)
          ; Ajuste 2: Ponta esquerda encurtada em 3.5cm (-18.5 passa para -15.0)
          (command "zoom" "c" (list (/ (+ esquerda_x (+ direita_x 15)) 2.0) (- fundo_y 3.3)) 5)
          (command "mline" 
                  (list (- direita_x 7) (- fundo_y 2.2)) 
                  (list (- esquerda_x 15.0) (- fundo_y 2.2)) 
                  "")

          ; Zoom antes do TRIM
          ; Zoom antes do TRIM
          ; (command "zoom" "c" (list (/ (+ direita_x (+ direita_x 15)) 2.0) (- fundo_y 1.2)) 5)
          ; TRIM 1cm acima da linha do fundo do retângulo adicional
          ; Espelhado: Trim na direita (Dir - 8)
          ; (command "trim" "" "f" (list (- direita_x 8) (- fundo_y 1.2)) (list (- esquerda_x 1) (- fundo_y 1.2)) "" "" )

          ; Define o layer para "MEIOPONTALETE"
          (command "-layer" "m" "MEIOPONTALETE" "")
          
          ; Desenha retângulo adicional a 15cm à ESQUERDA da abertura (ajustado 3.5cm esq)
          (setq ret_x1 (- esquerda_x 18.5))
          (setq ret_x2 (- ret_x1 7)) ; Largura 7cm agora (pra esquerda)
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

          ; Desenha MLINE (Montante) - Ancora na ESQUERDA (ret_x1) e desenha para Cima (Expande Esquerda)
          ; Espelhado: Desenha Baixo->Cima para expandir p/ esquerda
          (command "mline"
                  (list ret_x1 ret_y2) ; Fundo
                  (list ret_x1 ret_y1) ; Topo
                  ""
          )
          ; Zoom antes do TRIM
          ; Zoom antes do TRIM
          ; (command "zoom" "c" (list (/ (+ ret_x1 (+ ret_x1 15)) 2.0) (- ret_y1 1.2)) 5)
          ; TRIM 1cm acima da linha do fundo do retângulo adicional
          ; (command "trim" "" "f" (list (+ ret_x1 1) (+ ret_y1 1.2)) (list (+ ret_x1 1) (- ret_y1 1.2)) "" "" )
          ; Zoom antes do TRIM
          ; Zoom antes do TRIM
          ; (command "zoom" "c" (list (/ (+ ret_x1 (+ ret_x1 15)) 2.0) (- ret_y1 1.2)) 5)
          ; TRIM 1cm acima da linha do fundo do retângulo adicional
          ; (command "trim" "" "f" (list (+ ret_x1 9) (+ ret_y1 1.2)) (list (+ ret_x1 9) (- ret_y1 1.2)) "" "" )
          
          ; Define o layer para "Hachuracompleto"
          (command "-layer" "m" "Hachuracompleto" "")
          ; Linha horizontal do topo da linha vertical até o X do primeiro ponto
          (command "zoom" "c" (list (/ (+ ret_x1 (car p1)) 2.0) (+ ret_y1 2.2)) 5)
          (command "pline"
                  (list esquerda_x (+ ret_y1 2.2))
                  (list (car p1) (+ ret_y1 2.2))
                  ""
          )

          ; Linha vertical da parede removida conforme solicitado
      )
      (princ "\nPontos inválidos. O comando será cancelado.")
  )
  
  (princ)
)