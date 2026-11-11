const { EmbedBuilder } = require('discord.js');
function embedEvento({ titulo, cor = '#5865F2', descricao, campos = [], guild, ticket, autor }) {
    const embed = new EmbedBuilder().setColor(cor).setTitle(titulo).setDescription(descricao || null).addFields(campos).setTimestamp();
    if (guild) embed.setAuthor({ name: guild.name, iconURL: guild.iconURL?.({ dynamic: true }) || undefined });
    if (ticket) embed.addFields({ name: 'Ticket', value: `\`${ticket.nome || ticket.id}\``, inline: true });
    if (autor) embed.addFields({ name: 'Responsável', value: `${autor}`, inline: true });
    return embed;
}
async function enviar(config, guild, dados) {
    if (!config.logs) return;
    const canal = guild.channels.cache.get(config.logs) || await guild.channels.fetch(config.logs).catch(() => null);
    if (canal?.isTextBased()) await canal.send({ embeds: [embedEvento({ ...dados, guild })] }).catch(() => {});
}
module.exports = { embedEvento, enviar };
