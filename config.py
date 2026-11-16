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
PORT = int(os.environ.get("PORT", 7860))

# Configurações de Nuvem / Persistência
MONGO_URI = os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI") or ""
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.environ.get("GITHUB_REPO", "bsstore48-bot/NiveSalers").strip()
HF_DB_TOKEN = (os.environ.get("HF_DB_TOKEN") or os.environ.get("HF_TOKEN") or "").strip()
HF_DB_REPO = os.environ.get("HF_DB_REPO", "voidmc/nivebots-db").strip()

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
    },
    "settings": {
        "id": "1561908832173826048",
        "name": "settings",
        "tag": "<:settings:1561908832173826048>",
        "fallback": "⚙️"
    },
    "folder": {
        "id": "1561907786986561586",
        "name": "folder",
        "tag": "<:folder:1561907786986561586>",
        "fallback": "📁"
    },
    "on": {
        "id": "1561908741073281054",
        "name": "on",
        "tag": "<:on:1561908741073281054>",
        "fallback": "🟢"
    },
    "double_speech": {
        "id": "1561906215834091660",
        "name": "double_speech",
        "tag": "<:double_speech:1561906215834091660>",
        "fallback": "💬"
    },
    "cargo": {
        "id": "1555767392552886414",
        "name": "cargo",
        "tag": "<:cargo:1555767392552886414>",
        "fallback": "🛡️"
    },
    "member": {
        "id": "1561907903688876064",
        "name": "member",
        "tag": "<:member:1561907903688876064>",
        "fallback": "👤"
    },
    "pin": {
        "id": "1561908764532146246",
        "name": "pin",
        "tag": "<:pin:1561908764532146246>",
        "fallback": "📌"
    },
    "correto": {
        "id": "1560996992006496367",
        "name": "correto",
        "tag": "<:correto:1560996992006496367>",
        "fallback": "✅"
    },
    "ban": {
        "id": "1561906116030505050",
        "name": "ban",
        "tag": "<:ban:1561906116030505050>",
        "fallback": "🔨"
    },
    "rocket": {
        "id": "1561482854133669908",
        "name": "rocket",
        "tag": "<:rocket:1561482854133669908>",
        "fallback": "🚀"
    },
    "calendar": {
        "id": "1561906133155708989",
        "name": "calendar",
        "tag": "<:calendar:1561906133155708989>",
        "fallback": "📅"
    },
    "clock": {
        "id": "1561906156593479740",
        "name": "clock",
        "tag": "<:clock:1561906156593479740>",
        "fallback": "🕒"
    }
}
