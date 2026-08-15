from flask import Flask, request, jsonify
from flask_cors import CORS
import sys, io, time, traceback, os, base64, requests

app = Flask(__name__)
CORS(app)

# ==================== NUCLEAR-PHYSICS GITHUB CONNECTOR ====================
# Reads/writes files in a separate GitHub repo on behalf of Quantum App
# Studio. The GitHub token NEVER goes to the browser — it lives only here,
# as a server-side environment variable (set it as a Space Secret, never
# commit it to source control).
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_OWNER = os.environ.get('GITHUB_OWNER', 'laffitacamargof-create')
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'nuclear-physics')
GITHUB_BRANCH = os.environ.get('GITHUB_BRANCH', 'main')
# Shared secret the browser must send to prove it's an authenticated founder
# session. Set this as a Space Secret too. This has the same trust model as
# the rest of QCOL's founder access (client-supplied, not real per-user
# auth) — treat it like the founder password: don't reuse it elsewhere, and
# use a fine-grained GitHub PAT scoped ONLY to this one repo's contents.
QCOL_ADMIN_KEY = os.environ.get('QCOL_ADMIN_KEY', '')

def _gh_headers():
    return {
        'Authorization': f'Bearer {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }

def _gh_url(path):
    path = path.lstrip('/')
    return f'https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}'

def _require_admin():
    if not QCOL_ADMIN_KEY:
        return False, 'QCOL_ADMIN_KEY no está configurado en el servidor.'
    sent = request.headers.get('X-QCOL-Admin-Key', '')
    if sent != QCOL_ADMIN_KEY:
        return False, 'Clave de administrador inválida o ausente.'
    return True, 'OK'

@app.route('/github/list', methods=['GET'])
def github_list():
    if not GITHUB_TOKEN:
        return jsonify({'success': False, 'error': 'GITHUB_TOKEN no configurado en el servidor.'}), 500
    path = request.args.get('path', '')
    try:
        r = requests.get(_gh_url(path), headers=_gh_headers(),
                          params={'ref': GITHUB_BRANCH}, timeout=15)
        if r.status_code == 404:
            return jsonify({'success': False, 'error': 'Ruta no encontrada'}), 404
        r.raise_for_status()
        data = r.json()
        items = data if isinstance(data, list) else [data]
        out = [{
            'name': it['name'], 'path': it['path'], 'type': it['type'],
            'size': it.get('size', 0), 'sha': it['sha']
        } for it in items]
        return jsonify({'success': True, 'items': out})
    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'error': str(e)}), 502

@app.route('/github/read', methods=['GET'])
def github_read():
    if not GITHUB_TOKEN:
        return jsonify({'success': False, 'error': 'GITHUB_TOKEN no configurado en el servidor.'}), 500
    path = request.args.get('path', '')
    if not path:
        return jsonify({'success': False, 'error': 'Falta el parámetro path'}), 400
    try:
        r = requests.get(_gh_url(path), headers=_gh_headers(),
                          params={'ref': GITHUB_BRANCH}, timeout=15)
        if r.status_code == 404:
            return jsonify({'success': False, 'error': 'Archivo no encontrado'}), 404
        r.raise_for_status()
        data = r.json()
        if data.get('type') != 'file':
            return jsonify({'success': False, 'error': 'La ruta no es un archivo'}), 400
        content = base64.b64decode(data['content']).decode('utf-8', errors='replace')
        return jsonify({'success': True, 'path': data['path'], 'sha': data['sha'], 'content': content})
    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'error': str(e)}), 502

@app.route('/github/write', methods=['POST', 'OPTIONS'])
def github_write():
    if request.method == 'OPTIONS':
        r = jsonify({'ok': True})
        r.headers['Access-Control-Allow-Origin'] = '*'
        r.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        r.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-QCOL-Admin-Key'
        return r

    ok, msg = _require_admin()
    if not ok:
        return jsonify({'success': False, 'error': msg}), 403
    if not GITHUB_TOKEN:
        return jsonify({'success': False, 'error': 'GITHUB_TOKEN no configurado en el servidor.'}), 500

    data = request.get_json(silent=True) or {}
    path = data.get('path', '')
    content = data.get('content', '')
    commit_message = data.get('message') or f'QCOL App Studio: update {path}'
    if not path:
        return jsonify({'success': False, 'error': 'Falta path'}), 400
    if len(content.encode('utf-8')) > 900_000:
        return jsonify({'success': False, 'error': 'Archivo demasiado grande (límite ~900KB por la API de contenidos de GitHub)'}), 400

    try:
        # Need the current sha if the file already exists (GitHub requires it for updates)
        sha = None
        existing = requests.get(_gh_url(path), headers=_gh_headers(),
                                 params={'ref': GITHUB_BRANCH}, timeout=15)
        if existing.status_code == 200:
            sha = existing.json().get('sha')

        payload = {
            'message': commit_message,
            'content': base64.b64encode(content.encode('utf-8')).decode('ascii'),
            'branch': GITHUB_BRANCH,
        }
        if sha:
            payload['sha'] = sha

        r = requests.put(_gh_url(path), headers=_gh_headers(), json=payload, timeout=20)
        r.raise_for_status()
        result = r.json()
        return jsonify({
            'success': True,
            'path': path,
            'sha': result['content']['sha'],
            'commit_url': result['commit']['html_url'],
        })
    except requests.exceptions.RequestException as e:
        detail = ''
        try:
            detail = e.response.json().get('message', '')
        except Exception:
            pass
        return jsonify({'success': False, 'error': f'{e} {detail}'.strip()}), 502
