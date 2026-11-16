import os
import atexit
import signal
import threading
import asyncio
import gradio as gr
import spaces
import discord

import config
from utils.logger import logger
from database.cloud_storage import CloudStorage
from main import bot, load_extensions

_bot_lock = threading.Lock()
_bot_thread_started = False


async def start_discord_bot():
    await CloudStorage.initialize()
    await load_extensions()

    token = config.DISCORD_TOKEN
    if not token:
        logger.warning('DISCORD_TOKEN não definido nas variáveis/secrets do Space.')
        return

    try:
        await bot.start(token)
    except discord.LoginFailure:
        logger.critical('Falha de autenticação: DISCORD_TOKEN inválido.')
    except Exception as e:
        logger.critical(f'Erro fatal no bot: {e}')


def run_bot_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(start_discord_bot())
    finally:
        CloudStorage.flush_sync()


def _ensure_bot_started():
    global _bot_thread_started
    with _bot_lock:
        if not _bot_thread_started:
            _bot_thread_started = True
            threading.Thread(target=run_bot_thread, daemon=True, name='discord-bot-thread').start()


def _on_shutdown(*_args):
    CloudStorage.flush_sync()


atexit.register(_on_shutdown)
try:
    signal.signal(signal.SIGTERM, _on_shutdown)
except Exception:
    pass

_ensure_bot_started()


def get_status():
    if bot.user:
        return f'Online como {bot.user} | Servidores: {len(bot.guilds)} | Latência: {round(bot.latency * 1000)}ms'
    return 'Iniciando conexão com o Discord (verifique DISCORD_TOKEN nos Secrets do Space)...'


@spaces.GPU
def gpu_ping():
    return get_status()


with gr.Blocks(title='NiveSalers Bot') as demo:
    gr.Markdown('# NiveSalers Discord Bot')
    status_box = gr.Textbox(label='Status', value=get_status, interactive=False)
    refresh_btn = gr.Button('Atualizar Status')
    refresh_btn.click(fn=get_status, outputs=status_box)
    diag_btn = gr.Button('Diagnóstico')
    diag_btn.click(fn=gpu_ping, outputs=status_box)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7860))
    demo.launch(server_name='0.0.0.0', server_port=port)
