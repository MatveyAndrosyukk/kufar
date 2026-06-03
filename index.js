import axios from "axios";
import { sendMessage } from "./src/bot.js";
import { getSeenIds, saveSeenIds } from "./src/storage.js";
import { getUrl } from "./src/config.js";
import express from "express";

let seenIds = new Set();

async function firstLoad() {
    const url = await getUrl();

    if (!url) {
        console.log("URL не настроен");
        return;
    }

    const response = await axios.get(url);

    console.log("Ответ получен");

    const ads = response.data.ads ?? [];

    console.log("Объявлений:", ads.length);

    for (const ad of ads) {
        seenIds.add(ad.ad_id);
    }

    await saveSeenIds(seenIds);

    console.log(`Первичная загрузка: ${ads.length} объявлений`);
}

async function checkAds() {
    console.log("Проверяю объявления...");

    try {
        const url = await getUrl();

        if (!url) {
            console.log("URL не настроен");
            return;
        }

        const response = await axios.get(url);

        const ads = response.data.ads ?? [];

        for (const ad of ads) {
            if (seenIds.has(ad.ad_id)) {
                continue;
            }

            seenIds.add(ad.ad_id);

            const message =
                `🏠 Новое объявление

${ad.subject}

💵 ${ad.price_usd}$

🔗 ${ad.ad_link}`;

            await sendMessage(message);

            console.log(`Новое объявление: ${ad.ad_id}`);
        }

        await saveSeenIds(seenIds);

    } catch (error) {
        console.error("Ошибка проверки:", error.message);
    }
}

async function start() {
    console.log("Запуск бота...");

    seenIds = await getSeenIds();

    const url = await getUrl();

    console.log("URL:", url);
    console.log("seenIds:", seenIds.size);

    if (!url) {
        console.log("URL пока не задан.");
        console.log("Открой Telegram → /start → 🔗 Изменить URL");
    } else if (seenIds.size === 0) {
        await firstLoad();
    }

    await checkAds();

    setInterval(async () => {
        await checkAds();
    }, 30000);
}

start();

const app = express();

app.get("/", (req, res) => {
    res.send("Kufar bot is alive");
});

const PORT = 3000;

app.listen(PORT, () => {
    console.log(`HTTP сервер запущен на порту ${PORT}`);
});