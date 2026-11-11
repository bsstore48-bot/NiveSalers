const database = require('./database.js');

function getPlano(userId) {
    return database.getPlano(userId);
}

function podeConfigurarBoasVindas(plano) {
    return plano !== 'Grátis';
}

function podeTicketDM(plano) {
    return plano === 'VIP';
}

function getLimiteAtendentes(plano) {
    if (plano === 'VIP') return 467;
    if (plano === 'Premium') return 7;
    return 5;
}

module.exports = { getPlano, podeConfigurarBoasVindas, podeTicketDM, getLimiteAtendentes };
