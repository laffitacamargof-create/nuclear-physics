/**
 * qcol-nuclearphysics-connector.js
 *
 * Bridge between Quantum App Studio and the `nuclear-physics` GitHub repo.
 *
 * IMPORTANT: this file never talks to GitHub directly and never holds a
 * GitHub token. It calls your existing qcol_server.py backend (the same
 * "QCOL Motor" that already runs your code compiler), which holds the real
 * GITHUB_TOKEN server-side as an environment variable. That's the same
 * reason the Supabase service key should never live in the browser —
 * a write-capable token in client JS is visible to anyone with devtools.
 *
 * The QCOL_ADMIN_KEY sent with write requests is a shared secret, not a
 * per-user login — it has the same trust model as the founder password (1027)
 * already used elsewhere on this site. Treat it accordingly: don't reuse it
 * for anything else, and scope the underlying GitHub token to a fine-grained
 * PAT with write access to ONLY the nuclear-physics repo.
 */
class NuclearPhysicsConnector {
    constructor(motorUrl, adminKey) {
        this.motorUrl = (motorUrl || '').replace(/\/+$/, '');
        this.adminKey = adminKey || '';
    }

    isConfigured() {
        return !!this.motorUrl;
    }

    async listFiles(path = '') {
        if (!this.isConfigured()) throw new Error('Connector no configurado: falta la URL del motor.');
        const res = await fetch(`${this.motorUrl}/github/list?path=${encodeURIComponent(path)}`);
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error || `HTTP ${res.status}`);
        return data.items; // [{name, path, type, size, sha}]
    }

    async readFile(path) {
        if (!this.isConfigured()) throw new Error('Connector no configurado: falta la URL del motor.');
        const res = await fetch(`${this.motorUrl}/github/read?path=${encodeURIComponent(path)}`);
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error || `HTTP ${res.status}`);
        return data; // {path, sha, content}
    }

    async writeFile(path, content, message) {
        if (!this.isConfigured()) throw new Error('Connector no configurado: falta la URL del motor.');
        if (!this.adminKey) throw new Error('Falta la clave de administrador (founder) para escribir archivos.');
        const res = await fetch(`${this.motorUrl}/github/write`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-QCOL-Admin-Key': this.adminKey,
            },
            body: JSON.stringify({ path, content, message }),
        });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error || `HTTP ${res.status}`);
        return data; // {path, sha, commit_url}
    }
}

// Convenience singleton wired to the same localStorage keys the founder
// panel already writes to (motor/compiler URL + a new admin key field).
window.nuclearPhysicsConnector = new NuclearPhysicsConnector(
    localStorage.getItem('qcol_colab_url') || '',
    localStorage.getItem('qcol_github_admin_key') || ''
);
