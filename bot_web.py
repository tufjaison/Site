from telethon import TelegramClient, events
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.types import InputMessagesFilterVideo, InputPeerEmpty
import asyncio
from datetime import datetime, timedelta
import traceback
from flask import Flask
import threading
import os

# ==============================================
# CONFIGURAÇÕES — PODERÃO VIR DO RENDER DEPOIS
# ==============================================
API_ID = int(os.environ.get('API_ID', 30406487))
API_HASH = os.environ.get('API_HASH', 'ccfb152c69274a0424526084b7f96d28')
NUMERO_CONTA = os.environ.get('NUMERO_CONTA', '+5585992531589')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8812502952:AAGrFBp0oRatlCuHKpuRmqe794-e3CGi13Q')
LIMITE_RESULTADOS = 10
SEU_ID_TELEGRAM = int(os.environ.get('SEU_ID_TELEGRAM', 7637629980))

# ==============================================
# CLIENTES
# ==============================================
conta_busca = TelegramClient(
    'sessao_conta_busca',
    API_ID,
    API_HASH,
    connection_retries=5
)

bot = TelegramClient(
    'sessao_bot',
    API_ID,
    API_HASH,
    connection_retries=5
)

# ==============================================
# ENVIAR ERROS PARA O TELEGRAM
# ==============================================
async def enviar_erro_para_bot(descricao: str, excecao: Exception = None):
    mensagem = f"❌ ERRO — {descricao}\n"
    if excecao:
        mensagem += f"Tipo: {type(excecao).__name__}\n"
        mensagem += f"Detalhe: {str(excecao)}\n"
        rastreamento = traceback.format_exc()
        if len(rastreamento) > 1500:
            rastreamento = rastreamento[:1500] + "\n...[truncado]"
        mensagem += f"\n📋 Rastreamento:\n{rastreamento}"
    print(mensagem)
    try:
        await bot.send_message(SEU_ID_TELEGRAM, mensagem)
    except:
        try:
            await conta_busca.send_message(SEU_ID_TELEGRAM, mensagem)
        except:
            print("⚠️ Não foi possível enviar mensagem de erro")

# ==============================================
# FUNÇÃO DE BUSCA
# ==============================================
async def buscar_videos_globais(termo: str, limite: int = LIMITE_RESULTADOS):
    print(f"🔍 Buscando: '{termo}'")
    try:
        data_limite = datetime.now()
        data_inicio = data_limite - timedelta(days=365*10)
        resultado = await conta_busca(SearchGlobalRequest(
            q=termo,
            filter=InputMessagesFilterVideo(),
            broadcasts_only=True,
            limit=limite,
            min_date=data_inicio,
            max_date=data_limite,
            offset_rate=0,
            offset_peer=InputPeerEmpty(),
            offset_id=0
        ))
        videos = []
        for msg in resultado.messages:
            canal = None
            try:
                canal = await conta_busca.get_entity(msg.peer_id)
            except:
                continue
            link = None
            if canal:
                if hasattr(canal, 'username') and canal.username:
                    link = f"https://t.me/{canal.username}/{msg.id}"
                else:
                    canal_id = str(canal.id).replace('-100', '')
                    link = f"https://t.me/c/{canal_id}/{msg.id}"
            legenda = msg.message or "Vídeo sem legenda"
            if len(legenda) > 80:
                legenda = legenda[:77] + "..."
            duracao = "??:??"
            if msg.video:
                m, s = divmod(msg.video.duration, 60)
                duracao = f"{m}:{s:02d}"
            videos.append({
                'legenda': legenda,
                'canal': canal.title if canal else 'Canal desconhecido',
                'link': link,
                'duracao': duracao
            })
        return videos
    except Exception as e:
        await enviar_erro_para_bot(f"Busca falhou: '{termo}'", e)
        return []

# ==============================================
# COMANDOS DO BOT
# ==============================================
@bot.on(events.NewMessage(pattern='/start'))
async def inicio(event):
    await event.reply(
        "🎬 Busca Global de Vídeos Telegram\n\n"
        "Comandos:\n"
        "/buscar [termo] — Busca vídeos em canais públicos\n"
        "Exemplo: /buscar receitas"
    )

@bot.on(events.NewMessage(pattern='/buscar'))
async def comando_buscar(event):
    try:
        texto = event.raw_text
        partes = texto.split(maxsplit=1)
        if len(partes) < 2:
            await event.reply("⚠️ Exemplo: /buscar futebol")
            return
        termo = partes[1].strip()
        msg_aguarde = await event.reply(f"🔍 Buscando: **{termo}**...")
        videos = await buscar_videos_globais(termo)
        if not videos:
            await msg_aguarde.edit(
                f"❌ Nenhum vídeo encontrado para: **{termo}**",
                parse_mode='markdown'
            )
            return
        resposta = f"🎬 **{len(videos)} vídeo(s):**\n\n"
        for i, v in enumerate(videos, 1):
            resposta += f"{i}. [{v['legenda']}]({v['link']})\n"
            resposta += f"📢 {v['canal']}  |  ⏱️ {v['duracao']}\n\n"
        await msg_aguarde.edit(resposta, parse_mode='markdown', link_preview=False)
    except Exception as e:
        await enviar_erro_para_bot("Falha no comando /buscar", e)

# ==============================================
# SERVIDOR WEB + BOT
# ==============================================
app = Flask(__name__)
bot_iniciado = False

async def iniciar_bot():
    global bot_iniciado
    if bot_iniciado:
        print("⚠️ Bot já está rodando")
        return
    try:
        print("🔌 Conectando conta de busca...")
        await conta_busca.start(NUMERO_CONTA)
        print("✅ Conta de busca conectada")

        print("🤖 Conectando bot...")
        await bot.start(bot_token=BOT_TOKEN)
        print("✅ Bot online")

        try:
            await bot.send_message(SEU_ID_TELEGRAM, "bot iniciado")
            print("📤 Mensagem enviada: bot iniciado")
        except:
            print("⚠️ Envie /start ao bot primeiro no Telegram")

        bot_iniciado = True
        print("👂 Aguardando comandos...")
        await bot.run_until_disconnected()

    except Exception as e:
        print(f"❌ Erro fatal: {type(e).__name__}: {e}")
        await enviar_erro_para_bot("ERRO FATAL — Sistema parou", e)

@app.route('/')
def home():
    status = "✅ Bot Ativo — Rodando!" if bot_iniciado else "⏳ Carregando... aguarde"
    return status, 200

def run_bot_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(iniciar_bot())
    except Exception as e:
        print(f"❌ Loop do bot parou: {e}")

# Inicia o bot em thread separada
if not bot_iniciado:
    threading.Thread(target=run_bot_loop, daemon=True).start()
    print("🚀 Sistema iniciado em segundo plano")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
