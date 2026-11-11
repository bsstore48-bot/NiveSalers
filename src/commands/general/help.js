const { SlashCommandBuilder } = require('discord.js');
const { baseEmbed } = require('../../utils/embeds.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('help')
        .setDescription('Mostra todos os comandos disponíveis no bot'),

    async execute(interaction, client) {
        const embed = baseEmbed()
            .setTitle('📖 Central de Ajuda — NiveSalers')
            .setDescription('Aqui estão os comandos slash registrados e prontos para uso no seu servidor:\n\n' +
                '### 🛠 Geral\n' +
                '• `/ping` — Exibe a latência em tempo real e tempo online.\n' +
                '• `/info` — Exibe estatísticas de servidores, memória e status da nuvem.\n' +
                '• `/help` — Mostra este menu explicativo.\n\n' +
                '### ⚙️ Administração\n' +
                '• `/config ver` — Exibe as configurações salvas do servidor na nuvem.\n' +
                '• `/config definir-canal-logs` — Define o canal de logs e auditoria.\n' +
                '• `/config mensagem-boas-vindas` — Altera o texto de boas-vindas.\n' +
                '• `/clear` — Apaga mensagens em massa de forma rápida e segura.\n\n' +
                '### ☁️ Persistência em Nuvem (Render)\n' +
                'Todas as configurações que você define são salvas com **backup automático em nuvem** para nunca se perderem após reinicializações no Render.')
            .setColor('#5865F2');

        await interaction.reply({ embeds: [embed] });
    }
};
