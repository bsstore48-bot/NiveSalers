const {
    Client,
    GatewayIntentBits,
    REST,
    Routes,
    ChannelType,
    PermissionsBitField,
    EmbedBuilder,
    ActionRowBuilder,
    ButtonBuilder,
    ButtonStyle,
    StringSelectMenuBuilder,
    ModalBuilder,
    TextInputBuilder,
    TextInputStyle,
    AttachmentBuilder
} = require('discord.js');
const {
    joinVoiceChannel,
    getVoiceConnection,
    VoiceConnectionStatus,
    entersState
} = require('@discordjs/voice');
const fs = require('fs');
const path = require('path');
require('dotenv').config();
const { iniciarServidorHttp } = require('./server.js');
const cloudSync = require('./utils/cloudSync.js');
const config = require('./config.json');
const storage = require('./utils/storage.js');
const feedback = require('./utils/feedback.js');
const transcript = require('./utils/transcript.js');
const ia = require('./utils/ia.js');
const vercelDeploy = require('./utils/vercelDeploy.js');
const { instalarProtecoesGlobais, responderErro } = require('./utils/safe.js');

const VOICE_CHANNEL_ID = '1540799989981384777';

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers,
        GatewayIntentBits.DirectMessages,
        GatewayIntentBits.GuildVoiceStates
    ]
});

client.commands = new Map();
const fechamentosPendentes = new Map();
instalarProtecoesGlobais(client);

// Inicia servidor HTTP embutido para Render
iniciarServidorHttp(client);

function formatarData(timestamp) {
    return timestamp ? new Date(timestamp).toLocaleString('pt-BR') : 'Não informado';
}

function isAtendente(member, configGuild) {
    if (!member) return false;
    if (member.permissions.has(PermissionsBitField.Flags.Administrator)) return true;
    if (!configGuild.atendentes || !configGuild.atendentes.length) return false;
    return member.roles.cache.some(role => configGuild.atendentes.includes(role.id));
}

async function enviarLogEmbed(configGuild, guild, titulo, cor, campos, arquivos) {
    if (!configGuild.logs) return;
    const canalLogs = guild.channels.cache.get(configGuild.logs);
    if (!canalLogs) return;
    const embed = new EmbedBuilder().setColor(cor || '#5865F2').setTitle(titulo).addFields(campos || []).setFooter({ text: 'Nive Bots' }).setTimestamp();
    await canalLogs.send({ embeds: [embed], files: arquivos && arquivos.length ? arquivos : undefined }).catch(() => {});
}

function calcularDemanda(quantidade) {
    if (quantidade > 100) return 'Muito alta';
    if (quantidade > 50) return 'Alta';
    if (quantidade > 25) return 'Média';
    return 'Baixa';
}

function construirEmbedTicket(configGuild, ticketInfo, mensagemBoasVindas, guildName) {
    const ultimaNota = ticketInfo.notas?.length ? ticketInfo.notas[ticketInfo.notas.length - 1].texto : 'Nenhuma';
    const demanda = calcularDemanda(Object.keys(configGuild.ticketsAbertos || {}).length);
    return new EmbedBuilder()
        .setColor(configGuild.cor?.replace('#', '') || 0x2b2d31)
        .setDescription(mensagemBoasVindas)
        .addFields(
            { name: 'Atendimento com IA', value: ticketInfo.iaAtiva ? 'Sim' : 'Não', inline: true },
            { name: 'Assumido por', value: ticketInfo.responsavel ? `<@${ticketInfo.responsavel}>` : 'Ninguém', inline: true },
            { name: 'Nota adicionada', value: ultimaNota, inline: true },
            { name: 'Demanda atual', value: demanda, inline: true }
        )
        .setFooter({ text: `Obrigado pela paciência! ${guildName}` })
        .setTimestamp();
}

function construirComponentesTicket(ticketInfo) {
    const selectRow = new ActionRowBuilder().addComponents(
        new StringSelectMenuBuilder()
            .setCustomId('ticket_painel_select')
            .setPlaceholder('Selecione um painel')
            .addOptions([
                { label: 'Painel Atendente', value: 'atendente', description: 'Ações da equipe de suporte' },
                { label: 'Painel Cliente', value: 'cliente', description: 'Ações para quem abriu o ticket' }
            ])
    );
    const botoesRow = new ActionRowBuilder().addComponents(
        new ButtonBuilder().setCustomId('fechar_ticket').setLabel('Fechar ticket').setStyle(ButtonStyle.Danger),
        new ButtonBuilder().setCustomId('assumir_ticket_botao').setLabel('Assumir Atendimento').setStyle(ButtonStyle.Success).setDisabled(Boolean(ticketInfo.responsavel))
    );
    return [selectRow, botoesRow];
}

async function atualizarPainelTicket(canal, configGuild, ticketInfo) {
    try {
        if (!ticketInfo.painelMessageId) return;
        const mensagem = await canal.messages.fetch(ticketInfo.painelMessageId).catch(() => null);
        if (!mensagem) return;
        const mensagemBoasVindas = mensagem.embeds?.[0]?.description || configGuild.mensagemBoasVindas;
        await mensagem.edit({
            embeds: [construirEmbedTicket(configGuild, ticketInfo, mensagemBoasVindas, canal.guild.name)],
            components: construirComponentesTicket(ticketInfo)
        }).catch(() => {});
    } catch (erro) {
        console.log(`⚠️ Não foi possível atualizar o painel do ticket: ${erro.message}`);
    }
}

