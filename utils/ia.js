

const fs = require('fs');
const path = require('path');

const CAMINHO_TOKENS = path.join(__dirname, '..', 'tokens.json');

function carregarTokens() {
    try {
        return JSON.parse(fs.readFileSync(CAMINHO_TOKENS, 'utf8'));
    } catch (erro) {
        console.log(`⚠️ [ia.js] Não foi possível ler tokens.json: ${erro.message}`);
        return { apiKeys: [], niveIA: { apiKeys: [] } };
    }
}

const indices = { propria: 0, niveIA: 0 };
const chavesEsgotadas = new Set();

function codigoIndicaEsgotada(status) {
    return status === 401 || status === 403 || status === 429;
}

async function chamarChave(apiKey, endpoint, modelo, prompt, mensagemUsuario, historico = []) {
    const mensagens = [
        { role: 'system', content: prompt || 'Você é um assistente de suporte simpático e objetivo.' },
        ...historico,
        { role: 'user', content: mensagemUsuario }
    ];

    const resposta = await fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify({ model: modelo, messages: mensagens, max_tokens: 500 })
    });

    if (!resposta.ok) {
        const erro = new Error(`HTTP ${resposta.status}`);
        erro.status = resposta.status;
        throw erro;
    }

    const dados = await resposta.json();
    const texto = dados?.choices?.[0]?.message?.content;
    if (!texto) throw new Error('Resposta da IA veio vazia.');
    return texto.trim();
}

/**
 * Tenta responder usando uma lista de API keys, rotacionando para a próxima
 * automaticamente sempre que uma chave falha por estar esgotada/inválida.
 */
async function tentarComRotacao(lista, chaveGrupo, endpoint, modelo, prompt, mensagemUsuario, historico) {
    if (!Array.isArray(lista) || lista.length === 0) {
        console.log(`⚠️ [ia.js] Nenhuma API key configurada para o grupo "${chaveGrupo}".`);
        return null;
    }

    const total = lista.length;
    for (let tentativa = 0; tentativa < total; tentativa++) {
        const posicao = (indices[chaveGrupo] + tentativa) % total;
        const apiKey = lista[posicao];
        const idChave = `${chaveGrupo}:${posicao}`;

        if (chavesEsgotadas.has(idChave)) continue;

        try {
            const texto = await chamarChave(apiKey, endpoint, modelo, prompt, mensagemUsuario, historico);
            indices[chaveGrupo] = posicao;
            return texto;
        } catch (erro) {
            if (codigoIndicaEsgotada(erro.status)) {
                console.log(`❌ [ia.js] API key #${posicao} do grupo "${chaveGrupo}" esgotada/inválida (HTTP ${erro.status}). Marcando como indisponível e tentando a próxima.`);
                chavesEsgotadas.add(idChave);
            } else {
                console.log(`❌ [ia.js] Erro ao chamar API key #${posicao} do grupo "${chaveGrupo}": ${erro.message}`);
            }
        }
    }

    console.log(`❌ [ia.js] Todas as API keys do grupo "${chaveGrupo}" falharam.`);
    return null;
}

/**
 * Gera uma resposta de IA para um ticket.
 * @param {object} configIa - config.ia salvo do servidor (prompt, modoNiveIA, apiKeyPropria)
 * @param {string} mensagemUsuario - mensagem enviada pelo cliente
 * @param {Array} historico - histórico opcional [{role, content}]
 */
async function responder(configIa, mensagemUsuario, historico = []) {
    const tokens = carregarTokens();
    const prompt = configIa?.prompt || 'Você é um assistente de suporte simpático e objetivo.';

    if (configIa?.modoNiveIA) {
        return tentarComRotacao(
            tokens.niveIA?.apiKeys,
            'niveIA',
            tokens.niveIA?.endpoint || tokens.endpoint,
            tokens.niveIA?.modelo || tokens.modelo,
            prompt,
            mensagemUsuario,
            historico
        );
    }

    if (configIa?.apiKeyPropria) {
        return tentarComRotacao(
            [configIa.apiKeyPropria],
            'propria',
            tokens.endpoint,
            tokens.modelo,
            prompt,
            mensagemUsuario,
            historico
        );
    }

    return tentarComRotacao(tokens.apiKeys, 'geral', tokens.endpoint, tokens.modelo, prompt, mensagemUsuario, historico);
}

module.exports = { responder, carregarTokens };
