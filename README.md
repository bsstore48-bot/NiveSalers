# 🚀 NiveSalers — Discord Bot em JavaScript

Novo bot modular em **JavaScript (Node.js)** desenvolvido com arquitetura limpa, alta estabilidade, servidor HTTP embutido e sistema de persistência em nuvem para hospedagem 24/7 no **Render**.

---

## 📁 Estrutura do Projeto

```
nivesalers/
├── src/
│   ├── config/
│   │   └── index.js              # Variáveis de ambiente e opções globais
│   ├── commands/                 # Comandos Slash organizados por categorias
│   │   ├── general/
│   │   │   ├── ping.js           # Latência e tempo online em tempo real
│   │   │   ├── help.js           # Central de ajuda interativa
│   │   │   └── info.js           # Estatísticas do bot e status da nuvem
│   │   └── admin/
│   │       ├── clear.js          # Limpeza de mensagens em massa
│   │       └── config.js         # Configurações do servidor com salvamento em nuvem
│   ├── events/                   # Manipuladores de eventos do Discord
│   │   ├── client/
│   │   │   └── ready.js          # Inicialização, presença rotativa e registro de comandos
│   │   └── interactions/
│   │       └── interactionCreate.js # Execução segura de comandos, botões e modais
│   ├── handlers/
│   │   ├── commandHandler.js     # Carregador dinâmico de comandos slash
│   │   └── eventHandler.js       # Carregador dinâmico de eventos
│   ├── services/
│   │   ├── cloudStorage.js       # Persistência de dados em nuvem para o Render
│   │   └── httpServer.js         # Servidor HTTP 24/7 para Health Check do Render
│   ├── utils/
│   │   ├── logger.js             # Logger com cores e timestamps
│   │   └── embeds.js             # Modelos padronizados de embeds
│   └── index.js                  # Ponto de entrada da aplicação
├── data/                         # Armazenamento local de configurações (espelhado na nuvem)
├── render.yaml                   # Configuração de deploy do Render (rootDir: .)
├── package.json
└── README.md
```

---

## ☁️ Sistema de Cloud Storage para Render

No Render, o disco local é efêmero (reinicializações ou novos deploys resetam arquivos locais). Para que seus clientes nunca percam configurações:

1. **Recuperação Automática no Boot:** O bot puxa o snapshot mais recente da nuvem (branch `cloud-data` no GitHub ou endpoint configurado).
2. **Auto-Sync:** Toda vez que um administrador altera uma configuração (como em `/config`), os dados são automaticamente sincronizados na nuvem.
3. **Backup Periódico:** Um snapshot preventivo roda a cada 10 minutos.

---

## 🌐 Servidor HTTP Embutido (Sem Painel Web)

O bot conta com um servidor HTTP headless rodando em `process.env.PORT` (padrão 3000):
- `GET /` — Retorna status em JSON (uptime, memória, status da nuvem, latência).
- `GET /health` e `GET /ping` — Endpoints para o Health Check do Render (retornam `200 OK`).

---

## ⚙️ Variáveis de Ambiente no Render

| Variável | Descrição | Exemplo |
| :--- | :--- | :--- |
| `TOKEN` | Token do bot no Discord Developer Portal | `OTk4...` |
| `CLIENT_ID` | Application ID do bot no Discord | `1373832...` |
| `GITHUB_TOKEN` | Token com permissão `repo` para persistência em nuvem | `ghp_...` |
| `GITHUB_REPO` | Repositório de persistência | `bsstore48-bot/NiveSalers` |
| `GITHUB_DATA_BRANCH` | Branch onde os snapshots são guardados | `cloud-data` |
| `PORT` | Porta HTTP (injetada automaticamente pelo Render) | `10000` |
