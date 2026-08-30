from telethon import TelegramClient, events
from telethon.tl.functions.messages import SearchGlobalRequest, SearchRequest
from telethon.tl.types import InputMessagesFilterVideo, InputPeerEmpty, InputPeerChannel
import asyncio
from datetime import datetime, timedelta
import traceback
from flask import Flask
import threading
import os

# ==============================================
# CONFIGURAÇÕES
# ==============================================
API_ID = int(os.environ.get('API_ID', 30406487))
API_HASH = os.environ.get('API_HASH', 'ccfb152c69274a0424526084b7f96d28')
NUMERO_CONTA = os.environ.get('NUMERO_CONTA', '+5585992531589')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8812502952:AAGrFBp0oRatlCuHKpuRmqe794-e3CGi13Q')
LIMITE_RESULTADOS = 15
SEU_ID_TELEGRAM = int(os.environ.get('SEU_ID_TELEGRAM', 7637629980))

# ==============================================
# CANAIS ALVOS CONHECIDOS — Busca direta para mais resultados
# ==============================================
CANAIS_CONHECIDOS = [
    # Adicione canais que você sabe que postam vídeos sobre os temas
    # Exemplo: '@nome_do_canal'
]

# ==============================================
# SINÔNIMOS E VARIAÇÕES — Busca mais ampla
# ==============================================
def expandir_termo(termo: str):
    """Expande o termo buscando variações e sinônimos para mais resultados"""
    termo = termo.lower().strip()
    variacoes = {
        'futebol': ['futebol', 'football', 'soccer', 'gols', 'partida'],
        'musica': ['musica', 'música', 'music', 'canção', 'song'],
        'carro': ['carro', 'carros', 'car', 'veiculo', 'automovel'],
        'video': ['video', 'vídeo', 'videos', 'vídeos', 'clip'],
    }
    # Se tiver variações conhecidas, retorna elas
    chave = None
    for chave_base in variacoes:
        if termo in chave_base or chave_base in termo:
            chave = chave_base
            break
    if chave:
        return variacoes[chave]
    # Sem variações conhecidas — retorna só o termo original
    return [termo]

# ==============================================
# CLIENTES
# ==============================================
conta_busca = TelegramClient(
    'sessao_conta_busca',
    API_ID,
    API_HASH,
    connection_retries=3
)

bot = TelegramClient(
    'sessao_bot',
    API_ID,
    API_HASH,
    connection_retries=3
)

# ==============================================
# SISTEMA DE AVISOS
# ==============================================
async def enviar_aviso_telegram(titulo: str, detalhe: str = "", solucao: str = "", eh_erro: bool = True):
    icone = "❌ ERRO" if eh_erro else "ℹ️ AVISO"
    mensagem = f"{icone}: {titulo}\n"
    if detalhe:
        mensagem += f"📋 Detalhe: {detalhe}\n"
    if solucao:
        mensagem += f"💡 Solução: {solucao}\n"
    mensagem += "\n" + datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    print(mensagem)
    try:
        await bot.send_message(SEU_ID_TELEGRAM, mensagem)
    except:
        try:
            await conta_busca.send_message(SEU_ID_TELEGRAM, mensagem)
        except:
            pass

# ==============================================
# FUNÇÃO DE BUSCA PRINCIPAL — Aprimorada
# ==============================================
async def buscar_videos_globais(termo_original: str, limite: int = LIMITE_RESULTADOS):
    print(f"🔍 Buscando: '{termo_original}'")
    
    if not conta_busca.is_connected():
        await enviar_aviso_telegram(
            "Conta de busca NÃO está conectada",
            "A sessão não foi carregada corretamente.",
            "1. Rode login no PyDroid → 2. Envie .session pro GitHub → 3. Deploy no Render",
            eh_erro=True
        )
        return []

    # Expandir o termo para buscar variações
    termos_busca = expandir_termo(termo_original)
    print(f"🔍 Variações a buscar: {termos_busca}")
    
    todos_videos = []
    ids_vistos = set()  # Evita duplicatas

    # =====================================
    # BUSCA GLOBAL — em canais e grupos públicos
    # =====================================
    for termo in termos_busca:
        try:
            data_limite = datetime.now()
            # Busca em períodos diferentes para cobrir mais resultados
            periodos = [
                timedelta(days=30),   # últimos 30 dias
                timedelta(days=180),  # últimos 6 meses
                timedelta(days=365*2) # últimos 2 anos
            ]
            
            for periodo in periodos:
                data_inicio = data_limite - periodo
                resultado = await conta_busca(SearchGlobalRequest(
                    q=termo,
                    filter=InputMessagesFilterVideo(),
                    broadcasts_only=False,  # Busca em canais E grupos
                    limit=limite,
                    min_date=data_inicio,
                    max_date=data_limite,
                    offset_rate=0,
                    offset_peer=InputPeerEmpty(),
                    offset_id=0
                ))
                
                for msg in resultado.messages:
                    if msg.id in ids_vistos:
                        continue  # Já temos este vídeo — pula
                    
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
                    
                    todos_videos.append({
                        'legenda': legenda,
                        'canal': canal.title if canal else 'Canal desconhecido',
                        'link': link,
                        'duracao': duracao,
                        'data': msg.date,  # Para ordenar por data
                        'termo_usado': termo
                    })
                    ids_vistos.add(msg.id)
                
                await asyncio.sleep(0.5)  # Evita bloqueio por requisições demais
                
        except Exception as e:
            print(f"⚠️ Falha buscando '{termo}': {e}")
            continue

    # =====================================
    # ORDENAR — mais recentes primeiro
    # =====================================
    todos_videos.sort(key=lambda x: x['data'], reverse=True)
    
    # Limitar quantidade final
    todos_videos = todos_videos[:limite]
    
    print(f"✅ Total encontrado: {len(todos_videos)} vídeo(s) únicos")
    return todos_videos

