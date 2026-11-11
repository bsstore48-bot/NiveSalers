# NiveSalers Ticket Bot 🎫

Bot profissional de tickets e atendimento para Discord desenvolvido em Python, projetado especialmente para execução no **Render** com alta disponibilidade, servidor HTTP embutido e persistência em nuvem para tolerar reinícios sem perda de dados.

## 🚀 Principais Características

- **Servidor HTTP Embutido:** Escuta na porta `$PORT` do Render, mantendo o serviço ativo contra suspensões e atendendo a health checks (`/`, `/health`, `/ping`).
- **Persistência em Nuvem:** Sistema resiliente com suporte a MongoDB Atlas e sincronização remota que evita perda de configurações mesmo em reinícios e builds do Render.
- **Application Emojis Automáticos:** Upload e sincronização direta das imagens originais de emojis com a API do Discord (`POST /applications/{id}/emojis`), permitindo emojis personalizados globais em qualquer servidor sem Nitro.
- **Componentes V2 Ready:** Estrutura modular preparada para receber Layouts e Containers quando os primeiros botões forem implementados.
- **Comando `/configurar painel`:** Embed branca personalizada (`0xFFFFFF`) com texto padronizado e emojis dinâmicos.

## ⚙️ Variáveis de Ambiente

Configure no painel de Environment do Render:

| Variável | Descrição |
| --- | --- |
| `DISCORD_TOKEN` | Token do bot obtido no Discord Developer Portal |
| `APPLICATION_ID` | ID da aplicação no Discord Developer Portal |
| `PORT` | Porta HTTP (definida automaticamente pelo Render como 10000) |
| `MONGO_URI` | String de conexão MongoDB Atlas (para persistência em nuvem) |
| `GITHUB_TOKEN` | Token do GitHub com permissão de repositório (opcional para auto-sync) |

## 🛠️ Instalação Local

```bash
pip install -r requirements.txt
cp .env.example .env
# Preencha suas credenciais no .env
python main.py
```
