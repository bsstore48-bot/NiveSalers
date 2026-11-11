"""
NiveSalers - Cloud Storage & Persistent Database
Sistema resiliente de persistência para hospedagem no Render.
Garante que reinícios, atualizações e builds não percam as configurações dos servidores.
"""
import os
import json
import asyncio
from typing import Dict, Any, Optional
import aiohttp

import config
from utils.logger import logger

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_BASE_DIR, "database", "data")
BACKUP_FILE = os.path.join(DATA_DIR, "cloud_backup.json")

class CloudStorage:
    _guilds_data: Dict[str, Dict[str, Any]] = {}
    _mongo_client = None
    _mongo_db = None
    _is_initialized: bool = False

    @classmethod
    async def initialize(cls) -> None:
        """Inicializa conexões e restaura dados da nuvem."""
        if cls._is_initialized:
            return

        os.makedirs(DATA_DIR, exist_ok=True)

        # 1. Tenta carregar do backup local em disco
        cls._load_from_local_disk()

        # 2. Se configurado MongoDB Atlas, inicializa driver motor
        if config.MONGO_URI:
            try:
                import motor.motor_asyncio
                cls._mongo_client = motor.motor_asyncio.AsyncIOMotorClient(config.MONGO_URI)
                cls._mongo_db = cls._mongo_client.get_default_database("nivesalers_db")
                logger.info("Conexão com MongoDB Atlas estabelecida com sucesso.")
                await cls._sync_from_mongo()
            except Exception as e:
                logger.error(f"Erro ao conectar com MongoDB Atlas: {e}")

        # 3. Se configurado GitHub Token e sem MongoDB, tenta restaurar dados de backup da nuvem GitHub
        elif config.GITHUB_TOKEN:
            try:
                await cls._sync_from_github()
            except Exception as e:
                logger.warning(f"Aviso ao consultar backup no GitHub: {e}")

        cls._is_initialized = True
        logger.info(f"💾 CloudStorage pronto. {len(cls._guilds_data)} servidores carregados na memória.")

    @classmethod
    def _default_guild_config(cls, guild_id: str) -> Dict[str, Any]:
        """Estrutura padrão de configuração de atendimento por servidor."""
        return {
            "guild_id": str(guild_id),
            "painel": {
                "titulo": "Painel de Atendimento",
                "descricao": "Abra um ticket para falar com a nossa equipe.",
                "cor": config.EMBED_COLOR_DEFAULT,
                "banner_url": None,
                "canal_id": None,
                "categoria_id": None,
                "cargo_suporte_id": None,
                "modo_container": True,
                "atualizacao_automatica": True,
                "paineis_enviados": []
            },
            "categorias_ticket": [
                {
                    "id": "suporte_geral",
                    "nome": "Suporte Geral",
                    "descricao": "Tire suas dúvidas ou solicite suporte.",
                    "emoji": "information"
                }
            ],
            "logs": {
                "canal_logs_id": None,
                "transcripts_ativo": True
            },
            "horario_atendimento": {
                "ativo": False,
                "inicio": "08:00",
                "fim": "18:00"
            }
        }

    @classmethod
    def get_guild_config(cls, guild_id: str) -> Dict[str, Any]:
        """Obtém a configuração do servidor (ou cria uma padrão)."""
        gid = str(guild_id)
        if gid not in cls._guilds_data:
            cls._guilds_data[gid] = cls._default_guild_config(gid)
        return cls._guilds_data[gid]

    @classmethod
    async def save_guild_config(cls, guild_id: str, data: Dict[str, Any]) -> None:
        """Salva a configuração do servidor com sincronização automática na nuvem."""
        gid = str(guild_id)
        cls._guilds_data[gid] = data

        # 1. Salva em disco local com escrita atômica
        cls._save_to_local_disk()

        # 2. Sincroniza com MongoDB se ativo
        if cls._mongo_db is not None:
            try:
                collection = cls._mongo_db["guild_configs"]
                await collection.update_one(
                    {"guild_id": gid},
                    {"$set": data},
                    upsert=True
                )
            except Exception as e:
                logger.error(f"Erro ao persistir no MongoDB para servidor {gid}: {e}")

        # 3. Dispara sincronização com GitHub em segundo plano se configurado
        if config.GITHUB_TOKEN and not cls._mongo_db:
            asyncio.create_task(cls._save_to_github())

    @classmethod
    def _save_to_local_disk(cls) -> None:
        """Persiste em arquivo JSON local com escrita temporária segura."""
        try:
            temp_file = BACKUP_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(cls._guilds_data, f, indent=4, ensure_ascii=False)
            os.replace(temp_file, BACKUP_FILE)
        except Exception as e:
            logger.error(f"Erro ao salvar backup em disco local: {e}")

    @classmethod
    def _load_from_local_disk(cls) -> None:
        """Carrega configurações do backup em disco local."""
        if os.path.exists(BACKUP_FILE):
            try:
                with open(BACKUP_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        cls._guilds_data.update(data)
                        logger.info(f"Carregadas configurações de {len(data)} servidores do disco local.")
            except Exception as e:
                logger.error(f"Erro ao ler backup local: {e}")

    @classmethod
    async def _sync_from_mongo(cls) -> None:
        """Restaura todos os documentos do MongoDB Atlas."""
        if cls._mongo_db is None:
            return
        try:
            collection = cls._mongo_db["guild_configs"]
            cursor = collection.find({})
            count = 0
            async for doc in cursor:
                gid = str(doc.get("guild_id"))
                if gid:
                    doc.pop("_id", None)
                    cls._guilds_data[gid] = doc
                    count += 1
            logger.info(f"Recuperadas configurações de {count} servidores do MongoDB Atlas.")
            cls._save_to_local_disk()
        except Exception as e:
            logger.error(f"Erro ao sincronizar do MongoDB: {e}")

    @classmethod
    async def _sync_from_github(cls) -> None:
        """Restaura backup da nuvem via GitHub API para evitar perda em reinícios no Render."""
        if not config.GITHUB_TOKEN or not config.GITHUB_REPO:
            return

        url = f"https://api.github.com/repos/{config.GITHUB_REPO}/contents/database/data/cloud_backup.json"
        headers = {
            "Authorization": f"token {config.GITHUB_TOKEN}",
            "User-Agent": "NiveSalers-Bot"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        content = res.get("content", "")
                        import base64
                        decoded = base64.b64decode(content).decode("utf-8")
                        remote_data = json.loads(decoded)
                        if isinstance(remote_data, dict):
                            # Mescla dados remotos sem sobrepor alterações mais recentes
                            for gid, cfg in remote_data.items():
                                if gid not in cls._guilds_data:
                                    cls._guilds_data[gid] = cfg
                            logger.info(f"Backup na nuvem restaurado via GitHub: {len(remote_data)} servidores.")
                            cls._save_to_local_disk()
        except Exception as e:
            logger.warning(f"Aviso ao consultar backup no GitHub: {e}")

    @classmethod
    async def _save_to_github(cls) -> None:
        """Salva snapshot atualizado do backup no repositório GitHub em segundo plano."""
        if not config.GITHUB_TOKEN or not config.GITHUB_REPO:
            return

        url = f"https://api.github.com/repos/{config.GITHUB_REPO}/contents/database/data/cloud_backup.json"
        headers = {
            "Authorization": f"token {config.GITHUB_TOKEN}",
            "User-Agent": "NiveSalers-Bot",
            "Content-Type": "application/json"
        }
        try:
            import base64
            serialized = json.dumps(cls._guilds_data, indent=2, ensure_ascii=False)
            b64_content = base64.b64encode(serialized.encode("utf-8")).decode("utf-8")

            async with aiohttp.ClientSession() as session:
                sha = None
                async with session.get(url, headers=headers) as check_resp:
                    if check_resp.status == 200:
                        j = await check_resp.json()
                        sha = j.get("sha")

                payload = {
                    "message": "chore(cloud): auto-sync ticket configurations",
                    "content": b64_content
                }
                if sha:
                    payload["sha"] = sha

                async with session.put(url, headers=headers, json=payload) as put_resp:
                    if put_resp.status in (200, 201):
                        logger.info("Backup na nuvem sincronizado no GitHub com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao sincronizar backup com GitHub: {e}")
