"""
NiveSalers - Ticket Configuration Panel Cog
Comando /configurar painel com Componentes v2 (Layouts & Containers)
e Select Menu dentro do layout do painel.
"""
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

import config
from utils.logger import logger
from utils.emoji_manager import EmojiManager
from database.cloud_storage import CloudStorage

# Detecção dinâmica de suporte a Componentes v2 no discord.py (LayoutView e Container)
HAS_COMPONENTS_V2 = hasattr(discord.ui, "LayoutView") and hasattr(discord.ui, "Container")

class ConfigPainelSelect(discord.ui.Select):
    """
    Primeiro Select Menu do painel de atendimento.
    Placeholder: Selecione uma opção para configurar.
    Opções: Aparência do painel e Configurações do painel.
    Ambas sem ação por enquanto, conforme solicitado.
    """
    def __init__(self):
        # Resolve emojis de suporte (com fallback Unicode se necessário)
        emoji_aparencia = None
        emoji_config = None
        try:
            aparencia_str = EmojiManager.get("paint", fallback="🎨")
            config_str = EmojiManager.get("settings", fallback="⚙️")
            
            # Se for string customizada <:name:id>, converte em PartialEmoji
            if aparencia_str.startswith("<") and aparencia_str.endswith(">"):
                emoji_aparencia = discord.PartialEmoji.from_str(aparencia_str)
            else:
                emoji_aparencia = aparencia_str

            if config_str.startswith("<") and config_str.endswith(">"):
                emoji_config = discord.PartialEmoji.from_str(config_str)
            else:
                emoji_config = config_str
        except Exception:
            emoji_aparencia = "🎨"
            emoji_config = "⚙️"

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
        """
        Ambas as opções sem ação por enquanto, conforme instruído.
        Apenas confirma a interação de forma silenciosa e segura.
        """
        escolha = self.values[0] if self.values else "nenhuma"
        logger.info(f"Usuário {interaction.user} selecionou a opção '{escolha}' (sem ação por enquanto).")
        await interaction.response.defer(ephemeral=True)

class PainelConfigStandardView(discord.ui.View):
    """
    View padrão compatível com Discord API, organizando o Select Menu
    em um ActionRow estruturado.
    """
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.user_id = user_id
        # Adiciona o primeiro select menu
        self.add_item(ConfigPainelSelect())

def build_components_v2_view(description_text: str, guild_id: int, user_id: int):
    """
    Constrói a estrutura de LayoutView e Container (Componentes V2 - Type 17).
    Envolve o TextDisplay, Separator e ActionRow com o Select Menu dentro do card/container.
    """
    if not HAS_COMPONENTS_V2:
        return None

    try:
        layout_view = discord.ui.LayoutView(timeout=None)
        select_menu = ConfigPainelSelect()

        separator_spacing = getattr(discord, "SeparatorSpacing", None)
        spacing_arg = separator_spacing.small if separator_spacing else None

        # Container (Type 17) contendo os componentes filhos
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
        logger.warning(f"Não foi possível instanciar LayoutView v2: {e}. Usando fallback.")
        return None

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
        # Garante a persistência do servidor na nuvem
        guild_id = str(interaction.guild_id) if interaction.guild_id else "direct"
        CloudStorage.get_guild_config(guild_id)

        # Resolução dos emojis
        emoji_bot = EmojiManager.get("bot", fallback="<:bot:1557140838285582438>")
        emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")
        emoji_cloud = EmojiManager.get("cloud", fallback="<:cloud:1561906158984233031>")
        emoji_reload = EmojiManager.get("reload", fallback="<:reload:1561908806584115210>")

        # Texto padronizado
        description_lines = [
            f"## {emoji_bot} Painel de configuração dos painéis de atendimento",
            f"{emoji_info} Selecione uma opção para configurar no painel.",
            f"{emoji_cloud} Todas as configurações serão salvas imediatamente no sistema de atendimento.",
            f"{emoji_reload} Com atualização automática de painéis de atendimento existentes."
        ]
        description_text = "\n".join(description_lines)

        # Tenta enviar com Componentes V2 (LayoutView + Container Type 17)
        v2_view = build_components_v2_view(description_text, interaction.guild_id or 0, interaction.user.id)
        if v2_view is not None:
            try:
                await interaction.response.send_message(
                    view=v2_view,
                    ephemeral=True
                )
                logger.info(f"Painel enviado via Componentes V2 (Container) para {interaction.user}")
                return
            except Exception as e:
                logger.warning(f"Falha ao enviar via Components V2 direto: {e}. Enviando via embed + view container.")

        # Fallback: Embed branca (0xFFFFFF) + ActionRow View com o Select Menu
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
