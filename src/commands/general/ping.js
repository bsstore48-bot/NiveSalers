const { SlashCommandBuilder } = require('discord.js');
const { baseEmbed } = require('../../utils/embeds.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('ping')
        .setDescription('Mostra a latência e o status do bot'),

    async execute(interaction) {
        const sent = await interaction.reply({
            content: '🏓 Calculando latência...',
            fetchReply: true
        });

        const roundtrip = sent.createdTimestamp - interaction.createdTimestamp;
        const wsPing = Math.round(interaction.client.ws.ping);
        const uptime = Math.floor(process.uptime());

        const embed = baseEmbed()
            .setTitle('🏓 Pong!')
            .setColor('#5865F2')
            .addFields(
                { name: '📡 Latência de Resposta', value: `\`${roundtrip}ms\``, inline: true },
                { name: '🌐 Latência da API Discord', value: `\`${wsPing}ms\``, inline: true },
                { name: '⏱ Uptime', value: `<t:${Math.floor(Date.now() / 1000) - uptime}:R>`, inline: true }
            );

        await interaction.editReply({ content: null, embeds: [embed] });
    }
};
