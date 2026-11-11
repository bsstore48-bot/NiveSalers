"""
NiveSalers - Emoji Manager
Gerenciamento inteligente de Application Emojis via Discord API v10.
Garante o uso de emojis personalizados em qualquer servidor.
"""
import os
import json
import base64
import re
from typing import Dict, Any, Optional
import aiohttp
import asyncio

import config
from utils.logger import logger

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_PATH = os.path.join(_BASE_DIR, "assets", "emojis")
CACHE_FILE = os.path.join(_BASE_DIR, "database", "emojis_cache.json")

class EmojiManager:
    _cache: Dict[str, str] = {}
    _synced: bool = False

    @classmethod
    def load_cache(cls) -> None:
        """Carrega cache local de emojis."""
        # 1. Carrega prioritários do config como base padrão
        for k, v in config.PRIORITY_EMOJIS.items():
            cls._cache[k] = v["tag"]

        # 2. Carrega do cache salvo se existir
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        cls._cache.update(data)
                logger.info(f"🎨 {len(cls._cache)} emojis carregados do cache local.")
            except Exception as e:
                logger.warning(f"Não foi possível ler cache de emojis: {e}")

    @classmethod
    def get(cls, name: str, fallback: Optional[str] = None) -> str:
        """
        Retorna a tag formatada do emoji (ex: '<:bot:1557140838285582438>').
        Prioriza o emoji sincronizado da aplicação ou o fallback configurado.
        """
        if not cls._cache:
            cls.load_cache()

        if name in cls._cache:
            return cls._cache[name]

        if name in config.PRIORITY_EMOJIS:
            return config.PRIORITY_EMOJIS[name]["tag"]

        return fallback or (config.PRIORITY_EMOJIS.get(name, {}).get("fallback") or "🔹")

    @classmethod
    async def sync_application_emojis(cls, bot_token: str, application_id: str) -> Dict[str, Any]:
        """
        Sincroniza os emojis da pasta assets/emojis com os Application Emojis da aplicação Discord.
        Isso permite que o bot use emojis personalizados em qualquer servidor sem precisar de Nitro ou servidor exclusivo.
        """
        if not bot_token or not application_id:
            logger.warning("Token do bot ou Application ID não definidos para sincronização de emojis.")
            cls.load_cache()
            return {"status": "skipped", "reason": "Credenciais incompletas"}

        if not os.path.exists(ASSETS_PATH):
            logger.warning(f"Diretório de assets {ASSETS_PATH} não encontrado.")
            cls.load_cache()
            return {"status": "skipped", "reason": "Pasta de assets ausente"}

        cls.load_cache()
        headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json"
        }
        api_url = f"https://discord.com/api/v10/applications/{application_id}/emojis"
        stats = {"total": 0, "existing": 0, "uploaded": 0, "errors": 0}

        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # 1. Busca emojis já cadastrados na aplicação do Discord
                existing_remote = []
                async with session.get(api_url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        existing_remote = data.get("items", []) if isinstance(data, dict) else data
                        logger.info(f"Encontrados {len(existing_remote)} Application Emojis já cadastrados no Discord.")
                    else:
                        err_text = await resp.text()
                        logger.warning(f"Aviso ao consultar Application Emojis (status {resp.status}): {err_text}")

                remote_map = {e.get("name"): e for e in existing_remote if isinstance(e, dict) and "name" in e}

                # 2. Prioriza sincronização dos 4 emojis principais
                files_to_sync = ["bot.png", "information.png", "cloud.png", "reload.png"]
                
                # Adiciona outros assets se existirem
                for f in os.listdir(ASSETS_PATH):
                    if f.endswith((".png", ".gif")) and f not in files_to_sync:
                        files_to_sync.append(f)

                stats["total"] = len(files_to_sync)

                for filename in files_to_sync:
                    name, ext = os.path.splitext(filename)
                    is_animated = ext.lower() == ".gif"
                    image_path = os.path.join(ASSETS_PATH, filename)

                    if not os.path.exists(image_path):
                        continue

                    # Se já existe registrado na aplicação, guarda a tag correspondente
                    if name in remote_map:
                        e_id = remote_map[name].get("id")
                        tag = f"<a:{name}:{e_id}>" if is_animated else f"<:{name}:{e_id}>"
                        cls._cache[name] = tag
                        stats["existing"] += 1
                        continue

                    # Faz upload para a API do Discord
                    try:
                        with open(image_path, "rb") as img_file:
                            encoded_img = base64.b64encode(img_file.read()).decode("utf-8")

                        mime = "image/gif" if is_animated else "image/png"
                        payload = {
                            "name": name,
                            "image": f"data:{mime};base64,{encoded_img}"
                        }

                        async with session.post(api_url, headers=headers, json=payload) as up_res:
                            if up_res.status in (200, 201):
                                res_json = await up_res.json()
                                new_id = res_json.get("id")
                                tag = f"<a:{name}:{new_id}>" if is_animated else f"<:{name}:{new_id}>"
                                cls._cache[name] = tag
                                stats["uploaded"] += 1
                                logger.info(f"✨ Emoji '{name}' registrado na aplicação com sucesso: {tag}")
                            else:
                                stats["errors"] += 1
                                err_txt = await up_res.text()
                                logger.warning(f"Erro ao registrar emoji '{name}' ({up_res.status}): {err_txt}")

                        # Pausa para evitar rate limit do Discord
                        await asyncio.sleep(0.4)
                    except Exception as ex:
                        stats["errors"] += 1
                        logger.error(f"Falha ao processar emoji '{filename}': {ex}")

            # Salva no arquivo de cache
            os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cls._cache, f, indent=4, ensure_ascii=False)

            cls._synced = True
            logger.info(f"Sincronização de Application Emojis concluída. Stats: {stats}")
            return {"status": "success", "stats": stats}

        except Exception as e:
            logger.error(f"Erro na rotina de sincronização de emojis: {e}")
            return {"status": "error", "error": str(e), "stats": stats}

# Inicializa cache padrão
EmojiManager.load_cache()
