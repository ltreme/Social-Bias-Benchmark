# telegram_notifier.py

import os
import sys
from typing import Optional

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def send_telegram_message(
    text: str = "",
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> None:
    """
    Send a plain text message via Telegram Bot API.
    """
    bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        raise RuntimeError("Telegram bot token or chat ID not set")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(
        url, data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    )
    resp.raise_for_status()


def send_telegram_document(
    file_path: str,
    caption: str = "",
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> None:
    """
    Send a file via Telegram Bot API (sendDocument).
    """
    bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        raise RuntimeError("Telegram bot token or chat ID not set")
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
        resp = requests.post(url, data=data, files=files, timeout=60)
    resp.raise_for_status()


def notify_job_completion(
    job_name: str, job_id: str, exit_code: int, output_file: Optional[str] = None
) -> None:
    """
    Notify on job completion, optionally sending the output file.
    """
    status_emoji = "✅" if exit_code == 0 else "❌"
    base_msg = f"{status_emoji} Slurm job *{job_name}* (ID: {job_id}) finished with exit code {exit_code}."
    send_telegram_message(text=base_msg)

    # if output_file:
    #     caption = f"Output of job *{job_name}* (ID: {job_id}):"
    #     send_telegram_document(file_path=output_file, caption=caption)


if __name__ == "__main__":
    # Usage: python telegram_notifier.py <job_name> <job_id> <exit_code> [output_file]
    args = sys.argv[1:]
    if len(args) < 3:
        print(
            "Usage: telegram_notifier.py <job_name> <job_id> <exit_code> [output_file]",
            file=sys.stderr,
        )
        sys.exit(1)

    job_name, job_id, exit_code_str = args[:3]
    exit_code = int(exit_code_str)
    output_file = args[3] if len(args) >= 4 else None

    notify_job_completion(job_name, job_id, exit_code, output_file)
