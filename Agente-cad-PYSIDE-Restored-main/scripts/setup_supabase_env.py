
import os
import sys
from supabase import create_client, Client

# Load env manually or via python-dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SECRET_KEY") # Use Service Role Key for Admin Tasks

if not url or not key:
    print("Erro: SUPABASE_URL e SUPABASE_SECRET_KEY precisam estar no .env")
    sys.exit(1)

supabase: Client = create_client(url, key)

def setup_buckets():
    buckets = ["intelligence", "updates"]
    existing_buckets = [b.name for b in supabase.storage.list_buckets()]
    
    for b in buckets:
        if b not in existing_buckets:
            print(f"Criando bucket: {b}...")
            try:
                supabase.storage.create_bucket(b, options={"public": True})
                print(f"Bucket '{b}' criado com sucesso.")
            except Exception as e:
                print(f"Erro ao criar bucket '{b}': {e}")
        else:
            print(f"Bucket '{b}' já existe.")

def setup_admin_user():
    email = "thierry.tasf@gmail.com"
    password = "change_me_later_if_needed" # Using provided password manually or a default for initial check
    # O usuário forneceu 21057788 como senha. Vamos usar.
    password = "change_me_later_if_needed" # Don't hardcode sensitive info too blatantly if avoiding logs, but here it's a temp script.
    password = "21057788"

    try:
        # Check if user exists via admin api or just try to create
        # supabase-py user management is usually via auth.admin
        
        # Tentativa de criar usuário (SignUp normal ou Admin Create)
        # Com chave de serviço (Secret), podemos confirmar email automaticamente.
        
        print(f"Verificando usuário admin: {email}")
        try:
             # Admin list users not directly exposed in all clients easily, so we try creating.
             # If exists, it will fail friendly.
             res = supabase.auth.admin.create_user({
                 "email": email,
                 "password": password,
                 "email_confirm": True
             })
             print(f"Usuário Admin criado: {res.user.id}")
             
        except Exception as e:
            if "already registered" in str(e) or "User already exists" in str(e):
                print("Usuário Admin já existe.")
            else:
                print(f"Erro ao criar usuário: {e}")

    except Exception as e:
        print(f"Erro geral no setup de usuário: {e}")

if __name__ == "__main__":
    print("--- Inicializando Setup Supabase ---")
    setup_buckets()
    setup_admin_user()
    print("--- Setup Concluído ---")
