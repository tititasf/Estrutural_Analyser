
import os
import shutil
import logging
import pickle
import json
from pathlib import Path
import re

class ProjectStorageManager:
    """
    Gerencia o armazenamento físico de arquivos e dados do projeto,
    garantindo que a estrutura de pastas reflita a organização lógica
    (Obras > Fases > Classes).
    """

    PHASE_CLASSES = {
        1: ["Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)", "Documentos e Atas de Reunioes(.PDF/.MD)", "Detalhes Estruturais (.DWG/.PDF/.DXF/.MD)"],
        2: ["Estruturais Pavimentos Limpos", "Detalhamentos Específicos"],
        3: ["Estruturais Pavimentos Limpos", "Pilares", "Vigas", "Lajes"],
        4: ["JSON Pilares", "JSON Lajes", "JSON Vigas Laterais", "JSON Vigas Fundo"],
        5: ["Scripts Pilares", "Scripts Lajes", "Scripts Vigas Laterais", "Scripts Vigas Fundo"],
        6: ["DXF Pilares", "DXF Lajes", "DXF Vigas Laterais", "DXF Vigas Fundo"],
        7: ["DXF Consolidado por Pavimento", "DXF Consolidado por Tipo"],
        8: ["DXF Final Validado"]
    }

    # Mapa de nomes de pasta para as fases (sanitizados)
    PHASE_FOLDERS = {
        1: "Fase-1_Ingestao",
        2: "Fase-2_Triagem",
        3: "Fase-3_Interpretacao_Extracao",
        4: "Fase-4_Sincronizacao",
        5: "Fase-5_Geracao_Scripts",
        6: "Fase-6_Execucao_CAD",
        7: "Fase-7_Consolidacao",
        8: "Fase-8_Revisao_Entrega"
    }

    def __init__(self, base_dir=None):
        """
        Inicializa o gerenciador de armazenamento.
        
        Args:
            base_dir (str, optional): Diretório raiz do projeto. 
                                      Se None, tenta deduzir baseado no arquivo atual.
        """
        if base_dir:
            self.base_dir = Path(base_dir).resolve()
        else:
            # Deduzir a partir da localização deste arquivo: src/core/storage/
            # Subir 3 níveis para chegar à raiz: src/core/storage -> src/core -> src -> raiz
            self.base_dir = Path(__file__).resolve().parent.parent.parent.parent
            
        self.storage_root = self.base_dir / "DADOS-OBRAS"
        self._ensure_storage_root()
        logging.info(f"[ProjectStorageManager] Inicializado. Raiz: {self.storage_root}")

    def _ensure_storage_root(self):
        if not self.storage_root.exists():
            self.storage_root.mkdir(parents=True, exist_ok=True)

    def _sanitize_name(self, name):
        """Remove caracteres inválidos para nomes de pasta."""
        # Remover caracteres especiais, manter letras, números, _ e -
        # Substituir espaços por _
        name = name.replace(" ", "_").replace("/", "_").replace(".", "")
        return re.sub(r'[^\w\-]', '', name)

    def get_phase_folder_name(self, phase_id):
        return self.PHASE_FOLDERS.get(phase_id, f"Fase-{phase_id}")

    def get_class_folder_name(self, class_name):
        return self._sanitize_name(class_name)

    def get_work_path(self, work_name):
        return self.storage_root / self._sanitize_name(work_name)

    def initialize_work_structure(self, work_name):
        """
        Cria a estrutura de pastas padrão para uma nova obra.
        """
        work_path = self.get_work_path(work_name)
        
        if not work_path.exists():
            work_path.mkdir(parents=True, exist_ok=True)
            
        for phase_id, classes in self.PHASE_CLASSES.items():
            phase_folder = self.get_phase_folder_name(phase_id)
            phase_path = work_path / phase_folder
            phase_path.mkdir(exist_ok=True)
            
            for class_name in classes:
                class_folder = self.get_class_folder_name(class_name)
                (phase_path / class_folder).mkdir(exist_ok=True)
                
        logging.info(f"[ProjectStorageManager] Estrutura da obra '{work_name}' inicializada em {work_path}")
        return work_path

    def save_file(self, source_file_path, work_name, phase_id, class_name, new_filename=None):
        """
        Salva um arquivo físico na estrutura correta da obra.
        
        Args:
            source_file_path (str): Caminho do arquivo original.
            work_name (str): Nome da obra.
            phase_id (int): ID da fase (1-8).
            class_name (str): Nome da classe/categoria do documento.
            new_filename (str, optional): Novo nome do arquivo. Se None, usa o original.
            
        Returns:
            Path: Caminho absoluto do arquivo salvo.
        """
        source = Path(source_file_path)
        if not source.exists():
            raise FileNotFoundError(f"Arquivo de origem não encontrado: {source}")

        work_path = self.get_work_path(work_name)
        phase_folder = self.get_phase_folder_name(phase_id)
        class_folder = self.get_class_folder_name(class_name)
        
        target_dir = work_path / phase_folder / class_folder
        target_dir.mkdir(parents=True, exist_ok=True)
        
        filename = new_filename if new_filename else source.name
        target_path = target_dir / filename
        
        shutil.copy2(source, target_path)
        logging.info(f"[ProjectStorageManager] Arquivo salvo: {target_path}")
        
        return target_path

    def save_data_object(self, data_object, work_name, phase_id, class_name, identifier):
        """
        Salva um objeto Python complexo (dicionário, lista de objetos, vetores) como arquivo .pkl.
        
        Args:
            data_object (any): Objeto a ser serializado.
            work_name (str): Nome da obra.
            phase_id (int): ID da fase.
            class_name (str): Categoria.
            identifier (str): Nome identificador do objeto (sem extensão).
            
        Returns:
            Path: Caminho absoluto do arquivo .pkl salvo.
        """
        work_path = self.get_work_path(work_name)
        phase_folder = self.get_phase_folder_name(phase_id)
        class_folder = self.get_class_folder_name(class_name)
        
        target_dir = work_path / phase_folder / class_folder
        target_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{identifier}.pkl"
        target_path = target_dir / filename
        
        with open(target_path, 'wb') as f:
            pickle.dump(data_object, f)
            
        logging.info(f"[ProjectStorageManager] Objeto de dados salvo em PKL: {target_path}")
        return target_path

    def load_data_object(self, path):
        """Carrega um objeto de um arquivo .pkl."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")
            
        with open(path, 'rb') as f:
            return pickle.load(f)

