"""
NiveSalers - Cloud Storage & Persistent Database
Sistema resiliente de persistência em nuvem (MongoDB Atlas, Hugging Face Dataset privado ou GitHub).
Garante que reinícios, atualizações e rebuilds não percam as configurações dos servidores.
"""
import os
import json
import time
import copy
import base64
import asyncio
import urllib.request
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
    _hf_dirty: bool = False
    _hf_worker_running: bool = False
    _hf_sync_task: Optional[asyncio.Task] = None

    @classmethod
    def _merge_defaults(cls, guild_id: str, loaded: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Garante que qualquer config restaurada tenha todas as chaves padrão sem perder valores salvos."""
        base = cls._default_guild_config(guild_id)
        if not isinstance(loaded, dict):
            return base
        for key, val in loaded.items():
            if isinstance(val, dict) and isinstance(base.get(key), dict):
                merged_sub = copy.deepcopy(base[key])
                for sk, sv in val.items():
                    if isinstance(sv, dict) and isinstance(merged_sub.get(sk), dict):
                        merged_deep = copy.deepcopy(merged_sub[sk])
                        merged_deep.update(sv)
                        merged_sub[sk] = merged_deep
                    else:
                        merged_sub[sk] = sv
                base[key] = merged_sub
            else:
                base[key] = val
        base["guild_id"] = str(guild_id)
        return base

    @classmethod
    async def initialize(cls) -> None:
        """Inicializa conexões e restaura dados da nuvem (nuvem tem prioridade sobre disco local)."""
        if cls._is_initialized:
            return

        os.makedirs(DATA_DIR, exist_ok=True)

        # 1. Carrega fallback local em disco (pode ser sobrescrito pela nuvem logo abaixo)
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

        # 3. Se configurado Hugging Face Dataset privado, restaura dados da nuvem (prioritário)
        elif config.HF_DB_TOKEN and config.HF_DB_REPO:
            try:
                await cls._sync_from_hf_dataset()
            except Exception as e:
                logger.warning(f"Aviso ao consultar backup no Hugging Face Dataset: {e}")

        # 4. Se configurado GitHub Token, tenta restaurar dados de backup da nuvem GitHub
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
                "titulo": None,
                "descricao": None,
                "cor": None,
                "cor_hex": None,
                "banner_url": None,
                "thumbnail_url": None,
                "titulo_configurado": False,
                "descricao_configurada": False,
                "cor_configurada": False,
                "canal_id": None,
                "categoria_id": None,
                "cargo_suporte_id": None,
                "modo_container": True,
                "atualizacao_automatica": True,
                "paineis_enviados": []
            },
            "categorias_ticket": [],
            "logs": {
                "canal_logs_id": None,
                "canal_abertos_id": None,
                "canal_fechados_id": None,
                "canal_assumidos_id": None,
                "transcripts_ativo": True
            },
            "horario_atendimento": {
                "ativo": False,
                "inicio": "08:00",
                "fim": "18:00",
                "dias": {
                    "segunda": {"ativo": False, "inicio": None, "fim": None},
                    "terca": {"ativo": False, "inicio": None, "fim": None},
                    "quarta": {"ativo": False, "inicio": None, "fim": None},
                    "quinta": {"ativo": False, "inicio": None, "fim": None},
                    "sexta": {"ativo": False, "inicio": None, "fim": None},
                    "sabado": {"ativo": False, "inicio": None, "fim": None},
                    "domingo": {"ativo": False, "inicio": None, "fim": None}
                }
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
        cls._guilds_data[gid] = cls._merge_defaults(gid, data)

        # 1. Salva em disco local com escrita atômica
        cls._save_to_local_disk()

        # 2. Sincroniza com MongoDB se ativo
        if cls._mongo_db is not None:
            try:
                collection = cls._mongo_db["guild_configs"]
                await collection.update_one(
                    {"guild_id": gid},
                    {"$set": cls._guilds_data[gid]},
                    upsert=True
                )
            except Exception as e:
                logger.error(f"Erro ao persistir no MongoDB para servidor {gid}: {e}")

        # 3. Sincroniza com Hugging Face Dataset privado em segundo plano (serializado)
        elif config.HF_DB_TOKEN and config.HF_DB_REPO:
            cls._trigger_hf_sync()

        # 4. Dispara sincronização com GitHub em segundo plano se configurado
        elif config.GITHUB_TOKEN:
            asyncio.create_task(cls._save_to_github())

    @classmethod
    def _save_to_local_disk(cls) -> None:
        """Persiste em arquivo JSON local com escrita temporária segura."""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            temp_file = BACKUP_FILE + ".tmp"
            snapshot = copy.deepcopy(cls._guilds_data)
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=4, ensure_ascii=False)
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
                        for gid, cfg in data.items():
                            cls._guilds_data[str(gid)] = cls._merge_defaults(str(gid), cfg)
                        logger.info(f"Carregadas configurações de {len(data)} servidores do disco local.")
            except Exception as e:
                logger.error(f"Erro ao ler backup local: {e}")

    @classmethod
    async def _sync_from_mongo(cls) -> None:
        """Restaura todos os documentos do MongoDB Atlas (sobrescreve cache local)."""
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
                    cls._guilds_data[gid] = cls._merge_defaults(gid, doc)
                    count += 1
            logger.info(f"Recuperadas configurações de {count} servidores do MongoDB Atlas.")
            cls._save_to_local_disk()
        except Exception as e:
            logger.error(f"Erro ao sincronizar do MongoDB: {e}")

    @classmethod
    async def _sync_from_hf_dataset(cls) -> None:
        """Restaura backup da nuvem a partir do Dataset privado no Hugging Face Hub (sobrescreve cache local)."""
        if not config.HF_DB_TOKEN or not config.HF_DB_REPO:
            return

        url = f"https://huggingface.co/datasets/{config.HF_DB_REPO}/resolve/main/cloud_backup.json?t={int(time.time() * 1000)}"
        headers = {
            "Authorization": f"Bearer {config.HF_DB_TOKEN}",
            "Cache-Control": "no-cache, no-store, max-age=0",
            "Pragma": "no-cache",
            "User-Agent": "NiveSalers-Bot"
        }

        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        raw_text = await resp.text()
                        remote_data = json.loads(raw_text)
                        if isinstance(remote_data, dict):
                            for gid, cfg in remote_data.items():
                                gid_str = str(gid)
                                cls._guilds_data[gid_str] = cls._merge_defaults(gid_str, cfg)
                            logger.info(f"Backup restaurado do Hugging Face Dataset ({config.HF_DB_REPO}): {len(remote_data)} servidor(es).")
                            cls._save_to_local_disk()
                    elif resp.status == 404:
                        logger.info("Nenhum backup anterior encontrado no Hugging Face Dataset (primeira execução).")
                    else:
                        body = await resp.text()
                        logger.warning(f"Resposta inesperada ao ler HF Dataset ({resp.status}): {body[:200]}")
        except Exception as e:
            logger.warning(f"Aviso ao restaurar backup do Hugging Face Dataset: {e}")

    @classmethod
    def _build_hf_commit_payload(cls) -> bytes:
        snapshot = copy.deepcopy(cls._guilds_data)
        serialized = json.dumps(snapshot, indent=2, ensure_ascii=False)
        b64_content = base64.b64encode(serialized.encode("utf-8")).decode("ascii")
        ndjson_payload = "\n".join([
            json.dumps({
                "key": "header",
                "value": {"summary": "chore(db): auto-sync ticket configurations"}
            }),
            json.dumps({
                "key": "file",
                "value": {
                    "content": b64_content,
                    "path": "cloud_backup.json",
                    "encoding": "base64"
                }
            })
        ]) + "\n"
        return ndjson_payload.encode("utf-8")

    @classmethod
    def _trigger_hf_sync(cls) -> None:
        """Agenda sincronização serializada com o Dataset privado no Hugging Face Hub."""
        cls._hf_dirty = True
        if not cls._hf_worker_running:
            cls._hf_worker_running = True
            cls._hf_sync_task = asyncio.create_task(cls._hf_sync_worker())

    @classmethod
    async def _hf_sync_worker(cls) -> None:
        """Envia snapshots atualizados em fila sem concorrência para o Hugging Face Dataset."""
        url = f"https://huggingface.co/api/datasets/{config.HF_DB_REPO}/commit/main"
        headers = {
            "Authorization": f"Bearer {config.HF_DB_TOKEN}",
            "Content-Type": "application/x-ndjson",
            "User-Agent": "NiveSalers-Bot"
        }

        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                while cls._hf_dirty:
                    cls._hf_dirty = False
                    payload_bytes = cls._build_hf_commit_payload()

                    saved = False
                    for attempt in range(3):
                        try:
                            async with session.post(url, headers=headers, data=payload_bytes) as resp:
                                if resp.status in (200, 201):
                                    logger.info(f"Configurações persistidas no Hugging Face Dataset ({config.HF_DB_REPO}).")
                                    saved = True
                                    break
                                else:
                                    err_txt = await resp.text()
                                    logger.error(f"Erro ao salvar no HF Dataset (tentativa {attempt+1}, {resp.status}): {err_txt[:200]}")
                        except Exception as e:
                            logger.error(f"Falha de rede ao salvar no HF Dataset (tentativa {attempt+1}): {e}")
                        if not saved and attempt < 2:
                            await asyncio.sleep(1.0 * (attempt + 1))
        finally:
            cls._hf_worker_running = False
            cls._hf_sync_task = None
            if cls._hf_dirty:
                cls._trigger_hf_sync()

    @classmethod
    async def flush(cls) -> None:
        """Aguarda a conclusão de qualquer sincronização pendente com a nuvem."""
        if cls._hf_sync_task is not None and not cls._hf_sync_task.done():
            try:
                await asyncio.wait_for(cls._hf_sync_task, timeout=15)
            except Exception as e:
                logger.warning(f"Aviso ao aguardar flush do CloudStorage: {e}")

    @classmethod
    def flush_sync(cls) -> None:
        """Flush síncrono de emergência durante encerramento do processo (SIGTERM/atexit)."""
        cls._save_to_local_disk()
        if not cls._hf_dirty or not config.HF_DB_TOKEN or not config.HF_DB_REPO:
            return
        try:
            url = f"https://huggingface.co/api/datasets/{config.HF_DB_REPO}/commit/main"
            headers = {
                "Authorization": f"Bearer {config.HF_DB_TOKEN}",
                "Content-Type": "application/x-ndjson",
                "User-Agent": "NiveSalers-Bot"
            }
            payload_bytes = cls._build_hf_commit_payload()
            req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    cls._hf_dirty = False
                    logger.info("Flush síncrono de configurações para o HF Dataset concluído no encerramento.")
        except Exception as e:
            logger.warning(f"Aviso no flush síncrono de encerramento: {e}")

    @classmethod
    async def _sync_from_github(cls) -> None:
        """Restaura backup da nuvem via GitHub API para evitar perda em reinícios."""
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
                        decoded = base64.b64decode(content).decode("utf-8")
                        remote_data = json.loads(decoded)
                        if isinstance(remote_data, dict):
                            for gid, cfg in remote_data.items():
                                gid_str = str(gid)
                                cls._guilds_data[gid_str] = cls._merge_defaults(gid_str, cfg)
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
            snapshot = copy.deepcopy(cls._guilds_data)
            serialized = json.dumps(snapshot, indent=2, ensure_ascii=False)
            b64_content = base64.b64encode(serialized.encode("utf-8")).decode("ascii")

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
