from telethon import TelegramClient, events
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.types import InputMessagesFilterVideo, InputPeerEmpty
import asyncio
from datetime import datetime, timedelta
import traceback
from flask import Flask
import threading
import os
import sys

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
# CLIENTES — NOMES EXATOS DOS ARQUIVOS .session
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
# SISTEMA DE MENSAGENS DE ERRO COM SOLUÇÕES
# ==============================================
async def enviar_aviso_telegram(titulo: str, detalhe: str = "", solucao: str = "", eh_erro: bool = True):
    icone = "❌ ERRO" if eh_erro else "ℹ️ AVISO"
    mensagem = f"{icone}: {titulo}\n"
    if detalhe:
        mensagem += f"📋 Detalhe: {detalhe}\n"
    if solucao:
        mensagem += f"💡 Solução: {solucao}\n"
    mensagem += "\n" + datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    print("\n" + "="*60)
    print(mensagem)
    print("="*60 + "\n")
    
    try:
        await bot.send_message(SEU_ID_TELEGRAM, mensagem)
    except Exception as e:
        print(f"⚠️ Não foi possível enviar mensagem de aviso: {e}")
        try:
            await conta_busca.send_message(SEU_ID_TELEGRAM, mensagem)
        except:
            print("❌ Falha total — nenhum cliente conectado para avisar")

