const express = require('express');
const cloudSync = require('./utils/cloudSync.js');

function iniciarServidorHttp(client) {
    const app = express();
    const porta = process.env.PORT || 3000;

    app.use(express.json({ limit: '50mb' }));

    // Rota de Health Check para o Render
    app.get('/', (req, res) => {
        res.json({
            app: 'NiveSalers',
            version: '2.0.0',
            status: 'online',
            environment: process.env.NODE_ENV || 'production',
            uptime: Math.floor(process.uptime()),
            bot: client && client.user ? {
                tag: client.user.tag,
                id: client.user.id,
                ping: client.ws?.ping ?? 0,
                guilds: client.guilds?.cache?.size ?? 0
            } : 'connecting',
            cloudSync: cloudSync.getStatus(),
            timestamp: new Date().toISOString()
        });
    });

    app.get('/health', (req, res) => {
        res.status(200).json({ status: 'ok', uptime: process.uptime() });
    });

    app.get('/ping', (req, res) => {
        res.status(200).send('pong');
    });

    // Endpoints de gerenciamento em nuvem
    app.get('/api/cloud/status', (req, res) => {
        res.json(cloudSync.getStatus());
    });

    app.post('/api/cloud/sync', async (req, res) => {
        try {
            await cloudSync.pushToCloud();
            res.json({ success: true, message: 'Sincronização com a nuvem iniciada com sucesso.', status: cloudSync.getStatus() });
        } catch (e) {
            res.status(500).json({ success: false, error: e.message });
        }
    });

    app.post('/api/cloud/pull', async (req, res) => {
        try {
            const ok = await cloudSync.pullFromCloud();
            res.json({ success: ok, message: ok ? 'Configurações restauradas da nuvem.' : 'Nenhum dado encontrado ou falha ao restaurar.', status: cloudSync.getStatus() });
        } catch (e) {
            res.status(500).json({ success: false, error: e.message });
        }
    });

    app.get('/api/cloud/backup', (req, res) => {
        try {
            const snapshot = cloudSync.compilarSnapshot();
            res.setHeader('Content-Type', 'application/json');
            res.setHeader('Content-Disposition', `attachment; filename=nivesalers-backup-${Date.now()}.json`);
            res.send(JSON.stringify(snapshot, null, 2));
        } catch (e) {
            res.status(500).json({ error: e.message });
        }
    });

    app.post('/api/cloud/restore', (req, res) => {
        try {
            const payload = req.body;
            if (!payload || !payload.servidores) {
                return res.status(400).json({ error: 'Formato inválido. O snapshot deve conter a chave "servidores".' });
            }
            cloudSync.restaurarSnapshot(payload);
            cloudSync.agendarSincronizacao();
            res.json({ success: true, message: 'Dados restaurados e sincronizados com a nuvem.' });
        } catch (e) {
            res.status(500).json({ error: e.message });
        }
    });

    const servidor = app.listen(porta, () => {
        console.log(`🚀 [HTTP] Servidor HTTP embutido rodando na porta ${porta} (Render Ready)`);
    });

    return servidor;
}

module.exports = { iniciarServidorHttp };
