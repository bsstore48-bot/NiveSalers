const fs = require('fs');
const path = require('path');

const PASTA_DADOS = path.join(__dirname, '..', 'dados');
const PASTA_SERVIDORES = path.join(PASTA_DADOS, 'servidores');
const ARQUIVO_ANTIGO = path.join(__dirname, '..', 'dados.json');

function garantirPasta() {
    fs.mkdirSync(PASTA_SERVIDORES, { recursive: true });
}

function caminhoServidor(guildId) {
    return path.join(PASTA_SERVIDORES, `${guildId}.json`);
}

function padrao() {
    return {
        titulo: '🎫 Sistema de Tickets',
        descricao: 'Clique na opção abaixo para abrir um ticket com a nossa equipe.',
        cor: '#2b2d31',
        estilo: 'botao',
        painelModo: 'varios',
        botaoUnico: 'Abrir ticket',
        botoes: ['Suporte', 'Dúvidas', 'Reportar', 'Parceria'],
        tipos: {},
        categoria: null,
        tipo: 'canal',
        atendentes: [],
        logs: null,
        horarioInicio: null,
        horarioFim: null,
        fusoHorario: 'America/Sao_Paulo',
        diasFuncionamento: [],
        mensagemBoasVindas: `📌 Olá {user}, seja bem-vindo(a) ao nosso atendimento.\n\n✅ Seu ticket foi aberto com sucesso.\n⏳ Em breve um atendente irá lhe auxiliar.\n\n📝 Enquanto isso, descreva com clareza o seu problema ou dúvida.\n\n🔹 Evite o envio de mensagens repetidas.\n🔹 As solicitações são atendidas em ordem de chegada.\n\n🔒 Este canal é privado. Apenas você e a equipe responsável possuem acesso.\n\n🙏 Agradecemos pela sua paciência e compreensão.`,
        contadorTickets: 0,
        plano: 'Gratis',
        banner: null,
        footer: null,
        footerAutor: 'Nive Bots',
        transcriptModo: 'txt',
        categoriaVoz: null,
        canalTopico: null,
        vozObrigatoria: false,
        nomeCanalFormato: '{tipo}・{user}・{numero}',
        ticketsAbertos: {},
        blacklist: [],
        ia: {
            ativa: false,
            modoNiveIA: false,
            apiKeyPropria: null,
            prompt: null,
            aguardandoPrompt: false,
            aguardandoConfirmacao: false,
            promptPendente: null
        },
        feedback: {
            ativo: false,
            canalLogs: null,
            pendentes: {}
        }
    };
}

function normalizar(config) {
    const base = padrao();
    const resultado = { ...base, ...config };
    resultado.feedback = { ...base.feedback, ...(config.feedback || {}) };
    resultado.tipos = { ...(config.tipos || {}) };
    resultado.painelModo = resultado.painelModo === 'um' ? 'um' : 'varios';
    resultado.botaoUnico = resultado.botaoUnico || 'Abrir ticket';
    resultado.feedback.pendentes = { ...(config.feedback?.pendentes || {}) };
    resultado.ticketsAbertos = { ...(config.ticketsAbertos || {}) };
    resultado.footerAutor = resultado.footerAutor || 'Nive Bots';
    resultado.transcriptModo = resultado.transcriptModo === 'site' ? 'site' : 'txt';
    resultado.blacklist = Array.isArray(config.blacklist) ? config.blacklist : [];
    resultado.ia = { ...base.ia, ...(config.ia || {}) };
    resultado.vozObrigatoria = Boolean(config.vozObrigatoria);
    return resultado;
}

function migrarDadosAntigos(guildId) {
    if (!fs.existsSync(ARQUIVO_ANTIGO)) return null;
    try {
        const antigo = JSON.parse(fs.readFileSync(ARQUIVO_ANTIGO, 'utf8'));
        return antigo.tickets?.[guildId] || null;
    } catch {
        return null;
    }
}

function existeServidor(guildId) {
    return fs.existsSync(caminhoServidor(guildId));
}

function getServidor(guildId) {
    garantirPasta();
    if (existeServidor(guildId)) {
        const bruto = JSON.parse(fs.readFileSync(caminhoServidor(guildId), 'utf8'));
        return normalizar(bruto);
    }
    const migrado = migrarDadosAntigos(guildId);
    const config = normalizar(migrado || {});
    salvarServidor(guildId, config);
    return config;
}

