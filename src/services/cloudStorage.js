const fs = require('fs');
const path = require('path');
const config = require('../config/index.js');
const logger = require('../utils/logger.js');

const DATA_DIR = path.join(__dirname, '..', '..', 'data');
const GUILDS_DIR = path.join(DATA_DIR, 'guilds');

let isSyncing = false;
let pendingSync = null;
let lastSync = null;

function ensureDirs() {
    fs.mkdirSync(GUILDS_DIR, { recursive: true });
}

function getGuildConfig(guildId) {
    ensureDirs();
    const filePath = path.join(GUILDS_DIR, `${guildId}.json`);
    if (fs.existsSync(filePath)) {
        try {
            return JSON.parse(fs.readFileSync(filePath, 'utf8'));
        } catch (e) {
            logger.warn(`Erro ao ler config do servidor ${guildId}: ${e.message}`);
        }
    }
    // Config padrão para novo servidor
    return {
        guildId,
        prefix: '!',
        ticketCategory: null,
        logsChannel: null,
        staffRoles: [],
        welcomeMessage: 'Bem-vindo ao atendimento da nossa equipe!',
        plan: 'Standard',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
    };
}

function saveGuildConfig(guildId, data) {
    ensureDirs();
    data.updatedAt = new Date().toISOString();
    const filePath = path.join(GUILDS_DIR, `${guildId}.json`);
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
    scheduleSync();
    return data;
}

function exportSnapshot() {
    ensureDirs();
    const snapshot = {
        version: config.version,
        timestamp: new Date().toISOString(),
        guilds: {}
    };

    const files = fs.readdirSync(GUILDS_DIR).filter(f => f.endsWith('.json'));
    for (const file of files) {
        const id = file.replace('.json', '');
        try {
            snapshot.guilds[id] = JSON.parse(fs.readFileSync(path.join(GUILDS_DIR, file), 'utf8'));
        } catch {}
    }
    return snapshot;
}

function importSnapshot(snapshot) {
    if (!snapshot || !snapshot.guilds) return 0;
    ensureDirs();
    let count = 0;
    for (const [guildId, data] of Object.entries(snapshot.guilds)) {
        fs.writeFileSync(path.join(GUILDS_DIR, `${guildId}.json`), JSON.stringify(data, null, 2), 'utf8');
        count++;
    }
    return count;
}

async function getGitHubSha(filePath) {
    if (!config.githubToken || !config.githubRepo) return null;
    try {
        const url = `https://api.github.com/repos/${config.githubRepo}/contents/${filePath}?ref=${config.githubBranch}`;
        const res = await fetch(url, {
            headers: {
                'Authorization': `token ${config.githubToken}`,
                'User-Agent': 'NiveSalers-Bot',
                'Accept': 'application/vnd.github.v3+json'
            }
        });
        if (res.ok) {
            const data = await res.json();
            return data.sha;
        }
    } catch {}
    return null;
}

async function pushToCloud() {
    if (isSyncing) {
        scheduleSync();
        return;
    }
    isSyncing = true;

    try {
        const snapshot = exportSnapshot();
        const contentStr = JSON.stringify(snapshot, null, 2);

        if (config.githubToken && config.githubRepo) {
            const sha = await getGitHubSha('cloud-backup.json');
            const url = `https://api.github.com/repos/${config.githubRepo}/contents/cloud-backup.json`;
            const contentBase64 = Buffer.from(contentStr, 'utf8').toString('base64');

            const payload = {
                message: `chore(cloud-sync): persistência automática [${new Date().toISOString()}]`,
                content: contentBase64,
                branch: config.githubBranch
            };
            if (sha) payload.sha = sha;

            const res = await fetch(url, {
                method: 'PUT',
                headers: {
                    'Authorization': `token ${config.githubToken}`,
                    'User-Agent': 'NiveSalers-Bot',
                    'Content-Type': 'application/json',
                    'Accept': 'application/vnd.github.v3+json'
                },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                lastSync = new Date();
                logger.cloud(`Backup salvo na nuvem com sucesso (${Object.keys(snapshot.guilds).length} servidores).`);
            } else {
                logger.warn(`GitHub Cloud Sync respondeu status HTTP ${res.status}`);
            }
        }
    } catch (e) {
        logger.error(`Exceção durante o Cloud Sync: ${e.message}`);
    } finally {
        isSyncing = false;
    }
}

async function pullFromCloud() {
    logger.cloud('Sincronizando dados dos clientes da nuvem...');
    if (!config.githubToken || !config.githubRepo) return false;

    try {
        const url = `https://api.github.com/repos/${config.githubRepo}/contents/cloud-backup.json?ref=${config.githubBranch}`;
        const res = await fetch(url, {
            headers: {
                'Authorization': `token ${config.githubToken}`,
                'User-Agent': 'NiveSalers-Bot',
                'Accept': 'application/vnd.github.v3+json'
            }
        });

        if (res.ok) {
            const data = await res.json();
            const content = Buffer.from(data.content, 'base64').toString('utf8');
            const snapshot = JSON.parse(content);
            const count = importSnapshot(snapshot);
            lastSync = new Date();
            logger.cloud(`Restauração concluída: ${count} servidores restaurados da nuvem.`);
            return true;
        } else if (res.status === 404) {
            logger.cloud('Nenhum backup anterior encontrado na nuvem. Criando snapshot inicial...');
            await pushToCloud();
            return true;
        }
    } catch (e) {
        logger.error(`Erro ao restaurar dados da nuvem: ${e.message}`);
    }
    return false;
}

function scheduleSync() {
    if (pendingSync) clearTimeout(pendingSync);
    pendingSync = setTimeout(() => {
        pendingSync = null;
        pushToCloud();
    }, 5000);
}

const timer = setInterval(() => {
    scheduleSync();
}, 10 * 60 * 1000);
if (timer.unref) timer.unref();

module.exports = {
    getGuildConfig,
    saveGuildConfig,
    exportSnapshot,
    importSnapshot,
    pullFromCloud,
    pushToCloud,
    getStatus: () => ({
        enabled: Boolean(config.githubToken),
        lastSync,
        isSyncing
    })
};
