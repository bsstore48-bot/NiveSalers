"""
Cog responsável pelo comando /configurar painel e pelo fluxo interativo
utilizando Discord Components v2 (LayoutView, Container, ActionRow) e
modais com suporte nativo a componentes de upload de arquivo.
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional
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

def resolve_partial_emoji(emoji_key: str, default_unicode: str = "⚙️"):
    """Converte tag de emoji em discord.PartialEmoji ou string Unicode de forma segura."""
    raw = EmojiManager.get(emoji_key, fallback=default_unicode)
    if raw.startswith("<") and raw.endswith(">"):
        try:
            return discord.PartialEmoji.from_str(raw)
        except Exception:
            return default_unicode
    return raw


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


class CriarCategoriaModal(discord.ui.Modal, title="Criar Categoria"):
    """Modal com 5 abas (Label Type 18) para criar ou editar uma categoria de atendimento."""
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        edit_cat_id: Optional[str] = None,
        categoria_atual: Optional[Dict[str, Any]] = None,
        include_select_defaults: bool = True
    ):
        modal_title = "Editar Categoria" if categoria_atual is not None else "Criar Categoria"
        super().__init__(title=modal_title)
        self.guild_id = guild_id
        self.user_id = user_id
        self.edit_cat_id = edit_cat_id
        self.categoria_atual = categoria_atual
        self.include_select_defaults = include_select_defaults

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

        comp_cargos: Dict[str, Any] = {
            "type": 6,
            "custom_id": "cat_cargos_permitidos",
            "placeholder": "Selecione os cargos permitidos...",
            "min_values": 1,
            "max_values": 10,
            "required": True
        }
        if self.include_select_defaults:
            default_roles = [{"id": str(rid), "type": "role"} for rid in cargos_atuais if str(rid).isdigit()][:10]
            if default_roles:
                comp_cargos["default_values"] = default_roles

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
        logger.info(f"Botão Criar categoria clicado por {interaction.user} (abrindo modal)")
        await interaction.response.send_modal(
            CriarCategoriaModal(self.guild_id or (interaction.guild_id or 0), interaction.user.id)
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

        try:
            await interaction.response.send_modal(
                CriarCategoriaModal(
                    gid_int,
                    uid_int,
                    edit_cat_id=selected_id,
                    categoria_atual=categoria_alvo,
                    include_select_defaults=True
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
                        include_select_defaults=False
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


async def handle_public_category_selection(interaction: discord.Interaction, selected_id: str, guild_id: int = 0) -> None:
    """Processa a seleção de categoria no painel público de tickets (funciona também após reinício)."""
    if interaction.id in _handled_public_interactions:
        return
    _handled_public_interactions.append(interaction.id)
    if len(_handled_public_interactions) > 200:
        del _handled_public_interactions[:100]

    gid_str = str(guild_id or interaction.guild_id or "direct")
    cfg = CloudStorage.get_guild_config(gid_str)
    categorias = cfg.get("categorias_ticket", [])

    categoria_alvo = None
    for idx, cat in enumerate(categorias):
        cat_val = str(cat.get("id") or f"idx_{idx}")
        if cat_val == str(selected_id):
            categoria_alvo = cat
            break

    if categoria_alvo is None:
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Esta categoria não está mais disponível no painel.",
                ephemeral=True
            )
        return

    cat_nome = categoria_alvo.get("nome") or "Atendimento"
    logger.info(f"Categoria pública '{cat_nome}' selecionada por {interaction.user} na guilda {gid_str}")
    if not interaction.response.is_done():
        await interaction.response.send_message(
            f"Categoria **{cat_nome}** selecionada.",
            ephemeral=True
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
                status_msg="⚠️ Nenhuma categoria foi configurada ainda. Crie pelo menos uma categoria em `/painel` → **Configurações do sistema** → **Categorias**."
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
                    status_msg=f"❌ Não foi possível acessar o canal selecionado: {e}"
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
                    status_msg=f"❌ Não tenho permissão para enviar mensagens no canal {target_channel.mention}."
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
                    status_msg=f"❌ Não tenho permissão para enviar mensagens no canal {target_channel.mention}."
                )
                return
            except Exception as e:
                await render_set_painel(
                    interaction,
                    gid_int,
                    self.user_id or interaction.user.id,
                    is_edit=True,
                    status_msg=f"❌ Erro ao enviar o painel no canal {target_channel.mention}: {e}"
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


class VoltarParaConfiguracoesButton(discord.ui.Button):
    """Botão Voltar do painel de Canais para o painel /configurações."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Voltar",
            emoji=resolve_partial_emoji("back", "⬅️"),
            style=discord.ButtonStyle.primary,
            custom_id="btn_canais_voltar",
            row=3
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Botão Voltar clicado por {interaction.user} no painel de Canais")
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
        if hasattr(discord.ui, "MediaGallery") and hasattr(discord.ui, "MediaGalleryItem"):
            container_items.append(
                discord.ui.MediaGallery(discord.MediaGalleryItem(media=MAIN_PANEL_BANNER_URL))
            )
        container_items.extend([
            discord.ui.TextDisplay(text),
            separator,
            discord.ui.ActionRow(CanaisConfigButton(guild_id, user_id)),
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
        """Mantém o Select Menu do painel público de tickets funcional mesmo após reinícios do bot."""
        if interaction.type != discord.InteractionType.component:
            return
        data = interaction.data or {}
        if data.get("custom_id") != "select_ticket_abrir_categoria":
            return
        values = data.get("values") or []
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


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketPanelCog(bot))
