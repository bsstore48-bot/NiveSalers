const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const storage = require('../utils/storage.js');
const { responderErro } = require('../utils/safe.js');

function calcularDemanda(quantidade) {
    if (quantidade > 100) return { texto: 'Muito alta', cor: '#ED4245' };
    if (quantidade > 50) return { texto: 'Alta', cor: '#F1C40F' };
    if (quantidade > 25) return { texto: 'Média', cor: '#5865F2' };
    return { texto: 'Baixa', cor: '#57F287' };
}

module.exports = {
    data: new SlashCommandBuilder()
        .setName('status')
        .setDescription('Mostra o status atual dos tickets deste servidor'),

    async execute(interaction) {
        try {
            const config = storage.getServidor(interaction.guildId);
            const tickets = Object.entries(config.ticketsAbertos || {});
            const total = tickets.length;
            const semResponsavel = tickets.filter(([, t]) => !t.responsavel).length;
            const comIa = tickets.filter(([, t]) => t.iaAtiva).length;
            const porPrioridade = { Baixa: 0, Normal: 0, Alta: 0 };
            for (const [, t] of tickets) porPrioridade[t.prioridade || 'Normal']++;

            const demanda = calcularDemanda(total);

            const embed = new EmbedBuilder()
                .setColor(demanda.cor)
                .setTitle('📊 Status dos Tickets')
                .addFields(
                    { name: 'Tickets abertos', value: `${total}`, inline: true },
                    { name: 'Demanda atual', value: demanda.texto, inline: true },
                    { name: 'Sem atendente', value: `${semResponsavel}`, inline: true },
                    { name: 'Com IA ativa', value: `${comIa}`, inline: true },
                    { name: 'Plano do servidor', value: config.plano || 'Gratis', inline: true },
                    { name: 'Prioridade Baixa/Normal/Alta', value: `${porPrioridade.Baixa} / ${porPrioridade.Normal} / ${porPrioridade.Alta}`, inline: true }
                )
                .setFooter({ text: 'NiveTickets v9' })
                .setTimestamp();

            await interaction.reply({ embeds: [embed], flags: 64 });
        } catch (erro) {
            await responderErro(interaction, erro, '/status');
        }
    }
};
