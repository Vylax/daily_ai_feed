import os
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Force reload of environment variables
load_dotenv(override=True)

# Print email configuration values
print("=== Email Configuration Values ===")
print(f"EMAIL_PROVIDER: '{os.getenv('EMAIL_PROVIDER')}'")
print(f"RECIPIENT_EMAIL: '{os.getenv('RECIPIENT_EMAIL')}'")
print(f"SENDER_EMAIL: '{os.getenv('SENDER_EMAIL')}'")
print(f"EMAIL_SUBJECT_PREFIX: '{os.getenv('EMAIL_SUBJECT_PREFIX')}'")
print(f"SMTP_SERVER: '{os.getenv('SMTP_SERVER')}'")
print(f"SMTP_PORT: '{os.getenv('SMTP_PORT')}'")
print(f"SMTP_USERNAME: '{os.getenv('SMTP_USERNAME')}'")
# Don't print the actual password, just whether it exists
print(f"SMTP_PASSWORD: '{'*****' if os.getenv('SMTP_PASSWORD') else 'MISSING'}'")

# Print the raw value to check if there are any comments or quotes being included
raw_provider = os.getenv('EMAIL_PROVIDER')
print(f"\nRaw EMAIL_PROVIDER value: '{raw_provider}'")
print(f"Length: {len(raw_provider) if raw_provider else 0}")
print(f"Character codes: {[ord(c) for c in raw_provider] if raw_provider else []}") 