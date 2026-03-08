
import os
from supabase import create_client, Client
from src.core.services.auth_service import AuthService
from src.core.infra.supabase_client import SupabaseClient
from dotenv import load_dotenv

load_dotenv()

def verify_supabase():
    print("--- Verificando Conexão Supabase ---")
    try:
        client = SupabaseClient.get_instance().client
        # Test query to a basic table or just health check
        # Supabase client doesn't have a direct ping, but we can list buckets
        buckets = client.storage.list_buckets()
        print(f"✅ Conexão OK. Buckets encontrados: {[b.name for b in buckets]}")
    except Exception as e:
        print(f"❌ Erro na conexão Supabase: {e}")

def verify_auth_login():
    print("\n--- Verificando Login Admin ---")
    auth_service = AuthService()
    email = "thierry.tasf@gmail.com"
    password = "21057788" # Provided by user
    
    session = auth_service.login(email, password)
    if session:
        print(f"✅ Login bem-sucedido para: {session.user.email}")
        print(f"   ID: {session.user.id}")
        auth_service.logout()
    else:
        print("❌ Falha no login. Verifique as credenciais no script ou no Supabase.")

def verify_tufup():
    print("\n--- Verificando Tufup ---")
    keys_path = os.path.join(os.getcwd(), "keys")
    repo_path = os.path.join(os.getcwd(), "repository")
    
    if os.path.exists(keys_path) and os.path.exists(repo_path):
        print("✅ Estrutura de chaves e repositório Tufup encontrada.")
    else:
        print("❌ Estrutura Tufup incompleta.")

if __name__ == "__main__":
    verify_supabase()
    verify_auth_login()
    verify_tufup()
