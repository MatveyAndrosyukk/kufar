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

export async function setMonitoringType(
    chatId,
    monitoringType
) {
    await supabase
        .from("subscribers")
        .update({
            monitoring_type: monitoringType
        })
        .eq("chat_id", chatId);
}

export async function setMonitoringActive(
    chatId,
    isActive
) {
    await supabase
        .from("subscribers")
        .update({
            is_active: isActive
        })
        .eq("chat_id", chatId);
}

/*
 * Сохраняем сообщение бота
 */
export async function saveBotMessage(
    chatId,
    messageId
) {
    await supabase
        .from("bot_messages")
        .insert({
            chat_id: chatId,
            message_id: messageId
        });
}

/*
 * Получаем все сообщения бота
 * конкретного пользователя.
 */
export async function getBotMessages(chatId) {
    const { data } = await supabase
        .from("bot_messages")
        .select("message_id")
        .eq("chat_id", chatId);

    return data || [];
}

/*
 * Удаляем сообщения из базы
 * после очистки.
 */
export async function deleteBotMessages(
    chatId
) {
    await supabase
        .from("bot_messages")
        .delete()
        .eq("chat_id", chatId);
}