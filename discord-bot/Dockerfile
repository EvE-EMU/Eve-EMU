FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /bot

RUN pip install --no-cache-dir "pip==26.1.2"

COPY discord-bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY discord-bot/bot/ .

CMD ["python", "eve_mining_timer_bot.py"]
