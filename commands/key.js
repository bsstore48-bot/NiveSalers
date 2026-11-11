const { SlashCommandBuilder, EmbedBuilder, PermissionFlagsBits } = require('discord.js');
const fs = require('fs');
const path = require('path');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('key')
        .setDescription('Ativa uma key VIP ou Premium para este servidor')
        .addStringOption(option =>
            option.setName('chave')
                .setDescription('Digite sua key de ativação')
                .setRequired(true))
        .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild),

    async execute(interaction) {
        if (!interaction.member.permissions.has(PermissionFlagsBits.ManageGuild)) {
            return interaction.reply({
                content: '❌ Você precisa da permissão **Gerenciar Servidor** para usar este comando!',
                flags: 64
            });
        }

        const keyInserida = interaction.options.getString('chave');
        const serverId = interaction.guild.id;

        try {
            const keysPath = path.join(__dirname, '../keys.json');
            const keysData = JSON.parse(fs.readFileSync(keysPath, 'utf8'));

            const storage = require('../utils/storage.js');
            const serverData = storage.getServidor(serverId);

            let keyEncontrada = false;
            let tipoKey = null;
            let keyName = null;

            for (const [chave, valor] of Object.entries(keysData)) {
                if (valor === keyInserida) {
                    keyEncontrada = true;
                    keyName = chave;
                    if (chave.toLowerCase().includes('vip')) {
                        tipoKey = 'VIP';
                    } else if (chave.toLowerCase().includes('premium')) {
                        tipoKey = 'Premium';
                    }
                    break;
                }
            }

            if (!keyEncontrada) {
                return interaction.reply({
                    content: '❌ Key inválida! Esta key não existe no sistema.',
                    flags: 64
                });
            }

            if (keysData[keyName] === "USADA") {
                return interaction.reply({
                    content: '❌ Esta key já foi utilizada!',
                    flags: 64
                });
            }

            if (serverData.plano === tipoKey) {
                return interaction.reply({
                    content: `❌ Este servidor já possui o plano ${tipoKey}!`,
                    flags: 64
                });
            }

            keysData[keyName] = "USADA";
            serverData.plano = tipoKey;

            fs.writeFileSync(keysPath, JSON.stringify(keysData, null, 2));
            storage.salvarServidor(serverId, serverData);

            const embed = new EmbedBuilder()
                .setColor(tipoKey === 'VIP' ? '#FFD700' : '#9B59B6')
                .setTitle('✅ Key Ativada com Sucesso!')
                .setDescription(`O servidor **${interaction.guild.name}** agora possui o plano **${tipoKey}**`)
                .addFields(
                    { name: 'Key Utilizada', value: `\`${keyInserida}\`` },
                    { name: 'Plano', value: tipoKey },
                    { name: 'Ativado por', value: `${interaction.user.tag}` },
                    { name: 'Data', value: new Date().toLocaleString('pt-BR') }
                )
                .setThumbnail(interaction.guild.iconURL({ dynamic: true }))
                .setTimestamp()
                .setFooter({ 
                    text: 'Nive Bots - Sistema de Keys',
                    iconURL: interaction.client.user.displayAvatarURL()
                });

            await interaction.reply({ embeds: [embed] });

        } catch (error) {
            console.error('Erro ao processar key:', error);
            await interaction.reply({
                content: '❌ Ocorreu um erro ao processar a key. Tente novamente mais tarde.',
                flags: 64
            });
        }
    }
};

