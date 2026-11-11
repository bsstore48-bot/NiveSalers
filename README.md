# NiveSalers — Discord Tickets Bot & Cloud Persistence Service

Bot profissional de atendimento por tickets para Discord com servidor HTTP embutido e sistema de persistência em nuvem desenhado especialmente para hospedagem no **Render**.

---

## 🚀 Novidades e Correções Implementadas

1. **Servidor HTTP Embutido (Render Ready & Headless):**
   - Escuta na porta `PORT` definida pelo Render (ou 3000 por padrão).
   - Impede que o serviço seja derrubado por inatividade ou timeout no Render.
   - Endpoint `/health` e `/ping` para monitoramento 24/7 sem painel web.

2. **Sistema de Cloud Storage (Sem perda de dados em deploys):**
   - No Render, o disco local é efêmero (reinicializações ou novos deploys apagam arquivos locais).
   - O módulo `utils/cloudSync.js` sincroniza automaticamente todas as configurações de clientes (`dados/servidores/*.json`), tickets em aberto e keys de licença (`keys.json`) com o GitHub / nuvem.
   - Ao iniciar no Render, o bot puxa instantaneamente o backup mais recente, garantindo que nenhum cliente que comprou acesso perca suas configurações.
   - Sincronização periódica (a cada 10 minutos) e sincronização sob demanda com *debounce* a cada alteração de configuração.

3. **Correções de Erros no Código Original:**
   - **`utils/vercelDeploy.js`:** Corrigido erro de sintaxe com template literal truncado em `publicarTranscript`.
   - **`utils/ticketManager.js`:** Adicionadas as importações faltantes de modais do Discord.js (`ModalBuilder`, `TextInputBuilder`, `TextInputStyle`).
   - **`utils/database.js`:** Sincronizado com `utils/storage.js` e implementada a função `getPlano(id)` que estava ausente e causava exceções não tratadas no `utils/premiumVIP.js`.
   - **`commands/key.js`:** Corrigida a validação de servidor. Agora clientes novos que executam `/key` têm sua configuração criada e salva automaticamente sem o erro `❌ Servidor não encontrado na database!`.
   - **`commands/abrir.js`:** Implementada a execução do comando `/abrir` para criar tickets diretamente em vez de função vazia que gerava timeout na API do Discord.
   - **`index.js`:** Fallback seguro de autenticação (usando `process.env.TOKEN || process.env.DISCORD_TOKEN || config.token`) e tratamento de exceção no registro de comandos slash.

---

## 🛠️ Variáveis de Ambiente no Render

| Variável | Descrição | Padrão / Exemplo |
| :--- | :--- | :--- |
| `TOKEN` | Token do Bot no Discord Developer Portal | `OT...` |
| `PORT` | Porta HTTP injetada automaticamente pelo Render | `10000` ou `3000` |
| `GITHUB_TOKEN` | Token com permissão `repo` para sincronização de dados | `ghp_...` |
| `GITHUB_REPO` | Repositório onde o backup de nuvem é mantido | `bsstore48-bot/NiveSalers` |
| `GITHUB_DATA_BRANCH` | Branch onde os dados de clientes são persistidos | `cloud-data` |
| `NODE_ENV` | Ambiente de execução | `production` |

---

## 📡 Endpoints HTTP (Sem painel web)

- `GET /` — Status geral em formato JSON (tempo online, ping, servidores conectados, status da nuvem).
- `GET /health` — Health check (retorna `200 OK`).
- `GET /api/cloud/status` — Status da sincronização na nuvem.
- `POST /api/cloud/sync` — Força sincronização imediata com a nuvem.
- `POST /api/cloud/pull` — Restaura as configurações da nuvem para o container local.
- `GET /api/cloud/backup` — Exporta e baixa o arquivo JSON com todas as configurações de clientes.
- `POST /api/cloud/restore` — Restaura um snapshot JSON enviado no corpo da requisição.
