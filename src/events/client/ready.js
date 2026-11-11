const { ActivityType } = require('discord.js');
const logger = require('../../utils/logger.js');
const { registerSlashCommands } = require('../../handlers/commandHandler.js');

module.exports = {
    name: 'ready',
    once: true,
    async execute(client) {
        logger.success(`${client.user.tag} conectou com sucesso ao Discord!`);

        // Registra comandos slash
        if (client.slashCommandsData && client.slashCommandsData.length > 0) {
            await registerSlashCommands(client, client.slashCommandsData);
        }

        // Rotação de status do bot
        const activities = [
            () => ({ name: `/help • NiveSalers`, type: ActivityType.Playing }),
            () => ({ name: `${client.guilds.cache.size} servidores`, type: ActivityType.Watching }),
            () => ({ name: `Render Cloud 24/7`, type: ActivityType.Competing })
        ];

        let index = 0;
        const updatePresence = () => {
            if (!client.user) return;
            const current = activities[index]();
            client.user.setPresence({
                activities: [current],
                status: 'online'
            });
            index = (index + 1) % activities.length;
        };

        updatePresence();
        setInterval(updatePresence, 15000);
    }
};