async function abrirPainelAtendente(interaction, configGuild) {
    if (!isAtendente(interaction.member, configGuild)) {
        return interaction.reply({ content: 'Você não possui permissão para acessar este painel.', flags: 64 });
    }
    const row = new ActionRowBuilder().addComponents(
        new StringSelectMenuBuilder()
            .setCustomId('menu_atendente')
            .setPlaceholder('Selecione uma opção do painel do atendente')
            .addOptions([
                { label: 'Notificar Cliente', value: 'notificar_cliente', description: 'Notifica o cliente dentro do ticket' },
                { label: 'Notificar no DM', value: 'notificar_cliente_dm', description: 'Envia uma mensagem privada ao cliente' },
                { label: 'Renomear Ticket', value: 'renomear_ticket', description: 'Altera o nome do canal do ticket' },
                { label: 'Adicionar Usuário', value: 'add_user', description: 'Adiciona um usuário ao ticket' },
                { label: 'Remover Usuário', value: 'remove_user', description: 'Remove um usuário do ticket' },
                { label: 'Assumir Atendimento', value: 'assumir_ticket', description: 'Torna você o responsável pelo ticket' },
                { label: 'Definir Prioridade', value: 'definir_prioridade', description: 'Define a prioridade do atendimento' },
                { label: 'Adicionar Nota Interna', value: 'add_nota', description: 'Adiciona uma nota interna visível apenas à equipe' },
                { label: 'Criar Canal de Voz', value: 'criar_canal_voz', description: 'Cria uma sala de suporte com confirmação' }
            ])
    );
    return interaction.reply({ content: 'Painel do Atendente', components: [row], flags: 64 });
}

async function abrirPainelMembro(interaction) {
    const row = new ActionRowBuilder().addComponents(
        new StringSelectMenuBuilder()
            .setCustomId('menu_membro')
            .setPlaceholder('Selecione uma ação do painel do membro')
            .addOptions([
                { label: 'Notificar Atendentes', value: 'notificar_atendentes', description: 'Notifica os atendentes dentro do ticket' },
                { label: 'Notificar no DM', value: 'notificar_atendentes_dm', description: 'Envia uma mensagem privada aos atendentes' }
            ])
    );
    return interaction.reply({ content: 'Painel do Membro', components: [row], flags: 64 });
}

let conectandoCanalVoz = false;

async function conectarCanalVoz() {
    if (conectandoCanalVoz) return; // evita conexões simultâneas concorrentes (causa do "entra e sai" contínuo)
    conectandoCanalVoz = true;
    try {
        if (!client.isReady()) {
            console.log('⏳ Bot ainda não está pronto. Aguardando...');
            return;
        }

        const guild = client.guilds.cache.first();
        if (!guild) {
            console.log('⚠️ Nenhum servidor encontrado.');
            return;
        }

        const voiceChannel = guild.channels.cache.get(VOICE_CHANNEL_ID);
        if (!voiceChannel) {
            console.log(`⚠️ Canal de voz ${VOICE_CHANNEL_ID} não encontrado.`);
            return;
        }

        if (voiceChannel.type !== ChannelType.GuildVoice) {
            console.log(`⚠️ O canal ${VOICE_CHANNEL_ID} não é um canal de voz.`);
            return;
        }

        const conexaoExistente = getVoiceConnection(guild.id);
        if (conexaoExistente && conexaoExistente.joinConfig.channelId === VOICE_CHANNEL_ID && conexaoExistente.state.status !== VoiceConnectionStatus.Destroyed) {
            console.log('✅ Bot já está no canal de voz correto.');
            return;
        }

        if (conexaoExistente) {
            conexaoExistente.destroy();
            await new Promise(resolve => setTimeout(resolve, 1000));
        }

        const conexao = joinVoiceChannel({
            channelId: voiceChannel.id,
            guildId: guild.id,
            adapterCreator: guild.voiceAdapterCreator,
            selfDeaf: true,
            selfMute: false
        });

        try {
            await entersState(conexao, VoiceConnectionStatus.Ready, 15_000);
            console.log(`🎙️ Conectado ao canal de voz: ${voiceChannel.name} (${voiceChannel.id})`);
        } catch (err) {
            console.log(`⚠️ Não foi possível confirmar a conexão de voz a tempo: ${err.message}`);
            conexao.destroy();
        }

        conexao.on(VoiceConnectionStatus.Disconnected, async () => {
            try {
                await Promise.race([
                    entersState(conexao, VoiceConnectionStatus.Signalling, 5_000),
                    entersState(conexao, VoiceConnectionStatus.Connecting, 5_000)
                ]);
            } catch {
                conexao.destroy();
            }
        });

        conexao.on('error', (error) => {
            console.log(`❌ Erro na conexão de voz: ${error.message}`);
        });
    } catch (error) {
        console.log(`❌ Erro ao conectar ao canal de voz: ${error.message}`);
    } finally {
        conectandoCanalVoz = false;
    }
}

async function criarCanalVoz(interaction, incluirAtendente) {
    const configGuild = storage.getServidor(interaction.guild.id);
    if (!configGuild.categoriaVoz) return interaction.update({ content: 'A categoria de voz de suporte ainda não foi configurada.', components: [] });
    const categoria = interaction.guild.channels.cache.get(configGuild.categoriaVoz);
    if (!categoria || categoria.type !== ChannelType.GuildCategory) return interaction.update({ content: 'A categoria de voz configurada não foi encontrada.', components: [] });
    const ticket = configGuild.ticketsAbertos[interaction.channel.id];
    const dono = ticket?.donoId ? await interaction.guild.members.fetch(ticket.donoId).catch(() => null) : null;
    const responsavel = incluirAtendente && ticket?.responsavel ? await interaction.guild.members.fetch(ticket.responsavel).catch(() => null) : null;
    const nome = ['suporte', dono?.user.username || 'ticket', ...(responsavel ? [responsavel.user.username] : [])].join('-').toLowerCase().slice(0, 100);
    const permissoes = [{ id: interaction.guild.id, deny: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.Connect] }];
    if (dono) permissoes.push({ id: dono.id, allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.Connect, PermissionsBitField.Flags.Speak] });
    for (const cargoId of configGuild.atendentes) permissoes.push({ id: cargoId, allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.Connect, PermissionsBitField.Flags.Speak] });
    const canalVoz = await interaction.guild.channels.create({ name: nome, type: ChannelType.GuildVoice, parent: categoria.id, permissionOverwrites: permissoes, reason: `Canal de suporte do ticket ${interaction.channel.name}` });
    if (ticket) { ticket.vozId = canalVoz.id; storage.salvarServidor(interaction.guild.id, configGuild); }
    await interaction.update({ content: `Canal de voz criado: ${canalVoz}`, components: [] });
    await enviarLogEmbed(configGuild, interaction.guild, 'Canal de voz criado', '#57F287', [{ name: 'Ticket', value: interaction.channel.name, inline: true }, { name: 'Canal', value: `${canalVoz}`, inline: true }, { name: 'Atendente incluído', value: incluirAtendente ? 'Sim' : 'Não', inline: true }]);
}

