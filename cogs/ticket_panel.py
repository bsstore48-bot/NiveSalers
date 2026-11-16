"""
Cog responsável pelo comando /configurar painel e pelo fluxo interativo
utilizando Discord Components v2 (LayoutView, Container, ActionRow) e
modais com suporte nativo a componentes de upload de arquivo.
"""

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

def resolve_partial_emoji(emoji_key: str, default_unicode: str = "⚙️"):
    """Converte tag de emoji em discord.PartialEmoji ou string Unicode de forma segura."""
    raw = EmojiManager.get(emoji_key, fallback=default_unicode)
    if raw.startswith("<") and raw.endswith(">"):
        try:
            return discord.PartialEmoji.from_str(raw)
        except Exception:
            return default_unicode
    return raw

def format_main_panel_text() -> str:
    """Retorna o texto do painel principal de configuração."""
    emoji_bot = EmojiManager.get("bot", fallback="<:bot:1557140838285582438>")
    emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")
    emoji_cloud = EmojiManager.get("cloud", fallback="<:cloud:1561906158984233031>")
    emoji_reload = EmojiManager.get("reload", fallback="<:reload:1561908806584115210>")

    lines = [
        f"## {emoji_bot} Painel de configuração dos painéis de atendimento",
        f"{emoji_info} Selecione uma opção para configurar no painel.",
        f"{emoji_cloud} Todas as configurações serão salvas imediatamente no sistema de atendimento.",
        f"{emoji_reload} Com atualização automática de painéis de atendimento existentes."
    ]
    return "\n".join(lines)

