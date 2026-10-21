"""Kivy UI for the self-hosted mail server (runs on Android and desktop)."""
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import StringProperty
from kivy.uix.button import Button
from kivy.uix.screenmanager import Screen, ScreenManager

from mailcore import MailService

SMTP_PORT = 2525  # Android blocks ports below 1024 for normal apps

KV = """
#:import dp kivy.metrics.dp

<WrapLabel@Label>:
    text_size: self.width, None
    size_hint_y: None
    height: self.texture_size[1] + dp(8)
    halign: 'left'
    valign: 'top'

<Field@TextInput>:
    multiline: False
    size_hint_y: None
    height: dp(46)
    padding: dp(10), dp(12)

<Btn@Button>:
    size_hint_y: None
    height: dp(48)

<SetupScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(20)
        spacing: dp(10)
        Label:
            text: 'Create your mailbox'
            font_size: '22sp'
            size_hint_y: None
            height: dp(50)
        WrapLabel:
            text: 'Your address and an app password. The app password locks this app and is what other mail apps use to log in to your server.'
        Field:
            id: addr
            hint_text: 'you@yourdomain.com  (or me@localhost to test)'
            input_type: 'mail'
            keyboard_suggestions: False
        Field:
            id: pw
            hint_text: 'App password (min 8 characters)'
            password: True
        Field:
            id: pw2
            hint_text: 'Repeat app password'
            password: True
        WrapLabel:
            id: err
            color: 1, .3, .3, 1
        Btn:
            text: 'Create mailbox'
            on_release: root.create(addr.text, pw.text, pw2.text)
        Widget:

<LoginScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(20)
        spacing: dp(10)
        Widget:
        Label:
            text: 'Unlock mail'
            font_size: '22sp'
            size_hint_y: None
            height: dp(50)
        Label:
            id: who
            size_hint_y: None
            height: dp(30)
        Field:
            id: pw
            hint_text: 'App password'
            password: True
            focus: True
            on_text_validate: root.unlock(pw.text)
        WrapLabel:
            id: err
            color: 1, .3, .3, 1
        Btn:
            text: 'Unlock'
            on_release: root.unlock(pw.text)
        Widget:

<MainScreen>:
    BoxLayout:
        orientation: 'vertical'
        Label:
            id: status
            size_hint_y: None
            height: dp(34)
            font_size: '13sp'
        BoxLayout:
            size_hint_y: None
            height: dp(44)
            ToggleButton:
                id: t_inbox
                text: 'Inbox'
                group: 'tabs'
                state: 'down'
                allow_no_selection: False
                on_release: root.set_folder('inbox')
            ToggleButton:
                text: 'Sent'
                group: 'tabs'
                allow_no_selection: False
                on_release: root.set_folder('sent')
            ToggleButton:
                text: 'Outbox'
                group: 'tabs'
                allow_no_selection: False
                on_release: root.set_folder('outbox')
            ToggleButton:
                text: 'Info'
                group: 'tabs'
                allow_no_selection: False
                on_release: root.set_folder('info')
        ScrollView:
            do_scroll_x: False
            GridLayout:
                id: list_box
                cols: 1
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(2)
        BoxLayout:
            size_hint_y: None
            height: dp(52)
            padding: dp(4)
            spacing: dp(4)
            Button:
                text: 'Compose'
                on_release: app.goto('compose')
            Button:
                text: 'Lock'
                size_hint_x: .35
                on_release: app.lock()

<ReadScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(10)
        spacing: dp(6)
        WrapLabel:
            id: head
            font_size: '17sp'
            bold: True
        ScrollView:
            do_scroll_x: False
            WrapLabel:
                id: body
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            spacing: dp(6)
            Button:
                text: 'Back'
                on_release: app.goto('main', 'right')
            Button:
                text: 'Reply'
                on_release: root.reply()
            Button:
                text: 'Delete'
                on_release: root.delete()

<ComposeScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(10)
        spacing: dp(8)
        Field:
            id: to
            hint_text: 'To (separate several with commas)'
            input_type: 'mail'
        Field:
            id: subject
            hint_text: 'Subject'
        TextInput:
            id: body
            hint_text: 'Message'
        WrapLabel:
            id: err
            color: 1, .3, .3, 1
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            spacing: dp(6)
            Button:
                text: 'Cancel'
                on_release: app.goto('main', 'right')
            Button:
                text: 'Send'
                on_release: root.send()
"""


class SetupScreen(Screen):
    def create(self, addr, pw, pw2):
        if pw != pw2:
            self.ids.err.text = "Passwords do not match"
            return
        try:
            App.get_running_app().svc.setup(addr, pw)
        except ValueError as e:
            self.ids.err.text = str(e)
            return
        App.get_running_app().unlocked()


class LoginScreen(Screen):
    def on_pre_enter(self):
        self.ids.who.text = App.get_running_app().svc.address or ""
        self.ids.pw.text = ""
        self.ids.err.text = ""

    def unlock(self, pw):
        if App.get_running_app().svc.check_password(pw):
            App.get_running_app().unlocked()
        else:
            self.ids.err.text = "Wrong app password"


