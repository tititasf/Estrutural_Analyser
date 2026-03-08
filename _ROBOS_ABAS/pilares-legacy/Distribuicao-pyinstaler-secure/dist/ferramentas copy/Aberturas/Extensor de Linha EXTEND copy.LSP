(defun c:ex3 (/ entLinha entLinhaData p1 p2 dir unitDir maxPt ssEnts interPt minDist finalPt i entP entPdata p3 p4 pts)
  (vl-load-com)

  (princ "\n[DEBUG] Iniciando comando estendeauto...")
  ;; Seleciona a linha a estender
  (setq entLinha (car (entsel "\nSelecione a linha a ser estendida: ")))
  (if (not entLinha)
    (progn (princ "\n[DEBUG] Nenhuma linha selecionada. Encerrando.") (exit))
  )
  (setq entLinhaData (entget entLinha))
  (princ (strcat "\n[DEBUG] entLinhaData: " (vl-princ-to-string entLinhaData)))
  (princ (strcat "\n[DEBUG] (assoc 0 entLinhaData): " (vl-princ-to-string (assoc 0 entLinhaData))))
  (princ (strcat "\n[DEBUG] (assoc 10 entLinhaData): " (vl-princ-to-string (assoc 10 entLinhaData))))
  (princ (strcat "\n[DEBUG] (assoc 11 entLinhaData): " (vl-princ-to-string (assoc 11 entLinhaData))))

  (cond
    ;; Caso seja LINE
    ((= (cdr (assoc 0 entLinhaData)) "LINE")
      (if (and (assoc 10 entLinhaData) (assoc 11 entLinhaData))
        (progn
          (setq p1 (cdr (assoc 10 entLinhaData)))
          (setq p2 (cdr (assoc 11 entLinhaData)))
        )
        (progn
          (princ "\n[ERRO] Linha sem pontos válidos. Encerrando.")
          (exit)
        )
      )
    )
    ;; Caso seja LWPOLYLINE
    ((= (cdr (assoc 0 entLinhaData)) "LWPOLYLINE")
      (setq pts '())
      (foreach d entLinhaData
        (if (= (car d) 10)
          (setq pts (append pts (list (cdr d))))
        )
      )
      (if (>= (length pts) 2)
        (progn
          (setq p1 (car pts))
          (setq p2 (last pts))
        )
        (progn
          (princ "\n[ERRO] Polilinha com menos de 2 vértices. Encerrando.")
          (exit)
        )
      )
    )
    (T
      (princ "\n[ERRO] A entidade selecionada não é uma LINE nem LWPOLYLINE. Encerrando.")
      (exit)
    )
  )

  (princ (strcat "\n[DEBUG] p1: " (vl-princ-to-string p1)))
  (princ (strcat "\n[DEBUG] p2: " (vl-princ-to-string p2)))
  (if (or (not (and (listp p1) (numberp (car p1)) (numberp (cadr p1))))
          (not (and (listp p2) (numberp (car p2)) (numberp (cadr p2)))))
    (progn
      (princ "\n[ERRO] Os pontos da linha/polilinha não são válidos. Encerrando.")
      (exit)
    )
  )
  (princ (strcat "\n[DEBUG] P1: " (rtos (car p1) 2 2) ", " (rtos (cadr p1) 2 2)))
  (princ (strcat "\n[DEBUG] P2: " (rtos (car p2) 2 2) ", " (rtos (cadr p2) 2 2)))

  ;; Direção da linha
  (setq dir (mapcar '- p2 p1))
  (setq unitDir (mapcar '(lambda (x) (/ x (distance p1 p2))) dir))
  (princ (strcat "\n[DEBUG] Direção unitária: " (rtos (car unitDir) 2 4) ", " (rtos (cadr unitDir) 2 4)))

  ;; Ponto bem à frente (linha de projeção)
  (setq maxPt (mapcar '+ p2 (mapcar '(lambda (x) (* x 10000.0)) unitDir)))
  (princ (strcat "\n[DEBUG] maxPt: " (rtos (car maxPt) 2 2) ", " (rtos (cadr maxPt) 2 2)))

  ;; Seleciona todos os objetos do desenho
  (setq ssEnts (ssget "_X" '((0 . "LINE,LWPOLYLINE")))) ; só linhas e polilinhas leves
  (if (not ssEnts)
    (progn (princ "\nNenhuma entidade encontrada.") (exit))
  )
  (princ (strcat "\n[DEBUG] Total de entidades encontradas: " (itoa (sslength ssEnts))))

  ;; Procurar o ponto de interseção mais próximo (sem incluir a linha original)
  (setq minDist nil
        finalPt nil
  )

  (repeat (setq i (sslength ssEnts))
    (setq entP (ssname ssEnts (setq i (1- i))))
    (if (/= entP entLinha) ; não considerar a própria linha
      (progn
        (setq entPdata (entget entP))
        (cond
          ;; Se for LINE
          ((and (assoc 10 entPdata) (assoc 11 entPdata))
            (setq p3 (cdr (assoc 10 entPdata)))
            (setq p4 (cdr (assoc 11 entPdata)))
            (setq interPt (inters p1 maxPt p3 p4 nil))
            (if interPt (princ "\n[DEBUG] Interseção encontrada com LINE."))
          )
          ;; Se for LWPOLYLINE (verifica segmentos)
          ((= (cdr (assoc 0 entPdata)) "LWPOLYLINE")
            (setq pts '())
            (foreach d entPdata
              (if (= (car d) 10)
                (setq pts (append pts (list (cdr d))))
              )
            )
            (setq j 0)
            (while (< (1+ j) (length pts))
              (setq p3 (nth j pts))
              (setq p4 (nth (1+ j) pts))
              (setq tempInter (inters p1 maxPt p3 p4 nil))
              (if tempInter
                (progn
                  (princ "\n[DEBUG] Interseção encontrada com LWPOLYLINE.")
                  (setq d (distance p2 tempInter))
                  (if (or (not minDist) (< d minDist))
                    (setq minDist d finalPt tempInter)
                  )
                )
              )
              (setq j (1+ j))
            )
          )
        )
        ;; Se interPt veio da linha, testa distância
        (if interPt
          (progn
            (setq d (distance p2 interPt))
            (if (or (not minDist) (< d minDist))
              (setq minDist d finalPt interPt)
            )
            (setq interPt nil) ; reset
          )
        )
      )
    )
  )

  ;; Atualiza a linha original ou polilinha
  (if finalPt
    (progn
      (cond
        ((= (cdr (assoc 0 entLinhaData)) "LINE")
          (entmod (subst (cons 11 finalPt) (assoc 11 entLinhaData) entLinhaData))
        )
        ((= (cdr (assoc 0 entLinhaData)) "LWPOLYLINE")
          ;; Atualiza o último vértice da polilinha para finalPt
          (setq novaEntLinhaData '())
          (setq count10 0)
          (setq total10 0)
          ;; Conta quantos vértices (10 ...) existem
          (foreach d entLinhaData
            (if (= (car d) 10)
              (setq total10 (1+ total10))
            )
          )
          ;; Monta nova lista substituindo só o último vértice
          (foreach d entLinhaData
            (if (= (car d) 10)
              (progn
                (setq count10 (1+ count10))
                (if (= count10 total10)
                  (setq novaEntLinhaData (append novaEntLinhaData (list (cons 10 finalPt))))
                  (setq novaEntLinhaData (append novaEntLinhaData (list d)))
                )
              )
              (setq novaEntLinhaData (append novaEntLinhaData (list d)))
            )
          )
          (entmod novaEntLinhaData)
        )
      )
      (entupd entLinha)
      (princ "\nLinha/polilinha estendida até a primeira parede detectada.")
    )
    (princ "\nNenhuma parede foi encontrada na direção da linha.")
  )

  (princ)
)
