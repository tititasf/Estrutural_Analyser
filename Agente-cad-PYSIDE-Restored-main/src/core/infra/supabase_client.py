import os
from threading import Lock
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega variáveis do .env explicitamente
load_dotenv()

class SupabaseClient:
    """
    Singleton Thread-Safe para conexão com Supabase.
    Infraestrutura (Adapter).
    """
    _instance: Optional['SupabaseClient'] = None
    _lock: Lock = Lock()
    
    def __init__(self):
        self._client: Optional[Client] = None
        self._url = os.getenv("SUPABASE_URL")
        self._key = os.getenv("SUPABASE_KEY")
        
        if not self._url or not self._key:
            # Em produção/dev inicial, não explodir, mas avisar log
            print("WARNING: Supabase credentials not found in .env")

    @classmethod
    def get_instance(cls) -> 'SupabaseClient':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance._connect()
        return cls._instance

    def _connect(self):
        if self._url and self._key:
            try:
                self._client = create_client(self._url, self._key)
            except Exception as e:
                print(f"CRITICAL: Failed to connect to Supabase: {e}")
                self._client = None
    
    @property
    def client(self) -> Optional[Client]:
        """Acesso direto ao cliente nativo da lib supabase"""
        return self._client