# ==============================================
# FUNÇÃO DE BUSCA — COM TRATAMENTO COMPLETO
# ==============================================
async def buscar_videos_globais(termo: str, limite: int = LIMITE_RESULTADOS):
    print(f"🔍 Buscando: '{termo}'")
    
    # Verifica se a conta de busca está conectada antes de buscar
    if not conta_busca.is_connected():
        await enviar_aviso_telegram(
            "Conta de busca NÃO está conectada",
            "A busca não pode ser feita sem a conta logada.",
            "1. Rode o código de login no PyDroid/celular\n"
            "2. Envie os arquivos .session para o GitHub\n"
            "3. Faça Deploy no Render novamente",
            eh_erro=True
        )
        return []
    
    try:
        data_limite = datetime.now()
        data_inicio = data_limite - timedelta(days=365*10)
        resultado = await conta_busca(SearchGlobalRequest(
            q=termo,
            filter=InputMessagesFilterVideo(),
            broadcasts_only=False,
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
            except Exception as e:
                print(f"⚠️ Não foi possível obter canal: {e}")
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
        
        if not videos:
            await enviar_aviso_telegram(
                f"Nenhum vídeo encontrado para: '{termo}'",
                "A busca retornou vazia. Pode ser que não exista vídeo com esse termo público.",
                "1. Tente um termo mais comum (ex: musica, futebol)\n"
                "2. Verifique se escreveu certo\n"
                "3. A conta de busca precisa estar totalmente conectada",
                eh_erro=False
            )
        else:
            print(f"✅ Busca concluída: {len(videos)} vídeo(s) encontrado(s)")
        
        return videos
        
    except Exception as e:
        erro_tipo = type(e).__name__
        await enviar_aviso_telegram(
            f"Falha na busca: '{termo}'",
            f"{erro_tipo}: {str(e)}",
            "1. Verifique se a conta de busca está conectada\n"
            "2. Olhe os logs no Render para mais detalhes\n"
            "3. Reinicie o serviço no Render",
            eh_erro=True
        )
        return []

# ==============================================
# COMANDOS DO BOT
# ==============================================
@bot.on(events.NewMessage(pattern='/start'))
async def inicio(event):
    await event.reply(
        "🎬 Busca Global de Vídeos Telegram\n\n"
        "Comandos:\n"
        "/buscar [termo] — Busca vídeos em canais e grupos públicos\n"
        "Exemplo: /buscar musica"
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
            await event.reply("⚠️ Digite um termo para buscar. Ex: /buscar futebol")
            return
        
        msg_aguarde = await event.reply(f"🔍 Buscando: **{termo}**...")
        videos = await buscar_videos_globais(termo)
        
        if not videos:
            await msg_aguarde.edit(
                f"❌ Nenhum vídeo encontrado para: **{termo}**\n"
                "⚠️ Verifique se a conta de busca está conectada.",
                parse_mode='markdown'
            )
            return
        
        resposta = f"🎬 **{len(videos)} vídeo(s):**\n\n"
        for i, v in enumerate(videos, 1):
            resposta += f"{i}. [{v['legenda']}]({v['link']})\n"
            resposta += f"📢 {v['canal']}  |  ⏱️ {v['duracao']}\n\n"
        await msg_aguarde.edit(resposta, parse_mode='markdown', link_preview=False)
        
    except Exception as e:
        await enviar_aviso_telegram(
            "Erro ao processar comando /buscar",
            str(e),
            "Tente novamente ou reinicie o serviço no Render",
            eh_erro=True
        )
        await event.reply("❌ Ocorreu um erro. Aviso enviado com detalhes.")

# ==============================================
# INICIALIZAÇÃO COM VERIFICAÇÃO COMPLETA
# ==============================================
app = Flask(__name__)
bot_iniciado = False
conta_busca_conectada = False

async def iniciar_bot():
    global bot_iniciado, conta_busca_conectada
    if bot_iniciado:
        print("⚠️ Bot já está rodando")
        return
    
    try:
        # =====================================
        # PASSO 1 — CONECTAR CONTA DE BUSCA
        # =====================================
        print("🔌 Conectando conta de busca...")
        try:
            await conta_busca.start(NUMERO_CONTA)
            
            # Verificação real de conexão
            me = await conta_busca.get_me()
            if me:
                conta_busca_conectada = True
                print(f"✅ Conta de busca conectada — Usuário: {me.first_name}")
                await enviar_aviso_telegram(
                    "Conta de busca conectada com sucesso!",
                    f"Usuário: {me.first_name} | ID: {me.id}",
                    "Tudo pronto! Pode usar /buscar normalmente.",
                    eh_erro=False
                )
            else:
                raise Exception("Não foi possível obter dados da conta")
                
        except Exception as e:
            erro_tipo = type(e).__name__
            mensagem_erro = str(e)
            solucao = ""
            
            if "code" in mensagem_erro.lower() or "password" in mensagem_erro.lower():
                solucao = (
                    "O Render não tem onde digitar o código.\n"
                    "1. Rode o código no PyDroid/celular\n"
                    "2. Digite o código lá\n"
                    "3. Envie os arquivos .session para o GitHub\n"
                    "4. Deploy no Render"
                )
            elif "Session not found" in mensagem_erro or "not found" in mensagem_erro.lower():
                solucao = (
                    "Arquivo de sessão não encontrado ou nome errado.\n"
                    "1. Confirme que 'sessao_conta_busca.session' está no GitHub\n"
                    "2. O nome no código deve ser exatamente igual ao arquivo\n"
                    "3. Gere sessão nova no celular e envie"
                )
            elif "Connection" in erro_tipo or "Network" in erro_tipo:
                solucao = (
                    "Problema de conexão de rede.\n"
                    "1. O Render pode estar bloqueando temporariamente\n"
                    "2. Aguarde alguns minutos e tente novamente\n"
                    "3. Reinicie o serviço no Render"
                )
            else:
                solucao = (
                    f"1. Erro: {erro_tipo}\n"
                    "2. Rode o login no celular novamente\n"
                    "3. Envie os arquivos .session atualizados para o GitHub"
                )
            
            await enviar_aviso_telegram(
                "FALHA — Conta de busca NÃO conectou",
                f"{erro_tipo}: {mensagem_erro}",
                solucao,
                eh_erro=True
            )
            print("⚠️ Continuando sem conta de busca — comandos /buscar vão retornar vazio")
        
        # =====================================
        # PASSO 2 — CONECTAR BOT
        # =====================================
        print("🤖 Conectando bot...")
        await bot.start(bot_token=BOT_TOKEN)
        print("✅ Bot online")
        
        try:
            await bot.send_message(SEU_ID_TELEGRAM, "bot iniciado")
            print("📤 Mensagem enviada: bot iniciado")
        except Exception as e:
            print(f"⚠️ Não foi possível enviar mensagem de início: {e}")
        
        bot_iniciado = True
        print("👂 Aguardando comandos...")
        await bot.run_until_disconnected()

    except Exception as e:
        await enviar_aviso_telegram(
            "ERRO FATAL — Sistema parou",
            f"{type(e).__name__}: {str(e)}",
            "1. Reinicie o serviço no Render\n"
            "2. Verifique os logs\n"
            "3. Confirme os arquivos de sessão",
            eh_erro=True
        )

@app.route('/')
def home():
    if conta_busca_conectada:
        status = "✅ Bot Ativo — Conta de busca conectada — Tudo Pronto!"
    elif bot_iniciado:
        status = "⚠️ Bot rodando — Conta de busca NÃO conectada — Busca não funciona"
    else:
        status = "⏳ Carregando... aguarde"
    return status, 200

def run_bot_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(iniciar_bot())
    except Exception as e:
        print(f"❌ Loop do bot parou: {e}")
        try:
            asyncio.run(bot.send_message(SEU_ID_TELEGRAM, f"❌ Sistema parou: {type(e).__name__}: {e}"))
        except:
            pass

# Inicia o bot em thread separada
if not bot_iniciado:
    threading.Thread(target=run_bot_loop, daemon=True).start()
    print("🚀 Sistema iniciado em segundo plano")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
