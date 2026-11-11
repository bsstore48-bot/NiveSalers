const { SlashCommandBuilder } = require('discord.js');
const fs = require('fs');
const path = require('path');
const config = require('../config.json');
const storage = require('../utils/storage.js');

const CAMINHO_CONFIG = path.join(__dirname, '..', 'config.json');

function persistirConfig() {
    fs.writeFileSync(CAMINHO_CONFIG, JSON.stringify(config, null, 2));
}

function ehDono(userId) {
    return userId === config.donoId;
}

function ehAdmin(userId) {
    return ehDono(userId) || (Array.isArray(config.admins) && config.admins.includes(userId));
}

module.exports = {
    data: new SlashCommandBuilder()
        .setName('admin-plano')
        .setDescription('Gerencia os planos dos servidores e os administradores do bot')
        .addSubcommand(sub =>
            sub.setName('add')
                .setDescription('Adiciona um plano a um servidor')
                .addStringOption(opt =>
                    opt.setName('plano')
                        .setRequired(true)
                        .setDescription('Plano a ser atribuído ao servidor')
                        .addChoices(
                            { name: 'VIP', value: 'VIP' },
                            { name: 'Premium', value: 'Premium' }
                        )
                )
                .addStringOption(opt =>
                    opt.setName('servidor')
                        .setRequired(true)
                        .setDescription('ID do servidor')
                )
        )
        .addSubcommand(sub =>
            sub.setName('remove')
                .setDescription('Remove o plano de um servidor, retornando-o ao plano Gratuito')
                .addStringOption(opt =>
                    opt.setName('servidor')
                        .setRequired(true)
                        .setDescription('ID do servidor')
                )
        )
        .addSubcommand(sub =>
            sub.setName('admin-add')
                .setDescription('🔒 Exclusivo do dono: concede permissão de administrador do bot')
                .addStringOption(opt =>
                    opt.setName('usuario')
                        .setRequired(true)
                        .setDescription('ID do usuário')
                )
        )
        .addSubcommand(sub =>
            sub.setName('admin-remove')
                .setDescription('🔒 Exclusivo do dono: revoga a permissão de administrador do bot')
                .addStringOption(opt =>
                    opt.setName('usuario')
                        .setRequired(true)
                        .setDescription('ID do usuário')
                )
        ),

    async execute(interaction) {
        const sub = interaction.options.getSubcommand();

        if (sub === 'admin-add' || sub === 'admin-remove') {
            if (!ehDono(interaction.user.id)) {
                return interaction.reply({ content: '🔒 Apenas o dono do bot pode gerenciar os administradores.', flags: 64 });
            }

            const usuarioId = interaction.options.getString('usuario');

            if (usuarioId === config.donoId) {
                return interaction.reply({ content: '⚠️ O dono do bot já possui acesso total e não pode ser removido ou adicionado como administrador.', flags: 64 });
            }

            if (!Array.isArray(config.admins)) config.admins = [];

            if (sub === 'admin-add') {
                if (config.admins.includes(usuarioId)) {
                    return interaction.reply({ content: 'ℹ️ Este usuário já é um administrador do bot.', flags: 64 });
                }
                config.admins.push(usuarioId);
                persistirConfig();
                return interaction.reply({ content: `✅ O usuário <@${usuarioId}> agora é administrador do bot e pode definir planos dos servidores.`, flags: 64 });
            } else {
                config.admins = config.admins.filter(id => id !== usuarioId);
                persistirConfig();
                return interaction.reply({ content: `✅ O usuário <@${usuarioId}> não é mais administrador do bot.`, flags: 64 });
            }
        }

        if (!ehAdmin(interaction.user.id)) {
            return interaction.reply({ content: '🔒 Apenas o dono ou os administradores do bot podem utilizar este comando.', flags: 64 });
        }

        const servidorId = interaction.options.getString('servidor');

        if (sub === 'add') {
            const plano = interaction.options.getString('plano');
            const configGuild = storage.getServidor(servidorId);
            configGuild.plano = plano;
            storage.salvarServidor(servidorId, configGuild);
            return interaction.reply({ content: `✅ O servidor \`${servidorId}\` agora possui o plano **${plano}**.`, flags: 64 });
        } else {
            const configGuild = storage.getServidor(servidorId);
            configGuild.plano = 'Gratis';
            storage.salvarServidor(servidorId, configGuild);
            return interaction.reply({ content: `✅ O servidor \`${servidorId}\` retornou ao plano **Gratuito**.`, flags: 64 });
        }
    }
};
