const { SlashCommandBuilder } = require('discord.js');
const storage = require('../utils/storage.js');
const { responderErro } = require('../utils/safe.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('abrir')
        .setDescription('Abre um ticket diretamente')
        .addStringOption(o => 
            o.setName('tipo')
                .setDescription('Tipo/motivo do ticket (ex: Suporte, Duvidas, Compras)')
                .setRequired(false)
        ),

    async execute(interaction, client) {
        try {
            if (!interaction.guild) {
                return interaction.reply({ content: '❌ Este comando só pode ser utilizado dentro de um servidor.', flags: 64 });
            }

            const configGuild = storage.getServidor(interaction.guildId);
            const tipoOpcao = interaction.options.getString('tipo');
            const tipo = tipoOpcao || (configGuild.botoes && configGuild.botoes[0]) || 'Geral';

            if (client && typeof client.abrirTicketDireto === 'function') {
                return await client.abrirTicketDireto(interaction, tipo);
            }

            // Fallback se chamado isoladamente
            return interaction.reply({
                content: `🎫 Para abrir um ticket de **${tipo}**, por favor utilize o painel de tickets do servidor ou configure um canal através de \`/configurar-ticket\`.`,
                flags: 64
            });
        } catch (erro) {
            await responderErro(interaction, erro, '/abrir');
        }
    }
};
