const LIMITE_OPCOES_DISCORD = 25;

function limitarOpcoes(collection, montar) {
    const total = collection?.size ?? collection?.length ?? 0;
    const itens = collection?.map ? collection.map(montar) : Array.from(collection || [], montar);
    return { opcoes: itens.slice(0, LIMITE_OPCOES_DISCORD), total, truncado: total > LIMITE_OPCOES_DISCORD };
}

async function responderErro(interaction, erro, contexto = 'interação') {
    console.error(`[${contexto}]`, erro);
    const payload = { content: 'Não foi possível concluir esta ação. O erro foi registrado e o bot continuará funcionando.', flags: 64 };
    try {
        if (interaction?.deferred) return await interaction.editReply(payload);
        if (interaction?.replied) return await interaction.followUp(payload);
        return await interaction.reply(payload);
    } catch (falhaResposta) {
        console.error('[resposta de erro]', falhaResposta);
    }
}

function instalarProtecoesGlobais(client) {
    process.on('unhandledRejection', erro => console.error('[unhandledRejection]', erro));
    process.on('uncaughtException', erro => console.error('[uncaughtException — processo mantido ativo]', erro));
    client.on('error', erro => console.error('[Discord client error]', erro));
    client.on('shardError', erro => console.error('[Discord shard error]', erro));
}

module.exports = { LIMITE_OPCOES_DISCORD, limitarOpcoes, responderErro, instalarProtecoesGlobais };
