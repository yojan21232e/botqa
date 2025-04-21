import subprocess
import sys
import os
import time
import threading
import signal
from PIL import Image, ImageChops

# Configuración específica para Termux
ruta_referencia_android = "/storage/emulated/0/dat/referencia_roi.png"  # Ruta de la imagen de referencia en el dispositivo Android
R_ROI = (902, 1489, 948, 1532)  # Región de interés (ROI)
TOUCH_COORDS = (927, 1511)
INITIAL_TAP_COORDS = (796, 1348)

# Variables de estado
detectando = True
ejecutando = True
ruta_archivo_ed = os.path.expanduser("~/storage/shared/dat/ed.txt")  # Ruta ajustada para Termux
ruta_archivo_sel = os.path.expanduser("~/storage/shared/dat/sel.txt")  # Nueva ruta para sel.txt

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
        result = subprocess.run(['adb', 'exec-out', 'screencap', '-p'],
                               capture_output=True, check=True)
        if result.stdout:
            return Image.open(io.BytesIO(result.stdout))
        return None
    except Exception as e:
        print(f"[Error] Al capturar pantalla: {e}")
        return None

def cargar_referencia_android(ruta_referencia_android):
    """Carga la imagen de referencia desde el dispositivo Android"""
    try:
        # Copiar la imagen de referencia desde el dispositivo Android a la computadora temporalmente
        ruta_temporal_local = "temp_referencia.png"
        subprocess.run(['adb', 'pull', ruta_referencia_android, ruta_temporal_local], check=True)
        referencia = Image.open(ruta_temporal_local)
        os.remove(ruta_temporal_local)  # Eliminar el archivo temporal después de cargarlo
        return referencia
    except Exception as e:
        print(f"[Error] Al cargar imagen de referencia: {e}")
        return None

def imagenes_iguales(img1, img2, umbral=5):
    """
    Compara dos imágenes usando histogramas de Pillow.
    
    Args:
        img1, img2: Imágenes en formato PIL.
        umbral: Umbral de diferencia permitida.
    
    Returns:
        bool: True si las imágenes son similares, False en caso contrario.
    """
    if img1.size != img2.size:
        return False
    diferencia = ImageChops.difference(img1, img2)
    histograma = diferencia.histogram()
    total_pixeles = sum(histograma)
    suma_diferencias = sum(i * count for i, count in enumerate(histograma))
    return (suma_diferencias / total_pixeles) < umbral

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
    """Detecta el número '1' comparando imágenes y ejecuta acciones"""
    global detectando, ejecutando
    try:
        # Cargar la imagen de referencia
        referencia = cargar_referencia_android(ruta_referencia_android)
        if referencia is None:
            print("[Error] No se pudo cargar la imagen de referencia. Finalizando...")
            return

        while ejecutando:
            inicio_iteracion = time.time()  # Marca el inicio de la iteración
            if detectando:
                # Tocar las coordenadas iniciales
                print(f"[ACCIÓN] Tocando pantalla en {INITIAL_TAP_COORDS}")
                tocar_pantalla(INITIAL_TAP_COORDS)

                # Capturar pantalla y recortar ROI
                img = capturar_pantalla_optimizado()
                if not img:
                    continue
                roi_actual = img.crop(R_ROI)

                # Comparar la ROI actual con la referencia
                if imagenes_iguales(roi_actual, referencia):
                    print("[ACCIÓN] Detectado '1' mediante comparación de imágenes")
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