const fs = require('fs');
const path = require('path');
const { REST, Routes } = require('discord.js');
const config = require('../config/index.js');
const logger = require('../utils/logger.js');

function loadCommands(client) {
    client.commands = new Map();
    const slashCommandsData = [];
    const commandsPath = path.join(__dirname, '..', 'commands');

    if (!fs.existsSync(commandsPath)) return slashCommandsData;

    const categories = fs.readdirSync(commandsPath);

    for (const category of categories) {
        const categoryPath = path.join(commandsPath, category);
        if (!fs.statSync(categoryPath).isDirectory()) continue;

        const files = fs.readdirSync(categoryPath).filter(f => f.endsWith('.js'));
        for (const file of files) {
            try {
                const command = require(path.join(categoryPath, file));
                if (command.data && command.execute) {
                    client.commands.set(command.data.name, command);
                    slashCommandsData.push(command.data.toJSON ? command.data.toJSON() : command.data);
                    logger.info(`Comando carregado: /${command.data.name} [${category}]`);
                }
            } catch (err) {
                logger.error(`Falha ao carregar comando ${file}: ${err.message}`);
            }
        }
    }

    return slashCommandsData;
}

async function registerSlashCommands(client, slashCommandsData) {
    if (!config.token || config.token === 'd') {
        logger.warn('Token do Discord não configurado. Pulei o registro de comandos slash.');
        return;
    }

    try {
        logger.discord(`Registrando ${slashCommandsData.length} comando(s) slash no Discord...`);
        const rest = new REST({ version: '10' }).setToken(config.token);
        await rest.put(
            Routes.applicationCommands(client.user.id),
            { body: slashCommandsData }
        );
        logger.success(`Todos os ${slashCommandsData.length} comandos slash foram registrados globalmente!`);
    } catch (err) {
        logger.error(`Erro ao registrar comandos slash: ${err.message}`);
    }
}

module.exports = { loadCommands, registerSlashCommands };
