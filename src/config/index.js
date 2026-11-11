require('dotenv').config();

module.exports = {
    // Discord
    token: process.env.DISCORD_TOKEN || process.env.TOKEN || '',
    clientId: process.env.CLIENT_ID || '',
    ownerId: process.env.OWNER_ID || '',

    // Servidor HTTP (Render)
    port: parseInt(process.env.PORT, 10) || 3000,
    nodeEnv: process.env.NODE_ENV || 'production',

    // Cloud Storage para Render
    githubToken: process.env.GITHUB_TOKEN || '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',
    githubRepo: process.env.GITHUB_REPO || 'bsstore48-bot/NiveSalers',
    githubBranch: process.env.GITHUB_DATA_BRANCH || 'cloud-data',
    cloudSyncUrl: process.env.CLOUD_SYNC_URL || null,

    // Bot Info
    botName: 'NiveSalers',
    version: '3.0.0',
    embedColor: '#5865F2'
};
