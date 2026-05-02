import sqlite3
import os
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("TOKEN")  # usar no Render

ADMIN_ID = 5646224478

PIX = "768892f1-016a-4815-84a3-5a4cd3183c15"

GRUPOS = {
    "hetero": -1002831236793,
    "gay": -1002631302093,
    "trans": -4667321753
}

NOMES_GRUPOS = {
    "hetero": "BEST AMADOR HÉTERO",
    "gay": "BEST AMADOR GAY",
    "trans": "BEST AMADOR TRANS"
}

PLANOS = {
    "mensal": {"nome": "Mensal", "valor": "R$ 20,00", "dias": 30},
    "trimestral": {"nome": "Trimestral", "valor": "R$ 40,00", "dias": 90},
    "semestral": {"nome": "Semestral", "valor": "R$ 60,00", "dias": 180},
    "anual": {"nome": "Anual", "valor": "R$ 100,00", "dias": 365}
}

pendentes = {}


def conectar():
    return sqlite3.connect("clientes.db")


def criar_banco():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            user_id INTEGER,
            nome TEXT,
            grupo TEXT,
            plano TEXT,
            vencimento TEXT,
            ativo INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()


def salvar_cliente(user_id, nome, grupo, plano, dias):
    vencimento = datetime.now() + timedelta(days=dias)

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO clientes (user_id, nome, grupo, plano, vencimento, ativo)
        VALUES (?, ?, ?, ?, ?, 1)
    """, (
        user_id,
        nome,
        grupo,
        plano,
        vencimento.strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


async def start(update, context):
    botoes = [
        [InlineKeyboardButton("🔥 BEST AMADOR HÉTERO", callback_data="grupo_hetero")],
        [InlineKeyboardButton("🔥 BEST AMADOR GAY", callback_data="grupo_gay")],
        [InlineKeyboardButton("🔥 BEST AMADOR TRANS", callback_data="grupo_trans")]
    ]

    await update.message.reply_text(
        "🔥 BEST AMADORES\n\nEscolha o grupo:",
        reply_markup=InlineKeyboardMarkup(botoes)
    )


async def escolher_grupo(update, context):
    query = update.callback_query
    await query.answer()

    grupo = query.data.split("_")[1]

    botoes = [
        [InlineKeyboardButton("Mensal - R$ 20,00", callback_data=f"{grupo}_mensal")],
        [InlineKeyboardButton("Trimestral - R$ 40,00", callback_data=f"{grupo}_trimestral")],
        [InlineKeyboardButton("Semestral - R$ 60,00", callback_data=f"{grupo}_semestral")],
        [InlineKeyboardButton("Anual - R$ 100,00", callback_data=f"{grupo}_anual")]
    ]

    await query.message.reply_text(
        f"Grupo escolhido: {NOMES_GRUPOS[grupo]}\n\nEscolha o plano:",
        reply_markup=InlineKeyboardMarkup(botoes)
    )


async def escolher_plano(update, context):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    grupo, plano = query.data.split("_")

    pendentes[user.id] = {
        "nome": user.first_name,
        "grupo": grupo,
        "plano": plano
    }

    dados_plano = PLANOS[plano]

    botoes = [
        [InlineKeyboardButton("✅ Já paguei", callback_data=f"paguei_{user.id}")]
    ]

    await query.message.reply_text(
        f"""
💳 PAGAMENTO PIX

Grupo: {NOMES_GRUPOS[grupo]}
Plano: {dados_plano['nome']}
Valor: {dados_plano['valor']}

Chave Pix:
{PIX}

Após pagar, envie o comprovante e clique em “Já paguei”.
""",
        reply_markup=InlineKeyboardMarkup(botoes)
    )


async def paguei(update, context):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    dados = pendentes.get(user.id)

    if not dados:
        await query.message.reply_text("Erro. Digite /start novamente.")
        return

    botoes_admin = [[
        InlineKeyboardButton("✅ Aprovar", callback_data=f"aprovar_{user.id}"),
        InlineKeyboardButton("❌ Recusar", callback_data=f"recusar_{user.id}")
    ]]

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"""
💰 NOVO PAGAMENTO

Cliente: {dados['nome']}
ID: {user.id}
Grupo: {NOMES_GRUPOS[dados['grupo']]}
Plano: {PLANOS[dados['plano']]['nome']}
""",
        reply_markup=InlineKeyboardMarkup(botoes_admin)
    )

    await query.message.reply_text("Pagamento enviado para análise.")


async def aprovar(update, context):
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split("_")[1])
    dados = pendentes.get(user_id)

    if not dados:
        return

    grupo = dados["grupo"]
    plano = dados["plano"]
    dias = PLANOS[plano]["dias"]

    link = await context.bot.create_chat_invite_link(
        chat_id=GRUPOS[grupo],
        member_limit=1
    )

    salvar_cliente(user_id, dados["nome"], grupo, plano, dias)

    vencimento = datetime.now() + timedelta(days=dias)

    await context.bot.send_message(
        chat_id=user_id,
        text=f"""
✅ Aprovado!

Grupo: {NOMES_GRUPOS[grupo]}
Plano: {PLANOS[plano]['nome']}
Válido até: {vencimento.strftime('%d/%m/%Y')}

Link:
{link.invite_link}
"""
    )

    await query.message.reply_text("Cliente aprovado.")


async def verificar_vencimentos(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, grupo
        FROM clientes
        WHERE ativo = 1 AND vencimento <= ?
    """, (agora,))

    vencidos = cur.fetchall()

    for user_id, grupo in vencidos:
        try:
            await context.bot.ban_chat_member(GRUPOS[grupo], user_id)
            await context.bot.unban_chat_member(GRUPOS[grupo], user_id)
        except:
            pass

        cur.execute("UPDATE clientes SET ativo = 0 WHERE user_id = ?", (user_id,))

    conn.commit()
    conn.close()


def main():
    criar_banco()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CallbackQueryHandler(escolher_grupo, pattern="^grupo_"))
    app.add_handler(CallbackQueryHandler(escolher_plano, pattern="^(hetero|gay|trans)_"))
    app.add_handler(CallbackQueryHandler(paguei, pattern="^paguei_"))
    app.add_handler(CallbackQueryHandler(aprovar, pattern="^aprovar_"))

    app.job_queue.run_repeating(verificar_vencimentos, interval=86400, first=10)

    print("Bot rodando 24h nível Netflix...")
    app.run_polling()


if __name__ == "__main__":
    main()
