const express = require('express');
const config = require('../config/index.js');
const logger = require('../utils/logger.js');
const cloudStorage = require('./cloudStorage.js');

function startHttpServer(client) {
    const app = express();
    app.use(express.json());

    // Health check para o Render (impede desligamento do serviço)
    app.get('/', (req, res) => {
        res.json({
            app: config.botName,
            version: config.version,
            status: 'online',
            environment: config.nodeEnv,
            uptime: Math.floor(process.uptime()),
            discord: client && client.user ? {
                tag: client.user.tag,
                id: client.user.id,
                ping: client.ws?.ping ?? 0,
                guilds: client.guilds?.cache?.size ?? 0
            } : 'connecting',
            cloudSync: cloudStorage.getStatus(),
            timestamp: new Date().toISOString()
        });
    });

    app.get('/health', (req, res) => {
        res.status(200).json({ status: 'ok', uptime: process.uptime() });
    });

    app.get('/ping', (req, res) => {
        res.status(200).send('pong');
    });

    // Cloud backup & restore API (headless)
    app.get('/api/backup', (req, res) => {
        res.json(cloudStorage.exportSnapshot());
    });

    app.post('/api/sync', async (req, res) => {
        await cloudStorage.pushToCloud();
        res.json({ success: true, message: 'Cloud sync executado.' });
    });

    const server = app.listen(config.port, () => {
        logger.http(`Servidor HTTP ativo na porta ${config.port} (Render Ready)`);
    });

    return server;
}

module.exports = { startHttpServer };
