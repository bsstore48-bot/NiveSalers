const { SlashCommandBuilder, PermissionFlagsBits, ChannelType } = require('discord.js');
const { baseEmbed, successEmbed } = require('../../utils/embeds.js');
const cloudStorage = require('../../services/cloudStorage.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('config')
        .setDescription('Gerencia as configurações do servidor na nuvem')
        .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
        .addSubcommand(sub =>
            sub.setName('ver')
                .setDescription('Visualiza a configuração atual deste servidor')
        )
        .addSubcommand(sub =>
            sub.setName('definir-canal-logs')
                .setDescription('Define o canal onde logs serão enviados')
                .addChannelOption(opt =>
                    opt.setName('canal')
                        .setDescription('Canal de texto para logs')
                        .addChannelTypes(ChannelType.GuildText)
                        .setRequired(true)
                )
        )
        .addSubcommand(sub =>
            sub.setName('mensagem-boas-vindas')
                .setDescription('Define a mensagem de boas-vindas')
                .addStringOption(opt =>
                    opt.setName('texto')
                        .setDescription('Texto da mensagem')
                        .setRequired(true)
                )
        ),

    async execute(interaction) {
        const sub = interaction.options.getSubcommand();
        const cfg = cloudStorage.getGuildConfig(interaction.guild.id);

        if (sub === 'ver') {
            const embed = baseEmbed()
                .setTitle(`⚙️ Configurações de ${interaction.guild.name}`)
                .addFields(
                    { name: 'Plano do Servidor', value: `\`${cfg.plan || 'Standard'}\``, inline: true },
                    { name: 'Canal de Logs', value: cfg.logsChannel ? `<#${cfg.logsChannel}>` : '`Não definido`', inline: true },
                    { name: 'Mensagem de Boas-Vindas', value: cfg.welcomeMessage || '`Padrão`' },
                    { name: 'Última Atualização', value: cfg.updatedAt ? `<t:${Math.floor(new Date(cfg.updatedAt).getTime() / 1000)}:R>` : '`N/A`' }
                );
            return interaction.reply({ embeds: [embed] });
        }

        if (sub === 'definir-canal-logs') {
            const canal = interaction.options.getChannel('canal');
            cfg.logsChannel = canal.id;
            cloudStorage.saveGuildConfig(interaction.guild.id, cfg);

            return interaction.reply({
                embeds: [successEmbed('Canal de Logs Definido', `O canal ${canal} foi configurado e sincronizado com a nuvem do Render.`)],
                ephemeral: true
            });
        }

        if (sub === 'mensagem-boas-vindas') {
            const texto = interaction.options.getString('texto');
            cfg.welcomeMessage = texto;
            cloudStorage.saveGuildConfig(interaction.guild.id, cfg);

            return interaction.reply({
                embeds: [successEmbed('Mensagem Atualizada', `A nova mensagem de boas-vindas foi salva com sucesso e persistida na nuvem.`)],
                ephemeral: true
            });
        }
    }
};
