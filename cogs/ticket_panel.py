"""
Cog responsável pelo comando /configurar painel e pelo fluxo interativo
utilizando Discord Components v2 (LayoutView, Container, ActionRow) e
modais com suporte nativo a componentes de upload de arquivo.
"""

import asyncio
import io
import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.emoji_manager import EmojiManager
from database.cloud_storage import CloudStorage

logger = logging.getLogger("NiveSalers.TicketPanel")

# Detecção de suporte a Components V2 (discord.py git / 2.6+)
HAS_COMPONENTS_V2 = hasattr(discord.ui, "LayoutView") and hasattr(discord.ui, "Container")

if hasattr(discord.ui, "FileUpload") and hasattr(discord.ui, "Label"):
    FileUploadClass = discord.ui.FileUpload
    LabelClass = discord.ui.Label
else:
    class FileUploadClass(discord.ui.Item):
        """Componente Type 19: File Upload para Modals."""
        def __init__(self, *, custom_id: str, min_values: int = 1, max_values: int = 1, required: bool = True):
            super().__init__()
            self.custom_id = custom_id
            self.min_values = min_values
            self.max_values = max_values
            self.required = required
            self.values: List[Any] = []

        def to_component_dict(self) -> Dict[str, Any]:
            return {
                "type": 19,
                "custom_id": self.custom_id,
                "min_values": self.min_values,
                "max_values": self.max_values,
                "required": self.required,
                "file_types": ["image"]
            }

    class LabelClass(discord.ui.Item):
        """Componente Type 18: Label envoltório obrigatório para File Upload em Modals."""
        def __init__(self, *, text: str, component: discord.ui.Item, description: Optional[str] = None):
            super().__init__()
            self.text = text
            self.description = description
            self.component = component

        @property
        def width(self) -> int:
            return 5

        def _has_children(self) -> bool:
            return True

        def walk_children(self):
            yield self.component

        def to_component_dict(self) -> Dict[str, Any]:
            payload: Dict[str, Any] = {
                "type": 18,
                "label": self.text,
                "component": self.component.to_component_dict()
            }
            if self.description:
                payload["description"] = self.description
            return payload

MAIN_PANEL_BANNER_URL = "https://raw.githubusercontent.com/bsstore48-bot/NiveSalers/main/assets/banners/painel_principal_v2.png"

# 10 cores predefinidas para a embed/container do painel
CORES_DISPONIVEIS = [
    {"label": "Branco (Padrão)", "value": "FFFFFF", "hex": "#FFFFFF", "int": 0xFFFFFF, "desc": "Estilo limpo e minimalista"},
    {"label": "Preto Escuro", "value": "2B2D31", "hex": "#2B2D31", "int": 0x2B2D31, "desc": "Tema escuro Discord"},
    {"label": "Azul", "value": "3498DB", "hex": "#3498DB", "int": 0x3498DB, "desc": "Azul vibrante profissional"},
    {"label": "Verde", "value": "2ECC71", "hex": "#2ECC71", "int": 0x2ECC71, "desc": "Verde esmeralda"},
    {"label": "Vermelho", "value": "E74C3C", "hex": "#E74C3C", "int": 0xE74C3C, "desc": "Vermelho chamativo"},
    {"label": "Roxo", "value": "9B59B6", "hex": "#9B59B6", "int": 0x9B59B6, "desc": "Roxo elegante"},
    {"label": "Amarelo", "value": "F1C40F", "hex": "#F1C40F", "int": 0xF1C40F, "desc": "Amarelo dourado"},
    {"label": "Laranja", "value": "E67E22", "hex": "#E67E22", "int": 0xE67E22, "desc": "Laranja pôr do sol"},
    {"label": "Rosa", "value": "E91E63", "hex": "#E91E63", "int": 0xE91E63, "desc": "Rosa moderno"},
    {"label": "Ciano", "value": "1ABC9C", "hex": "#1ABC9C", "int": 0x1ABC9C, "desc": "Ciano turquesa"}
]

DIAS_SEMANA = [
    {"key": "segunda", "label": "Segunda-feira"},
    {"key": "terca", "label": "Terça-feira"},
    {"key": "quarta", "label": "Quarta-feira"},
    {"key": "quinta", "label": "Quinta-feira"},
    {"key": "sexta", "label": "Sexta-feira"},
    {"key": "sabado", "label": "Sábado"},
    {"key": "domingo", "label": "Domingo"},
]


def _normalize_hhmm(raw: str) -> Optional[str]:
    """Normaliza entrada de horário para HH:MM (00:00 a 23:59). Retorna None se inválido."""
    s = (raw or "").strip().lower().replace("h", ":")
    if ":" not in s:
        if s.isdigit() and len(s) in (1, 2):
            s = f"{s}:00"
        elif s.isdigit() and len(s) == 4:
            s = f"{s[:2]}:{s[2:]}"
        else:
            return None
    parts = s.split(":")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return None
    hour = int(parts[0])
    minute = int(parts[1])
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return None


