import axios from "axios";
import express from "express";

import { sendMessage } from "./src/bot.js";
import { getUrl } from "./src/config.js";
import { isSeen, markSeen } from "./src/storage.js";

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

        console.log(`Получено объявлений: ${ads.length}`);

        for (const ad of ads) {

            const alreadySeen = await isSeen(ad.ad_id);

            if (alreadySeen) {
                continue;
            }

            await markSeen(ad.ad_id);

            const message =
                `🏠 Новое объявление\n\n` +
                `${ad.subject}\n\n` +
                `🔗 ${ad.ad_link}`;

            await sendMessage(message);

            console.log(`Новое объявление: ${ad.ad_id}`);
        }

    } catch (error) {
        console.error(
            "Ошибка проверки:",
            error.response?.data || error.message
        );
    }
}

async function firstLoad() {

    const url = await getUrl();

    if (!url) {
        return;
    }

    const response = await axios.get(url);

    const ads = response.data.ads ?? [];

    for (const ad of ads) {
        await markSeen(ad.ad_id);
    }

    console.log(
        `Первичная загрузка завершена. Сохранено ${ads.length} объявлений`
    );
}

async function start() {

    console.log("Запуск бота...");

    const url = await getUrl();

    console.log("Текущий URL:", url);

    if (!url) {
        console.log(
            "Открой Telegram → /start → 🔗 Изменить URL"
        );
        return;
    }

    const response = await axios.get(url);

    const ads = response.data.ads ?? [];

    if (ads.length > 0) {

        const firstAd = ads[0];

        const exists = await isSeen(firstAd.ad_id);

        if (!exists) {
            await firstLoad();
        }
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

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
    console.log(
        `HTTP сервер запущен на порту ${PORT}`
    );
});