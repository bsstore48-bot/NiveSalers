const { SlashCommandBuilder, PermissionsBitField, ChannelType } = require('discord.js');
const storage = require('../utils/storage.js');
const { responderErro } = require('../utils/safe.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('fechar')
        .setDescription('Apaga todos os tickets abertos da categoria/canal de suporte configurado'),

    async execute(interaction) {
        try {
            if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageGuild)) {
                return interaction.reply({ content: 'Você precisa da permissão "Gerenciar Servidor" para utilizar este comando.', flags: 64 });
            }

            const config = storage.getServidor(interaction.guildId);
            await interaction.deferReply({ flags: 64 });

            let apagados = 0;

            if (config.tipo === 'topico') {
                const canalPai = interaction.guild.channels.cache.get(config.canalTopico);
                if (!canalPai) return interaction.editReply({ content: 'O canal de tópicos configurado não foi encontrado.' });

                const threadsAtivas = await canalPai.threads.fetchActive().catch(() => null);
                const threadsArquivadas = await canalPai.threads.fetchArchived().catch(() => null);
                const todasThreads = [
                    ...(threadsAtivas?.threads.values() || []),
                    ...(threadsArquivadas?.threads.values() || [])
                ];

                for (const thread of todasThreads) {
                    if (!config.ticketsAbertos[thread.id]) continue;
                    await thread.delete().catch(() => {});
                    delete config.ticketsAbertos[thread.id];
                    apagados++;
                }
            } else {
                const categoria = interaction.guild.channels.cache.get(config.categoria);
                if (!categoria || categoria.type !== ChannelType.GuildCategory) {
                    return interaction.editReply({ content: 'A categoria de suporte configurada não foi encontrada.' });
                }

                const canaisDaCategoria = interaction.guild.channels.cache.filter(c => c.parentId === categoria.id);
                for (const canal of canaisDaCategoria.values()) {
                    await canal.delete().catch(() => {});
                    if (config.ticketsAbertos[canal.id]) {
                        delete config.ticketsAbertos[canal.id];
                        apagados++;
                    }
                }
            }

            storage.salvarServidor(interaction.guildId, config);
            await interaction.editReply({ content: `✅ ${apagados} ticket(s) apagado(s) com sucesso.` });
        } catch (erro) {
            await responderErro(interaction, erro, '/fechar');
        }
    }
};