# ==============================================
# COMANDOS DO BOT
# ==============================================
@bot.on(events.NewMessage(pattern='/start'))
async def inicio(event):
    await event.reply(
        "🎬 Busca Global de Vídeos Telegram — Versão Aprimorada\n\n"
        "Comandos:\n"
        "/buscar [termo] — Busca vídeos em canais e grupos públicos\n"
        "Exemplo: /buscar musica\n\n"
        "🔍 Busca por variações e em múltiplos períodos!"
    )

@bot.on(events.NewMessage(pattern='/buscar'))
async def comando_buscar(event):
    try:
        texto = event.raw_text
        partes = texto.split(maxsplit=1)
        if len(partes) < 2:
            await event.reply("⚠️ Exemplo: /buscar musica")
            return
        termo = partes[1].strip()
        if not termo:
            await event.reply("⚠️ Digite um termo para buscar.")
            return
        
        msg_aguarde = await event.reply(f"🔍 Buscando: **{termo}**...\n🔄 Buscando variações e períodos...")
        videos = await buscar_videos_globais(termo)
        
        if not videos:
            await msg_aguarde.edit(
                f"❌ Nenhum vídeo encontrado para: **{termo}**\n"
                "Tente outro termo mais comum ou verifique se a conta de busca está conectada.",
                parse_mode='markdown'
            )
            return
        
        resposta = f"🎬 **{len(videos)} vídeo(s) encontrado(s):**\n\n"
        for i, v in enumerate(videos, 1):
            resposta += f"{i}. [{v['legenda']}]({v['link']})\n"
            resposta += f"📢 {v['canal']}  |  ⏱️ {v['duracao']}\n\n"
        await msg_aguarde.edit(resposta, parse_mode='markdown', link_preview=False)
        
    except Exception as e:
        await enviar_aviso_telegram(
            "Erro no comando /buscar",
            str(e),
            "Reinicie o serviço no Render e tente novamente",
            eh_erro=True
        )
        await event.reply("❌ Ocorreu um erro. Aviso enviado com detalhes.")

# ==============================================
# INICIALIZAÇÃO
# ==============================================
app = Flask(__name__)
bot_iniciado = False
conta_busca_conectada = False

async def iniciar_bot():
    global bot_iniciado, conta_busca_conectada
    if bot_iniciado:
        return
    
    try:
        print("🔌 Conectando conta de busca...")
        try:
            await conta_busca.start(NUMERO_CONTA)
            me = await conta_busca.get_me()
            if me:
                conta_busca_conectada = True
                print(f"✅ Conta de busca conectada — {me.first_name}")
                await enviar_aviso_telegram(
                    "Conta de busca conectada!",
                    f"Usuário: {me.first_name} | ID: {me.id}",
                    "Sistema pronto — busca variações e períodos!",
                    eh_erro=False
                )
        except Exception as e:
            await enviar_aviso_telegram(
                "FALHA — Conta de busca NÃO conectou",
                f"{type(e).__name__}: {str(e)}",
                "1. Login no PyDroid → 2. Envie .session → 3. Deploy no Render",
                eh_erro=True
            )
        
        print("🤖 Conectando bot...")
        await bot.start(bot_token=BOT_TOKEN)
        print("✅ Bot online")
        await bot.send_message(SEU_ID_TELEGRAM, "bot iniciado")
        
        bot_iniciado = True
        await bot.run_until_disconnected()

    except Exception as e:
        await enviar_aviso_telegram(
            "ERRO FATAL",
            f"{type(e).__name__}: {str(e)}",
            "Reinicie e verifique os arquivos de sessão",
            eh_erro=True
        )

@app.route('/')
def home():
    if conta_busca_conectada:
        return "✅ Bot Ativo — Conta conectada — Busca aprimorada!", 200
    elif bot_iniciado:
        return "⚠️ Bot rodando — Conta de busca NÃO conectada", 200
    return "⏳ Carregando...", 200

def run_bot_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(iniciar_bot())
    except Exception as e:
        print(f"❌ Erro: {e}")

if not bot_iniciado:
    threading.Thread(target=run_bot_loop, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
