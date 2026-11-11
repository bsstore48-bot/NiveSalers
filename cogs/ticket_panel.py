"""
NiveSalers - Ticket Configuration Panel Cog
Comando /configurar painel com Componentes v2 (Layouts & Containers),
painel de aparência, modals interativos e seletor com 10 cores de embed.
"""
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict, Any

import config
from utils.logger import logger
from utils.emoji_manager import EmojiManager
from database.cloud_storage import CloudStorage

# Detecção dinâmica de suporte a Componentes v2 no discord.py (LayoutView e Container)
HAS_COMPONENTS_V2 = hasattr(discord.ui, "LayoutView") and hasattr(discord.ui, "Container")

# 10 cores predefinidas para a embed do painel
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
    """Converte tag de emoji em discord.PartialEmoji ou string Unicode."""
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
# MODALS INTERATIVOS DE CONFIGURAÇÃO
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


class BannerModal(discord.ui.Modal, title="Configurar Banner"):
    """Modal para inserir a imagem/banner do painel."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id

        cfg = CloudStorage.get_guild_config(str(guild_id))
        valor_atual = cfg.get("painel", {}).get("banner_url") or ""

        self.banner_input = discord.ui.TextInput(
            label="URL / Link da Imagem do Banner",
            placeholder="https://exemplo.com/imagem_banner.png",
            default=valor_atual if valor_atual != "Não definido" else "",
            min_length=0,
            max_length=512,
            required=False
        )
        self.add_item(self.banner_input)

    async def on_submit(self, interaction: discord.Interaction):
        novo_banner = self.banner_input.value.strip() or None
        cfg = CloudStorage.get_guild_config(str(self.guild_id))
        cfg["painel"]["banner_url"] = novo_banner
        await CloudStorage.save_guild_config(str(self.guild_id), cfg)

        logger.info(f"Banner atualizado por {interaction.user} no servidor {self.guild_id}")
        await render_appearance_panel(interaction, self.guild_id, self.user_id, is_edit=True)


class ThumbnailModal(discord.ui.Modal, title="Configurar Thumbnail"):
    """Modal para inserir a miniatura/thumbnail do painel."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id

        cfg = CloudStorage.get_guild_config(str(guild_id))
        valor_atual = cfg.get("painel", {}).get("thumbnail_url") or ""

        self.thumbnail_input = discord.ui.TextInput(
            label="URL / Link da Imagem da Thumbnail",
            placeholder="https://exemplo.com/imagem_thumbnail.png",
            default=valor_atual if valor_atual != "Não definido" else "",
            min_length=0,
            max_length=512,
            required=False
        )
        self.add_item(self.thumbnail_input)

    async def on_submit(self, interaction: discord.Interaction):
        nova_thumb = self.thumbnail_input.value.strip() or None
        cfg = CloudStorage.get_guild_config(str(self.guild_id))
        cfg["painel"]["thumbnail_url"] = nova_thumb
        await CloudStorage.save_guild_config(str(self.guild_id), cfg)

        logger.info(f"Thumbnail atualizada por {interaction.user} no servidor {self.guild_id}")
        await render_appearance_panel(interaction, self.guild_id, self.user_id, is_edit=True)


# =====================================================================
# PAINEL DE SELEÇÃO DE COR DA EMBED (10 CORES)
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
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Você não tem permissão para alterar esta cor.", ephemeral=True)
            return

        cor_hex_val = self.values[0]
        cor_selecionada = next((c for c in CORES_DISPONIVEIS if c["value"] == cor_hex_val), None)

        if cor_selecionada:
            cfg = CloudStorage.get_guild_config(str(self.guild_id))
            cfg["painel"]["cor_hex"] = cor_selecionada["hex"]
            cfg["painel"]["cor"] = cor_selecionada["int"]
            await CloudStorage.save_guild_config(str(self.guild_id), cfg)
            logger.info(f"Cor da embed alterada por {interaction.user} para {cor_selecionada['hex']}")

            # Atualiza o painel de cor com a nova cor selecionada
            await render_cor_panel(interaction, self.guild_id, self.user_id, is_edit=True)


