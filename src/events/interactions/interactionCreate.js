const logger = require('../../utils/logger.js');
const { errorEmbed } = require('../../utils/embeds.js');

module.exports = {
    name: 'interactionCreate',
    async execute(interaction, client) {
        // Manipulação de Comandos Slash
        if (interaction.isChatInputCommand()) {
            const command = client.commands.get(interaction.commandName);
            if (!command) {
                logger.warn(`Comando desconhecido executado: ${interaction.commandName}`);
                return interaction.reply({
                    embeds: [errorEmbed('Comando não encontrado', 'Este comando não está mais disponível no sistema.')],
                    ephemeral: true
                });
            }

            try {
                await command.execute(interaction, client);
            } catch (err) {
                logger.error(`Erro ao executar /${interaction.commandName}: ${err.message}`);
                const reply = {
                    embeds: [errorEmbed('Erro na Execução', 'Ocorreu um erro interno ao processar este comando.')],
                    ephemeral: true
                };

                if (interaction.deferred || interaction.replied) {
                    await interaction.followUp(reply).catch(() => {});
                } else {
                    await interaction.reply(reply).catch(() => {});
                }
            }
            return;
        }

        // Manipulação de Botões
        if (interaction.isButton()) {
            // Emite para handlers customizados se houver
            client.emit('buttonClick', interaction);
            return;
        }

        // Manipulação de Menus de Seleção
        if (interaction.isAnySelectMenu()) {
            client.emit('selectMenu', interaction);
            return;
        }

        // Manipulação de Modais
        if (interaction.isModalSubmit()) {
            client.emit('modalSubmit', interaction);
            return;
        }
    }
};
