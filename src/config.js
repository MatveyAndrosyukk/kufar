import { supabase } from "./db.js";

const DEFAULT_URL =
    "https://api.kufar.by/search-api/v2/search/rendered-paginated?cat=1010&cur=BYR&gtsy=country-belarus~province-brestskaja_oblast~locality-brest&lang=ru&prc=r%3A0%2C60000&size=30&typ=let";

export async function getUrl() {

    const { data } = await supabase
        .from("settings")
        .select("*")
        .eq("id", 1)
        .single();

    if (!data) {

        await saveUrl(DEFAULT_URL);

        return DEFAULT_URL;
    }

    return data.url;
}

export async function saveUrl(url) {

    await supabase
        .from("settings")
        .upsert({
            id: 1,
            url
        });
}