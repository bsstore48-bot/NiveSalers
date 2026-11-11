const fs = require('fs');
const path = require('path');

const PASTA_DADOS = path.join(__dirname, '..', 'dados');
const PASTA_SERVIDORES = path.join(PASTA_DADOS, 'servidores');
const CAMINHO_KEYS = path.join(__dirname, '..', 'keys.json');
const CAMINHO_CONFIG = path.join(__dirname, '..', 'config.json');

// Configurações do provedor de nuvem
const GITHUB_TOKEN = process.env.GITHUB_TOKEN || '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';
const GITHUB_REPO = process.env.GITHUB_REPO || 'bsstore48-bot/NiveSalers';
const GITHUB_BRANCH = process.env.GITHUB_DATA_BRANCH || 'cloud-data';
const CLOUD_SYNC_URL = process.env.CLOUD_SYNC_URL || null;

let isSyncing = false;
let syncScheduled = null;
let lastSyncTime = null;
let lastSyncStatus = 'idle';
let lastSyncError = null;

function garantirPastas() {
    fs.mkdirSync(PASTA_SERVIDORES, { recursive: true });
}

/**
 * Coleta todas as configurações de clientes, servidores e chaves em um único snapshot
 */
function compilarSnapshot() {
    garantirPastas();
    const servidores = {};
    const arquivos = fs.readdirSync(PASTA_SERVIDORES).filter(f => f.endsWith('.json'));

    for (const arq of arquivos) {
        const guildId = arq.replace('.json', '');
        try {
            servidores[guildId] = JSON.parse(fs.readFileSync(path.join(PASTA_SERVIDORES, arq), 'utf8'));
        } catch (e) {
            console.error(`⚠️ [cloudSync] Erro ao ler servidor ${arq}:`, e.message);
        }
    }

    let keys = {};
    if (fs.existsSync(CAMINHO_KEYS)) {
        try {
            keys = JSON.parse(fs.readFileSync(CAMINHO_KEYS, 'utf8'));
        } catch (e) {
            console.error('⚠️ [cloudSync] Erro ao ler keys.json:', e.message);
        }
    }

    return {
        versao: '2.0.0',
        atualizadoEm: new Date().toISOString(),
        totalServidores: Object.keys(servidores).length,
        servidores,
        keys
    };
}

/**
 * Restaura o snapshot para o disco local do container/máquina
 */
function restaurarSnapshot(snapshot) {
    if (!snapshot || typeof snapshot !== 'object') return false;
    garantirPastas();

    let restaurados = 0;
    if (snapshot.servidores && typeof snapshot.servidores === 'object') {
        for (const [guildId, config] of Object.entries(snapshot.servidores)) {
            const dest = path.join(PASTA_SERVIDORES, `${guildId}.json`);
            fs.writeFileSync(dest, JSON.stringify(config, null, 2), 'utf8');
            restaurados++;
        }
    }

    if (snapshot.keys && typeof snapshot.keys === 'object' && Object.keys(snapshot.keys).length > 0) {
        fs.writeFileSync(CAMINHO_KEYS, JSON.stringify(snapshot.keys, null, 2), 'utf8');
    }

    console.log(`✅ [cloudSync] Restauração concluída com sucesso: ${restaurados} servidores recuperados da nuvem.`);
    return true;
}

/**
 * Obtém o SHA do arquivo no GitHub para permitir atualizações
 */
async function obterShaGitHub(caminhoArquivo) {
    try {
        const url = `https://api.github.com/repos/${GITHUB_REPO}/contents/${caminhoArquivo}?ref=${GITHUB_BRANCH}`;
        const res = await fetch(url, {
            headers: {
                'Authorization': `token ${GITHUB_TOKEN}`,
                'User-Agent': 'NiveSalers-CloudSync',
                'Accept': 'application/vnd.github.v3+json'
            }
        });

        if (res.status === 200) {
            const data = await res.json();
            return data.sha;
        }
        return null;
    } catch {
        return null;
    }
}

/**
 * Garante que a branch de dados exista no GitHub
 */
async function garantirBranchGitHub() {
    try {
        const resRepo = await fetch(`https://api.github.com/repos/${GITHUB_REPO}`, {
            headers: {
                'Authorization': `token ${GITHUB_TOKEN}`,
                'User-Agent': 'NiveSalers-CloudSync'
            }
        });

        if (!resRepo.ok) return false;
        const repoData = await resRepo.json();
        const defaultBranch = repoData.default_branch || 'main';

        const resBranch = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/branches/${GITHUB_BRANCH}`, {
            headers: {
                'Authorization': `token ${GITHUB_TOKEN}`,
                'User-Agent': 'NiveSalers-CloudSync'
            }
        });

        if (resBranch.status === 404) {
            // Obter SHA da branch padrão
            const resRef = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/git/refs/heads/${defaultBranch}`, {
                headers: {
                    'Authorization': `token ${GITHUB_TOKEN}`,
                    'User-Agent': 'NiveSalers-CloudSync'
                }
            });

            if (resRef.ok) {
                const refData = await resRef.json();
                const sha = refData.object.sha;

                // Criar nova branch
                await fetch(`https://api.github.com/repos/${GITHUB_REPO}/git/refs`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `token ${GITHUB_TOKEN}`,
                        'User-Agent': 'NiveSalers-CloudSync',
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        ref: `refs/heads/${GITHUB_BRANCH}`,
                        sha
                    })
                });
                console.log(`🌿 [cloudSync] Branch "${GITHUB_BRANCH}" criada para armazenamento de configurações.`);
            }
        }
        return true;
    } catch (e) {
        console.error('⚠️ [cloudSync] Erro ao verificar branch no GitHub:', e.message);
        return false;
    }
}

