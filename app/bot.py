"""Telegram bot: log incomes, see the balance, split it into buckets, mark it paid out."""
import asyncio
import logging
from decimal import Decimal

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app import db
from app.config import Settings, load_settings
from app.money import parse_amount, split_amount

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

BTN_BALANCE = "📊 Баланс"
BTN_SPLIT = "✂️ Разделить"
BTN_HISTORY = "📜 История"
BTN_STATS = "📈 По месяцам"
BTN_PAYOUT = "✅ Выплачено"

KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_BALANCE), KeyboardButton(text=BTN_SPLIT)],
        [KeyboardButton(text=BTN_HISTORY), KeyboardButton(text=BTN_STATS)],
        [KeyboardButton(text=BTN_PAYOUT)],
    ],
    resize_keyboard=True,
    input_field_placeholder="Сумма, например 1500",
)


def fmt(amount: Decimal, currency: str) -> str:
    return f"{amount:,.2f}".replace(",", " ") + f" {currency}"


def build_dispatcher(settings: Settings, pool) -> Dispatcher:
    dp = Dispatcher()
    cur = settings.currency

    def allowed(msg: types.Message) -> bool:
        return not settings.allowed_user_ids or msg.from_user.id in settings.allowed_user_ids

    @dp.message(Command("start"))
    async def start(msg: types.Message):
        if not allowed(msg):
            await msg.answer("⛔ Нет доступа")
            return
        bal = await db.get_balance(pool)
        await msg.answer(
            "Отправьте сумму, чтобы записать доход.\n"
            f"Текущий баланс: <b>{fmt(bal, cur)}</b>",
            reply_markup=KEYBOARD,
        )

    @dp.message(Command("id"))
    async def my_id(msg: types.Message):
        # Lets a new user find their Telegram ID to add it to ALLOWED_USER_IDS
        await msg.answer(f"Ваш Telegram ID: <code>{msg.from_user.id}</code>")

    @dp.message(F.text)
    async def on_text(msg: types.Message):
        if not allowed(msg):
            await msg.answer("⛔ Нет доступа")
            return
        text = msg.text.strip()

        amount = parse_amount(text)
        if amount is not None:
            new_balance = await db.add_income(pool, msg.from_user.id, amount)
            await msg.answer(f"✅ +{fmt(amount, cur)}\nБаланс: <b>{fmt(new_balance, cur)}</b>")
            return

        if text == BTN_BALANCE:
            await msg.answer(f"Баланс: <b>{fmt(await db.get_balance(pool), cur)}</b>")
        elif text == BTN_SPLIT:
            bal = await db.get_balance(pool)
            if bal <= 0:
                await msg.answer("Баланс пуст, делить нечего.")
                return
            lines = [f"{name}: <b>{fmt(share, cur)}</b>" for name, share in split_amount(bal, settings.split)]
            await msg.answer(f"Баланс {fmt(bal, cur)}:\n" + "\n".join(lines))
        elif text == BTN_HISTORY:
            rows = await db.history(pool, limit=10)
            if not rows:
                await msg.answer("Записей пока нет.")
                return
            lines = [
                f"{ts:%d.%m %H:%M}  {'+' if kind == 'income' else '−'}{fmt(abs(amount), cur)}"
                + ("" if kind == "income" else "  (выплата)")
                for ts, kind, amount in rows
            ]
            await msg.answer("Последние операции:\n<pre>" + "\n".join(lines) + "</pre>")
        elif text == BTN_STATS:
            rows = await db.monthly(pool, months=6)
            if not rows:
                await msg.answer("Записей пока нет.")
                return
            lines = [
                f"{r['month']:%m.%Y}: доход {fmt(r['income_total'], cur)} ({r['income_entries']} зап.), "
                f"выплачено {fmt(r['paid_out'], cur)}"
                for r in rows
            ]
            await msg.answer("По месяцам:\n" + "\n".join(lines))
        elif text == BTN_PAYOUT:
            paid = await db.payout_all(pool, msg.from_user.id)
            if paid == 0:
                await msg.answer("Баланс уже пуст.")
            else:
                await msg.answer(f"Записал выплату {fmt(paid, cur)}. Баланс: <b>{fmt(Decimal(0), cur)}</b>")
        else:
            await msg.answer("Отправьте сумму (например, 1500 или 1 250,50) или нажмите кнопку.")

    return dp


async def main() -> None:
    settings = load_settings()
    pool = await db.create_pool(settings.database_url, settings.db_ssl)
    await db.apply_schema(pool)
    log.info("Database ready")

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher(settings, pool)

    if settings.webhook_base_url:
        from aiohttp import web
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

        await bot.set_webhook(f"{settings.webhook_base_url}/webhook")
        app = web.Application()
        SimpleRequestHandler(dp, bot).register(app, path="/webhook")
        setup_application(app, dp, bot=bot)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", settings.port).start()
        log.info("Webhook mode on port %s", settings.port)
        await asyncio.Event().wait()
    else:
        log.info("Polling mode")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
