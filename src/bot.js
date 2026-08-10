import TelegramBot from "node-telegram-bot-api";
import dotenv from "dotenv";

import {
    addSubscriber,
    deleteBotMessages,
    getBotMessages,
    getSubscribers,
    saveBotMessage,
    setMonitoringActive,
    setMonitoringType
} from "./subscribers.js";

dotenv.config();

const BOT_TOKEN = process.env.BOT_TOKEN;

const bot = new TelegramBot(
    BOT_TOKEN,
    {
        polling: true
    }
);

bot.setMyCommands([
    {
        command: "start",
        description: "Запустить бота"
    }
]);

const mainKeyboard = {
    reply_markup: {
        keyboard: [
            ["📡 Выбрать мониторинг"],
            ["▶️ Старт", "⏹ Стоп"],
            ["🧹 Очистить чат"]
        ],
        resize_keyboard: true
    }
};


/*
 * =====================================================
 * ОТПРАВКА СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЮ
 * =====================================================
 */

async function sendUserMessage(
    chatId,
    text,
    options = {}
) {
    const message = await bot.sendMessage(
        chatId,
        text,
        options
    );

    await saveBotMessage(
        chatId,
        message.message_id
    );

    return message;
}


/*
 * =====================================================
 * ОЧИСТКА ЧАТА
 * =====================================================
 */

async function clearChat(chatId) {
    const messages = await getBotMessages(chatId);

    console.log(
        "================================="
    );

    console.log(
        "ОЧИСТКА ЧАТА:",
        chatId
    );

    console.log(
        "НАЙДЕНО СООБЩЕНИЙ В БАЗЕ:",
        messages.length
    );

    console.log(
        "СООБЩЕНИЯ:",
        messages
    );

    console.log(
        "================================="
    );

    for (const message of messages) {
        try {
            console.log(
                "Удаляю message_id:",
                message.message_id
            );

            await bot.deleteMessage(
                chatId,
                message.message_id
            );

            console.log(
                "Удалено:",
                message.message_id
            );

        } catch (error) {
            console.log(
                "Ошибка удаления:",
                message.message_id,
                error.message
            );
        }
    }

    await deleteBotMessages(chatId);

    console.log(
        "Записи о сообщениях удалены из БД"
    );
}


/*
 * =====================================================
 * /start
 * =====================================================
 */

bot.onText(/\/start/, async (msg) => {

    await addSubscriber(
        msg.chat.id
    );

    await sendUserMessage(
        msg.chat.id,
        "✅ Вы подписаны на уведомления Kufar",
        mainKeyboard
    );
});


/*
 * =====================================================
 * ЛОГ CHAT ID
 * =====================================================
 */

bot.on("message", (msg) => {

    console.log(
        "CHAT ID:",
        msg.chat.id
    );

});


/*
 * =====================================================
 * ОСНОВНОЙ ОБРАБОТЧИК
 * =====================================================
 */

bot.on("message", async (msg) => {

    const text = msg.text;

    if (!text) {
        return;
    }


    /*
     * =================================================
     * ОЧИСТИТЬ ЧАТ
     * =================================================
     */

    if (text === "🧹 Очистить чат") {

        /*
         * Удаляем сообщение пользователя
         * с кнопкой очистки.
         */
        try {

            await bot.deleteMessage(
                msg.chat.id,
                msg.message_id
            );

        } catch (error) {

            console.log(
                "Не удалось удалить сообщение пользователя"
            );

        }


        /*
         * Удаляем все сообщения бота,
         * которые сохранены в Supabase.
         */

        await clearChat(
            msg.chat.id
        );


        /*
         * Показываем новое меню.
         */

        await sendUserMessage(
            msg.chat.id,
            "🧹 Чат очищен.",
            mainKeyboard
        );

        return;
    }


    /*
     * =================================================
     * ВЫБРАТЬ МОНИТОРИНГ
     * =================================================
     */

    if (
        text === "📡 Выбрать мониторинг"
    ) {

        await sendUserMessage(
            msg.chat.id,
            "Выберите, что мониторить:\n\n" +
            "1 — 🏠 Квартиры\n" +
            "2 — 📺 Телевизоры\n" +
            "3 — 🚲 Велосипеды"
        );

        return;
    }


    /*
     * =================================================
     * КВАРТИРЫ
     * =================================================
     */

    if (text === "1") {

        await setMonitoringType(
            msg.chat.id,
            "apartments"
        );

        await setMonitoringActive(
            msg.chat.id,
            true
        );

        await sendUserMessage(
            msg.chat.id,
            "🏠 Выбран мониторинг квартир.\n\n" +
            "▶️ Мониторинг запущен.",
            mainKeyboard
        );

        return;
    }


    /*
     * =================================================
     * ТЕЛЕВИЗОРЫ
     * =================================================
     */

    if (text === "2") {

        await setMonitoringType(
            msg.chat.id,
            "tv"
        );

        await setMonitoringActive(
            msg.chat.id,
            true
        );

        await sendUserMessage(
            msg.chat.id,
            "📺 Выбран мониторинг телевизоров.\n\n" +
            "▶️ Мониторинг запущен.",
            mainKeyboard
        );

        return;
    }


    /*
     * =================================================
     * ВЕЛОСИПЕДЫ
     * =================================================
     */

    if (text === "3") {

        await setMonitoringType(
            msg.chat.id,
            "bicycles"
        );

        await setMonitoringActive(
            msg.chat.id,
            true
        );

        await sendUserMessage(
            msg.chat.id,
            "🚲 Выбран мониторинг велосипедов.\n\n" +
            "▶️ Мониторинг запущен.",
            mainKeyboard
        );

        return;
    }


    /*
     * =================================================
     * СТАРТ
     * =================================================
     */

    if (text === "▶️ Старт") {

        await setMonitoringActive(
            msg.chat.id,
            true
        );

        await sendUserMessage(
            msg.chat.id,
            "▶️ Мониторинг запущен.",
            mainKeyboard
        );

        return;
    }


    /*
     * =================================================
     * СТОП
     * =================================================
     */

    if (text === "⏹ Стоп") {

        await setMonitoringActive(
            msg.chat.id,
            false
        );

        await sendUserMessage(
            msg.chat.id,
            "⏹ Мониторинг остановлен.",
            mainKeyboard
        );

        return;
    }

});


/*
 * =====================================================
 * ОТПРАВКА НОВЫХ ОБЪЯВЛЕНИЙ
 * =====================================================
 */

export async function sendMessage(
    monitoringType,
    text
) {

    const subscribers =
        await getSubscribers();

    for (const user of subscribers) {

        /*
         * Мониторинг выключен
         */
        if (!user.is_active) {
            continue;
        }

        /*
         * Другой тип мониторинга
         */
        if (
            user.monitoring_type !==
            monitoringType
        ) {
            continue;
        }

        try {

            const message =
                await bot.sendMessage(
                    user.chat_id,
                    text
                );


            /*
             * Сохраняем message_id объявления
             * в Supabase.
             */

            await saveBotMessage(
                user.chat_id,
                message.message_id
            );

        } catch (error) {

            console.log(
                `Не удалось отправить ${user.chat_id}`,
                error.message
            );

        }
    }
}