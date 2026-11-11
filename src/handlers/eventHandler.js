const fs = require('fs');
const path = require('path');
const logger = require('../utils/logger.js');

function loadEvents(client) {
    const eventsPath = path.join(__dirname, '..', 'events');
    if (!fs.existsSync(eventsPath)) return;

    const folders = fs.readdirSync(eventsPath);

    for (const folder of folders) {
        const folderPath = path.join(eventsPath, folder);
        if (!fs.statSync(folderPath).isDirectory()) continue;

        const files = fs.readdirSync(folderPath).filter(f => f.endsWith('.js'));
        for (const file of files) {
            try {
                const event = require(path.join(folderPath, file));
                const eventName = event.name || file.split('.')[0];

                if (event.once) {
                    client.once(eventName, (...args) => event.execute(...args, client));
                } else {
                    client.on(eventName, (...args) => event.execute(...args, client));
                }
                logger.info(`Evento registrado: ${eventName} [${folder}]`);
            } catch (err) {
                logger.error(`Falha ao registrar evento ${file}: ${err.message}`);
            }
        }
    }
}

module.exports = { loadEvents };