def _get_dias_horario(cfg: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Retorna o dicionário normalizado dos 7 dias da semana na config da guilda."""
    ha = cfg.setdefault("horario_atendimento", {})
    dias = ha.setdefault("dias", {})
    for d in DIAS_SEMANA:
        k = d["key"]
        if k not in dias or not isinstance(dias[k], dict):
            dias[k] = {"ativo": False, "inicio": None, "fim": None}
    return dias

def _sys_emoji(emoji_key: str, default_key: str = "information") -> str:
    """Retorna sempre um emoji personalizado do sistema de Application Emojis (nunca Unicode)."""
    raw = EmojiManager.get(emoji_key)
    if raw and raw.startswith("<") and raw.endswith(">"):
        return raw
    fallback_raw = EmojiManager.get(default_key)
    if fallback_raw and fallback_raw.startswith("<") and fallback_raw.endswith(">"):
        return fallback_raw
    pinfo = config.PRIORITY_EMOJIS.get(emoji_key) or config.PRIORITY_EMOJIS.get(default_key) or {}
    return pinfo.get("tag", "")


def resolve_partial_emoji(emoji_key: str, default_unicode: Optional[str] = "⚙️"):
    """Converte tag de emoji em discord.PartialEmoji ou string Unicode de forma segura."""
    raw = EmojiManager.get(emoji_key, fallback=default_unicode)
    if raw and raw.startswith("<") and raw.endswith(">"):
        try:
            return discord.PartialEmoji.from_str(raw)
        except Exception:
            return default_unicode or None
    return raw or default_unicode or None


def _format_ticket_duration(
    created_at_ts: Optional[int],
    data_criacao: str = "",
    horario_criacao: str = "",
    now_brt: Optional[datetime] = None,
) -> str:
    """Calcula duração legível entre abertura e fechamento do ticket."""
    brt_tz = timezone(timedelta(hours=-3))
    end_dt = now_brt or datetime.now(brt_tz)
    start_dt: Optional[datetime] = None
    if isinstance(created_at_ts, (int, float)) and created_at_ts > 0:
        start_dt = datetime.fromtimestamp(created_at_ts, tz=brt_tz)
    elif data_criacao and horario_criacao:
        try:
            start_dt = datetime.strptime(f"{data_criacao} {horario_criacao}", "%d/%m/%Y %H:%M").replace(tzinfo=brt_tz)
        except Exception:
            start_dt = None
    if start_dt is None:
        return "Indisponível"
    total_secs = max(0, int((end_dt - start_dt).total_seconds()))
    if total_secs < 60:
        return f"{total_secs}s"
    mins, secs = divmod(total_secs, 60)
    hours, mins = divmod(mins, 60)
    days, hours = divmod(hours, 24)
    parts: List[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}min")
    if not days and not hours and secs:
        parts.append(f"{secs}s")
    return " ".join(parts) if parts else "0s"


async def _resolve_log_channel(guild, client, cfg: Dict[str, Any], log_key: str) -> Optional[Any]:
    """Resolve o canal configurado para um tipo específico de log (com fallback para canal_logs_id legado)."""
    logs_cfg = cfg.get("logs", {})
    raw_id = logs_cfg.get(log_key) or logs_cfg.get("canal_logs_id")
    if not raw_id or not str(raw_id).isdigit():
        return None
    ch_id = int(raw_id)
    ch = None
    if guild is not None:
        if hasattr(guild, "get_channel_or_thread"):
            ch = guild.get_channel_or_thread(ch_id)
        if ch is None:
            ch = guild.get_channel(ch_id)
    if ch is None and client is not None:
        ch = client.get_channel(ch_id)
    if ch is None and client is not None:
        try:
            ch = await client.fetch_channel(ch_id)
        except Exception as e:
            logger.warning(f"Não foi possível buscar canal de log {ch_id} ({log_key}): {e}")
            return None
    return ch


async def _build_ticket_transcript(
    thread,
    ticket_data: Dict[str, Any],
    closed_by,
    guild,
    closed_at_brt: datetime,
    duracao_str: str,
) -> Tuple[Optional[bytes], str, int]:
    """Coleta as mensagens do tópico antes do encerramento e gera um transcript .txt em UTF-8."""
    tid = getattr(thread, "id", 0)
    filename = f"transcript-{tid}.txt"
    brt_tz = timezone(timedelta(hours=-3))
    lines: List[str] = []
    msg_count = 0

    if thread is not None and hasattr(thread, "history"):
        try:
            async for msg in thread.history(limit=500, oldest_first=True):
                msg_count += 1
                created_brt = msg.created_at.astimezone(brt_tz)
                ts_str = created_brt.strftime("%d/%m/%Y %H:%M:%S")
                author_tag = f"{msg.author} ({msg.author.id})"
                content = (msg.content or "").strip()
                extras: List[str] = []
                for att in getattr(msg, "attachments", []):
                    extras.append(f"[Anexo: {att.filename} - {att.url}]")
                if getattr(msg, "embeds", None):
                    for emb in msg.embeds:
                        emb_txt = " | ".join(p for p in [emb.title, emb.description] if p)
                        if emb_txt:
                            extras.append(f"[Embed: {emb_txt[:200]}]")
                if not content and not extras:
                    if getattr(msg, "components", None):
                        extras.append("[Painel / Componentes V2]")
                    else:
                        extras.append("[Mensagem sem conteúdo de texto]")
                body = " ".join(p for p in [content, *extras] if p)
                lines.append(f"[{ts_str}] {author_tag}: {body}")
        except Exception as e:
            logger.warning(f"Aviso ao gerar transcript do tópico {tid}: {e}")
            lines.append(f"[Aviso] Não foi possível ler todas as mensagens: {e}")

    owner_id = ticket_data.get("owner_id")
    assumed_by_id = ticket_data.get("assumed_by_id")
    cat_nome = ticket_data.get("category_name") or "Atendimento"
    thread_name = getattr(thread, "name", None) or ticket_data.get("thread_name") or f"ticket-{tid}"
    data_criacao = ticket_data.get("data_criacao") or "--/--/----"
    horario_criacao = ticket_data.get("horario_criacao") or "--:--"
    guild_name = getattr(guild, "name", "Servidor") if guild else "Servidor"

    header = [
        "=" * 60,
        f"TRANSCRIPT DE ATENDIMENTO - {guild_name}",
        "=" * 60,
        f"Tópico: {thread_name} (ID: {tid})",
        f"Categoria: {cat_nome}",
        f"Dono do ticket: {owner_id or 'Desconhecido'}",
        f"Atendente: {assumed_by_id or 'Não assumido'}",
        f"Fechado por: {closed_by} ({getattr(closed_by, 'id', '')})",
        f"Abertura: {data_criacao} às {horario_criacao} (BRT)",
        f"Fechamento: {closed_at_brt.strftime('%d/%m/%Y às %H:%M:%S')} (BRT)",
        f"Duração: {duracao_str}",
        f"Total de mensagens: {msg_count}",
    ]
    added_members = ticket_data.get("added_members") or []
    if added_members:
        header.append(f"Membros adicionados: {', '.join(str(m) for m in added_members)}")
    renamed_history = ticket_data.get("renamed_history") or []
    if renamed_history:
        ren_fmt = "; ".join(f"{r.get('de', '?')} -> {r.get('para', '?')}" for r in renamed_history if isinstance(r, dict))
        if ren_fmt:
            header.append(f"Renomeações: {ren_fmt}")
    if ticket_data.get("opener_left"):
        header.append(f"Saída do autor: Sim ({ticket_data.get('opener_left_at') or 'registrado'})")
    header.extend(["=" * 60, ""])

    full_text = "\n".join(header + (lines if lines else ["(Nenhuma mensagem registrada neste tópico.)"]))
    return full_text.encode("utf-8"), filename, msg_count


async def _send_ticket_log(
    *,
    guild,
    client,
    cfg: Dict[str, Any],
    log_key: str,
    title: str,
    title_emoji_key: str,
    lines: List[str],
    accent_color: int,
    jump_url: Optional[str] = None,
    transcript_bytes: Optional[bytes] = None,
    transcript_filename: Optional[str] = None,
) -> bool:
    """Envia log padronizado em Components V2 para o canal configurado em /configurações -> Canais."""
    log_ch = await _resolve_log_channel(guild, client, cfg, log_key)
    if log_ch is None:
        return False

    emoji_title = _sys_emoji(title_emoji_key, "bot")
    log_text = f"## {emoji_title} {title}\n\n" + "\n".join(lines)
    no_pings = discord.AllowedMentions.none()

    if HAS_COMPONENTS_V2:
        try:
            separator_spacing = getattr(discord, "SeparatorSpacing", None)
            spacing_arg = separator_spacing.small if separator_spacing else None
            def _make_sep():
                return (
                    discord.ui.Separator(visible=True)
                    if spacing_arg is None
                    else discord.ui.Separator(visible=True, spacing=spacing_arg)
                )

            container_items: List[Any] = [discord.ui.TextDisplay(log_text)]
            has_file_comp = bool(transcript_bytes and transcript_filename and hasattr(discord.ui, "File"))
            if has_file_comp:
                container_items.append(_make_sep())
                container_items.append(discord.ui.File(f"attachment://{transcript_filename}"))
            if jump_url:
                if not has_file_comp:
                    container_items.append(_make_sep())
                link_emoji = resolve_partial_emoji("link", None)
                btn_kwargs: Dict[str, Any] = {
                    "label": "Ir para o ticket",
                    "style": discord.ButtonStyle.link,
                    "url": jump_url,
                }
                if link_emoji is not None:
                    btn_kwargs["emoji"] = link_emoji
                container_items.append(discord.ui.ActionRow(discord.ui.Button(**btn_kwargs)))

            log_view = discord.ui.LayoutView(timeout=None)
            log_view.add_item(discord.ui.Container(*container_items, accent_colour=accent_color))

            send_kwargs: Dict[str, Any] = {"view": log_view, "allowed_mentions": no_pings}
            if has_file_comp and transcript_bytes and transcript_filename:
                send_kwargs["file"] = discord.File(io.BytesIO(transcript_bytes), filename=transcript_filename)

            await log_ch.send(**send_kwargs)
            return True
        except Exception as e:
            logger.warning(f"Aviso ao enviar log V2 ({log_key}): {e}. Tentando fallback seguro.")
            if transcript_bytes and transcript_filename:
                try:
                    fallback_v2_items: List[Any] = [discord.ui.TextDisplay(log_text)]
                    if jump_url:
                        fallback_v2_items.append(
                            discord.ui.ActionRow(
                                discord.ui.Button(label="Ir para o ticket", style=discord.ButtonStyle.link, url=jump_url)
                            )
                        )
                    fb_v2 = discord.ui.LayoutView(timeout=None)
                    fb_v2.add_item(discord.ui.Container(*fallback_v2_items, accent_colour=accent_color))
                    await log_ch.send(view=fb_v2, allowed_mentions=no_pings)
                    await log_ch.send(file=discord.File(io.BytesIO(transcript_bytes), filename=transcript_filename))
                    return True
                except Exception as e2:
                    logger.warning(f"Aviso no fallback V2 com arquivo ({log_key}): {e2}")

    try:
        emb = discord.Embed(description=log_text, color=accent_color)
        fb_kwargs: Dict[str, Any] = {"embed": emb, "allowed_mentions": no_pings}
        if jump_url:
            fb_view = discord.ui.View(timeout=None)
            fb_view.add_item(discord.ui.Button(label="Ir para o ticket", style=discord.ButtonStyle.link, url=jump_url))
            fb_kwargs["view"] = fb_view
        if transcript_bytes and transcript_filename:
            fb_kwargs["file"] = discord.File(io.BytesIO(transcript_bytes), filename=transcript_filename)
        await log_ch.send(**fb_kwargs)
        return True
    except Exception as e:
        logger.warning(f"Erro ao enviar log ({log_key}) para canal {getattr(log_ch, 'id', '?')}: {e}")
        return False


def resolve_category_emoji(raw_emoji: Optional[str], fallback_key: str = "folder", fallback_unicode: str = "📁", guild=None):
    """Converte emoji personalizado (<:nome:id> / <a:nome:id>) ou Unicode salvo na categoria para SelectOption."""
    raw = EmojiManager.get_usable_tag(raw_emoji)
    if raw:
        if raw.startswith("<") and raw.endswith(">"):
            try:
                parsed = discord.PartialEmoji.from_str(raw)
                if parsed.id is not None and EmojiManager.is_app_or_guild_emoji(str(parsed.id), guild=guild):
                    return parsed
            except Exception:
                pass
        elif " " not in raw and len(raw) <= 12 and not raw.isascii():
            return raw
    return resolve_partial_emoji(fallback_key, fallback_unicode)

def format_main_panel_text() -> str:
    """Retorna o texto do painel principal de configuração."""
    emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")
    emoji_cloud = EmojiManager.get("cloud", fallback="<:cloud:1561906158984233031>")
    emoji_reload = EmojiManager.get("reload", fallback="<:reload:1561908806584115210>")

    lines = [
        f"{emoji_info} Selecione uma opção para configurar no painel.",
        f"{emoji_cloud} Todas as configurações serão salvas imediatamente no sistema de atendimento.",
        f"{emoji_reload} Com atualização automática de painéis de atendimento existentes."
    ]
    return "\n".join(lines)

def _get_configured_appearance(painel_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Retorna apenas os campos de aparência realmente configurados pelo usuário."""
    raw_titulo = (painel_cfg.get("titulo") or "").strip()
    titulo_cfg = bool(painel_cfg.get("titulo_configurado"))
    titulo = raw_titulo if raw_titulo and (titulo_cfg or raw_titulo != "Painel de Atendimento") else None

    raw_desc = (painel_cfg.get("descricao") or "").strip()
    desc_cfg = bool(painel_cfg.get("descricao_configurada"))
    descricao = raw_desc if raw_desc and (desc_cfg or raw_desc != "Abra um ticket para falar com a nossa equipe.") else None

    banner_url = (painel_cfg.get("banner_url") or "").strip() or None
    thumbnail_url = (painel_cfg.get("thumbnail_url") or "").strip() or None

    cor_hex = (painel_cfg.get("cor_hex") or "").strip() or None
    cor_val = painel_cfg.get("cor")
    cor_cfg = bool(painel_cfg.get("cor_configurada")) or bool(cor_hex) or (cor_val is not None and cor_val != config.EMBED_COLOR_DEFAULT)
    cor = cor_val if cor_cfg and cor_val is not None else None

    return {
        "titulo": titulo,
        "descricao": descricao,
        "banner_url": banner_url,
        "thumbnail_url": thumbnail_url,
        "cor": cor,
        "cor_hex": cor_hex,
    }


def format_appearance_panel_text(guild_id: str) -> str:
    """Retorna o texto formatado do painel de aparência com os valores dinâmicos do servidor."""
    cfg = CloudStorage.get_guild_config(guild_id)
    painel_cfg = cfg.get("painel", {})
    app = _get_configured_appearance(painel_cfg)

    titulo = EmojiManager.replace_known_text_emojis(app["titulo"]) if app["titulo"] else "Não definido"
    descricao = EmojiManager.replace_known_text_emojis(app["descricao"]) if app["descricao"] else "Não definido"
    banner = app["banner_url"] or "Não definido"
    thumbnail = app["thumbnail_url"] or "Não definido"
    cor = app["cor_hex"] or (f"#{app['cor']:06X}" if app["cor"] is not None else "Não definido")

    emoji_bot = EmojiManager.get("bot", fallback="<:bot:1557140838285582438>")
    emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")
    emoji_reload = EmojiManager.get("reload", fallback="<:reload:1561908806584115210>")
    emoji_reaction = EmojiManager.get("reaction_add", fallback="<:reaction_add:1561908795226198026>")
    emoji_edit = EmojiManager.get("edit", fallback="<:edit:1561906222062506015>")
    emoji_embed = EmojiManager.get("embed", fallback="<:embed:1561906227305521172>")
    emoji_image = EmojiManager.get("image", fallback="<:image:1561907844142342196>")
    emoji_colors = EmojiManager.get("colors", fallback="<:colors:1561906164810125362>")

    lines = [
        f"## {emoji_bot} Painel de configuração da aparência do painel\n",
        f"> {emoji_info} Selecione uma opção para configurar, clicando nos botões abaixo.",
        f"> {emoji_reload} Todas elas irão ser atualizadas automaticamente em paineis existentes.",
        f"> {emoji_reaction} Para melhor interface do painel, você pode usar emojis do Discord.\n",
        f"{emoji_edit} Título: {titulo}",
        f"{emoji_embed} Descrição: {descricao}",
        f"{emoji_image} Banner: {banner}",
        f"{emoji_image} Thumbnail: {thumbnail}",
        f"{emoji_colors} Cor da embed: {cor}"
    ]
    return "\n".join(lines)


def format_settings_panel_text() -> str:
    """Retorna o texto do painel de configurações do painel."""
    emoji_bot = EmojiManager.get("bot", fallback="<:bot:1557140838285582438>")
    emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")
    emoji_settings = EmojiManager.get("settings", fallback="<:settings:1561908832173826048>")

    lines = [
        f"## {emoji_bot} Painel de configurações do sistema\n",
        f"> {emoji_info} Clique nos botões abaixo para configurar funcionalidades.",
        f"> {emoji_settings} Tudo isso que é possível configurar por aqui pode ser essencial para a melhor experiência do seu servidor."
    ]
    return "\n".join(lines)


def format_business_hours_panel_text(guild_id: str) -> str:
    """Retorna o texto do painel de horário de atendimento com o status de cada dia da semana."""
    emoji_bot = EmojiManager.get("bot", fallback="<:bot:1557140838285582438>")
    emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")
    emoji_online = EmojiManager.get("on", fallback="<:on:1561908741073281054>")
    emoji_off = EmojiManager.get("off", fallback="⚪")

    cfg = CloudStorage.get_guild_config(guild_id)
    dias = _get_dias_horario(cfg)

    lines = [
        f"## {emoji_bot} Horário de atendimento\n",
        f"> {emoji_info} Configure o horário em que os membros podem abrir tickets para serem atendidos.\n"
    ]

    for d in DIAS_SEMANA:
        info = dias.get(d["key"], {})
        ativo = bool(info.get("ativo")) and bool(info.get("inicio")) and bool(info.get("fim"))
        if ativo:
            lines.append(f"> {emoji_online} **{d['label']}:** `{info['inicio']}` às `{info['fim']}`")
        else:
            lines.append(f"> {emoji_off} **{d['label']}:** Não configurado")

    return "\n".join(lines)


def format_categories_panel_text(guild_id: str) -> str:
    """Retorna o texto do painel de categorias com as categorias cadastradas no servidor."""
    emoji_bot = EmojiManager.get("bot", fallback="<:bot:1557140838285582438>")
    emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")
    emoji_folder = EmojiManager.get("folder", fallback="<:folder:1561907786986561586>")

    cfg = CloudStorage.get_guild_config(guild_id)
    categorias = cfg.get("categorias_ticket", [])

    lines = [
        f"## {emoji_bot} Categorias\n",
        f"> {emoji_info} Use os botões abaixo para criar, editar e remover categorias do sistema de atendimento do seu servidor."
    ]

    if not categorias:
        lines.append(f"> {emoji_folder} Categorias existentes: Nenhuma categoria criada.")
    else:
        lines.append(f"> {emoji_folder} Categorias existentes:")
        for idx, cat in enumerate(categorias, 1):
            nome = cat.get("nome", "Sem nome")
            desc = cat.get("descricao", "")
            cat_emoji = EmojiManager.get_usable_tag(cat.get("emoji"))
            emoji_prefix = f"{cat_emoji} " if cat_emoji else ""
            canal_id = cat.get("canal_topicos_id")
            cargos_ids = cat.get("cargos_permitidos_ids", [])
            canal_fmt = f"<#{canal_id}>" if canal_id else "Não definido"
            cargos_fmt = ", ".join(f"<@&{rid}>" for rid in cargos_ids) if cargos_ids else "Nenhum"
            lines.append(f"\n**{idx}.** {emoji_prefix}**{nome}** — {desc}\nCanal: {canal_fmt} | Cargos: {cargos_fmt}")

    return "\n".join(lines)


def format_remove_category_panel_text(has_categories: bool = True) -> str:
    """Retorna o texto do painel de remoção de categoria."""
    emoji_bot = EmojiManager.get("bot", fallback="<:bot:1557140838285582438>")
    emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")

    text = (
        f"## {emoji_bot} Remover categoria\n\n"
        f"{emoji_info} Selecione a categoria que deseja remover, usando o select menu abaixo."
    )
    if not has_categories:
        text += "\n\n> Nenhuma categoria existente no momento."
    return text


def format_edit_category_panel_text(has_categories: bool = True) -> str:
    """Retorna o texto do painel de edição de categoria."""
    emoji_bot = EmojiManager.get("bot", fallback="<:bot:1557140838285582438>")
    emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")

    text = (
        f"## {emoji_bot} Editar categoria\n\n"
        f"{emoji_info} Selecione a categoria que deseja editar, usando o select menu abaixo."
    )
    if not has_categories:
        text += "\n\n> Nenhuma categoria existente no momento."
    return text


# =====================================================================
# MODALS INTERATIVOS COM COMPONENTE NATIVO DE UPLOAD (LABEL TIPO 18 + FILE UPLOAD TIPO 19)
# =====================================================================

class TituloModal(discord.ui.Modal, title="Configurar Título"):
    """Modal para digitar o título do painel."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id

        cfg = CloudStorage.get_guild_config(str(guild_id))
        valor_atual = _get_configured_appearance(cfg.get("painel", {})).get("titulo") or ""

        self.titulo_input = discord.ui.TextInput(
            label="Título do painel",
            placeholder="Digite o título do painel de atendimento...",
            default=valor_atual,
            min_length=1,
            max_length=256,
            required=True
        )
        self.add_item(self.titulo_input)

    async def on_submit(self, interaction: discord.Interaction):
        novo_titulo = self.titulo_input.value.strip()
        if EmojiManager.text_needs_remote_resolve(novo_titulo, guild=interaction.guild) and not interaction.response.is_done():
            await interaction.response.defer()
        novo_titulo = await EmojiManager.resolve_text_emojis(
            novo_titulo,
            guild=interaction.guild,
            bot=interaction.client
        )
        gid_int = self.guild_id or (interaction.guild_id or 0)
        gid_str = str(gid_int or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        cfg["painel"]["titulo"] = novo_titulo
        cfg["painel"]["titulo_configurado"] = True
        await CloudStorage.save_guild_config(gid_str, cfg)
        _schedule_panel_refresh(interaction.client, gid_int, interaction.guild)

        logger.info(f"Título atualizado por {interaction.user} no servidor {gid_str}: '{novo_titulo}'")
        await render_appearance_panel(interaction, gid_int, self.user_id, is_edit=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Erro no modal de título: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Ocorreu um erro ao salvar o título: {error}", ephemeral=True)


class DescricaoModal(discord.ui.Modal, title="Configurar Descrição"):
    """Modal para digitar a descrição do painel."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id

        cfg = CloudStorage.get_guild_config(str(guild_id))
        valor_atual = _get_configured_appearance(cfg.get("painel", {})).get("descricao") or ""

        self.descricao_input = discord.ui.TextInput(
            label="Descrição do painel",
            style=discord.TextStyle.paragraph,
            placeholder="Digite a descrição detalhada do painel...",
            default=valor_atual,
            min_length=1,
            max_length=4000,
            required=True
        )
        self.add_item(self.descricao_input)

    async def on_submit(self, interaction: discord.Interaction):
        nova_descricao = self.descricao_input.value.strip()
        if EmojiManager.text_needs_remote_resolve(nova_descricao, guild=interaction.guild) and not interaction.response.is_done():
            await interaction.response.defer()
        nova_descricao = await EmojiManager.resolve_text_emojis(
            nova_descricao,
            guild=interaction.guild,
            bot=interaction.client
        )
        gid_int = self.guild_id or (interaction.guild_id or 0)
        gid_str = str(gid_int or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        cfg["painel"]["descricao"] = nova_descricao
        cfg["painel"]["descricao_configurada"] = True
        await CloudStorage.save_guild_config(gid_str, cfg)
        _schedule_panel_refresh(interaction.client, gid_int, interaction.guild)

        logger.info(f"Descrição atualizada por {interaction.user} no servidor {gid_str}")
        await render_appearance_panel(interaction, gid_int, self.user_id, is_edit=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Erro no modal de descrição: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Ocorreu um erro ao salvar a descrição: {error}", ephemeral=True)


class BannerModal(discord.ui.Modal, title="Configurar Banner"):
    """Modal com componente nativo de upload para a imagem do banner."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id

        self.file_upload = FileUploadClass(
            custom_id="banner_file_upload",
            min_values=1,
            max_values=1,
            required=True
        )
        self.label_wrapper = LabelClass(
            text="Upload do Banner",
            description="Selecione o arquivo da imagem do banner para carregar",
            component=self.file_upload
        )
        self.add_item(self.label_wrapper)

    def to_components(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": 18,
                "label": "Upload do Banner",
                "description": "Selecione o arquivo da imagem do banner para carregar",
                "component": {
                    "type": 19,
                    "custom_id": "banner_file_upload",
                    "min_values": 1,
                    "max_values": 1,
                    "required": True,
                    "file_types": ["image"]
                }
            }
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "custom_id": self.custom_id,
            "components": self.to_components()
        }

    async def on_submit(self, interaction: discord.Interaction):
        novo_banner = None

        # 1. Recupera via resolved attachments do payload de interação da API do Discord
        resolved_attachments = interaction.data.get("resolved", {}).get("attachments", {})
        if resolved_attachments:
            first_att = next(iter(resolved_attachments.values()))
            novo_banner = first_att.get("url")

        # 2. Varredura recursiva nos components do interaction.data
        if not novo_banner:
            for comp_wrapper in interaction.data.get("components", []):
                inner = comp_wrapper.get("component") if comp_wrapper.get("type") == 18 else comp_wrapper
                if inner and inner.get("type") == 19:
                    values = inner.get("values", [])
                    if values and resolved_attachments:
                        att_id = str(values[0])
                        if att_id in resolved_attachments:
                            novo_banner = resolved_attachments[att_id].get("url")

        # 3. Recupera via atributo values da classe se populado pelo discord.py
        if not novo_banner and hasattr(self.file_upload, "values") and self.file_upload.values:
            att = self.file_upload.values[0]
            novo_banner = getattr(att, "url", None) or getattr(att, "proxy_url", None) or str(att)

        gid_int = self.guild_id or (interaction.guild_id or 0)
        gid_str = str(gid_int or "direct")
        if novo_banner:
            cfg = CloudStorage.get_guild_config(gid_str)
            cfg["painel"]["banner_url"] = novo_banner
            await CloudStorage.save_guild_config(gid_str, cfg)
            _schedule_panel_refresh(interaction.client, gid_int, interaction.guild)
            logger.info(f"Banner atualizado via componente de upload por {interaction.user}: {novo_banner}")

        await render_appearance_panel(interaction, gid_int, self.user_id, is_edit=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Erro no modal de upload do banner: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Ocorreu um erro no upload do banner: {error}", ephemeral=True)


class ThumbnailModal(discord.ui.Modal, title="Configurar Thumbnail"):
    """Modal com componente nativo de upload para a imagem da thumbnail."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id

        self.file_upload = FileUploadClass(
            custom_id="thumbnail_file_upload",
            min_values=1,
            max_values=1,
            required=True
        )
        self.label_wrapper = LabelClass(
            text="Upload da Thumbnail",
            description="Selecione o arquivo da imagem da thumbnail para carregar",
            component=self.file_upload
        )
        self.add_item(self.label_wrapper)

    def to_components(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": 18,
                "label": "Upload da Thumbnail",
                "description": "Selecione o arquivo da imagem da thumbnail para carregar",
                "component": {
                    "type": 19,
                    "custom_id": "thumbnail_file_upload",
                    "min_values": 1,
                    "max_values": 1,
                    "required": True,
                    "file_types": ["image"]
                }
            }
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "custom_id": self.custom_id,
            "components": self.to_components()
        }

    async def on_submit(self, interaction: discord.Interaction):
        nova_thumb = None

        # 1. Recupera via resolved attachments do payload de interação da API do Discord
        resolved_attachments = interaction.data.get("resolved", {}).get("attachments", {})
        if resolved_attachments:
            first_att = next(iter(resolved_attachments.values()))
            nova_thumb = first_att.get("url")

        # 2. Varredura recursiva nos components do interaction.data
        if not nova_thumb:
            for comp_wrapper in interaction.data.get("components", []):
                inner = comp_wrapper.get("component") if comp_wrapper.get("type") == 18 else comp_wrapper
                if inner and inner.get("type") == 19:
                    values = inner.get("values", [])
                    if values and resolved_attachments:
                        att_id = str(values[0])
                        if att_id in resolved_attachments:
                            nova_thumb = resolved_attachments[att_id].get("url")

        # 3. Recupera via atributo values da classe se populado pelo discord.py
        if not nova_thumb and hasattr(self.file_upload, "values") and self.file_upload.values:
            att = self.file_upload.values[0]
            nova_thumb = getattr(att, "url", None) or getattr(att, "proxy_url", None) or str(att)

        gid_int = self.guild_id or (interaction.guild_id or 0)
        gid_str = str(gid_int or "direct")
        if nova_thumb:
            cfg = CloudStorage.get_guild_config(gid_str)
            cfg["painel"]["thumbnail_url"] = nova_thumb
            await CloudStorage.save_guild_config(gid_str, cfg)
            _schedule_panel_refresh(interaction.client, gid_int, interaction.guild)
            logger.info(f"Thumbnail atualizada via componente de upload por {interaction.user}: {nova_thumb}")

        await render_appearance_panel(interaction, gid_int, self.user_id, is_edit=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Erro no modal de upload da thumbnail: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Ocorreu um erro no upload da thumbnail: {error}", ephemeral=True)


def _get_allowed_category_role_ids(guild_id: str, guild: Optional[discord.Guild] = None) -> List[str]:
    """Retorna os IDs de Cargos Permitidos configurados em /configurações -> Cargos (sem Cargo Membros)."""
    cfg = CloudStorage.get_guild_config(guild_id)
    cargos_cfg = cfg.get("cargos", {})
    cargo_membros_id = str(cargos_cfg.get("cargo_membros_id") or "").strip()
    raw_ids = cargos_cfg.get("cargos_permitidos_ids") or []
    result: List[str] = []
    seen = set()
    for rid in raw_ids:
        rid_str = str(rid).strip()
        if not rid_str.isdigit() or rid_str == cargo_membros_id or rid_str in seen:
            continue
        if guild is not None and guild.get_role(int(rid_str)) is None:
            continue
        seen.add(rid_str)
        result.append(rid_str)
    return result


class CriarCategoriaModal(discord.ui.Modal, title="Criar Categoria"):
    """Modal com 5 abas (Label Type 18) para criar ou editar uma categoria de atendimento."""
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        edit_cat_id: Optional[str] = None,
        categoria_atual: Optional[Dict[str, Any]] = None,
        include_select_defaults: bool = True,
        guild: Optional[discord.Guild] = None
    ):
        modal_title = "Editar Categoria" if categoria_atual is not None else "Criar Categoria"
        super().__init__(title=modal_title)
        self.guild_id = guild_id
        self.user_id = user_id
        self.edit_cat_id = edit_cat_id
        self.categoria_atual = categoria_atual
        self.include_select_defaults = include_select_defaults
        self.guild = guild

    def to_components(self) -> List[Dict[str, Any]]:
        cat = self.categoria_atual or {}
        nome_atual = (cat.get("nome") or "").strip()[:50]
        desc_atual = (cat.get("descricao") or "").strip()[:50]
        emoji_atual = (cat.get("emoji") or "").strip()[:100]
        canal_atual = cat.get("canal_topicos_id")
        cargos_atuais = cat.get("cargos_permitidos_ids") or []

        comp_nome: Dict[str, Any] = {
            "type": 4,
            "custom_id": "cat_nome",
            "style": 1,
            "placeholder": "Ex: Suporte Técnico",
            "min_length": 1,
            "max_length": 50,
            "required": True
        }
        if nome_atual:
            comp_nome["value"] = nome_atual

        comp_desc: Dict[str, Any] = {
            "type": 4,
            "custom_id": "cat_descricao",
            "style": 1,
            "placeholder": "Ex: Tire suas dúvidas aqui",
            "min_length": 1,
            "max_length": 50,
            "required": True
        }
        if desc_atual:
            comp_desc["value"] = desc_atual

        comp_emoji: Dict[str, Any] = {
            "type": 4,
            "custom_id": "cat_emoji",
            "style": 1,
            "placeholder": "Ex: 🎫 ou <:suporte:123456789012345678>",
            "min_length": 0,
            "max_length": 100,
            "required": False
        }
        if emoji_atual:
            comp_emoji["value"] = emoji_atual

        comp_canal: Dict[str, Any] = {
            "type": 8,
            "custom_id": "cat_canal_topicos",
            "placeholder": "Selecione o canal de texto...",
            "channel_types": [0, 5],
            "min_values": 1,
            "max_values": 1,
            "required": True
        }
        if self.include_select_defaults and canal_atual and str(canal_atual).isdigit():
            comp_canal["default_values"] = [{"id": str(canal_atual), "type": "channel"}]

        gid_str = str(self.guild_id or (self.guild.id if self.guild else 0) or "direct")
        allowed_role_ids = _get_allowed_category_role_ids(gid_str, guild=self.guild)
        cargos_atuais_set = {str(rid) for rid in cargos_atuais if str(rid).isdigit()}
        role_options: List[Dict[str, Any]] = []
        for rid in allowed_role_ids[:25]:
            role_obj = self.guild.get_role(int(rid)) if (self.guild and rid.isdigit()) else None
            role_name = role_obj.name[:100] if role_obj else f"Cargo {rid}"
            opt: Dict[str, Any] = {
                "label": role_name,
                "value": rid
            }
            if self.include_select_defaults and rid in cargos_atuais_set:
                opt["default"] = True
            role_options.append(opt)

        comp_cargos: Dict[str, Any] = {
            "type": 3,
            "custom_id": "cat_cargos_permitidos",
            "placeholder": "Selecione os cargos permitidos...",
            "min_values": 1,
            "max_values": max(1, min(25, len(role_options))),
            "required": True,
            "options": role_options
        }

        return [
            {
                "type": 18,
                "label": "Nome da categoria",
                "description": "Nome exibido na opção do painel de atendimento",
                "component": comp_nome
            },
            {
                "type": 18,
                "label": "Descrição da categoria",
                "description": "Descrição breve (~25 caracteres) exibida no painel público",
                "component": comp_desc
            },
            {
                "type": 18,
                "label": "Emoji da categoria",
                "description": "Emoji Unicode ou personalizado (<:nome:id>) para o painel público",
                "component": comp_emoji
            },
            {
                "type": 18,
                "label": "Canal de tópicos",
                "description": "Onde o bot abrirá os tópicos privados de atendimento",
                "component": comp_canal
            },
            {
                "type": 18,
                "label": "Cargos permitidos",
                "description": "Cargos que poderão participar dos tópicos privados",
                "component": comp_cargos
            }
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "custom_id": self.custom_id,
            "components": self.to_components()
        }

    async def on_submit(self, interaction: discord.Interaction):
        nome = ""
        descricao = ""
        emoji_cat = ""
        canal_id = None
        cargos_ids: List[str] = []

        for wrapper in interaction.data.get("components", []):
            if wrapper.get("type") == 18 and isinstance(wrapper.get("component"), dict):
                inner_list = [wrapper["component"]]
            elif wrapper.get("type") == 1 and isinstance(wrapper.get("components"), list):
                inner_list = wrapper["components"]
            else:
                inner_list = [wrapper]

            for comp in inner_list:
                cid = comp.get("custom_id")
                if cid == "cat_nome":
                    nome = (comp.get("value") or "").strip()
                elif cid == "cat_descricao":
                    descricao = (comp.get("value") or "").strip()
                elif cid == "cat_emoji":
                    emoji_cat = (comp.get("value") or "").strip()[:100]
                elif cid == "cat_canal_topicos":
                    vals = comp.get("values") or []
                    if vals:
                        canal_id = str(vals[0])
                elif cid == "cat_cargos_permitidos":
                    vals = comp.get("values") or []
                    cargos_ids = [str(v) for v in vals]

        if emoji_cat:
            if EmojiManager.needs_remote_resolve(emoji_cat, guild=interaction.guild) and not interaction.response.is_done():
                await interaction.response.defer()
            emoji_cat = await EmojiManager.resolve_or_clone_emoji(
                emoji_cat,
                guild=interaction.guild,
                bot=interaction.client
            )

        gid_str = str(self.guild_id or interaction.guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        if not isinstance(cfg.get("categorias_ticket"), list):
            cfg["categorias_ticket"] = []

        if self.edit_cat_id is not None:
            updated = False
            for idx, cat in enumerate(cfg["categorias_ticket"]):
                cat_val = str(cat.get("id") or f"idx_{idx}")
                if cat_val == self.edit_cat_id:
                    if not cat.get("id"):
                        cat["id"] = uuid.uuid4().hex[:8]
                    cat["nome"] = nome
                    cat["descricao"] = descricao
                    cat["emoji"] = emoji_cat
                    cat["canal_topicos_id"] = canal_id
                    cat["cargos_permitidos_ids"] = cargos_ids
                    updated = True
                    break
            if not updated:
                cfg["categorias_ticket"].append({
                    "id": uuid.uuid4().hex[:8],
                    "nome": nome,
                    "descricao": descricao,
                    "emoji": emoji_cat,
                    "canal_topicos_id": canal_id,
                    "cargos_permitidos_ids": cargos_ids
                })
            logger.info(f"Categoria '{nome}' atualizada por {interaction.user} na guilda {gid_str}")
        else:
            nova_categoria = {
                "id": uuid.uuid4().hex[:8],
                "nome": nome,
                "descricao": descricao,
                "emoji": emoji_cat,
                "canal_topicos_id": canal_id,
                "cargos_permitidos_ids": cargos_ids
            }
            cfg["categorias_ticket"].append(nova_categoria)
            logger.info(f"Nova categoria '{nome}' criada por {interaction.user} na guilda {gid_str}")

        await CloudStorage.save_guild_config(gid_str, cfg)
        _schedule_panel_refresh(interaction.client, self.guild_id or (interaction.guild_id or 0), interaction.guild)
        await render_categories_panel(interaction, self.guild_id or (interaction.guild_id or 0), self.user_id, is_edit=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Erro no modal de categoria: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Ocorreu um erro ao salvar categoria: {error}", ephemeral=True)


class HorarioDiaModal(discord.ui.Modal, title="Horário de atendimento"):
    """Modal com 2 abas (Label Type 18) para definir horário de começo e término de um dia."""
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        dia_key: str,
        dia_label: str,
        inicio_atual: Optional[str] = None,
        fim_atual: Optional[str] = None
    ):
        super().__init__(title=f"Horário - {dia_label}"[:45])
        self.guild_id = guild_id
        self.user_id = user_id
        self.dia_key = dia_key
        self.dia_label = dia_label
        self.inicio_atual = inicio_atual
        self.fim_atual = fim_atual

    def to_components(self) -> List[Dict[str, Any]]:
        comp_inicio: Dict[str, Any] = {
            "type": 4,
            "custom_id": "horario_inicio",
            "style": 1,
            "placeholder": "Ex: 08:00",
            "min_length": 0,
            "max_length": 5,
            "required": False
        }
        if self.inicio_atual:
            comp_inicio["value"] = str(self.inicio_atual)[:5]

        comp_fim: Dict[str, Any] = {
            "type": 4,
            "custom_id": "horario_fim",
            "style": 1,
            "placeholder": "Ex: 18:00",
            "min_length": 0,
            "max_length": 5,
            "required": False
        }
        if self.fim_atual:
            comp_fim["value"] = str(self.fim_atual)[:5]

        return [
            {
                "type": 18,
                "label": "Horário de começo dos atendimentos",
                "description": "Formato HH:MM (ex: 08:00). Deixe vazio para desativar o dia.",
                "component": comp_inicio
            },
            {
                "type": 18,
                "label": "Horário de término dos atendimentos",
                "description": "Formato HH:MM (ex: 18:00). Deixe vazio para desativar o dia.",
                "component": comp_fim
            }
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "custom_id": self.custom_id,
            "components": self.to_components()
        }

    async def on_submit(self, interaction: discord.Interaction):
        raw_inicio = ""
        raw_fim = ""

        for wrapper in interaction.data.get("components", []):
            if wrapper.get("type") == 18 and isinstance(wrapper.get("component"), dict):
                inner_list = [wrapper["component"]]
            elif wrapper.get("type") == 1 and isinstance(wrapper.get("components"), list):
                inner_list = wrapper["components"]
            else:
                inner_list = [wrapper]

            for comp in inner_list:
                cid = comp.get("custom_id")
                if cid == "horario_inicio":
                    raw_inicio = (comp.get("value") or "").strip()
                elif cid == "horario_fim":
                    raw_fim = (comp.get("value") or "").strip()

        gid_str = str(self.guild_id or interaction.guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        dias = _get_dias_horario(cfg)

        if not raw_inicio and not raw_fim:
            dias[self.dia_key] = {"ativo": False, "inicio": None, "fim": None}
            logger.info(f"Horário de {self.dia_label} desativado por {interaction.user} na guilda {gid_str}")
        else:
            inicio_fmt = _normalize_hhmm(raw_inicio)
            fim_fmt = _normalize_hhmm(raw_fim)
            if not inicio_fmt or not fim_fmt:
                await interaction.response.send_message(
                    "Formato de horário inválido. Use o padrão `HH:MM` (ex: `08:00` e `18:00`) ou deixe ambos vazios para desativar.",
                    ephemeral=True
                )
                return
            dias[self.dia_key] = {"ativo": True, "inicio": inicio_fmt, "fim": fim_fmt}
            logger.info(f"Horário de {self.dia_label} definido para {inicio_fmt}-{fim_fmt} por {interaction.user} na guilda {gid_str}")

        cfg["horario_atendimento"]["ativo"] = any(bool(v.get("ativo")) for v in dias.values())
        await CloudStorage.save_guild_config(gid_str, cfg)

        await render_business_hours_panel(
            interaction,
            self.guild_id or (interaction.guild_id or 0),
            self.user_id or interaction.user.id,
            is_edit=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Erro no modal de horário de atendimento: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Ocorreu um erro ao salvar horário: {error}", ephemeral=True)


# =====================================================================
# BOTÕES DO PAINEL DE APARÊNCIA (SUBCLASSES COM CALLBACK PRÓPRIO)
# =====================================================================

class TituloButton(discord.ui.Button):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Título",
            emoji=resolve_partial_emoji("edit", "✏️"),
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_titulo",
            row=0
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Título button clicado por {interaction.user}")
        await interaction.response.send_modal(TituloModal(self.guild_id or (interaction.guild_id or 0), interaction.user.id))


class DescricaoButton(discord.ui.Button):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Descrição",
            emoji=resolve_partial_emoji("embed", "📄"),
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_descricao",
            row=0
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Descrição button clicado por {interaction.user}")
        await interaction.response.send_modal(DescricaoModal(self.guild_id or (interaction.guild_id or 0), interaction.user.id))


class BannerButton(discord.ui.Button):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Banner",
            emoji=resolve_partial_emoji("image", "🖼️"),
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_banner",
            row=0
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Banner button clicado por {interaction.user} (abrindo modal com componente de upload)")
        await interaction.response.send_modal(BannerModal(self.guild_id or (interaction.guild_id or 0), interaction.user.id))


class ThumbnailButton(discord.ui.Button):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Thumbnail",
            emoji=resolve_partial_emoji("image", "🖼️"),
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_thumbnail",
            row=1
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Thumbnail button clicado por {interaction.user} (abrindo modal com componente de upload)")
        await interaction.response.send_modal(ThumbnailModal(self.guild_id or (interaction.guild_id or 0), interaction.user.id))


class CorButton(discord.ui.Button):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Cor da embed",
            emoji=resolve_partial_emoji("colors", "🎨"),
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_cor",
            row=1
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Cor da embed button clicado por {interaction.user} (abrindo painel de cores)")
        await render_cor_panel(interaction, self.guild_id or (interaction.guild_id or 0), self.user_id or interaction.user.id, is_edit=True)


class CategoriasButton(discord.ui.Button):
    """Botão Categorias do painel de configurações do sistema."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Categorias",
            emoji=resolve_partial_emoji("folder", "📁"),
            style=discord.ButtonStyle.secondary,
            custom_id="btn_sistema_categorias",
            row=0
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Botão Categorias clicado por {interaction.user} (abrindo painel de categorias)")
        await render_categories_panel(
            interaction,
            self.guild_id or (interaction.guild_id or 0),
            self.user_id or interaction.user.id,
            is_edit=True
        )


class HorarioAtendimentoButton(discord.ui.Button):
    """Botão Horário de atendimento do painel de configurações do sistema."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Horário de atendimento",
            emoji=resolve_partial_emoji("clock", "🕒"),
            style=discord.ButtonStyle.secondary,
            custom_id="btn_sistema_horario_atendimento",
            row=0
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Botão Horário de atendimento clicado por {interaction.user} (abrindo painel de horário)")
        await render_business_hours_panel(
            interaction,
            self.guild_id or (interaction.guild_id or 0),
            self.user_id or interaction.user.id,
            is_edit=True
        )


class CriarCategoriaButton(discord.ui.Button):
    """Botão verde Criar categoria (abre o modal de criação)."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Criar categoria",
            emoji=resolve_partial_emoji("plus", "➕"),
            style=discord.ButtonStyle.success,  # Verde
            custom_id="btn_categorias_criar",
            row=0
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        gid_int = self.guild_id or (interaction.guild_id or 0)
        allowed_roles = _get_allowed_category_role_ids(str(gid_int or "direct"), guild=interaction.guild)
        if not allowed_roles:
            await interaction.response.send_message(
                f"{EmojiManager.get('warn')} Nenhum **Cargo Permitido** foi configurado ainda! "
                "Vá em `/configurações` → **Cargos** e selecione os **Cargos Permitidos** primeiro.",
                ephemeral=True
            )
            return
        logger.info(f"Botão Criar categoria clicado por {interaction.user} (abrindo modal)")
        await interaction.response.send_modal(
            CriarCategoriaModal(gid_int, interaction.user.id, guild=interaction.guild)
        )


class RemoverCategoriaButton(discord.ui.Button):
    """Botão vermelho Remover categoria (abre painel com select menu das categorias existentes)."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Remover categoria",
            emoji=resolve_partial_emoji("delete", "🗑️"),
            style=discord.ButtonStyle.danger,  # Vermelho
            custom_id="btn_categorias_remover",
            row=0
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Botão Remover categoria clicado por {interaction.user} (abrindo painel de remoção)")
        await render_remove_category_panel(
            interaction,
            self.guild_id or (interaction.guild_id or 0),
            self.user_id or interaction.user.id,
            is_edit=True
        )


class EditarCategoriaButton(discord.ui.Button):
    """Botão cinza Editar categoria (abre painel com select menu das categorias existentes)."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Editar categoria",
            emoji=resolve_partial_emoji("edit", "✏️"),
            style=discord.ButtonStyle.secondary,  # Cinza
            custom_id="btn_categorias_editar",
            row=0
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Botão Editar categoria clicado por {interaction.user} (abrindo painel de edição)")
        await render_edit_category_panel(
            interaction,
            self.guild_id or (interaction.guild_id or 0),
            self.user_id or interaction.user.id,
            is_edit=True
        )


class VoltarParaSistemaButton(discord.ui.Button):
    """Botão Voltar dos subpainéis do sistema: sempre azul na última linha separada."""
    def __init__(self, guild_id: int, user_id: int, custom_id: str = "btn_categorias_voltar"):
        super().__init__(
            label="Voltar",
            emoji=resolve_partial_emoji("back", "⬅️"),
            style=discord.ButtonStyle.primary,  # Sempre Azul (Primary)
            custom_id=custom_id,
            row=1  # Última fila separada
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Botão Voltar clicado por {interaction.user} no painel de categorias")
        await render_settings_panel(
            interaction,
            self.guild_id or (interaction.guild_id or 0),
            self.user_id or interaction.user.id,
            is_edit=True
        )


class VoltarParaPrincipalButton(discord.ui.Button):
    def __init__(self, guild_id: int, user_id: int, row: int = 2, custom_id: str = "btn_aparencia_voltar"):
        super().__init__(
            label="Voltar",
            emoji=resolve_partial_emoji("back", "⬅️"),
            style=discord.ButtonStyle.primary,  # Sempre Azul (Primary)
            custom_id=custom_id,
            row=row  # Última fila separada exclusivamente para o botão Voltar
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Voltar button clicado por {interaction.user}")
        await render_main_panel(interaction, self.guild_id or (interaction.guild_id or 0), interaction.user.id, is_edit=True)


# =====================================================================
# SELECT MENUS & VIEWS DE CORES COM EMOJI <:colors:1561906164810125362>
# =====================================================================

class CorEmbedSelect(discord.ui.Select):
    """
    Select Menu contendo as 10 cores predefinidas para a embed.
    Todas as opções possuem obrigatoriamente o emoji <:colors:1561906164810125362>.
    """
    def __init__(self, guild_id: int, user_id: int):
        self.guild_id = guild_id
        self.user_id = user_id

        # Emoji <:colors:1561906164810125362> em todas as 10 opções
        emoji_colors = resolve_partial_emoji("colors", "🎨")

        options = [
            discord.SelectOption(
                label=cor["label"],
                value=cor["value"],
                description=cor["desc"],
                emoji=emoji_colors
            )
            for cor in CORES_DISPONIVEIS
        ]

        super().__init__(
            placeholder="Selecione a cor desejada...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_cor_embed"
        )

    async def callback(self, interaction: discord.Interaction):
        cor_hex_val = self.values[0]
        cor_selecionada = next((c for c in CORES_DISPONIVEIS if c["value"] == cor_hex_val), None)

        if cor_selecionada:
            gid = str(self.guild_id or interaction.guild_id or "direct")
            cfg = CloudStorage.get_guild_config(gid)
            cfg["painel"]["cor_hex"] = cor_selecionada["hex"]
            cfg["painel"]["cor"] = cor_selecionada["int"]
            cfg["painel"]["cor_configurada"] = True
            await CloudStorage.save_guild_config(gid, cfg)
            _schedule_panel_refresh(interaction.client, self.guild_id or (interaction.guild_id or 0), interaction.guild)
            logger.info(f"Cor da embed alterada por {interaction.user} para {cor_selecionada['hex']}")

            await render_cor_panel(interaction, self.guild_id, self.user_id, is_edit=True)


class VoltarParaAparenciaButton(discord.ui.Button):
    """
    Botão Voltar do painel de cores:
    Chama-se apenas 'Voltar', sempre em linha separada (última fila) e sempre azul (primary).
    """
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Voltar",  # Chamado apenas 'Voltar' e nada mais
            emoji=resolve_partial_emoji("back", "⬅️"),
            style=discord.ButtonStyle.primary,  # Sempre Azul (Primary)
            custom_id="btn_cor_voltar",
            row=1  # Última fila separada da ActionRow do select
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Voltar clicado por {interaction.user} no painel de cores")
        await render_appearance_panel(interaction, self.guild_id or (interaction.guild_id or 0), self.user_id or interaction.user.id, is_edit=True)


class RemoverCategoriaSelect(discord.ui.Select):
    """Select Menu contendo apenas as categorias existentes para remoção."""
    def __init__(self, guild_id: int, user_id: int, categorias: List[Dict[str, Any]], guild=None):
        self.guild_id = guild_id
        self.user_id = user_id

        options = []
        for idx, cat in enumerate(categorias[:25]):
            nome = (cat.get("nome") or f"Categoria {idx + 1}").strip()[:100]
            desc_raw = (cat.get("descricao") or "").strip()
            desc = desc_raw[:100] if desc_raw else None
            val = str(cat.get("id") or f"idx_{idx}")[:100]
            opt_emoji = resolve_category_emoji(cat.get("emoji"), "folder", "📁", guild=guild)
            options.append(
                discord.SelectOption(
                    label=nome,
                    value=val,
                    description=desc,
                    emoji=opt_emoji
                )
            )

        super().__init__(
            placeholder="Selecione a categoria para remover...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_remover_categoria"
        )

    async def callback(self, interaction: discord.Interaction):
        selected_id = self.values[0]
        gid = str(self.guild_id or interaction.guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid)
        categorias = cfg.get("categorias_ticket", [])

        novas_categorias = []
        removida_nome = selected_id
        removed = False
        for idx, cat in enumerate(categorias):
            cat_val = str(cat.get("id") or f"idx_{idx}")
            if not removed and cat_val == selected_id:
                removida_nome = cat.get("nome") or selected_id
                removed = True
                continue
            novas_categorias.append(cat)

        cfg["categorias_ticket"] = novas_categorias
        await CloudStorage.save_guild_config(gid, cfg)
        _schedule_panel_refresh(interaction.client, self.guild_id or (interaction.guild_id or 0), interaction.guild)
        logger.info(f"Categoria '{removida_nome}' removida por {interaction.user} na guilda {gid}")

        await render_categories_panel(
            interaction,
            self.guild_id or (interaction.guild_id or 0),
            self.user_id or interaction.user.id,
            is_edit=True
        )


class EditarCategoriaSelect(discord.ui.Select):
    """Select Menu contendo as categorias existentes para edição via modal."""
    def __init__(self, guild_id: int, user_id: int, categorias: List[Dict[str, Any]], guild=None):
        self.guild_id = guild_id
        self.user_id = user_id

        options = []
        for idx, cat in enumerate(categorias[:25]):
            nome = (cat.get("nome") or f"Categoria {idx + 1}").strip()[:100]
            desc_raw = (cat.get("descricao") or "").strip()
            desc = desc_raw[:100] if desc_raw else None
            val = str(cat.get("id") or f"idx_{idx}")[:100]
            opt_emoji = resolve_category_emoji(cat.get("emoji"), "folder", "📁", guild=guild)
            options.append(
                discord.SelectOption(
                    label=nome,
                    value=val,
                    description=desc,
                    emoji=opt_emoji
                )
            )

        super().__init__(
            placeholder="Selecione a categoria para editar...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_editar_categoria"
        )

    async def callback(self, interaction: discord.Interaction):
        selected_id = self.values[0]
        gid = str(self.guild_id or interaction.guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid)
        categorias = cfg.get("categorias_ticket", [])

        categoria_alvo = None
        for idx, cat in enumerate(categorias):
            cat_val = str(cat.get("id") or f"idx_{idx}")
            if cat_val == selected_id:
                categoria_alvo = cat
                break

        if categoria_alvo is None:
            await render_categories_panel(
                interaction,
                self.guild_id or (interaction.guild_id or 0),
                self.user_id or interaction.user.id,
                is_edit=True
            )
            return

        cat_nome_log = categoria_alvo.get("nome", selected_id)
        logger.info(f"Categoria '{cat_nome_log}' selecionada para edição por {interaction.user}")

        gid_int = self.guild_id or (interaction.guild_id or 0)
        uid_int = self.user_id or interaction.user.id

        allowed_roles = _get_allowed_category_role_ids(str(gid_int or "direct"), guild=interaction.guild)
        if not allowed_roles:
            await interaction.response.send_message(
                f"{EmojiManager.get('warn')} Nenhum **Cargo Permitido** foi configurado ainda! "
                "Vá em `/configurações` → **Cargos** e selecione os **Cargos Permitidos** primeiro.",
                ephemeral=True
            )
            return
        try:
            await interaction.response.send_modal(
                CriarCategoriaModal(
                    gid_int,
                    uid_int,
                    edit_cat_id=selected_id,
                    categoria_atual=categoria_alvo,
                    include_select_defaults=True,
                    guild=interaction.guild
                )
            )
        except discord.HTTPException as e:
            logger.warning(f"Falha ao abrir modal com default_values ({e}). Tentando sem default_values...")
            if not interaction.response.is_done():
                await interaction.response.send_modal(
                    CriarCategoriaModal(
                        gid_int,
                        uid_int,
                        edit_cat_id=selected_id,
                        categoria_atual=categoria_alvo,
                        include_select_defaults=False,
                        guild=interaction.guild
                    )
                )


class HorarioDiaSelect(discord.ui.Select):
    """Select Menu contendo todos os 7 dias da semana para configurar horário de atendimento."""
    def __init__(self, guild_id: int, user_id: int, cfg: Dict[str, Any]):
        self.guild_id = guild_id
        self.user_id = user_id

        dias = _get_dias_horario(cfg)
        emoji_online = resolve_partial_emoji("on", "🟢")
        emoji_off = resolve_partial_emoji("off", "⚪")

        options = []
        for d in DIAS_SEMANA:
            info = dias.get(d["key"], {})
            ativo = bool(info.get("ativo")) and bool(info.get("inicio")) and bool(info.get("fim"))
            if ativo:
                desc = f"{info['inicio']} às {info['fim']}"
                opt_emoji = emoji_online
            else:
                desc = "Não configurado"
                opt_emoji = emoji_off

            options.append(
                discord.SelectOption(
                    label=d["label"],
                    value=d["key"],
                    description=desc,
                    emoji=opt_emoji
                )
            )

        super().__init__(
            placeholder="Selecione um dia da semana...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_horario_dia"
        )

    async def callback(self, interaction: discord.Interaction):
        dia_key = self.values[0]
        dia_info = next((d for d in DIAS_SEMANA if d["key"] == dia_key), None)
        dia_label = dia_info["label"] if dia_info else dia_key

        gid = str(self.guild_id or interaction.guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid)
        dias = _get_dias_horario(cfg)
        atual = dias.get(dia_key, {})

        logger.info(f"Dia '{dia_label}' selecionado para edição de horário por {interaction.user}")
        await interaction.response.send_modal(
            HorarioDiaModal(
                self.guild_id or (interaction.guild_id or 0),
                self.user_id or interaction.user.id,
                dia_key=dia_key,
                dia_label=dia_label,
                inicio_atual=atual.get("inicio"),
                fim_atual=atual.get("fim")
            )
        )


class VoltarParaCategoriasButton(discord.ui.Button):
    """Botão Voltar dos subpainéis de categoria: sempre azul na última linha separada."""
    def __init__(self, guild_id: int, user_id: int, custom_id: str = "btn_remover_categoria_voltar"):
        super().__init__(
            label="Voltar",
            emoji=resolve_partial_emoji("back", "⬅️"),
            style=discord.ButtonStyle.primary,
            custom_id=custom_id,
            row=1
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Botão Voltar clicado por {interaction.user} no painel de remover categoria")
        await render_categories_panel(
            interaction,
            self.guild_id or (interaction.guild_id or 0),
            self.user_id or interaction.user.id,
            is_edit=True
        )


# =====================================================================
# SELECT MENU PRINCIPAL
# =====================================================================

class ConfigPainelSelect(discord.ui.Select):
    """Select Menu do painel principal de configuração."""
    def __init__(self, guild_id: int = 0, user_id: int = 0):
        self.guild_id = guild_id
        self.user_id = user_id

        emoji_aparencia = resolve_partial_emoji("paint", "🎨")
        emoji_config = resolve_partial_emoji("settings", "⚙️")

        options = [
            discord.SelectOption(
                label="Aparência do painel",
                value="aparencia",
                description="Personalize cores, textos, banners e imagem",
                emoji=emoji_aparencia
            ),
            discord.SelectOption(
                label="Configurações do sistema",
                value="configuracoes",
                description="Defina categorias, canais e funcionalidades do sistema",
                emoji=emoji_config
            )
        ]

        super().__init__(
            placeholder="Selecione uma opção para configurar.",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_config_painel_principal"
        )

    async def callback(self, interaction: discord.Interaction):
        escolha = self.values[0]
        logger.info(f"Opção '{escolha}' selecionada por {interaction.user}")

        if escolha == "aparencia":
            await render_appearance_panel(
                interaction,
                self.guild_id or (interaction.guild_id or 0),
                self.user_id or interaction.user.id,
                is_edit=True
            )
        elif escolha == "configuracoes":
            await render_settings_panel(
                interaction,
                self.guild_id or (interaction.guild_id or 0),
                self.user_id or interaction.user.id,
                is_edit=True
            )


# =====================================================================
# CONSTRUTORES DE LAYOUT COMPONENTS V2 (CONTAINER TYPE 17)
# =====================================================================

def build_v2_main_layout(guild_id: int, user_id: int):
    """Constrói a árvore de LayoutView com Container para o painel principal."""
    if not HAS_COMPONENTS_V2:
        return None

    try:
        text = format_main_panel_text()
        layout_view = discord.ui.LayoutView(timeout=None)
        select = ConfigPainelSelect(guild_id, user_id)
        row = discord.ui.ActionRow(select)

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = discord.ui.Separator(visible=True) if spacing_arg is None else discord.ui.Separator(visible=True, spacing=spacing_arg)

        container_items: List[Any] = []
        if hasattr(discord.ui, "MediaGallery") and hasattr(discord, "MediaGalleryItem"):
            container_items.append(
                discord.ui.MediaGallery(discord.MediaGalleryItem(media=MAIN_PANEL_BANNER_URL))
            )
        container_items.extend([
            discord.ui.TextDisplay(text),
            separator,
            row,
        ])
        container = discord.ui.Container(
            *container_items,
            accent_colour=config.EMBED_COLOR_DEFAULT
        )
        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Erro ao instanciar LayoutView v2 principal: {e}")
        return None


def build_v2_appearance_layout(guild_id: int, user_id: int):
    """
    Constrói a árvore de LayoutView com Container para o painel de aparência.
    Botão Voltar estritamente na última linha separada e em azul.
    """
    if not HAS_COMPONENTS_V2:
        return None

    try:
        gid_str = str(guild_id or "direct")
        text = format_appearance_panel_text(gid_str)
        cfg = CloudStorage.get_guild_config(gid_str)
        cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT

        layout_view = discord.ui.LayoutView(timeout=None)

        # Linha 1 (Título, Descrição, Banner)
        row1 = discord.ui.ActionRow(
            TituloButton(guild_id, user_id),
            DescricaoButton(guild_id, user_id),
            BannerButton(guild_id, user_id)
        )

        # Linha 2 (Thumbnail, Cor da embed)
        row2 = discord.ui.ActionRow(
            ThumbnailButton(guild_id, user_id),
            CorButton(guild_id, user_id)
        )

        # Linha 3 (Última fila separada exclusivamente para o botão Voltar em azul)
        row_voltar = discord.ui.ActionRow(
            VoltarParaPrincipalButton(guild_id, user_id)
        )

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = discord.ui.Separator(visible=True) if spacing_arg is None else discord.ui.Separator(visible=True, spacing=spacing_arg)

        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            separator,
            row1,
            row2,
            row_voltar,
            accent_colour=cor_embed
        )
        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Erro ao instanciar LayoutView v2 de aparência: {e}")
        return None


def build_v2_cor_layout(guild_id: int, user_id: int):
    """
    Constrói a árvore de LayoutView com Container para o painel de cores.
    Botão Voltar estritamente na última linha separada, chamado 'Voltar' e em azul.
    """
    if not HAS_COMPONENTS_V2:
        return None

    try:
        gid_str = str(guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT
        emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")

        text = (
            "## Configurar Cor da embed do painel de atendimento.\n\n"
            f"{emoji_info} Selecione a cor desejada usando o select menu abaixo."
        )

        layout_view = discord.ui.LayoutView(timeout=None)

        row_select = discord.ui.ActionRow(CorEmbedSelect(guild_id, user_id))
        row_btn_voltar = discord.ui.ActionRow(VoltarParaAparenciaButton(guild_id, user_id))

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = discord.ui.Separator(visible=True) if spacing_arg is None else discord.ui.Separator(visible=True, spacing=spacing_arg)

        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            separator,
            row_select,
            row_btn_voltar,
            accent_colour=cor_embed
        )
        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Erro ao instanciar LayoutView v2 de cor: {e}")
        return None


def build_v2_settings_layout(guild_id: int, user_id: int):
    """
    Constrói a árvore de LayoutView com Container para o painel de configurações do sistema.
    Contém o botão Categorias (sem ação) e o botão Voltar azul na última linha separada.
    """
    if not HAS_COMPONENTS_V2:
        return None

    try:
        gid_str = str(guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT
        text = format_settings_panel_text()

        layout_view = discord.ui.LayoutView(timeout=None)

        row1 = discord.ui.ActionRow(
            CategoriasButton(guild_id, user_id),
            HorarioAtendimentoButton(guild_id, user_id)
        )
        row_voltar = discord.ui.ActionRow(
            VoltarParaPrincipalButton(guild_id, user_id, row=1, custom_id="btn_sistema_voltar")
        )

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = discord.ui.Separator(visible=True) if spacing_arg is None else discord.ui.Separator(visible=True, spacing=spacing_arg)

        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            separator,
            row1,
            row_voltar,
            accent_colour=cor_embed
        )
        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Erro ao instanciar LayoutView v2 de configurações do sistema: {e}")
        return None


def build_v2_business_hours_layout(guild_id: int, user_id: int):
    """
    Constrói a árvore de LayoutView com Container para o painel de Horário de atendimento.
    """
    if not HAS_COMPONENTS_V2:
        return None

    try:
        gid_str = str(guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT
        text = format_business_hours_panel_text(gid_str)

        layout_view = discord.ui.LayoutView(timeout=None)

        row_select = discord.ui.ActionRow(
            HorarioDiaSelect(guild_id, user_id, cfg)
        )
        row_voltar = discord.ui.ActionRow(
            VoltarParaSistemaButton(guild_id, user_id, custom_id="btn_horario_voltar")
        )

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = discord.ui.Separator(visible=True) if spacing_arg is None else discord.ui.Separator(visible=True, spacing=spacing_arg)

        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            separator,
            row_select,
            row_voltar,
            accent_colour=cor_embed
        )
        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Erro ao instanciar LayoutView v2 de horário de atendimento: {e}")
        return None


def build_v2_categories_layout(guild_id: int, user_id: int):
    """
    Constrói a árvore de LayoutView com Container para o painel de Categorias.
    Contém Criar (verde), Remover (vermelho), Editar (cinza) e Voltar (azul na última linha).
    """
    if not HAS_COMPONENTS_V2:
        return None

    try:
        gid_str = str(guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT
        text = format_categories_panel_text(gid_str)

        layout_view = discord.ui.LayoutView(timeout=None)

        row1 = discord.ui.ActionRow(
            CriarCategoriaButton(guild_id, user_id),
            RemoverCategoriaButton(guild_id, user_id),
            EditarCategoriaButton(guild_id, user_id)
        )
        row_voltar = discord.ui.ActionRow(
            VoltarParaSistemaButton(guild_id, user_id)
        )

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = discord.ui.Separator(visible=True) if spacing_arg is None else discord.ui.Separator(visible=True, spacing=spacing_arg)

        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            separator,
            row1,
            row_voltar,
            accent_colour=cor_embed
        )
        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Erro ao instanciar LayoutView v2 de categorias: {e}")
        return None


def build_v2_remove_category_layout(guild_id: int, user_id: int, guild=None):
    """
    Constrói a árvore de LayoutView com Container para o painel de Remover categoria.
    Contém apenas as categorias existentes no Select Menu + botão Voltar azul na última linha.
    """
    if not HAS_COMPONENTS_V2:
        return None

    try:
        gid_str = str(guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT
        categorias = cfg.get("categorias_ticket", [])
        text = format_remove_category_panel_text(has_categories=bool(categorias))

        layout_view = discord.ui.LayoutView(timeout=None)

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = discord.ui.Separator(visible=True) if spacing_arg is None else discord.ui.Separator(visible=True, spacing=spacing_arg)

        row_voltar = discord.ui.ActionRow(VoltarParaCategoriasButton(guild_id, user_id))

        if categorias:
            row_select = discord.ui.ActionRow(RemoverCategoriaSelect(guild_id, user_id, categorias, guild=guild))
            container = discord.ui.Container(
                discord.ui.TextDisplay(text),
                separator,
                row_select,
                row_voltar,
                accent_colour=cor_embed
            )
        else:
            container = discord.ui.Container(
                discord.ui.TextDisplay(text),
                separator,
                row_voltar,
                accent_colour=cor_embed
            )

        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Erro ao instanciar LayoutView v2 de remover categoria: {e}")
        return None


def build_v2_edit_category_layout(guild_id: int, user_id: int, guild=None):
    """
    Constrói a árvore de LayoutView com Container para o painel de Editar categoria.
    Contém as categorias existentes no Select Menu + botão Voltar azul na última linha.
    """
    if not HAS_COMPONENTS_V2:
        return None

    try:
        gid_str = str(guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT
        categorias = cfg.get("categorias_ticket", [])
        text = format_edit_category_panel_text(has_categories=bool(categorias))

        layout_view = discord.ui.LayoutView(timeout=None)

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = discord.ui.Separator(visible=True) if spacing_arg is None else discord.ui.Separator(visible=True, spacing=spacing_arg)

        row_voltar = discord.ui.ActionRow(
            VoltarParaCategoriasButton(guild_id, user_id, custom_id="btn_editar_categoria_voltar")
        )

        if categorias:
            row_select = discord.ui.ActionRow(EditarCategoriaSelect(guild_id, user_id, categorias, guild=guild))
            container = discord.ui.Container(
                discord.ui.TextDisplay(text),
                separator,
                row_select,
                row_voltar,
                accent_colour=cor_embed
            )
        else:
            container = discord.ui.Container(
                discord.ui.TextDisplay(text),
                separator,
                row_voltar,
                accent_colour=cor_embed
            )

        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Erro ao instanciar LayoutView v2 de editar categoria: {e}")
        return None


# =====================================================================
# RENDERIZADORES COMPATÍVEIS (V2 PRIMARY COM FALLBACK AUTOMÁTICO)
# =====================================================================

async def render_main_panel(interaction: discord.Interaction, guild_id: int, user_id: int, is_edit: bool = False):
    """Renderiza o painel principal com Componentes V2 / Container."""
    v2_view = build_v2_main_layout(guild_id, user_id)
    if v2_view is not None:
        try:
            if is_edit:
                await interaction.response.edit_message(view=v2_view)
            else:
                await interaction.response.send_message(view=v2_view, ephemeral=True)
            logger.info("Painel principal enviado com Componentes V2 (Container)")
            return
        except discord.NotFound as e:
            elapsed = (discord.utils.utcnow() - interaction.created_at).total_seconds()
            if getattr(e, "code", None) == 10062 and elapsed < 2.5:
                logger.critical(f"[DUPLICATE INSTANCE] 10062 Unknown interaction em {elapsed:.3f}s! Outra instância com o mesmo DISCORD_TOKEN respondeu antes.")
                return
            logger.warning(f"Aviso ao enviar LayoutView v2: {e}. Usando fallback.")
        except Exception as e:
            logger.warning(f"Aviso ao enviar LayoutView v2: {e}. Usando fallback.")

    text = format_main_panel_text()
    embed = discord.Embed(description=text, color=config.EMBED_COLOR_DEFAULT)
    embed.set_image(url=MAIN_PANEL_BANNER_URL)
    view = discord.ui.View(timeout=None)
    view.add_item(ConfigPainelSelect(guild_id, user_id))

    if is_edit:
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def _ensure_guild_appearance_emojis(interaction: discord.Interaction, guild_id: int) -> None:
    """Migra emojis externos em título/descrição antes de renderizar o painel."""
    gid_str = str(guild_id or "direct")
    cfg = CloudStorage.get_guild_config(gid_str)
    painel_cfg = cfg.get("painel", {})
    for field in ("titulo", "descricao"):
        raw = painel_cfg.get(field)
        if isinstance(raw, str) and EmojiManager.text_needs_remote_resolve(raw, guild=interaction.guild):
            await EmojiManager.migrate_guild_appearance(gid_str, guild=interaction.guild, bot=interaction.client)
            break


async def render_appearance_panel(interaction: discord.Interaction, guild_id: int, user_id: int, is_edit: bool = True):
    """Renderiza o painel de aparência com Componentes V2 (Container + botões)."""
    await _ensure_guild_appearance_emojis(interaction, guild_id)
    v2_view = build_v2_appearance_layout(guild_id, user_id)
    if v2_view is not None:
        try:
            if is_edit:
                if interaction.response.is_done():
                    await interaction.edit_original_response(view=v2_view)
                else:
                    await interaction.response.edit_message(view=v2_view)
            else:
                if interaction.response.is_done():
                    await interaction.followup.send(view=v2_view, ephemeral=True)
                else:
                    await interaction.response.send_message(view=v2_view, ephemeral=True)
            logger.info("Painel de aparência enviado com Componentes V2 (Container)")
            return
        except Exception as e:
            logger.warning(f"Aviso ao enviar LayoutView v2: {e}. Usando fallback.")

    text = format_appearance_panel_text(str(guild_id))
    embed = discord.Embed(description=text, color=config.EMBED_COLOR_DEFAULT)
    view = discord.ui.View(timeout=None)
    view.add_item(TituloButton(guild_id, user_id))
    view.add_item(DescricaoButton(guild_id, user_id))
    view.add_item(BannerButton(guild_id, user_id))
    view.add_item(ThumbnailButton(guild_id, user_id))
    view.add_item(CorButton(guild_id, user_id))
    view.add_item(VoltarParaPrincipalButton(guild_id, user_id))

    if is_edit:
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def render_cor_panel(interaction: discord.Interaction, guild_id: int, user_id: int, is_edit: bool = True):
    """Renderiza o painel de cores com Componentes V2 (Container + Select de 10 cores com emoji <:colors:...>)."""
    v2_view = build_v2_cor_layout(guild_id, user_id)
    if v2_view is not None:
        try:
            if is_edit:
                await interaction.response.edit_message(view=v2_view)
            else:
                await interaction.response.send_message(view=v2_view, ephemeral=True)
            logger.info("Painel de cores enviado com Componentes V2 (Container)")
            return
        except Exception as e:
            logger.warning(f"Aviso ao enviar LayoutView v2: {e}. Usando fallback.")

    gid_str = str(guild_id or "direct")
    cfg = CloudStorage.get_guild_config(gid_str)
    cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT
    emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")

    text = (
        "## Configurar Cor da embed do painel de atendimento.\n\n"
        f"{emoji_info} Selecione a cor desejada usando o select menu abaixo."
    )
    embed = discord.Embed(description=text, color=cor_embed)
    view = discord.ui.View(timeout=None)
    view.add_item(CorEmbedSelect(guild_id, user_id))
    view.add_item(VoltarParaAparenciaButton(guild_id, user_id))

    if is_edit:
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def render_settings_panel(interaction: discord.Interaction, guild_id: int, user_id: int, is_edit: bool = True):
    """Renderiza o painel de configurações do sistema com Componentes V2 (Container + Categorias + Voltar)."""
    v2_view = build_v2_settings_layout(guild_id, user_id)
    if v2_view is not None:
        try:
            if is_edit:
                await interaction.response.edit_message(view=v2_view)
            else:
                await interaction.response.send_message(view=v2_view, ephemeral=True)
            logger.info("Painel de configurações do sistema enviado com Componentes V2 (Container)")
            return
        except Exception as e:
            logger.warning(f"Aviso ao enviar LayoutView v2 de configurações do sistema: {e}. Usando fallback.")

    gid_str = str(guild_id or "direct")
    cfg = CloudStorage.get_guild_config(gid_str)
    cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT
    text = format_settings_panel_text()
    embed = discord.Embed(description=text, color=cor_embed)
    view = discord.ui.View(timeout=None)
    view.add_item(CategoriasButton(guild_id, user_id))
    view.add_item(HorarioAtendimentoButton(guild_id, user_id))
    view.add_item(VoltarParaPrincipalButton(guild_id, user_id, row=1, custom_id="btn_sistema_voltar"))

    if is_edit:
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def render_business_hours_panel(interaction: discord.Interaction, guild_id: int, user_id: int, is_edit: bool = True):
    """Renderiza o painel de Horário de atendimento com Componentes V2 (Container + Voltar)."""
    v2_view = build_v2_business_hours_layout(guild_id, user_id)
    if v2_view is not None:
        try:
            if is_edit:
                if interaction.response.is_done():
                    await interaction.edit_original_response(view=v2_view)
                else:
                    await interaction.response.edit_message(view=v2_view)
            else:
                await interaction.response.send_message(view=v2_view, ephemeral=True)
            logger.info("Painel de horário de atendimento enviado com Componentes V2 (Container)")
            return
        except Exception as e:
            logger.warning(f"Aviso ao enviar LayoutView v2 de horário de atendimento: {e}. Usando fallback.")

    gid_str = str(guild_id or "direct")
    cfg = CloudStorage.get_guild_config(gid_str)
    cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT
    text = format_business_hours_panel_text(gid_str)
    embed = discord.Embed(description=text, color=cor_embed)
    view = discord.ui.View(timeout=None)
    view.add_item(HorarioDiaSelect(guild_id, user_id, cfg))
    view.add_item(VoltarParaSistemaButton(guild_id, user_id, custom_id="btn_horario_voltar"))

    if is_edit:
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def _ensure_guild_category_emojis(interaction: discord.Interaction, guild_id: int) -> None:
    """Garante que emojis externos de categorias já salvas sejam clonados antes de renderizar."""
    gid_str = str(guild_id or "direct")
    cfg = CloudStorage.get_guild_config(gid_str)
    categorias = cfg.get("categorias_ticket", [])
    if any(EmojiManager.needs_remote_resolve(c.get("emoji"), guild=interaction.guild) for c in categorias):
        if not interaction.response.is_done():
            await interaction.response.defer()
        await EmojiManager.migrate_guild_categories(gid_str, guild=interaction.guild, bot=interaction.client)


async def render_categories_panel(interaction: discord.Interaction, guild_id: int, user_id: int, is_edit: bool = True):
    """Renderiza o painel de Categorias com Componentes V2 (Container + Criar/Remover/Editar + Voltar)."""
    await _ensure_guild_category_emojis(interaction, guild_id)
    v2_view = build_v2_categories_layout(guild_id, user_id)
    if v2_view is not None:
        try:
            if is_edit:
                if interaction.response.is_done():
                    await interaction.edit_original_response(view=v2_view)
                else:
                    await interaction.response.edit_message(view=v2_view)
            else:
                if interaction.response.is_done():
                    await interaction.followup.send(view=v2_view, ephemeral=True)
                else:
                    await interaction.response.send_message(view=v2_view, ephemeral=True)
            logger.info("Painel de categorias enviado com Componentes V2 (Container)")
            return
        except Exception as e:
            logger.warning(f"Aviso ao enviar LayoutView v2 de categorias: {e}. Usando fallback.")

    gid_str = str(guild_id or "direct")
    cfg = CloudStorage.get_guild_config(gid_str)
    cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT
    text = format_categories_panel_text(gid_str)
    embed = discord.Embed(description=text, color=cor_embed)
    view = discord.ui.View(timeout=None)
    view.add_item(CriarCategoriaButton(guild_id, user_id))
    view.add_item(RemoverCategoriaButton(guild_id, user_id))
    view.add_item(EditarCategoriaButton(guild_id, user_id))
    view.add_item(VoltarParaSistemaButton(guild_id, user_id))

    if is_edit:
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def render_remove_category_panel(interaction: discord.Interaction, guild_id: int, user_id: int, is_edit: bool = True):
    """Renderiza o painel de Remover categoria com Select Menu apenas das categorias existentes."""
    await _ensure_guild_category_emojis(interaction, guild_id)
    v2_view = build_v2_remove_category_layout(guild_id, user_id, guild=interaction.guild)
    if v2_view is not None:
        try:
            if is_edit:
                if interaction.response.is_done():
                    await interaction.edit_original_response(view=v2_view)
                else:
                    await interaction.response.edit_message(view=v2_view)
            else:
                if interaction.response.is_done():
                    await interaction.followup.send(view=v2_view, ephemeral=True)
                else:
                    await interaction.response.send_message(view=v2_view, ephemeral=True)
            logger.info("Painel de remover categoria enviado com Componentes V2 (Container)")
            return
        except Exception as e:
            logger.warning(f"Aviso ao enviar LayoutView v2 de remover categoria: {e}. Usando fallback.")

    gid_str = str(guild_id or "direct")
    cfg = CloudStorage.get_guild_config(gid_str)
    cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT
    categorias = cfg.get("categorias_ticket", [])
    text = format_remove_category_panel_text(has_categories=bool(categorias))
    embed = discord.Embed(description=text, color=cor_embed)
    view = discord.ui.View(timeout=None)
    if categorias:
        view.add_item(RemoverCategoriaSelect(guild_id, user_id, categorias, guild=interaction.guild))
    view.add_item(VoltarParaCategoriasButton(guild_id, user_id))

    if is_edit:
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def render_edit_category_panel(interaction: discord.Interaction, guild_id: int, user_id: int, is_edit: bool = True):
    """Renderiza o painel de Editar categoria com Select Menu das categorias existentes."""
    await _ensure_guild_category_emojis(interaction, guild_id)
    v2_view = build_v2_edit_category_layout(guild_id, user_id, guild=interaction.guild)
    if v2_view is not None:
        try:
            if is_edit:
                if interaction.response.is_done():
                    await interaction.edit_original_response(view=v2_view)
                else:
                    await interaction.response.edit_message(view=v2_view)
            else:
                if interaction.response.is_done():
                    await interaction.followup.send(view=v2_view, ephemeral=True)
                else:
                    await interaction.response.send_message(view=v2_view, ephemeral=True)
            logger.info("Painel de editar categoria enviado com Componentes V2 (Container)")
            return
        except Exception as e:
            logger.warning(f"Aviso ao enviar LayoutView v2 de editar categoria: {e}. Usando fallback.")

    gid_str = str(guild_id or "direct")
    cfg = CloudStorage.get_guild_config(gid_str)
    cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT
    categorias = cfg.get("categorias_ticket", [])
    text = format_edit_category_panel_text(has_categories=bool(categorias))
    embed = discord.Embed(description=text, color=cor_embed)
    view = discord.ui.View(timeout=None)
    if categorias:
        view.add_item(EditarCategoriaSelect(guild_id, user_id, categorias, guild=interaction.guild))
    view.add_item(VoltarParaCategoriasButton(guild_id, user_id, custom_id="btn_editar_categoria_voltar"))

    if is_edit:
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# =====================================================================
# PAINEL PÚBLICO DE TICKETS (/set painel)
# =====================================================================

_handled_public_interactions: List[int] = []


def format_ticket_welcome_text(
    user_mention: str,
    cat_nome: str,
    atendente_text: str,
    data_criacao: str,
    horario_criacao: str,
) -> str:
    """Retorna o texto padronizado do painel enviado dentro do tópico do ticket."""
    emoji_member = EmojiManager.get("member", fallback="<:member:1561907903688876064>")
    emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")
    emoji_rocket = EmojiManager.get("rocket", fallback="<:rocket:1561482854133669908>")
    emoji_calendar = EmojiManager.get("calendar", fallback="<:calendar:1561906133155708989>")
    emoji_clock = EmojiManager.get("clock", fallback="<:clock:1561906156593479740>")

    return (
        f"## {emoji_member} {cat_nome}  —  {user_mention}\n\n"
        f"> {emoji_info} Informe o que precisa com detalhes  para que nossa equipe consiga resolver seu caso.\n"
        f"> \n"
        f"> {emoji_member} Dono do ticket: {user_mention}\n"
        f"> {emoji_rocket} Atendente: {atendente_text}\n"
        f"> {emoji_calendar} Data de criação: {data_criacao}\n"
        f"> {emoji_clock} Horário de criação: {horario_criacao}"
    )


class TicketControlSelect(discord.ui.Select):
    """Select Menu de gerenciamento dentro do painel do tópico do ticket."""
    def __init__(self, thread_id: int, guild_id: int):
        self.thread_id = thread_id
        self.guild_id = guild_id
        options = [
            discord.SelectOption(
                label="Assumir",
                value="assumir",
                description="Assumir o atendimento deste ticket",
                emoji=resolve_partial_emoji("rocket", "🚀"),
            ),
            discord.SelectOption(
                label="Fechar ticket",
                value="fechar",
                description="Encerrar e fechar este ticket",
                emoji=resolve_partial_emoji("lock", "🔒"),
            ),
            discord.SelectOption(
                label="Puxar membro",
                value="puxar_membro",
                description="Dar acesso a um membro neste tópico",
                emoji=resolve_partial_emoji("member", "👤"),
            ),
            discord.SelectOption(
                label="Renomear",
                value="renomear",
                description="Mudar o nome do tópico deste ticket",
                emoji=resolve_partial_emoji("edit", "✏️"),
            ),
        ]
        super().__init__(
            placeholder="Gerenciar ticket...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_ticket_painel_acoes",
        )

    async def callback(self, interaction: discord.Interaction):
        await handle_ticket_panel_action(
            interaction,
            str(self.values[0]),
            self.guild_id or (interaction.guild_id or 0),
            self.thread_id or (interaction.channel_id or 0),
        )


class NotificarEquipeButton(discord.ui.Button):
    """Botão para quem abriu o ticket notificar todos os cargos permitidos."""
    def __init__(self, thread_id: int, guild_id: int):
        super().__init__(
            label="Notificar equipe",
            emoji=resolve_partial_emoji("announcement", None),
            style=discord.ButtonStyle.secondary,
            custom_id="btn_ticket_notificar_equipe",
            row=1,
        )
        self.thread_id = thread_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        await handle_ticket_notify_staff(
            interaction,
            self.guild_id or (interaction.guild_id or 0),
            self.thread_id or (interaction.channel_id or 0),
        )


class SairAtendimentoButton(discord.ui.Button):
    """Botão para quem abriu o ticket sair forçado do tópico."""
    def __init__(self, thread_id: int, guild_id: int):
        super().__init__(
            label="Sair do atendimento",
            emoji=resolve_partial_emoji("back", None),
            style=discord.ButtonStyle.danger,
            custom_id="btn_ticket_sair_atendimento",
            row=1,
        )
        self.thread_id = thread_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        await handle_ticket_leave_opener(
            interaction,
            self.guild_id or (interaction.guild_id or 0),
            self.thread_id or (interaction.channel_id or 0),
        )


def build_v2_ticket_welcome_layout(
    user_mention: str,
    cat_nome: str,
    atendente_text: str,
    data_criacao: str,
    horario_criacao: str,
    accent_color: int,
    thread_id: int = 0,
    guild_id: int = 0,
):
    """Constrói o painel inicial em Components V2 dentro do tópico privado do ticket com Select Menu + 2 botões."""
    if not HAS_COMPONENTS_V2:
        return None
    try:
        text = format_ticket_welcome_text(
            user_mention=user_mention,
            cat_nome=cat_nome,
            atendente_text=atendente_text,
            data_criacao=data_criacao,
            horario_criacao=horario_criacao,
        )
        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = (
            discord.ui.Separator(visible=True)
            if spacing_arg is None
            else discord.ui.Separator(visible=True, spacing=spacing_arg)
        )
        layout_view = discord.ui.LayoutView(timeout=None)
        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            separator,
            discord.ui.ActionRow(TicketControlSelect(thread_id=thread_id, guild_id=guild_id)),
            discord.ui.ActionRow(
                NotificarEquipeButton(thread_id=thread_id, guild_id=guild_id),
                SairAtendimentoButton(thread_id=thread_id, guild_id=guild_id),
            ),
            accent_colour=accent_color
        )
        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Erro ao instanciar LayoutView v2 de boas-vindas do ticket: {e}")
        return None


class PuxarMembroUserSelect(discord.ui.UserSelect):
    """User Select Menu em Components V2 para adicionar membros ao tópico privado."""
    def __init__(self, thread_id: int, guild_id: int, accent_color: int):
        self.thread_id = thread_id
        self.guild_id = guild_id
        self.accent_color = accent_color
        super().__init__(
            placeholder="Selecione o(s) membro(s) para puxar...",
            min_values=1,
            max_values=5,
            custom_id=f"select_ticket_puxar_membro_{thread_id}",
        )

    async def callback(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        thread = interaction.channel
        if thread is None or getattr(thread, "id", 0) != self.thread_id:
            try:
                thread = await interaction.client.fetch_channel(self.thread_id)
            except Exception:
                thread = interaction.channel

        if thread is None or not hasattr(thread, "add_user"):
            await interaction.edit_original_response(content=f"{EmojiManager.get('wrong')} Não foi possível acessar este tópico.")
            return

        added_mentions: List[str] = []
        added_ids_log: List[str] = []
        failed_names: List[str] = []
        for user_obj in self.values:
            try:
                await thread.add_user(user_obj)
                added_mentions.append(user_obj.mention)
                added_ids_log.append(f"{user_obj} ({user_obj.id})")
            except Exception as e:
                logger.warning(f"Erro ao puxar {user_obj} para o tópico {self.thread_id}: {e}")
                failed_names.append(getattr(user_obj, "display_name", str(user_obj)))

        if added_ids_log:
            gid_str = str(self.guild_id or interaction.guild_id or "direct")
            cfg_p = CloudStorage.get_guild_config(gid_str)
            t_data = cfg_p.get("tickets_ativos", {}).get(str(self.thread_id))
            if isinstance(t_data, dict):
                prev_added = t_data.setdefault("added_members", [])
                for entry in added_ids_log:
                    if entry not in prev_added:
                        prev_added.append(entry)
                await CloudStorage.save_guild_config(gid_str, cfg_p)

        emoji_correto = _sys_emoji("correto")
        emoji_member = _sys_emoji("member")
        emoji_warn = _sys_emoji("warn")
        result_lines: List[str] = []
        if added_mentions:
            result_lines.append(
                f"{emoji_correto} Membro(s) adicionado(s) ao tópico: {', '.join(added_mentions)}"
            )
            notice_txt = f"{emoji_member} {', '.join(added_mentions)} foi adicionado(a) ao ticket por {interaction.user.mention}."
            try:
                if HAS_COMPONENTS_V2:
                    n_view = discord.ui.LayoutView(timeout=None)
                    n_view.add_item(discord.ui.Container(discord.ui.TextDisplay(notice_txt), accent_colour=self.accent_color))
                    await thread.send(view=n_view)
                else:
                    await thread.send(notice_txt)
            except Exception:
                pass
        if failed_names:
            result_lines.append(f"{emoji_warn} Não foi possível adicionar: {', '.join(failed_names)}")

        final_msg = "\n".join(result_lines) or f"{EmojiManager.get('wrong')} Nenhum membro foi adicionado."
        if HAS_COMPONENTS_V2:
            try:
                done_view = discord.ui.LayoutView(timeout=None)
                done_view.add_item(
                    discord.ui.Container(discord.ui.TextDisplay(final_msg), accent_colour=self.accent_color)
                )
                await interaction.edit_original_response(view=done_view)
                return
            except Exception:
                pass
        await interaction.edit_original_response(content=final_msg, view=None)


def build_v2_puxar_membro_layout(thread_id: int, guild_id: int, accent_color: int):
    """Constrói o painel efêmero em Components V2 para puxar membro ao tópico."""
    if not HAS_COMPONENTS_V2:
        return None
    try:
        emoji_member = EmojiManager.get("member", fallback="<:member:1561907903688876064>")
        emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")
        text = (
            f"## {emoji_member} Puxar membro\n\n"
            f"> {emoji_info} Selecione no menu abaixo quem você deseja adicionar a este ticket."
        )
        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = (
            discord.ui.Separator(visible=True)
            if spacing_arg is None
            else discord.ui.Separator(visible=True, spacing=spacing_arg)
        )
        layout_view = discord.ui.LayoutView(timeout=None)
        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            separator,
            discord.ui.ActionRow(PuxarMembroUserSelect(thread_id, guild_id, accent_color)),
            accent_colour=accent_color
        )
        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Erro ao instanciar LayoutView v2 de puxar membro: {e}")
        return None


class RenomearTicketModal(discord.ui.Modal, title="Renomear Ticket"):
    """Modal para alterar o nome do tópico do ticket."""
    novo_nome_input = discord.ui.TextInput(
        label="Novo nome do tópico",
        placeholder="Ex: suporte-resolvido",
        min_length=1,
        max_length=100,
        required=True,
    )

    def __init__(self, thread_id: int, guild_id: int, current_name: str = "", accent_color: int = config.EMBED_COLOR_DEFAULT):
        super().__init__(title="Renomear Ticket")
        self.thread_id = thread_id
        self.guild_id = guild_id
        self.accent_color = accent_color
        if current_name:
            self.novo_nome_input.default = current_name[:100]

    async def on_submit(self, interaction: discord.Interaction):
        novo_nome = (self.novo_nome_input.value or "").strip()[:100]
        if not novo_nome:
            await interaction.response.send_message(f"{EmojiManager.get('wrong')} Informe um nome válido para o tópico.", ephemeral=True)
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        thread = interaction.channel
        if thread is None or getattr(thread, "id", 0) != self.thread_id:
            try:
                thread = await interaction.client.fetch_channel(self.thread_id)
            except Exception:
                thread = interaction.channel

        if thread is None or not hasattr(thread, "edit"):
            await interaction.followup.send(f"{EmojiManager.get('wrong')} Não foi possível acessar o tópico.", ephemeral=True)
            return

        old_name = getattr(thread, "name", "") or f"ticket-{self.thread_id}"
        try:
            await thread.edit(name=novo_nome, reason=f"Ticket renomeado por {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send(f"{_sys_emoji('wrong')} Não tenho permissão para renomear este tópico.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"{_sys_emoji('wrong')} Não foi possível renomear o tópico agora: {e}", ephemeral=True)
            return

        gid_str = str(self.guild_id or interaction.guild_id or "direct")
        cfg_r = CloudStorage.get_guild_config(gid_str)
        t_data = cfg_r.get("tickets_ativos", {}).get(str(self.thread_id))
        if isinstance(t_data, dict):
            brt_tz = timezone(timedelta(hours=-3))
            now_brt = datetime.now(brt_tz)
            t_data["thread_name"] = novo_nome
            t_data.setdefault("renamed_history", []).append({
                "de": old_name,
                "para": novo_nome,
                "por": str(interaction.user.id),
                "em": now_brt.strftime("%d/%m/%Y às %H:%M"),
            })
            await CloudStorage.save_guild_config(gid_str, cfg_r)

        emoji_edit = _sys_emoji("edit")
        thread_notice = f"{emoji_edit} O tópico foi renomeado para **{novo_nome}** por {interaction.user.mention}."
        try:
            if HAS_COMPONENTS_V2:
                ren_view = discord.ui.LayoutView(timeout=None)
                ren_view.add_item(discord.ui.Container(discord.ui.TextDisplay(thread_notice), accent_colour=self.accent_color))
                await thread.send(view=ren_view, allowed_mentions=discord.AllowedMentions.none())
            else:
                await thread.send(thread_notice, allowed_mentions=discord.AllowedMentions.none())
        except Exception:
            pass

        emoji_correto = _sys_emoji("correto")
        msg_txt = f"{emoji_correto} Tópico renomeado para **{novo_nome}**!"
        if HAS_COMPONENTS_V2:
            try:
                done_view = discord.ui.LayoutView(timeout=None)
                done_view.add_item(
                    discord.ui.Container(discord.ui.TextDisplay(msg_txt), accent_colour=self.accent_color)
                )
                await interaction.followup.send(view=done_view, ephemeral=True)
                return
            except Exception:
                pass
        await interaction.followup.send(content=msg_txt, ephemeral=True)


async def _reset_ticket_panel_select(
    message: Optional[discord.Message],
    ticket_data: Dict[str, Any],
    accent_color: int,
    guild_id: int,
    thread_id: int,
) -> None:
    """Re-renderiza o painel do tópico para resetar a seleção do Select Menu."""
    if message is None:
        return
    try:
        assumed_by = ticket_data.get("assumed_by_id")
        atendente_text = f"<@{assumed_by}>" if assumed_by else "Não assumido"
        owner_id = ticket_data.get("owner_id")
        user_mention = f"<@{owner_id}>" if owner_id else "Membro"
        cat_nome = ticket_data.get("category_name") or "Atendimento"
        data_criacao = ticket_data.get("data_criacao") or "--/--/----"
        horario_criacao = ticket_data.get("horario_criacao") or "--:--"

        v2 = build_v2_ticket_welcome_layout(
            user_mention=user_mention,
            cat_nome=cat_nome,
            atendente_text=atendente_text,
            data_criacao=data_criacao,
            horario_criacao=horario_criacao,
            accent_color=accent_color,
            thread_id=thread_id,
            guild_id=guild_id,
        )
        if v2 is not None:
            await message.edit(view=v2, allowed_mentions=discord.AllowedMentions(users=True, roles=False))
        else:
            fallback_txt = format_ticket_welcome_text(
                user_mention=user_mention,
                cat_nome=cat_nome,
                atendente_text=atendente_text,
                data_criacao=data_criacao,
                horario_criacao=horario_criacao,
            )
            fb_view = discord.ui.View(timeout=None)
            fb_view.add_item(TicketControlSelect(thread_id=thread_id, guild_id=guild_id))
            fb_view.add_item(NotificarEquipeButton(thread_id=thread_id, guild_id=guild_id))
            fb_view.add_item(SairAtendimentoButton(thread_id=thread_id, guild_id=guild_id))
            await message.edit(embed=discord.Embed(description=fallback_txt, color=accent_color), view=fb_view)
    except Exception as e:
        logger.debug(f"Aviso ao resetar Select Menu do ticket {thread_id}: {e}")


def _is_unknown_interaction(exc: Exception) -> bool:
    """Retorna True se a exceção for 10062 Unknown interaction (outra réplica respondeu antes)."""
    return isinstance(exc, discord.NotFound) and getattr(exc, "code", None) == 10062


def _extract_text_from_message(msg: Optional[discord.Message]) -> str:
    """Extrai todo o texto de um painel de ticket (Components V2 TextDisplay ou Embed description)."""
    if msg is None:
        return ""
    texts: List[str] = []

    def _walk(node: Any) -> None:
        if node is None:
            return
        if isinstance(node, dict):
            c = node.get("content")
            if isinstance(c, str) and c.strip():
                texts.append(c)
            if "component" in node:
                _walk(node.get("component"))
            for child in (node.get("components") or []):
                _walk(child)
            return
        c = getattr(node, "content", None)
        if isinstance(c, str) and c.strip():
            texts.append(c)
        if hasattr(node, "component"):
            _walk(getattr(node, "component", None))
        for attr in ("children", "components"):
            sub = getattr(node, attr, None)
            if sub:
                for child in sub:
                    _walk(child)

    for comp in (getattr(msg, "components", None) or []):
        _walk(comp)
    for emb in (getattr(msg, "embeds", None) or []):
        desc = getattr(emb, "description", None)
        if isinstance(desc, str) and desc.strip():
            texts.append(desc)
    return "\n".join(texts)


def _recover_ticket_from_message(
    msg: Optional[discord.Message],
    channel: Any,
    cfg: Dict[str, Any],
    tid_int: int,
) -> Optional[Dict[str, Any]]:
    """Reconstrói os dados do ticket em 0ms a partir do painel enviado no tópico caso falte no cache local."""
    full_text = _extract_text_from_message(msg)
    if not full_text:
        return None

    m_owner = re.search(r"Dono do ticket:\s*<@!?(\d+)>", full_text)
    if not m_owner:
        m_owner = re.search(r"—\s*<@!?(\d+)>", full_text)
    if not m_owner:
        return None

    owner_id = m_owner.group(1)
    m_att = re.search(r"Atendente:\s*<@!?(\d+)>", full_text)
    assumed_by_id = m_att.group(1) if m_att else None

    m_cat = re.search(r"##\s+(?:<a?:[a-zA-Z0-9_]+:\d+>\s*)?(.+?)\s+—\s+<@!?\d+>", full_text)
    cat_nome = m_cat.group(1).strip() if m_cat else "Atendimento"

    m_data = re.search(r"Data de criação:\s*(\d{2}/\d{2}/\d{4})", full_text)
    data_criacao = m_data.group(1) if m_data else "--/--/----"

    m_hora = re.search(r"Horário de criação:\s*(\d{2}:\d{2})", full_text)
    horario_criacao = m_hora.group(1) if m_hora else "--:--"

    category_id = ""
    allowed_role_ids: List[str] = []
    for cat in (cfg.get("categorias_ticket") or []):
        if (cat.get("nome") or "").strip().lower() == cat_nome.lower():
            category_id = str(cat.get("id") or "")
            allowed_role_ids = [str(r) for r in (cat.get("cargos_permitidos_ids") or []) if str(r).isdigit()]
            break
    if not allowed_role_ids:
        allowed_role_ids = [str(r) for r in (cfg.get("cargos", {}).get("cargos_permitidos_ids") or []) if str(r).isdigit()]

    created_ts: Optional[int] = None
    ch_created = getattr(channel, "created_at", None)
    if ch_created is not None:
        try:
            created_ts = int(ch_created.timestamp())
        except Exception:
            created_ts = None

    reconstructed: Dict[str, Any] = {
        "thread_id": str(tid_int),
        "thread_name": getattr(channel, "name", None) or f"ticket-{tid_int}",
        "message_id": str(getattr(msg, "id", "")) if msg is not None else None,
        "owner_id": str(owner_id),
        "category_id": category_id,
        "category_name": cat_nome,
        "allowed_role_ids": allowed_role_ids,
        "assumed_by_id": assumed_by_id,
        "data_criacao": data_criacao,
        "horario_criacao": horario_criacao,
        "created_at_ts": created_ts,
        "added_members": [],
        "renamed_history": [],
        "opener_left": False,
    }
    tickets_ativos = cfg.setdefault("tickets_ativos", {})
    tickets_ativos[str(tid_int)] = reconstructed
    logger.info(f"Dados do ticket {tid_int} reconstruídos automaticamente a partir da mensagem do painel.")
    return reconstructed


async def _get_or_recover_ticket_data(
    interaction: discord.Interaction,
    cfg: Dict[str, Any],
    tid_int: int,
    allow_cloud_fetch: bool = True,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """Busca dados do ticket no cache local, na mensagem do painel (0ms) ou no Hugging Face Dataset."""
    tid_str = str(tid_int)
    tickets_ativos = cfg.setdefault("tickets_ativos", {})
    ticket_data = tickets_ativos.get(tid_str)
    if isinstance(ticket_data, dict):
        return cfg, ticket_data

    # 1. Tenta reconstrução instantânea (0ms) pela mensagem do painel que originou a interação
    recovered = _recover_ticket_from_message(interaction.message, interaction.channel, cfg, tid_int)
    if isinstance(recovered, dict):
        return cfg, recovered

    # 2. Fallback: força atualização imediata a partir do HF Dataset (caso outra réplica tenha salvo)
    if allow_cloud_fetch:
        await CloudStorage.force_refresh_from_hf()
        gid_str = str(interaction.guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        tickets_ativos = cfg.setdefault("tickets_ativos", {})
        ticket_data = tickets_ativos.get(tid_str)
        if isinstance(ticket_data, dict):
            return cfg, ticket_data

    return cfg, None


_handled_ticket_action_interactions: List[int] = []


async def handle_ticket_notify_staff(
    interaction: discord.Interaction,
    guild_id: int = 0,
    thread_id: int = 0,
) -> None:
    """Notifica todos os cargos permitidos do ticket (exclusivo para quem abriu o ticket)."""
    if interaction.id in _handled_ticket_action_interactions:
        return
    _handled_ticket_action_interactions.append(interaction.id)
    if len(_handled_ticket_action_interactions) > 200:
        del _handled_ticket_action_interactions[:100]

    gid_int = guild_id or (interaction.guild_id or 0)
    gid_str = str(gid_int or "direct")
    tid_int = thread_id or (interaction.channel_id or 0)
    tid_str = str(tid_int)

    cfg = CloudStorage.get_guild_config(gid_str)
    cfg, ticket_data = await _get_or_recover_ticket_data(interaction, cfg, tid_int, allow_cloud_fetch=True)
    if not isinstance(ticket_data, dict):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"{_sys_emoji('warn')} Os dados deste ticket não foram encontrados no sistema.",
                    ephemeral=True
                )
        except Exception:
            pass
        return

    owner_id = str(ticket_data.get("owner_id") or "")
    if str(interaction.user.id) != owner_id:
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"{_sys_emoji('wrong')} Apenas quem abriu este ticket pode usar o botão **Notificar equipe**.",
                    ephemeral=True
                )
        except Exception:
            pass
        return

    allowed_ids = [str(r) for r in (ticket_data.get("allowed_role_ids") or []) if str(r).isdigit()]
    if not allowed_ids:
        allowed_ids = [str(r) for r in (cfg.get("cargos", {}).get("cargos_permitidos_ids") or []) if str(r).isdigit()]

    if not allowed_ids:
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"{_sys_emoji('warn')} Nenhum cargo de equipe configurado para notificar neste ticket.",
                    ephemeral=True
                )
        except Exception:
            pass
        return

    if not interaction.response.is_done():
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.NotFound as e:
            if _is_unknown_interaction(e):
                return
            raise

    thread = interaction.channel
    if thread is None or getattr(thread, "id", 0) != tid_int:
        try:
            thread = await interaction.client.fetch_channel(tid_int)
        except Exception:
            thread = interaction.channel

    if thread is None:
        await interaction.followup.send(f"{EmojiManager.get('wrong')} Não foi possível acessar este tópico.", ephemeral=True)
        return

    roles_mention = " ".join(f"<@&{rid}>" for rid in allowed_ids)
    emoji_announcement = _sys_emoji("announcement")
    emoji_correto = _sys_emoji("correto")
    painel_cfg = cfg.get("painel", {})
    app = _get_configured_appearance(painel_cfg)
    accent_color = app["cor"] if app["cor"] is not None else config.EMBED_COLOR_DEFAULT

    notify_msg = f"{emoji_announcement} {interaction.user.mention} notificou a equipe sobre este atendimento: {roles_mention}"
    allowed_mentions = discord.AllowedMentions(roles=True, users=True)
    try:
        if HAS_COMPONENTS_V2:
            notify_view = discord.ui.LayoutView(timeout=None)
            notify_view.add_item(
                discord.ui.Container(discord.ui.TextDisplay(notify_msg), accent_colour=accent_color)
            )
            await thread.send(view=notify_view, allowed_mentions=allowed_mentions)
        else:
            await thread.send(content=notify_msg, allowed_mentions=allowed_mentions)
    except Exception as e:
        logger.warning(f"Erro ao notificar equipe no tópico {tid_int}: {e}")
        await interaction.followup.send(f"{EmojiManager.get('wrong')} Erro ao notificar a equipe: {e}", ephemeral=True)
        return

    await interaction.followup.send(
        f"{emoji_correto} A equipe foi notificada sobre o seu ticket!",
        ephemeral=True
    )


async def handle_ticket_leave_opener(
    interaction: discord.Interaction,
    guild_id: int = 0,
    thread_id: int = 0,
) -> None:
    """Remove o autor do ticket forçadamente do tópico privado (exclusivo para quem abriu)."""
    if interaction.id in _handled_ticket_action_interactions:
        return
    _handled_ticket_action_interactions.append(interaction.id)
    if len(_handled_ticket_action_interactions) > 200:
        del _handled_ticket_action_interactions[:100]

    gid_int = guild_id or (interaction.guild_id or 0)
    gid_str = str(gid_int or "direct")
    tid_int = thread_id or (interaction.channel_id or 0)
    tid_str = str(tid_int)

    cfg = CloudStorage.get_guild_config(gid_str)
    cfg, ticket_data = await _get_or_recover_ticket_data(interaction, cfg, tid_int, allow_cloud_fetch=True)
    if not isinstance(ticket_data, dict):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"{_sys_emoji('warn')} Os dados deste ticket não foram encontrados no sistema.",
                    ephemeral=True
                )
        except Exception:
            pass
        return

    owner_id = str(ticket_data.get("owner_id") or "")
    if str(interaction.user.id) != owner_id:
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"{_sys_emoji('wrong')} Apenas quem abriu este ticket pode usar o botão **Sair do atendimento**.",
                    ephemeral=True
                )
        except Exception:
            pass
        return

    thread = interaction.channel
    if thread is None or getattr(thread, "id", 0) != tid_int:
        try:
            thread = await interaction.client.fetch_channel(tid_int)
        except Exception:
            thread = interaction.channel

    if thread is None or not hasattr(thread, "remove_user"):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"{_sys_emoji('wrong')} Não foi possível acessar este tópico.", ephemeral=True)
        except Exception:
            pass
        return

    emoji_back = _sys_emoji("back")
    emoji_member = _sys_emoji("member")
    painel_cfg = cfg.get("painel", {})
    app = _get_configured_appearance(painel_cfg)
    accent_color = app["cor"] if app["cor"] is not None else config.EMBED_COLOR_DEFAULT

    if not interaction.response.is_done():
        try:
            await interaction.response.send_message(
                f"{emoji_back} Você saiu do atendimento.",
                ephemeral=True
            )
        except discord.NotFound as e:
            if _is_unknown_interaction(e):
                return
            raise

    brt_tz = timezone(timedelta(hours=-3))
    now_brt = datetime.now(brt_tz)
    ticket_data["opener_left"] = True
    ticket_data["opener_left_at"] = now_brt.strftime("%d/%m/%Y às %H:%M")
    await CloudStorage.save_guild_config(gid_str, cfg)

    leave_txt = f"{emoji_member} {interaction.user.mention} saiu do atendimento."
    try:
        if HAS_COMPONENTS_V2:
            leave_view = discord.ui.LayoutView(timeout=None)
            leave_view.add_item(
                discord.ui.Container(discord.ui.TextDisplay(leave_txt), accent_colour=accent_color)
            )
            await thread.send(view=leave_view)
        else:
            await thread.send(content=leave_txt)
    except Exception:
        pass

    try:
        await thread.remove_user(interaction.user)
        logger.info(f"Autor {interaction.user} saiu do atendimento no tópico {tid_int}")
    except discord.Forbidden:
        try:
            await interaction.followup.send(
                f"{EmojiManager.get('wrong')} Não tenho permissão para remover você deste tópico.",
                ephemeral=True
            )
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"Erro ao remover usuário {interaction.user} do tópico {tid_int}: {e}")


async def handle_ticket_panel_action(
    interaction: discord.Interaction,
    action: str,
    guild_id: int = 0,
    thread_id: int = 0,
) -> None:
    """Processa as 4 ações do Select Menu no painel do tópico (funciona também após reinícios)."""
    if interaction.id in _handled_ticket_action_interactions:
        return
    _handled_ticket_action_interactions.append(interaction.id)
    if len(_handled_ticket_action_interactions) > 200:
        del _handled_ticket_action_interactions[:100]

    gid_int = guild_id or (interaction.guild_id or 0)
    gid_str = str(gid_int or "direct")
    tid_int = thread_id or (interaction.channel_id or 0)
    tid_str = str(tid_int)

    cfg = CloudStorage.get_guild_config(gid_str)
    # Modal ("renomear") não pode fazer defer nem demorar >3s; para ele, fazemos recuperação em 0ms pela mensagem
    cfg, ticket_data = await _get_or_recover_ticket_data(
        interaction,
        cfg,
        tid_int,
        allow_cloud_fetch=(action != "renomear"),
    )
    tickets_ativos = cfg.setdefault("tickets_ativos", {})

    if not isinstance(ticket_data, dict):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"{_sys_emoji('warn')} Os dados deste ticket não foram encontrados no sistema.",
                    ephemeral=True
                )
        except Exception:
            pass
        return

    # Verifica se o usuário possui algum cargo permitido da categoria (ou fallback global) ou é Administrador
    allowed_ids = [str(r) for r in (ticket_data.get("allowed_role_ids") or []) if str(r).isdigit()]
    if not allowed_ids:
        allowed_ids = [str(r) for r in (cfg.get("cargos", {}).get("cargos_permitidos_ids") or []) if str(r).isdigit()]

    member_role_ids = {str(r.id) for r in getattr(interaction.user, "roles", [])}
    is_admin = bool(getattr(getattr(interaction.user, "guild_permissions", None), "administrator", False))
    has_allowed_role = bool(member_role_ids & set(allowed_ids))

    painel_cfg = cfg.get("painel", {})
    app = _get_configured_appearance(painel_cfg)
    accent_color = app["cor"] if app["cor"] is not None else config.EMBED_COLOR_DEFAULT

    if not has_allowed_role and not is_admin:
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message(
                    f"{_sys_emoji('wrong')} Apenas membros com cargo permitido podem usar as opções deste ticket.",
                    ephemeral=True
                )
            except discord.NotFound as e:
                if _is_unknown_interaction(e):
                    return
                raise
        asyncio.create_task(
            _reset_ticket_panel_select(interaction.message, ticket_data, accent_color, gid_int, tid_int)
        )
        return

    assumed_by_id = ticket_data.get("assumed_by_id")

    if action == "assumir":
        if assumed_by_id:
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        f"{_sys_emoji('warn')} Este ticket já foi assumido por <@{assumed_by_id}>.",
                        ephemeral=True
                    )
                except discord.NotFound as e:
                    if _is_unknown_interaction(e):
                        return
                    raise
            asyncio.create_task(
                _reset_ticket_panel_select(interaction.message, ticket_data, accent_color, gid_int, tid_int)
            )
            return

        brt_tz = timezone(timedelta(hours=-3))
        now_brt = datetime.now(brt_tz)
        data_assumido = now_brt.strftime("%d/%m/%Y")
        horario_assumido = now_brt.strftime("%H:%M")

        owner_id = ticket_data.get("owner_id")
        user_mention = f"<@{owner_id}>" if owner_id else "Membro"
        cat_nome = ticket_data.get("category_name") or "Atendimento"
        data_criacao = ticket_data.get("data_criacao") or "--/--/----"
        horario_criacao = ticket_data.get("horario_criacao") or "--:--"
        atendente_text = interaction.user.mention

        updated_v2 = build_v2_ticket_welcome_layout(
            user_mention=user_mention,
            cat_nome=cat_nome,
            atendente_text=atendente_text,
            data_criacao=data_criacao,
            horario_criacao=horario_criacao,
            accent_color=accent_color,
            thread_id=tid_int,
            guild_id=gid_int,
        )
        if not interaction.response.is_done():
            try:
                if updated_v2 is not None:
                    await interaction.response.edit_message(
                        view=updated_v2,
                        allowed_mentions=discord.AllowedMentions(users=True, roles=False)
                    )
                else:
                    fallback_txt = format_ticket_welcome_text(
                        user_mention=user_mention,
                        cat_nome=cat_nome,
                        atendente_text=atendente_text,
                        data_criacao=data_criacao,
                        horario_criacao=horario_criacao,
                    )
                    fb_view = discord.ui.View(timeout=None)
                    fb_view.add_item(TicketControlSelect(thread_id=tid_int, guild_id=gid_int))
                    fb_view.add_item(NotificarEquipeButton(thread_id=tid_int, guild_id=gid_int))
                    fb_view.add_item(SairAtendimentoButton(thread_id=tid_int, guild_id=gid_int))
                    await interaction.response.edit_message(
                        embed=discord.Embed(description=fallback_txt, color=accent_color),
                        view=fb_view
                    )
            except discord.NotFound as e:
                if _is_unknown_interaction(e):
                    return
                raise

        ticket_data["assumed_by_id"] = str(interaction.user.id)
        ticket_data["assumed_at_ts"] = int(now_brt.timestamp())
        ticket_data["data_assumido"] = data_assumido
        ticket_data["horario_assumido"] = horario_assumido
        await CloudStorage.save_guild_config(gid_str, cfg)

        emoji_correto = EmojiManager.get("correto", fallback="<:correto:1560996992006496367>")
        if EmojiManager.needs_remote_resolve(emoji_correto, guild=interaction.guild):
            emoji_correto = await EmojiManager.resolve_or_clone_emoji(
                emoji_correto, guild=interaction.guild, bot=interaction.client
            )
        await interaction.followup.send(
            f"{emoji_correto} Você assumiu este ticket!",
            ephemeral=True
        )

        # Log em Canal Logs de tickets assumidos se configurado
        thread_obj = interaction.channel
        if thread_obj is None or getattr(thread_obj, "id", 0) != tid_int:
            try:
                thread_obj = await interaction.client.fetch_channel(tid_int)
            except Exception:
                thread_obj = interaction.channel
        thread_ref = getattr(thread_obj, "mention", None) or f"<#{tid_int}>"
        thread_name_assumido = getattr(thread_obj, "name", None) or ticket_data.get("thread_name") or f"ticket-{tid_int}"
        owner_log_fmt = f"<@{owner_id}> (`{owner_id}`)" if owner_id else "Membro"
        await _send_ticket_log(
            guild=interaction.guild,
            client=interaction.client,
            cfg=cfg,
            log_key="canal_assumidos_id",
            title="Ticket Assumido",
            title_emoji_key="rocket",
            lines=[
                f"> {_sys_emoji('rocket')} **Atendente:** {interaction.user.mention} (`{interaction.user.id}`)",
                f"> {_sys_emoji('member')} **Dono do ticket:** {owner_log_fmt}",
                f"> {_sys_emoji('folder')} **Categoria:** {cat_nome}",
                f"> {_sys_emoji('ban')} **Tópico:** {thread_ref} (`{thread_name_assumido}`)",
                f"> {_sys_emoji('calendar')} **Data:** {data_assumido}",
                f"> {_sys_emoji('clock')} **Horário:** {horario_assumido}",
            ],
            accent_color=accent_color,
            jump_url=getattr(thread_obj, "jump_url", None),
        )
        return

    # Demais opções (fechar, puxar_membro, renomear) só podem ser usadas após assumir o ticket
    if not assumed_by_id:
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message(
                    f"{_sys_emoji('warn')} Você precisa **Assumir** o ticket primeiro para poder usar as demais opções.",
                    ephemeral=True
                )
            except discord.NotFound as e:
                if _is_unknown_interaction(e):
                    return
                raise
        asyncio.create_task(
            _reset_ticket_panel_select(interaction.message, ticket_data, accent_color, gid_int, tid_int)
        )
        return

    if str(interaction.user.id) != str(assumed_by_id):
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message(
                    f"{_sys_emoji('warn')} Apenas <@{assumed_by_id}> (quem assumiu este ticket) pode usar as demais opções.",
                    ephemeral=True
                )
            except discord.NotFound as e:
                if _is_unknown_interaction(e):
                    return
                raise
        asyncio.create_task(
            _reset_ticket_panel_select(interaction.message, ticket_data, accent_color, gid_int, tid_int)
        )
        return

    if action == "puxar_membro":
        puxar_v2 = build_v2_puxar_membro_layout(tid_int, gid_int, accent_color)
        if not interaction.response.is_done():
            try:
                if puxar_v2 is not None:
                    await interaction.response.send_message(view=puxar_v2, ephemeral=True)
                else:
                    fb_view = discord.ui.View(timeout=180)
                    fb_view.add_item(PuxarMembroUserSelect(tid_int, gid_int, accent_color))
                    await interaction.response.send_message(
                        "Selecione o(s) membro(s) para puxar para este tópico:",
                        view=fb_view,
                        ephemeral=True
                    )
            except discord.NotFound as e:
                if _is_unknown_interaction(e):
                    return
                raise
        asyncio.create_task(
            _reset_ticket_panel_select(interaction.message, ticket_data, accent_color, gid_int, tid_int)
        )
        return

    if action == "renomear":
        current_name = getattr(interaction.channel, "name", "") or ""
        if not interaction.response.is_done():
            try:
                await interaction.response.send_modal(
                    RenomearTicketModal(tid_int, gid_int, current_name=current_name, accent_color=accent_color)
                )
            except discord.NotFound as e:
                if _is_unknown_interaction(e):
                    return
                raise
        asyncio.create_task(
            _reset_ticket_panel_select(interaction.message, ticket_data, accent_color, gid_int, tid_int)
        )
        return

    if action == "fechar":
        if not interaction.response.is_done():
            try:
                await interaction.response.defer(ephemeral=True)
            except discord.NotFound as e:
                if _is_unknown_interaction(e):
                    return
                raise

        thread = interaction.channel
        if thread is None or getattr(thread, "id", 0) != tid_int:
            try:
                thread = await interaction.client.fetch_channel(tid_int)
            except Exception:
                thread = interaction.channel

        owner_id = ticket_data.get("owner_id")
        owner_log_fmt = f"<@{owner_id}> (`{owner_id}`)" if owner_id else "Membro"
        atendente_log_fmt = f"<@{assumed_by_id}> (`{assumed_by_id}`)" if assumed_by_id else "Não assumido"
        cat_nome = ticket_data.get("category_name") or "Atendimento"
        thread_name = getattr(thread, "name", None) or ticket_data.get("thread_name") or f"ticket-{tid_int}"
        data_criacao = ticket_data.get("data_criacao") or "--/--/----"
        horario_criacao = ticket_data.get("horario_criacao") or "--:--"

        brt_tz = timezone(timedelta(hours=-3))
        now_brt = datetime.now(brt_tz)
        data_fechamento = now_brt.strftime("%d/%m/%Y")
        horario_fechamento = now_brt.strftime("%H:%M")
        duracao_str = _format_ticket_duration(
            ticket_data.get("created_at_ts"),
            data_criacao=data_criacao,
            horario_criacao=horario_criacao,
            now_brt=now_brt,
        )

        transcript_bytes: Optional[bytes] = None
        transcript_filename: Optional[str] = None
        msg_count = 0
        if thread is not None and cfg.get("logs", {}).get("transcripts_ativo", True):
            transcript_bytes, transcript_filename, msg_count = await _build_ticket_transcript(
                thread=thread,
                ticket_data=ticket_data,
                closed_by=interaction.user,
                guild=interaction.guild,
                closed_at_brt=now_brt,
                duracao_str=duracao_str,
            )

        close_lines = [
            f"> {_sys_emoji('lock')} **Fechado por:** {interaction.user.mention} (`{interaction.user.id}`)",
            f"> {_sys_emoji('member')} **Dono do ticket:** {owner_log_fmt}",
            f"> {_sys_emoji('rocket')} **Atendente:** {atendente_log_fmt}",
            f"> {_sys_emoji('folder')} **Categoria:** {cat_nome}",
            f"> {_sys_emoji('ban')} **Tópico:** `{thread_name}`",
            f"> {_sys_emoji('calendar')} **Abertura:** {data_criacao} às {horario_criacao}",
            f"> {_sys_emoji('clock')} **Fechamento:** {data_fechamento} às {horario_fechamento}",
            f"> {_sys_emoji('time')} **Duração:** {duracao_str}",
            f"> {_sys_emoji('receipt')} **Mensagens registradas:** {msg_count}",
        ]
        if ticket_data.get("opener_left"):
            close_lines.append(
                f"> {_sys_emoji('back')} **Autor saiu antes do fechamento:** Sim ({ticket_data.get('opener_left_at') or 'registrado'})"
            )

        await _send_ticket_log(
            guild=interaction.guild,
            client=interaction.client,
            cfg=cfg,
            log_key="canal_fechados_id",
            title="Ticket Fechado",
            title_emoji_key="lock",
            lines=close_lines,
            accent_color=accent_color,
            transcript_bytes=transcript_bytes,
            transcript_filename=transcript_filename,
        )

        CloudStorage.mark_ticket_closed(gid_str, tid_str)
        tickets_ativos.pop(tid_str, None)
        await CloudStorage.save_guild_config(gid_str, cfg)

        emoji_lock = _sys_emoji("lock")
        await interaction.followup.send(
            f"{emoji_lock} Fechando este ticket...",
            ephemeral=True
        )
        if thread is not None:
            close_notice = f"{emoji_lock} Ticket encerrado por {interaction.user.mention}. O tópico será fechado em 3 segundos..."
            try:
                if HAS_COMPONENTS_V2:
                    c_view = discord.ui.LayoutView(timeout=None)
                    c_view.add_item(discord.ui.Container(discord.ui.TextDisplay(close_notice), accent_colour=accent_color))
                    await thread.send(view=c_view)
                else:
                    await thread.send(close_notice)
            except Exception:
                pass
            await asyncio.sleep(3)
            try:
                await thread.delete(reason=f"Ticket fechado por {interaction.user}")
            except discord.Forbidden:
                try:
                    await thread.edit(archived=True, locked=True, reason=f"Ticket fechado por {interaction.user}")
                except Exception as e:
                    logger.warning(f"Erro ao arquivar tópico {tid_int}: {e}")
            except Exception as e:
                logger.warning(f"Erro ao deletar tópico {tid_int}: {e}")


async def _reply_ephemeral_status(interaction: discord.Interaction, message: str) -> None:
    """Atualiza a mensagem efêmera inicial ('Criando ticket...') ou envia followup se necessário."""
    try:
        if interaction.response.is_done():
            await interaction.edit_original_response(content=message)
        else:
            await interaction.response.send_message(content=message, ephemeral=True)
    except Exception:
        try:
            await interaction.followup.send(content=message, ephemeral=True)
        except Exception:
            pass


async def handle_public_category_selection(interaction: discord.Interaction, selected_id: str, guild_id: int = 0) -> None:
    """Processa a seleção de categoria no painel público, mostra ':reload: Criando ticket...', cria o tópico privado e edita a mensagem."""
    if interaction.id in _handled_public_interactions:
        return
    _handled_public_interactions.append(interaction.id)
    if len(_handled_public_interactions) > 200:
        del _handled_public_interactions[:100]

    gid_int = guild_id or (interaction.guild_id or 0)
    gid_str = str(gid_int or "direct")
    cfg = CloudStorage.get_guild_config(gid_str)
    categorias = cfg.get("categorias_ticket", [])

    categoria_alvo = None
    for idx, cat in enumerate(categorias):
        cat_val = str(cat.get("id") or f"idx_{idx}")
        if cat_val == str(selected_id):
            categoria_alvo = cat
            break

    if categoria_alvo is None:
        await _reply_ephemeral_status(interaction, "Esta categoria não está mais disponível no painel.")
        return

    emoji_reload = EmojiManager.get("reload", fallback="<:reload:1561908806584115210>")
    if not interaction.response.is_done():
        try:
            await interaction.response.send_message(
                content=f"{emoji_reload} Criando ticket...",
                ephemeral=True
            )
        except discord.NotFound as e:
            if _is_unknown_interaction(e):
                logger.info(f"Interação de abertura {interaction.id} já tratada por outra instância; ignorando.")
                return
            raise

    cat_nome = (categoria_alvo.get("nome") or "Atendimento").strip()
    canal_topicos_id = categoria_alvo.get("canal_topicos_id")
    target_channel = None

    if canal_topicos_id and str(canal_topicos_id).isdigit():
        ch_id_int = int(canal_topicos_id)
        target_channel = (
            (interaction.guild.get_channel(ch_id_int) if interaction.guild else None)
            or interaction.client.get_channel(ch_id_int)
        )
        if target_channel is None:
            try:
                target_channel = await interaction.client.fetch_channel(ch_id_int)
            except Exception:
                target_channel = None

    if target_channel is None and isinstance(interaction.channel, discord.TextChannel):
        target_channel = interaction.channel

    if target_channel is None or not hasattr(target_channel, "create_thread"):
        await _reply_ephemeral_status(
            interaction,
            f"{EmojiManager.get('wrong')} Canal de tópicos não configurado ou inválido para esta categoria."
        )
        return

    safe_user = re.sub(r"[^a-zA-Z0-9_-]", "", interaction.user.name) or str(interaction.user.id)
    thread_name = f"🎫・{cat_nome}-{safe_user}"[:100]

    try:
        thread = await target_channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread,
            invitable=False,
            reason=f"Ticket aberto por {interaction.user} ({cat_nome})"
        )
    except discord.Forbidden:
        await _reply_ephemeral_status(
            interaction,
            f"{EmojiManager.get('wrong')} Não tenho permissão para criar tópicos privados em {target_channel.mention}."
        )
        return
    except Exception as e:
        logger.error(f"Erro ao criar tópico privado de ticket: {e}", exc_info=True)
        await _reply_ephemeral_status(
            interaction,
            f"{EmojiManager.get('wrong')} Não foi possível criar o tópico do ticket: {e}"
        )
        return

    try:
        await thread.add_user(interaction.user)
    except Exception as e:
        logger.warning(f"Aviso ao adicionar autor {interaction.user} no tópico {thread.id}: {e}")

    painel_cfg = cfg.get("painel", {})
    app = _get_configured_appearance(painel_cfg)
    accent_color = app["cor"] if app["cor"] is not None else config.EMBED_COLOR_DEFAULT

    cargos_ids = [str(rid) for rid in (categoria_alvo.get("cargos_permitidos_ids") or []) if str(rid).isdigit()]
    brt_tz = timezone(timedelta(hours=-3))
    now_brt = datetime.now(brt_tz)
    data_criacao = now_brt.strftime("%d/%m/%Y")
    horario_criacao = now_brt.strftime("%H:%M")
    atendente_text = "Não assumido"

    allowed_mentions = discord.AllowedMentions(users=True, roles=False)
    welcome_v2 = build_v2_ticket_welcome_layout(
        user_mention=interaction.user.mention,
        cat_nome=cat_nome,
        atendente_text=atendente_text,
        data_criacao=data_criacao,
        horario_criacao=horario_criacao,
        accent_color=accent_color,
        thread_id=thread.id,
        guild_id=gid_int,
    )
    panel_msg = None
    try:
        if welcome_v2 is not None:
            panel_msg = await thread.send(view=welcome_v2, allowed_mentions=allowed_mentions)
        else:
            fallback_txt = format_ticket_welcome_text(
                user_mention=interaction.user.mention,
                cat_nome=cat_nome,
                atendente_text=atendente_text,
                data_criacao=data_criacao,
                horario_criacao=horario_criacao,
            )
            fb_view = discord.ui.View(timeout=None)
            fb_view.add_item(TicketControlSelect(thread_id=thread.id, guild_id=gid_int))
            fb_view.add_item(NotificarEquipeButton(thread_id=thread.id, guild_id=gid_int))
            fb_view.add_item(SairAtendimentoButton(thread_id=thread.id, guild_id=gid_int))
            panel_msg = await thread.send(
                embed=discord.Embed(description=fallback_txt, color=accent_color),
                view=fb_view,
                allowed_mentions=allowed_mentions
            )
    except Exception as e:
        logger.warning(f"Aviso ao enviar mensagem inicial no tópico {thread.id}: {e}")

    # Salva estado do ticket ativo para persistir após reinícios
    tickets_ativos = cfg.setdefault("tickets_ativos", {})
    tickets_ativos[str(thread.id)] = {
        "thread_id": str(thread.id),
        "thread_name": thread.name,
        "message_id": str(panel_msg.id) if panel_msg else None,
        "owner_id": str(interaction.user.id),
        "category_id": str(categoria_alvo.get("id") or ""),
        "category_name": cat_nome,
        "allowed_role_ids": cargos_ids,
        "assumed_by_id": None,
        "data_criacao": data_criacao,
        "horario_criacao": horario_criacao,
        "created_at_ts": int(now_brt.timestamp()),
        "added_members": [],
        "renamed_history": [],
        "opener_left": False,
    }
    await CloudStorage.save_guild_config(gid_str, cfg)

    # Adiciona membros dos cargos permitidos ao tópico privado sem sujar o chat
    if interaction.guild and cargos_ids:
        added_ids = {interaction.user.id}
        for rid in cargos_ids:
            role_obj = interaction.guild.get_role(int(rid))
            if not role_obj:
                continue
            for member in role_obj.members:
                if member.bot or member.id in added_ids:
                    continue
                added_ids.add(member.id)
                try:
                    await thread.add_user(member)
                except Exception:
                    pass

    # Log em Canal Logs de tickets abertos se configurado
    await _send_ticket_log(
        guild=interaction.guild,
        client=interaction.client,
        cfg=cfg,
        log_key="canal_abertos_id",
        title="Ticket Aberto",
        title_emoji_key="ticket",
        lines=[
            f"> {_sys_emoji('member')} **Dono do ticket:** {interaction.user.mention} (`{interaction.user.id}`)",
            f"> {_sys_emoji('folder')} **Categoria:** {cat_nome}",
            f"> {_sys_emoji('ban')} **Tópico:** {thread.mention} (`{thread.name}`)",
            f"> {_sys_emoji('calendar')} **Data de criação:** {data_criacao}",
            f"> {_sys_emoji('clock')} **Horário de criação:** {horario_criacao}",
        ],
        accent_color=accent_color,
        jump_url=getattr(thread, "jump_url", None),
    )

    # Resolve/clona emojis de confirmação se necessário para exibição garantida
    emoji_correto = EmojiManager.get("correto", fallback="<:correto:1560996992006496367>")
    emoji_ban = EmojiManager.get("ban", fallback="<:ban:1561906116030505050>")
    if EmojiManager.needs_remote_resolve(emoji_correto, guild=interaction.guild):
        emoji_correto = await EmojiManager.resolve_or_clone_emoji(
            emoji_correto, guild=interaction.guild, bot=interaction.client
        )
    if EmojiManager.needs_remote_resolve(emoji_ban, guild=interaction.guild):
        emoji_ban = await EmojiManager.resolve_or_clone_emoji(
            emoji_ban, guild=interaction.guild, bot=interaction.client
        )

    logger.info(
        f"Ticket aberto por {interaction.user} na categoria '{cat_nome}' -> tópico {thread.name} ({thread.id}) na guilda {gid_str}"
    )

    await _reply_ephemeral_status(
        interaction,
        f"{emoji_correto} Seu ticket foi criado com sucesso!\n{emoji_ban} {thread.mention}"
    )


class PublicTicketCategorySelect(discord.ui.Select):
    """Select Menu público exibido no painel de tickets contendo apenas as categorias configuradas."""
    def __init__(self, guild_id: int, categorias: List[Dict[str, Any]], guild=None):
        self.guild_id = guild_id
        options = []
        for idx, cat in enumerate(categorias[:25]):
            nome = (cat.get("nome") or f"Categoria {idx + 1}").strip()[:100]
            desc_raw = (cat.get("descricao") or "").strip()
            desc = desc_raw[:100] if desc_raw else None
            val = str(cat.get("id") or f"idx_{idx}")[:100]
            raw_emoji = (cat.get("emoji") or "").strip()
            opt_emoji = resolve_category_emoji(raw_emoji, "folder", "📁", guild=guild) if raw_emoji else None
            options.append(
                discord.SelectOption(
                    label=nome,
                    value=val,
                    description=desc,
                    emoji=opt_emoji
                )
            )

        super().__init__(
            placeholder="Selecione uma categoria...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_ticket_abrir_categoria"
        )

    async def callback(self, interaction: discord.Interaction):
        await handle_public_category_selection(
            interaction,
            self.values[0],
            self.guild_id or (interaction.guild_id or 0)
        )


def build_v2_public_ticket_layout(guild_id: int, guild=None):
    """
    Constrói o painel público de tickets em Componentes V2 contendo EXCLUSIVAMENTE
    o que foi configurado na Aparência (/configurar painel) e o Select Menu de categorias.
    """
    if not HAS_COMPONENTS_V2:
        return None

    try:
        gid_str = str(guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        painel_cfg = cfg.get("painel", {})
        app = _get_configured_appearance(painel_cfg)
        categorias = cfg.get("categorias_ticket", [])
        if not categorias:
            return None

        container_items: List[Any] = []
        text_parts: List[str] = []
        titulo_vis = EmojiManager.replace_known_text_emojis(app["titulo"], guild=guild) if app["titulo"] else None
        desc_vis = EmojiManager.replace_known_text_emojis(app["descricao"], guild=guild) if app["descricao"] else None
        if titulo_vis:
            text_parts.append(f"## {titulo_vis}")
        if desc_vis:
            text_parts.append(desc_vis)

        has_section = hasattr(discord.ui, "Section") and hasattr(discord.ui, "Thumbnail")
        has_gallery = hasattr(discord.ui, "MediaGallery") and hasattr(discord, "MediaGalleryItem")

        if text_parts:
            text_display = discord.ui.TextDisplay("\n\n".join(text_parts))
            if app["thumbnail_url"] and has_section:
                container_items.append(
                    discord.ui.Section(
                        text_display,
                        accessory=discord.ui.Thumbnail(media=app["thumbnail_url"])
                    )
                )
            else:
                container_items.append(text_display)
        elif app["thumbnail_url"] and has_gallery:
            container_items.append(
                discord.ui.MediaGallery(discord.MediaGalleryItem(media=app["thumbnail_url"]))
            )

        if app["banner_url"] and has_gallery:
            container_items.append(
                discord.ui.MediaGallery(discord.MediaGalleryItem(media=app["banner_url"]))
            )

        if container_items:
            separator_spacing = getattr(discord, "SeparatorSpacing", None)
            spacing_arg = separator_spacing.small if separator_spacing else None
            separator = (
                discord.ui.Separator(visible=True)
                if spacing_arg is None
                else discord.ui.Separator(visible=True, spacing=spacing_arg)
            )
            container_items.append(separator)

        container_items.append(
            discord.ui.ActionRow(PublicTicketCategorySelect(guild_id, categorias, guild=guild))
        )

        container_kwargs: Dict[str, Any] = {}
        if app["cor"] is not None:
            container_kwargs["accent_colour"] = app["cor"]

        layout_view = discord.ui.LayoutView(timeout=None)
        container = discord.ui.Container(*container_items, **container_kwargs)
        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Erro ao instanciar LayoutView v2 do painel público: {e}")
        return None


def build_fallback_public_ticket_payload(guild_id: int, guild=None) -> Dict[str, Any]:
    """Fallback em Embed padrão usando estritamente o que foi configurado na Aparência."""
    gid_str = str(guild_id or "direct")
    cfg = CloudStorage.get_guild_config(gid_str)
    painel_cfg = cfg.get("painel", {})
    app = _get_configured_appearance(painel_cfg)
    categorias = cfg.get("categorias_ticket", [])

    view = discord.ui.View(timeout=None)
    if categorias:
        view.add_item(PublicTicketCategorySelect(guild_id, categorias, guild=guild))

    titulo_vis = EmojiManager.replace_known_text_emojis(app["titulo"], guild=guild) if app["titulo"] else None
    desc_vis = EmojiManager.replace_known_text_emojis(app["descricao"], guild=guild) if app["descricao"] else None
    has_embed_content = any([titulo_vis, desc_vis, app["banner_url"], app["thumbnail_url"]])
    if has_embed_content:
        embed_kwargs: Dict[str, Any] = {}
        has_custom_emoji_in_title = bool(titulo_vis and ("<:" in titulo_vis or "<a:" in titulo_vis))
        if titulo_vis and not has_custom_emoji_in_title:
            embed_kwargs["title"] = titulo_vis
            if desc_vis:
                embed_kwargs["description"] = desc_vis
        elif titulo_vis and has_custom_emoji_in_title:
            combined = f"## {titulo_vis}\n\n{desc_vis}" if desc_vis else f"## {titulo_vis}"
            embed_kwargs["description"] = combined
        elif desc_vis:
            embed_kwargs["description"] = desc_vis
        if app["cor"] is not None:
            embed_kwargs["color"] = app["cor"]
        embed = discord.Embed(**embed_kwargs)
        if app["banner_url"]:
            embed.set_image(url=app["banner_url"])
        if app["thumbnail_url"]:
            embed.set_thumbnail(url=app["thumbnail_url"])
        return {"embed": embed, "view": view}

    return {"view": view}


async def refresh_sent_ticket_panels(bot: discord.Client, guild_id: int, guild=None) -> None:
    """Atualiza automaticamente painéis públicos já enviados quando aparência ou categorias mudam."""
    gid_str = str(guild_id or "direct")
    cfg = CloudStorage.get_guild_config(gid_str)
    painel_cfg = cfg.get("painel", {})
    if not painel_cfg.get("atualizacao_automatica", True):
        return
    enviados = painel_cfg.get("paineis_enviados") or []
    if not enviados or not cfg.get("categorias_ticket"):
        return

    v2_view = build_v2_public_ticket_layout(guild_id, guild=guild)
    fallback_payload = None if v2_view is not None else build_fallback_public_ticket_payload(guild_id, guild=guild)

    valid_entries = []
    changed = False
    for entry in enviados:
        ch_id = entry.get("channel_id")
        msg_id = entry.get("message_id")
        if not ch_id or not msg_id:
            continue
        try:
            channel = (guild.get_channel(int(ch_id)) if guild else None) or bot.get_channel(int(ch_id)) or await bot.fetch_channel(int(ch_id))
            msg = await channel.fetch_message(int(msg_id))
            if v2_view is not None:
                await msg.edit(view=v2_view, embed=None, content=None)
            elif fallback_payload is not None:
                await msg.edit(**fallback_payload, content=None)
            valid_entries.append(entry)
        except discord.NotFound:
            changed = True
        except Exception as e:
            logger.warning(f"Não foi possível atualizar painel enviado ({ch_id}/{msg_id}): {e}")
            valid_entries.append(entry)

    if changed:
        painel_cfg["paineis_enviados"] = valid_entries
        await CloudStorage.save_guild_config(gid_str, cfg)


def _schedule_panel_refresh(bot: discord.Client, guild_id: int, guild=None) -> None:
    try:
        asyncio.create_task(refresh_sent_ticket_panels(bot, guild_id, guild=guild))
    except Exception:
        pass


def format_set_painel_text(status_msg: Optional[str] = None) -> str:
    """Texto do painel do comando /set painel."""
    emoji_bot = EmojiManager.get("bot", fallback="<:bot:1557140838285582438>")
    emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")
    lines = [
        f"## {emoji_bot} Enviar painel de tickets\n",
        f"> {emoji_info} Selecione abaixo o canal onde deseja enviar o painel de tickets."
    ]
    if status_msg:
        lines.append(f"\n{status_msg}")
    return "\n".join(lines)


class SetPainelChannelSelect(discord.ui.ChannelSelect):
    """Select Menu de canais para escolher onde enviar o painel público de tickets."""
    def __init__(self, guild_id: int, user_id: int):
        self.guild_id = guild_id
        self.user_id = user_id
        super().__init__(
            placeholder="Selecione o canal para enviar o painel...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
            custom_id="select_set_painel_canal"
        )

    async def callback(self, interaction: discord.Interaction):
        gid_int = self.guild_id or (interaction.guild_id or 0)
        gid_str = str(gid_int or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        categorias = cfg.get("categorias_ticket", [])

        if not categorias:
            await render_set_painel(
                interaction,
                gid_int,
                self.user_id or interaction.user.id,
                is_edit=True,
                status_msg=f"{EmojiManager.get('warn')} Nenhuma categoria foi configurada ainda. Crie pelo menos uma categoria em `/painel` → **Configurações do sistema** → **Categorias**."
            )
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        selected_ch = self.values[0]
        channel_id = int(getattr(selected_ch, "id", selected_ch))
        target_channel = (
            (interaction.guild.get_channel(channel_id) if interaction.guild else None)
            or interaction.client.get_channel(channel_id)
        )
        if target_channel is None:
            try:
                target_channel = await interaction.client.fetch_channel(channel_id)
            except Exception as e:
                await render_set_painel(
                    interaction,
                    gid_int,
                    self.user_id or interaction.user.id,
                    is_edit=True,
                    status_msg=f"{EmojiManager.get('wrong')} Não foi possível acessar o canal selecionado: {e}"
                )
                return

        await _ensure_guild_category_emojis(interaction, gid_int)
        await _ensure_guild_appearance_emojis(interaction, gid_int)

        sent_msg = None
        v2_view = build_v2_public_ticket_layout(gid_int, guild=interaction.guild)
        if v2_view is not None:
            try:
                sent_msg = await target_channel.send(view=v2_view)
            except discord.Forbidden:
                await render_set_painel(
                    interaction,
                    gid_int,
                    self.user_id or interaction.user.id,
                    is_edit=True,
                    status_msg=f"{EmojiManager.get('wrong')} Não tenho permissão para enviar mensagens no canal {target_channel.mention}."
                )
                return
            except Exception as e:
                logger.warning(f"Aviso ao enviar painel público V2 em {target_channel.id}: {e}. Tentando fallback.")

        if sent_msg is None:
            fallback_payload = build_fallback_public_ticket_payload(gid_int, guild=interaction.guild)
            try:
                sent_msg = await target_channel.send(**fallback_payload)
            except discord.Forbidden:
                await render_set_painel(
                    interaction,
                    gid_int,
                    self.user_id or interaction.user.id,
                    is_edit=True,
                    status_msg=f"{EmojiManager.get('wrong')} Não tenho permissão para enviar mensagens no canal {target_channel.mention}."
                )
                return
            except Exception as e:
                await render_set_painel(
                    interaction,
                    gid_int,
                    self.user_id or interaction.user.id,
                    is_edit=True,
                    status_msg=f"{EmojiManager.get('wrong')} Erro ao enviar o painel no canal {target_channel.mention}: {e}"
                )
                return

        enviados = cfg.setdefault("painel", {}).setdefault("paineis_enviados", [])
        enviados.append({"channel_id": str(target_channel.id), "message_id": str(sent_msg.id)})
        await CloudStorage.save_guild_config(gid_str, cfg)

        emoji_on = EmojiManager.get("on", fallback="<:on:1561908741073281054>")
        logger.info(f"Painel público de tickets enviado em #{target_channel} ({target_channel.id}) por {interaction.user} na guilda {gid_str}")
        await render_set_painel(
            interaction,
            gid_int,
            self.user_id or interaction.user.id,
            is_edit=True,
            status_msg=f"{emoji_on} Painel de tickets enviado com sucesso em {target_channel.mention}!"
        )


def build_v2_set_painel_layout(guild_id: int, user_id: int, status_msg: Optional[str] = None):
    """Constrói o painel V2 do comando /set painel com Select Menu de canal."""
    if not HAS_COMPONENTS_V2:
        return None
    try:
        gid_str = str(guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        app = _get_configured_appearance(cfg.get("painel", {}))
        cor_embed = app["cor"] if app["cor"] is not None else config.EMBED_COLOR_DEFAULT

        text = format_set_painel_text(status_msg=status_msg)
        layout_view = discord.ui.LayoutView(timeout=None)

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = discord.ui.Separator(visible=True) if spacing_arg is None else discord.ui.Separator(visible=True, spacing=spacing_arg)

        row_select = discord.ui.ActionRow(SetPainelChannelSelect(guild_id, user_id))
        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            separator,
            row_select,
            accent_colour=cor_embed
        )
        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Erro ao instanciar LayoutView v2 de /set painel: {e}")
        return None


async def render_set_painel(
    interaction: discord.Interaction,
    guild_id: int,
    user_id: int,
    is_edit: bool = False,
    status_msg: Optional[str] = None
):
    """Renderiza o painel efêmero de seleção de canal do comando /set painel."""
    v2_view = build_v2_set_painel_layout(guild_id, user_id, status_msg=status_msg)
    if v2_view is not None:
        try:
            if is_edit:
                if interaction.response.is_done():
                    await interaction.edit_original_response(view=v2_view)
                else:
                    await interaction.response.edit_message(view=v2_view)
            else:
                if interaction.response.is_done():
                    await interaction.followup.send(view=v2_view, ephemeral=True)
                else:
                    await interaction.response.send_message(view=v2_view, ephemeral=True)
            return
        except Exception as e:
            logger.warning(f"Aviso ao enviar LayoutView v2 de /set painel: {e}. Usando fallback.")

    gid_str = str(guild_id or "direct")
    cfg = CloudStorage.get_guild_config(gid_str)
    app = _get_configured_appearance(cfg.get("painel", {}))
    cor_embed = app["cor"] if app["cor"] is not None else config.EMBED_COLOR_DEFAULT

    embed = discord.Embed(description=format_set_painel_text(status_msg=status_msg), color=cor_embed)
    view = discord.ui.View(timeout=None)
    view.add_item(SetPainelChannelSelect(guild_id, user_id))

    if is_edit:
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# =====================================================================
# PAINEL DE CONFIGURAÇÕES ESSENCIAIS (/configurações)
# =====================================================================

def format_configuracoes_panel_text() -> str:
    """Retorna o texto do painel do comando /configurações."""
    emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")
    emoji_cloud = EmojiManager.get("cloud", fallback="<:cloud:1561906158984233031>")
    return (
        f"> {emoji_info} Configure os canais, cargos, etc. "
        "Configurações essenciais para a melhor funcionalidade do bot em seu servidor.\n"
        f"> {emoji_cloud} Todas as configurações são salvas na hora."
    )


def format_canais_config_panel_text(guild_id: str) -> str:
    """Retorna o texto do painel de configuração de canais (/configurações -> Canais)."""
    emoji_bot = EmojiManager.get("bot", fallback="<:bot:1557140838285582438>")
    emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")
    emoji_double_speech = EmojiManager.get("double_speech", fallback="<:double_speech:1561906215834091660>")

    cfg = CloudStorage.get_guild_config(guild_id)
    logs_cfg = cfg.get("logs", {})

    def _fmt_ch(ch_id: Optional[str]) -> str:
        return f"<#{ch_id}>" if ch_id else "Não definido"

    abertos = _fmt_ch(logs_cfg.get("canal_abertos_id"))
    fechados = _fmt_ch(logs_cfg.get("canal_fechados_id"))
    assumidos = _fmt_ch(logs_cfg.get("canal_assumidos_id"))

    return (
        f"## {emoji_bot} Canais\n\n"
        f"> {emoji_info} Configure os seguintes canais para conseguir monitorar tudo que acontece no atendimento do seu servidor.\n"
        f"> \n"
        f"> {emoji_double_speech} Canal Logs de tickets abertos: {abertos}\n"
        f"> {emoji_double_speech} Canal Logs de tickets fechados: {fechados}\n"
        f"> {emoji_double_speech} Canal Logs de tickets assumidos: {assumidos}"
    )


class LogsCanalSelect(discord.ui.ChannelSelect):
    """Channel Select Menu reutilizável para configurar um canal de log de tickets."""
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        log_key: str,
        placeholder: str,
        custom_id: str,
        current_channel_id: Optional[str] = None,
    ):
        self.guild_id = guild_id
        self.user_id = user_id
        self.log_key = log_key

        default_values = []
        if current_channel_id:
            try:
                default_val_cls = getattr(discord, "SelectDefaultValue", None)
                default_type_enum = getattr(discord, "SelectDefaultValueType", None)
                if default_val_cls and default_type_enum:
                    default_values = [
                        default_val_cls(id=int(current_channel_id), type=default_type_enum.channel)
                    ]
                else:
                    default_values = [discord.Object(id=int(current_channel_id))]
            except Exception:
                default_values = []

        select_kwargs: Dict[str, Any] = {
            "placeholder": placeholder,
            "channel_types": [discord.ChannelType.text, discord.ChannelType.news],
            "min_values": 0,
            "max_values": 1,
            "custom_id": custom_id,
        }
        if default_values:
            select_kwargs["default_values"] = default_values

        try:
            super().__init__(**select_kwargs)
        except TypeError:
            select_kwargs.pop("default_values", None)
            super().__init__(**select_kwargs)

    async def callback(self, interaction: discord.Interaction):
        gid_int = self.guild_id or (interaction.guild_id or 0)
        gid_str = str(gid_int or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        logs_cfg = cfg.setdefault("logs", {})

        if self.values:
            selected_ch = self.values[0]
            channel_id = str(getattr(selected_ch, "id", selected_ch))
            logs_cfg[self.log_key] = channel_id
            logger.info(
                f"Canal de log '{self.log_key}' definido para {channel_id} por {interaction.user} na guilda {gid_str}"
            )
        else:
            logs_cfg[self.log_key] = None
            logger.info(
                f"Canal de log '{self.log_key}' removido por {interaction.user} na guilda {gid_str}"
            )

        await CloudStorage.save_guild_config(gid_str, cfg)
        await render_canais_config_panel(
            interaction,
            gid_int,
            self.user_id or interaction.user.id,
            is_edit=True
        )


def format_cargos_config_panel_text(guild_id: str) -> str:
    """Retorna o texto do painel de configuração de cargos (/configurações -> Cargos)."""
    emoji_bot = EmojiManager.get("bot", fallback="<:bot:1557140838285582438>")
    emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")
    emoji_member = EmojiManager.get("member", fallback="<:member:1561907903688876064>")
    emoji_pin = EmojiManager.get("pin", fallback="<:pin:1561908764532146246>")

    cfg = CloudStorage.get_guild_config(guild_id)
    cargos_cfg = cfg.get("cargos", {})
    cargo_membros_id = cargos_cfg.get("cargo_membros_id")
    cargos_permitidos_ids = cargos_cfg.get("cargos_permitidos_ids") or []

    membros_fmt = f"<@&{cargo_membros_id}>" if cargo_membros_id else "Não definido"
    permitidos_fmt = (
        ", ".join(f"<@&{rid}>" for rid in cargos_permitidos_ids)
        if cargos_permitidos_ids
        else "Não definido"
    )

    return (
        f"## {emoji_bot} Cargos\n\n"
        f"> {emoji_info} Selecione os cargos usando os selects menus abaixo.\n"
        f"> {emoji_member} Cargo Membros: {membros_fmt}\n"
        f"> {emoji_pin} Cargos Permitidos: {permitidos_fmt}"
    )


def _build_role_default_values(role_ids: List[str]) -> List[Any]:
    """Constrói default_values para RoleSelect de forma compatível com diferentes versões do discord.py."""
    defaults: List[Any] = []
    default_val_cls = getattr(discord, "SelectDefaultValue", None)
    default_type_enum = getattr(discord, "SelectDefaultValueType", None)
    for rid in role_ids:
        if not rid or not str(rid).isdigit():
            continue
        try:
            if default_val_cls and default_type_enum:
                defaults.append(default_val_cls(id=int(rid), type=default_type_enum.role))
            else:
                defaults.append(discord.Object(id=int(rid)))
        except Exception:
            pass
    return defaults


class CargoMembrosSelect(discord.ui.RoleSelect):
    """Role Select Menu para escolher 1 Cargo Membros."""
    def __init__(self, guild_id: int, user_id: int, current_role_id: Optional[str] = None):
        self.guild_id = guild_id
        self.user_id = user_id

        default_values = _build_role_default_values([current_role_id] if current_role_id else [])
        select_kwargs: Dict[str, Any] = {
            "placeholder": "Selecione o Cargo Membros (apenas 1)...",
            "min_values": 0,
            "max_values": 1,
            "custom_id": "select_config_cargo_membros",
        }
        if default_values:
            select_kwargs["default_values"] = default_values

        try:
            super().__init__(**select_kwargs)
        except TypeError:
            select_kwargs.pop("default_values", None)
            super().__init__(**select_kwargs)

    async def callback(self, interaction: discord.Interaction):
        gid_int = self.guild_id or (interaction.guild_id or 0)
        gid_str = str(gid_int or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        cargos_cfg = cfg.setdefault("cargos", {})

        if self.values:
            selected_role = self.values[0]
            role_id = str(getattr(selected_role, "id", selected_role))
            cargos_cfg["cargo_membros_id"] = role_id
            logger.info(f"Cargo Membros definido para {role_id} por {interaction.user} na guilda {gid_str}")
        else:
            cargos_cfg["cargo_membros_id"] = None
            logger.info(f"Cargo Membros removido por {interaction.user} na guilda {gid_str}")

        await CloudStorage.save_guild_config(gid_str, cfg)
        await render_cargos_config_panel(
            interaction,
            gid_int,
            self.user_id or interaction.user.id,
            is_edit=True
        )


class CargosPermitidosSelect(discord.ui.RoleSelect):
    """Role Select Menu para escolher múltiplos Cargos Permitidos."""
    def __init__(self, guild_id: int, user_id: int, current_role_ids: Optional[List[str]] = None):
        self.guild_id = guild_id
        self.user_id = user_id

        default_values = _build_role_default_values((current_role_ids or [])[:25])
        select_kwargs: Dict[str, Any] = {
            "placeholder": "Selecione os Cargos Permitidos (vários)...",
            "min_values": 0,
            "max_values": 25,
            "custom_id": "select_config_cargos_permitidos",
        }
        if default_values:
            select_kwargs["default_values"] = default_values

        try:
            super().__init__(**select_kwargs)
        except TypeError:
            select_kwargs.pop("default_values", None)
            super().__init__(**select_kwargs)

    async def callback(self, interaction: discord.Interaction):
        gid_int = self.guild_id or (interaction.guild_id or 0)
        gid_str = str(gid_int or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        cargos_cfg = cfg.setdefault("cargos", {})

        role_ids = [str(getattr(r, "id", r)) for r in (self.values or [])]
        cargos_cfg["cargos_permitidos_ids"] = role_ids
        logger.info(f"Cargos Permitidos atualizados ({len(role_ids)}) por {interaction.user} na guilda {gid_str}")

        await CloudStorage.save_guild_config(gid_str, cfg)
        await render_cargos_config_panel(
            interaction,
            gid_int,
            self.user_id or interaction.user.id,
            is_edit=True
        )


class VoltarParaConfiguracoesButton(discord.ui.Button):
    """Botão Voltar dos subpainéis do /configurações para o painel principal do /configurações."""
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        custom_id: str = "btn_canais_voltar",
        row: int = 3
    ):
        super().__init__(
            label="Voltar",
            emoji=resolve_partial_emoji("back", "⬅️"),
            style=discord.ButtonStyle.primary,
            custom_id=custom_id,
            row=row
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Botão Voltar clicado por {interaction.user} para /configurações")
        await render_configuracoes_panel(
            interaction,
            self.guild_id or (interaction.guild_id or 0),
            self.user_id or interaction.user.id,
            is_edit=True
        )


class CanaisConfigButton(discord.ui.Button):
    """Botão Canais do painel /configurações."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Canais",
            emoji=resolve_partial_emoji("double_speech", "💬"),
            style=discord.ButtonStyle.secondary,
            custom_id="btn_configuracoes_canais",
            row=0
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Botão Canais clicado por {interaction.user} no /configurações")
        await render_canais_config_panel(
            interaction,
            self.guild_id or (interaction.guild_id or 0),
            self.user_id or interaction.user.id,
            is_edit=True
        )


class CargosConfigButton(discord.ui.Button):
    """Botão Cargos do painel /configurações."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Cargos",
            emoji=resolve_partial_emoji("cargo", "🛡️"),
            style=discord.ButtonStyle.secondary,
            custom_id="btn_configuracoes_cargos",
            row=0
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Botão Cargos clicado por {interaction.user} no /configurações")
        await render_cargos_config_panel(
            interaction,
            self.guild_id or (interaction.guild_id or 0),
            self.user_id or interaction.user.id,
            is_edit=True
        )


def build_v2_cargos_config_layout(guild_id: int, user_id: int):
    """Constrói o painel V2 de Cargos (/configurações -> Cargos) com 2 RoleSelects e botão Voltar."""
    if not HAS_COMPONENTS_V2:
        return None
    try:
        gid_str = str(guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        cargos_cfg = cfg.get("cargos", {})
        text = format_cargos_config_panel_text(gid_str)

        layout_view = discord.ui.LayoutView(timeout=None)

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = (
            discord.ui.Separator(visible=True)
            if spacing_arg is None
            else discord.ui.Separator(visible=True, spacing=spacing_arg)
        )

        row_membros = discord.ui.ActionRow(
            CargoMembrosSelect(
                guild_id,
                user_id,
                current_role_id=cargos_cfg.get("cargo_membros_id"),
            )
        )
        row_permitidos = discord.ui.ActionRow(
            CargosPermitidosSelect(
                guild_id,
                user_id,
                current_role_ids=cargos_cfg.get("cargos_permitidos_ids") or [],
            )
        )
        row_voltar = discord.ui.ActionRow(
            VoltarParaConfiguracoesButton(guild_id, user_id, custom_id="btn_cargos_voltar", row=2)
        )

        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            separator,
            row_membros,
            row_permitidos,
            row_voltar,
            accent_colour=config.EMBED_COLOR_DEFAULT
        )
        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Erro ao instanciar LayoutView v2 de Cargos (/configurações): {e}")
        return None


async def render_cargos_config_panel(
    interaction: discord.Interaction,
    guild_id: int,
    user_id: int,
    is_edit: bool = True
):
    """Renderiza o painel efêmero de Cargos dentro do fluxo /configurações."""
    gid_str = str(guild_id or "direct")
    v2_view = build_v2_cargos_config_layout(guild_id, user_id)
    if v2_view is not None:
        try:
            if is_edit:
                if interaction.response.is_done():
                    await interaction.edit_original_response(view=v2_view)
                else:
                    await interaction.response.edit_message(view=v2_view)
            else:
                if interaction.response.is_done():
                    await interaction.followup.send(view=v2_view, ephemeral=True)
                else:
                    await interaction.response.send_message(view=v2_view, ephemeral=True)
            logger.info("Painel Cargos (/configurações) enviado com Componentes V2 (Container)")
            return
        except Exception as e:
            logger.warning(f"Aviso ao enviar LayoutView v2 de Cargos: {e}. Usando fallback.")

    cfg = CloudStorage.get_guild_config(gid_str)
    cargos_cfg = cfg.get("cargos", {})
    embed = discord.Embed(
        description=format_cargos_config_panel_text(gid_str),
        color=config.EMBED_COLOR_DEFAULT
    )
    view = discord.ui.View(timeout=None)
    view.add_item(CargoMembrosSelect(guild_id, user_id, current_role_id=cargos_cfg.get("cargo_membros_id")))
    view.add_item(CargosPermitidosSelect(guild_id, user_id, current_role_ids=cargos_cfg.get("cargos_permitidos_ids") or []))
    view.add_item(VoltarParaConfiguracoesButton(guild_id, user_id, custom_id="btn_cargos_voltar", row=2))
    if is_edit:
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


def build_v2_canais_config_layout(guild_id: int, user_id: int):
    """Constrói o painel V2 de Canais (/configurações -> Canais) com 3 ChannelSelects e botão Voltar."""
    if not HAS_COMPONENTS_V2:
        return None
    try:
        gid_str = str(guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        logs_cfg = cfg.get("logs", {})
        text = format_canais_config_panel_text(gid_str)

        layout_view = discord.ui.LayoutView(timeout=None)

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = (
            discord.ui.Separator(visible=True)
            if spacing_arg is None
            else discord.ui.Separator(visible=True, spacing=spacing_arg)
        )

        row_abertos = discord.ui.ActionRow(
            LogsCanalSelect(
                guild_id,
                user_id,
                log_key="canal_abertos_id",
                placeholder="Canal Logs de tickets abertos...",
                custom_id="select_config_canal_abertos",
                current_channel_id=logs_cfg.get("canal_abertos_id"),
            )
        )
        row_fechados = discord.ui.ActionRow(
            LogsCanalSelect(
                guild_id,
                user_id,
                log_key="canal_fechados_id",
                placeholder="Canal Logs de tickets fechados...",
                custom_id="select_config_canal_fechados",
                current_channel_id=logs_cfg.get("canal_fechados_id"),
            )
        )
        row_assumidos = discord.ui.ActionRow(
            LogsCanalSelect(
                guild_id,
                user_id,
                log_key="canal_assumidos_id",
                placeholder="Canal Logs de tickets assumidos...",
                custom_id="select_config_canal_assumidos",
                current_channel_id=logs_cfg.get("canal_assumidos_id"),
            )
        )
        row_voltar = discord.ui.ActionRow(VoltarParaConfiguracoesButton(guild_id, user_id))

        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            separator,
            row_abertos,
            row_fechados,
            row_assumidos,
            row_voltar,
            accent_colour=config.EMBED_COLOR_DEFAULT
        )
        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Erro ao instanciar LayoutView v2 de Canais (/configurações): {e}")
        return None


async def render_canais_config_panel(
    interaction: discord.Interaction,
    guild_id: int,
    user_id: int,
    is_edit: bool = True
):
    """Renderiza o painel efêmero de Canais dentro do fluxo /configurações."""
    gid_str = str(guild_id or "direct")
    v2_view = build_v2_canais_config_layout(guild_id, user_id)
    if v2_view is not None:
        try:
            if is_edit:
                if interaction.response.is_done():
                    await interaction.edit_original_response(view=v2_view)
                else:
                    await interaction.response.edit_message(view=v2_view)
            else:
                if interaction.response.is_done():
                    await interaction.followup.send(view=v2_view, ephemeral=True)
                else:
                    await interaction.response.send_message(view=v2_view, ephemeral=True)
            logger.info("Painel Canais (/configurações) enviado com Componentes V2 (Container)")
            return
        except Exception as e:
            logger.warning(f"Aviso ao enviar LayoutView v2 de Canais: {e}. Usando fallback.")

    cfg = CloudStorage.get_guild_config(gid_str)
    logs_cfg = cfg.get("logs", {})
    embed = discord.Embed(
        description=format_canais_config_panel_text(gid_str),
        color=config.EMBED_COLOR_DEFAULT
    )
    view = discord.ui.View(timeout=None)
    view.add_item(LogsCanalSelect(
        guild_id,
        user_id,
        log_key="canal_abertos_id",
        placeholder="Canal Logs de tickets abertos...",
        custom_id="select_config_canal_abertos",
        current_channel_id=logs_cfg.get("canal_abertos_id"),
    ))
    view.add_item(LogsCanalSelect(
        guild_id,
        user_id,
        log_key="canal_fechados_id",
        placeholder="Canal Logs de tickets fechados...",
        custom_id="select_config_canal_fechados",
        current_channel_id=logs_cfg.get("canal_fechados_id"),
    ))
    view.add_item(LogsCanalSelect(
        guild_id,
        user_id,
        log_key="canal_assumidos_id",
        placeholder="Canal Logs de tickets assumidos...",
        custom_id="select_config_canal_assumidos",
        current_channel_id=logs_cfg.get("canal_assumidos_id"),
    ))
    view.add_item(VoltarParaConfiguracoesButton(guild_id, user_id))
    if is_edit:
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


def build_v2_configuracoes_layout(guild_id: int, user_id: int):
    """Constrói o painel V2 do comando /configurações com banner e botão Canais."""
    if not HAS_COMPONENTS_V2:
        return None
    try:
        text = format_configuracoes_panel_text()
        layout_view = discord.ui.LayoutView(timeout=None)

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = (
            discord.ui.Separator(visible=True)
            if spacing_arg is None
            else discord.ui.Separator(visible=True, spacing=spacing_arg)
        )

        container_items: List[Any] = []
        if hasattr(discord.ui, "MediaGallery") and hasattr(discord, "MediaGalleryItem"):
            container_items.append(
                discord.ui.MediaGallery(discord.MediaGalleryItem(media=MAIN_PANEL_BANNER_URL))
            )
        container_items.extend([
            discord.ui.TextDisplay(text),
            separator,
            discord.ui.ActionRow(
                CanaisConfigButton(guild_id, user_id),
                CargosConfigButton(guild_id, user_id),
            ),
        ])

        container = discord.ui.Container(
            *container_items,
            accent_colour=config.EMBED_COLOR_DEFAULT
        )
        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Erro ao instanciar LayoutView v2 de /configurações: {e}")
        return None


async def render_configuracoes_panel(
    interaction: discord.Interaction,
    guild_id: int,
    user_id: int,
    is_edit: bool = False
):
    """Renderiza o painel efêmero do comando /configurações."""
    v2_view = build_v2_configuracoes_layout(guild_id, user_id)
    if v2_view is not None:
        try:
            if is_edit:
                if interaction.response.is_done():
                    await interaction.edit_original_response(view=v2_view)
                else:
                    await interaction.response.edit_message(view=v2_view)
            else:
                await interaction.response.send_message(view=v2_view, ephemeral=True)
            logger.info("Painel /configurações enviado com Componentes V2 (Container)")
            return
        except discord.NotFound as e:
            elapsed = (discord.utils.utcnow() - interaction.created_at).total_seconds()
            if getattr(e, "code", None) == 10062 and elapsed < 2.5:
                logger.critical(f"[DUPLICATE INSTANCE] 10062 Unknown interaction em {elapsed:.3f}s no /configurações!")
                return
            logger.warning(f"Aviso ao enviar LayoutView v2 de /configurações: {e}. Usando fallback.")
        except Exception as e:
            logger.warning(f"Aviso ao enviar LayoutView v2 de /configurações: {e}. Usando fallback.")

    embed = discord.Embed(
        description=format_configuracoes_panel_text(),
        color=config.EMBED_COLOR_DEFAULT
    )
    embed.set_image(url=MAIN_PANEL_BANNER_URL)
    view = discord.ui.View(timeout=None)
    view.add_item(CanaisConfigButton(guild_id, user_id))
    view.add_item(CargosConfigButton(guild_id, user_id))
    if is_edit:
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# =====================================================================
# COMANDOS SLASH /painel, /configurações E /set painel
# =====================================================================

class SetGroup(app_commands.Group):
    """Grupo de comandos /set"""
    def __init__(self):
        super().__init__(name="set", description="Define e envia painéis do sistema de atendimento NiveSalers")

    @app_commands.command(
        name="painel",
        description="Escolhe o canal e envia o painel público de tickets configurado."
    )
    @app_commands.default_permissions(administrator=True)
    async def painel(self, interaction: discord.Interaction):
        """Abre o painel com Select Menu para escolher o canal de envio do painel de tickets."""
        guild_id = interaction.guild_id or 0
        user_id = interaction.user.id
        logger.info(f"Comando /set painel executado por {interaction.user} (ID: {user_id}) na guilda {guild_id}")
        await render_set_painel(interaction, guild_id, user_id, is_edit=False)


class TicketPanelCog(commands.Cog, name="PainelConfig"):
    """Cog responsável pelos comandos e interações do painel de configuração."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.set_group = SetGroup()
        self.bot.tree.add_command(self.set_group)
        logger.info("TicketPanelCog carregado com sucesso")

    @app_commands.command(
        name="painel",
        description="Abre o painel de configuração dos painéis de atendimento com Componentes V2."
    )
    @app_commands.default_permissions(administrator=True)
    async def painel(self, interaction: discord.Interaction):
        """Abre o painel com Componentes V2 e Container de Layout."""
        guild_id = interaction.guild_id or 0
        user_id = interaction.user.id
        logger.info(f"Comando /painel executado por {interaction.user} (ID: {user_id}) na guilda {guild_id}")
        await render_main_panel(interaction, guild_id, user_id, is_edit=False)

    @app_commands.command(
        name="configurações",
        description="Configure canais, cargos e definições essenciais do bot no servidor."
    )
    @app_commands.default_permissions(administrator=True)
    async def configuracoes(self, interaction: discord.Interaction):
        """Abre o painel de configurações essenciais do servidor."""
        guild_id = interaction.guild_id or 0
        user_id = interaction.user.id
        logger.info(f"Comando /configurações executado por {interaction.user} (ID: {user_id}) na guilda {guild_id}")
        await render_configuracoes_panel(interaction, guild_id, user_id)

    @commands.Cog.listener("on_interaction")
    async def on_public_ticket_interaction(self, interaction: discord.Interaction):
        """Mantém os Select Menus do painel público e do painel interno do ticket funcionais após reinícios."""
        if interaction.type != discord.InteractionType.component:
            return
        data = interaction.data or {}
        custom_id = data.get("custom_id")
        values = data.get("values") or []

        if custom_id == "select_ticket_abrir_categoria":
            if not values:
                return
            await asyncio.sleep(0.05)
            if interaction.response.is_done():
                return
            await handle_public_category_selection(
                interaction,
                str(values[0]),
                interaction.guild_id or 0
            )
        elif custom_id == "select_ticket_painel_acoes":
            if not values:
                return
            await asyncio.sleep(0.05)
            if interaction.response.is_done():
                return
            await handle_ticket_panel_action(
                interaction,
                str(values[0]),
                interaction.guild_id or 0,
                interaction.channel_id or 0,
            )
        elif custom_id == "btn_ticket_notificar_equipe":
            await asyncio.sleep(0.05)
            if interaction.response.is_done():
                return
            await handle_ticket_notify_staff(
                interaction,
                interaction.guild_id or 0,
                interaction.channel_id or 0,
            )
        elif custom_id == "btn_ticket_sair_atendimento":
            await asyncio.sleep(0.05)
            if interaction.response.is_done():
                return
            await handle_ticket_leave_opener(
                interaction,
                interaction.guild_id or 0,
                interaction.channel_id or 0,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketPanelCog(bot))
