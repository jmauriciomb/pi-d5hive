import os
import json


def send_notification(env: str, user: str, get_secret, subject: str, text: str, html: str,  email_addresses: list[str],) -> None:

    if not email_addresses:
        print("  Sem endereços de email")
        return

    if env == "render":
        _send_brevo(subject, text, html, email_addresses)
    else:
        _send_gmail(get_secret, user, subject, text, html, email_addresses)


def _send_brevo(subject: str, text: str, html: str, addresses: list[str]) -> None:
    import requests as _req

    resp = _req.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key":      os.getenv("BREVO_PASSWORD"),
            "Content-Type": "application/json",
        },
        json={
            "sender":      {"email": os.getenv("BREVO_FROM")},
            "to":          [{"email": e} for e in addresses],
            "subject":     subject,
            "textContent": text,
            "htmlContent": html,
        },
        timeout=30,
    )
    resp.raise_for_status()
    print("  Notificação enviada via Brevo ✅:", resp.json())


def _send_gmail(get_secret, user: str, subject: str, text: str, html: str, addresses: list[str]) -> None:
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import smtplib
    import ssl as _ssl

    raw = get_secret(get_secret(f"configGMail_{user}_json"))
    if raw is None:
        raise ValueError(f"Credenciais Gmail em falta (get_secret(configGMail_{user}_json))")
    creds = json.loads(raw)

    message             = MIMEMultipart("alternative")
    message["Subject"]  = subject
    message["From"]     = creds["UserFrom"]
    message["To"]       = ", ".join(addresses)
    message["Reply-To"] = creds["UserFrom"]
    message.attach(MIMEText(text,  "plain"))
    message.attach(MIMEText(html,  "html"))

    ctx = _ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
        server.login(creds["UserName"], creds["UserPwd"])
        server.sendmail(creds["UserFrom"], addresses, message.as_string())
    print("  Notificação enviada via Gmail ✅")
