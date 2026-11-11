const { EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const storage = require('./storage.js');

function montarBotoesNota(guildId) {
    const linha1 = new ActionRowBuilder();
    const linha2 = new ActionRowBuilder();
    for (let nota = 1; nota <= 5; nota++) {
        linha1.addComponents(
            new ButtonBuilder().setCustomId(`feedback_nota_${guildId}_${nota}`).setLabel(`${nota}`).setStyle(ButtonStyle.Secondary)
        );
    }
    for (let nota = 6; nota <= 10; nota++) {
        linha2.addComponents(
            new ButtonBuilder().setCustomId(`feedback_nota_${guildId}_${nota}`).setLabel(`${nota}`).setStyle(ButtonStyle.Secondary)
        );
    }
    return [linha1, linha2];
}

async function enviarPedidoFeedback(client, guildId, userId, ticketNome) {
    const config = storage.getServidor(guildId);
    if (!config.feedback.ativo) return;

    const usuario = await client.users.fetch(userId).catch(() => null);
    if (!usuario) return;

    const embed = new EmbedBuilder()
        .setColor(config.cor || '#2b2d31')
        .setTitle('⭐ Avalie o seu atendimento')
        .setDescription(`O seu ticket **${ticketNome}** foi encerrado com sucesso.\n\nPor gentileza, escolha uma nota de 1 a 10 para avaliar o atendimento recebido.`);

    const enviado = await usuario.send({ embeds: [embed], components: montarBotoesNota(guildId) }).catch(() => null);
    if (!enviado) return;

    config.feedback.pendentes[userId] = {
        ticket: ticketNome,
        fechadoEm: Date.now()
    };
    storage.salvarServidor(guildId, config);
}

function temFeedbackPendente(guildId, userId) {
    const config = storage.getServidor(guildId);
    return Boolean(config.feedback?.pendentes?.[userId]);
}

module.exports = { enviarPedidoFeedback, temFeedbackPendente };
