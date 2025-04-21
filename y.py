import subprocess
import sys
import os
import time
import threading
import signal
from PIL import Image, ImageEnhance, ImageChops, ImageStat
import pytesseract
import io

# Configuración específica para Termux
pytesseract.pytesseract.tesseract_cmd = 'tesseract'  # Ajustado para Termux

# Variables de estado
detectando = True
ejecutando = True
ruta_archivo_ed = os.path.expanduser("~/storage/shared/dat/ed.txt")  # Ruta ajustada para Termux
ruta_archivo_sel = os.path.expanduser("~/storage/shared/dat/sel.txt")  # Nueva ruta para sel.txt
ruta_imagen_referencia = "/storage/emulated/0/dat/referencia_roi.png"  # Ruta a la imagen de referencia

# Región de interés (ROI) para detectar "1"
R_ROI = (902, 1489, 948, 1532)
TOUCH_COORDS = (927, 1511)
INITIAL_TAP_COORDS = (796, 1348)

def verificar_archivo_existe(ruta_archivo):
    """Verifica si un archivo existe en el sistema de archivos local"""
    return os.path.exists(ruta_archivo)

def eliminar_archivo(ruta_archivo):
    """Elimina un archivo del sistema de archivos local"""
    try:
        if os.path.exists(ruta_archivo):
            os.remove(ruta_archivo)
            print(f"[CONTROL] Archivo {ruta_archivo} eliminado automáticamente")
    except Exception as e:
        print(f"[Error] Al eliminar archivo {ruta_archivo}: {e}")

def capturar_pantalla_optimizado():
    """Captura la pantalla directamente en memoria usando ADB"""
    try:
        start_time = time.time()
        result = subprocess.run(['adb', 'exec-out', 'screencap', '-p'],
                               capture_output=True, check=True)
        end_time = time.time()
        tiem = end_time - start_time
        print(f"Captura en {tiem:.4f} segundos.")
        if result.stdout:
            return Image.open(io.BytesIO(result.stdout))
        return None
    except Exception as e:
        print(f"[Error] Al capturar pantalla: {e}")
        return None

def procesar_imagen(img, roi_box):
    """Procesa la imagen para mejorar la detección"""
    try:
        cropped = img.crop(roi_box)
        enhanced = ImageEnhance.Contrast(cropped).enhance(3.5).convert('L')
        return enhanced
    except Exception as e:
        print(f"[Error] Al procesar imagen: {e}")
        return None

def comparar_imagenes(img1, img2):
    """Compara dos imágenes usando solo PIL y devuelve el porcentaje de similitud"""
    try:
        # Asegurar que ambas imágenes tengan el mismo tamaño
        if img1.size != img2.size:
            img2 = img2.resize(img1.size)
        
        # Calcular diferencia
        diff = ImageChops.difference(img1, img2)
        
        # Calcular estadísticas de la diferencia
        stat = ImageStat.Stat(diff)
        
        # Calcular valor medio de diferencia (0-255)
        mean_diff = sum(stat.mean) / len(stat.mean)
        
        # Convertir a porcentaje de similitud (0-100)
        # 0 diferencia = 100% similitud, 255 diferencia = 0% similitud
        similitud_porcentaje = 100 - (mean_diff * 100 / 255)
        
        return similitud_porcentaje
    except Exception as e:
        print(f"[Error] Al comparar imágenes: {e}")
        return 0

