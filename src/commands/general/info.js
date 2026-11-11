const { SlashCommandBuilder, version: djsVersion } = require('discord.js');
const { baseEmbed } = require('../../utils/embeds.js');
const config = require('../../config/index.js');
const cloudStorage = require('../../services/cloudStorage.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('info')
        .setDescription('Exibe informações detalhadas do bot e status da nuvem'),

    async execute(interaction, client) {
        const cloud = cloudStorage.getStatus();
        const memMb = (process.memoryUsage().heapUsed / 1024 / 1024).toFixed(1);

        const embed = baseEmbed()
            .setTitle(`ℹ️ Informações sobre ${config.botName}`)
            .setDescription('Bot desenvolvido em JavaScript (Node.js) com alta resiliência e suporte à hospedagem 24/7 no Render.')
            .addFields(
                { name: '🤖 Versão do Bot', value: `\`v${config.version}\``, inline: true },
                { name: '📦 Discord.js', value: `\`v${djsVersion}\``, inline: true },
                { name: '⚡ Node.js', value: `\`${process.version}\``, inline: true },
                { name: '🏰 Servidores', value: `\`${client.guilds.cache.size}\``, inline: true },
                { name: '👥 Usuários', value: `\`${client.users.cache.size}\``, inline: true },
                { name: '🧠 Memória Usada', value: `\`${memMb} MB\``, inline: true },
                { name: '☁️ Cloud Sync (Render)', value: cloud.enabled ? '`Ativo (GitHub Cloud)`' : '`Local`', inline: true },
                { name: '🔄 Último Backup', value: cloud.lastSync ? `<t:${Math.floor(cloud.lastSync.getTime() / 1000)}:R>` : '`Nenhum ainda`', inline: true }
            );

        await interaction.reply({ embeds: [embed] });
    }
};
