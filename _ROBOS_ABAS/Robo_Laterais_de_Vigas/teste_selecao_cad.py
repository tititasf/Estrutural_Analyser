import win32com.client
import pythoncom
import time
import sys
import pyautogui
import keyboard

def get_text_content(obj):
    """Tenta obter o conteúdo do texto de várias maneiras possíveis"""
    # Se for MText, usa apenas TextString
    if obj.ObjectName == "AcDbMText":
        try:
            return {'TextString': obj.TextString}
        except:
            return {}
    
    # Se for bloco, tenta obter o valor
    elif obj.ObjectName == "AcDbBlockReference":
        try:
            # Tenta obter atributos primeiro
            for attrib in obj.GetAttributes():
                if attrib.TagString == "VALOR" or attrib.TagString == "TEXTO":
                    return {'Value': attrib.TextString}
            
            # Se não encontrar atributos específicos, tenta outras propriedades
            if hasattr(obj, 'Value'):
                return {'Value': obj.Value}
            elif hasattr(obj, 'PropertyValue'):
                return {'Value': obj.PropertyValue}
        except:
            pass
    
    # Para outros tipos de texto
    methods = [
        ('TextString', lambda: obj.TextString),
        ('Text', lambda: obj.Text),
        ('Value', lambda: obj.Value)
    ]
    
    results = {}
    for method_name, method in methods:
        try:
            value = method()
            if value:
                results[method_name] = value
        except:
            continue
    return results

def get_block_attributes(obj):
    """Obtém todos os atributos de um bloco"""
    attributes = []
    try:
        if hasattr(obj, 'GetAttributes'):
            for attrib in obj.GetAttributes():
                try:
                    attributes.append({
                        'tag': attrib.TagString,
                        'text': attrib.TextString,
                        'invisible': attrib.Invisible,
                        'layer': attrib.Layer
                    })
                except:
                    continue
    except:
        pass
    return attributes

def debug_selecao_cad():
    try:
        # Inicializa o COM
        print("Iniciando COM...")
        pythoncom.CoInitialize()
        
        # Conecta ao AutoCAD
        print("Tentando conectar ao AutoCAD...")
        acad = win32com.client.Dispatch("AutoCAD.Application")
        doc = acad.ActiveDocument
        print(f"Conectado ao documento: {doc.Name}")
        
        # Aguarda seleção do usuário
        print("\nPor favor, selecione um item no AutoCAD...")
        print("Pressione ESC para cancelar")
        
        while True:
            try:
                # Tenta obter a seleção
                selection = doc.Utility.GetEntity()
                
                # Informações básicas do objeto
                obj = selection[0]
                print("\n=== Informações do Objeto ===")
                print(f"Tipo do objeto: {obj.ObjectName}")
                print(f"Handle: {obj.Handle}")
                print(f"Layer: {obj.Layer}")
                
                # Tenta obter o conteúdo do texto de várias maneiras
                text_content = get_text_content(obj)
                if text_content:
                    print("\n=== Conteúdo do Texto ===")
                    for method, content in text_content.items():
                        print(f"{method}: {content}")
                
                # Se for um bloco, obtém informações específicas
                if obj.ObjectName == "AcDbBlockReference":
                    print("\n=== Informações do Bloco ===")
                    try:
                        print(f"Nome do Bloco: {obj.Name}")
                        
                        # Tenta obter o valor diretamente
                        if hasattr(obj, 'Value'):
                            print(f"Valor: {obj.Value}")
                        
                        # Tenta obter propriedades dinâmicas
                        try:
                            for prop in obj.GetDynamicBlockProperties():
                                print(f"Propriedade: {prop.PropertyName} = {prop.Value}")
                        except:
                            pass
                            
                    except:
                        pass
                    
                    # Obtém atributos do bloco
                    attributes = get_block_attributes(obj)
                    if attributes:
                        print("\n=== Atributos do Bloco ===")
                        for attr in attributes:
                            print(f"Tag: {attr['tag']}")
                            print(f"  Texto: {attr['text']}")
                            print(f"  Layer: {attr['layer']}")
                
                # Tenta obter coordenadas
                try:
                    if hasattr(obj, 'InsertionPoint'):
                        print("\n=== Posição ===")
                        coords = obj.InsertionPoint
                        print(f"Ponto de Inserção: X={coords[0]:.2f}, Y={coords[1]:.2f}, Z={coords[2]:.2f}")
                except Exception as e:
                    print(f"Erro ao obter coordenadas: {str(e)}")
                
                # Tenta obter propriedades extras
                try:
                    print("\n=== Propriedades Extras ===")
                    if hasattr(obj, 'Height'):
                        print(f"Altura: {obj.Height}")
                    if hasattr(obj, 'Rotation'):
                        print(f"Rotação: {obj.Rotation}")
                    if hasattr(obj, 'StyleName'):
                        print(f"Estilo: {obj.StyleName}")
                except:
                    pass
                
                # Pergunta se quer continuar
                print("\nPressione 'C' para continuar ou 'ESC' para sair")
                while True:
                    if keyboard.is_pressed('c'):
                        print("\nContinuando...")
                        break
                    elif keyboard.is_pressed('esc'):
                        print("\nEncerrando...")
                        return
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"\nErro ao processar seleção: {str(e)}")
                print("Pressione 'C' para tentar novamente ou 'ESC' para sair")
                while True:
                    if keyboard.is_pressed('c'):
                        break
                    elif keyboard.is_pressed('esc'):
                        return
                    time.sleep(0.1)
    
    except Exception as e:
        print(f"Erro geral: {str(e)}")
    finally:
        print("\nFinalizando COM...")
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    print("=== Teste de Seleção CAD ===")
    print("Este script vai analisar objetos selecionados no CAD")
    print("Instruções:")
    print("1. Selecione um objeto no CAD quando solicitado")
    print("2. Pressione 'C' para continuar com nova seleção")
    print("3. Pressione 'ESC' para sair")
    print("\nIniciando...")
    debug_selecao_cad() 