const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('ping')
        .setDescription('Exibe a latência atual do bot'),

    async execute(interaction) {
        const enviado = await interaction.reply({ content: '🏓 Calculando a latência, por favor aguarde...', fetchReply: true });
        const latencia = enviado.createdTimestamp - interaction.createdTimestamp;
        const latenciaApi = Math.round(interaction.client.ws.ping);

        const embed = new EmbedBuilder()
            .setTitle('🏓 Pong!')
            .setColor('#2b2d31')
            .addFields(
                { name: '📡 Latência do bot', value: `${latencia}ms`, inline: true },
                { name: '🌐 Latência da API', value: `${latenciaApi}ms`, inline: true }
            )
            .setFooter({ text: 'Nive Bots' })
            .setTimestamp();

        await interaction.editReply({ content: null, embeds: [embed] });
    }
};
