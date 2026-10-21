"""
mailcore.py - mail engine (no UI). SMTP server + SMTP sender + SQLite storage.

* One mailbox per install, protected by an "app password" (stored as a salted
  PBKDF2 hash, never in plain text).
* Anyone can deliver mail TO your address (normal SMTP receiving).
* Only a client that logs in (AUTH LOGIN/PLAIN) with your address + app password
  can SEND mail through the server, so it is never an open relay.
"""
import hashlib
import hmac
import os
import secrets
import smtplib
import socket
import sqlite3
import threading
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formatdate, make_msgid, parseaddr

import dns.resolver
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult, LoginPassword

MAX_ATTEMPTS = 6
PBKDF2_ITERS = 200_000


class _Handler:
    """aiosmtpd handler: decides who may deliver / relay and stores the mail."""

    def __init__(self, svc):
        self.svc = svc

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        domain = address.rsplit("@", 1)[-1].lower()
        if domain == self.svc.domain or session.authenticated:
            envelope.rcpt_tos.append(address)
            return "250 OK"
        return "550 5.7.1 Relaying denied"

    async def handle_DATA(self, server, session, envelope):
        self.svc._ingest(
            envelope.mail_from, list(envelope.rcpt_tos), envelope.content,
            authenticated=bool(session.authenticated),
        )
        return "250 Message accepted for delivery"


