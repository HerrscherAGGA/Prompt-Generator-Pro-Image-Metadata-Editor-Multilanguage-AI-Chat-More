import os
import string
from PIL import Image

def inspect_metadata(image_path):
    print(f"\n{'='*50}")
    print(f"🔍 ANALIZANDO: {os.path.basename(image_path)}")
    print(f"{'='*50}\n")
    
    # ---------------------------------------------------------
    # 1. ANÁLISIS CON PILLOW (Lectura estándar)
    # ---------------------------------------------------------
    print("--- 1. LECTURA CON PILLOW (img.info) ---")
    try:
        with Image.open(image_path) as img:
            print(f"Formato: {img.format} | Tamaño: {img.size} | Modo: {img.mode}")
            
            if img.info:
                for k, v in img.info.items():
                    if k == 'exif':
                        print(f"- [exif]: {len(v)} bytes de datos crudos")
                    else:
                        val_str = str(v)
                        # Truncar si es absurdamente largo para la consola
                        if len(val_str) > 300:
                            val_str = val_str[:300] + "... [TRUNCADO]"
                        print(f"- [{k}]: {val_str}")
            else:
                print("- Pillow no encontró diccionarios en img.info")
            
            # Revisión de EXIF directo
            exif = img.getexif()
            if exif:
                print("\n--- 2. LECTURA EXIF ---")
                for tag_id, data in exif.items():
                    print(f"- Etiqueta [{tag_id}]: {str(data)[:200]}")
    except Exception as e:
        print(f"❌ Error con Pillow: {e}")

    # ---------------------------------------------------------
    # 3. ANÁLISIS EN CRUDO (Modo Aspiradora Binaria)
    # ---------------------------------------------------------
    print("\n--- 3. ESCÁNER BINARIO (Buscando textos ocultos) ---")
    try:
        with open(image_path, 'rb') as f:
            data = f.read()
            
        # Caracteres ASCII imprimibles comunes
        printable = set(bytes(string.printable, 'ascii'))
        
        found_texts = []
        current_string = bytearray()
        
        # Recorremos cada byte del archivo buscando textos largos
        for byte in data:
            if byte in printable:
                current_string.append(byte)
            else:
                # Si encontramos un salto/corte y el texto acumulado es largo...
                if len(current_string) >= 30: 
                    text = current_string.decode('ascii', errors='ignore').strip()
                    
                    # Filtramos basura y nos quedamos solo con lo sospechoso
                    text_lower = text.lower()
                    if "{" in text or "prompt" in text_lower or "steps:" in text or "civitai" in text_lower:
                        found_texts.append(text)
                        
                current_string = bytearray()
                
        if found_texts:
            for idx, txt in enumerate(found_texts):
                print(f"\n[Fragmento Sospechoso {idx+1}]:\n{txt[:1000]}")
        else:
            print("- No se encontraron textos estilo Prompt o JSON en el código binario.")
            
    except Exception as e:
        print(f"❌ Error en escaneo binario: {e}")

if __name__ == "__main__":
    while True:
        # Pide la imagen, quitando comillas por si arrastras el archivo en Windows
        ruta = input("\n🖼️ Arrastra la imagen aquí y presiona Enter (o 'q' para salir):\n> ").strip().strip('"').strip("'")
        
        if ruta.lower() == 'q':
            break
            
        if os.path.exists(ruta):
            inspect_metadata(ruta)
        else:
            print("⚠️ Archivo no encontrado. Asegúrate de arrastrar el archivo correctamente.")