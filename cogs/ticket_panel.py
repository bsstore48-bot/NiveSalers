"""
NiveSalers - Ticket Configuration Panel Cog
Comando /configurar painel com Componentes v2 (Layouts & Containers)
e painel de configuração de aparência com botões sem ação inicial.
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
# TELAS E COMPONENTES DE APARÊNCIA
# =====================================================================

class AppearanceConfigView(discord.ui.View):
    """
    View de botões do painel de aparência.
    Botões: Título, Descrição, Banner, Thumbnail, Cor da embed e Voltar.
    Todos sem ação por enquanto, conforme solicitado.
    """
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.user_id = user_id

        # O emoji solicitado para os botões é o mesmo de Título (<:edit:...>)
        emoji_edit = resolve_partial_emoji("edit", "✏️")
        emoji_back = resolve_partial_emoji("back", "⬅️")

        # Botão 1: Título
        btn_titulo = discord.ui.Button(
            label="Título",
            emoji=emoji_edit,
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_titulo",
            row=0
        )
        btn_titulo.callback = self.on_dummy_click
        self.add_item(btn_titulo)

        # Botão 2: Descrição
        btn_descricao = discord.ui.Button(
            label="Descrição",
            emoji=emoji_edit,
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_descricao",
            row=0
        )
        btn_descricao.callback = self.on_dummy_click
        self.add_item(btn_descricao)

        # Botão 3: Banner
        btn_banner = discord.ui.Button(
            label="Banner",
            emoji=emoji_edit,
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_banner",
            row=0
        )
        btn_banner.callback = self.on_dummy_click
        self.add_item(btn_banner)

        # Botão 4: Thumbnail
        btn_thumbnail = discord.ui.Button(
            label="Thumbnail",
            emoji=emoji_edit,
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_thumbnail",
            row=1
        )
        btn_thumbnail.callback = self.on_dummy_click
        self.add_item(btn_thumbnail)

        # Botão 5: Cor da embed
        btn_cor = discord.ui.Button(
            label="Cor da embed",
            emoji=emoji_edit,
            style=discord.ButtonStyle.secondary,
            custom_id="btn_aparencia_cor",
            row=1
        )
        btn_cor.callback = self.on_dummy_click
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

    async def on_dummy_click(self, interaction: discord.Interaction):
        """Ações sem efeito por enquanto, conforme solicitado."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Você não tem permissão para interagir neste painel.", ephemeral=True)
            return
        logger.info(f"Botão de aparência clicado por {interaction.user}: {interaction.data.get('custom_id')} (sem ação por enquanto).")
        await interaction.response.defer(ephemeral=True)

    async def on_voltar_click(self, interaction: discord.Interaction):
        """Retorna ao painel principal /configurar painel."""
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


# =====================================================================
# SELECT MENU PRINCIPAL
# =====================================================================

class ConfigPainelSelect(discord.ui.Select):
    """
    Primeiro Select Menu do painel de atendimento.
    Placeholder: Selecione uma opção para configurar.
    Opções: Aparência do painel e Configurações do painel.
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
            # Abre o painel de configuração da aparência solicitado
            guild_id_str = str(self.guild_id) if self.guild_id else "direct"
            text = format_appearance_panel_text(guild_id_str)

            # Tenta via Componentes V2
            v2_view = build_appearance_components_v2_view(text, self.guild_id, self.user_id)
            if v2_view is not None:
                try:
                    await interaction.response.edit_message(view=v2_view)
                    logger.info(f"Painel de aparência aberto (v2) para {interaction.user}")
                    return
                except Exception as e:
                    logger.warning(f"Erro ao abrir aparência em v2: {e}")

            # Fallback padrão: Embed branca + ActionRows
            embed = discord.Embed(
                description=text,
                color=config.EMBED_COLOR_DEFAULT
            )
            view = AppearanceConfigView(self.guild_id, self.user_id)
            await interaction.response.edit_message(embed=embed, view=view)
            logger.info(f"Painel de aparência aberto para {interaction.user}")

        elif escolha == "configuracoes":
            # Configurações do painel sem ação por enquanto
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
            accent_colour=config.EMBED_COLOR_DEFAULT
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

        # Tenta enviar com Componentes V2 (LayoutView + Container Type 17)
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