function dentroDoHorario(configGuild) {
    if (!configGuild.horarioInicio || !configGuild.horarioFim) return true;
    try {
        const agora = new Date().toLocaleString('pt-BR', { timeZone: configGuild.fusoHorario || 'America/Sao_Paulo', hour12: false });
        const horaAtual = agora.split(' ')[1]?.slice(0, 5) ?? null;
        if (!horaAtual) return true;
        return horaAtual >= configGuild.horarioInicio && horaAtual <= configGuild.horarioFim;
    } catch {
        return true;
    }
}

function gerarNomeCanal(configGuild, tipo, user, numero) {
    const isVIP = (configGuild.plano || 'Gratis') === 'VIP';
    const formato = isVIP && configGuild.nomeCanalFormato ? configGuild.nomeCanalFormato : '{tipo}・{user}・{numero}';
    const nome = formato
        .replace(/{tipo}/g, tipo)
        .replace(/{user}/g, user.username)
        .replace(/{numero}/g, numero);
    return nome.slice(0, 100);
}

let statusIndex = 0;

function atualizarStatus() {
    if (!client.user) return;

    const totalMembros = client.guilds.cache.reduce(
        (total, guild) => total + (guild.memberCount || 0),
        0
    );

    const totalServidores = client.guilds.cache.size;

    const statusLista = [
        `Atendendo ${totalMembros.toLocaleString('pt-BR')} membros`,
        `Gerenciando tickets pra ${totalServidores} servidores!`,
        `Latência: ${client.ws.ping}ms`,
        `Desenvolvido por NiveBOTS`,
        `nivebots.vercel.app`
    ];

    const texto = statusLista[statusIndex];

    client.user.setPresence({
        status: 'online',
        activities: [
            {
                name: texto,
                type: 0
            }
        ]
    });

    statusIndex = (statusIndex + 1) % statusLista.length;
}

client.once('clientReady', async () => {
    console.log(`✅ ${client.user.tag} está online!`);

    const commands = [];
    const commandsDir = path.join(__dirname, 'commands');
    const commandFiles = fs.existsSync(commandsDir) ? fs.readdirSync(commandsDir).filter(f => f.endsWith('.js')) : [];

    for (const file of commandFiles) {
        try {
            const command = require(path.join(commandsDir, file));
            if (!command.data || !command.execute) {
                console.log(`⚠️ Comando ignorado: ${file}`);
                continue;
            }
            commands.push(command.data);
            client.commands.set(command.data.name, command);
            console.log(`✅ Comando carregado: ${command.data.name}`);
        } catch (err) {
            console.log(`❌ Erro ao carregar ${file}: ${err.message}`);
        }
    }

    const token = process.env.DISCORD_TOKEN || process.env.TOKEN || config.token;
    try {
        const rest = new REST({ version: '10' }).setToken(token);
        await rest.put(Routes.applicationCommands(client.user.id), { body: commands });
        console.log(`📁 ${commands.length} comando(s) registrado(s) com sucesso.`);
    } catch (restErr) {
        console.error(`⚠️ Erro ao registrar comandos slash no Discord: ${restErr.message}`);
    }

    setTimeout(async () => {
        await conectarCanalVoz();
    }, 3000);

    atualizarStatus();
    setInterval(atualizarStatus, 10000);
});

client.on('guildCreate', guild => {
    console.log(`📥 Entrei em ${guild.name}`);
    atualizarStatus();
    
    setTimeout(async () => {
        await conectarCanalVoz();
    }, 3000);
});

client.on('guildDelete', guild => {
    console.log(`📤 Saí de ${guild.name}`);
    atualizarStatus();
});

setInterval(async () => {
    try {
        if (!client.isReady()) return;

        const guild = client.guilds.cache.first();
        if (!guild) return;

        const conexao = getVoiceConnection(guild.id);

        if (!conexao || conexao.state.status === VoiceConnectionStatus.Destroyed || conexao.joinConfig.channelId !== VOICE_CHANNEL_ID) {
            console.log('🔄 Bot não está no canal de voz correto. Reconectando...');
            await conectarCanalVoz();
        }
    } catch (error) {
        console.log(`❌ Erro no monitoramento do canal de voz: ${error.message}`);
    }
}, 30000);

client.on('guildMemberRemove', async member => {
    try {
        const configGuild = storage.getServidor(member.guild.id);
        let alterou = false;

        for (const [canalId, ticket] of Object.entries(configGuild.ticketsAbertos)) {
            if (ticket.donoId !== member.id || ticket.donoSaiuDoServidor) continue;

            const canal = member.guild.channels.cache.get(canalId);
            if (canal) {
                const embed = new EmbedBuilder()
                    .setColor('#e74c3c')
                    .setTitle('O autor do ticket saiu do servidor')
                    .setDescription(`⚠O usuário **${member.user.tag}**, autor deste ticket, acabou de sair do servidor.\n\nRecomendamos que a equipe avalie se o atendimento deve ser encerrado.`)
                    .setTimestamp();

                const mencoes = configGuild.atendentes.map(id => `<@&${id}>`).join(' ');
                await canal.send({ content: mencoes || null, embeds: [embed] }).catch(() => {});
            }

            ticket.donoSaiuDoServidor = true;
            alterou = true;
        }

        if (alterou) storage.salvarServidor(member.guild.id, configGuild);
    } catch (err) {
        console.log(`❌ Erro ao processar saída de membro: ${err.message}`);
    }
});

client.on('messageCreate', async message => {
    try {
        if (message.author.bot || !message.guild) return;

        const configGuild = storage.getServidor(message.guild.id);
        const ticketInfo = configGuild.ticketsAbertos[message.channel.id];
        if (!ticketInfo) return;

        const ehAtendenteMsg = isAtendente(message.member, configGuild);

        if (ehAtendenteMsg && ticketInfo.iaAtiva) {
            ticketInfo.iaAtiva = false;
            storage.salvarServidor(message.guild.id, configGuild);
            await atualizarPainelTicket(message.channel, configGuild, ticketInfo);
            return;
        }

        if (!ehAtendenteMsg && message.author.id === ticketInfo.donoId && ticketInfo.iaAtiva && configGuild.ia?.ativa) {
            await message.channel.sendTyping().catch(() => {});
            const historico = (ticketInfo.historicoIa || []).slice(-8);
            const respostaIa = await ia.responder(configGuild.ia, message.content, historico).catch(erro => {
                console.log(`⚠️ [IA] Falha ao gerar resposta: ${erro.message}`);
                return null;
            });
            if (respostaIa) {
                ticketInfo.historicoIa = [...historico, { role: 'user', content: message.content }, { role: 'assistant', content: respostaIa }];
                storage.salvarServidor(message.guild.id, configGuild);
                await message.channel.send({ content: respostaIa }).catch(() => {});
            }
        }
    } catch (erro) {
        console.log(`❌ Erro no processamento de mensagem (IA/ticket): ${erro.message}`);
    }
});

