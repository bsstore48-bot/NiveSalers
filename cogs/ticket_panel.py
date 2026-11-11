"""
NiveSalers - Ticket Configuration Panel Cog
Componentes V2 (LayoutView & Container Type 17).
Modals de imagem com componentes nativos de upload (Type 19).
Botões de voltar sempre em linha separada (última fila) e com estilo azul (primary).
"""
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict, Any, List

import config
from utils.logger import logger
from utils.emoji_manager import EmojiManager
from database.cloud_storage import CloudStorage

# Detecção de suporte nativo a Componentes v2 (discord.py 2.6+)
HAS_COMPONENTS_V2 = hasattr(discord.ui, "LayoutView") and hasattr(discord.ui, "Container")

# Garante a existência da classe FileUpload (Componente Type 19 de Upload em Modals)
if hasattr(discord.ui, "FileUpload"):
    FileUploadComponentClass = discord.ui.FileUpload
else:
    class FileUploadComponentClass(discord.ui.Item):
        """Implementação do componente de upload de arquivos para modals (Type 19)."""
        def __init__(self, *, custom_id: str, min_values: int = 0, max_values: int = 1, required: bool = False):
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
                "required": self.required
            }

# 10 cores predefinidas para a embed/container do painel
CORES_DISPONIVEIS = [
    {"label": "Branco (Padrão)", "value": "FFFFFF", "hex": "#FFFFFF", "int": 0xFFFFFF, "emoji": "⚪", "desc": "Estilo limpo e minimalista"},
    {"label": "Preto Escuro", "value": "2B2D31", "hex": "#2B2D31", "int": 0x2B2D31, "emoji": "⚫", "desc": "Tema escuro Discord"},
    {"label": "Azul", "value": "3498DB", "hex": "#3498DB", "int": 0x3498DB, "emoji": "🔵", "desc": "Azul vibrante profissional"},
    {"label": "Verde", "value": "2ECC71", "hex": "#2ECC71", "int": 0x2ECC71, "emoji": "🟢", "desc": "Verde esmeralda"},
    {"label": "Vermelho", "value": "E74C3C", "hex": "#E74C3C", "int": 0xE74C3C, "emoji": "🔴", "desc": "Vermelho chamativo"},
    {"label": "Roxo", "value": "9B59B6", "hex": "#9B59B6", "int": 0x9B59B6, "emoji": "🟣", "desc": "Roxo elegante"},
    {"label": "Amarelo", "value": "F1C40F", "hex": "#F1C40F", "int": 0xF1C40F, "emoji": "🟡", "desc": "Amarelo dourado"},
    {"label": "Laranja", "value": "E67E22", "hex": "#E67E22", "int": 0xE67E22, "emoji": "🟠", "desc": "Laranja pôr do sol"},
    {"label": "Rosa", "value": "E91E63", "hex": "#E91E63", "int": 0xE91E63, "emoji": "🌸", "desc": "Rosa moderno"},
    {"label": "Ciano", "value": "1ABC9C", "hex": "#1ABC9C", "int": 0x1ABC9C, "emoji": "💎", "desc": "Ciano turquesa"}
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
        f"{emoji_edit} ``Título:`` {titulo}",
        f"{emoji_embed} ``Descrição:`` {descricao}",
        f"{emoji_image} ``Banner:`` {banner}",
        f"{emoji_image} ``Thumbnail:`` {thumbnail}",
        f"{emoji_colors} ``Cor da embed:`` {cor}"
    ]
    return "\n".join(lines)


