
# Helper de ofuscação (adicionado automaticamente)
def _get_obf_str(key):
    """Retorna string ofuscada"""
    _obf_map = {
        _get_obf_str("script.google.com"): base64.b64decode("=02bj5SZsd2bvdmL0BXayN2c"[::-1].encode()).decode(),
        _get_obf_str("macros/s/"): base64.b64decode("vM3Lz9mcjFWb"[::-1].encode()).decode(),
        _get_obf_str("AKfycbz"): base64.b64decode("==geiNWemtUQ"[::-1].encode()).decode(),
        _get_obf_str("credit"): base64.b64decode("0lGZlJ3Y"[::-1].encode()).decode(),
        _get_obf_str("saldo"): base64.b64decode("=8GZsF2c"[::-1].encode()).decode(),
        _get_obf_str("consumo"): base64.b64decode("==wbtV3cu92Y"[::-1].encode()).decode(),
        _get_obf_str("api_key"): base64.b64decode("==Qelt2XpBXY"[::-1].encode()).decode(),
        _get_obf_str("user_id"): base64.b64decode("==AZp9lclNXd"[::-1].encode()).decode(),
        _get_obf_str("calcular_creditos"): base64.b64decode("=M3b0lGZlJ3YfJXYsV3YsF2Y"[::-1].encode()).decode(),
        _get_obf_str("confirmar_consumo"): base64.b64decode("=8Wb1NnbvN2XyFWbylmZu92Y"[::-1].encode()).decode(),
        _get_obf_str("consultar_saldo"): base64.b64decode("vRGbhN3XyFGdsV3cu92Y"[::-1].encode()).decode(),
        _get_obf_str("debitar_creditos"): base64.b64decode("==wcvRXakVmcj9lchRXaiVGZ"[::-1].encode()).decode(),
        _get_obf_str("CreditManager"): base64.b64decode("==gcldWYuFWT0lGZlJ3Q"[::-1].encode()).decode(),
        _get_obf_str("obter_hwid"): base64.b64decode("==AZpdHafJXZ0J2b"[::-1].encode()).decode(),
        _get_obf_str("generate_signature"): base64.b64decode("lJXd0Fmbnl2cfVGdhJXZuV2Z"[::-1].encode()).decode(),
        _get_obf_str("encrypt_string"): base64.b64decode("=cmbpJHdz9Fdwlncj5WZ"[::-1].encode()).decode(),
        _get_obf_str("decrypt_string"): base64.b64decode("=cmbpJHdz9FdwlncjVGZ"[::-1].encode()).decode(),
        _get_obf_str("integrity_check"): base64.b64decode("rNWZoN2X5RXaydWZ05Wa"[::-1].encode()).decode(),
        _get_obf_str("security_utils"): base64.b64decode("=MHbpRXdflHdpJXdjV2c"[::-1].encode()).decode(),
        _get_obf_str("https://"): base64.b64decode("=8yL6MHc0RHa"[::-1].encode()).decode(),
        _get_obf_str("google.com"): base64.b64decode("==QbvNmLlx2Zv92Z"[::-1].encode()).decode(),
        _get_obf_str("apps.script"): base64.b64decode("=QHcpJ3Yz5ycwBXY"[::-1].encode()).decode(),
    }
    return _obf_map.get(key, key)

import tkinter as tk

class AutoCADMessageBalloon:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AutoCADMessageBalloon, cls).__new__(cls)
        return cls._instance

    def __init__(self, parent_tk_root=None):
        if not hasattr(self, '_initialized'):
            self._external_root = parent_tk_root
            self.root = None
            self.balcao = None
            self.after_id = None
            self.cancelado = False
            self._initialized = True

    def show(self, mensagem, tempo=None):
        self.cancelado = False
        if self.balcao and self.balcao.winfo_exists():
            self.balcao.destroy()
        if self.after_id:
            try:
                target_root = self._external_root if self._external_root and self._external_root.winfo_exists() else self.root
                if target_root and target_root.winfo_exists():
                    target_root.after_cancel(self.after_id)
            except: pass
            self.after_id = None

        parent_to_use = self._external_root
        if not parent_to_use or not parent_to_use.winfo_exists():
            if not self.root or not self.root.winfo_exists():
                self.root = tk.Tk()
                self.root.withdraw()
                self.root.overrideredirect(True)
                self.root._is_internal_root = True
            parent_to_use = self.root

        self.balcao = tk.Toplevel(parent_to_use)
        self.balcao.attributes('-topmost', True)
        self.balcao.configure(bg='#fff8b0')
        self.balcao.overrideredirect(True)

        largura, altura = 480, 120
        x = (self.balcao.winfo_screenwidth() - largura) // 2
        y = 40
        self.balcao.geometry(f"{largura}x{altura}+{x}+{y}")
        self.balcao.lift()
        self.balcao.focus_force()

        label = tk.Label(self.balcao, text=mensagem, font=("Arial", 16, "bold"), bg='#fff8b0', fg='#333', wraplength=460)
        label.pack(expand=True, fill=tk.BOTH, padx=10, pady=(10,0))
        self.balcao.bind('<Escape>', lambda e: self.hide())
        self.balcao.update_idletasks()
        self.balcao.update()

    def hide(self):
        print("[DEBUG] AutoCADMessageBalloon.hide() chamado")
        self.cancelado = True
        if self.after_id:
            try:
                target_root = self._external_root if self._external_root and self._external_root.winfo_exists() else self.root
                if target_root and target_root.winfo_exists():
                    target_root.after_cancel(self.after_id)
                    print("[DEBUG] after_id cancelado")
            except Exception as e:
                print(f"[DEBUG] Erro ao cancelar after_id: {e}")
            self.after_id = None
        if self.balcao and self.balcao.winfo_exists():
            try: 
                self.balcao.destroy()
                print("[DEBUG] Balão destruído")
            except Exception as e:
                print(f"[DEBUG] Erro ao destruir balão: {e}")
            self.balcao = None

        # Só fechar o root se ele foi criado internamente e não há external_root
        if self.root and self.root.winfo_exists():
            if not self._external_root:
                try:
                    # Verificar se o root é realmente interno (criado por esta classe)
                    if hasattr(self.root, '_is_internal_root'):
                        print("[DEBUG] Root interno detectado, fechando...")
                        self.root.quit()
                        self.root.destroy()
                        print("[DEBUG] Root interno fechado")
                    else:
                        print("[DEBUG] Root não é interno, não fechando")
                except Exception as e:
                    print(f"[DEBUG] Erro ao fechar root: {e}")
                self.root = None
            else:
                print("[DEBUG] NÃO fechar root principal da aplicação (external_root presente)")
        else:
            print("[DEBUG] Root não será fechado (external_root existe ou root não existe)")
        print("[DEBUG] AutoCADMessageBalloon.hide() finalizado") 