"""Comando /ping do NiveSalers."""
import time
import discord
from discord import app_commands
from discord.ext import commands


class Ping(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Verifica a latência e o estado do NiveSalers.")
    async def ping(self, interaction: discord.Interaction):
        started = time.perf_counter()
        ws_ms = round(self.bot.latency * 1000, 1)
        interaction_ms = round((discord.utils.utcnow() - interaction.created_at).total_seconds() * 1000, 1)

        if ws_ms < 100:
            color = discord.Color.green()
            health = "Excelente"
        elif ws_ms < 200:
            color = discord.Color.gold()
            health = "Bom"
        elif ws_ms <  400:
            color = discord.Color.orange()
            health = "Instável"
        else:
            color = discord.Color.red()
            health = "Alto"

        embed = discord.Embed(
            title="🏓 Pong! NiveSalers está online",
            description=f"**Estado:** {health}",
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="🌐 Latência Gateway", value=f"`{ws_ms} ms`", inline=True)
        embed.add_field(name="⚡ Resposta Discord", value=f"`{interaction_ms} ms`", inline=True)
        embed.add_field(name="🖥️ Servidores", value=f"`{len(self.bot.guilds)}`", inline=True)
        if self.bot.shard_count:
            embed.add_field(name="🔀 Shards", value=f"`{self.bot.shard_count}`", inline=True)
        embed.set_footer(text="NiveSalers • Monitoramento")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Ping(bot))
