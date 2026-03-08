(defun c:app ()
  (setvar "CMDECHO" 0)
  
  ;Solicita pontos para desenhar retângulo
  (setq p1 (getpoint "\nSelecione primeiro ponto do retângulo: "))
  (setq p2 (getpoint p1 "\nSelecione segundo ponto do retângulo: "))
  
  ; Adiciona zoom centralizado entre p1 e p2
  (setq centro (list (/ (+ (car p1) (car p2)) 2.0)
                     (/ (+ (cadr p1) (cadr p2)) 2.0)))
  (command "_.ZOOM" "C" centro 300)
  
  ;Organiza os pontos para garantir consistência independente da direção
  (setq x1 (min (car p1) (car p2)))
  (setq x2 (max (car p1) (car p2)))
  (setq y1 (min (cadr p1) (cadr p2)))
  (setq y2 (max (cadr p1) (cadr p2)))
  
  ;Redefine os pontos organizados
  (setq p1 (list x1 y2))  ;superior esquerdo
  (setq p2 (list x2 y1))  ;inferior direito
  (setq p3 (list x1 y1))  ;inferior esquerdo
  (setq p4 (list x2 y2))  ;superior direito
  
  ;Função auxiliar para criar retângulo
  (defun criar_retangulo (pt1 pt2)
    ;Determina a direção da seleção
    (setq x1 (car pt1))
    (setq y1 (cadr pt1))
    (setq x2 (car pt2))
    (setq y2 (cadr pt2))
    
    ;Desenha o retângulo
    (command "rectangle" pt1 pt2)
    (setq ret (entlast))
    
    ;Cria retângulo interno com offset mínimo
    (command "offset" 0.01 ret "")
    (setq ret_interno (entlast))
    
    ;Cria múltiplas linhas de corte com offsets menores
    (setq offsets '(0.15 0.3 0.45 0.6 1.5 3)) ; offsets menores e mais linhas
    (setq linhas_corte '())
    (foreach off offsets
      (command "offset" off ret "")
      (setq linhas_corte (cons (entlast) linhas_corte))
    )
    
    ;Executa TRIM com área de seleção mais restrita para cada linha de corte
    (foreach linha linhas_corte
      (command "trim" linha "" 
              "f" (list (+ x1 0.1) (+ y1 0.1)) 
                  (list (- x2 0.1) (- y2 0.1)) ""
              "")
    )
    
    ;Apaga área interna com margem ainda menor
    (command "select" "w" 
            (list (+ x1 0.2) (+ y1 0.2))  ; Margem interna mais segura
            (list (- x2 0.2) (- y2 0.2))  ; Margem interna mais segura
            "")
    (command "erase" "p" "")
  )
  
  ;Cria os 4 retângulos
  (criar_retangulo p1 p2)  ;superior esquerdo para inferior direito
  (criar_retangulo p2 p1)  ;inferior direito para superior esquerdo
  (criar_retangulo p3 p4)  ;inferior esquerdo para superior direito
  (criar_retangulo p4 p3)  ;superior direito para inferior esquerdo
  
  ;Limpa variáveis
  (setq p1 nil p2 nil p3 nil p4 nil ret nil ret_interno nil linhas_corte nil)
  (princ)
) 