class MailService:
    def __init__(self, data_dir):
        os.makedirs(data_dir, exist_ok=True)
        self.db_path = os.path.join(data_dir, "mail.db")
        self.port = 2525
        self.controller = None
        self._worker = None
        self._stop = threading.Event()
        self._init_db()

    # ------------------------------------------------------------------ db
    def _conn(self):
        c = sqlite3.connect(self.db_path, timeout=30)
        c.row_factory = sqlite3.Row
        return c

    def _init_db(self):
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder TEXT NOT NULL,            -- inbox / sent
                    mail_from TEXT, rcpt_to TEXT, subject TEXT, body TEXT,
                    raw BLOB, date TEXT, is_read INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mail_from TEXT NOT NULL, rcpt_to TEXT NOT NULL, raw BLOB NOT NULL,
                    attempts INTEGER DEFAULT 0, status TEXT DEFAULT 'pending',
                    last_error TEXT, next_try REAL DEFAULT 0
                );
                """
            )

    def _get(self, key):
        with self._conn() as c:
            r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else None

    def _set(self, key, value):
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))

    # ------------------------------------------------------------- account
    @property
    def address(self):
        return self._get("address")

    @property
    def domain(self):
        a = self.address
        return a.rsplit("@", 1)[-1] if a else None

    def is_configured(self):
        return bool(self._get("pw_hash"))

    @staticmethod
    def _hash(password, salt):
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERS).hex()

    def setup(self, address, password):
        address = address.strip().lower()
        _, parsed = parseaddr(address)
        if parsed != address or "@" not in address or "." not in address.rsplit("@", 1)[-1] and \
                address.rsplit("@", 1)[-1] != "localhost":
            raise ValueError("Enter a valid address like you@yourdomain.com")
        if len(password) < 8:
            raise ValueError("App password must be at least 8 characters")
        salt = secrets.token_bytes(16)
        self._set("address", address)
        self._set("pw_salt", salt.hex())
        self._set("pw_hash", self._hash(password, salt))

    def check_password(self, password):
        salt, stored = self._get("pw_salt"), self._get("pw_hash")
        if not salt or not stored:
            return False
        return hmac.compare_digest(self._hash(password, bytes.fromhex(salt)), stored)

    # --------------------------------------------------------- SMTP server
    def _authenticator(self, server, session, envelope, mechanism, auth_data):
        ok = False
        if isinstance(auth_data, LoginPassword):
            user = auth_data.login.decode("utf-8", "ignore").strip().lower()
            pw = auth_data.password.decode("utf-8", "ignore")
            ok = user == self.address and self.check_password(pw)
        return AuthResult(success=ok, handled=ok)  # handled=False lets aiosmtpd send the 535 reply

    def start(self, port=2525, host="0.0.0.0"):
        if self.controller:
            return
        self.port = port
        self.controller = Controller(
            _Handler(self), hostname=host, port=port, ready_timeout=15,
            authenticator=self._authenticator, auth_required=False,
            auth_require_tls=False,   # plain LAN use; put TLS/VPN in front for the internet
        )
        self.controller.start()
        self._stop.clear()
        self._worker = threading.Thread(target=self._outbox_loop, daemon=True)
        self._worker.start()

    def stop(self):
        self._stop.set()
        if self.controller:
            self.controller.stop()
            self.controller = None

    @property
    def running(self):
        return self.controller is not None

    @staticmethod
    def local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    # ------------------------------------------------------------- storage
    def _store(self, folder, mail_from, rcpt_to, raw, is_read=0):
        msg = BytesParser(policy=policy.default).parsebytes(raw)
        part = msg.get_body(preferencelist=("plain", "html"))
        try:
            body = part.get_content() if part else ""
        except Exception:
            body = ""
        with self._conn() as c:
            c.execute(
                "INSERT INTO messages (folder, mail_from, rcpt_to, subject, body, raw, date, is_read)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (folder, mail_from, rcpt_to, str(msg.get("Subject", "(no subject)")), body, raw,
                 str(msg.get("Date", formatdate(localtime=True))), is_read),
            )

    def _ingest(self, mail_from, rcpts, raw, authenticated):
        if authenticated:  # message submitted by the owner -> keep a copy in Sent
            self._store("sent", mail_from, ", ".join(rcpts), raw, is_read=1)
        for rcpt in rcpts:
            rcpt = parseaddr(rcpt)[1]
            if rcpt.rsplit("@", 1)[-1].lower() == self.domain:
                self._store("inbox", mail_from, rcpt, raw)
            elif authenticated:
                with self._conn() as c:
                    c.execute("INSERT INTO outbox (mail_from, rcpt_to, raw) VALUES (?,?,?)",
                              (mail_from, rcpt, raw))

    def send(self, recipients, subject, body):
        """Called by the app UI to send mail from your own address."""
        recipients = [r.strip() for r in recipients if r.strip()]
        if not recipients:
            raise ValueError("Add at least one recipient")
        msg = EmailMessage()
        msg["From"] = self.address
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject or "(no subject)"
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=self.domain)
        msg.set_content(body)
        self._ingest(self.address, recipients, msg.as_bytes(), authenticated=True)

    # ------------------------------------------------------------- queries
    def list_messages(self, folder, limit=200):
        with self._conn() as c:
            return c.execute("SELECT id, mail_from, rcpt_to, subject, date, is_read FROM messages"
                             " WHERE folder=? ORDER BY id DESC LIMIT ?", (folder, limit)).fetchall()

    def get_message(self, mid):
        with self._conn() as c:
            c.execute("UPDATE messages SET is_read=1 WHERE id=?", (mid,))
            return c.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()

    def delete_message(self, mid):
        with self._conn() as c:
            c.execute("DELETE FROM messages WHERE id=?", (mid,))

    def unread_count(self):
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) n FROM messages WHERE folder='inbox' AND is_read=0"
                             ).fetchone()["n"]

    def list_outbox(self):
        with self._conn() as c:
            return c.execute("SELECT id, rcpt_to, status, attempts, last_error FROM outbox"
                             " ORDER BY id DESC LIMIT 100").fetchall()

    # ------------------------------------------------------------ outbound
    def _deliver(self, mail_from, rcpt, raw):
        domain = rcpt.rsplit("@", 1)[-1]
        # Android has no /etc/resolv.conf, so use explicit public resolvers.
        res = dns.resolver.Resolver(configure=False)
        res.nameservers = ["8.8.8.8", "1.1.1.1"]
        res.lifetime = 10
        answers = res.resolve(domain, "MX")
        hosts = [str(r.exchange).rstrip(".") for r in sorted(answers, key=lambda r: r.preference)]
        last = None
        for host in hosts:
            try:
                with smtplib.SMTP(host, 25, timeout=30) as s:
                    s.ehlo(self.domain)
                    if s.has_extn("starttls"):
                        s.starttls()
                        s.ehlo(self.domain)
                    s.sendmail(mail_from, [rcpt], raw)
                return
            except Exception as e:
                last = e
        raise last or RuntimeError("No MX host reachable")

    def _outbox_loop(self):
        import time
        while not self._stop.is_set():
            try:
                with self._conn() as c:
                    rows = c.execute("SELECT * FROM outbox WHERE status='pending' AND next_try<=?",
                                     (time.time(),)).fetchall()
                for r in rows:
                    try:
                        self._deliver(r["mail_from"], r["rcpt_to"], r["raw"])
                        with self._conn() as c:
                            c.execute("UPDATE outbox SET status='sent', last_error=NULL WHERE id=?",
                                      (r["id"],))
                    except Exception as e:
                        n = r["attempts"] + 1
                        with self._conn() as c:
                            c.execute("UPDATE outbox SET attempts=?, status=?, last_error=?, next_try=?"
                                      " WHERE id=?",
                                      (n, "failed" if n >= MAX_ATTEMPTS else "pending", str(e)[:200],
                                       time.time() + min(3600, 60 * 2 ** n), r["id"]))
            except Exception:
                pass
            self._stop.wait(10)
