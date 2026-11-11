"""
NiveSalers - Ticket Configuration Panel Cog
Comando /configurar painel com embed branca e estrutura pronta para Componentes v2 (Layouts/Containers).
"""
import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.logger import logger
from utils.emoji_manager import EmojiManager
from database.cloud_storage import CloudStorage

class PainelConfigContainerView(discord.ui.View):
    """
    View base preparada para a arquitetura de Componentes v2 (Layouts e Containers).
    Conforme as diretrizes iniciais, nenhum botão é adicionado nesta etapa,
    deixando a estrutura pronta para a injeção modular dos primeiros botões na próxima fase.
    """
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.user_id = user_id
        # Layouts e Containers v2 serão inseridos aqui nas próximas etapas

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
        Abre o painel de configuração com a embed branca solicitada
        e os emojis sincronizados via Discord API.
        """
        # Garante que o storage do servidor esteja inicializado
        guild_id = str(interaction.guild_id) if interaction.guild_id else "direct"
        guild_cfg = CloudStorage.get_guild_config(guild_id)

        # Resolução dinâmica dos emojis (utiliza Application Emojis ou tags exatas)
        emoji_bot = EmojiManager.get("bot", fallback="<:bot:1557140838285582438>")
        emoji_info = EmojiManager.get("information", fallback="<:information:1561907852124225599>")
        emoji_cloud = EmojiManager.get("cloud", fallback="<:cloud:1561906158984233031>")
        emoji_reload = EmojiManager.get("reload", fallback="<:reload:1561908806584115210>")

        # Montagem do conteúdo exato especificado
        description_lines = [
            f"## {emoji_bot} Painel de configuração dos painéis de atendimento",
            f"{emoji_info} Selecione uma opção para configurar no painel.",
            f"{emoji_cloud} Todas as configurações serão salvas imediatamente no sistema de atendimento.",
            f"{emoji_reload} Com atualização automática de painéis de atendimento existentes."
        ]
        description_text = "\n".join(description_lines)

        # Embed branca (0xFFFFFF)
        embed = discord.Embed(
            description=description_text,
            color=config.EMBED_COLOR_DEFAULT
        )

        # Prepara a view (sem botões ainda, conforme instrução explícita)
        view = PainelConfigContainerView(
            guild_id=interaction.guild_id or 0,
            user_id=interaction.user.id
        )

        # Envio da resposta ao usuário
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )
        logger.info(f"Painel de configuração aberto por {interaction.user} no servidor {interaction.guild_id}")

class TicketPanelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Registra o grupo /configurar
        self.configurar_group = ConfigurarGroup()
        self.bot.tree.add_command(self.configurar_group)

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketPanelCog(bot))
