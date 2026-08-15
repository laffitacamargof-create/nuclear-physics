# qcol_connector_qcol.py
# CONECTOR PARA QCOL - Ejecutar directamente en el entorno QCOL

import importlib.util
import os
import json
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

# ============================================================
# 2. FUNCIÓN PARA EJECUTAR
# ============================================================
def ejecutar(funcion_nombre, parametros=None):
    """Ejecuta una función del repositorio"""
    if parametros is None:
        parametros = {}
    
    repositorio = cargar_repositorio()
    if repositorio is None:
        return {"error": "Repositorio no cargado"}
    
    if not hasattr(repositorio, funcion_nombre):
        return {"error": f"Función '{funcion_nombre}' no encontrada"}
    
    funcion = getattr(repositorio, funcion_nombre)
    if not callable(funcion):
        return {"error": f"'{funcion_nombre}' no es una función"}
    
    try:
        resultado = funcion(**parametros)
        return {
            "resultado": resultado,
            "funcion": funcion_nombre,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# 3. INTERFAZ PARA QCOL (HTML)
# ============================================================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>QCOL · Nuclear Physics</title>
    <style>
        body { font-family: Arial; padding: 20px; background: #f0f2f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 12px; }
        .header { background: #1a2b4a; color: white; padding: 15px 20px; border-radius: 8px; }
        .panel { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 15px 0; }
        .panel label { display: block; margin: 10px 0 5px; font-weight: bold; }
        .panel input, .panel select { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
        .panel button { padding: 10px 20px; background: #1a2b4a; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .output { background: #1e1e1e; color: #d4d4d4; padding: 20px; border-radius: 8px; max-height: 300px; overflow-y: auto; white-space: pre-wrap; font-family: monospace; }
        .iframe-wrapper { border: 1px solid #ddd; border-radius: 8px; overflow: hidden; margin: 15px 0; }
        .iframe-wrapper iframe { width: 100%; height: 500px; border: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔗 QCOL · Nuclear Physics</h1>
        </div>
        
        <div class="iframe-wrapper">
            <iframe src="index.html"></iframe>
        </div>
        
        <div class="panel">
            <h3>▶️ Ejecutar función</h3>
            <label>Función:</label>
            <select id="funcion">
                <option value="calcular_energia_nuclear">calcular_energia_nuclear</option>
                <option value="simular_decaimiento">simular_decaimiento</option>
                <option value="info_circuito">info_circuito</option>
            </select>
            
            <label>Parámetros (JSON):</label>
            <input id="parametros" value='{"nucleo": "U-235", "shots": 1024}'>
            
            <button onclick="ejecutar()" style="margin-top:15px;">▶️ Ejecutar</button>
            <button onclick="limpiar()" style="margin-top:15px; background:#7f8c8d;">🧹 Limpiar</button>
        </div>
        
        <div class="output" id="output">// Resultados aparecerán aquí</div>
    </div>
    
    <script>
        function ejecutar() {
            const funcion = document.getElementById('funcion').value;
            let parametros;
            try {
                parametros = JSON.parse(document.getElementById('parametros').value);
            } catch(e) {
                document.getElementById('output').textContent = '❌ Error en JSON: ' + e.message;
                return;
            }
            
            document.getElementById('output').textContent = '⏳ Ejecutando...';
            
            // En QCOL, esto se ejecuta directamente
            const resultado = ejecutar_funcion(funcion, parametros);
            document.getElementById('output').textContent = JSON.stringify(resultado, null, 2);
        }
        
        function limpiar() {
            document.getElementById('output').textContent = '// Resultados limpiados';
        }
    </script>
</body>
</html>
'''

# ============================================================
# 4. EXPONER FUNCIONES PARA QCOL
# ============================================================
# Esta es la función que QCOL llamará directamente
def ejecutar_desde_qcol(funcion_nombre, parametros_json):
    """Función principal para QCOL"""
    try:
        parametros = json.loads(parametros_json) if parametros_json else {}
        return ejecutar(funcion_nombre, parametros)
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# 5. EJECUCIÓN DIRECTA (para pruebas)
# ============================================================
if __name__ == '__main__':
    print("=" * 50)
    print("🔗 CONECTOR QCOL - NUCLEAR PHYSICS")
    print("=" * 50)
    print("📂 Directorio:", os.getcwd())
    
    # Mostrar HTML para copiar
    print("\n📄 COPIA ESTE HTML EN QCOL:\n")
    print(HTML_TEMPLATE)
    print("\n" + "=" * 50)
    
    # Probar ejecución
    print("\n🧪 Probando conexión con el repositorio...")
    repositorio = cargar_repositorio()
    if repositorio:
        print("✅ Repositorio cargado correctamente")
        print("📋 Funciones disponibles:")
        for attr in dir(repositorio):
            if not attr.startswith('_') and callable(getattr(repositorio, attr)):
                print(f"   - {attr}")
    else:
        print("❌ No se pudo cargar el repositorio")