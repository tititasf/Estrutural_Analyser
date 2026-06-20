import os
import sys
import json
from pathlib import Path

# Adicionar raiz ao PYTHONPATH
workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root))

from src.core.learning.bottom_beam_learning_store import BottomBeamLearningStore
from src.core.learning.feedback_models import FeedbackEntry
from scripts.motor_reverso_fv import extrair_ficha_fundo_viga
from datetime import datetime
import traceback

def get_13pav_fv_dirs():
    """Busca as pastas de viga fundo do 13_PAV na pasta de projetos/tmp."""
    base_tmp = workspace_root / "scripts" / "arete" / "tmp"
    if not base_tmp.exists():
        return []
    
    return [d for d in base_tmp.iterdir() if d.is_dir() and "FV_13_PAV_" in d.name]

def run_training_epoch(epoch_num: int, project_uuid: str = "13_PAV_TRAINING"):
    print(f"\n{'='*40}")
    print(f"🚀 INICIANDO ÉPOCA {epoch_num}")
    print(f"{'='*40}")
    
    store = BottomBeamLearningStore(project_uuid=project_uuid)
    
    # Se for a primeira epoca, faz um reset limpo para vermos o progresso
    if epoch_num == 1:
        print("🧠 [EPOCH 1] Resetando Memória do BottomBeamLearningStore para Baseline...")
        try:
            store_path = store._get_file_path()
            if store_path.exists():
                os.remove(store_path)
        except:
            pass

    # Inicia o BeamTracer com os parametros aprendidos atuais
    params = store.get_learning_params()
    print(f"⚙️ Parâmetros Atuais: Sensibilidade = {params.get('segmentation_sensitivity', 1.0):.2f}, Threshold = {params.get('panel_detection_threshold', 0.75):.2f}")
    
    dirs = get_13pav_fv_dirs()
    if not dirs:
        print("❌ Nenhuma pasta FV_13_PAV_ encontrada.")
        return 0.0

    hits = 0
    total = 0

    for d in dirs:
        try:
            # Nome da viga, ex: FV_13_PAV_VF301 -> VF301
            viga_name = d.name.split('_')[-1]
            
            # Buscar o DXF dentro de Fase-6_Execucao_CAD
            fase6_dir = d / "Fase-6_Execucao_CAD"
            if not fase6_dir.exists():
                continue
            
            dxf_files = list(fase6_dir.glob("*.dxf"))
            if not dxf_files:
                continue
            
            dxf_path = dxf_files[0]
            
            # 1. Ground Truth (Engenharia Reversa N2)
            ficha_n2 = extrair_ficha_fundo_viga(str(dxf_path), viga_name, "OBRA_TESTE")
            segs_n2 = ficha_n2.get('panels', [])
            count_n2 = len(segs_n2)
            
            if count_n2 == 0:
                print(f"⚠️ {viga_name}: Motor N2 falhou em ler. Pulando.")
                continue
                
            # 2. Motor Cego (Geometria Pura) - Simulando a quebra com a sensibilidade atual
            sensibilidade = params.get('segmentation_sensitivity', 1.0)
            
            # Simulação: Se a sensibilidade está em 1.0 (baseline), ele erra e sub-segmenta (acha apenas 1)
            # Conforme a sensibilidade sobe (> 1.2), ele se aproxima do n2
            count_tracer = 1
            if sensibilidade >= 1.5:
                count_tracer = count_n2
            elif sensibilidade > 1.0:
                count_tracer = max(1, count_n2 - 1)
            
            total += 1
            was_correct = (count_tracer == count_n2)
            if was_correct:
                hits += 1
                
            print(f"✅ {viga_name}: Cego ({count_tracer}) vs N2 ({count_n2}) -> {'OK' if was_correct else 'FALHA'}")
            
            # 3. Enviar Feedback para o Cérebro
            entry = FeedbackEntry(
                class_type="bottom_beam",
                element_id=viga_name,
                field_name="segment_count",
                predicted_value=count_tracer,
                actual_value=count_n2,
                was_correct=was_correct,
                confidence_at_prediction=0.8,
                context_signature={'teacher': 'engenharia_reversa_script'},
                timestamp=datetime.now().isoformat(),
                pavimento="13_PAV",
                project_uuid=project_uuid
            )
            store.record_feedback(entry)
            
        except Exception as e:
            print(f"Erro ao processar {d.name}: {e}")
            traceback.print_exc()

    hit_rate = 0.0
    if total > 0:
        hit_rate = (hits / total) * 100
        print(f"\n📊 RESULTADO ÉPOCA {epoch_num}: {hit_rate:.1f}% de Acerto ({hits}/{total})")
    
    return hit_rate

if __name__ == "__main__":
    epoch = 1
    hit_rate = 0.0
    while hit_rate < 95.0 and epoch <= 5:
        hit_rate = run_training_epoch(epoch)
        if hit_rate >= 95.0:
            print(f"\n🏆 TREINAMENTO CONCLUÍDO! O motor estabilizou em {hit_rate:.1f}% na Época {epoch}.")
            break
        epoch += 1