client.on('interactionCreate', async interaction => {
    try {
    if (interaction.isCommand()) {
        const cmd = client.commands.get(interaction.commandName);
        if (cmd) await cmd.execute(interaction, client);
        return;
    }

    if (interaction.isButton()) {
        if (interaction.customId.startsWith('abrir_ticket_')) {
            const tipo = interaction.customId.replace('abrir_ticket_', '');
            await abrirTicket(interaction, tipo);
            return;
        }

        if (interaction.customId === 'voz_cancelar') return interaction.update({ content: 'Criação do canal de voz cancelada.', components: [] });
        if (interaction.customId === 'voz_confirmar') {
            return interaction.update({ content: 'Deseja incluir o nome do atendente que assumiu este ticket?', components: [new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId('voz_com_atendente').setLabel('Sim').setStyle(ButtonStyle.Success), new ButtonBuilder().setCustomId('voz_sem_atendente').setLabel('Não').setStyle(ButtonStyle.Secondary))] });
        }
        if (interaction.customId === 'voz_com_atendente') return criarCanalVoz(interaction, true);
        if (interaction.customId === 'voz_sem_atendente') return criarCanalVoz(interaction, false);

        if (interaction.customId.startsWith('fechamento_detalhes_') || interaction.customId.startsWith('fechamento_transcript_')) {
            const partes = interaction.customId.split('_');
            const chave = partes.slice(2).join('_');
            const fechamento = fechamentosPendentes.get(chave);
            if (!fechamento) return interaction.reply({ content: 'Os detalhes deste fechamento expiraram. O transcript não está mais disponível nesta sessão.', flags: 64 });
            if (interaction.user.id !== fechamento.donoId) return interaction.reply({ content: 'Somente o dono do ticket pode consultar estes detalhes.', flags: 64 });

            if (interaction.customId.startsWith('fechamento_detalhes_')) {
                const embedDetalhes = new EmbedBuilder()
                    .setColor('#5865F2')
                    .setTitle('Detalhes do ticket fechado')
                    .addFields(
                        { name: 'Servidor', value: fechamento.guildName, inline: true },
                        { name: 'Ticket', value: fechamento.ticketName, inline: true },
                        { name: 'Tipo', value: fechamento.tipo, inline: true },
                        { name: 'Criado em', value: formatarData(fechamento.criadoEm), inline: true },
                        { name: 'Fechado em', value: formatarData(fechamento.fechadoEm), inline: true },
                        { name: 'Fechado por', value: fechamento.fechadoPor, inline: true },
                        { name: 'Motivo', value: fechamento.motivo, inline: false }
                    )
                    .setFooter({ text: 'Nive Bots' })
                    .setTimestamp();
                return interaction.reply({ embeds: [embedDetalhes], flags: 64 });
            }

            const arquivoDownload = path.join(__dirname, `${chave}-download.txt`);
            try {
                fs.writeFileSync(arquivoDownload, fechamento.conteudo);
                await interaction.reply({ content: 'Aqui está o transcript do seu ticket.', files: [new AttachmentBuilder(arquivoDownload, { name: `${fechamento.ticketName}.txt` })] });
            } finally {
                if (fs.existsSync(arquivoDownload)) fs.unlinkSync(arquivoDownload);
            }
            return;
        }

        if (interaction.customId.startsWith('feedback_nota_')) {
            const partes = interaction.customId.split('_');
            const guildId = partes[2];
            const nota = partes[3];

            const modal = new ModalBuilder().setCustomId(`feedback_modal_${guildId}_${nota}`).setTitle('Avaliação do Ticket');
            modal.addComponents(
                new ActionRowBuilder().addComponents(
                    new TextInputBuilder().setCustomId('comentario').setLabel('Deixe um comentário sobre o atendimento').setStyle(TextInputStyle.Paragraph).setRequired(true)
                )
            );
            await interaction.showModal(modal);

            const modalSubmit = await interaction.awaitModalSubmit({
                filter: (m) => m.customId === `feedback_modal_${guildId}_${nota}` && m.user.id === interaction.user.id,
                time: 300000
            }).catch(() => null);

            if (modalSubmit) {
                const comentario = modalSubmit.fields.getTextInputValue('comentario');
                const configGuild = storage.getServidor(guildId);
                if (configGuild.feedback && configGuild.feedback.pendentes) {
                    delete configGuild.feedback.pendentes[interaction.user.id];
                }
                await storage.salvarServidor(guildId, configGuild);

                if (configGuild.feedback?.canalLogs) {
                    const guild = client.guilds.cache.get(guildId);
                    const canalLogs = guild?.channels.cache.get(configGuild.feedback.canalLogs);
                    if (canalLogs) {
                        const embedLog = new EmbedBuilder()
                            .setColor('#2b2d31')
                            .setTitle('Novo Feedback Recebido')
                            .addFields(
                                { name: 'Usuário', value: `${interaction.user.tag}`, inline: true },
                                { name: 'Nota', value: `${nota}/10`, inline: true },
                                { name: 'Comentário', value: comentario, inline: false }
                            )
                            .setTimestamp();
                        await canalLogs.send({ embeds: [embedLog] }).catch(() => {});
                    }
                }

                await modalSubmit.reply({ content: 'Muito obrigado pelo seu feedback!', flags: 64 });
            }
            return;
        }

        if (interaction.customId === 'painel_atendente') {
            const configGuild = storage.getServidor(interaction.guild.id);
            await abrirPainelAtendente(interaction, configGuild);
            return;
        }

        if (interaction.customId === 'painel_membro') {
            await abrirPainelMembro(interaction);
            return;
        }

        if (interaction.customId === 'assumir_ticket_botao') {
            const configGuild = storage.getServidor(interaction.guild.id);
            const ticketInfo = configGuild.ticketsAbertos[interaction.channel.id];

            if (!isAtendente(interaction.member, configGuild)) {
                await interaction.reply({ content: 'Você não possui permissão para assumir este ticket.', flags: 64 });
                return;
            }
            if (!ticketInfo) {
                await interaction.reply({ content: 'Este ticket não foi encontrado nos registros do bot.', flags: 64 });
                return;
            }
            if (ticketInfo.responsavel) {
                await interaction.reply({ content: `Este ticket já foi assumido por <@${ticketInfo.responsavel}>.`, flags: 64 });
                return;
            }

            ticketInfo.responsavel = interaction.user.id;
            const iaEstavaAtiva = ticketInfo.iaAtiva;
            ticketInfo.iaAtiva = false;
            storage.salvarServidor(interaction.guild.id, configGuild);

            await interaction.reply({
                content: `<@${ticketInfo.donoId}> o atendente <@${interaction.user.id}> acabou de **assumir** o seu ticket${iaEstavaAtiva ? ', a ia foi desligada e agora você tem atendimento humano' : ''}.`
            });
            await atualizarPainelTicket(interaction.channel, configGuild, ticketInfo);
            return;
        }

        if (interaction.customId === 'fechar_ticket') {
            if (!interaction.member.permissions.has(PermissionsBitField.Flags.ManageChannels)) {
                await interaction.reply({ content: 'Você não possui permissão para fechar este ticket.', flags: 64 });
                return;
            }

            const modalMotivo = new ModalBuilder().setCustomId('modal_motivo_fechamento').setTitle('Fechar Ticket');
            modalMotivo.addComponents(
                new ActionRowBuilder().addComponents(
                    new TextInputBuilder()
                        .setCustomId('motivo')
                        .setLabel('Motivo do encerramento (opcional)')
                        .setStyle(TextInputStyle.Paragraph)
                        .setRequired(false)
                )
            );
            await interaction.showModal(modalMotivo);

            const submit = await interaction.awaitModalSubmit({
                filter: (m) => m.customId === 'modal_motivo_fechamento' && m.user.id === interaction.user.id,
                time: 60000
            }).catch(() => null);

            if (!submit) return;

            const motivo = submit.fields.getTextInputValue('motivo') || 'Não informado';

            const canal = submit.channel;
            const guild = canal.guild;
            const configGuild = storage.getServidor(guild.id);
            const plano = configGuild.plano || 'Gratis';
            const isPremium = plano === 'Premium' || plano === 'VIP';
            const isVIP = plano === 'VIP';
            const ticketInfo = configGuild.ticketsAbertos[canal.id];

            if (ticketInfo) ticketInfo.motivoFechamento = motivo;

            let anexoTranscript = null;
            let caminhoTranscript = null;
            let conteudoTranscript = null;
            const fechadoEm = Date.now();
            const donoId = ticketInfo?.donoId ?? canal.permissionOverwrites.cache.find(o => o.type === 1 && o.id !== client.user.id)?.id;
            let anexoSite = null;
            let caminhoSite = null;
            let urlSite = null;

            if (plano === 'Gratis' || isPremium) {
                const mensagens = await canal.messages.fetch({ limit: 100 });
                const listaMensagens = mensagens.reverse();
                let conteudo = `Transcript do ticket: ${canal.name}\n`;
                conteudo += `Data de fechamento: ${new Date(fechadoEm).toLocaleString('pt-BR')}\n`;
                conteudo += `Fechado por: ${submit.user.tag} (${submit.user.id})\n`;
                conteudo += `Motivo do encerramento: ${motivo}\n`;
                conteudo += `----------------------------------------\n\n`;
                for (const msg of listaMensagens.values()) {
                    const dataHora = msg.createdAt.toLocaleString('pt-BR');
                    conteudo += `[${dataHora}] ${msg.author.tag}:\n`;
                    conteudo += `${msg.content || '(sem texto)'}\n`;
                    if (msg.attachments.size > 0) {
                        conteudo += `[Anexos: ${msg.attachments.map(a => a.url).join(', ')}]\n`;
                    }
                    conteudo += `\n`;
                }
                conteudo += `----------------------------------------\n`;
                conteudo += `Transcript gerado por Nive Bots\n`;
                conteudoTranscript = conteudo;

                caminhoTranscript = path.join(__dirname, `${canal.id}.txt`);
                fs.writeFileSync(caminhoTranscript, conteudo);
                anexoTranscript = new AttachmentBuilder(caminhoTranscript, { name: `${canal.name}.txt` });
                if (isPremium && configGuild.transcriptModo === 'site') {
                    const donoMember = donoId ? await guild.members.fetch(donoId).catch(() => null) : null;
                    const slugPublico = transcript.gerarSlugTicket(donoMember?.user.username || submit.user.username, guild.name);
                    const resultadoSite = await transcript.gerarHtml(canal, motivo, configGuild.footerAutor || 'Nive Bots', { slugPublico });
                    caminhoSite = resultadoSite.arquivo;
                    anexoSite = new AttachmentBuilder(caminhoSite, { name: `${canal.name}.html` });
                    urlSite = await vercelDeploy.publicarTranscript(slugPublico, resultadoSite.html).catch(erro => {
                        console.log(`⚠️ Erro ao publicar transcript na Vercel: ${erro.message}`);
                        return null;
                    });
                }
            }

            const embedFechamento = new EmbedBuilder()
                .setColor('#000000')
                .setTitle('Encerrando o ticket')
                .setDescription('Este ticket será fechado em 5 segundos.')
                .addFields(
                    { name: 'Fechado por', value: `${submit.user.tag} (${submit.user.id})`, inline: true },
                    { name: 'Motivo', value: motivo, inline: true }
                )
                .setTimestamp();

            await submit.reply({ embeds: [embedFechamento], files: [ ...(anexoTranscript ? [anexoTranscript] : []), ...(anexoSite ? [anexoSite] : []) ] });

            if (donoId) {
                const fechamento = {
                    donoId,
                    guildName: guild.name,
                    ticketName: canal.name,
                    tipo: ticketInfo?.tipo || 'Não informado',
                    criadoEm: ticketInfo?.criadoEm,
                    fechadoEm,
                    fechadoPor: `${submit.user.tag} (${submit.user.id})`,
                    motivo,
                    conteudo: conteudoTranscript || 'Transcript indisponível.'
                };
                const chaveFechamento = canal.id;
                fechamentosPendentes.set(chaveFechamento, fechamento);
                setTimeout(() => fechamentosPendentes.delete(chaveFechamento), 15 * 60 * 1000);
                const dono = await client.users.fetch(donoId).catch(() => null);
                if (dono) {
                    const embedDM = new EmbedBuilder()
                        .setColor('#5865F2')
                        .setTitle('Ticket fechado')
                        .setDescription(`Olá, <@${donoId}>. Seu ticket em **${guild.name}** foi fechado pelo atendente **${submit.user.tag}**.`)
                        .addFields(
                            { name: 'Ticket', value: canal.name, inline: true },
                            { name: 'Tipo', value: fechamento.tipo, inline: true },
                            { name: 'Motivo', value: motivo, inline: false }
                        )
                        .setFooter({ text: 'Use os botões abaixo para consultar o fechamento.' })
                        .setTimestamp();
                    const botoesDM = new ActionRowBuilder().addComponents(
                        new ButtonBuilder().setCustomId(`fechamento_detalhes_${chaveFechamento}`).setLabel('Ver detalhes').setStyle(ButtonStyle.Primary),
                        new ButtonBuilder().setCustomId(`fechamento_transcript_${chaveFechamento}`).setLabel('Baixar transcript').setStyle(ButtonStyle.Secondary)
                    );
                    await dono.send({ embeds: [embedDM], components: [botoesDM] }).catch(erro => console.error('DM de fechamento não enviada:', erro.message));
                }
            }

            if (isVIP && donoId) {
                await feedback.enviarPedidoFeedback(client, guild.id, donoId, canal.name);
            }

            storage.removerTicket(configGuild, canal.id);
            storage.salvarServidor(guild.id, configGuild);

            setTimeout(async () => {
                const camposTranscript = [
                    { name: 'Ticket', value: canal.name, inline: true },
                    { name: 'Fechado por', value: `${submit.user.tag} (${submit.user.id})`, inline: true },
                    { name: 'Motivo', value: motivo, inline: false },
                    { name: 'Transcript', value: urlSite ? `Arquivo TXT anexado abaixo · [Ver no site](${urlSite})` : 'Arquivo TXT anexado abaixo', inline: false }
                ];
                const arquivosLog = [];
                if (caminhoTranscript && fs.existsSync(caminhoTranscript)) arquivosLog.push(new AttachmentBuilder(caminhoTranscript, { name: `${canal.name}.txt` }));
                if (caminhoSite && fs.existsSync(caminhoSite)) arquivosLog.push(new AttachmentBuilder(caminhoSite, { name: `${canal.name}.html` }));

                await enviarLogEmbed(configGuild, guild, 'Ticket fechado', '#ED4245', camposTranscript, arquivosLog);

                if (caminhoTranscript) fs.unlinkSync(caminhoTranscript);
                if (caminhoSite) fs.unlinkSync(caminhoSite);
                await canal.delete().catch(() => {});
            }, 5000);
            return;
        }
    }

    if (interaction.isStringSelectMenu()) {
        if (interaction.customId === 'ticket_painel_select') {
            const configGuild = storage.getServidor(interaction.guild.id);
            if (interaction.values[0] === 'atendente') {
                await abrirPainelAtendente(interaction, configGuild);
            } else {
                await abrirPainelMembro(interaction);
            }
            return;
        }

        if (interaction.customId === 'menu_atendente') {
            const valor = interaction.values[0];
            const configGuild = storage.getServidor(interaction.guild.id);
            const ticketInfo = configGuild.ticketsAbertos[interaction.channel.id];

            if (valor === 'criar_canal_voz') {
                await interaction.reply({ content: `Vou criar um canal de voz na categoria configurada para suporte, com o nome do cliente. Confirme para continuar.`, components: [new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId('voz_confirmar').setLabel('Continuar').setStyle(ButtonStyle.Success), new ButtonBuilder().setCustomId('voz_cancelar').setLabel('Cancelar').setStyle(ButtonStyle.Secondary))], flags: 64 });
            }
            else if (valor === 'notificar_cliente') {
                const clientUser = interaction.channel.permissionOverwrites.cache.find(o => o.type === 1);
                if (clientUser) {
                    await interaction.channel.send(`<@${clientUser.id}>, a equipe de atendimento está lhe aguardando.`);
                }
                await interaction.reply({ content: '✅ Cliente notificado com sucesso.', flags: 64 });
            }
            else if (valor === 'notificar_cliente_dm') {
                const clientUser = interaction.channel.permissionOverwrites.cache.find(o => o.type === 1);
                if (clientUser) {
                    const member = await interaction.guild.members.fetch(clientUser.id).catch(() => null);
                    if (member) {
                        await member.send('O seu ticket foi atualizado pela equipe de atendimento.').catch(() => {});
                    }
                }
                await interaction.reply({ content: '✅ Cliente notificado por mensagem privada.', flags: 64 });
            }
            else if (valor === 'assumir_ticket') {
                if (ticketInfo && !ticketInfo.responsavel) {
                    const iaEstavaAtiva = ticketInfo.iaAtiva;
                    ticketInfo.responsavel = interaction.user.id;
                    ticketInfo.iaAtiva = false;
                    storage.salvarServidor(interaction.guild.id, configGuild);
                    await interaction.reply({ content: `<@${ticketInfo.donoId}> o atendente <@${interaction.user.id}> acabou de **assumir** o seu ticket${iaEstavaAtiva ? ', a ia foi desligada e agora você tem atendimento humano' : ''}.` });
                    await atualizarPainelTicket(interaction.channel, configGuild, ticketInfo);
                } else if (ticketInfo?.responsavel) {
                    await interaction.reply({ content: `Este ticket já foi assumido por <@${ticketInfo.responsavel}>.`, flags: 64 });
                } else {
                    await interaction.reply({ content: `Você assumiu a responsabilidade por este ticket, ${interaction.user}.`, flags: 64 });
                }
            }
            else if (valor === 'definir_prioridade') {
                const rowPrioridade = new ActionRowBuilder().addComponents(
                    new StringSelectMenuBuilder()
                        .setCustomId('select_prioridade')
                        .setPlaceholder('Selecione a prioridade do atendimento')
                        .addOptions([
                            { label: 'Baixa', value: 'Baixa', emoji: '🟢' },
                            { label: 'Normal', value: 'Normal', emoji: '🟡' },
                            { label: 'Alta', value: 'Alta', emoji: '🔴' }
                        ])
                );
                await interaction.reply({ content: 'Selecione a prioridade deste atendimento:', components: [rowPrioridade], flags: 64 });
                const select = await interaction.channel.awaitMessageComponent({ filter: (m) => m.customId === 'select_prioridade' && m.user.id === interaction.user.id, time: 60000 }).catch(() => null);
                if (!select) return;
                if (ticketInfo) {
                    ticketInfo.prioridade = select.values[0];
                    storage.salvarServidor(interaction.guild.id, configGuild);
                }
                await select.update({ content: `Prioridade definida como **${select.values[0]}**.`, components: [] });
            }
            else if (valor === 'add_nota') {
                const modalNota = new ModalBuilder().setCustomId('modal_nota').setTitle('Adicionar Nota Interna');
                modalNota.addComponents(
                    new ActionRowBuilder().addComponents(
                        new TextInputBuilder().setCustomId('nota').setLabel('Conteúdo da nota').setStyle(TextInputStyle.Paragraph).setRequired(true)
                    )
                );
                await interaction.showModal(modalNota);
                const submit = await interaction.awaitModalSubmit({
                    filter: (m) => m.customId === 'modal_nota' && m.user.id === interaction.user.id,
                    time: 60000
                }).catch(() => null);
                if (submit) {
                    const textoNota = submit.fields.getTextInputValue('nota');
                    if (ticketInfo) {
                        ticketInfo.notas.push({ autor: submit.user.tag, texto: textoNota, data: Date.now() });
                        storage.salvarServidor(interaction.guild.id, configGuild);
                        await atualizarPainelTicket(interaction.channel, configGuild, ticketInfo);
                    }
                    await submit.reply({ content: 'Nota interna adicionada com sucesso.', flags: 64 });
                }
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
                    await submit.reply({ content: `Ticket renomeado para: **${novoNome}**`, flags: 64 });
                }
            }
            else if (valor === 'add_user') {
                await interaction.reply({
                    content: '👤 Mencione o usuário que deseja adicionar ao ticket.\nExemplo: @usuario',
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
                        await interaction.followUp({ content: '⚠Nenhum usuário foi mencionado.', flags: 64 });
                    }
                }
            }
            else if (valor === 'remove_user') {
                await interaction.reply({
                    content: '👤 Mencione o usuário que deseja remover do ticket.\nExemplo: @usuario',
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
                        await interaction.followUp({ content: `✅ Usuário ${user} removido do ticket.`, flags: 64 });
                    } else {
                        await interaction.followUp({ content: 'Nenhum usuário foi mencionado.', flags: 64 });
                    }
                }
            }
            return;
        }

        if (interaction.customId === 'menu_membro') {
            const valor = interaction.values[0];

            if (valor === 'notificar_atendentes') {
                const configGuild = storage.getServidor(interaction.guild.id);
                if (configGuild.atendentes && configGuild.atendentes.length) {
                    const mentions = configGuild.atendentes.map(id => `<@&${id}>`).join(' ');
                    await interaction.channel.send(`${mentions} o cliente está aguardando atendimento.`);
                }
                await interaction.reply({ content: 'Atendentes notificados com sucesso.', flags: 64 });
            }
            else if (valor === 'notificar_atendentes_dm') {
                const configGuild = storage.getServidor(interaction.guild.id);
                if (configGuild.atendentes && configGuild.atendentes.length) {
                    for (const id of configGuild.atendentes) {
                        const role = await interaction.guild.roles.fetch(id).catch(() => null);
                        if (!role) continue;
                        for (const membro of role.members.values()) {
                            await membro.send('Um cliente está aguardando atendimento em um dos tickets.').catch(() => {});
                        }
                    }
                }
                await interaction.reply({ content: 'Atendentes notificados por mensagem privada.', flags: 64 });
            }
            return;
        }

        if (interaction.customId === 'abrir_ticket_lista') {
            const tipo = interaction.values[0];
            await abrirTicket(interaction, tipo);
            return;
        }
    }
    } catch (error) {
        await responderErro(interaction, error, 'interactionCreate');
    }
});