# =====================================================================
# MODALS INTERATIVOS COM COMPONENTE DE UPLOAD
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
    """Modal com componente de upload para a imagem do banner."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id

        # Componente de upload para a imagem do banner
        self.file_upload = FileUploadComponentClass(
            custom_id="banner_file_upload",
            min_values=0,
            max_values=1,
            required=False
        )
        self.add_item(self.file_upload)

    async def on_submit(self, interaction: discord.Interaction):
        novo_banner = None

        # 1. Tenta recuperar arquivo do componente de upload
        if hasattr(self.file_upload, "values") and self.file_upload.values:
            att = self.file_upload.values[0]
            novo_banner = getattr(att, "url", None) or getattr(att, "proxy_url", None) or str(att)

        # 2. Tenta recuperar dos anexos resolvidos da interação (Discord API)
        if not novo_banner:
            resolved_attachments = interaction.data.get("resolved", {}).get("attachments", {})
            if resolved_attachments:
                first_att = next(iter(resolved_attachments.values()))
                novo_banner = first_att.get("url")

        cfg = CloudStorage.get_guild_config(str(self.guild_id))
        cfg["painel"]["banner_url"] = novo_banner or "Não definido"
        await CloudStorage.save_guild_config(str(self.guild_id), cfg)

        logger.info(f"Banner atualizado via componente de upload por {interaction.user}: {novo_banner}")
        await render_appearance_panel(interaction, self.guild_id, self.user_id, is_edit=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Erro no modal de banner: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Ocorreu um erro ao salvar o banner: {error}", ephemeral=True)


class ThumbnailModal(discord.ui.Modal, title="Configurar Thumbnail"):
    """Modal com componente de upload para a imagem da thumbnail."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id

        # Componente de upload para a imagem da miniatura
        self.file_upload = FileUploadComponentClass(
            custom_id="thumbnail_file_upload",
            min_values=0,
            max_values=1,
            required=False
        )
        self.add_item(self.file_upload)

    async def on_submit(self, interaction: discord.Interaction):
        nova_thumb = None

        # 1. Tenta recuperar arquivo do componente de upload
        if hasattr(self.file_upload, "values") and self.file_upload.values:
            att = self.file_upload.values[0]
            nova_thumb = getattr(att, "url", None) or getattr(att, "proxy_url", None) or str(att)

        # 2. Tenta recuperar dos anexos resolvidos da interação (Discord API)
        if not nova_thumb:
            resolved_attachments = interaction.data.get("resolved", {}).get("attachments", {})
            if resolved_attachments:
                first_att = next(iter(resolved_attachments.values()))
                nova_thumb = first_att.get("url")

        cfg = CloudStorage.get_guild_config(str(self.guild_id))
        cfg["painel"]["thumbnail_url"] = nova_thumb or "Não definido"
        await CloudStorage.save_guild_config(str(self.guild_id), cfg)

        logger.info(f"Thumbnail atualizada via componente de upload por {interaction.user}: {nova_thumb}")
        await render_appearance_panel(interaction, self.guild_id, self.user_id, is_edit=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Erro no modal de thumbnail: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Ocorreu um erro ao salvar a thumbnail: {error}", ephemeral=True)


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
            emoji=resolve_partial_emoji("edit", "✏️"),
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
            emoji=resolve_partial_emoji("edit", "✏️"),
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_banner",
            row=0
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Banner button clicado por {interaction.user} (abrindo modal de upload)")
        await interaction.response.send_modal(BannerModal(self.guild_id or (interaction.guild_id or 0), interaction.user.id))


class ThumbnailButton(discord.ui.Button):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Thumbnail",
            emoji=resolve_partial_emoji("edit", "✏️"),
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_thumbnail",
            row=1
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Thumbnail button clicado por {interaction.user} (abrindo modal de upload)")
        await interaction.response.send_modal(ThumbnailModal(self.guild_id or (interaction.guild_id or 0), interaction.user.id))


class CorButton(discord.ui.Button):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Cor da embed",
            emoji=resolve_partial_emoji("edit", "✏️"),
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_cor",
            row=1
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Cor button clicado por {interaction.user}")
        await render_cor_panel(interaction, self.guild_id or (interaction.guild_id or 0), interaction.user.id, is_edit=True)


class VoltarParaPrincipalButton(discord.ui.Button):
    """Botão Voltar: sempre em linha separada (última fila) e com cor azul (primary)."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Voltar",
            emoji=resolve_partial_emoji("back", "⬅️"),
            style=discord.ButtonStyle.primary,  # Sempre Azul (Primary)
            custom_id="btn_aparencia_voltar",
            row=2  # Última fila separada
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Voltar button clicado por {interaction.user}")
        await render_main_panel(interaction, self.guild_id or (interaction.guild_id or 0), interaction.user.id, is_edit=True)


# =====================================================================
# SELECT MENUS & VIEWS DE CORES
# =====================================================================

class CorEmbedSelect(discord.ui.Select):
    """Select Menu contendo as 10 cores predefinidas para a embed."""
    def __init__(self, guild_id: int, user_id: int):
        self.guild_id = guild_id
        self.user_id = user_id

        options = [
            discord.SelectOption(
                label=cor["label"],
                value=cor["value"],
                description=cor["desc"],
                emoji=cor["emoji"]
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
    """Botão Voltar: sempre em linha separada (última fila) e com cor azul (primary)."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(
            label="Voltar para Aparência",
            emoji=resolve_partial_emoji("back", "⬅️"),
            style=discord.ButtonStyle.primary,  # Sempre Azul (Primary)
            custom_id="btn_cor_voltar_aparencia",
            row=1  # Última fila separada da ActionRow do select
        )
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"Voltar para Aparência clicado por {interaction.user}")
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
                label="Configurações do painel",
                value="configuracoes",
                description="Defina canais, categorias, cargos e regras de atendimento",
                emoji=emoji_config
            )
        ]

        super().__init__(
            placeholder="Selecione uma opção para configurar.",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="nivesalers_config_painel_select"
        )

    async def callback(self, interaction: discord.Interaction):
        escolha = self.values[0] if self.values else ""

        if escolha == "aparencia":
            gid = self.guild_id or (interaction.guild_id or 0)
            await render_appearance_panel(interaction, gid, interaction.user.id, is_edit=True)
            logger.info(f"Painel de aparência acessado por {interaction.user}")

        elif escolha == "configuracoes":
            logger.info(f"Opção 'Configurações do painel' selecionada por {interaction.user} (sem ação por enquanto).")
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)