def tocar_pantalla(coords):
    """Toca la pantalla en las coordenadas especificadas usando ADB"""
    try:
        subprocess.run(['adb', 'shell', 'input', 'tap', str(coords[0]), str(coords[1])],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[Error] Al tocar pantalla: {e}")

def ejecutar_secuencia_sel():
    """Ejecuta una secuencia de 4 toques en las coordenadas (781, 2121)"""
    try:
        coords = (781, 2121)
        print(f"[SECUENCIA SEL] Iniciando secuencia de 4 toques en {coords}")
        for i in range(4):  # Realiza 4 toques
            print(f"[SECUENCIA SEL] Toque {i+1}/4 en {coords}")
            tocar_pantalla(coords)
            time.sleep(0.3)  # Espera 0.3 segundos entre toques
        print("[SECUENCIA SEL] Secuencia de toques completada")
        eliminar_archivo(ruta_archivo_sel)  # Elimina el archivo sel.txt después de la secuencia
    except Exception as e:
        print(f"[Error] En secuencia SEL: {e}")

def enviar_alerta():
    """Envía una alerta en paralelo usando ADB."""
    try:
        comando = ['adb', 'shell', 'am', 'broadcast', '-n', 'com.yojan.alert/.NotificationReceiver']
        resultado = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = resultado.communicate()
        if resultado.returncode == 0:
            print("[INFO] Alerta enviada correctamente.")
        else:
            print(f"[Error] Falló al enviar alerta: {stderr.decode('utf-8')}")
    except Exception as e:
        print(f"[Error] Ocurrió un error al enviar alerta: {e}")

def verificar_archivo_deteccion():
    """Verifica periódicamente si existe el archivo de toggle para la detección o sel.txt"""
    global detectando
    while ejecutando:
        try:
            # Verificar archivo ed.txt
            archivo_ed_existe = verificar_archivo_existe(ruta_archivo_ed)
            if archivo_ed_existe:
                detectando = not detectando
                estado = "ACTIVADA" if detectando else "DESACTIVADA"
                print(f"[CONTROL] Detección {estado} mediante archivo toggle")
                eliminar_archivo(ruta_archivo_ed)

            # Verificar archivo sel.txt
            archivo_sel_existe = verificar_archivo_existe(ruta_archivo_sel)
            if archivo_sel_existe:
                print("[CONTROL] Archivo sel.txt detectado. Iniciando secuencia de toques...")
                ejecutar_secuencia_sel()

            time.sleep(0.5)
        except Exception as e:
            print(f"[Error] Al verificar archivos de control: {e}")
            time.sleep(1)

def detectar_1_y_acciones():
    """Detecta el número '1' mediante comparación de imágenes y ejecuta acciones"""
    global detectando, ejecutando
    try:
        # Cargar la imagen de referencia
        if not os.path.exists(ruta_imagen_referencia):
            print(f"[ERROR] No se encontró la imagen de referencia en {ruta_imagen_referencia}")
            ejecutando = False
            return
            
        imagen_referencia = Image.open(ruta_imagen_referencia).convert('L')
        print(f"[INFO] Imagen de referencia cargada desde {ruta_imagen_referencia}")
        
        while ejecutando:
            inicio_iteracion = time.time()  # Marca el inicio de la iteración
            if detectando:
                # Tocar las coordenadas iniciales
                print(f"[ACCIÓN] Tocando pantalla en {INITIAL_TAP_COORDS}")
                tocar_pantalla(INITIAL_TAP_COORDS)

                # Capturar pantalla y procesar imagen
                img = capturar_pantalla_optimizado()
                if not img:
                    continue
                processed_img = procesar_imagen(img, R_ROI)
                if not processed_img:
                    continue
                
                # Comparar la imagen procesada con la imagen de referencia
                similitud = comparar_imagenes(processed_img, imagen_referencia)
                print(f"[INFO] Porcentaje de similitud: {similitud:.2f}%")

                # Acciones si la similitud es superior al 95%
                if similitud > 95:
                    print(f"[ACCIÓN] Detectada coincidencia con {similitud:.2f}% de similitud")
                    # Enviar alerta en paralelo
                    threading.Thread(target=enviar_alerta, daemon=True).start()
                    # Esperar 0.65 segundos
                    time.sleep(0.65)
                    # Tocar la pantalla
                    print(f"[ACCIÓN] Tocando pantalla en {TOUCH_COORDS}")
                    tocar_pantalla(TOUCH_COORDS)
                    # Pausar el bucle hasta que se active/desactive la detección
                    print("[INFO] Esperando archivo toggle para reanudar...")
                    detectando = False

            fin_iteracion = time.time()  # Marca el final de la iteración
            tiempo_iteracion = fin_iteracion - inicio_iteracion
            print(f"[INFO] Tiempo total de la iteración: {tiempo_iteracion:.4f} segundos")


    except Exception as e:
        print(f"[Error] detectar_1_y_acciones(): {e}")
    finally:
        print("[INFO] Detector finalizado")

def manejar_senal(sig, frame):
    """Maneja señales de terminación"""
    global ejecutando
    print("\n[INFO] Señal de terminación recibida. Finalizando...")
    ejecutando = False
    sys.exit(0)

if __name__ == "__main__":
    # Crear directorio para los archivos toggle si no existen
    os.makedirs(os.path.dirname(ruta_archivo_ed), exist_ok=True)
    os.makedirs(os.path.dirname(ruta_archivo_sel), exist_ok=True)

    # Configurar manejo de señales
    signal.signal(signal.SIGINT, manejar_senal)

    # Iniciar el hilo de verificación de archivos de control
    deteccion_thread = threading.Thread(target=verificar_archivo_deteccion, daemon=True)
    deteccion_thread.start()

    print("[INFO] Iniciando detector optimizado con ADB")
    print("[INFO] Asegúrate de tener ADB instalado y el dispositivo conectado")
    print("[INFO] Para activar/desactivar la detección, crea el archivo: ed.txt")
    print("[INFO] Para iniciar la secuencia SEL, crea el archivo: sel.txt")

    # Ejecutar la función de detección
    detectar_1_y_acciones()