async function abrirTicket(interaction, tipo) {
    const guild = interaction.guild;
    const user = interaction.user;

    const configGuild = storage.getServidor(guild.id);

    if (storage.estaNaBlacklist(configGuild, user.id)) {
        return interaction.reply({ content: '🚫 Você está impedido de abrir tickets neste servidor.', flags: 64 });
    }

    const usaTopico = configGuild.tipo === 'topico';
    if (usaTopico && !configGuild.canalTopico) {
        return interaction.reply({ content: 'O canal onde os tickets em tópico são criados ainda não foi configurado. Contate um administrador.', flags: 64 });
    }
    if (!usaTopico && !configGuild.categoria) {
        return interaction.reply({ content: 'A categoria de tickets ainda não foi configurada. Contate um administrador.', flags: 64 });
    }

    if (configGuild.feedback?.pendentes?.[user.id]) {
        return interaction.reply({ content: 'Você possui uma avaliação pendente do seu último ticket. Verifique sua mensagem privada antes de abrir um novo.', flags: 64 });
    }

    if (storage.possuiTicketAberto(configGuild, user.id)) {
        return interaction.reply({ content: '⚠Você já possui um ticket em aberto. Finalize-o antes de abrir um novo.', flags: 64 });
    }

    if (configGuild.horarioInicio && configGuild.horarioFim) {
        try {
            const agora = new Date().toLocaleString('pt-BR', { 
                timeZone: configGuild.fusoHorario || 'America/Sao_Paulo', 
                hour12: false 
            });
            const horaAtual = agora.split(' ')[1]?.slice(0, 5) ?? null;
            
            if (horaAtual) {
                const foraDoHorario = horaAtual < configGuild.horarioInicio || horaAtual > configGuild.horarioFim;
                
                if (foraDoHorario) {
                    const embedHorario = new EmbedBuilder()
                        .setColor('#e74c3c')
                        .setTitle('Fora do Horário de Atendimento')
                        .setDescription(`No momento não estamos em horário de atendimento.\n\nHorário de funcionamento: **${configGuild.horarioInicio} às ${configGuild.horarioFim}**\nFuso horário: ${configGuild.fusoHorario || 'America/Sao_Paulo'}\n\nPor favor, tente novamente dentro do horário de atendimento.`)
                        .setTimestamp();
                    
                    return interaction.reply({ embeds: [embedHorario], flags: 64 });
                }
            }
        } catch (err) {
            console.log(`⚠️ Erro ao verificar horário: ${err.message}`);
        }
    }

    if (!configGuild.contadorTickets) configGuild.contadorTickets = 0;
    configGuild.contadorTickets++;
    const numero = configGuild.contadorTickets.toString().padStart(3, '0');
    const nomeCanal = gerarNomeCanal(configGuild, tipo, user, numero);

    try {
        await interaction.deferReply({ flags: 64 });

        const permissoesBase = [
            { id: guild.id, deny: [PermissionsBitField.Flags.ViewChannel] },
            { id: user.id, allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.SendMessages, PermissionsBitField.Flags.ReadMessageHistory] },
            ...configGuild.atendentes.map(id => ({ id: id, allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.SendMessages, PermissionsBitField.Flags.ReadMessageHistory] }))
        ];

        let canal;
        if (usaTopico) {
            const canalPai = guild.channels.cache.get(configGuild.canalTopico);
            if (!canalPai) {
                await interaction.editReply({ content: 'O canal configurado para tópicos não foi encontrado. Contate um administrador.' });
                return;
            }
            canal = await canalPai.threads.create({
                name: nomeCanal,
                type: ChannelType.PrivateThread,
                invitable: false,
                reason: `Ticket de ${user.tag}`
            });
            await canal.members.add(user.id).catch(() => {});
            for (const cargoId of configGuild.atendentes) {
                const role = await guild.roles.fetch(cargoId).catch(() => null);
                if (!role) continue;
                for (const membro of role.members.values()) {
                    await canal.members.add(membro.id).catch(() => {});
                }
            }
        } else {
            canal = await guild.channels.create({
                name: nomeCanal,
                type: ChannelType.GuildText,
                parent: configGuild.categoria,
                permissionOverwrites: permissoesBase
            });
        }

        const mensagemBoasVindas = configGuild.mensagemBoasVindas.replace(/{nome}/g, user.username).replace(/{user}/g, user.username);

        storage.registrarTicket(configGuild, canal.id, { donoId: user.id, tipo, numero, ehTopico: usaTopico, iaAtiva: Boolean(configGuild.ia?.ativa) });
        const ticketInfo = configGuild.ticketsAbertos[canal.id];

        const mencoesAtendentes = configGuild.atendentes.map(id => `<@&${id}>`).join(' ');
        const conteudoMencao = [`${user}`, mencoesAtendentes].filter(Boolean).join(' | ');

        const mensagemPainel = await canal.send({
            content: conteudoMencao,
            embeds: [construirEmbedTicket(configGuild, ticketInfo, mensagemBoasVindas, guild.name)],
            components: construirComponentesTicket(ticketInfo)
        });
        ticketInfo.painelMessageId = mensagemPainel.id;

        if (configGuild.vozObrigatoria && configGuild.categoriaVoz) {
            const categoriaVoz = guild.channels.cache.get(configGuild.categoriaVoz);
            if (categoriaVoz && categoriaVoz.type === ChannelType.GuildCategory) {
                try {
                    const canalVoz = await guild.channels.create({
                        name: `suporte-${user.username}`.toLowerCase().slice(0, 100),
                        type: ChannelType.GuildVoice,
                        parent: categoriaVoz.id,
                        permissionOverwrites: [
                            { id: guild.id, deny: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.Connect] },
                            { id: user.id, allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.Connect, PermissionsBitField.Flags.Speak] },
                            ...configGuild.atendentes.map(id => ({ id, allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.Connect, PermissionsBitField.Flags.Speak] }))
                        ],
                        reason: `Canal de voz obrigatório do ticket ${canal.name}`
                    });
                    ticketInfo.vozId = canalVoz.id;
                    await canal.send({ content: `🔊 Canal de voz criado automaticamente: ${canalVoz}` }).catch(() => {});
                } catch (erroVoz) {
                    console.log(`⚠️ Não foi possível criar o canal de voz obrigatório: ${erroVoz.message}`);
                }
            }
        }

        await enviarLogEmbed(configGuild, guild, 'Ticket aberto', '#57F287', [
            { name: 'Ticket', value: canal.name, inline: true },
            { name: 'Cliente', value: `${user}`, inline: true },
            { name: 'Tipo', value: usaTopico ? 'Tópico' : tipo, inline: true }
        ]);

        storage.salvarServidor(guild.id, configGuild);
        await interaction.editReply({ content: `Ticket criado com sucesso: ${canal}` });

    } catch (err) {
        console.log(err);
        if (interaction.deferred) {
            await interaction.editReply({ content: 'Ocorreu um erro ao criar o ticket. Caso o problema persista, contate a Nive Bots.' });
        } else {
            await interaction.reply({ content: 'Ocorreu um erro ao criar o ticket. Caso o problema persista, contate a Nive Bots.', flags: 64 
       });
     }
   }
}

client.abrirTicketDireto = abrirTicket;

(async () => {
    // Restaura as configurações da nuvem para o disco do container
    try {
        await cloudSync.pullFromCloud();
    } catch (err) {
        console.error('⚠️ [cloudSync] Erro no sync inicial da nuvem:', err.message);
    }

    const token = process.env.DISCORD_TOKEN || process.env.TOKEN || config.token;
    if (!token || token === 'd' || token === '') {
        console.log('ℹ️ [Discord] Nenhum TOKEN real configurado (config.token="d"). O servidor HTTP embutido está ativo e pronto.');
        console.log('💡 Dica: No painel do Render, adicione a variável de ambiente TOKEN com seu token de bot do Discord.');
    } else {
        client.login(token).catch(error => console.error('❌ [login Discord]', error.message));
    }
})();
