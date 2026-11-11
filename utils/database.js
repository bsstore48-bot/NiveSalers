const fs = require('fs');
const storage = require('./storage.js');

function carregar() {
    if (!fs.existsSync('./dados.json')) return {};
    try {
        return JSON.parse(fs.readFileSync('./dados.json', 'utf8'));
    } catch {
        return {};
    }
}

function salvar(dados) {
    try {
        fs.writeFileSync('./dados.json', JSON.stringify(dados, null, 2));
    } catch (e) {
        console.error('Erro ao salvar dados.json:', e);
    }
}

function getPlano(guildOrUserId) {
    if (storage.existeServidor(guildOrUserId)) {
        const cfg = storage.getServidor(guildOrUserId);
        return cfg.plano || 'Gratis';
    }
    const dados = carregar();
    return dados.usuarios?.[guildOrUserId]?.plano || dados.servidores?.[guildOrUserId]?.plano || 'Gratis';
}

function getLimiteAtendentes(guildId) {
    const cfg = storage.getServidor(guildId);
    const plano = cfg.plano || 'Gratis';
    if (plano === 'VIP') return 467;
    if (plano === 'Premium') return 7;
    return 5;
}

function getTranscriptHtml(guildId) {
    const cfg = storage.getServidor(guildId);
    return cfg.transcriptModo === 'site';
}

function getConfig(guildId) {
    return storage.getServidor(guildId);
}

function getNextTicketNumber(guildId) {
    const cfg = storage.getServidor(guildId);
    cfg.contadorTickets = (cfg.contadorTickets || 0) + 1;
    storage.salvarServidor(guildId, cfg);
    return cfg.contadorTickets.toString().padStart(3, '0');
}

module.exports = { carregar, salvar, getPlano, getLimiteAtendentes, getTranscriptHtml, getConfig, getNextTicketNumber };
