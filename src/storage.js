import { supabase } from "./db.js";

export async function isSeen(adId) {

    const { data } = await supabase
        .from("seen_ads")
        .select("ad_id")
        .eq("ad_id", adId)
        .maybeSingle();

    return !!data;
}

export async function markSeen(adId) {

    await supabase
        .from("seen_ads")
        .upsert({
            ad_id: adId
        });
}