# ==================== FIN CONECTOR ====================

# Seguridad básica
BLOCKED = ['import os', 'import subprocess', 'import socket',
           '__import__("os")', 'open(', 'os.system', 'shutil.']

def is_safe(code):
    for b in BLOCKED:
        if b in code:
            return False, f'Operación no permitida: {b}'
    return True, 'OK'

@app.route('/')
def index():
    return jsonify({
        'name': 'QCOL Motor',
        'status': 'online',
        'version': '2.0',
        'endpoints': ['/health', '/run', '/version']
    })

@app.route('/health')
def health():
    try:
        import qiskit
        qiskit_v = qiskit.__version__
    except:
        qiskit_v = 'no instalado'
    try:
        import cirq
        cirq_v = cirq.__version__
    except:
        cirq_v = 'no instalado'
    return jsonify({
        'status': 'ok',
        'engine': 'QCOL-Render',
        'libs': ['qiskit', 'cirq'],
        'qiskit': qiskit_v,
        'cirq': cirq_v,
    })

@app.route('/version')
def version():
    try:
        import qiskit, numpy
        return jsonify({
            'qiskit': qiskit.__version__,
            'numpy': numpy.__version__,
            'python': sys.version.split()[0]
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/run', methods=['POST', 'OPTIONS'])
def run():
    # CORS preflight
    if request.method == 'OPTIONS':
        r = jsonify({'ok': True})
        r.headers['Access-Control-Allow-Origin'] = '*'
        r.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        r.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return r

    data = request.get_json()
    if not data or 'code' not in data:
        return jsonify({'success': False, 'output': 'No se recibió código'})

    code = data.get('code', '')
    if len(code) > 20000:
        return jsonify({'success': False, 'output': 'Código muy largo'})

    safe, msg = is_safe(code)
    if not safe:
        return jsonify({'success': False, 'output': msg})

    # Capturar output
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = buf = io.StringIO()
    sys.stderr = buf_err = io.StringIO()

    t0 = time.time()
    result = {}

    try:
        import qiskit, cirq, numpy as np
        from numpy import pi

        exec_env = {
            'qiskit': qiskit,
            'cirq': cirq,
            'np': np,
            'pi': pi,
            '__builtins__': __builtins__
        }
        exec(code, exec_env)

        output = buf.getvalue()
        warnings = buf_err.getvalue()
        if warnings and 'DeprecationWarning' not in warnings:
            output += '\n' + warnings

        # Extraer probabilidades si hay circuito Qiskit
        qc = exec_env.get('qc', None)
        bloch_data = None

        if qc is not None:
            try:
                from qiskit.quantum_info import Statevector
                from qiskit_aer import AerSimulator
                from qiskit import transpile

                has_measure = any(
                    inst.operation.name == 'measure'
                    for inst in qc.data
                )

                if has_measure:
                    sim = AerSimulator()
                    qc_t = transpile(qc, sim)
                    res = sim.run(qc_t, shots=1024).result()
                    counts = res.get_counts()
                    total = sum(counts.values())
                    bloch_data = {
                        'counts': counts,
                        'probabilities': {k: v/total for k, v in counts.items()},
                        'shots': 1024
                    }
                else:
                    sv = Statevector(qc)
                    probs = sv.probabilities_dict()
                    bloch_data = {
                        'probabilities': {k: float(v) for k, v in probs.items()}
                    }
            except Exception:
                pass

        result = {
            'success': True,
            'output': output.strip() if output.strip() else '✅ Ejecutado sin output',
            'bloch': bloch_data,
            'time': round(time.time() - t0, 3)
        }

    except SyntaxError as e:
        result = {
            'success': False,
            'output': f'Error de sintaxis línea {e.lineno}:\n{e.msg}'
        }
    except Exception as e:
        tb = traceback.format_exc()
        lineas = [l for l in tb.split('\n')
                  if 'File "<string>"' in l or 'Error' in l or 'error' in l.lower()]
        result = {
            'success': False,
            'output': 'Error:\n' + '\n'.join(lineas) if lineas else str(e)
        }
    finally:
        sys.stdout = old_out
        sys.stderr = old_err

    return jsonify(result)


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    print(f'🚀 QCOL Motor iniciando en puerto {port}')
    app.run(host='0.0.0.0', port=port)
