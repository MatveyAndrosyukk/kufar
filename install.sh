#!/usr/bin/env bash
# Установка/обновление бота на сервере (Ubuntu/Debian).
# Первый запуск:  curl -fsSL https://raw.githubusercontent.com/MatveyAndrosyukk/kufar/master/install.sh | BOT_TOKEN=xxx bash
# Обновление:     bash /opt/kufar-bot/install.sh
set -euo pipefail
DIR=/opt/kufar-bot
REPO=https://github.com/MatveyAndrosyukk/kufar.git

if ! command -v docker >/dev/null 2>&1; then
  echo ">> Ставлю Docker..."
  curl -fsSL https://get.docker.com | sh
fi
command -v git >/dev/null 2>&1 || (apt-get update -y && apt-get install -y git)

if [ -d "$DIR/.git" ]; then
  echo ">> Обновляю код..."
  git -C "$DIR" fetch --depth 1 origin master && git -C "$DIR" reset --hard origin/master
else
  echo ">> Клонирую репозиторий..."
  git clone --depth 1 "$REPO" "$DIR"
fi
cd "$DIR"

if [ ! -f .env ]; then
  if [ -z "${BOT_TOKEN:-}" ]; then
    read -rp "Вставь токен бота: " BOT_TOKEN </dev/tty
  fi
  printf 'BOT_TOKEN=%s\nCHECK_INTERVAL=60\nALLOWED_USERS=%s\n' "$BOT_TOKEN" "${ALLOWED_USERS:-}" > .env
  chmod 600 .env
fi
mkdir -p data

echo ">> Собираю и запускаю контейнер..."
docker compose up -d --build
sleep 5
docker compose ps
docker compose logs --tail 20
echo ">> Готово. Логи: cd $DIR && docker compose logs -f"
