import json
import hmac
import hashlib
from datetime import datetime, timedelta
import argparse

SECRET_KEY = b"MY_SUPER_SECRET_KEY"  # Must match middleware

def generate_license(client, days):
    expires_at = (datetime.now() + timedelta(days=days)).replace(microsecond=0)
    msg = f"{client}|{expires_at.isoformat()}".encode()
    signature = hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()

    data = {
        "client": client,
        "expires_at": expires_at.isoformat(),
        "signature": signature,
    }

    filename = f"license_{client}.json"
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

    print(f"License file generated: {filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True, help="Client ID/Name")
    parser.add_argument("--days", type=int, required=True, help="Number of days valid")
    args = parser.parse_args()

    generate_license(args.client, args.days)
