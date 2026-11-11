const { EmbedBuilder } = require('discord.js');
const config = require('../config/index.js');

function baseEmbed() {
    return new EmbedBuilder()
        .setColor(config.embedColor)
        .setFooter({ text: `${config.botName} • v${config.version}` })
        .setTimestamp();
}

function successEmbed(titulo, descricao) {
    return baseEmbed()
        .setColor('#57F287')
        .setTitle(`✅ ${titulo}`)
        .setDescription(descricao);
}

function errorEmbed(titulo, descricao) {
    return baseEmbed()
        .setColor('#ED4245')
        .setTitle(`❌ ${titulo}`)
        .setDescription(descricao);
}

function infoEmbed(titulo, descricao) {
    return baseEmbed()
        .setColor('#5865F2')
        .setTitle(`ℹ️ ${titulo}`)
        .setDescription(descricao);
}

module.exports = {
    baseEmbed,
    successEmbed,
    errorEmbed,
    infoEmbed
};
