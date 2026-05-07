import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TFL_API_KEY = os.environ["TFL_API_KEY"]
EPC_API_KEY = os.environ.get("EPC_API_KEY", "")  # base64(email:key) from epc.opendatacommunities.org


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS = [x.strip() for x in os.environ.get("TELEGRAM_CHAT_IDS", "").split(",") if x.strip()]

# Legacy CallMeBot (kept for reference)
CALLMEBOT_API_KEY = os.environ.get("CALLMEBOT_API_KEY", "")
WHATSAPP_PHONE = os.environ.get("WHATSAPP_PHONE", "")

SCORE_THRESHOLD = int(os.environ.get("SCORE_THRESHOLD", "7"))