# =====================================================================
# CONSTRUTORES DE COMPONENTES V2 (LAYOUTVIEW & CONTAINER TYPE 17)
# =====================================================================

def build_v2_main_layout(guild_id: int, user_id: int):
    """
    Constrói a árvore de LayoutView com Container e ActionRow para o painel principal.
    Garante que o Select Menu esteja rigorosamente dentro do container de layout.
    """
    if not HAS_COMPONENTS_V2:
        return None

    try:
        text = format_main_panel_text()
        layout_view = discord.ui.LayoutView(timeout=None)

        # ActionRow contendo o Select Menu dentro do container
        action_row = discord.ui.ActionRow(ConfigPainelSelect(guild_id, user_id))

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = discord.ui.Separator(visible=True) if spacing_arg is None else discord.ui.Separator(visible=True, spacing=spacing_arg)

        # Container V2 (Type 17) agrupando texto, divisor e action row
        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            separator,
            action_row,
            accent_colour=config.EMBED_COLOR_DEFAULT
        )
        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Erro ao instanciar LayoutView v2 principal: {e}")
        return None


def build_v2_appearance_layout(guild_id: int, user_id: int):
    """
    Constrói a árvore de LayoutView com Container e ActionRows para o painel de aparência.
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

        # Linha 1 de botões
        row1 = discord.ui.ActionRow(
            TituloButton(guild_id, user_id),
            DescricaoButton(guild_id, user_id),
            BannerButton(guild_id, user_id)
        )

        # Linha 2 de botões
        row2 = discord.ui.ActionRow(
            ThumbnailButton(guild_id, user_id),
            CorButton(guild_id, user_id)
        )

        # Linha 3 (Última fila separada exclusivamente para o botão Voltar)
        row_voltar = discord.ui.ActionRow(
            VoltarParaPrincipalButton(guild_id, user_id)
        )

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = discord.ui.Separator(visible=True) if spacing_arg is None else discord.ui.Separator(visible=True, spacing=spacing_arg)

        # Container V2 (Type 17) contendo todos os layouts
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
    Botão Voltar para Aparência estritamente na última linha separada e em azul.
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
            await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def render_appearance_panel(interaction: discord.Interaction, guild_id: int, user_id: int, is_edit: bool = True):
    """Renderiza o painel de aparência com Componentes V2 (Container + Botões nos Layouts)."""
    v2_view = build_v2_appearance_layout(guild_id, user_id)
    if v2_view is not None:
        try:
            if is_edit:
                await interaction.response.edit_message(view=v2_view)
            else:
                await interaction.response.send_message(view=v2_view, ephemeral=True)
            logger.info("Painel de aparência enviado com Componentes V2 (Container com botões internos)")
            return
        except Exception as e:
            logger.warning(f"Aviso ao enviar LayoutView v2 de aparência: {e}. Usando fallback.")

    gid_str = str(guild_id or (interaction.guild_id or "direct"))
    text = format_appearance_panel_text(gid_str)
    cfg = CloudStorage.get_guild_config(gid_str)
    cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT

    embed = discord.Embed(description=text, color=cor_embed)
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
            await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def render_cor_panel(interaction: discord.Interaction, guild_id: int, user_id: int, is_edit: bool = True):
    """Renderiza o painel de cores com Componentes V2 (Container + Select de 10 cores)."""
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
            logger.warning(f"Aviso ao enviar LayoutView v2 de cores: {e}. Usando fallback.")

    gid_str = str(guild_id or (interaction.guild_id or "direct"))
    cfg = CloudStorage.get_guild_config(gid_str)
    cor_atual_int = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT
    emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")

    text = (
        "## Configurar Cor da embed do painel de atendimento.\n\n"
        f"{emoji_info} Selecione a cor desejada usando o select menu abaixo."
    )

    embed = discord.Embed(description=text, color=cor_atual_int)
    view = discord.ui.View(timeout=None)
    view.add_item(CorEmbedSelect(guild_id, user_id))
    view.add_item(VoltarParaAparenciaButton(guild_id, user_id))

    if is_edit:
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# =====================================================================
# COMANDO SLASH /configurar painel
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
        CloudStorage.get_guild_config(str(guild_id))
        await render_main_panel(interaction, guild_id, interaction.user.id, is_edit=False)


class TicketPanelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.configurar_group = ConfigurarGroup()
        self.bot.tree.add_command(self.configurar_group)

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketPanelCog(bot))
