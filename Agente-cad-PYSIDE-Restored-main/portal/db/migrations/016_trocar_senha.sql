-- Troca de senha obrigatória no primeiro acesso (2026-09-28).
-- Membro criado com a senha padrão nasce com trocar_senha=1; enquanto a flag
-- estiver ligada, o portal só serve a página de troca de senha (main.py).
ALTER TABLE portal_membros
    ADD COLUMN trocar_senha INTEGER NOT NULL DEFAULT 0 CHECK (trocar_senha IN (0,1));