class CorEmbedView(discord.ui.View):
    """View do painel de cores com o select menu de 10 cores e botão de voltar."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.user_id = user_id

        # Adiciona o Select Menu das 10 cores
        self.add_item(CorEmbedSelect(guild_id, user_id))

        # Botão de voltar ao painel de aparência
        emoji_back = resolve_partial_emoji("back", "⬅️")
        btn_voltar = discord.ui.Button(
            label="Voltar para Aparência",
            emoji=emoji_back,
            style=discord.ButtonStyle.danger,
            custom_id="btn_cor_voltar_aparencia",
            row=1
        )
        btn_voltar.callback = self.on_voltar_click
        self.add_item(btn_voltar)

    async def on_voltar_click(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Você não tem permissão para interagir neste painel.", ephemeral=True)
            return
        await render_appearance_panel(interaction, self.guild_id, self.user_id, is_edit=True)


async def render_cor_panel(interaction: discord.Interaction, guild_id: int, user_id: int, is_edit: bool = False):
    """Renderiza a embed de seleção de cores."""
    cfg = CloudStorage.get_guild_config(str(guild_id))
    cor_atual_int = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT
    emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")

    description_text = (
        "## Configurar Cor da embed do painel de atendimento.\n\n"
        f"{emoji_info} Selecione a cor desejada usando o select menu abaixo."
    )

    embed = discord.Embed(
        description=description_text,
        color=cor_atual_int
    )
    view = CorEmbedView(guild_id, user_id)

    if is_edit:
        await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


# =====================================================================
# VIEW DE BOTÕES DO PAINEL DE APARÊNCIA
# =====================================================================

class AppearanceConfigView(discord.ui.View):
    """
    View de botões do painel de aparência.
    Botões: Título, Descrição, Banner, Thumbnail, Cor da embed e Voltar.
    """
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.user_id = user_id

        emoji_edit = resolve_partial_emoji("edit", "✏️")
        emoji_back = resolve_partial_emoji("back", "⬅️")

        # Botão 1: Título (abre TituloModal)
        btn_titulo = discord.ui.Button(
            label="Título",
            emoji=emoji_edit,
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_titulo",
            row=0
        )
        btn_titulo.callback = self.on_titulo_click
        self.add_item(btn_titulo)

        # Botão 2: Descrição (abre DescricaoModal)
        btn_descricao = discord.ui.Button(
            label="Descrição",
            emoji=emoji_edit,
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_descricao",
            row=0
        )
        btn_descricao.callback = self.on_descricao_click
        self.add_item(btn_descricao)

        # Botão 3: Banner (abre BannerModal)
        btn_banner = discord.ui.Button(
            label="Banner",
            emoji=emoji_edit,
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_banner",
            row=0
        )
        btn_banner.callback = self.on_banner_click
        self.add_item(btn_banner)

        # Botão 4: Thumbnail (abre ThumbnailModal)
        btn_thumbnail = discord.ui.Button(
            label="Thumbnail",
            emoji=emoji_edit,
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_thumbnail",
            row=1
        )
        btn_thumbnail.callback = self.on_thumbnail_click
        self.add_item(btn_thumbnail)

        # Botão 5: Cor da embed (abre painel com 10 cores)
        btn_cor = discord.ui.Button(
            label="Cor da embed",
            emoji=emoji_edit,
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_cor",
            row=1
        )
        btn_cor.callback = self.on_cor_click
        self.add_item(btn_cor)

        # Botão 6: Voltar ao menu principal
        btn_voltar = discord.ui.Button(
            label="Voltar",
            emoji=emoji_back,
            style=discord.ButtonStyle.danger,
            custom_id="btn_aparencia_voltar",
            row=1
        )
        btn_voltar.callback = self.on_voltar_click
        self.add_item(btn_voltar)

    async def on_titulo_click(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Você não tem permissão para interagir neste painel.", ephemeral=True)
            return
        await interaction.response.send_modal(TituloModal(self.guild_id, self.user_id))

    async def on_descricao_click(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Você não tem permissão para interagir neste painel.", ephemeral=True)
            return
        await interaction.response.send_modal(DescricaoModal(self.guild_id, self.user_id))

    async def on_banner_click(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Você não tem permissão para interagir neste painel.", ephemeral=True)
            return
        await interaction.response.send_modal(BannerModal(self.guild_id, self.user_id))

    async def on_thumbnail_click(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Você não tem permissão para interagir neste painel.", ephemeral=True)
            return
        await interaction.response.send_modal(ThumbnailModal(self.guild_id, self.user_id))

    async def on_cor_click(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Você não tem permissão para interagir neste painel.", ephemeral=True)
            return
        await render_cor_panel(interaction, self.guild_id, self.user_id, is_edit=True)

    async def on_voltar_click(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Você não tem permissão para interagir neste painel.", ephemeral=True)
            return

        text = format_main_panel_text()
        v2_view = build_main_components_v2_view(text, self.guild_id, self.user_id)
        if v2_view is not None:
            try:
                await interaction.response.edit_message(view=v2_view)
                return
            except Exception as e:
                logger.warning(f"Erro ao atualizar view v2: {e}")

        embed = discord.Embed(
            description=text,
            color=config.EMBED_COLOR_DEFAULT
        )
        std_view = PainelConfigStandardView(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=std_view)


async def render_appearance_panel(interaction: discord.Interaction, guild_id: int, user_id: int, is_edit: bool = True):
    """Função utilitária centralizada para renderizar o painel de aparência."""
    text = format_appearance_panel_text(str(guild_id))
    cfg = CloudStorage.get_guild_config(str(guild_id))
    cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT

    # Tenta via Componentes V2
    v2_view = build_appearance_components_v2_view(text, guild_id, user_id)
    if v2_view is not None:
        try:
            if is_edit:
                await interaction.response.edit_message(view=v2_view)
            else:
                await interaction.response.send_message(view=v2_view, ephemeral=True)
            return
        except Exception as e:
            logger.warning(f"Erro ao enviar aparência em v2: {e}")

    # Fallback padrão: Embed + View de botões
    embed = discord.Embed(
        description=text,
        color=cor_embed
    )
    view = AppearanceConfigView(guild_id, user_id)
    if is_edit:
        await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# =====================================================================
# SELECT MENU PRINCIPAL
# =====================================================================

class ConfigPainelSelect(discord.ui.Select):
    """
    Select Menu do painel principal de configuração.
    """
    def __init__(self, guild_id: int, user_id: int):
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
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Você não tem permissão para interagir neste painel.", ephemeral=True)
            return

        escolha = self.values[0] if self.values else ""

        if escolha == "aparencia":
            await render_appearance_panel(interaction, self.guild_id, self.user_id, is_edit=True)
            logger.info(f"Painel de aparência acessado por {interaction.user}")

        elif escolha == "configuracoes":
            logger.info(f"Opção 'Configurações do painel' selecionada por {interaction.user} (sem ação por enquanto).")
            await interaction.response.defer(ephemeral=True)


class PainelConfigStandardView(discord.ui.View):
    """View padrão do painel principal."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.user_id = user_id
        self.add_item(ConfigPainelSelect(guild_id, user_id))


