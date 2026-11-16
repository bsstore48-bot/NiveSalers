"""
NiveSalers - Emoji Manager
Gerenciamento inteligente de Application Emojis via Discord API v10.
Garante o uso e renderização visual imediata de emojis personalizados em qualquer servidor.
"""
import os
import json
import base64
import re
from typing import Dict, Any, Optional, Tuple
import aiohttp
import asyncio

import config
from utils.logger import logger

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_PATH = os.path.join(_BASE_DIR, "assets", "emojis")
CACHE_FILE = os.path.join(_BASE_DIR, "database", "emojis_cache.json")

CUSTOM_EMOJI_RE = re.compile(r"^<(a?):([a-zA-Z0-9_]{1,32}):(\d{15,25})>$")
CUSTOM_EMOJI_INLINE_RE = re.compile(r"<(a?):([a-zA-Z0-9_]{1,32}):(\d{15,25})>")
SHORTCODE_RE = re.compile(r"^:?([a-zA-Z0-9_]{2,32}):?$")
SHORTCODE_INLINE_RE = re.compile(r"(?<!<)(?<!<a):([a-zA-Z0-9_]{2,32}):(?!\d+>)")
RAW_ID_RE = re.compile(r"^(\d{15,25})$")


class EmojiManager:
    _cache: Dict[str, str] = {}
    _synced: bool = False
    _bot_token: str = ""
    _application_id: str = ""
    _remote_by_id: Dict[str, str] = {}
    _remote_by_name: Dict[str, str] = {}
    _cloned_source_map: Dict[str, str] = {}

    @classmethod
    def load_cache(cls) -> None:
        """Carrega cache local de emojis (sem assumir IDs legados como pertencentes ao bot atual)."""
        for k, v in config.PRIORITY_EMOJIS.items():
            if k not in cls._cache:
                cls._cache[k] = v["tag"]

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
    def get_usable_tag(cls, raw_emoji: Optional[str]) -> str:
        """Retorna a tag clonada se o emoji original tiver sido clonado para Application Emojis."""
        raw = (raw_emoji or "").strip()
        if not raw:
            return ""
        m = CUSTOM_EMOJI_RE.match(raw)
        if m:
            eid = m.group(3)
            if eid in cls._cloned_source_map:
                return cls._cloned_source_map[eid]
            if eid in cls._remote_by_id:
                return cls._remote_by_id[eid]
        return raw

    @classmethod
    def is_app_or_guild_emoji(cls, emoji_id: str, guild=None) -> bool:
        """Verifica se o ID já pertence aos Application Emojis do bot ou ao servidor atual."""
        if emoji_id in cls._remote_by_id:
            return True
        if guild is not None:
            for e in getattr(guild, "emojis", []):
                if str(e.id) == str(emoji_id):
                    return True
        return False

    @classmethod
    def needs_remote_resolve(cls, raw_emoji: Optional[str], guild=None) -> bool:
        """Indica se o input provavelmente precisará de download/upload assíncrono."""
        raw = (raw_emoji or "").strip()
        if not raw:
            return False
        m = CUSTOM_EMOJI_RE.match(raw)
        if m:
            eid = m.group(3)
            if eid in cls._cloned_source_map or cls.is_app_or_guild_emoji(eid, guild=guild):
                return False
            return True
        if RAW_ID_RE.match(raw):
            return raw not in cls._cloned_source_map and not cls.is_app_or_guild_emoji(raw, guild=guild)
        return False

    @classmethod
    async def _download_emoji_image(cls, session: aiohttp.ClientSession, emoji_id: str, prefer_animated: bool = False) -> Tuple[Optional[bytes], bool]:
        """Baixa a imagem do emoji do CDN do Discord (.gif ou .png)."""
        exts = ["gif", "png"] if prefer_animated else ["png", "gif"]
        for ext in exts:
            url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}?size=128&quality=lossless"
            try:
                async with session.get(url, headers={"User-Agent": "NiveSalers-Bot"}) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        if data:
                            return data, (ext == "gif")
            except Exception:
                pass
        return None, False

    @classmethod
    async def resolve_or_clone_emoji(
        cls,
        raw_emoji: Optional[str],
        *,
        guild=None,
        bot=None,
        bot_token: str = "",
        application_id: str = ""
    ) -> str:
        """
        Resolve emojis Unicode, shortcodes (:nome:), IDs ou tags <:nome:id> / <a:nome:id>.
        Se for um emoji personalizado externo (de outro servidor/bot), faz o download no CDN
        e registra automaticamente como Application Emoji do bot para renderizar visualmente na hora.
        """
        raw = (raw_emoji or "").strip()
        if not raw:
            return ""

        if not cls._cache:
            cls.load_cache()

        token = (bot_token or cls._bot_token or config.DISCORD_TOKEN).strip()
        app_id = str(
            application_id
            or cls._application_id
            or (getattr(bot, "application_id", None) if bot else None)
            or (getattr(getattr(bot, "user", None), "id", None) if bot else None)
            or config.APPLICATION_ID
        ).strip()

        # 1. Tag completa <:nome:id> ou <a:nome:id>
        m = CUSTOM_EMOJI_RE.match(raw)
        if m:
            is_anim = m.group(1) == "a"
            ename = m.group(2)
            eid = m.group(3)

            if eid in cls._remote_by_id:
                return cls._remote_by_id[eid]
            if eid in cls._cloned_source_map:
                return cls._cloned_source_map[eid]
            if guild is not None:
                for e in getattr(guild, "emojis", []):
                    if str(e.id) == eid:
                        return f"<a:{e.name}:{e.id}>" if e.animated else f"<:{e.name}:{e.id}>"
            if bot is not None:
                found = bot.get_emoji(int(eid))
                if found is not None:
                    return str(found)
            priority_ids = {str(v.get("id")) for v in config.PRIORITY_EMOJIS.values() if v.get("id")}
            if eid in priority_ids and ename.lower() in cls._remote_by_name:
                mapped = cls._remote_by_name[ename.lower()]
                cls._cloned_source_map[eid] = mapped
                return mapped

            cloned = await cls._clone_to_application_emoji(
                emoji_id=eid,
                emoji_name=ename,
                prefer_animated=is_anim,
                bot_token=token,
                application_id=app_id
            )
            return cloned or raw

        # 2. Apenas ID numérico de emoji (15..25 dígitos)
        if RAW_ID_RE.match(raw):
            eid = raw
            if eid in cls._remote_by_id:
                return cls._remote_by_id[eid]
            if eid in cls._cloned_source_map:
                return cls._cloned_source_map[eid]
            if guild is not None:
                for e in getattr(guild, "emojis", []):
                    if str(e.id) == eid:
                        return f"<a:{e.name}:{e.id}>" if e.animated else f"<:{e.name}:{e.id}>"
            cloned = await cls._clone_to_application_emoji(
                emoji_id=eid,
                emoji_name=f"cat_{eid[-8:]}",
                prefer_animated=False,
                bot_token=token,
                application_id=app_id
            )
            return cloned or raw

        # 3. Shortcode :nome: ou nome ASCII
        sm = SHORTCODE_RE.match(raw)
        if sm:
            sname = sm.group(1).lower()
            if guild is not None:
                for e in getattr(guild, "emojis", []):
                    if e.name.lower() == sname:
                        return f"<a:{e.name}:{e.id}>" if e.animated else f"<:{e.name}:{e.id}>"
            if sname in cls._remote_by_name:
                return cls._remote_by_name[sname]
            if sname in cls._cache:
                return cls._cache[sname]
            return raw

        # 4. Unicode emoji (ex: 🎫, 🔥, ❤️)
        return raw

    @classmethod
    async def _clone_to_application_emoji(
        cls,
        *,
        emoji_id: str,
        emoji_name: str,
        prefer_animated: bool,
        bot_token: str,
        application_id: str
    ) -> Optional[str]:
        """Baixa emoji do CDN do Discord e registra como Application Emoji do bot."""
        if not bot_token or not application_id or not application_id.isdigit():
            logger.warning("Não foi possível clonar emoji externo: token ou application_id ausente.")
            return None

        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", emoji_name)[:32]
        if len(clean_name) < 2:
            clean_name = f"em_{clean_name or emoji_id[-6:]}"[:32]

        if clean_name.lower() in cls._remote_by_name:
            clean_name = f"{clean_name[:22]}_{emoji_id[-8:]}"[:32]

        api_url = f"https://discord.com/api/v10/applications/{application_id}/emojis"
        headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json"
        }

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                img_bytes, is_gif = await cls._download_emoji_image(session, emoji_id, prefer_animated=prefer_animated)
                if not img_bytes:
                    logger.warning(f"Não foi possível baixar imagem do emoji {emoji_id} no CDN.")
                    return None

                encoded_img = base64.b64encode(img_bytes).decode("utf-8")
                mime = "image/gif" if is_gif else "image/png"
                payload = {
                    "name": clean_name,
                    "image": f"data:{mime};base64,{encoded_img}"
                }

                async with session.post(api_url, headers=headers, json=payload) as up_res:
                    if up_res.status in (200, 201):
                        res_json = await up_res.json()
                        new_id = str(res_json.get("id"))
                        final_name = res_json.get("name") or clean_name
                        animated = bool(res_json.get("animated", is_gif))
                        tag = f"<a:{final_name}:{new_id}>" if animated else f"<:{final_name}:{new_id}>"
                        cls._remote_by_id[new_id] = tag
                        cls._remote_by_name[final_name.lower()] = tag
                        cls._cloned_source_map[str(emoji_id)] = tag
                        logger.info(f"✨ Emoji externo '{emoji_name}' ({emoji_id}) clonado para Application Emoji: {tag}")
                        return tag

                    # Se colidir nome por falta de cache atualizado, tenta com sufixo único
                    if up_res.status == 400:
                        fallback_name = f"c_{emoji_id[-10:]}_{clean_name}"[:32]
                        payload["name"] = fallback_name
                        async with session.post(api_url, headers=headers, json=payload) as retry_res:
                            if retry_res.status in (200, 201):
                                res_json = await retry_res.json()
                                new_id = str(res_json.get("id"))
                                final_name = res_json.get("name") or fallback_name
                                animated = bool(res_json.get("animated", is_gif))
                                tag = f"<a:{final_name}:{new_id}>" if animated else f"<:{final_name}:{new_id}>"
                                cls._remote_by_id[new_id] = tag
                                cls._remote_by_name[final_name.lower()] = tag
                                cls._cloned_source_map[str(emoji_id)] = tag
                                logger.info(f"✨ Emoji externo '{emoji_name}' clonado com fallback: {tag}")
                                return tag

                    err_txt = await up_res.text()
                    logger.warning(f"Erro ao clonar emoji '{emoji_name}' ({up_res.status}): {err_txt[:200]}")
        except Exception as e:
            logger.error(f"Falha ao clonar emoji externo '{emoji_id}': {e}")

        return None

    @classmethod
    def _lookup_shortcode_tag(cls, name: str, *, guild=None, bot=None) -> Optional[str]:
        """Procura um emoji pelo nome no servidor atual, Application Emojis do bot ou demais servidores do bot."""
        sname = (name or "").strip().lower()
        if not sname:
            return None
        if guild is not None:
            for e in getattr(guild, "emojis", []):
                if e.name.lower() == sname:
                    return f"<a:{e.name}:{e.id}>" if e.animated else f"<:{e.name}:{e.id}>"
        if sname in cls._remote_by_name:
            return cls._remote_by_name[sname]
        if bot is not None:
            for e in getattr(bot, "emojis", []):
                if e.name.lower() == sname:
                    return f"<a:{e.name}:{e.id}>" if e.animated else f"<:{e.name}:{e.id}>"
        if cls._synced and sname in cls._cache:
            return cls._cache[sname]
        return None

    @classmethod
    def replace_known_text_emojis(cls, text: Optional[str], *, guild=None, bot=None) -> str:
        """Substitui de forma síncrona emojis clonados/conhecidos e :shortcodes: em textos livres."""
        if not text:
            return text or ""

        def _repl_custom(match: re.Match) -> str:
            eid = match.group(3)
            if eid in cls._cloned_source_map:
                return cls._cloned_source_map[eid]
            if eid in cls._remote_by_id:
                return cls._remote_by_id[eid]
            return match.group(0)

        out = CUSTOM_EMOJI_INLINE_RE.sub(_repl_custom, text)

        def _repl_short(match: re.Match) -> str:
            found = cls._lookup_shortcode_tag(match.group(1), guild=guild, bot=bot)
            return found if found else match.group(0)

        out = SHORTCODE_INLINE_RE.sub(_repl_short, out)
        return out

    @classmethod
    def text_needs_remote_resolve(cls, text: Optional[str], guild=None) -> bool:
        """Indica se um texto livre contém algum emoji custom externo que precise de clonagem."""
        if not text:
            return False
        for m in CUSTOM_EMOJI_INLINE_RE.finditer(text):
            eid = m.group(3)
            if eid not in cls._cloned_source_map and not cls.is_app_or_guild_emoji(eid, guild=guild):
                return True
        return False

    @classmethod
    async def resolve_text_emojis(
        cls,
        text: Optional[str],
        *,
        guild=None,
        bot=None,
        bot_token: str = "",
        application_id: str = ""
    ) -> str:
        """
        Resolve todos os emojis personalizados (<:nome:id>, <a:nome:id> e :nome:) dentro de um texto
        (ex: Título ou Descrição do painel), clonando emojis externos para Application Emojis do bot.
        """
        if not text:
            return ""

        result = text
        # 1. Resolve tags <:nome:id> / <a:nome:id> preservando todas as ocorrências
        matches = list(CUSTOM_EMOJI_INLINE_RE.finditer(result))
        if matches:
            replacements: Dict[str, str] = {}
            for m in matches:
                full_tag = m.group(0)
                if full_tag in replacements:
                    continue
                resolved = await cls.resolve_or_clone_emoji(
                    full_tag,
                    guild=guild,
                    bot=bot,
                    bot_token=bot_token,
                    application_id=application_id
                )
                replacements[full_tag] = resolved or full_tag
            for src_tag, dst_tag in replacements.items():
                if dst_tag != src_tag:
                    result = result.replace(src_tag, dst_tag)

        # 2. Resolve :shortcodes: soltos que o modal do Discord não converte automaticamente
        def _repl_short(match: re.Match) -> str:
            found = cls._lookup_shortcode_tag(match.group(1), guild=guild, bot=bot)
            return found if found else match.group(0)

        result = SHORTCODE_INLINE_RE.sub(_repl_short, result)
        return result

    @classmethod
    async def migrate_guild_appearance(cls, guild_id: str, *, guild=None, bot=None) -> bool:
        """Migra emojis externos presentes em título e descrição do painel da guilda."""
        from database.cloud_storage import CloudStorage

        cfg = CloudStorage.get_guild_config(str(guild_id))
        painel_cfg = cfg.get("painel", {})
        changed = False

        for field in ("titulo", "descricao"):
            raw = painel_cfg.get(field)
            if isinstance(raw, str) and raw.strip():
                resolved = await cls.resolve_text_emojis(raw, guild=guild, bot=bot)
                if resolved and resolved != raw:
                    painel_cfg[field] = resolved
                    changed = True

        if changed:
            await CloudStorage.save_guild_config(str(guild_id), cfg)
            logger.info(f"🎨 Emojis de aparência migrados para Application Emojis na guilda {guild_id}.")
        return changed

    @classmethod
    async def migrate_guild_categories(cls, guild_id: str, *, guild=None, bot=None) -> bool:
        """Garante que todas as categorias de uma guilda tenham emojis renderizáveis pelo bot."""
        from database.cloud_storage import CloudStorage

        cfg = CloudStorage.get_guild_config(str(guild_id))
        categorias = cfg.get("categorias_ticket", [])
        if not categorias:
            return False

        changed = False
        for cat in categorias:
            raw = (cat.get("emoji") or "").strip()
            if not raw:
                continue
            if cls.needs_remote_resolve(raw, guild=guild):
                resolved = await cls.resolve_or_clone_emoji(raw, guild=guild, bot=bot)
                if resolved and resolved != raw:
                    cat["emoji"] = resolved
                    changed = True

        if changed:
            await CloudStorage.save_guild_config(str(guild_id), cfg)
            logger.info(f"🎨 Emojis de categorias migrados para Application Emojis na guilda {guild_id}.")
        return changed

    @classmethod
    async def sync_application_emojis(cls, bot_token: str, application_id: str, bot=None) -> Dict[str, Any]:
        """
        Sincroniza os emojis da pasta assets/emojis com os Application Emojis da aplicação Discord.
        Isso permite que o bot use emojis personalizados em qualquer servidor sem precisar de Nitro ou servidor exclusivo.
        """
        cls._bot_token = (bot_token or "").strip()
        cls._application_id = str(application_id or "").strip()

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
                existing_remote = []
                async with session.get(api_url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        existing_remote = data.get("items", []) if isinstance(data, dict) else data
                        logger.info(f"Encontrados {len(existing_remote)} Application Emojis já cadastrados no Discord.")
                    else:
                        err_text = await resp.text()
                        logger.warning(f"Aviso ao consultar Application Emojis (status {resp.status}): {err_text}")

                cls._remote_by_id.clear()
                cls._remote_by_name.clear()
                remote_map = {}
                for e in existing_remote:
                    if isinstance(e, dict) and "name" in e and "id" in e:
                        ename = e["name"]
                        eid = str(e["id"])
                        is_anim = bool(e.get("animated", False))
                        tag = f"<a:{ename}:{eid}>" if is_anim else f"<:{ename}:{eid}>"
                        remote_map[ename] = e
                        cls._remote_by_id[eid] = tag
                        cls._remote_by_name[ename.lower()] = tag

                files_to_sync = ["bot.png", "information.png", "cloud.png", "reload.png"]
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

                    if name in remote_map:
                        e_id = str(remote_map[name].get("id"))
                        tag = f"<a:{name}:{e_id}>" if is_animated else f"<:{name}:{e_id}>"
                        cls._cache[name] = tag
                        cls._remote_by_id[e_id] = tag
                        cls._remote_by_name[name.lower()] = tag
                        stats["existing"] += 1
                        continue

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
                                new_id = str(res_json.get("id"))
                                tag = f"<a:{name}:{new_id}>" if is_animated else f"<:{name}:{new_id}>"
                                cls._cache[name] = tag
                                cls._remote_by_id[new_id] = tag
                                cls._remote_by_name[name.lower()] = tag
                                stats["uploaded"] += 1
                                logger.info(f"✨ Emoji '{name}' registrado na aplicação com sucesso: {tag}")
                            else:
                                stats["errors"] += 1
                                err_txt = await up_res.text()
                                logger.warning(f"Erro ao registrar emoji '{name}' ({up_res.status}): {err_txt}")

                        await asyncio.sleep(0.4)
                    except Exception as ex:
                        stats["errors"] += 1
                        logger.error(f"Falha ao processar emoji '{filename}': {ex}")

            os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cls._cache, f, indent=4, ensure_ascii=False)

            cls._synced = True
            logger.info(f"Sincronização de Application Emojis concluída. Stats: {stats}")

            # Migra emojis externos de categorias salvas para Application Emojis
            from database.cloud_storage import CloudStorage
            for gid in list(CloudStorage._guilds_data.keys()):
                g_obj = bot.get_guild(int(gid)) if (bot and str(gid).isdigit()) else None
                await cls.migrate_guild_categories(gid, guild=g_obj, bot=bot)
                await cls.migrate_guild_appearance(gid, guild=g_obj, bot=bot)

            return {"status": "success", "stats": stats}

        except Exception as e:
            logger.error(f"Erro na rotina de sincronização de emojis: {e}")
            return {"status": "error", "error": str(e), "stats": stats}


# Inicializa cache padrão
EmojiManager.load_cache()
