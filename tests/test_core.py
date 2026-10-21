
import smtplib, tempfile, time
from email.message import EmailMessage
from mailcore import MailService

svc = MailService(tempfile.mkdtemp())
assert not svc.is_configured()
for bad in [("nope", "longenough1"), ("me@localhost", "short")]:
    try: svc.setup(*bad); raise SystemExit("should have failed")
    except ValueError as e: print("validation ok:", e)
svc.setup("me@localhost", "my-app-pass-1")
assert svc.check_password("my-app-pass-1") and not svc.check_password("wrong")
svc.start(port=2599)

def mk(frm, to, subj):
    m = EmailMessage(); m["From"], m["To"], m["Subject"] = frm, to, subj; m.set_content("hello body"); return m

# 1. anonymous delivery to local address works
with smtplib.SMTP("127.0.0.1", 2599, timeout=10) as s: s.send_message(mk("x@test.com", "me@localhost", "anon in"))
# 2. anonymous relay to outside is refused
try:
    with smtplib.SMTP("127.0.0.1", 2599, timeout=10) as s: s.send_message(mk("x@test.com", "victim@gmail.com", "relay"))
    raise SystemExit("OPEN RELAY!")
except smtplib.SMTPRecipientsRefused: print("relay refused ok")
# 3. wrong password rejected
try:
    with smtplib.SMTP("127.0.0.1", 2599, timeout=10) as s: s.login("me@localhost", "wrong")
    raise SystemExit("bad auth accepted")
except smtplib.SMTPAuthenticationError: print("bad password rejected ok")
# 4. authenticated client can send (local + remote queued)
with smtplib.SMTP("127.0.0.1", 2599, timeout=10) as s:
    s.login("me@localhost", "my-app-pass-1")
    s.send_message(mk("me@localhost", "me@localhost, someone@example.org", "auth send"))
# 5. UI-side send
svc.send(["me@localhost"], "from app", "typed in the app")
time.sleep(0.5)
print("inbox:", [m["subject"] for m in svc.list_messages("inbox")])
print("sent :", [m["subject"] for m in svc.list_messages("sent")])
print("outbox:", [(o["rcpt_to"], o["status"]) for o in svc.list_outbox()])
print("unread:", svc.unread_count()); m = svc.get_message(svc.list_messages("inbox")[0]["id"]); print("body:", m["body"].strip())
svc.stop(); print("ALL OK")