function salvarServidor(guildId, config) {
    garantirPasta();
    fs.writeFileSync(caminhoServidor(guildId), JSON.stringify(config, null, 2));
    try {
        const cloudSync = require('./cloudSync.js');
        cloudSync.agendarSincronizacao();
    } catch {}
}

function listarServidores() {
    garantirPasta();
    return fs.readdirSync(PASTA_SERVIDORES).filter(f => f.endsWith('.json')).map(f => f.replace('.json', ''));
}

function registrarTicket(config, canalId, dados) {
    config.ticketsAbertos[canalId] = {
        donoId: dados.donoId,
        tipo: dados.tipo,
        numero: dados.numero,
        criadoEm: Date.now(),
        responsavel: null,
        prioridade: 'Normal',
        motivoFechamento: null,
        notas: [],
        donoSaiuDoServidor: false,
        abertoPor: dados.donoId,
        fechadoPor: null,
        painelMessageId: dados.painelMessageId || null,
        iaAtiva: Boolean(dados.iaAtiva),
        historicoIa: [],
        vozId: null,
        ehTopico: dados.ehTopico || false
    };
}

function adicionarBlacklist(config, userId) {
    if (!config.blacklist.includes(userId)) config.blacklist.push(userId);
}

function removerBlacklist(config, userId) {
    config.blacklist = config.blacklist.filter(id => id !== userId);
}

function estaNaBlacklist(config, userId) {
    return config.blacklist.includes(userId);
}

function removerTicket(config, canalId) {
    delete config.ticketsAbertos[canalId];
}

function possuiTicketAberto(config, userId) {
    return Object.values(config.ticketsAbertos).some(t => t.donoId === userId);
}

const ITENS_ESSENCIAIS = [
    { chave: 'titulo', nome: 'Título do painel', checar: c => Boolean(c.titulo) },
    { chave: 'descricao', nome: 'Descrição do painel', checar: c => Boolean(c.descricao) },
    { chave: 'categoria', nome: 'Categoria de criação dos tickets', checar: c => Boolean(c.categoria) },
    { chave: 'atendentes', nome: 'Cargos de atendentes', checar: c => Array.isArray(c.atendentes) && c.atendentes.length > 0 },
    { chave: 'botoes', nome: 'Opções/categorias de ticket', checar: c => Array.isArray(c.botoes) && c.botoes.length > 0 },
    { chave: 'mensagemBoasVindas', nome: 'Mensagem de boas-vindas', checar: c => Boolean(c.mensagemBoasVindas) }
];

const ITENS_EXTRA_PREMIUM = [
    { chave: 'logs', nome: 'Canal de logs', checar: c => Boolean(c.logs) }
];

const ITENS_EXTRA_VIP = [
    { chave: 'horario', nome: 'Horário de atendimento', checar: c => Boolean(c.horarioInicio && c.horarioFim) },
    { chave: 'feedback_logs', nome: 'Canal de logs de feedback', checar: c => Boolean(c.feedback?.canalLogs) },
    { chave: 'banner', nome: 'Banner do painel de tickets', checar: c => Boolean(c.banner) }
];

const LIMIAR_POR_PLANO = { Gratis: 50, Premium: 70, VIP: 100 };

function calcularConfiguracao(config, plano) {
    let itensExtra = [];
    if (plano === 'Premium' || plano === 'VIP') itensExtra = itensExtra.concat(ITENS_EXTRA_PREMIUM);
    if (plano === 'VIP') itensExtra = itensExtra.concat(ITENS_EXTRA_VIP);

    const todosItens = [...ITENS_ESSENCIAIS, ...itensExtra];
    const configurados = todosItens.filter(item => item.checar(config));
    const percentual = todosItens.length ? Math.round((configurados.length / todosItens.length) * 100) : 100;

    const faltandoEssencial = ITENS_ESSENCIAIS.filter(item => !item.checar(config));
    const faltandoExtra = itensExtra.filter(item => !item.checar(config));

    const limiar = LIMIAR_POR_PLANO[plano] ?? 50;
    const podeEnviar = faltandoEssencial.length === 0;

    return {
        percentual,
        limiar,
        podeEnviar,
        faltandoEssencial,
        faltandoExtra,
        totalItens: todosItens.length,
        totalConfigurados: configurados.length
    };
}

module.exports = {
    getServidor,
    salvarServidor,
    existeServidor,
    listarServidores,
    registrarTicket,
    removerTicket,
    possuiTicketAberto,
    calcularConfiguracao,
    adicionarBlacklist,
    removerBlacklist,
    estaNaBlacklist
};
