

const fs = require('fs');
const path = require('path');

const CAMINHO_TOKENS = path.join(__dirname, '..', 'tokens.json');
const CAMINHO_INDICE = path.join(__dirname, '..', 'dados', 'transcripts-vercel.json');
const DOMINIO_PUBLICO = 'nivebots.vercel.app';

function carregarTokens() {
    try {
        return JSON.parse(fs.readFileSync(CAMINHO_TOKENS, 'utf8'));
    } catch {
        return {};
    }
}

function carregarIndice() {
    try {
        return JSON.parse(fs.readFileSync(CAMINHO_INDICE, 'utf8'));
    } catch {
        return {};
    }
}

function salvarIndice(indice) {
    fs.mkdirSync(path.dirname(CAMINHO_INDICE), { recursive: true });
    fs.writeFileSync(CAMINHO_INDICE, JSON.stringify(indice, null, 2));
}

/**
 * Publica (ou atualiza) o transcript de um ticket na Vercel.
 * @param {string} slug - identificador único do ticket (ex: joao123-comunidadedobn)
 * @param {string} html - conteúdo HTML único (sem robots.txt, sem mais nada)
 * @returns {Promise<string|null>} URL pública ou null se a Vercel não estiver configurada
 */
async function publicarTranscript(slug, html) {
    const tokens = carregarTokens();
    const vercel = tokens.vercel || {};

    if (!vercel.token || !vercel.projectId) {
        console.log('⚠️ [vercelDeploy] Token/projeto da Vercel não configurados em tokens.json (chave "vercel"). Publicação do site pulada — o TXT continua disponível normalmente.');
        return null;
    }

    const indice = carregarIndice();
    indice[slug] = html;
    salvarIndice(indice);

    const arquivos = Object.entries(indice).map(([slugArquivo, conteudo]) => ({
        file: `transcript-${slugArquivo}/index.html`,
        data: conteudo
    }));

    const query = vercel.teamId ? `?teamId=${encodeURIComponent(vercel.teamId)}` : '';

    try {
        const resposta = await fetch(`https://api.vercel.com/v13/deployments${query}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${vercel.token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: vercel.projectId,
                project: vercel.projectId,
                target: 'production',
                files: arquivos,
                projectSettings: { framework: null }
            })
        });

        if (!resposta.ok) {
            const texto = await resposta.text().catch(() => '');
            console.log(`❌ [vercelDeploy] Falha ao publicar transcript na Vercel (HTTP ${resposta.status}): ${texto}`);
            return null;
        }

        console.log(`✅ [vercelDeploy] Transcript "${slug}" publicado com sucesso.`);
        return `https://${DOMINIO_PUBLICO}/transcript-${slug}/`;
    } catch (erro) {
        console.log(`❌ [vercelDeploy] Erro ao publicar transcript na Vercel: ${erro.message}`);
        return null;
    }
}

module.exports = { publicarTranscript, DOMINIO_PUBLICO };
