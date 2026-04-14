"""
╔══════════════════════════════════════════════════════════════╗
║         AUTOPSIA FORENSE — CAJA DE PRUEBAS v3.1              ║
║  SIN LÍMITES — lee el archivo completo siempre               ║
║                                                              ║
║  Dependencias: pip install Pillow                            ║
║  Opcional:     ffprobe (FFmpeg) + exiftool en PATH           ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import re
import json
import struct
import shutil
import hashlib
import subprocess
import zlib
from datetime import datetime
from pathlib import Path
from tkinter import Tk, filedialog

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    PILLOW_OK = True
except ImportError:
    PILLOW_OK = False


# ══════════════════════════════════════════════════════════════
#  UTILIDADES
# ══════════════════════════════════════════════════════════════

EXTS_IMAGEN = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.gif'}

def guardar_txt(ruta_base, contenido):
    out = ruta_base + "_autopsia.txt"
    with open(out, 'w', encoding='utf-8') as f:
        f.write(contenido)
    return out

def guardar_json(ruta_base, sufijo, data):
    out = ruta_base + f"_{sufijo}.json"
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return out

def guardar_json_raw(ruta_base, sufijo, texto):
    out = ruta_base + f"_{sufijo}.json"
    with open(out, 'w', encoding='utf-8') as f:
        f.write(texto)
    return out

def seccion(titulo):
    return f"\n{'═'*70}\n  {titulo}\n{'═'*70}\n"

def sub(titulo):
    sep = '─' * max(0, 60 - len(titulo))
    return f"\n── {titulo} {sep}\n"


# ══════════════════════════════════════════════════════════════
#  MÓDULO A — INFO BÁSICA DEL ARCHIVO
# ══════════════════════════════════════════════════════════════

def info_basica(ruta):
    stat = os.stat(ruta)
    with open(ruta, 'rb') as f:
        magic = f.read(16)
        f.seek(0)
        raw = f.read()
    return raw, {
        "Nombre"      : os.path.basename(ruta),
        "Tamaño"      : f"{stat.st_size:,} bytes ({stat.st_size / 1048576:.2f} MB)",
        "Modificado"  : datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        "MD5"         : hashlib.md5(raw).hexdigest(),
        "SHA1"        : hashlib.sha1(raw).hexdigest(),
        "Magic (hex)" : magic.hex(' ').upper(),
    }


# ══════════════════════════════════════════════════════════════
#  MÓDULO B — FFPROBE
# ══════════════════════════════════════════════════════════════

def run_ffprobe(ruta):
    import sys, os, subprocess, json, shutil
    base_dir = os.path.dirname(os.path.abspath(__file__))
    exe_path = os.path.join(base_dir, "tools", "ffprobe.exe")
    
    if not os.path.exists(exe_path):
        exe_path = shutil.which("ffprobe")
        if not exe_path:
            return None, "ffprobe no encontrado en tools/ ni en PATH"

    cmd = [exe_path, "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", "-show_chapters", ruta]
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, creationflags=flags)
        return json.loads(r.stdout), None
    except Exception as e:
        return None, str(e)

def formatear_ffprobe(data):
    lineas = []
    fmt = data.get("format", {})
    if fmt:
        lineas.append(f"Contenedor : {fmt.get('format_long_name', fmt.get('format_name', '?'))}")
        dur = float(fmt.get("duration", 0))
        lineas.append(f"Duración   : {int(dur//60):02d}:{dur%60:06.3f}s")
        lineas.append(f"Bitrate    : {int(fmt.get('bit_rate', 0))//1000} kbps")
        tags = fmt.get("tags", {})
        if tags:
            lineas.append("\nTAGS DEL CONTENEDOR:")
            for k, v in tags.items():
                lineas.append(f"  {k:<30}: {v}")

    for s in data.get("streams", []):
        tipo = s.get("codec_type", "?").upper()
        lineas.append(f"\nSTREAM #{s.get('index', 0)} [{tipo}]")
        lineas.append(f"  Codec  : {s.get('codec_long_name', s.get('codec_name', '?'))}")
        if tipo == "VIDEO":
            lineas.append(f"  Res    : {s.get('width','?')}x{s.get('height','?')}")
            try:
                n, d = s.get("r_frame_rate", "0/1").split("/")
                lineas.append(f"  FPS    : {round(int(n)/int(d), 3)}")
            except Exception:
                pass
            lineas.append(f"  Pixfmt : {s.get('pix_fmt','?')}")
            lineas.append(f"  Color  : {s.get('color_space','?')} / {s.get('color_transfer','?')}")
        elif tipo == "AUDIO":
            lineas.append(f"  Hz     : {s.get('sample_rate','?')}")
            lineas.append(f"  Ch     : {s.get('channels','?')} ({s.get('channel_layout','?')})")
        stags = s.get("tags", {})
        if stags:
            lineas.append("  TAGS:")
            for k, v in stags.items():
                lineas.append(f"    {k:<28}: {v}")

    chs = data.get("chapters", [])
    if chs:
        lineas.append(f"\nCAPÍTULOS ({len(chs)}):")
        for ch in chs:
            t = float(ch.get("start_time", 0))
            lineas.append(f"  {int(t//60):02d}:{t%60:05.2f}  {ch.get('tags',{}).get('title','')}")

    return "\n".join(lineas)


# ══════════════════════════════════════════════════════════════
#  MÓDULO C — EXIFTOOL
# ══════════════════════════════════════════════════════════════

def run_exiftool(ruta):
    import sys, os, subprocess, json, shutil
    base_dir = os.path.dirname(os.path.abspath(__file__))
    exe_path = os.path.join(base_dir, "tools", "exiftool.exe")
    
    if not os.path.exists(exe_path):
        exe_path = shutil.which("exiftool")
        if not exe_path:
            return None, "exiftool no encontrado en tools/ ni en PATH"

    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        r = subprocess.run([exe_path, "-j", "-G", "-a", "-u", ruta],
                           capture_output=True, text=True, timeout=120, creationflags=flags)
        data = json.loads(r.stdout)
        return data[0] if data else {}, None
    except Exception as e:
        return None, str(e)


# ══════════════════════════════════════════════════════════════
#  MÓDULO D — PILLOW + EXIF UserComment
# ══════════════════════════════════════════════════════════════

def parse_exif_user_comment(exif_bytes):
    if not exif_bytes:
        return None
    try:
        start = 6 if exif_bytes.startswith(b'Exif\x00\x00') else 0
        tiff  = exif_bytes[start:]
        if len(tiff) < 8:
            return None

        endian = '<' if tiff.startswith(b'II') else ('>' if tiff.startswith(b'MM') else None)
        if not endian:
            return None

        def get16(o): return struct.unpack_from(endian + 'H', tiff, o)[0]
        def get32(o): return struct.unpack_from(endian + 'I', tiff, o)[0]

        if get16(2) != 0x002A:
            return None

        def parse_ifd(off):
            if off + 2 > len(tiff):
                return {}
            tags = {}
            for i in range(get16(off)):
                e = off + 2 + i * 12
                if e + 12 > len(tiff):
                    break
                tags[get16(e)] = (get16(e+2), get32(e+4), get32(e+8), e)
            return tags

        ifd0     = parse_ifd(get32(4))
        if 0x8769 not in ifd0:
            return None
        exif_ifd = parse_ifd(ifd0[0x8769][2])
        if 0x9286 not in exif_ifd:
            return None

        type_, cnt, val_off, entry_off = exif_ifd[0x9286]
        val = tiff[entry_off+8 : entry_off+8+cnt] if cnt <= 4 else tiff[val_off : val_off+cnt]
        if len(val) < 8:
            return None

        prefix, payload = val[:8], val[8:]
        if prefix.startswith(b'UNICODE\x00'):
            ci  = sum(1 for i in range(1, min(40, len(payload)), 2) if payload[i] == 0)
            cp  = sum(1 for i in range(0, min(40, len(payload)), 2) if payload[i] == 0)
            enc = 'utf-16le' if ci >= cp else 'utf-16be'
            return payload.decode(enc, errors='ignore').replace('\x00', '').strip()
        elif prefix.startswith(b'ASCII\x00'):
            return payload.decode('ascii', errors='ignore').replace('\x00', '').strip()
        else:
            return payload.decode('utf-8', errors='ignore').replace('\x00', '').strip()
    except Exception:
        return None

def analizar_pillow(ruta):
    if not PILLOW_OK:
        return {}, "Pillow no instalado"

    resultado = {}
    ext = Path(ruta).suffix.lower()

    try:
        with Image.open(ruta) as img:
            resultado["formato"]    = img.format
            resultado["resolución"] = f"{img.size[0]}x{img.size[1]}"
            resultado["modo"]       = img.mode
            if hasattr(img, 'n_frames'):
                resultado["frames"] = img.n_frames

            chunks = {}
            for k, v in img.info.items():
                if k == 'exif':
                    continue
                chunks[k] = str(v)
            if chunks:
                resultado["chunks"] = chunks

            exif = img.getexif()
            if exif:
                exif_legible = {}
                for tag_id, value in exif.items():
                    nombre = TAGS.get(tag_id, f"Tag_{tag_id}")
                    exif_legible[nombre] = str(value)
                resultado["exif"] = exif_legible

                gps_ifd = exif.get_ifd(0x8825)
                if gps_ifd:
                    resultado["gps"] = {
                        GPSTAGS.get(t, f"GPS_{t}"): str(v)
                        for t, v in gps_ifd.items()
                    }

            if 'exif' in img.info:
                uc = parse_exif_user_comment(img.info['exif'])
                if uc:
                    resultado["user_comment"] = uc
                else:
                    raw_exif = img.info['exif']
                    m = re.search(b'UNICODE\x00(.*)', raw_exif, re.DOTALL)
                    if m:
                        payload = m.group(1)
                        ci  = sum(1 for i in range(1, min(40, len(payload)), 2) if payload[i] == 0)
                        cp  = sum(1 for i in range(0, min(40, len(payload)), 2) if payload[i] == 0)
                        enc = 'utf-16le' if ci >= cp else 'utf-16be'
                        uc2 = payload.decode(enc, errors='ignore').replace('\x00', '').strip()
                        if uc2:
                            resultado["user_comment_fallback"] = uc2
                    elif b"Steps:" in raw_exif:
                        resultado["user_comment_raw"] = (
                            raw_exif.decode('utf-8', errors='ignore').replace('\x00', '').strip()
                        )

            if ext in ('.jpg', '.jpeg'):
                with open(ruta, 'rb') as fj:
                    jdata = fj.read()
                off = 2
                markers_extra = []
                while off < len(jdata) - 4:
                    if jdata[off] != 0xFF:
                        break
                    marker = jdata[off+1]
                    size   = struct.unpack_from('>H', jdata, off+2)[0]
                    if marker == 0xE1:
                        seg = jdata[off+4 : off+2+size]
                        if seg.startswith(b'Exif\x00\x00'):
                            uc = parse_exif_user_comment(seg)
                            if uc:
                                resultado["jpeg_user_comment"] = uc
                        elif seg[:20].startswith((b'http://ns.adobe.com', b'<?xpacket')):
                            resultado["jpeg_xmp_raw"] = seg.decode('utf-8', errors='ignore')
                    elif marker in (0xE2, 0xED):
                        markers_extra.append({"marker": f"0xFF{marker:02X}", "size": size})
                    off += 2 + size
                if markers_extra:
                    resultado["jpeg_markers_extra"] = markers_extra

    except Exception as e:
        resultado["error"] = str(e)

    return resultado, None


# ══════════════════════════════════════════════════════════════
#  MÓDULO E — BLOQUES WEBP
# ══════════════════════════════════════════════════════════════

def analizar_webp(ruta, raw_bytes):
    data = raw_bytes
    if not (data[:4] == b'RIFF' and data[8:12] == b'WEBP'):
        return {"error": "No es WebP válido"}

    bloques = []
    offset  = 12
    while offset < len(data) - 8:
        try:
            tag     = data[offset:offset+4].decode('ascii', errors='replace')
            size    = struct.unpack_from('<I', data, offset+4)[0]
            payload = data[offset+8 : offset+8+size]
            bloque  = {"tag": tag, "size": size, "offset": offset}

            if tag == 'VP8X':
                flags = payload[0]
                bloque["flags"] = {
                    "animated": bool(flags & 0x02),
                    "exif"    : bool(flags & 0x08),
                    "xmp"     : bool(flags & 0x04),
                    "alpha"   : bool(flags & 0x10),
                }
                w = struct.unpack_from('<I', payload[4:7] + b'\x00', 0)[0] + 1
                h = struct.unpack_from('<I', payload[7:10] + b'\x00', 0)[0] + 1
                bloque["canvas"] = f"{w}x{h}"

            elif tag in ('EXIF', 'XMP ', 'XMP\x00'):
                bloque["contenido"] = payload.replace(b'\x00', b'').decode('utf-8', errors='ignore')
                uc = parse_exif_user_comment(payload)
                if uc:
                    bloque["user_comment"] = uc

            elif tag == 'ICCP':
                bloque["nota"] = f"Perfil ICC ({size} bytes)"

            elif tag == 'ANIM':
                bg    = struct.unpack_from('<I', payload, 0)[0]
                loops = struct.unpack_from('<H', payload, 4)[0]
                bloque["bg_color"] = f"#{bg:08X}"
                bloque["loops"]    = loops or "infinito"

            bloques.append(bloque)
            offset += 8 + size + (size % 2)
        except Exception as e:
            bloques.append({"error": str(e), "offset": offset})
            break

    return {"bloques": bloques}


# ══════════════════════════════════════════════════════════════
#  MÓDULO F — ASPIRADORA BINARIA (sin límites)
# ══════════════════════════════════════════════════════════════

PATRONES_IA = [
    (re.compile(r'\{\s*"[^"]+"\s*:\s*\{\s*"(?:class_type|inputs|prompt|workflow)"\s*:', re.I), "ComfyUI (graph)"),
    (re.compile(r'\{\s*"(?:prompt|workflow|parameters|metadata)"\s*:', re.I),                  "ComfyUI / JSON genérico"),
    (re.compile(r'Steps:\s*\d+.*?Sampler:\s*\w+', re.I | re.S),                               "AUTOMATIC1111"),
    (re.compile(r'Negative\s+prompt:', re.I),                                                 "A1111 negative"),
    (re.compile(r'<lora:[^>]+>', re.I),                                                       "LoRA tag"),
    (re.compile(r'"cfg_scale"\s*:\s*[\d.]+', re.I),                                           "cfg_scale"),
    (re.compile(r'"seed"\s*:\s*\d{5,}', re.I),                                                "Seed"),
    (re.compile(r'"noise_schedule"\s*:', re.I),                                               "NovelAI"),
    (re.compile(r'"v4_prompt"\s*:', re.I),                                                    "NovelAI v4"),
    (re.compile(r'"sui_image_params"\s*:', re.I),                                             "SwarmUI"),
    (re.compile(r'--(?:ar|v|q|style|s|niji)\s+[\w.]+'),                                       "MidJourney flag"),
    (re.compile(r'Job ID:\s*[0-9a-f\-]{36}', re.I),                                           "MidJourney Job ID"),
    (re.compile(r'"invoke_ai"\s*:', re.I),                                                    "InvokeAI"),
    (re.compile(r'clip[\s_\-]?skip', re.I),                                                   "CLIP skip"),
    (re.compile(r'ecosystem.*?civitai', re.I | re.S),                                         "Civitai"),
]

def extraer_json_de_texto(texto, ruta_base, contador):
    hallazgos = []

    patrones_busqueda = [
        (re.compile(r'\{\s*"[^"]+"\s*:\s*\{\s*"(?:class_type|inputs|prompt|workflow)"\s*:', re.I), False),
        (re.compile(r'\{\s*"(?:prompt|workflow|parameters|metadata)"\s*:', re.I), False),
        (re.compile(r'\{\s*\\"[a-zA-Z0-9_-]+\\"\s*:\s*\{\s*\\"(?:class_type|inputs|prompt|workflow)\\"\s*:', re.I), True),
        (re.compile(r'\{\s*\\"(?:prompt|workflow)\\"\s*:', re.I), True),
    ]

    seen   = set()
    matches = []
    for pat, escaped in patrones_busqueda:
        for m in pat.finditer(texto):
            if m.start() not in seen:
                seen.add(m.start())
                matches.append((m.start(), escaped))
    matches.sort()

    for start, is_escaped in matches:
        candidate = texto[start:]
        llaves  = 0
        in_q    = False
        end_idx = -1
        i       = 0

        while i < len(candidate):
            ch = candidate[i]
            if not is_escaped:
                if ch == '\\':
                    i += 2
                    continue
                if ch == '"':
                    in_q = not in_q
                if not in_q:
                    if ch == '{': llaves += 1
                    elif ch == '}':
                        llaves -= 1
                        if llaves == 0: end_idx = i; break
            else:
                if ch == '\\' and i + 1 < len(candidate):
                    nc = candidate[i+1]
                    if nc == '"':
                        in_q = not in_q
                        i += 2; continue
                    elif nc == '\\':
                        i += 2; continue
                if not in_q:
                    if ch == '{': llaves += 1
                    elif ch == '}':
                        llaves -= 1
                        if llaves == 0: end_idx = i; break
            i += 1

        if end_idx == -1: continue

        raw_json = candidate[:end_idx+1]
        contador[0] += 1
        idx = contador[0]

        try:
            limpio = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', raw_json)
            if is_escaped: limpio = json.loads('"' + limpio + '"')
            parsed = json.loads(limpio, strict=False)
            
            # --- NUEVO: RESUMEN HUMANO (Mini-Traductor) ---
            json_str_limpio = json.dumps(parsed, ensure_ascii=False)
            resumen = []
            
            # 1. Pescar Prompts (Ignorando basura y archivos)
            textos = re.findall(r'"(?:text|text_g|text_l|text_prompt|wildcard_text|populated_text|string|value)"\s*:\s*"([^"]+)"', json_str_limpio, re.IGNORECASE)
            validos = [t for t in textos if len(t) > 15 and not t.lower().endswith(('.safetensors', '.pth', '.mp4', '.webp'))]
            if validos:
                resumen.append("      📝 TEXTOS / PROMPTS DETECTADOS:")
                for t in set(validos): resumen.append(f"        - {t[:250]}...")
                    
            # 2. Pescar LORAs
            loras = re.findall(r'"(?:lora_name|lora)"\s*:\s*"([^"]+\.(?:safetensors|ckpt|pt))"', json_str_limpio, re.IGNORECASE)
            if loras:
                resumen.append("      🧩 LORAS DETECTADOS:")
                for l in set(loras): resumen.append(f"        - {os.path.basename(l)}")
                    
            # 3. Pescar Modelos
            modelos = re.findall(r'"(?:ckpt_name|unet_name)"\s*:\s*"([^"]+\.(?:safetensors|gguf|ckpt))"', json_str_limpio, re.IGNORECASE)
            if modelos:
                resumen.append("      🧠 MODELOS DETECTADOS:")
                for m in set(modelos): resumen.append(f"        - {os.path.basename(m)}")
            
            resumen_final = "\n".join(resumen) if resumen else "      (No se encontraron prompts legibles)"
            # -----------------------------------------------

            ruta_j = guardar_json(ruta_base, f"JSON_{idx:02d}", parsed)
            hallazgos.append({
                "indice" : idx,
                "estado" : "OK (Guardado en archivo)",
                "archivo": os.path.basename(ruta_j),
                "preview": resumen_final  # ¡Reemplazamos el preview basura por el resumen útil!
            })
        except json.JSONDecodeError as e:
            ruta_j = guardar_json_raw(ruta_base, f"JSON_{idx:02d}_RAW", raw_json)
            hallazgos.append({
                "indice" : idx,
                "estado" : f"ERROR ({e})",
                "archivo": os.path.basename(ruta_j),
                "preview": raw_json[:200] + "..."
            })

    return hallazgos

def aspiradora_binaria(ruta, ruta_base, raw_bytes):
    resultado = {
        "json_encontrados"   : [],
        "patrones_ia"        : [],
        "a1111_raw"          : [],
        "cadenas_sospechosas": [],
    }

    texto = raw_bytes.replace(b'\x00', b'').decode('utf-8', errors='ignore')

    if "widget_ue_connectable" in texto:
        texto = texto.replace('"widget_ue_connectable"', '"_ue_junk"')

    contador = [0]

    # ── JSON completos ───────────────────────────────────────────────────────
    resultado["json_encontrados"] = extraer_json_de_texto(texto, ruta_base, contador)

    # ── Patrones de IA ───────────────────────────────────────────────────────
    ya_vistos = set()
    for patron, nombre in PATRONES_IA:
        for m in patron.finditer(texto):
            ctx = texto[max(0, m.start()-2000) : min(len(texto), m.end()+5000)].strip()
            key = ctx[:80]
            if key in ya_vistos:
                continue
            ya_vistos.add(key)
            resultado["patrones_ia"].append({"tipo": nombre, "contexto": ctx})

    # ── A1111 explícito ──────────────────────────────────────────────────────
    a1111_re = re.compile(r'Steps:\s*\d+.*?Sampler:\s*[^\n,]+', re.S | re.I)
    for m in a1111_re.finditer(texto):
        ctx = texto[max(0, m.start()-2000) : min(len(texto), m.end()+3000)].strip()
        if not any(ctx[:80] in p["contexto"] for p in resultado["patrones_ia"]):
            resultado["a1111_raw"].append(ctx)

    # ── Fallback: cadenas largas legibles ────────────────────────────────────
    if not any([resultado["json_encontrados"], resultado["patrones_ia"], resultado["a1111_raw"]]):
        cadenas = re.findall(r'[a-zA-Z0-9 ,()\[\]:\-_\'\"\.]{80,}', texto)
        validas = [c.strip() for c in cadenas if c.count(' ') > 5 and len(set(c)) > 15]
        resultado["cadenas_sospechosas"] = validas[:20]

    return resultado


# ══════════════════════════════════════════════════════════════
#  MÓDULO G — EXTRACCIÓN EXTREMA (Zlib, Post-EOF, XMP)
# ══════════════════════════════════════════════════════════════

def extraccion_extrema(raw_bytes, ruta_base):
    resultados = {
        "zlib_oculto": [],
        "post_eof": [],
        "xmp_crudo": []
    }
    
    ext = Path(ruta_base).suffix.lower()
    es_video = ext in ['.mp4', '.mkv', '.webm', '.avi', '.mov']
    
    # ── 1. FUERZA BRUTA ZLIB (Prompts comprimidos) ──────────────────────────
    # Cabeceras mágicas típicas de zlib: 78 01 (baja), 78 9C (default), 78 DA (máxima)
    for cabecera in [b'\x78\x9c', b'\x78\xda', b'\x78\x01']:
        offset = 0
        while True:
            idx = raw_bytes.find(cabecera, offset)
            if idx == -1: break
            
            try:
                # Intentamos descomprimir todo lo que haya desde esa cabecera
                descomprimido = zlib.decompress(raw_bytes[idx:])
                texto_desc = descomprimido.decode('utf-8', errors='ignore')
                
                # Filtramos para no guardar basura: ¿Parece un prompt o un JSON?
                if "{" in texto_desc or "prompt" in texto_desc.lower() or "steps" in texto_desc.lower():
                    resultados["zlib_oculto"].append({
                        "offset": idx,
                        "cabecera_hex": cabecera.hex().upper(),
                        "texto": texto_desc
                    })
            except Exception:
                pass # No era un bloque zlib válido, seguimos buscando
            
            offset = idx + 2

    # ── 2. BÚSQUEDA POST-EOF (SOLO PARA IMÁGENES) ─────────────
    # Evitamos ejecutar esto en videos (MP4/MKV) porque arroja falsos positivos de compresión.
    if not es_video:
        # Para PNG: termina en IEND + 4 bytes de CRC (total 8 bytes desde la I)
        iend_idx = raw_bytes.find(b'IEND')
        if iend_idx != -1 and len(raw_bytes) > (iend_idx + 8):
            post_eof_data = raw_bytes[iend_idx + 8:]
            # Si hay más de 20 bytes después del final oficial, es altamentente sospechoso
            if len(post_eof_data) > 20: 
                texto_anomalo = post_eof_data.decode('utf-8', errors='ignore').strip()
                resultados["post_eof"].append({
                    "tamaño_bytes": len(post_eof_data),
                    "preview": texto_anomalo[:500] if texto_anomalo else "Datos binarios no legibles"
                })

        # Para JPEG: termina en FF D9
        ffd9_idx = raw_bytes.rfind(b'\xff\xd9')
        if ffd9_idx != -1 and len(raw_bytes) > (ffd9_idx + 2):
            post_eof_data = raw_bytes[ffd9_idx + 2:]
            if len(post_eof_data) > 20:
                texto_anomalo = post_eof_data.decode('utf-8', errors='ignore').strip()
                resultados["post_eof"].append({
                    "tamaño_bytes": len(post_eof_data),
                    "preview": texto_anomalo[:500] if texto_anomalo else "Datos binarios no legibles"
                })

    # ── 3. BÚSQUEDA XMP CRUDO (Midjourney / Adobe) ────────────────────────────
    xmp_inicio = raw_bytes.find(b'<x:xmpmeta')
    if xmp_inicio != -1:
        xmp_fin = raw_bytes.find(b'</x:xmpmeta>', xmp_inicio)
        if xmp_fin != -1:
            xmp_data = raw_bytes[xmp_inicio:xmp_fin+12].decode('utf-8', errors='ignore')
            resultados["xmp_crudo"].append(xmp_data)

    # Opcional: Guardar los zlib ocultos en JSON si son muy largos
    for i, hallazgo in enumerate(resultados["zlib_oculto"]):
        if hallazgo["texto"].startswith("{"):
            try:
                parsed = json.loads(hallazgo["texto"])
                guardar_json(ruta_base, f"ZLIB_{i:02d}", parsed)
            except:
                pass

    return resultados


# ══════════════════════════════════════════════════════════════
#  ORQUESTADOR
# ══════════════════════════════════════════════════════════════

def analizar_archivo(ruta):
    nombre = os.path.basename(ruta)
    ext    = Path(ruta).suffix.lower()
    base   = ruta

    print(f"\n{'═'*65}")
    print(f"  AUTOPSIA: {nombre}")
    print(f"{'═'*65}")

    reporte  = f"AUTOPSIA FORENSE — {nombre}\n"
    reporte += f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    reporte += "═" * 70 + "\n"
    archivos_generados = []

    # ── A: Info básica — lee el archivo completo una sola vez ────────────────
    print("  [A] Leyendo archivo completo...")
    raw_bytes, info = info_basica(ruta)
    reporte += seccion("A — INFORMACIÓN DEL ARCHIVO")
    for k, v in info.items():
        reporte += f"  {k:<20}: {v}\n"
    print(f"     Tamaño: {info['Tamaño']}")

    # ── B: ffprobe ───────────────────────────────────────────────────────────
    print("  [B] ffprobe...")
    ff_data, ff_err = run_ffprobe(ruta)
    reporte += seccion("B — FFPROBE")
    if ff_data:
        reporte += formatear_ffprobe(ff_data) + "\n"
        ruta_ff = guardar_json(base, "ffprobe", ff_data)
        archivos_generados.append(ruta_ff)
        print(f"     → {os.path.basename(ruta_ff)}")
    else:
        reporte += f"  {ff_err}\n"

    # ── C: exiftool ──────────────────────────────────────────────────────────
    print("  [C] exiftool...")
    et_data, et_err = run_exiftool(ruta)
    reporte += seccion("C — EXIFTOOL")
    if et_data:
        for k, v in et_data.items():
            reporte += f"  {k:<45}: {str(v)}\n"
        ruta_et = guardar_json(base, "exiftool", et_data)
        archivos_generados.append(ruta_et)
        print(f"     → {os.path.basename(ruta_et)}")
    else:
        reporte += f"  {et_err}\n"

    # ── D: Pillow + UserComment ──────────────────────────────────────────────
    if ext in EXTS_IMAGEN:
        print("  [D] Pillow + UserComment...")
        pil_data, pil_err = analizar_pillow(ruta)
        reporte += seccion("D — PILLOW / EXIF")
        if pil_data:
            reporte += json.dumps(pil_data, indent=2, ensure_ascii=False) + "\n"
            ruta_pil = guardar_json(base, "pillow", pil_data)
            archivos_generados.append(ruta_pil)
            print(f"     → {os.path.basename(ruta_pil)}")
        else:
            reporte += f"  {pil_err}\n"

    # ── E: Bloques WebP ──────────────────────────────────────────────────────
    if ext == '.webp':
        print("  [E] Bloques WebP...")
        webp_data = analizar_webp(ruta, raw_bytes)
        reporte  += seccion("E — BLOQUES WEBP")
        reporte  += json.dumps(webp_data, indent=2, ensure_ascii=False) + "\n"
        ruta_wp   = guardar_json(base, "webp_bloques", webp_data)
        archivos_generados.append(ruta_wp)
        print(f"     → {os.path.basename(ruta_wp)}")

    # ── F: Aspiradora binaria ────────────────────────────────────────────────
    print("  [F] Aspiradora binaria (archivo completo)...")
    aspira = aspiradora_binaria(ruta, base, raw_bytes)
    reporte += seccion("F — BÚSQUEDA BINARIA (IA / JSON oculto)")

    if aspira["json_encontrados"]:
        reporte += f"\nJSON ENCONTRADOS ({len(aspira['json_encontrados'])}):\n"
        for h in aspira["json_encontrados"]:
            reporte += f"  [{h['indice']:02d}] {h['estado']} → {h['archivo']}\n"
            reporte += f"       {h['preview']}\n\n"
            ruta_j = os.path.join(os.path.dirname(ruta), h['archivo'])
            archivos_generados.append(ruta_j)
    else:
        reporte += "  (no se encontraron JSON)\n"

    if aspira["patrones_ia"]:
        reporte += f"\nPATRONES IA ({len(aspira['patrones_ia'])}):\n"
        ya = set()
        for p in aspira["patrones_ia"]:
            k = p["contexto"][:60]
            if k in ya:
                continue
            ya.add(k)
            reporte += f"\n  Tipo: {p['tipo']}\n  {'─'*50}\n  {p['contexto']}\n"

    if aspira["a1111_raw"]:
        reporte += f"\nA1111 COMPLETO:\n"
        for bloque in aspira["a1111_raw"]:
            reporte += f"  {bloque}\n\n"

    if aspira["cadenas_sospechosas"]:
        reporte += f"\nCADENAS (fallback):\n"
        for i, c in enumerate(aspira["cadenas_sospechosas"]):
            reporte += f"  [{i+1}] {c}\n"

    # ── G: Extracción Extrema ────────────────────────────────────────────────
    print("  [G] Extracción extrema (Zlib, Post-EOF, XMP)...")
    extrema = extraccion_extrema(raw_bytes, base)
    
    if any(extrema.values()):
        reporte += seccion("G — EXTRACCIÓN EXTREMA (ADN PROFUNDO)")
        
        if extrema["zlib_oculto"]:
            reporte += f"\n[!] SE ENCONTRÓ TEXTO COMPRIMIDO (ZLIB) ({len(extrema['zlib_oculto'])}):\n"
            for z in extrema["zlib_oculto"]:
                reporte += f"  Offset: {z['offset']} | Cabecera: {z['cabecera_hex']}\n"
                reporte += f"  {z['texto'][:800]}...\n\n"
                
        if extrema["post_eof"]:
            reporte += f"\n[!] ANOMALÍA: DATOS DESPUÉS DEL FINAL DEL ARCHIVO (POST-EOF):\n"
            for p in extrema["post_eof"]:
                reporte += f"  Tamaño oculto: {p['tamaño_bytes']} bytes\n"
                reporte += f"  Preview: {p['preview']}\n\n"
                
        if extrema["xmp_crudo"]:
            reporte += f"\n[!] METADATOS XMP CRUDOS ENCONTRADOS:\n"
            for x in extrema["xmp_crudo"]:
                reporte += f"  {x[:1000]}...\n\n"
    else:
        reporte += seccion("G — EXTRACCIÓN EXTREMA")
        reporte += "  (No se detectaron datos comprimidos ni ofuscados post-EOF)\n"

    # ── Guardar TXT ──────────────────────────────────────────────────────────
    ruta_txt = guardar_txt(base, reporte)
    archivos_generados.append(ruta_txt)

    print(f"\n  Archivos generados:")
    for a in archivos_generados:
        if os.path.exists(a):
            print(f"    → {os.path.basename(a)}")
    print("  ✅ Listo.")


# ══════════════════════════════════════════════════════════════
#  PUNTO DE ENTRADA
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os, shutil
    
    # Obtener la ruta real donde está guardado Autopsia_Metadatos.py
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    ffprobe_path = os.path.join(base_dir, "tools", "ffprobe.exe")
    exiftool_path = os.path.join(base_dir, "tools", "exiftool.exe")
    
    ffprobe_ok = os.path.exists(ffprobe_path) or shutil.which("ffprobe")
    exiftool_ok = os.path.exists(exiftool_path) or shutil.which("exiftool")

    print("""
