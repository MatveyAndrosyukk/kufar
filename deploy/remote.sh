#!/usr/bin/env bash
# Выполняется на сервере при деплое (BOT_TOKEN и FLATS_BOT_TOKEN приходят через env)
(
  set -e
  curl -fsSL https://raw.githubusercontent.com/MatveyAndrosyukk/kufar/master/install.sh -o /tmp/kufar-install.sh
  bash /tmp/kufar-install.sh
  cd /opt/kufar-bot
  setenv() { if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi; }
  setenv BOT_TOKEN "$BOT_TOKEN"
  setenv FLATS_BOT_TOKEN "$FLATS_BOT_TOKEN"
  docker compose up -d --build
  docker compose ps

  avatar() {  # $1 токен, $2 файл, $3 метка
    H=$(sha1sum "$2" | cut -c1-40)
    if [ "$(cat data/.avatar_$3 2>/dev/null)" != "$H" ]; then
      R=$(curl -s -F 'photo={"type":"static","photo":"attach://avatar"}' -F "avatar=@$2" "https://api.telegram.org/bot$1/setMyProfilePhoto")
      echo "$R" | grep -q '"ok":true' && echo "$H" > data/.avatar_$3 || echo "avatar $3: $R"
    fi
    test "$(cat data/.avatar_$3 2>/dev/null)" = "$H" && echo "AVATAR_OK $3"
  }
  [ -f data/.avatar ] && [ ! -f data/.avatar_kufar ] && mv data/.avatar data/.avatar_kufar
  avatar "$BOT_TOKEN" deploy/avatar.jpg kufar
  avatar "$FLATS_BOT_TOKEN" deploy/avatar_flats.jpg flats

  echo ">> Проверка: оба бота подключились к Telegram"
  for s in bot flats; do
    for i in $(seq 1 15); do docker compose logs $s 2>&1 | grep -q "Run polling" && break; sleep 5; done
    docker compose logs --tail 15 $s
    docker compose logs $s 2>&1 | grep -q "Run polling"
  done
  echo ">> Проверка: Kufar API"
  docker compose exec -T bot python -W ignore -c "import asyncio,kufar;ads=asyncio.run(kufar.search({'query':'квартира','region_id':1,'city':'Брест'}));print('KUFAR_OK',len(ads));assert ads;assert all('брест' in str(kufar.location(a)).lower() for a in ads[:5])"
  echo ">> Проверка: источники бота квартир"
  docker compose exec -T flats python /flats_check.py
  echo ">> Время ответа realt с сервера"
  for u in https://realt.by/rent/flat-for-day/ https://realt.by/brest-region/rent/flat-for-day/?sortType=createdAt; do curl -s -o /dev/null -w "%{http_code} %{time_total}s %{size_download}b $u\n" -A "Mozilla/5.0 Chrome/129" -m 90 "$u" || true; done
  echo DEPLOY_SUCCESS
) > /tmp/deploy.log 2>&1

