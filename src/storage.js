import fs from "fs/promises";

const FILE = "./seen.json";

export async function getSeenIds() {
    try {
        const raw = await fs.readFile(FILE, "utf8");
        const data = JSON.parse(raw);

        return new Set(data.ids || []);
    } catch {
        await fs.writeFile(
            FILE,
            JSON.stringify(
                {
                    ids: []
                },
                null,
                2
            )
        );

        return new Set();
    }
}

export async function saveSeenIds(ids) {
    await fs.writeFile(
        FILE,
        JSON.stringify(
            {
                ids: [...ids]
            },
            null,
            2
        )
    );
}