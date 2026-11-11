"""
NiveSalers - Ticket Bot Configuration
"""
import os
from typing import Dict, Any
from dotenv import load_dotenv

# Carrega variáveis de ambiente de um arquivo .env se presente
load_dotenv()

# Tokens e IDs essenciais do Discord
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "").strip()
APPLICATION_ID = os.environ.get("APPLICATION_ID", "").strip()

# Porta para o servidor HTTP embutido (Render utiliza a variável $PORT)
PORT = int(os.environ.get("PORT", 8080))

# Configurações de Nuvem / Persistência
MONGO_URI = os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI") or ""
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.environ.get("GITHUB_REPO", "bsstore48-bot/NiveSalers").strip()

# Cor padrão das embeds do sistema (Branco puro 0xFFFFFF)
EMBED_COLOR_DEFAULT = 0xFFFFFF

# Emojis prioritários do painel de configuração (com tags exatas fornecidas)
PRIORITY_EMOJIS: Dict[str, Dict[str, Any]] = {
    "bot": {
        "id": "1557140838285582438",
        "name": "bot",
        "tag": "<:bot:1557140838285582438>",
        "fallback": "🤖"
    },
    "information": {
        "id": "1561907852124225599",
        "name": "information",
        "tag": "<:information:1561907852124225599>",
        "fallback": "ℹ️"
    },
    "cloud": {
        "id": "1561906158984233031",
        "name": "cloud",
        "tag": "<:cloud:1561906158984233031>",
        "fallback": "☁️"
    },
    "reload": {
        "id": "1561908806584115210",
        "name": "reload",
        "tag": "<:reload:1561908806584115210>",
        "fallback": "🔄"
    },
    "reaction_add": {
        "id": "1561908795226198026",
        "name": "reaction_add",
        "tag": "<:reaction_add:1561908795226198026>",
        "fallback": "✨"
    },
    "edit": {
        "id": "1561906222062506015",
        "name": "edit",
        "tag": "<:edit:1561906222062506015>",
        "fallback": "✏️"
    },
    "embed": {
        "id": "1561906227305521172",
        "name": "embed",
        "tag": "<:embed:1561906227305521172>",
        "fallback": "📄"
    },
    "image": {
        "id": "1561907844142342196",
        "name": "image",
        "tag": "<:image:1561907844142342196>",
        "fallback": "🖼️"
    },
    "colors": {
        "id": "1561906164810125362",
        "name": "colors",
        "tag": "<:colors:1561906164810125362>",
        "fallback": "🎨"
    }
}
