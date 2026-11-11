const cores = {
    reset: '\x1b[0m',
    bright: '\x1b[1m',
    dim: '\x1b[2m',
    red: '\x1b[31m',
    green: '\x1b[32m',
    yellow: '\x1b[33m',
    blue: '\x1b[34m',
    magenta: '\x1b[35m',
    cyan: '\x1b[36m',
    white: '\x1b[37m',
    gray: '\x1b[90m'
};

function timestamp() {
    return `${cores.gray}[${new Date().toLocaleTimeString('pt-BR')}]${cores.reset}`;
}

const logger = {
    info: (msg, ...args) => console.log(`${timestamp()} ${cores.blue}ℹ INFO${cores.reset}  ${msg}`, ...args),
    success: (msg, ...args) => console.log(`${timestamp()} ${cores.green}✔ SUCESSO${cores.reset}  ${msg}`, ...args),
    warn: (msg, ...args) => console.warn(`${timestamp()} ${cores.yellow}⚠ AVISO${cores.reset}  ${msg}`, ...args),
    error: (msg, ...args) => console.error(`${timestamp()} ${cores.red}✖ ERRO${cores.reset}  ${msg}`, ...args),
    discord: (msg, ...args) => console.log(`${timestamp()} ${cores.magenta}🤖 DISCORD${cores.reset}  ${msg}`, ...args),
    http: (msg, ...args) => console.log(`${timestamp()} ${cores.cyan}🌐 HTTP${cores.reset}  ${msg}`, ...args),
    cloud: (msg, ...args) => console.log(`${timestamp()} ${cores.bright}${cores.cyan}☁ CLOUD${cores.reset}  ${msg}`, ...args)
};

module.exports = logger;
