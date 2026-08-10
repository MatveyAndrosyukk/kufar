import axios from "axios";
import express from "express";

import { sendMessage } from "./src/bot.js";
import { isSeen, markSeen } from "./src/storage.js";

const MONITORING = {
    apartments: {
        name: "квартиры",
        emoji: "🏠",
        url: "https://api.kufar.by/search-api/v2/search/rendered-paginated?cat=1010&cur=BYR&gtsy=country-belarus~province-brestskaja_oblast~locality-brest&lang=ru&prc=r%3A0%2C60000&size=30&typ=let"
    },

    tv: {
        name: "телевизоры",
        emoji: "📺",
        url: "https://api.kufar.by/search-api/v2/search/rendered-paginated?ar=1&cursor=eyJ0IjoiYWJzIiwiZiI6dHJ1ZSwicCI6MiwicGl0IjoiMjk3NzIzODUifQ%3D%3D&lang=ru&query=%D0%A2%D0%B5%D0%BB%D0%B5%D0%B2%D0%B8%D0%B7%D0%BE%D1%80&rgn=1&size=43&sort=lst.d"
    },

    bicycles: {
        name: "велосипеды",
        emoji: "🚲",
        url: "https://api.kufar.by/search-api/v2/search/rendered-paginated?ar=1&cursor=eyJ0IjoiYWJzIiwiZiI6dHJ1ZSwicCI6MiwicGl0IjoiMjk3NzIzOTAifQ%3D%3D&lang=ru&query=%D0%92%D0%B5%D0%BB%D0%BE%D1%81%D0%B8%D0%BF%D0%B5%D0%B4&rgn=1&size=43&sort=lst.d"
    }
};

async function getAds(url) {
    const response = await axios.get(url);

    return response.data.ads ?? [];
}

async function firstLoad(monitoringType, url) {
    try {
        const ads = await getAds(url);

        for (const ad of ads) {
            await markSeen(ad.ad_id);
        }

        console.log(
            `[${monitoringType}] Первичная загрузка завершена. ` +
            `Сохранено ${ads.length} объявлений`
        );
    } catch (error) {
        console.error(
            `[${monitoringType}] Ошибка первичной загрузки:`,
            error.response?.data || error.message
        );
    }
}

async function checkAds(monitoringType, config) {
    console.log(
        `[${monitoringType}] Проверяю объявления...`
    );

    try {
        const ads = await getAds(config.url);

        console.log(
            `[${monitoringType}] Получено объявлений: ${ads.length}`
        );

        for (const ad of ads) {
            const alreadySeen = await isSeen(ad.ad_id);

            if (alreadySeen) {
                continue;
            }

            await markSeen(ad.ad_id);

            const description =
                ad.body ||
                ad.body_short ||
                "Описание отсутствует";

            const message =
                `${config.emoji} Новое объявление\n\n` +
                `Название: ${ad.subject || "Без названия"}\n\n` +
                `Описание: ${description}\n\n` +
                `🔗 ${ad.ad_link}`;

            await sendMessage(
                monitoringType,
                message
            );

            console.log(
                `[${monitoringType}] Новое объявление: ${ad.ad_id}`
            );
        }
    } catch (error) {
        console.error(
            `[${monitoringType}] Ошибка проверки:`,
            error.response?.data || error.message
        );
    }
}

async function prepareMonitoring(monitoringType, config) {
    try {
        const ads = await getAds(config.url);

        if (ads.length === 0) {
            console.log(
                `[${monitoringType}] API вернул 0 объявлений`
            );

            return;
        }

        const firstAd = ads[0];

        const exists = await isSeen(firstAd.ad_id);

        if (!exists) {
            await firstLoad(
                monitoringType,
                config.url
            );
        }

        await checkAds(
            monitoringType,
            config
        );
    } catch (error) {
        console.error(
            `[${monitoringType}] Ошибка запуска:`,
            error.response?.data || error.message
        );
    }
}

async function start() {
    console.log("Запуск бота...");

    for (const [monitoringType, config] of Object.entries(MONITORING)) {
        console.log(
            `Подготовка мониторинга: ${config.name}`
        );

        await prepareMonitoring(
            monitoringType,
            config
        );
    }

    setInterval(async () => {
        for (const [monitoringType, config] of Object.entries(MONITORING)) {
            await checkAds(
                monitoringType,
                config
            );
        }
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