"""
NiveSalers - Ticket Configuration Panel Cog
Comando /configurar painel com botões persistentes, modals interativos
e seletor de 10 cores com callbacks garantidos e robustos.
"""
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict, Any

import config
from utils.logger import logger
from utils.emoji_manager import EmojiManager
from database.cloud_storage import CloudStorage

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

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Erro no modal de banner: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Ocorreu um erro ao salvar o banner: {error}", ephemeral=True)


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

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Erro no modal de thumbnail: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Ocorreu um erro ao salvar a thumbnail: {error}", ephemeral=True)


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
        # Validação de permissões: não bloqueia se for administrador
        if self.user_id and interaction.user.id != self.user_id and not getattr(interaction.user.guild_permissions, "administrator", False):
            await interaction.response.send_message("Apenas administradores podem configurar este painel.", ephemeral=True)
            return

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


class CorEmbedView(discord.ui.View):
    """View do painel de cores com o select menu de 10 cores e botão de voltar."""
    def __init__(self, guild_id: int = 0, user_id: int = 0):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.user_id = user_id

        self.add_item(CorEmbedSelect(guild_id, user_id))

    @discord.ui.button(
        label="Voltar para Aparência",
        style=discord.ButtonStyle.danger,
        custom_id="btn_cor_voltar_aparencia",
        row=1
    )
    async def btn_voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"Usuário {interaction.user} voltou para o painel de aparência a partir de cores.")
        await render_appearance_panel(interaction, self.guild_id or (interaction.guild_id or 0), self.user_id or interaction.user.id, is_edit=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        logger.error(f"Erro na view de cores no componente {getattr(item, 'custom_id', item)}: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message("Ocorreu um erro ao processar a cor.", ephemeral=True)


async def render_cor_panel(interaction: discord.Interaction, guild_id: int, user_id: int, is_edit: bool = False):
    """Renderiza a embed de seleção de cores."""
    gid = str(guild_id or (interaction.guild_id or "direct"))
    cfg = CloudStorage.get_guild_config(gid)
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

    try:
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.edit_original_response(embed=embed, view=view)
    except Exception as e:
        logger.error(f"Erro ao renderizar painel de cores: {e}")
        try:
            if interaction.message:
                await interaction.message.edit(embed=embed, view=view)
        except Exception:
            pass


# =====================================================================
# VIEW DE BOTÕES DO PAINEL DE APARÊNCIA (ROBUSTA & PERSISTENTE)
# =====================================================================

class AppearanceConfigView(discord.ui.View):
    """
    View de botões do painel de aparência.
    Botões: Título, Descrição, Banner, Thumbnail, Cor da embed e Voltar.
    Implementados com o decorator @discord.ui.button para resposta instantânea garantida.
    """
    def __init__(self, guild_id: int = 0, user_id: int = 0):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.user_id = user_id

        # Atribuição segura dos emojis aos botões
        emoji_edit = resolve_partial_emoji("edit", "✏️")
        emoji_back = resolve_partial_emoji("back", "⬅️")

        self.btn_titulo.emoji = emoji_edit
        self.btn_descricao.emoji = emoji_edit
        self.btn_banner.emoji = emoji_edit
        self.btn_thumbnail.emoji = emoji_edit
        self.btn_cor.emoji = emoji_edit
        self.btn_voltar.emoji = emoji_back

    @discord.ui.button(
        label="Título",
        style=discord.ButtonStyle.secondary,
        custom_id="btn_aparencia_titulo",
        row=0
    )
    async def btn_titulo(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"Botão 'Título' acionado por {interaction.user}")
        gid = self.guild_id or (interaction.guild_id or 0)
        await interaction.response.send_modal(TituloModal(gid, interaction.user.id))

    @discord.ui.button(
        label="Descrição",
        style=discord.ButtonStyle.secondary,
        custom_id="btn_aparencia_descricao",
        row=0
    )
    async def btn_descricao(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"Botão 'Descrição' acionado por {interaction.user}")
        gid = self.guild_id or (interaction.guild_id or 0)
        await interaction.response.send_modal(DescricaoModal(gid, interaction.user.id))

    @discord.ui.button(
        label="Banner",
        style=discord.ButtonStyle.secondary,
        custom_id="btn_aparencia_banner",
        row=0
    )
    async def btn_banner(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"Botão 'Banner' acionado por {interaction.user}")
        gid = self.guild_id or (interaction.guild_id or 0)
        await interaction.response.send_modal(BannerModal(gid, interaction.user.id))

    @discord.ui.button(
        label="Thumbnail",
        style=discord.ButtonStyle.secondary,
        custom_id="btn_aparencia_thumbnail",
        row=1
    )
    async def btn_thumbnail(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"Botão 'Thumbnail' acionado por {interaction.user}")
        gid = self.guild_id or (interaction.guild_id or 0)
        await interaction.response.send_modal(ThumbnailModal(gid, interaction.user.id))

    @discord.ui.button(
        label="Cor da embed",
        style=discord.ButtonStyle.secondary,
        custom_id="btn_aparencia_cor",
        row=1
    )
    async def btn_cor(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"Botão 'Cor da embed' acionado por {interaction.user}")
        gid = self.guild_id or (interaction.guild_id or 0)
        await render_cor_panel(interaction, gid, interaction.user.id, is_edit=True)

    @discord.ui.button(
        label="Voltar",
        style=discord.ButtonStyle.danger,
        custom_id="btn_aparencia_voltar",
        row=1
    )
    async def btn_voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"Botão 'Voltar' acionado por {interaction.user}")
        gid = self.guild_id or (interaction.guild_id or 0)
        text = format_main_panel_text()
        embed = discord.Embed(
            description=text,
            color=config.EMBED_COLOR_DEFAULT
        )
        std_view = PainelConfigStandardView(gid, interaction.user.id)
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=std_view)
        else:
            await interaction.edit_original_response(embed=embed, view=std_view)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        logger.error(f"Erro no botão {getattr(item, 'custom_id', item)}: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Ocorreu um erro ao processar o botão: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"Ocorreu um erro ao processar o botão: {error}", ephemeral=True)


async def render_appearance_panel(interaction: discord.Interaction, guild_id: int, user_id: int = 0, is_edit: bool = True):
    """Função utilitária centralizada para renderizar o painel de aparência."""
    gid = str(guild_id or (interaction.guild_id or "direct"))
    text = format_appearance_panel_text(gid)
    cfg = CloudStorage.get_guild_config(gid)
    cor_embed = cfg.get("painel", {}).get("cor") or config.EMBED_COLOR_DEFAULT

    embed = discord.Embed(
        description=text,
        color=cor_embed
    )
    view = AppearanceConfigView(int(guild_id) if str(guild_id).isdigit() else 0, user_id or interaction.user.id)

    try:
        if is_edit:
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.edit_original_response(embed=embed, view=view)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    except Exception as e:
        logger.error(f"Erro ao renderizar painel de aparência: {e}")
        try:
            if interaction.message:
                await interaction.message.edit(embed=embed, view=view)
        except Exception as e2:
            logger.error(f"Falha secundária ao editar mensagem: {e2}")


# =====================================================================
# SELECT MENU PRINCIPAL
# =====================================================================

class ConfigPainelSelect(discord.ui.Select):
    """
    Select Menu do painel principal de configuração.
    """
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


class PainelConfigStandardView(discord.ui.View):
    """View padrão do painel principal."""
    def __init__(self, guild_id: int = 0, user_id: int = 0):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.user_id = user_id
        self.add_item(ConfigPainelSelect(guild_id, user_id))


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
        Abre o painel de configuração com embed branca e o Select Menu principal.
        """
        guild_id = str(interaction.guild_id) if interaction.guild_id else "direct"
        CloudStorage.get_guild_config(guild_id)

        description_text = format_main_panel_text()

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
    # Registra as views persistentes no bot para garantir que qualquer clique responda imediatamente
    bot.add_view(AppearanceConfigView())
    bot.add_view(CorEmbedView())
    bot.add_view(PainelConfigStandardView())
    await bot.add_cog(TicketPanelCog(bot))