# =====================================================================
# CONSTRUTORES DE COMPONENTES V2 (LayoutView & Container Type 17)
# =====================================================================

def build_main_components_v2_view(description_text: str, guild_id: int, user_id: int):
    """Constrói o LayoutView v2 com Container para o painel principal."""
    if not HAS_COMPONENTS_V2:
        return None

    try:
        layout_view = discord.ui.LayoutView(timeout=None)
        select_menu = ConfigPainelSelect(guild_id, user_id)

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = discord.ui.Separator(visible=True) if spacing_arg is None else discord.ui.Separator(visible=True, spacing=spacing_arg)

        container = discord.ui.Container(
            discord.ui.TextDisplay(description_text),
            separator,
            discord.ui.ActionRow(select_menu),
            accent_colour=config.EMBED_COLOR_DEFAULT
        )
        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Não foi possível instanciar LayoutView v2 principal: {e}")
        return None

def build_appearance_components_v2_view(description_text: str, guild_id: int, user_id: int):
    """Constrói o LayoutView v2 com Container para o painel de aparência."""
    if not HAS_COMPONENTS_V2:
        return None

    try:
        layout_view = discord.ui.LayoutView(timeout=None)
        cfg = CloudStorage.get_guild_config(str(guild_id))
        cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT

        emoji_edit = resolve_partial_emoji("edit", "✏️")
        emoji_back = resolve_partial_emoji("back", "⬅️")

        row1 = discord.ui.ActionRow(
            discord.ui.Button(label="Título", emoji=emoji_edit, style=discord.ButtonStyle.secondary, custom_id="btn_aparencia_titulo"),
            discord.ui.Button(label="Descrição", emoji=emoji_edit, style=discord.ButtonStyle.secondary, custom_id="btn_aparencia_descricao"),
            discord.ui.Button(label="Banner", emoji=emoji_edit, style=discord.ButtonStyle.secondary, custom_id="btn_aparencia_banner")
        )

        row2 = discord.ui.ActionRow(
            discord.ui.Button(label="Thumbnail", emoji=emoji_edit, style=discord.ButtonStyle.secondary, custom_id="btn_aparencia_thumbnail"),
            discord.ui.Button(label="Cor da embed", emoji=emoji_edit, style=discord.ButtonStyle.secondary, custom_id="btn_aparencia_cor"),
            discord.ui.Button(label="Voltar", emoji=emoji_back, style=discord.ButtonStyle.danger, custom_id="btn_aparencia_voltar")
        )

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None
        separator = discord.ui.Separator(visible=True) if spacing_arg is None else discord.ui.Separator(visible=True, spacing=spacing_arg)

        container = discord.ui.Container(
            discord.ui.TextDisplay(description_text),
            separator,
            row1,
            row2,
            accent_colour=cor_embed
        )
        layout_view.add_item(container)
        return layout_view
    except Exception as e:
        logger.warning(f"Não foi possível instanciar LayoutView v2 aparência: {e}")
        return None


