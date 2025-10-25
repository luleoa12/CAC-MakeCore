import os
import requests
from dotenv import load_dotenv

load_dotenv()


def _render_verification_html(code):
    with open('templates/email_template.html', 'r') as file:
        template = file.read()
    return (
        template
        .replace('{{code[0]}}', code[0])
        .replace('{{code[1]}}', code[1])
        .replace('{{code[2]}}', code[2])
        .replace('{{code[3]}}', code[3])
    )


def send_verification_email(to_email, code):
    mailgun_key = os.getenv('MAILGUN_KEY')
    mailgun_domain = os.getenv('MAILGUN_DOMAIN')
    if not mailgun_key or not mailgun_domain:
        print('[Email Error] MAILGUN_KEY and/or MAILGUN_DOMAIN are not set')
        return False

    from_name = os.getenv('MAILGUN_FROM_NAME', 'MakeCore')
    from_email = os.getenv('MAILGUN_FROM_EMAIL', f'noreply@{mailgun_domain}')
    sender = f"{from_name} <{from_email}>"

    html_content = _render_verification_html(code)

    try:
        response = requests.post(
            f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
            auth=("api", mailgun_key),
            data={
                "from": sender,
                "to": [to_email],
                "subject": "MakeCore Email Verification",
                "html": html_content,
            },
            timeout=10,
        )
        if response.status_code >= 200 and response.status_code < 300:
            return True
        print(f"[Email Error] Mailgun API responded with {response.status_code}: {response.text}")
        return False
    except Exception as e:
        print(f"[Email Error] {e}")
        return False