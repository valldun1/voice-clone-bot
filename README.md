# 🎙️ Voice Clone Bot

Telegram бот для клонирования голоса. Отправь голосовое + текст → получи озвучку своим голосом.

**Стек:** OmniVoice (k2-fsa) + Modal (GPU) + Telegram + Railway (CPU)

## Архитектура

```
Telegram → Railway (bot.py, CPU) → Modal (modal_app.py, GPU T4) → Telegram
```

## Деплой

### 1. Modal (GPU endpoint)

```bash
# Установить Modal CLI
pip install modal

# Авторизоваться
modal setup

# Задеплоить (скачает модель ~2-3GB, один раз)
modal deploy modal_app.py
```

После деплоя Modal покажет URL вида:
```
https://YOUR_USERNAME--omnivoice-tts-voicecloner-generate.modal.run
```

### 2. Railway (Telegram bot)

Env vars:
- `TELEGRAM_TOKEN` — от @BotFather
- `MODAL_ENDPOINT` — URL от Modal (см. выше)

```bash
# В Codespaces
git push  # auto-deploy
```

## Использование

1. `/start` — начать
2. Отправить голосовое (3–10 сек)
3. Написать текст → получить озвучку
4. `/voice` — сменить голос

## Стоимость

- Modal T4: ~$0.59/час
- Один инференс ~5 сек: ~$0.0008
- Container idle timeout: 5 мин (потом GPU отключается)
- $5 кредита ≈ 6000 генераций

## Roadmap

- [ ] MVP — клон голоса без хранения
- [ ] v2 — сохранение голосов в Modal Volume (база голосов)
- [ ] v3 — оплата звёздами Telegram
- [ ] v4 — Voice Design (описание голоса текстом)
