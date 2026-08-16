# qcol_connector.py
# CONECTOR PARA QCOL - Ejecutar directamente en el entorno QCOL

import importlib.util
import os
import json
import sys
from datetime import datetime

# ============================================================
# 1. CARGAR EL REPOSITORIO
# ============================================================
def cargar_repositorio():
    """Carga el archivo Python del repositorio"""
    archivos = [
        "deepseek_python_20260815_8a14ee.py",
        "QCOL_App_Studio_Backend_Colab.ipynb"
    ]
    
    for archivo in archivos:
        if os.path.exists(archivo):
            try:
                spec = importlib.util.spec_from_file_location("repositorio", archivo)
                if spec:
                    modulo = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(modulo)
                    print(f"✅ Cargado: {archivo}")
                    return modulo
            except Exception as e:
                print(f"⚠️ Error al cargar {archivo}: {e}")
                continue
    
    print("❌ No se encontró archivo Python del repositorio")
    return None

# Cargar al inicio
REPOSITORIO = cargar_repositorio()

# ============================================================
# 2. FUNCIÓN PARA EJECUTAR (PRINCIPAL)
# ============================================================
def ejecutar(funcion_nombre, parametros=None):
    """
    Ejecuta una función del repositorio
    
    Args:
        funcion_nombre: Nombre de la función (ej: "calcular_energia_nuclear")
        parametros: Diccionario con los parámetros (ej: {"nucleo": "U-235"})
    
    Returns:
        Diccionario con el resultado o error
    """
    if parametros is None:
        parametros = {}
    
    if REPOSITORIO is None:
        return {"error": "Repositorio no cargado"}
    
    if not hasattr(REPOSITORIO, funcion_nombre):
        # Listar funciones disponibles
        funciones = []
        for attr in dir(REPOSITORIO):
            if not attr.startswith('_') and callable(getattr(REPOSITORIO, attr)):
                funciones.append(attr)
        return {
            "error": f"Función '{funcion_nombre}' no encontrada",
            "funciones_disponibles": funciones
        }
    
    funcion = getattr(REPOSITORIO, funcion_nombre)
    if not callable(funcion):
        return {"error": f"'{funcion_nombre}' no es una función"}
    
    try:
        print(f"▶️ Ejecutando: {funcion_nombre}")
        print(f"   Parámetros: {parametros}")
        
        # Intentar ejecutar
        try:
            resultado = funcion(**parametros)
        except TypeError:
            # Si falla, intentar con argumentos posicionales
            args = list(parametros.values()) if parametros else []
            resultado = funcion(*args)
        
        return {
            "exito": True,
            "resultado": resultado,
            "funcion": funcion_nombre,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "funcion": funcion_nombre,
            "detalle": traceback.format_exc()
        }

# ============================================================
# 3. LISTAR FUNCIONES DISPONIBLES
# ============================================================
def listar_funciones():
    """Lista todas las funciones disponibles en el repositorio"""
    if REPOSITORIO is None:
        return []
    
    funciones = []
    for attr in dir(REPOSITORIO):
        if not attr.startswith('_') and callable(getattr(REPOSITORIO, attr)):
            funciones.append(attr)
    
    return sorted(funciones)

# ============================================================
# 4. FUNCIÓN PARA QCOL (CON JSON)
# ============================================================
def qcol_ejecutar(funcion_nombre, parametros_json):
    """
    Función para QCOL que recibe parámetros en JSON
    
    Args:
        funcion_nombre: Nombre de la función
        parametros_json: String JSON con los parámetros
    
    Returns:
        Diccionario con el resultado
    """
    try:
        parametros = json.loads(parametros_json) if parametros_json else {}
        return ejecutar(funcion_nombre, parametros)
    except json.JSONDecodeError as e:
        return {"error": f"Error en JSON: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# 5. PRUEBA RÁPIDA
# ============================================================
if __name__ == '__main__':
    print("=" * 50)
    print("🔗 CONECTOR QCOL - NUCLEAR PHYSICS")
    print("=" * 50)
    print(f"📂 Directorio: {os.getcwd()}")
    print(f"📦 Repositorio: {'✅ Cargado' if REPOSITORIO else '❌ No cargado'}")
    
    if REPOSITORIO:
        funciones = listar_funciones()
        print(f"📋 Funciones disponibles: {len(funciones)}")
        for f in funciones[:10]:
            print(f"   - {f}")
        if len(funciones) > 10:
            print(f"   ... y {len(funciones) - 10} más")
    
    print("\n" + "=" * 50)
    print("📌 CÓMO USAR EN QCOL:")
    print("   from qcol_connector import ejecutar")
    print('   resultado = ejecutar("calcular_energia_nuclear", {"nucleo": "U-235"})')
    print("   print(resultado)")
    print("=" * 50)
