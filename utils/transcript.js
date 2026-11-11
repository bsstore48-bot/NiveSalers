const fs = require('fs');
const path = require('path');

function escapar(valor = '') {
    return String(valor).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function slug(valor = 'ticket') {
    return String(valor).normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-zA-Z0-9_-]+/g, '-').replace(/^-|-$/g, '').toLowerCase() || 'ticket';
}
async function coletarMensagens(canal) {
    const mensagens = await canal.messages.fetch({ limit: 100 });
    return [...mensagens.values()].reverse();
}
async function gerar(canal, interaction) {
    const mensagens = await coletarMensagens(canal);
    const conteudo = mensagens.map(m => `[${m.createdAt.toLocaleString('pt-BR')}] ${m.author.tag}: ${m.content || '(sem texto)'}`).join('\n');
    const nomeArquivo = path.join(__dirname, '..', `${canal.id}.txt`);
    fs.writeFileSync(nomeArquivo, conteudo, 'utf8');
    await interaction.reply({ files: [nomeArquivo], flags: 64 });
    fs.unlinkSync(nomeArquivo);
}
function gerarSlugTicket(nomeUsuario, nomeServidor) {
    return `${slug(nomeUsuario)}-${slug(nomeServidor)}`;
}

async function gerarHtml(canal, motivo, autor = 'Nive Bots', dados = {}) {
    const mensagens = await coletarMensagens(canal);
    const itens = mensagens.map(m => `<div class="message"><div class="msg-avatar user1">${escapar((m.author.username || m.author.tag || '?')[0].toUpperCase())}</div><div class="msg-content"><div class="msg-header"><span class="username">${escapar(m.author.tag)}</span><span class="timestamp">${escapar(m.createdAt.toLocaleString('pt-BR'))}</span></div><div class="msg-text">${escapar(m.content || '(sem texto)').replace(/\n/g, '<br>')}</div></div></div>`).join('\n');
    const modelo = fs.readFileSync(path.join(__dirname, '..', 'transcript', 'index.html'), 'utf8');
    const mapa = {
        '{{TICKET_NAME}}': escapar(canal.name), '{{GENERATED_AT}}': escapar(new Date().toLocaleString('pt-BR')),
        '{{CLOSE_REASON}}': escapar(motivo || 'Não informado'), '{{FOOTER}}': escapar(autor), '{{MESSAGES}}': itens,
        '{{TICKET_ID}}': escapar(dados.ticketId || canal.id), '{{OPENED_BY}}': escapar(dados.abertoPor || 'Não informado'),
        '{{CLOSED_BY}}': escapar(dados.fechadoPor || 'Não informado'), '{{ATTENDANT}}': escapar(dados.responsavel || 'Não assumido')
    };
    let html = modelo;
    for (const [chave, valor] of Object.entries(mapa)) html = html.replaceAll(chave, valor);
    const inicioMensagens = html.indexOf('<div class="messages">');
    const marcadorFim = '\n    </div>\n\n    <!-- Footer do chat';
    const fimMensagens = html.indexOf(marcadorFim, inicioMensagens);
    if (inicioMensagens >= 0 && fimMensagens > inicioMensagens) html = html.slice(0, inicioMensagens) + '<div class="messages">\n' + itens + '\n    </div>' + html.slice(fimMensagens + '\n    </div>'.length);
    html = html.replaceAll('#7421', `#${escapar(dados.ticketId || canal.id)}`).replaceAll('NiveBOTS • Suporte', `${escapar(autor)} • Ticket`);
    const nomeArquivo = dados.slugPublico || slug(canal.id);
    const arquivo = path.join(__dirname, '..', 'transcript', `${nomeArquivo}.html`);
    fs.writeFileSync(arquivo, html, 'utf8');
    return { arquivo, html, slugPublico: nomeArquivo };
}
module.exports = { gerar, gerarHtml, slug, gerarSlugTicket };
