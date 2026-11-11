const { Client, GatewayIntentBits, Partials } = require('discord.js');
const config = require('./config/index.js');
const logger = require('./utils/logger.js');
const { startHttpServer } = require('./services/httpServer.js');
const cloudStorage = require('./services/cloudStorage.js');
const { loadCommands } = require('./handlers/commandHandler.js');
const { loadEvents } = require('./handlers/eventHandler.js');

// Prevenção contra encerramento inesperado
process.on('unhandledRejection', (reason, promise) => {
    logger.error('Unhandled Rejection detectada:', reason?.stack || reason);
});

process.on('uncaughtException', (err, origin) => {
    logger.error('Uncaught Exception detectada:', err?.stack || err);
});

// Inicialização do cliente Discord
const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers
    ],
    partials: [Partials.Channel, Partials.Message, Partials.User]
});

// Inicia servidor HTTP embutido para 24/7 no Render (Headless, sem painel web)
startHttpServer(client);

// Carregamento dinâmico de Comandos e Eventos
const slashCommandsData = loadCommands(client);
client.slashCommandsData = slashCommandsData;
loadEvents(client);

// Inicialização e conexão
(async () => {
    // Restaura as configurações da nuvem para o disco do container
    await cloudStorage.pullFromCloud().catch(err => {
        logger.warn(`Sync inicial da nuvem não pôde ser completado: ${err.message}`);
    });

    if (!config.token || config.token === 'd') {
        logger.warn('Nenhum TOKEN do Discord configurado nas variáveis de ambiente.');
        logger.warn('O servidor HTTP está ativo para passar no Health Check do Render.');
        logger.info('Para conectar o bot, defina a variável TOKEN no painel do Render.');
    } else {
        client.login(config.token).catch(err => {
            logger.error(`Falha na autenticação do Discord: ${err.message}`);
        });
    }
})();
