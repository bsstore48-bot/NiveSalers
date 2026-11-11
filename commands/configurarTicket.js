const { SlashCommandBuilder, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, StringSelectMenuBuilder, RoleSelectMenuBuilder, ChannelSelectMenuBuilder, ModalBuilder, TextInputBuilder, TextInputStyle, ChannelType, PermissionsBitField } = require('discord.js');
const storage = require('../utils/storage.js');
const { responderErro } = require('../utils/safe.js');
const { getLimiteAtendentes } = require('../utils/premiumVIP.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('configurar-ticket')
        .setDescription('Configura o sistema de tickets do servidor'),

    async execute(interaction) {
        if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageGuild)) {
            return interaction.reply({ content: 'Você precisa da permissão "Gerenciar Servidor" para utilizar este comando.', flags: 64 });
        }

        const config = storage.getServidor(interaction.guildId);
        const plano = config.plano || 'Gratis';
        const isPremium = plano === 'Premium' || plano === 'VIP';
        const isVIP = plano === 'VIP';

        function montarEmbed(cfg) {
            const status = storage.calcularConfiguracao(cfg, plano);

            let textoStatus;
            if (status.faltandoEssencial.length === 0) {
                textoStatus = `O seu sistema de tickets está **${status.percentual}%** configurado.\n\n✅ Você já configurou tudo o que é necessário, portanto já pode enviar o painel!`;
            } else {
                const itens = status.faltandoEssencial.map(item => `🔸 ${item.nome}`).join('\n');
                textoStatus = `O seu sistema de tickets está **${status.percentual}%** configurado.\n\n❌ Você ainda não configurou:\n${itens}\n\nSem essas configurações, você não pode enviar o painel de tickets.`;
            }

            const embed = new EmbedBuilder()
                .setColor(cfg.cor)
                .setTitle('Configuração de Tickets')
                .setDescription('Configure abaixo, com atenção, o sistema de tickets deste servidor.')
                .addFields(
                    { name: 'Total de Configurações', value: textoStatus, inline: false },
                    { name: 'Título', value: cfg.titulo, inline: true },
                    { name: 'Descrição', value: cfg.descricao.slice(0, 50) + '...', inline: true },
                    { name: 'Cor', value: cfg.cor, inline: true },
                    { name: 'Estilo', value: cfg.estilo === 'botao' ? 'Botões' : 'Lista Suspensa', inline: true },
                    { name: 'Modo do Painel', value: cfg.painelModo === 'um' ? `Um botão: ${cfg.botaoUnico}` : 'Vários botões', inline: true },
                    { name: 'Opções de Ticket', value: cfg.botoes.join(', '), inline: false },
                    { name: 'Categoria', value: cfg.categoria ? `<#${cfg.categoria}>` : 'Não configurada', inline: true },
                    { name: 'Tipo', value: cfg.tipo === 'canal' ? 'Canal' : 'Tópico', inline: true },
                    { name: 'Canal de Tópicos', value: cfg.canalTopico ? `<#${cfg.canalTopico}>` : 'Não configurado', inline: true },
                    { name: 'Atendentes', value: cfg.atendentes.length ? cfg.atendentes.map(r => `<@&${r}>`).join(', ') : 'Nenhum', inline: false },
                    { name: 'Plano do Servidor', value: `${plano}`, inline: true }
                );

            embed.addFields({ name: 'Canal de Logs', value: cfg.logs ? `<#${cfg.logs}>` : 'Não configurado', inline: true });

            if (isVIP) {
                embed.addFields(
                    { name: 'Horário de Atendimento', value: (cfg.horarioInicio && cfg.horarioFim) ? `${cfg.horarioInicio} às ${cfg.horarioFim}` : 'Não configurado', inline: true },
                    { name: 'Sistema de Feedback', value: cfg.feedback.ativo ? '✅ Ativado' : '❌ Desativado', inline: true },
                    { name: 'Logs de Feedback', value: cfg.feedback.canalLogs ? `<#${cfg.feedback.canalLogs}>` : 'Não configurado', inline: true },
                    { name: 'Banner do Painel', value: cfg.banner ? '✅ Configurado' : 'Não configurado', inline: true },
                    { name: 'Formato do Nome do Canal', value: `\`${cfg.nomeCanalFormato}\``, inline: true }
                );
            }

            embed.addFields({ name: 'Mensagem de Boas-Vindas', value: cfg.mensagemBoasVindas.slice(0, 50) + '...', inline: false });

            if (isPremium) {
                embed.addFields(
                    { name: 'IA no Atendimento', value: cfg.ia?.ativa ? `✅ Ativa (${cfg.ia.modoNiveIA ? 'NiveIA' : 'API Key própria'})` : '❌ Desativada', inline: true },
                    { name: 'Voz Obrigatória', value: cfg.vozObrigatoria ? '✅ Ativada' : '❌ Desativada', inline: true },
                    { name: 'Blacklist', value: `${cfg.blacklist.length} usuário(s)`, inline: true }
                );
            } else {
                embed.addFields({ name: 'Blacklist', value: `${cfg.blacklist.length} usuário(s)`, inline: true });
            }

            embed.setFooter({ text: 'NiveTickets v9' });

            return embed;
        }

        function montarMenu() {
            const opcoes = [
                { label: 'Título', value: 'titulo', description: 'Define o título do painel' },
                { label: 'Descrição', value: 'desc', description: 'Define a descrição do painel' },
                { label: 'Cor', value: 'cor', description: 'Define a cor dos embeds' },
                { label: 'Estilo', value: 'estilo', description: 'Botões ou lista suspensa no painel' },
                { label: 'Modo do Painel', value: 'modo_painel', description: 'Um botão ou vários botões' },
                { label: 'Categorias por Tipo', value: 'tipos', description: 'Configura uma categoria para cada tipo' },
                { label: 'Opções de Ticket', value: 'botoes', description: 'Define as categorias de ticket' },
                { label: 'Categoria', value: 'categoria', description: 'Categoria onde os tickets são criados' },
                { label: 'Categoria de Voz', value: 'categoria_voz', description: 'Categoria opcional para salas de suporte' },
                { label: 'Tipo', value: 'tipo', description: 'Canal de texto ou tópico' },
                { label: 'Canal de Tópicos', value: 'canal_topico', description: 'Canal único onde os tickets em tópico são criados' },
                { label: 'Atendentes', value: 'atendentes', description: 'Cargos responsáveis pelo atendimento' },
                { label: 'Boas-Vindas', value: 'mensagem', description: 'Mensagem enviada ao abrir o ticket' }
            ];

            opcoes.push({ label: 'Logs Profissionais — Grátis', value: 'logs', description: 'Canal de logs de tickets em embeds' });
            opcoes.push({ label: 'Blacklist — Grátis', value: 'blacklist', description: 'Impede usuários de abrirem tickets' });
            opcoes.push({ label: 'Voz Obrigatória — Grátis', value: 'voz_obrigatoria', description: 'Cria uma sala de voz junto com todo ticket' });

            if (isPremium) {
                opcoes.push({ label: 'Footer e Autor — Premium/VIP', value: 'footer', description: 'Personaliza o rodapé dos embeds' });
                opcoes.push({ label: 'Transcript via Site — Premium/VIP', value: 'transcript_site', description: 'Ativa ou desativa a página HTML' });
                opcoes.push({ label: 'IA no Atendimento — Premium/VIP', value: 'ia', description: 'Configura a IA que responde os clientes' });
            }

            if (isVIP) {
                opcoes.push({ label: 'Horário — VIP', value: 'horario', description: 'Horário de funcionamento do suporte' });
                opcoes.push({ label: 'Sistema de Feedback —  VIP', value: 'feedback', description: 'Ativa ou desativa a avaliação de tickets' });
                opcoes.push({ label: 'Logs de Feedback — VIP', value: 'feedback_logs', description: 'Canal onde as avaliações são registradas' });
                opcoes.push({ label: 'Banner do Painel — Premium/VIP', value: 'banner', description: 'Define uma imagem de banner para o painel' });
                opcoes.push({ label: 'Nome do Canal — VIP', value: 'nome_canal', description: 'Personaliza o formato do nome dos tickets' });
            }

            opcoes.push({ label: 'Enviar Painel', value: 'enviar', description: 'Envia o painel de abertura de tickets' });

            return new ActionRowBuilder().addComponents(
                new StringSelectMenuBuilder()
                    .setCustomId('ticket_config_menu')
                    .setPlaceholder('Selecione uma opção para configurar')
                    .addOptions(opcoes)
            );
        }

        await interaction.reply({ embeds: [montarEmbed(config)], components: [montarMenu()], flags: 64 });

        const collector = interaction.channel.createMessageComponentCollector({
            filter: (i) => i.user.id === interaction.user.id,
            time: 300000
        });

        collector.on('collect', async i => {
        try {
            if (i.user.id !== interaction.user.id) return;
            if (i.customId !== 'ticket_config_menu') return;

            const opcao = i.values[0];

            if (opcao === 'titulo') {
                const modal = new ModalBuilder().setCustomId('modal_titulo').setTitle('Configurar Título');
                modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('titulo').setLabel('Título do painel').setStyle(TextInputStyle.Short).setValue(config.titulo).setRequired(true)));
                await i.showModal(modal);
                const modalSubmit = await i.awaitModalSubmit({ filter: (m) => m.customId === 'modal_titulo' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (modalSubmit) {
                    config.titulo = modalSubmit.fields.getTextInputValue('titulo');
                    storage.salvarServidor(interaction.guildId, config);
                    await modalSubmit.update({ embeds: [montarEmbed(config)], components: [montarMenu()] });
                }
            }

            else if (opcao === 'desc') {
                const modal = new ModalBuilder().setCustomId('modal_desc').setTitle('Configurar Descrição');
                modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('desc').setLabel('Descrição do painel').setStyle(TextInputStyle.Paragraph).setValue(config.descricao).setRequired(true)));
                await i.showModal(modal);
                const modalSubmit = await i.awaitModalSubmit({ filter: (m) => m.customId === 'modal_desc' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (modalSubmit) {
                    config.descricao = modalSubmit.fields.getTextInputValue('desc');
                    storage.salvarServidor(interaction.guildId, config);
                    await modalSubmit.update({ embeds: [montarEmbed(config)], components: [montarMenu()] });
                }
            }

            else if (opcao === 'cor') {
                const modal = new ModalBuilder().setCustomId('modal_cor').setTitle('Configurar Cor');
                modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('cor').setLabel('Cor em formato hexadecimal').setStyle(TextInputStyle.Short).setValue(config.cor).setRequired(true)));
                await i.showModal(modal);
                const modalSubmit = await i.awaitModalSubmit({ filter: (m) => m.customId === 'modal_cor' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (modalSubmit) {
                    config.cor = modalSubmit.fields.getTextInputValue('cor');
                    storage.salvarServidor(interaction.guildId, config);
                    await modalSubmit.update({ embeds: [montarEmbed(config)], components: [montarMenu()] });
                }
            }

            else if (opcao === 'estilo') {
                const rowEstilo = new ActionRowBuilder().addComponents(
                    new StringSelectMenuBuilder()
                        .setCustomId('select_estilo')
                        .setPlaceholder('Selecione o estilo')
                        .addOptions([
                            { label: 'Botões', value: 'botao' },
                            { label: 'Lista Suspensa', value: 'lista' }
                        ])
                );
                await i.reply({ content: 'Selecione o estilo do painel:', components: [rowEstilo], flags: 64 });
                const select = await i.channel.awaitMessageComponent({ filter: (m) => m.customId === 'select_estilo' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (!select) return;
                config.estilo = select.values[0];
                storage.salvarServidor(interaction.guildId, config);
                await select.update({ content: `Estilo definido como: ${config.estilo === 'botao' ? 'Botões' : 'Lista Suspensa'}`, components: [] });
                await i.editReply({ embeds: [montarEmbed(config)], components: [montarMenu()] });
            }

            else if (opcao === 'modo_painel') {
                const row = new ActionRowBuilder().addComponents(new StringSelectMenuBuilder().setCustomId('select_modo_painel').setPlaceholder('Escolha o modo do painel').addOptions([
                    { label: 'Vários botões', value: 'varios', description: 'Um botão para cada tipo configurado' },
                    { label: 'Apenas um botão', value: 'um', description: 'Um botão com texto personalizado' }
                ]));
                await i.reply({ content: 'Escolha o modo do painel:', components: [row], flags: 64 });
                const select = await i.channel.awaitMessageComponent({ filter: m => m.customId === 'select_modo_painel' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (!select) return;
                config.painelModo = select.values[0];
                if (config.painelModo === 'um') {
                    const modal = new ModalBuilder().setCustomId('modal_botao_unico').setTitle('Texto do botão único').addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('texto').setLabel('Texto do botão').setStyle(TextInputStyle.Short).setValue(config.botaoUnico).setRequired(true)));
                    await select.showModal(modal);
                    const sub = await select.awaitModalSubmit({ filter: m => m.customId === 'modal_botao_unico' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                    if (sub) config.botaoUnico = sub.fields.getTextInputValue('texto').trim() || 'Abrir ticket';
                }
                storage.salvarServidor(interaction.guildId, config);
                await i.editReply({ embeds: [montarEmbed(config)], components: [montarMenu()] });
            }

            else if (opcao === 'tipos') {
                const tipos = config.botoes.map(nome => ({ nome, categoria: config.tipos[nome]?.categoria || config.categoria || null }));
                const modal = new ModalBuilder().setCustomId('modal_tipos').setTitle('Categorias por tipo').addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('dados').setLabel('tipo=categoriaID, separados por vírgula').setStyle(TextInputStyle.Paragraph).setValue(tipos.map(t => `${t.nome}=${t.categoria || ''}`).join(', ')).setRequired(false)));
                await i.showModal(modal);
                const sub = await i.awaitModalSubmit({ filter: m => m.customId === 'modal_tipos' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (sub) {
                    config.tipos = {};
                    for (const item of sub.fields.getTextInputValue('dados').split(',')) { const [nome, categoria] = item.split('=').map(v => v?.trim()); if (nome) config.tipos[nome] = { categoria: categoria || config.categoria }; }
                    storage.salvarServidor(interaction.guildId, config);
                    await sub.update({ embeds: [montarEmbed(config)], components: [montarMenu()] });
                }
            }

            else if (opcao === 'botoes') {
                const modal = new ModalBuilder().setCustomId('modal_botoes').setTitle('Configurar Opções de Ticket');
                modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('botoes').setLabel('Nomes separados por vírgula').setStyle(TextInputStyle.Paragraph).setValue(config.botoes.join(', ')).setRequired(true)));
                await i.showModal(modal);
                const modalSubmit = await i.awaitModalSubmit({ filter: (m) => m.customId === 'modal_botoes' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (modalSubmit) {
                    const botoes = modalSubmit.fields.getTextInputValue('botoes').split(',').map(b => b.trim()).filter(b => b.length);
                    const botoesUnicos = [...new Set(botoes)];
                    if (botoes.length !== botoesUnicos.length) {
                        const duplicadas = botoes.filter((item, index) => botoes.indexOf(item) !== index);
                        return modalSubmit.reply({
                            content: `As seguintes categorias estão duplicadas: ${[...new Set(duplicadas)].join(', ')}\nPor gentileza, remova as duplicatas.`,
                            flags: 64
                        });
                    }
                    config.botoes = botoes.length ? botoes : ['Suporte', 'Dúvidas', 'Reportar'];
                    storage.salvarServidor(interaction.guildId, config);
                    await modalSubmit.update({ embeds: [montarEmbed(config)], components: [montarMenu()] });
                }
            }

            else if (opcao === 'categoria') {
                const menu = new ActionRowBuilder().addComponents(
                    new ChannelSelectMenuBuilder().setCustomId('select_categoria').setPlaceholder('Pesquise a categoria').setChannelTypes(ChannelType.GuildCategory)
                );
                await i.reply({ content: 'Selecione a categoria onde os tickets serão criados:', components: [menu], flags: 64 });
                const select = await i.channel.awaitMessageComponent({ filter: (m) => m.customId === 'select_categoria' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (!select) return;
                config.categoria = select.values[0];
                storage.salvarServidor(interaction.guildId, config);
                await select.update({ content: `Categoria definida como: <#${config.categoria}>`, components: [] });
                await i.editReply({ embeds: [montarEmbed(config)], components: [montarMenu()] });
            }

            else if (opcao === 'categoria_voz') {
                const menu = new ActionRowBuilder().addComponents(
                    new ChannelSelectMenuBuilder().setCustomId('select_categoria_voz').setPlaceholder('Pesquise a categoria de voz').setChannelTypes(ChannelType.GuildCategory)
                );
                await i.reply({ content: 'Selecione a categoria opcional para canais de voz de suporte:', components: [menu], flags: 64 });
                const select = await i.channel.awaitMessageComponent({ filter: m => m.customId === 'select_categoria_voz' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (!select) return;
                config.categoriaVoz = select.values[0];
                storage.salvarServidor(interaction.guildId, config);
                await select.update({ content: `Categoria de voz definida como: <#${config.categoriaVoz}>`, components: [] });
                await i.editReply({ embeds: [montarEmbed(config)], components: [montarMenu()] });
            }

            else if (opcao === 'canal_topico') {
                const menu = new ActionRowBuilder().addComponents(
                    new ChannelSelectMenuBuilder().setCustomId('select_canal_topico').setPlaceholder('Pesquise o canal').setChannelTypes(ChannelType.GuildText)
                );
                await i.reply({ content: 'Selecione o canal único onde os tickets em tópico serão criados:', components: [menu], flags: 64 });
                const select = await i.channel.awaitMessageComponent({ filter: m => m.customId === 'select_canal_topico' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (!select) return;
                config.canalTopico = select.values[0];
                storage.salvarServidor(interaction.guildId, config);
                await select.update({ content: `Canal de tópicos definido como: <#${config.canalTopico}>`, components: [] });
                await i.editReply({ embeds: [montarEmbed(config)], components: [montarMenu()] });
            }

            else if (opcao === 'tipo') {
                const rowTipo = new ActionRowBuilder().addComponents(
                    new StringSelectMenuBuilder()
                        .setCustomId('select_tipo')
                        .setPlaceholder('Selecione o tipo')
                        .addOptions([
                            { label: 'Canal de Texto', value: 'canal' },
                            { label: 'Tópico', value: 'topico' }
                        ])
                );
                await i.reply({ content: 'Selecione o tipo de ticket:', components: [rowTipo], flags: 64 });
                const select = await i.channel.awaitMessageComponent({ filter: (m) => m.customId === 'select_tipo' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (!select) return;

                if (select.values[0] === 'topico') {
                    const avisoCategoria = (config.tipo === 'canal' && config.categoria) ? 'Sua configuração atual é categoria e não é suportada para tópicos.\n\n' : '';
                    await select.update({ content: `${avisoCategoria}Selecione abaixo o canal único onde os tickets em tópico serão criados:`, components: [new ActionRowBuilder().addComponents(new ChannelSelectMenuBuilder().setCustomId('select_canal_topico_pos_tipo').setPlaceholder('Pesquise o canal').setChannelTypes(ChannelType.GuildText))] });
                    const selectCanal = await i.channel.awaitMessageComponent({ filter: m => m.customId === 'select_canal_topico_pos_tipo' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                    if (!selectCanal) return;
                    config.tipo = 'topico';
                    config.canalTopico = selectCanal.values[0];
                    storage.salvarServidor(interaction.guildId, config);
                    await selectCanal.update({ content: `Tipo definido como: Tópico\nCanal de tópicos: <#${config.canalTopico}>`, components: [] });
                } else {
                    config.tipo = 'canal';
                    storage.salvarServidor(interaction.guildId, config);
                    await select.update({ content: 'Tipo definido como: Canal', components: [] });
                }
                await i.editReply({ embeds: [montarEmbed(config)], components: [montarMenu()] });
            }

            else if (opcao === 'atendentes') {
                const limite = getLimiteAtendentes(plano) || 10;
                const menu = new ActionRowBuilder().addComponents(
                    new RoleSelectMenuBuilder().setCustomId('select_atendentes').setPlaceholder('Pesquise os cargos de atendente').setMinValues(1).setMaxValues(Math.min(limite, 25))
                );
                await i.reply({ content: `Selecione os cargos responsáveis pelo atendimento (limite do seu plano: ${Math.min(limite, 25)}):`, components: [menu], flags: 64 });
                const select = await i.channel.awaitMessageComponent({ filter: (m) => m.customId === 'select_atendentes' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (!select) return;
                config.atendentes = select.values;
                storage.salvarServidor(interaction.guildId, config);
                await select.update({ content: `${config.atendentes.length} cargo(s) de atendente configurado(s) com sucesso.`, components: [] });
                await i.editReply({ embeds: [montarEmbed(config)], components: [montarMenu()] });
            }

            else if (opcao === 'logs') {
                const menu = new ActionRowBuilder().addComponents(
                    new ChannelSelectMenuBuilder().setCustomId('select_logs').setPlaceholder('Pesquise o canal de logs').setChannelTypes(ChannelType.GuildText)
                );
                await i.reply({ content: 'Selecione o canal de logs de tickets:', components: [menu], flags: 64 });
                const select = await i.channel.awaitMessageComponent({ filter: (m) => m.customId === 'select_logs' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (!select) return;
                config.logs = select.values[0];
                storage.salvarServidor(interaction.guildId, config);
                await select.update({ content: `Canal de logs definido como: <#${config.logs}>`, components: [] });
                await i.editReply({ embeds: [montarEmbed(config)], components: [montarMenu()] });
            }

            else if (opcao === 'blacklist') {
                const row = new ActionRowBuilder().addComponents(
                    new StringSelectMenuBuilder().setCustomId('select_blacklist_acao').setPlaceholder('O que deseja fazer?').addOptions([
                        { label: 'Adicionar usuário', value: 'add' },
                        { label: 'Remover usuário', value: 'remove' }
                    ])
                );
                await i.reply({ content: `Blacklist atual: ${config.blacklist.length ? config.blacklist.map(id => `<@${id}>`).join(', ') : 'vazia'}`, components: [row], flags: 64 });
                const acaoSel = await i.channel.awaitMessageComponent({ filter: m => m.customId === 'select_blacklist_acao' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (!acaoSel) return;
                await acaoSel.reply({ content: 'Mencione o usuário (@usuario). Você tem 1 minuto.', flags: 64 });
                const collected = await interaction.channel.awaitMessages({ filter: m => m.author.id === interaction.user.id, max: 1, time: 60000 });
                const mensagem = collected?.first();
                const alvo = mensagem?.mentions.users.first();
                if (!alvo) return i.followUp({ content: 'Nenhum usuário foi mencionado.', flags: 64 });
                if (acaoSel.customId === 'select_blacklist_acao' && acaoSel.values[0] === 'add') storage.adicionarBlacklist(config, alvo.id);
                else storage.removerBlacklist(config, alvo.id);
                storage.salvarServidor(interaction.guildId, config);
                await mensagem.delete().catch(() => {});
                await i.followUp({ content: `Blacklist atualizada. ${alvo} ${config.blacklist.includes(alvo.id) ? 'agora está bloqueado.' : 'foi removido da blacklist.'}`, flags: 64 });
                await i.editReply({ embeds: [montarEmbed(config)], components: [montarMenu()] });
            }

            else if (opcao === 'voz_obrigatoria') {
                if (!config.categoriaVoz) return i.reply({ content: 'Configure primeiro a "Categoria de Voz" antes de ativar este recurso.', flags: 64 });
                const row = new ActionRowBuilder().addComponents(
                    new StringSelectMenuBuilder().setCustomId('select_voz_obrigatoria').setPlaceholder('Ativar ou desativar').addOptions([
                        { label: 'Ativar', value: 'ativar' },
                        { label: 'Desativar', value: 'desativar' }
                    ])
                );
                await i.reply({ content: 'Todo ticket criado deve abrir automaticamente um canal de voz junto?', components: [row], flags: 64 });
                const select = await i.channel.awaitMessageComponent({ filter: m => m.customId === 'select_voz_obrigatoria' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (!select) return;
                config.vozObrigatoria = select.values[0] === 'ativar';
                storage.salvarServidor(interaction.guildId, config);
                await select.update({ content: `Voz obrigatória: ${config.vozObrigatoria ? 'Ativada' : 'Desativada'}`, components: [] });
                await i.editReply({ embeds: [montarEmbed(config)], components: [montarMenu()] });
            }

            else if (opcao === 'ia') {
                if (!isPremium) return i.reply({ content: 'Este recurso está disponível apenas para Premium ou VIP.', flags: 64 });

                const rowChave = new ActionRowBuilder().addComponents(
                    new ButtonBuilder().setCustomId('ia_tem_chave_sim').setLabel('Sim, tenho uma API Key').setStyle(ButtonStyle.Success),
                    new ButtonBuilder().setCustomId('ia_tem_chave_nao').setLabel('Não tenho').setStyle(ButtonStyle.Secondary)
                );
                await i.reply({ content: `Olá ${interaction.user}\n\nAqui você configura a IA do seu servidor.\n\nPrimeiro, você tem uma API Key de alguma IA?`, components: [rowChave], flags: 64 });

                const respostaChave = await i.channel.awaitMessageComponent({ filter: m => ['ia_tem_chave_sim', 'ia_tem_chave_nao'].includes(m.customId) && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (!respostaChave) return;

                if (respostaChave.customId === 'ia_tem_chave_sim') {
		    await respostaChave.update({ content: 'Caso você queira criar uma API Key, assista ao tutorial abaixo:\nhttps://www.youtube.com/results?search_query=como+criar+api+key+openai\n\nEnvie agora sua API Key aqui no chat (você tem 2 minutos).', components: [] });
                    const collected = await interaction.channel.awaitMessages({ filter: m => m.author.id === interaction.user.id, max: 1, time: 120000 });
                    const msgChave = collected?.first();
                    if (!msgChave) return;
                    config.ia.apiKeyPropria = msgChave.content.trim();
                    config.ia.modoNiveIA = false;
                    storage.salvarServidor(interaction.guildId, config);
                    await msgChave.delete().catch(() => {});
                    await i.followUp({ content: 'API Key salva com sucesso. Agora, preciso que você envie o prompt da IA (como ela deve se comportar). Você tem 2 minutos.', flags: 64 });
                } else {
                    await respostaChave.update({ content: 'Certo, você usará a NiveIA. Agora, preciso que você envie o prompt abaixo (como a IA deve se comportar). Você tem 2 minutos.\n\nExemplo: "Você é uma ia do servidor do bn"', components: [] });
                    config.ia.modoNiveIA = true;
                    config.ia.apiKeyPropria = null;
                    storage.salvarServidor(interaction.guildId, config);
                }

                const collectedPrompt = await interaction.channel.awaitMessages({ filter: m => m.author.id === interaction.user.id, max: 1, time: 120000 });
                const msgPrompt = collectedPrompt?.first();
                if (!msgPrompt) return;
                const promptTexto = msgPrompt.content.trim();

                const rowConfirmar = new ActionRowBuilder().addComponents(
                    new ButtonBuilder().setCustomId('ia_prompt_sim').setLabel('Sim').setStyle(ButtonStyle.Success),
                    new ButtonBuilder().setCustomId('ia_prompt_nao').setLabel('Não').setStyle(ButtonStyle.Danger),
                    new ButtonBuilder().setCustomId('ia_prompt_trocar').setLabel('Trocar').setStyle(ButtonStyle.Secondary)
                );
                const confirmMsg = await i.followUp({ content: `Certo, você configurou o prompt: "${promptTexto}"\n\nConfirme dizendo sim, negue dizendo não e troque dizendo trocar.`, components: [rowConfirmar], flags: 64 });

                const confirmacao = await i.channel.awaitMessageComponent({ filter: m => m.user.id === interaction.user.id && m.customId.startsWith('ia_prompt_'), time: 60000 }).catch(() => null);
                if (!confirmacao) return;

                if (confirmacao.customId === 'ia_prompt_sim') {
                    config.ia.prompt = promptTexto;
                    config.ia.ativa = true;
                    storage.salvarServidor(interaction.guildId, config);
                    await confirmacao.update({ content: '✅ IA configurada e ativada com sucesso!', components: [] });
                } else if (confirmacao.customId === 'ia_prompt_trocar') {
                    await confirmacao.update({ content: 'Ok, use a opção "IA no Atendimento" novamente para reenviar o prompt.', components: [] });
                } else {
                    config.ia.ativa = false;
                    storage.salvarServidor(interaction.guildId, config);
                    await confirmacao.update({ content: 'Prompt não confirmado. A IA permanece desativada.', components: [] });
                }
                await i.editReply({ embeds: [montarEmbed(config)], components: [montarMenu()] });
            }

            else if (opcao === 'mensagem') {
                const modal = new ModalBuilder().setCustomId('modal_mensagem').setTitle('Configurar Boas-Vindas');
                modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('mensagem').setLabel('Utilize {user} para o nome do cliente').setStyle(TextInputStyle.Paragraph).setValue(config.mensagemBoasVindas).setRequired(true)));
                await i.showModal(modal);
                const modalSubmit = await i.awaitModalSubmit({ filter: (m) => m.customId === 'modal_mensagem' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (modalSubmit) {
                    config.mensagemBoasVindas = modalSubmit.fields.getTextInputValue('mensagem');
                    storage.salvarServidor(interaction.guildId, config);
                    await modalSubmit.update({ embeds: [montarEmbed(config)], components: [montarMenu()] });
                }
            }

            else if (opcao === 'banner') {
                if (!isPremium) return i.reply({ content: 'Este recurso está disponível apenas para Premium ou VIP.', flags: 64 });
                const modal = new ModalBuilder().setCustomId('modal_banner').setTitle('Configurar Banner do Painel');
                modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('banner').setLabel('URL da imagem (deixe vazio para remover)').setStyle(TextInputStyle.Short).setValue(config.banner || '').setRequired(false)));
                await i.showModal(modal);
                const modalSubmit = await i.awaitModalSubmit({ filter: (m) => m.customId === 'modal_banner' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (modalSubmit) {
                    const url = modalSubmit.fields.getTextInputValue('banner').trim();
                    config.banner = url.length ? url : null;
                    storage.salvarServidor(interaction.guildId, config);
                    await modalSubmit.update({ embeds: [montarEmbed(config)], components: [montarMenu()] });
                }
            }

            else if (opcao === 'footer') {
                if (!isPremium) return i.reply({ content: 'Este recurso está disponível apenas para Premium ou VIP.', flags: 64 });
                const modal = new ModalBuilder().setCustomId('modal_footer').setTitle('Configurar Footer').addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('footer').setLabel('Texto do footer').setStyle(TextInputStyle.Short).setValue(config.footer || '').setRequired(false)), new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('autor').setLabel('Autor do footer').setStyle(TextInputStyle.Short).setValue(config.footerAutor || 'Nive Bots').setRequired(false)));
                await i.showModal(modal);
                const modalSubmit = await i.awaitModalSubmit({ filter: m => m.customId === 'modal_footer' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (modalSubmit) { config.footer = modalSubmit.fields.getTextInputValue('footer').trim() || null; config.footerAutor = modalSubmit.fields.getTextInputValue('autor').trim() || 'Nive Bots'; storage.salvarServidor(interaction.guildId, config); await modalSubmit.update({ embeds: [montarEmbed(config)], components: [montarMenu()] }); }
            }

            else if (opcao === 'transcript_site') {
                if (!isPremium) return i.reply({ content: 'Este recurso está disponível apenas para Premium ou VIP.', flags: 64 });
                const row = new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId('transcript_site_sim').setLabel('Ativar site').setStyle(ButtonStyle.Success), new ButtonBuilder().setCustomId('transcript_site_nao').setLabel('Usar somente TXT').setStyle(ButtonStyle.Secondary));
                await i.reply({ content: 'O transcript TXT continua gratuito. Escolha se o transcript via site ficará ativo.', components: [row], flags: 64 });
                const escolha = await i.channel.awaitMessageComponent({ filter: m => m.user.id === interaction.user.id && m.customId.startsWith('transcript_site_'), time: 60000 }).catch(() => null);
                if (escolha) { config.transcriptModo = escolha.customId.endsWith('sim') ? 'site' : 'txt'; storage.salvarServidor(interaction.guildId, config); await escolha.update({ content: `Transcript definido como ${config.transcriptModo === 'site' ? 'site HTML + TXT' : 'TXT gratuito'}.`, components: [] }); await i.editReply({ embeds: [montarEmbed(config)], components: [montarMenu()] }); }
            }

            else if (opcao === 'nome_canal') {
                if (!isVIP) return i.reply({ content: 'Este recurso está disponível apenas para o plano VIP.', flags: 64 });
                const modal = new ModalBuilder().setCustomId('modal_nome_canal').setTitle('Formato do Nome do Canal');
                modal.addComponents(new ActionRowBuilder().addComponents(
                    new TextInputBuilder()
                        .setCustomId('formato')
                        .setLabel('Use {tipo}, {user} e {numero}')
                        .setStyle(TextInputStyle.Short)
                        .setValue(config.nomeCanalFormato)
                        .setRequired(true)
                ));
                await i.showModal(modal);
                const modalSubmit = await i.awaitModalSubmit({ filter: (m) => m.customId === 'modal_nome_canal' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (modalSubmit) {
                    const formato = modalSubmit.fields.getTextInputValue('formato').trim();
                    config.nomeCanalFormato = formato.length ? formato : '{tipo}・{user}・{numero}';
                    storage.salvarServidor(interaction.guildId, config);
                    await modalSubmit.reply({ content: `Formato do nome do canal atualizado para: \`${config.nomeCanalFormato}\`\n\nDica: você pode substituir \`{tipo}\` por um texto fixo. Exemplo: \`Pizza・{user}・{numero}\` — mesmo que o botão continue com o nome "Suporte", o canal usará "Pizza".`, flags: 64 });
                    await i.editReply({ embeds: [montarEmbed(config)], components: [montarMenu()] });
                }
            }

            else if (opcao === 'enviar') {
                const status = storage.calcularConfiguracao(config, plano);
                if (!status.podeEnviar) {
                    const itens = status.faltandoEssencial.map(item => `${item.nome}`).join('\n');
                    return i.reply({
                        content: `Você ainda não configurou os itens essenciais:\n${itens}\n\nSomente essas configurações são obrigatórias para enviar o painel.`,
                        flags: 64
                    });
                }

                const embedPainel = new EmbedBuilder()
                    .setColor(config.cor)
                    .setTitle(config.titulo)
                    .setDescription(config.descricao);
                if (isPremium && config.footer) embedPainel.setFooter({ text: config.footer, iconURL: undefined });

                if (isPremium && config.banner) {
                    embedPainel.setImage(config.banner);
                }

                const slug = b => b.toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 45);
                if (config.painelModo === 'um') {
                    await interaction.channel.send({ embeds: [embedPainel], components: [new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId('abrir_ticket_unico').setLabel(config.botaoUnico || 'Abrir ticket').setStyle(ButtonStyle.Primary))] });
                } else if (config.estilo === 'botao') {
                    const botoes = config.botoes.slice(0, 5).map(b => new ButtonBuilder().setCustomId(`abrir_ticket_${slug(b)}`).setLabel(b.slice(0, 80)).setStyle(ButtonStyle.Primary));
                    await interaction.channel.send({ embeds: [embedPainel], components: [new ActionRowBuilder().addComponents(botoes)] });
                } else {
                    const options = config.botoes.slice(0, 25).map(b => ({ label: b.slice(0, 100), value: slug(b) }));
                    await interaction.channel.send({ embeds: [embedPainel], components: [new ActionRowBuilder().addComponents(new StringSelectMenuBuilder().setCustomId('abrir_ticket_lista').setPlaceholder('Selecione o tipo de ticket').addOptions(options))] });
                }
                await i.reply({ content: 'oainel de tickets enviado com sucesso!', flags: 64 });
            }

            else if (opcao === 'horario') {
                if (!isVIP) return i.reply({ content: 'Este recurso está disponível apenas para o plano VIP.', flags: 64 });
                const modal = new ModalBuilder().setCustomId('modal_horario').setTitle('Configurar Horário');
                modal.addComponents(
                    new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('inicio').setLabel('Horário de início (ex: 08:00)').setStyle(TextInputStyle.Short).setValue(config.horarioInicio || '').setRequired(false)),
                    new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('fim').setLabel('Horário de fim (ex: 18:00)').setStyle(TextInputStyle.Short).setValue(config.horarioFim || '').setRequired(false)),
                    new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('dias').setLabel('Dias (ex: SEG./SEX.)').setStyle(TextInputStyle.Short).setValue(config.diasFuncionamento?.join(', ') || '').setRequired(false))
                );
                await i.showModal(modal);
                const modalSubmit = await i.awaitModalSubmit({ filter: (m) => m.customId === 'modal_horario' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (modalSubmit) {
                    config.horarioInicio = modalSubmit.fields.getTextInputValue('inicio') || null;
                    config.horarioFim = modalSubmit.fields.getTextInputValue('fim') || null;
                    config.diasFuncionamento = modalSubmit.fields.getTextInputValue('dias').split(',').map(d => d.trim()).filter(d => d);
                    storage.salvarServidor(interaction.guildId, config);
                    await modalSubmit.update({ embeds: [montarEmbed(config)], components: [montarMenu()] });
                }
            }

            else if (opcao === 'feedback') {
                if (!isVIP) return i.reply({ content: 'Este recurso está disponível apenas para o plano VIP.', flags: 64 });
                const rowFeedback = new ActionRowBuilder().addComponents(
                    new StringSelectMenuBuilder()
                        .setCustomId('select_feedback')
                        .setPlaceholder('Ativar ou desativar')
                        .addOptions([
                            { label: 'Ativar', value: 'ativar' },
                            { label: 'Desativar', value: 'desativar' }
                        ])
                );
                await i.reply({ content: 'Deseja ativar o sistema de feedback?', components: [rowFeedback], flags: 64 });
                const select = await i.channel.awaitMessageComponent({ filter: (m) => m.customId === 'select_feedback' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (!select) return;
                config.feedback.ativo = select.values[0] === 'ativar';
                storage.salvarServidor(interaction.guildId, config);
                await select.update({ content: `Sistema de feedback: ${config.feedback.ativo ? 'Ativado' : 'Desativado'}`, components: [] });
                await i.editReply({ embeds: [montarEmbed(config)], components: [montarMenu()] });
            }

            else if (opcao === 'feedback_logs') {
                if (!isVIP) return i.reply({ content: 'Este recurso está disponível apenas para o plano VIP.', flags: 64 });
                const menu = new ActionRowBuilder().addComponents(
                    new ChannelSelectMenuBuilder().setCustomId('select_feedback_logs').setPlaceholder('Pesquise o canal de logs de feedback').setChannelTypes(ChannelType.GuildText)
                );
                await i.reply({ content: 'Selecione o canal de logs de feedback:', components: [menu], flags: 64 });
                const select = await i.channel.awaitMessageComponent({ filter: (m) => m.customId === 'select_feedback_logs' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (!select) return;
                config.feedback.canalLogs = select.values[0];
                storage.salvarServidor(interaction.guildId, config);
                await select.update({ content: `Canal de logs de feedback: <#${config.feedback.canalLogs}>`, components: [] });
                await i.editReply({ embeds: [montarEmbed(config)], components: [montarMenu()] });
            }
        } catch (erro) {
            await responderErro(i, erro, 'configurar-ticket');
        }
        });
    }
};