# =====================================================================
# COMANDO /configurar painel
# =====================================================================

class ConfigurarGroup(app_commands.Group):
    """Grupo de comandos /configurar"""
    def __init__(self):
        super().__init__(name="configurar", description="Configurações do sistema de atendimento NiveSalers")

    @app_commands.command(
        name="painel",
        description="Abre o painel de configuração dos painéis de atendimento."
    )
    @app_commands.default_permissions(administrator=True)
    async def painel(self, interaction: discord.Interaction):
        """
        Abre o painel de configuração com Componentes V2 (Layouts & Containers),
        embed branca e o primeiro Select Menu dentro do layout.
        """
        guild_id = str(interaction.guild_id) if interaction.guild_id else "direct"
        CloudStorage.get_guild_config(guild_id)

        description_text = format_main_panel_text()

        # Tenta enviar com Componentes V2
        v2_view = build_main_components_v2_view(description_text, interaction.guild_id or 0, interaction.user.id)
        if v2_view is not None:
            try:
                await interaction.response.send_message(
                    view=v2_view,
                    ephemeral=True
                )
                logger.info(f"Painel enviado via Componentes V2 (Container) para {interaction.user}")
                return
            except Exception as e:
                logger.warning(f"Falha ao enviar via Components V2 direto: {e}. Usando embed + view.")

        # Fallback padrão: Embed branca + ActionRow View com o Select Menu
        embed = discord.Embed(
            description=description_text,
            color=config.EMBED_COLOR_DEFAULT
        )

        std_view = PainelConfigStandardView(
            guild_id=interaction.guild_id or 0,
            user_id=interaction.user.id
        )

        await interaction.response.send_message(
            embed=embed,
            view=std_view,
            ephemeral=True
        )
        logger.info(f"Painel enviado para {interaction.user} no servidor {interaction.guild_id}")

class TicketPanelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.configurar_group = ConfigurarGroup()
        self.bot.tree.add_command(self.configurar_group)

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketPanelCog(bot))