/**
 * Puxa dados da nuvem para o container local (executado no boot do bot)
 */
async function pullFromCloud() {
    console.log('☁️ [cloudSync] Puxando configurações dos clientes da nuvem...');

    // 1. Tentar via URL externa personalizada se configurada
    if (CLOUD_SYNC_URL) {
        try {
            const res = await fetch(`${CLOUD_SYNC_URL}/backup`, {
                headers: { 'Accept': 'application/json' }
            });
            if (res.ok) {
                const snapshot = await res.json();
                restaurarSnapshot(snapshot);
                lastSyncTime = new Date();
                lastSyncStatus = 'success (external-url)';
                return true;
            }
        } catch (e) {
            console.error('⚠️ [cloudSync] Falha ao puxar da CLOUD_SYNC_URL:', e.message);
        }
    }

    // 2. Tentar via GitHub API
    if (GITHUB_TOKEN && GITHUB_REPO) {
        try {
            const url = `https://api.github.com/repos/${GITHUB_REPO}/contents/cloud-backup.json?ref=${GITHUB_BRANCH}`;
            const res = await fetch(url, {
                headers: {
                    'Authorization': `token ${GITHUB_TOKEN}`,
                    'User-Agent': 'NiveSalers-CloudSync',
                    'Accept': 'application/vnd.github.v3+json'
                }
            });

            if (res.ok) {
                const data = await res.json();
                const content = Buffer.from(data.content, 'base64').toString('utf8');
                const snapshot = JSON.parse(content);
                restaurarSnapshot(snapshot);
                lastSyncTime = new Date();
                lastSyncStatus = 'success (github)';
                return true;
            } else if (res.status === 404) {
                console.log('ℹ️ [cloudSync] Nenhum backup prévio encontrado na nuvem. Criando snapshot inicial...');
                await pushToCloud();
                return true;
            }
        } catch (e) {
            console.error('❌ [cloudSync] Erro ao sincronizar com GitHub:', e.message);
            lastSyncStatus = 'error';
            lastSyncError = e.message;
        }
    }

    return false;
}

/**
 * Envia o snapshot local atualizado para a nuvem
 */
async function pushToCloud() {
    if (isSyncing) {
        agendarSincronizacao();
        return;
    }

    isSyncing = true;
    try {
        const snapshot = compilarSnapshot();
        const conteudoStr = JSON.stringify(snapshot, null, 2);

        // 1. Enviar para URL externa se houver
        if (CLOUD_SYNC_URL) {
            try {
                await fetch(`${CLOUD_SYNC_URL}/backup`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: conteudoStr
                });
            } catch (e) {
                console.error('⚠️ [cloudSync] Falha ao enviar para CLOUD_SYNC_URL:', e.message);
            }
        }

        // 2. Enviar para GitHub API
        if (GITHUB_TOKEN && GITHUB_REPO) {
            await garantirBranchGitHub();
            const sha = await obterShaGitHub('cloud-backup.json');
            const url = `https://api.github.com/repos/${GITHUB_REPO}/contents/cloud-backup.json`;
            const contentBase64 = Buffer.from(conteudoStr, 'utf8').toString('base64');

            const payload = {
                message: `chore(cloud-sync): backup automático de configurações [${new Date().toISOString()}]`,
                content: contentBase64,
                branch: GITHUB_BRANCH
            };
            if (sha) payload.sha = sha;

            const res = await fetch(url, {
                method: 'PUT',
                headers: {
                    'Authorization': `token ${GITHUB_TOKEN}`,
                    'User-Agent': 'NiveSalers-CloudSync',
                    'Content-Type': 'application/json',
                    'Accept': 'application/vnd.github.v3+json'
                },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                lastSyncTime = new Date();
                lastSyncStatus = 'success';
                lastSyncError = null;
                console.log(`☁️ [cloudSync] Backup na nuvem concluído com sucesso (${snapshot.totalServidores} servidores).`);
            } else {
                const erroTxt = await res.text();
                lastSyncStatus = 'error';
                lastSyncError = `GitHub HTTP ${res.status}: ${erroTxt}`;
                console.error(`❌ [cloudSync] Erro ao salvar no GitHub: ${lastSyncError}`);
            }
        }
    } catch (e) {
        lastSyncStatus = 'error';
        lastSyncError = e.message;
        console.error('❌ [cloudSync] Exceção ao sincronizar:', e);
    } finally {
        isSyncing = false;
    }
}

/**
 * Agenda sincronização com debounce de 5 segundos para não sobrecarregar
 */
function agendarSincronizacao() {
    if (syncScheduled) clearTimeout(syncScheduled);
    syncScheduled = setTimeout(() => {
        syncScheduled = null;
        pushToCloud().catch(err => console.error('[cloudSync]', err));
    }, 5000);
}

function getStatus() {
    return {
        enabled: Boolean(GITHUB_TOKEN || CLOUD_SYNC_URL),
        provider: GITHUB_TOKEN ? 'GitHub Cloud Storage' : 'Local Only',
        repository: GITHUB_REPO,
        branch: GITHUB_BRANCH,
        lastSyncTime,
        lastSyncStatus,
        lastSyncError,
        isSyncing
    };
}

// Inicia sincronização periódica a cada 10 minutos
const timerSincronizacao = setInterval(() => {
    agendarSincronizacao();
}, 10 * 60 * 1000);
if (timerSincronizacao.unref) timerSincronizacao.unref();

module.exports = {
    pullFromCloud,
    pushToCloud,
    agendarSincronizacao,
    compilarSnapshot,
    restaurarSnapshot,
    getStatus
};
