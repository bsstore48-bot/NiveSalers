const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('help')
        .setDescription('Exibe todos os comandos e funcionalidades disponíveis do bot'),

    async execute(interaction) {
        const embed = new EmbedBuilder()
            .setColor('#2b2d31')
            .setTitle('🎫 Sistema de Tickets — Central de Ajuda')
            .setDescription('Confira abaixo os comandos e as funcionalidades disponíveis para o seu servidor.')
            .addFields(
                { name: '⚙️ Configuração', value: '`/configurar-ticket` — Configura todo o sistema de tickets do servidor.' },
                { name: '📤 Enviar Painel', value: 'Dentro de `/configurar-ticket`, selecione a opção "Enviar Painel".' },
                { name: '🧩 Painéis Interativos', value: 'Botões exclusivos para atendentes e para membros dentro de cada ticket.' },
                { name: '🔔 Notificações Automáticas', value: 'O bot avisa automaticamente no ticket caso o dono do ticket saia do servidor.' },
                { name: '📝 Notas e Prioridade', value: 'Atendentes podem adicionar notas internas e definir a prioridade de cada ticket.' },
                { name: 'Transcript', value: 'Arquivo TXT gratuito para todos; transcript via site disponível no Premium/VIP.' },
                { name: '⭐ Feedback (VIP)', value: 'Sistema de avaliação por DM após o encerramento do atendimento.' },
                { name: 'Banner e Footer (Premium/VIP)', value: 'Configure banner, footer e autor do footer no painel.' },
                { name: 'Canal de Voz', value: 'Atendentes podem criar uma sala de suporte com confirmação, ou ativar a criação automática (voz obrigatória).' },
                { name: '🤖 IA no Atendimento (Premium/VIP)', value: 'Responde os clientes automaticamente até que um atendente envie uma mensagem ou assuma o ticket.' },
                { name: '🚫 Blacklist', value: 'Impede usuários específicos de abrirem novos tickets.' },
                { name: '🔒 /fechar', value: 'Apaga de uma vez todos os tickets abertos da categoria/canal configurado.' },
                { name: '📊 /status', value: 'Mostra o status e a demanda atual dos tickets do servidor.' },
                { name: '🏓 /ping', value: 'Mostra a latência atual do bot.' }
            )
            .setFooter({ text: 'NiveTickets v9' })
            .setTimestamp();

        await interaction.reply({ embeds: [embed], flags: 64 });
    }
};
