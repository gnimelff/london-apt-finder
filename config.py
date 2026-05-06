import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TFL_API_KEY = os.environ["TFL_API_KEY"]
EPC_API_KEY = os.environ.get("EPC_API_KEY", "")  # base64(email:key) from epc.opendatacommunities.org

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

CALLMEBOT_API_KEY = os.environ["CALLMEBOT_API_KEY"]
WHATSAPP_PHONE = os.environ["WHATSAPP_PHONE"]  # format: 447xxxxxxxxx (no + prefix)

SCORE_THRESHOLD = int(os.environ.get("SCORE_THRESHOLD", "7"))
