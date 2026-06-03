import TelegramBot from "node-telegram-bot-api";
import dotenv from "dotenv";
import { saveUrl, getUrl } from "./config.js";
import { addSubscriber, getSubscribers } from "./subscribers.js";

dotenv.config();
const BOT_TOKEN = "8968549054:AAFMnSz5jW4uWSSl57AtxgwD-6VtKsLSaHs"

const bot = new TelegramBot(
    BOT_TOKEN,
    {
        polling: true
    }
);

let waitingForUrl = false;

bot.onText(/\/start/, async (msg) => {

    await addSubscriber(msg.chat.id);

    await bot.sendMessage(
        msg.chat.id,
        "✅ Вы подписаны на уведомления Kufar",
        {
            reply_markup: {
                keyboard: [
                    ["🔗 Изменить URL"],
                    ["📄 Текущий URL"]
                ],
                resize_keyboard: true
            }
        }
    );
});

bot.on("message", (msg) => {
    console.log("CHAT ID:", msg.chat.id);
});

bot.on("message", async (msg) => {
    const text = msg.text;

    if (!text) {
        return;
    }

    if (text === "🔗 Изменить URL") {
        waitingForUrl = true;

        await bot.sendMessage(
            msg.chat.id,
            "Отправьте новый URL API Kufar"
        );

        return;
    }

    if (text === "📄 Текущий URL") {
        const url = await getUrl();

        await bot.sendMessage(
            msg.chat.id,
            url
        );

        return;
    }

    if (
        waitingForUrl &&
        text.startsWith("http")
    ) {
        waitingForUrl = false;

        await saveUrl(text);

        await bot.sendMessage(
            msg.chat.id,
            "✅ URL успешно обновлен"
        );
    }
});

export async function sendMessage(text) {

    const subscribers = await getSubscribers();

    for (const user of subscribers) {
        try {
            await bot.sendMessage(
                user.chat_id,
                text
            );
        } catch (error) {
            console.log(
                `Не удалось отправить ${user.chat_id}`
            );
        }
    }
}