class MainScreen(Screen):
    folder = StringProperty("inbox")
    _sig = None
    _ev = None

    def on_enter(self):
        self._sig = None
        self.refresh()
        self._ev = Clock.schedule_interval(lambda dt: self.refresh(), 4)

    def on_leave(self):
        if self._ev:
            self._ev.cancel()

    def set_folder(self, f):
        self.folder = f
        self._sig = None
        self.refresh()

    def refresh(self):
        svc = App.get_running_app().svc
        ids = self.ids
        state = "running" if svc.running else "stopped"
        ids.status.text = f"{svc.address}   |   SMTP {state} on {svc.local_ip()}:{svc.port}"
        unread = svc.unread_count()
        ids.t_inbox.text = f"Inbox ({unread})" if unread else "Inbox"

        if self.folder in ("inbox", "sent"):
            rows = svc.list_messages(self.folder)
            sig = (self.folder, [(r["id"], r["is_read"]) for r in rows])
        elif self.folder == "outbox":
            rows = svc.list_outbox()
            sig = (self.folder, [(r["id"], r["status"], r["attempts"]) for r in rows])
        else:
            rows, sig = [], ("info", svc.port, svc.local_ip())
        if sig == self._sig:
            return
        self._sig = sig

        box = ids.list_box
        box.clear_widgets()
        if self.folder == "info":
            self._info(box, svc)
            return
        if not rows:
            box.add_widget(self._label("Nothing here yet."))
        for r in rows:
            if self.folder == "outbox":
                txt = f"To: {r['rcpt_to']}\n{r['status']} - tries: {r['attempts']}"
                if r["last_error"]:
                    txt += f"\n{r['last_error']}"
                box.add_widget(self._label(txt))
            else:
                who = r["mail_from"] if self.folder == "inbox" else "To: " + (r["rcpt_to"] or "")
                bold = self.folder == "inbox" and not r["is_read"]
                b = Button(text=f"{'[b]' if bold else ''}{who}\n{r['subject']}{'[/b]' if bold else ''}",
                           markup=True, size_hint_y=None, height=140, halign="left", valign="middle",
                           background_color=(.2, .2, .25, 1))
                b.bind(size=lambda w, s: setattr(w, "text_size", (s[0] - 30, None)))
                b.bind(on_release=lambda w, mid=r["id"]: App.get_running_app().open_message(mid))
                box.add_widget(b)

    @staticmethod
    def _label(text):
        from kivy.uix.label import Label
        l = Label(text=text, size_hint_y=None, halign="left", valign="top", padding=(12, 10))
        l.bind(width=lambda w, v: setattr(w, "text_size", (v - 24, None)))
        l.bind(texture_size=lambda w, s: setattr(w, "height", s[1] + 24))
        return l

    def _info(self, box, svc):
        box.add_widget(self._label(
            "Connect another mail app (Thunderbird, K-9, a script...):\n\n"
            f"Server:   {svc.local_ip()}\nSMTP port: {svc.port}\n"
            f"Username: {svc.address}\nPassword: your app password\n"
            "Security: none (plain, same Wi-Fi only)\n\n"
            "Receiving: other servers deliver to your address on port 25 via your domain's MX record. "
            "A phone normally has no public IP, so for internet mail forward port 25 -> "
            f"{svc.port} on a VPS/tunnel."))


class ReadScreen(Screen):
    mid = None
    mail_from = ""
    subject = ""

    def show(self, mid):
        m = App.get_running_app().svc.get_message(mid)
        if not m:
            return
        self.mid, self.mail_from, self.subject = mid, m["mail_from"], m["subject"]
        self.ids.head.text = f"{m['subject']}\nFrom: {m['mail_from']}\nTo: {m['rcpt_to']}\n{m['date']}"
        self.ids.body.text = m["body"] or "(empty)"

    def reply(self):
        c = App.get_running_app().root.get_screen("compose")
        c.prefill(self.mail_from, "Re: " + self.subject.removeprefix("Re: "))
        App.get_running_app().goto("compose")

    def delete(self):
        App.get_running_app().svc.delete_message(self.mid)
        App.get_running_app().goto("main", "right")


class ComposeScreen(Screen):
    def prefill(self, to, subject):
        self.ids.to.text, self.ids.subject.text, self.ids.body.text, self.ids.err.text = to, subject, "", ""

    def on_pre_enter(self):
        self.ids.err.text = ""

    def send(self):
        try:
            App.get_running_app().svc.send(self.ids.to.text.split(","), self.ids.subject.text,
                                           self.ids.body.text)
        except ValueError as e:
            self.ids.err.text = str(e)
            return
        self.prefill("", "")
        App.get_running_app().goto("main", "right")


class MailApp(App):
    title = "Mail"

    def build(self):
        Builder.load_string(KV)
        Window.softinput_mode = "below_target"
        self.svc = MailService(self.user_data_dir)
        sm = ScreenManager()
        for cls, name in [(SetupScreen, "setup"), (LoginScreen, "login"), (MainScreen, "main"),
                          (ReadScreen, "read"), (ComposeScreen, "compose")]:
            sm.add_widget(cls(name=name))
        sm.current = "login" if self.svc.is_configured() else "setup"
        Window.bind(on_keyboard=self._on_key)
        return sm

    def unlocked(self):
        if not self.svc.running:
            try:
                self.svc.start(port=SMTP_PORT)
            except Exception as e:  # e.g. port already in use
                print("SMTP start failed:", e)
        self.goto("main")

    def lock(self):
        self.goto("login")  # server keeps running so mail still arrives

    def goto(self, name, direction="left"):
        self.root.transition.direction = direction
        self.root.current = name

    def open_message(self, mid):
        self.root.get_screen("read").show(mid)
        self.goto("read")

    def _on_key(self, window, key, *args):
        if key == 27:  # Android back button
            cur = self.root.current
            if cur in ("read", "compose"):
                self.goto("main", "right")
                return True
            return False  # let Android close/minimise from main/login
        return False

    def on_pause(self):
        return True  # keep running when the app is minimised

    def on_stop(self):
        self.svc.stop()


if __name__ == "__main__":
    MailApp().run()
