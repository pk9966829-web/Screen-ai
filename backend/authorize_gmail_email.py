"""Authorize the local CHERRY AI backend to send transactional Gmail messages."""
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().with_name(".env"))

from email_delivery import authorize_gmail_oauth


if __name__ == "__main__":
    authorize_gmail_oauth()
    print("Gmail send-only authorization saved locally. Do not share or commit the token file.")