╔══════════════════════════════════════════════════════════════╗
║        AUTOPSIA FORENSE — CAJA DE PRUEBAS v3.1               ║
║        SIN LÍMITES — lee archivos completos                  ║
╚══════════════════════════════════════════════════════════════╝
""")
    print(f"  ffprobe  : {'OK' if ffprobe_ok else 'NO ENCONTRADO (Carpeta tools/ vacía)'}")
    print(f"  exiftool : {'OK' if exiftool_ok else 'NO ENCONTRADO (Carpeta tools/ vacía)'}")
    print(f"  Pillow   : {'OK' if PILLOW_OK else 'NO ENCONTRADO (pip install Pillow)'}")

    root = Tk()
    root.withdraw()

    print("\n  Selecciona los archivos a analizar...")
    rutas = filedialog.askopenfilenames(
        title="Autopsia — Seleccionar archivos",
        filetypes=[
            ("Multimedia", "*.mp4 *.mkv *.webm *.avi *.mov *.gif "
                           "*.png *.jpg *.jpeg *.webp *.bmp *.tiff"),
            ("Todos", "*.*"),
        ]
    )

    if rutas:
        for r in rutas:
            analizar_archivo(r)
        print("\n✅ Todas las autopsias completadas.")
    else:
        print("  Cancelado.")
