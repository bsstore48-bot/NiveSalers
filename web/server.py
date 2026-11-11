"""
NiveSalers - Embedded HTTP Server
Servidor HTTP assíncrono para hospedagem no Render.
Mantém o serviço ativo respondendo na porta designada ($PORT) e expõe rotas de status/healthcheck.
"""
import os
import time
from typing import Optional
from aiohttp import web
import asyncio

import config
from utils.logger import logger

_start_time = time.time()
_bot_ref = None

async def handle_root(request: web.Request) -> web.Response:
    uptime_seconds = int(time.time() - _start_time)
    bot_user = str(_bot_ref.user) if _bot_ref and _bot_ref.user else "Conectando..."
    guild_count = len(_bot_ref.guilds) if _bot_ref else 0
    latency_ms = round(_bot_ref.latency * 1000, 2) if _bot_ref and _bot_ref.latency else 0

    data = {
        "status": "online",
        "service": "NiveSalers Ticket Bot",
        "bot_user": bot_user,
        "guilds": guild_count,
        "latency_ms": latency_ms,
        "uptime_seconds": uptime_seconds,
        "environment": "Render Cloud"
    }
    return web.json_response(data)

async def handle_health(request: web.Request) -> web.Response:
    return web.Response(text="OK", status=200)

async def start_web_server(bot=None) -> Optional[web.AppRunner]:
    """Inicia o servidor HTTP embutido de forma assíncrona."""
    global _bot_ref
    _bot_ref = bot

    port = int(os.environ.get("PORT", config.PORT))
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/ping", handle_health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    try:
        await site.start()
        logger.info(f"🌐 Servidor HTTP embutido iniciado com sucesso na porta {port} (0.0.0.0:{port}).")
        return runner
    except Exception as e:
        logger.error(f"Erro ao iniciar servidor HTTP na porta {port}: {e}")
        return None
