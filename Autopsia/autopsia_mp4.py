import os
import re
from tkinter import Tk, filedialog

def autopsia_mp4(ruta):
    print(f"\n{'='*60}")
    print(f"🎬 AUTOPSIA DE VIDEO: {os.path.basename(ruta)}")
    print(f"{'='*60}")
    
    try:
        with open(ruta, 'rb') as f:
            data = f.read() # El video pesa poco, la RAM lo aguanta perfecto.
            
        # Limpiar bytes nulos que suelen romper las lecturas de texto en binarios
        data_limpia = data.replace(b'\x00', b'')
        texto_crudo = data_limpia.decode('utf-8', errors='ignore')
        
        print(f"📦 Tamaño del archivo: {len(data) / (1024*1024):.2f} MB")
        print("🔍 Buscando rastros de metadatos de IA...\n")
        
        encontrado = False
        
        # 1. Buscar JSON estándar (Civitai / ComfyUI)
        # Buscamos llaves { } que contengan la palabra "prompt" o "steps"
        matches_json = re.finditer(r'\{[^{]*?"(?:prompt|steps)"[^}]*?\}', texto_crudo, re.IGNORECASE | re.DOTALL)
        for m in matches_json:
            print(f"✅ [¡JSON Encontrado!]:\n{m.group(0)[:500]}...\n")
            encontrado = True
            
        # 2. Buscar formato A1111 (Steps: xx, Sampler: xx)
        matches_a1111 = re.finditer(r'(?:Negative prompt:.*?)?Steps:\s*\d+.*?Sampler:.*?(?:Model hash:.*?)?', texto_crudo, re.IGNORECASE | re.DOTALL)
        for m in matches_a1111:
            print(f"✅ [¡A1111 Encontrado!]:\n{m.group(0)[:500]}...\n")
            encontrado = True

        if not encontrado:
            print("❌ No se encontraron metadatos con formato conocido.")
            print("Explorando cadenas de texto largas (más de 100 caracteres) por si Civitai lo encriptó o usó otro formato...\n")
            
            # Buscar cualquier cadena de texto larga que parezca un prompt
            cadenas = re.findall(r'[a-zA-Z0-9 ,()\[\]:\-_\n]{100,}', texto_crudo)
            if cadenas:
                for i, c in enumerate(cadenas[:3]): # Mostrar solo las primeras 3
                    print(f"--- Cadena Sospechosa {i+1} ---\n{c[:300]}...\n")
            else:
                print("No hay rastros de texto oculto en este video.")
                
    except Exception as e:
        print(f"Error analizando el video: {e}")

if __name__ == "__main__":
    # Ocultar la ventana vacía de Tkinter
    root = Tk()
    root.withdraw()
    
    print("Por favor, selecciona el MP4 original de Civitai...")
    rutas = filedialog.askopenfilenames(
        title="Seleccionar Video", 
        filetypes=[("Videos", "*.mp4 *.webm")]
    )
    
    if rutas:
        for r in rutas:
            autopsia_mp4(r)
    else:
        print("Operación cancelada.")