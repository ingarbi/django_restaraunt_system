import json
import os
import hmac
import hashlib
from datetime import datetime
from django.shortcuts import redirect
from django.utils.timezone import now, make_aware

SECRET_KEY = b"MY_SUPER_SECRET_KEY"  # Keep this only with YOU, never share

def verify_license(file_path="license.json"):
    if not os.path.exists(file_path):
        return None, False
    
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except Exception:
        return None, False

    expires_at = datetime.fromisoformat(data["expires_at"])
    signature = data["signature"]

    # Verify signature
    
    msg = f"{data['client']}|{data['expires_at']}".encode()
    expected = hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()

    if signature != expected:
        return None, False
    
    return expires_at, True


class SubscriptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        expires_at, valid = verify_license()
        if not valid or expires_at.date() < now().date():
            if not request.path.startswith("/subscription-expired/"):
                return redirect("subscription_expired")
        return self.get_response(request)
