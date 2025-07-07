from django.conf import settings
from django.http import HttpRequest
import os


def cafe_name(request: HttpRequest) -> dict:
    """Adds site-wide settings to the context."""
    file_path = os.path.join(settings.BASE_DIR, "main/cafe_name.txt")

    try:
        with open(file_path, "r") as file:
            file_content = file.read()
            return {
                "CAFE_NAME": f"{file_content}",
            }
    except FileNotFoundError:
        return {
            "CAFE_NAME": f"{file_content}",
        }