def format_appearance_panel_text(guild_id: str) -> str:
    """Retorna o texto formatado do painel de aparência com os valores dinâmicos do servidor."""
    cfg = CloudStorage.get_guild_config(guild_id)
    painel_cfg = cfg.get("painel", {})

    titulo = painel_cfg.get("titulo") or "Não definido"
    descricao = painel_cfg.get("descricao") or "Não definido"
    banner = painel_cfg.get("banner_url") or "Não definido"
    thumbnail = painel_cfg.get("thumbnail_url") or "Não definido"
    cor = painel_cfg.get("cor_hex") or "#FFFFFF"

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
            canal_id = cat.get("canal_topicos_id")
            cargos_ids = cat.get("cargos_permitidos_ids", [])
            canal_fmt = f"<#{canal_id}>" if canal_id else "Não definido"
            cargos_fmt = ", ".join(f"<@&{rid}>" for rid in cargos_ids) if cargos_ids else "Nenhum"
            lines.append(f"\n**{idx}. {nome}** — {desc}\nCanal: {canal_fmt} | Cargos: {cargos_fmt}")

    return "\n".join(lines)


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
        valor_atual = cfg.get("painel", {}).get("titulo") or ""

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
        cfg = CloudStorage.get_guild_config(str(self.guild_id))
        cfg["painel"]["titulo"] = novo_titulo
        await CloudStorage.save_guild_config(str(self.guild_id), cfg)

        logger.info(f"Título atualizado por {interaction.user} no servidor {self.guild_id}: '{novo_titulo}'")
        await render_appearance_panel(interaction, self.guild_id, self.user_id, is_edit=True)

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
        valor_atual = cfg.get("painel", {}).get("descricao") or ""

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
        cfg = CloudStorage.get_guild_config(str(self.guild_id))
        cfg["painel"]["descricao"] = nova_descricao
        await CloudStorage.save_guild_config(str(self.guild_id), cfg)

        logger.info(f"Descrição atualizada por {interaction.user} no servidor {self.guild_id}")
        await render_appearance_panel(interaction, self.guild_id, self.user_id, is_edit=True)

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

        if novo_banner:
            cfg = CloudStorage.get_guild_config(str(self.guild_id))
            cfg["painel"]["banner_url"] = novo_banner
            await CloudStorage.save_guild_config(str(self.guild_id), cfg)
            logger.info(f"Banner atualizado via componente de upload por {interaction.user}: {novo_banner}")

        await render_appearance_panel(interaction, self.guild_id, self.user_id, is_edit=True)

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

        if nova_thumb:
            cfg = CloudStorage.get_guild_config(str(self.guild_id))
            cfg["painel"]["thumbnail_url"] = nova_thumb
            await CloudStorage.save_guild_config(str(self.guild_id), cfg)
            logger.info(f"Thumbnail atualizada via componente de upload por {interaction.user}: {nova_thumb}")

        await render_appearance_panel(interaction, self.guild_id, self.user_id, is_edit=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Erro no modal de upload da thumbnail: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Ocorreu um erro no upload da thumbnail: {error}", ephemeral=True)


class CriarCategoriaModal(discord.ui.Modal, title="Criar Categoria"):
    """Modal com 4 abas (Label Type 18) para criar uma nova categoria de atendimento."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id

    def to_components(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": 18,
                "label": "Nome da categoria",
                "description": "Nome exibido na opção do painel de atendimento",
                "component": {
                    "type": 4,
                    "custom_id": "cat_nome",
                    "style": 1,
                    "placeholder": "Ex: Suporte Técnico",
                    "min_length": 1,
                    "max_length": 50,
                    "required": True
                }
            },
            {
                "type": 18,
                "label": "Descrição da categoria",
                "description": "Descrição breve (~25 caracteres) exibida no painel público",
                "component": {
                    "type": 4,
                    "custom_id": "cat_descricao",
                    "style": 1,
                    "placeholder": "Ex: Tire suas dúvidas aqui",
                    "min_length": 1,
                    "max_length": 50,
                    "required": True
                }
            },
            {
                "type": 18,
                "label": "Canal de tópicos",
                "description": "Onde o bot abrirá os tópicos privados de atendimento",
                "component": {
                    "type": 8,
                    "custom_id": "cat_canal_topicos",
                    "placeholder": "Selecione o canal de texto...",
                    "channel_types": [0, 5],
                    "min_values": 1,
                    "max_values": 1,
                    "required": True
                }
            },
            {
                "type": 18,
                "label": "Cargos permitidos",
                "description": "Cargos que poderão participar dos tópicos privados",
                "component": {
                    "type": 6,
                    "custom_id": "cat_cargos_permitidos",
                    "placeholder": "Selecione os cargos permitidos...",
                    "min_values": 1,
                    "max_values": 10,
                    "required": True
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
        nome = ""
        descricao = ""
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
                elif cid == "cat_canal_topicos":
                    vals = comp.get("values") or []
                    if vals:
                        canal_id = str(vals[0])
                elif cid == "cat_cargos_permitidos":
                    vals = comp.get("values") or []
                    cargos_ids = [str(v) for v in vals]

        gid_str = str(self.guild_id or interaction.guild_id or "direct")
        cfg = CloudStorage.get_guild_config(gid_str)
        if not isinstance(cfg.get("categorias_ticket"), list):
            cfg["categorias_ticket"] = []

        nova_categoria = {
            "id": uuid.uuid4().hex[:8],
            "nome": nome,
            "descricao": descricao,
            "canal_topicos_id": canal_id,
            "cargos_permitidos_ids": cargos_ids
        }
        cfg["categorias_ticket"].append(nova_categoria)
        await CloudStorage.save_guild_config(gid_str, cfg)

        logger.info(f"Nova categoria '{nome}' criada por {interaction.user} na guilda {gid_str}")
        await render_categories_panel(interaction, self.guild_id or (interaction.guild_id or 0), self.user_id, is_edit=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Erro no modal de criar categoria: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Ocorreu um erro ao criar categoria: {error}", ephemeral=True)


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
    """Botão vermelho Remover categoria (sem ação por enquanto)."""
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
        logger.info(f"Botão Remover categoria clicado por {interaction.user} (sem ação por enquanto)")
        await interaction.response.defer()


class EditarCategoriaButton(discord.ui.Button):
    """Botão cinza Editar categoria (sem ação por enquanto)."""
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
        logger.info(f"Botão Editar categoria clicado por {interaction.user} (sem ação por enquanto)")
        await interaction.response.defer()


class VoltarParaSistemaButton(discord.ui.Button):
    """Botão Voltar do painel de categorias: sempre azul na última linha separada."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Voltar",
            emoji=resolve_partial_emoji("back", "⬅️"),
            style=discord.ButtonStyle.primary,  # Sempre Azul (Primary)
            custom_id="btn_categorias_voltar",
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
            await CloudStorage.save_guild_config(gid, cfg)
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

        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            separator,
            row,
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
            CategoriasButton(guild_id, user_id)
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
        except Exception as e:
            logger.warning(f"Aviso ao enviar LayoutView v2: {e}. Usando fallback.")

    text = format_main_panel_text()
    embed = discord.Embed(description=text, color=config.EMBED_COLOR_DEFAULT)
    view = discord.ui.View(timeout=None)
    view.add_item(ConfigPainelSelect(guild_id, user_id))

    if is_edit:
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def render_appearance_panel(interaction: discord.Interaction, guild_id: int, user_id: int, is_edit: bool = True):
    """Renderiza o painel de aparência com Componentes V2 (Container + botões)."""
    v2_view = build_v2_appearance_layout(guild_id, user_id)
    if v2_view is not None:
        try:
            if is_edit:
                await interaction.response.edit_message(view=v2_view)
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
    view.add_item(VoltarParaPrincipalButton(guild_id, user_id, row=1, custom_id="btn_sistema_voltar"))

    if is_edit:
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def render_categories_panel(interaction: discord.Interaction, guild_id: int, user_id: int, is_edit: bool = True):
    """Renderiza o painel de Categorias com Componentes V2 (Container + Criar/Remover/Editar + Voltar)."""
    v2_view = build_v2_categories_layout(guild_id, user_id)
    if v2_view is not None:
        try:
            if is_edit:
                await interaction.response.edit_message(view=v2_view)
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


# =====================================================================
# COMANDO SLASH /configurar painel (SEM PARÂMETRO)
# =====================================================================

class ConfigurarGroup(app_commands.Group):
    """Grupo de comandos /configurar"""
    def __init__(self):
        super().__init__(name="configurar", description="Configurações do sistema de atendimento NiveSalers")

    @app_commands.command(
        name="painel",
        description="Abre o painel de configuração dos painéis de atendimento com Componentes V2."
    )
    @app_commands.default_permissions(administrator=True)
    async def painel(self, interaction: discord.Interaction):
        """Abre o painel com Componentes V2 e Container de Layout."""
        guild_id = interaction.guild_id or 0
        user_id = interaction.user.id
        logger.info(f"Comando /configurar painel executado por {interaction.user} (ID: {user_id}) na guilda {guild_id}")
        await render_main_panel(interaction, guild_id, user_id, is_edit=False)


class TicketPanelCog(commands.Cog, name="PainelConfig"):
    """Cog responsável pelos comandos e interações do painel de configuração."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.configurar_group = ConfigurarGroup()
        self.bot.tree.add_command(self.configurar_group)
        logger.info("TicketPanelCog carregado com sucesso")


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketPanelCog(bot))
