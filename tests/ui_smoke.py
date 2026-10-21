import os, tempfile
os.environ["KIVY_NO_ARGS"] = "1"
from kivy.config import Config
Config.set("graphics", "width", "400"); Config.set("graphics", "height", "800")
from kivy.clock import Clock
import main
from main import MailApp

class T(MailApp):
    user_data_dir_override = tempfile.mkdtemp()
    @property
    def user_data_dir(self): return self.user_data_dir_override

app = T()
main.SMTP_PORT = 2598
def run(dt):
    try:
        r = app.root
        assert r.current == "setup"
        s = r.get_screen("setup")
        s.create("me@localhost", "short", "short"); print("short pw ->", s.ids.err.text)
        s.create("me@localhost", "apppass-123", "apppass-123"); assert r.current == "main", r.current
        app.svc.send(["me@localhost"], "Hello UI", "body text")
        m = r.get_screen("main"); m.refresh(); print("inbox children:", len(m.ids.list_box.children), "|", m.ids.status.text)
        for f in ("sent", "outbox", "info"): m.set_folder(f); print(f, "->", len(m.ids.list_box.children))
        m.set_folder("inbox")
        mid = app.svc.list_messages("inbox")[0]["id"]; app.open_message(mid)
        print("read:", r.get_screen("read").ids.head.text.splitlines()[0])
        app.goto("compose"); c = r.get_screen("compose"); c.ids.to.text = "me@localhost"; c.ids.subject.text = "via ui"; c.send()
        print("after send screen:", r.current, "| inbox count:", len(app.svc.list_messages("inbox")))
        app.lock(); l = r.get_screen("login"); l.unlock("bad"); print("bad unlock ->", l.ids.err.text); l.unlock("apppass-123"); print("unlocked ->", r.current)
        print("UI SMOKE OK")
    except Exception:
        import traceback; traceback.print_exc()
    finally:
        app.stop()
Clock.schedule_once(run, 1.5)
app.run()
