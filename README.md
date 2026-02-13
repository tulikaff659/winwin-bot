# WinWin Bukmeker Bot

Telegram bot for game analysis and statistics.

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and get the token.
2. Replace `ADMIN_ID` in `bot.py` with your Telegram user ID.
3. Deploy to Railway (see below).

## Railway Deployment

1. Push this repository to GitHub.
2. Create a new project on Railway and connect your GitHub repo.
3. Add environment variable `BOT_TOKEN` with your bot token.
4. Deploy. The bot will start automatically.

## Usage

- `/start` – welcome message and games list.
- `/admin` – admin panel (only for admin).
