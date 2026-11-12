"""
NiveSalers - Discord Tickets Bot
Sistema em Python com servidor HTTP embutido, persistência em nuvem (Render)
e suporte a Application Emojis via Discord API v10.
"""
import os
import sys
import asyncio
import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.logger import logger
from utils.emoji_manager import EmojiManager
from database.cloud_storage import CloudStorage
from web.server import start_web_server

# Intents necessárias
intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    application_id=int(config.APPLICATION_ID) if config.APPLICATION_ID.isdigit() else None
)

@bot.event
async def on_ready():
    logger.info("=" * 60)
    logger.info(f"🚀 Bot inicializado com sucesso: {bot.user} (ID: {bot.user.id})")
    logger.info(f"🌐 Servidores conectados: {len(bot.guilds)}")
    logger.info("=" * 60)

    # 1. Atividade personalizada
    try:
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="atendimentos | /configurar"
        )
        await bot.change_presence(status=discord.Status.online, activity=activity)
    except Exception as e:
        logger.warning(f"Não foi possível definir presença: {e}")

    # 2. Sincronização automática dos Application Emojis via Discord API
    app_id = str(bot.application_id or bot.user.id)
    token = config.DISCORD_TOKEN
    if token and app_id:
        logger.info(f"Iniciando sincronização de Application Emojis para o bot (App ID: {app_id})...")
        asyncio.create_task(EmojiManager.sync_application_emojis(token, app_id))

    # 3. Sincroniza Slash Commands globalmente
    try:
        synced = await bot.tree.sync()
        logger.info(f"⚡ {len(synced)} comando(s) slash sincronizados globalmente com sucesso!")
    except Exception as e:
        logger.error(f"Erro ao sincronizar comandos slash: {e}")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    logger.error(f"Erro na execução do comando {interaction.command}: {error}", exc_info=True)
    try:
        msg = f"Ocorreu um erro ao processar: {error}"
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)
    except Exception:
        pass

async def load_extensions():
    """Carrega as cogs do bot."""
    cogs = ["cogs.ticket_panel", "cogs.ping"]
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            logger.info(f"📦 Módulo carregado: {cog}")
        except Exception as e:
            logger.error(f"Erro ao carregar módulo {cog}: {e}")

async def main():
    # 1. Inicializa persistência em nuvem (carrega backups e conexões)
    await CloudStorage.initialize()

    # 2. Inicia servidor HTTP embutido para o Render ($PORT)
    await start_web_server(bot)

    # 3. Carrega cogs
    await load_extensions()

    # 4. Inicia o bot
    token = config.DISCORD_TOKEN
    if not token:
        logger.warning("DISCORD_TOKEN não encontrado no ambiente. O servidor HTTP continuará rodando para manter o Render ativo.")
        while True:
            await asyncio.sleep(3600)

    try:
        await bot.start(token)
    except discord.LoginFailure:
        logger.critical("Falha de autenticação: DISCORD_TOKEN inválido.")
    except Exception as e:
        logger.critical(f"Erro fatal na inicialização do bot: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot encerrado pelo usuário.")
