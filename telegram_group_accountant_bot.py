import re
import sqlite3
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters
)

# —— 数据库初始化 ——
conn = sqlite3.connect('accounts.db', check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER,
    user_id INTEGER,
    user_name TEXT,
    type TEXT,
    quantity REAL,
    unit_price REAL,
    amount REAL,
    product_name TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

# —— /start 命令 ——
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "欢迎使用群组记账机器人！\n"
        "• 发送 +数量商品名称（单价）总价 记录收入；\n"
        "  例如：+10个苹果（18）180\n"
        "• 发送 -数量商品名称（单价）总价 记录支出；\n"
        "• 发送“总计”查看当日明细与汇总；\n"
        "• 发送“清空账单”清除今日所有记录。"
    )

# —— 文本消息处理 ——
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    user = update.effective_user
    user_name = user.full_name

    # 记录收入/支出，格式：+数量商品名称（单价）总价
    if text.startswith(('+', '-')):
        sign = text[0]
        body = text[1:].strip()
        # 正则：数量 + 商品名称（单价）总价
        pattern = r'^([0-9]+(?:\.[0-9]+)?)(.+?)[\(\（]([0-9]+(?:\.[0-9]+)?)[\)\）]([0-9]+(?:\.[0-9]+)?)$'
        m = re.match(pattern, body)
        if not m:
            await update.message.reply_text(
                "❌ 格式错误，请按 +数量商品名称（单价）总价 重试，例如：+10个苹果（18）180"
            )
            return

        quantity    = float(m.group(1))
        product_name= m.group(2).strip()
        unit_price  = float(m.group(3))
        amount      = float(m.group(4))
        rec_type    = '收入' if sign == '+' else '支出'

        # 写入数据库
        c.execute(
            "INSERT INTO records (chat_id, user_id, user_name, type, quantity, unit_price, amount, product_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (chat_id, user.id, user_name, rec_type, quantity, unit_price, amount, product_name)
        )
        conn.commit()
        await update.message.reply_text(
            f"✅ 已记录：{rec_type}  {quantity}×{unit_price:.2f} 元  [{product_name}]  = {amount:.2f} 元"
        )

    # 查询总计
    elif text == '总计':
        c.execute(
            "SELECT user_name, type, quantity, unit_price, product_name, amount, timestamp "
            "FROM records "
            "WHERE chat_id=? AND date(timestamp,'localtime')=date('now','localtime')",
            (chat_id,)
        )
        rows = c.fetchall()
        if not rows:
            await update.message.reply_text("今日暂无记录。")
            return

        total_inc = total_exp = 0.0
        lines = ["📋 今日明细："]
        for uname, typ, qty, price, name, amt, ts in rows:
            hh = ts.split()[1]
            lines.append(
                f"[{hh}] {typ} — {qty}×{price:.2f} 元  [{name}] = {amt:.2f} 元 （{uname}）"
            )
            if typ == '收入':
                total_inc += amt
            else:
                total_exp += amt

        lines.append(f"\n💰 收入合计：{total_inc:.2f} 元")
        lines.append(f"💸 支出合计：{total_exp:.2f} 元")
        lines.append(f"🧮 结余：{(total_inc - total_exp):.2f} 元")
        await update.message.reply_text("\n".join(lines))

    # 清空账单
    elif text == '清空账单':
        c.execute(
            "DELETE FROM records "
            "WHERE chat_id=? AND date(timestamp,'localtime')=date('now','localtime')",
            (chat_id,)
        )
        conn.commit()
        await update.message.reply_text("🗑️ 已清空今日所有记录。")

# —— 主函数 ——  
if __name__ == "__main__":
    TOKEN = "7760839957:AAH5LwDzVfGcC7dhQVBO85ZlrNbewiRB25M"
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
