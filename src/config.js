import fs from "fs/promises";

const FILE = "./config.json";

const DEFAULT_URL =
    "https://api.kufar.by/search-api/v2/search/rendered-paginated?cat=1010&cur=BYR&gtsy=country-belarus~province-brestskaja_oblast~locality-brest&lang=ru&prc=r%3A0%2C60000&size=30&typ=let";

export async function getUrl() {
    try {
        const raw = await fs.readFile(FILE, "utf8");
        const data = JSON.parse(raw);

        return data.url || DEFAULT_URL;
    } catch {
        await saveUrl(DEFAULT_URL);

        return DEFAULT_URL;
    }
}

export async function saveUrl(url) {
    await fs.writeFile(
        FILE,
        JSON.stringify(
            {
                url
            },
            null,
            2
        )
    );
}