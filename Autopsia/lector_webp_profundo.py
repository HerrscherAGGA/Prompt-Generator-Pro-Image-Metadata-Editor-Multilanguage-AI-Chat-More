import struct
import os
import string
from tkinter import Tk, filedialog

def extraer_texto_legible(payload):
    """Extrae cualquier cosa que parezca texto dentro del código binario."""
    # Quitamos los bytes nulos que suele poner EXIF (UNICODE\x00)
    limpio_utf16 = payload.replace(b'\x00', b'')
    
    try:
        # Intentamos decodificar como ASCII/UTF-8
        texto = limpio_utf16.decode('utf-8', errors='ignore')
        # Filtramos solo caracteres imprimibles para no ver basura binaria
        imprimibles = set(string.printable)
        texto_filtrado = ''.join(filter(lambda x: x in imprimibles, texto))
        
        # Buscar palabras clave de IA para resaltar
        if "prompt" in texto_filtrado.lower() or "steps:" in texto_filtrado.lower():
            return f"\n      [!] METADATOS DE IA ENCONTRADOS:\n      {texto_filtrado[:500]}..."
        elif len(texto_filtrado.strip()) > 5:
            return f"\n      Texto encontrado: {texto_filtrado[:200]}..."
    except:
        pass
    return ""

def analizar_webp(ruta_archivo):
    print(f"\n{'='*60}")
    print(f"🔍 AUTOPSIA BINARIA: {os.path.basename(ruta_archivo)}")
    print(f"{'='*60}")
    
    with open(ruta_archivo, 'rb') as f:
        data = f.read()
        
    if data[0:4] != b'RIFF' or data[8:12] != b'WEBP':
        print("❌ El archivo no es un contenedor WebP/RIFF válido.")
        return
        
    tamaño_total = struct.unpack_from('<I', data, 4)[0]
    print(f"📦 Contenedor: RIFF | Tamaño: {tamaño_total / 1024:.2f} KB | Tipo: WEBP\n")
    
    offset = 12
    num_chunk = 1
    
    while offset < len(data):
        if offset + 8 > len(data):
            break
            
        # Leer cabecera del bloque (4 bytes nombre, 4 bytes tamaño)
        tag = data[offset:offset+4].decode('ascii', errors='replace')
        size = struct.unpack_from('<I', data, offset+4)[0]
        
        print(f"  [{num_chunk}] Bloque: {tag} | Tamaño: {size} bytes")
        
        # --- ANÁLISIS PROFUNDO DE BLOQUES CLAVE ---
        payload_start = offset + 8
        payload_end = payload_start + size
        payload = data[payload_start:payload_end]
        
        # 1. Analizar VP8X (El cerebro del WebP, indica si es animado o tiene EXIF)
        if tag == 'VP8X':
            flags = payload[0]
            es_animado = bool(flags & 0x02)
            tiene_exif = bool(flags & 0x08)
            tiene_xmp = bool(flags & 0x04)
            print(f"      -> Flags VP8X: Animado={es_animado}, EXIF={tiene_exif}, XMP={tiene_xmp}")
            
        # 2. Analizar ANIM (Configuración de la animación)
        elif tag == 'ANIM':
            bg_color = struct.unpack_from('<I', payload, 0)[0]
            loop_count = struct.unpack_from('<H', payload, 4)[0]
            print(f"      -> Config Animación: Loops={loop_count} (0=infinito)")
            
        # 3. Analizar EXIF o XMP (Donde se esconde la metadata)
        elif tag in ['EXIF', 'XMP ']:
            texto_oculto = extraer_texto_legible(payload)
            if texto_oculto:
                print(texto_oculto)
            else:
                print("      -> [Advertencia] El bloque existe pero parece estar vacío o cifrado.")
        
        # Avanzar al siguiente bloque (size + padding si es impar)
        offset += 8 + size + (size % 2)
        num_chunk += 1
        
    print(f"\n{'='*60}")

if __name__ == "__main__":
    # Ocultar la ventana vacía de Tkinter
    root = Tk()
    root.withdraw()
    
    print("Por favor, selecciona un archivo WebP para analizar...")
    rutas = filedialog.askopenfilenames(
        title="Selecciona archivos WebP", 
        filetypes=[("WebP Files", "*.webp")]
    )
    
    if rutas:
        for ruta in rutas:
            analizar_webp(ruta)
    else:
        print("Operación cancelada.")