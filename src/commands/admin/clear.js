const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { successEmbed, errorEmbed } = require('../../utils/embeds.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('clear')
        .setDescription('Apaga uma quantidade específica de mensagens do canal')
        .setDefaultMemberPermissions(PermissionFlagsBits.ManageMessages)
        .addIntegerOption(opt =>
            opt.setName('quantidade')
                .setDescription('Número de mensagens a apagar (entre 1 e 100)')
                .setRequired(true)
                .setMinValue(1)
                .setMaxValue(100)
        ),

    async execute(interaction) {
        const quantidade = interaction.options.getInteger('quantidade');

        try {
            const deleted = await interaction.channel.bulkDelete(quantidade, true);
            const count = deleted.size;

            return interaction.reply({
                embeds: [successEmbed('Mensagens Apagadas', `Foram limpas **${count}** mensagem(ns) deste canal com sucesso.`)],
                ephemeral: true
            });
        } catch (err) {
            return interaction.reply({
                embeds: [errorEmbed('Erro ao Apagar Mensagens', 'Não foi possível apagar as mensagens. Verifique se as mensagens possuem mais de 14 dias.')],
                ephemeral: true
            });
        }
    }
};
