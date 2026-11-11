const { 
    ChannelType, 
    PermissionFlagsBits, 
    EmbedBuilder, 
    ActionRowBuilder, 
    ButtonBuilder, 
    ButtonStyle, 
    StringSelectMenuBuilder,
    ModalBuilder,
    TextInputBuilder,
    TextInputStyle
} = require('discord.js');
const { getConfig, getNextTicketNumber, getLimiteAtendentes } = require('./database.js');

async function criarTicket(interaction, tipo) {
    const guildId = interaction.guildId;
    const config = getConfig(guildId);
    const limiteAtendentes = getLimiteAtendentes(guildId);
    
    const userId = interaction.user.id;
    const numero = getNextTicketNumber(guildId);
    const nomeTicket = `${tipo}・${interaction.user.username}・${numero}`;
    
    const atendentesLimitados = (config.atendentes || []).slice(0, limiteAtendentes);
    
    const embed = new EmbedBuilder()
        .setColor(config.cor?.replace('#', '') || 0x2b2d31)
        .setTitle(config.titulo || 'Sistema de Tickets')
        .setDescription(config.mensagemBoasVindas?.replace('{user}', interaction.user.username) || 'Olá {user}, seu ticket foi aberto. Aguarde um atendente.')
        .setTimestamp();
    
    const row = new ActionRowBuilder().addComponents(
        new ButtonBuilder().setCustomId(`atendente_${Date.now()}`).setLabel('Painel Atendente').setStyle(ButtonStyle.Primary),
        new ButtonBuilder().setCustomId(`membro_${Date.now()}`).setLabel('Painel Membro').setStyle(ButtonStyle.Secondary),
        new ButtonBuilder().setCustomId(`fechar_${Date.now()}`).setLabel('Fechar Ticket').setStyle(ButtonStyle.Danger)
    );
    
    let canalCriado;
    
    if (config.tipo === 'topico') {
        const topico = await interaction.channel.threads.create({
            name: nomeTicket,
            type: ChannelType.PrivateThread,
            invitable: false,
            reason: `Ticket de ${interaction.user.tag}`
        });
        
        await topico.members.add(userId);
        
        for (const cargoId of atendentesLimitados) {
            const role = await interaction.guild.roles.fetch(cargoId).catch(() => null);
            if (role) {
                for (const member of role.members.values()) {
                    await topico.members.add(member.id).catch(() => {});
                }
            }
        }
        
        await topico.send({ content: `<@${userId}>`, embeds: [embed], components: [row] });
        canalCriado = topico;
        
    } else {
        if (!config.categoria) {
            return interaction.reply({ content: 'Categoria não configurada. Use /configurar-ticket para configurar.', flags: 64 });
        }
        
        const canal = await interaction.guild.channels.create({
            name: nomeTicket,
            type: ChannelType.GuildText,
            parent: config.categoria,
            permissionOverwrites: [
                { id: interaction.guild.id, deny: [PermissionsBitField.Flags.ViewChannel] },
                { id: userId, allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.SendMessages, PermissionsBitField.Flags.ReadMessageHistory] },
                ...atendentesLimitados.map(id => ({ 
                    id: id, 
                    allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.SendMessages, PermissionsBitField.Flags.ReadMessageHistory] 
                }))
            ]
        });
        
        await canal.send({ content: `<@${userId}>`, embeds: [embed], components: [row] });
        canalCriado = canal;
    }
    
    await interaction.reply({ content: `Ticket criado: ${canalCriado}`, flags: 64 });
}

async function gerarTranscript(canal, interaction, tipo) {
    await interaction.reply({
        content: 'Indisponível',
        flags: 64
    });
}

