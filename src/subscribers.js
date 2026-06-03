import { supabase } from "./db.js";

export async function addSubscriber(chatId) {

    await supabase
        .from("subscribers")
        .upsert({
            chat_id: chatId
        });
}

export async function getSubscribers() {

    const { data } = await supabase
        .from("subscribers")
        .select("*");

    return data || [];
}