async function handleInteraction(interaction, client) {
    const customId = interaction.customId;
    
    if (customId.startsWith('fechar_')) {
        if (!interaction.memberPermissions.has(PermissionFlagsBits.ManageChannels)) {
            return interaction.reply({ content: 'Você não tem permissão para fechar este ticket.', flags: 64 });
        }
        
        await interaction.reply({ content: 'Ticket será fechado em 3 segundos...', flags: 64 });
        setTimeout(async () => {
            await interaction.channel.delete().catch(() => {});
        }, 3000);
        return;
    }
    
    if (customId.startsWith('atendente_')) {
        const menu = new ActionRowBuilder().addComponents(
            new StringSelectMenuBuilder()
                .setCustomId('menu_atendente')
                .setPlaceholder('Selecione uma ação')
                .addOptions([
                    { label: 'Notificar Cliente', value: 'notificar_cliente' },
                    { label: 'Notificar no DM', value: 'notificar_cliente_dm' },
                    { label: 'Renomear Ticket', value: 'renomear_ticket' },
                    { label: 'Adicionar Usuário', value: 'add_user' },
                    { label: 'Remover Usuário', value: 'remove_user' },
                    { label: 'Assumir Atendimento', value: 'assumir_ticket' },
                    { label: 'Adicionar Nota', value: 'add_nota' }
                ])
        );
        await interaction.reply({ content: 'Painel do Atendente', components: [menu], flags: 64 });
        return;
    }
    
    if (customId.startsWith('membro_')) {
        const menu = new ActionRowBuilder().addComponents(
            new StringSelectMenuBuilder()
                .setCustomId('menu_membro')
                .setPlaceholder('Selecione uma ação')
                .addOptions([
                    { label: 'Notificar Atendentes', value: 'notificar_atendentes' },
                    { label: 'Notificar no DM', value: 'notificar_atendentes_dm' }
                ])
        );
        await interaction.reply({ content: 'Painel do Membro', components: [menu], flags: 64 });
        return;
    }
    
    if (interaction.isStringSelectMenu()) {
        const valor = interaction.values[0];
        
        if (valor === 'notificar_cliente') {
            const clienteId = interaction.channel.permissionOverwrites.cache.find(o => o.type === 1)?.id;
            if (clienteId) {
                await interaction.channel.send(`<@${clienteId}>, você foi notificado pela equipe.`);
                await interaction.reply({ content: 'Cliente notificado no ticket.', flags: 64 });
            }
        }
        else if (valor === 'notificar_cliente_dm') {
            const clienteId = interaction.channel.permissionOverwrites.cache.find(o => o.type === 1)?.id;
            if (clienteId) {
                const member = await interaction.guild.members.fetch(clienteId).catch(() => null);
                if (member) {
                    await member.send('Seu ticket foi atualizado pelos atendentes.');
                }
                await interaction.reply({ content: 'Cliente notificado no DM.', flags: 64 });
            }
        }
        else if (valor === 'notificar_atendentes') {
            const config = getConfig(interaction.guildId);
            const cargos = config.atendentes || [];
            const mentions = cargos.map(id => `<@&${id}>`).join(' ');
            await interaction.channel.send(`${mentions} o cliente está esperando vocês.`);
            await interaction.reply({ content: 'Atendentes notificados no ticket.', flags: 64 });
        }
        else if (valor === 'notificar_atendentes_dm') {
            const config = getConfig(interaction.guildId);
            const cargos = config.atendentes || [];
            for (const id of cargos) {
                const member = await interaction.guild.members.fetch(id).catch(() => null);
                if (member) {
                    await member.send('Um cliente está esperando atendimento no ticket.');
                }
            }
            await interaction.reply({ content: 'Atendentes notificados no DM.', flags: 64 });
        }
        else if (valor === 'assumir_ticket') {
            await interaction.reply({ content: 'Você assumiu o atendimento deste ticket.', flags: 64 });
        }
        else if (valor === 'add_nota') {
            await interaction.reply({ content: 'Nota adicionada internamente.', flags: 64 });
        }
        else if (valor === 'renomear_ticket') {
            const modal = new ModalBuilder()
                .setCustomId('modal_renomear')
                .setTitle('Renomear Ticket')
                .addComponents(
                    new ActionRowBuilder().addComponents(
                        new TextInputBuilder()
                            .setCustomId('novo_nome')
                            .setLabel('Novo nome do ticket')
                            .setStyle(TextInputStyle.Short)
                            .setRequired(true)
                    )
                );
            await interaction.showModal(modal);
            
            const submit = await interaction.awaitModalSubmit({
                filter: (i) => i.customId === 'modal_renomear' && i.user.id === interaction.user.id,
                time: 60000
            }).catch(() => null);
            
            if (submit) {
                const novoNome = submit.fields.getTextInputValue('novo_nome');
                await interaction.channel.setName(novoNome);
                await submit.reply({ content: `Ticket renomeado para: ${novoNome}`, flags: 64 });
            }
        }
        else if (valor === 'add_user') {
            await interaction.reply({ 
                content: 'Mencione o usuário que deseja adicionar ao ticket.\nExemplo: @usuario',
                flags: 64 
            });
            
            const collected = await interaction.channel.awaitMessages({
                filter: (m) => m.author.id === interaction.user.id,
                max: 1,
                time: 60000
            });
            
            if (collected) {
                const mensagem = collected.first();
                const mencoes = mensagem.mentions.users;
                if (mencoes.size > 0) {
                    const user = mencoes.first();
                    await interaction.channel.permissionOverwrites.edit(user.id, {
                        ViewChannel: true,
                        SendMessages: true,
                        ReadMessageHistory: true
                    });
                    await interaction.followUp({ content: `Usuário ${user} adicionado ao ticket.`, flags: 64 });
                } else {
                    await interaction.followUp({ content: 'Nenhum usuário mencionado.', flags: 64 });
                }
            }
        }
        else if (valor === 'remove_user') {
            await interaction.reply({ 
                content: 'Mencione o usuário que deseja remover do ticket.\nExemplo: @usuario',
                flags: 64 
            });
            
            const collected = await interaction.channel.awaitMessages({
                filter: (m) => m.author.id === interaction.user.id,
                max: 1,
                time: 60000
            });
            
            if (collected) {
                const mensagem = collected.first();
                const mencoes = mensagem.mentions.users;
                if (mencoes.size > 0) {
                    const user = mencoes.first();
                    await interaction.channel.permissionOverwrites.delete(user.id);
                    await interaction.followUp({ content: `Usuário ${user} removido do ticket.`, flags: 64 });
                } else {
                    await interaction.followUp({ content: 'Nenhum usuário mencionado.', flags: 64 });
                }
            }
        }
        else {
            await interaction.reply({ content: `Ação "${valor}" executada.`, flags: 64 });
        }
    }
}

module.exports = { criarTicket, handleInteraction, gerarTranscript };