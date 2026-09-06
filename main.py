import sys,json,base64,mimetypes,html,os
from urllib.parse import urlparse
import requests

from PySide6.QtCore import Qt,Signal,QPropertyAnimation,QParallelAnimationGroup,QThread,QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,
    QLineEdit,QTextEdit,QPushButton,QMessageBox,QFileDialog,QGroupBox,
    QSplitter,QScrollArea,QCheckBox,QColorDialog,QDateTimeEdit,QToolTip
)

MAX_CONTENT,MAX_FIELDS=2000,25
MAX_TITLE,MAX_DESCRIPTION=256,4096
MAX_AUTHOR,MAX_FIELD_NAME,MAX_FIELD_VALUE,MAX_FOOTER=256,256,1024,2048
MAX_EMBED_CONTENT=6000
MAX_AVATAR_BYTES=8*1024*1024
DEFAULT_COLOR="#5865F2"

avatar_path=""
embed_color=DEFAULT_COLOR
preview_window=None


def tooltip(w,text):
    w.setToolTip(text)
    w.setToolTipDuration(10000)


def button_style(color=DEFAULT_COLOR):
    return f"""
    QPushButton {{
        background:{color};
        color:white;
        border:1px solid rgba(255,255,255,.06);
        border-radius:9px;
        padding:9px 13px;
        font-weight:600;
    }}
    QPushButton:hover {{background:#6d78ff;}}
    QPushButton:pressed {{background:#4752c4;}}
    QPushButton:disabled {{background:#292b30;color:#555;}}
    """


def set_status(text,color="#949ba4"):
    status_label.setText(f"●  {text}")
    status_label.setStyleSheet(f"color:{color};font-weight:600;")


def valid_url(url):
    try:
        p=urlparse(url)
        return bool(url) and p.scheme in ("http","https") and bool(p.netloc)
    except Exception:
        return False


def valid_webhook(url):
    try:
        p=urlparse(url)
        parts=p.path.split("/")
        return (
            p.scheme=="https"
            and p.netloc.lower() in {"discord.com","discordapp.com"}
            and len(parts)==5
            and parts[1:3]==["api","webhooks"]
            and parts[3].isdigit()
            and bool(parts[4])
        )
    except Exception:
        return False


def choose_image(title):
    return QFileDialog.getOpenFileName(
        window,title,"","Images (*.png *.jpg *.jpeg *.gif *.webp)"
    )[0]


def image_data_url(path):
    try:
        mime=mimetypes.guess_type(path)[0]
        if mime not in {"image/png","image/jpeg","image/gif","image/webp"} or os.path.getsize(path)>MAX_AVATAR_BYTES:
            return None
        with open(path,"rb") as f:
            return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"
    except OSError:
        return None


def insert_format(start,end):
    c=message_input.textCursor()
    selected=c.selectedText()
    c.insertText(f"{start}{selected}{end}" if selected else start+end)

    if not selected:
        c.movePosition(c.MoveOperation.Left,n=len(end))
        message_input.setTextCursor(c)

    message_input.setFocus()


def markdown_to_html(text):
    text=html.escape(text)

    for marker,op,cl in (
        ("||","<span style='background:#202225;color:#202225;'>","</span>"),
        ("**","<b>","</b>"),
        ("__","<u>","</u>"),
        ("~~","<s>","</s>"),
        ("`","<code style='background:#1e1f22;padding:2px 4px;border-radius:3px;'>","</code>"),
        ("*","<i>","</i>")
    ):
        while marker in text:
            a=text.find(marker)
            b=text.find(marker,a+len(marker))
            if b<0:
                break
            text=text[:a]+op+text[a+len(marker):b]+cl+text[b+len(marker):]

    return text.replace("\n","<br>")


def choose_avatar():
    global avatar_path
    path=choose_image("Select Webhook Avatar")

    if path:
        avatar_path=path
        avatar_input.setText(path)
        set_status("Avatar selected","#57f287")


def update_avatar(url,path):
    data=image_data_url(path)

    if not data:
        return False,"Unsupported or unreadable image."

    try:
        r=requests.patch(url,json={"avatar":data},timeout=15)
        return (True,None) if r.ok else (False,f"Discord returned HTTP {r.status_code}.")
    except requests.RequestException as e:
        return False,str(e)


class EmbedField(QWidget):
    changed=Signal()
    remove_requested=Signal()

    def __init__(self):
        super().__init__()

        l=QGridLayout(self)
        l.setContentsMargins(0,5,0,5)
        l.setHorizontalSpacing(8)

        self.name_input=QLineEdit()
        self.name_input.setPlaceholderText("Field name")

        self.value_input=QLineEdit()
        self.value_input.setPlaceholderText("Field value")

        self.inline=QCheckBox("Inline")

        remove=QPushButton("Remove")
        remove.setStyleSheet(button_style("#35373c"))

        tooltip(self.name_input,"Maximum 256 characters.")
        tooltip(self.value_input,"Maximum 1024 characters.")

        l.addWidget(self.name_input,0,0)
        l.addWidget(self.value_input,0,1)
        l.addWidget(self.inline,0,2)
        l.addWidget(remove,0,3)

        self.name_input.textChanged.connect(self.changed.emit)
        self.value_input.textChanged.connect(self.changed.emit)
        self.inline.stateChanged.connect(self.changed.emit)
        remove.clicked.connect(self.remove_requested.emit)

    def data(self):
        n=self.name_input.text().strip()
        v=self.value_input.text().strip()

        return {
            "name":n[:MAX_FIELD_NAME],
            "value":v[:MAX_FIELD_VALUE],
            "inline":self.inline.isChecked()
        } if n and v else None


def add_field():
    count=sum(
        isinstance(fields_layout.itemAt(i).widget(),EmbedField)
        for i in range(fields_layout.count())
    )

    if count>=MAX_FIELDS:
        QMessageBox.warning(window,"Field Limit","Discord allows a maximum of 25 fields.")
        return

    f=EmbedField()
    f.changed.connect(update_preview)
    f.remove_requested.connect(lambda:remove_field(f))
    fields_layout.insertWidget(fields_layout.count()-1,f)
    update_preview()


def remove_field(field):
    field.deleteLater()
    update_preview()


def get_fields():
    result=[]

    for i in range(fields_layout.count()):
        w=fields_layout.itemAt(i).widget()

        if isinstance(w,EmbedField):
            d=w.data()
            if d:
                result.append(d)

    return result[:MAX_FIELDS]


def choose_color():
    global embed_color

    c=QColorDialog.getColor(QColor(embed_color),window,"Choose Embed Colour")

    if c.isValid():
        embed_color=c.name()
        color_button.setStyleSheet(button_style(embed_color))
        update_preview()


def get_timestamp():
    if not timestamp_enabled.isChecked():
        return None

    return timestamp_input.dateTime().toUTC().toString("yyyy-MM-ddTHH:mm:ssZ")


def build_embed(image_url=None,thumbnail_url=None):
    if not embed_enabled.isChecked():
        return None

    e={}

    title=embed_title.text().strip()[:MAX_TITLE]
    desc=embed_description.toPlainText().strip()[:MAX_DESCRIPTION]
    url=embed_url.text().strip()

    author=embed_author.text().strip()[:MAX_AUTHOR]
    author_url=embed_author_url.text().strip()
    author_icon=embed_author_icon.text().strip()

    footer=embed_footer.text().strip()[:MAX_FOOTER]
    footer_icon=embed_footer_icon.text().strip()

    if title:
        e["title"]=title

    if desc:
        e["description"]=desc

    if url and valid_url(url):
        e["url"]=url

    e["color"]=int(embed_color.lstrip("#"),16)

    if t:=get_timestamp():
        e["timestamp"]=t

    if author:
        e["author"]={"name":author}

        if valid_url(author_url):
            e["author"]["url"]=author_url

        if valid_url(author_icon):
            e["author"]["icon_url"]=author_icon

    if footer:
        e["footer"]={"text":footer}

        if valid_url(footer_icon):
            e["footer"]["icon_url"]=footer_icon

    if fields:=get_fields():
        e["fields"]=fields

    if image_url and valid_url(image_url):
        e["image"]={"url":image_url}

    if thumbnail_url and valid_url(thumbnail_url):
        e["thumbnail"]={"url":thumbnail_url}

    return e


def embed_size(embed):
    return len(embed.get("title",""))+len(embed.get("description",""))+sum(
        len(f["name"])+len(f["value"]) for f in embed.get("fields",[])
    )+len(embed.get("footer",{}).get("text",""))+len(embed.get("author",{}).get("name",""))


class WebhookWorker(QObject):
    finished=Signal(object)

    def __init__(self,url,path,payload):
        super().__init__()
        self.url=url
        self.path=path
        self.payload=payload

    def run(self):
        if self.path:
            ok,error=update_avatar(self.url,self.path)
            if not ok:
                self.finished.emit({"kind":"avatar","error":error})
                return
        try:
            response=requests.post(self.url,json=self.payload,timeout=20)
            self.finished.emit({"kind":"response","response":response})
        except requests.RequestException as error:
            self.finished.emit({"kind":"connection","error":error})


class PreviewWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("DisHook Preview")
        self.resize(650,700)
        self.setMinimumSize(500,500)

        l=QVBoxLayout(self)
        l.setContentsMargins(20,20,20,20)
        l.setSpacing(14)

        title=QLabel("Live Preview")
        title.setStyleSheet("font-size:20px;font-weight:800;")

        self.preview=QLabel()
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.RichText)
        self.preview.setAlignment(Qt.AlignTop)
        self.preview.setStyleSheet("""
            QLabel {
                background:#313338;
                color:#dbdee1;
                border:1px solid #3f4147;
                border-radius:12px;
                padding:20px;
            }
        """)

        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container=QWidget()
        cl=QVBoxLayout(container)
        cl.setContentsMargins(0,0,0,0)
        cl.addWidget(self.preview)
        cl.addStretch()

        scroll.setWidget(container)

        l.addWidget(title)
        l.addWidget(scroll,1)

    def set_preview(self,content):
        self.preview.setText(content)


def open_preview():
    global preview_window

    if preview_window is None:
        preview_window=PreviewWindow()

    update_preview()
    preview_window.show()
    preview_window.raise_()
    preview_window.activateWindow()


def preview_media(url,label):
    return (
        f"<div style='margin-top:12px;color:#949ba4;'>"
        f"{label}: {html.escape(url)}</div>"
        if url else ""
    )


def update_preview():
    if preview_window is None:
        return

    username=username_input.text().strip() or "Webhook"
    message=message_input.toPlainText().strip()

    image_url=embed_image_input.text().strip()
    thumbnail_url=embed_thumbnail_input.text().strip()

    e=build_embed(
        image_url if valid_url(image_url) else None,
        thumbnail_url if valid_url(thumbnail_url) else None
    )

    p=f"""
    <div style='font-family:Arial;color:#dbdee1;font-size:14px;'>
        <div style='font-size:15px;'>
            <b>{html.escape(username)}</b>
            <span style='color:#949ba4;font-size:11px;'>&nbsp; just now</span>
        </div>
        <div style='margin-top:8px;line-height:1.5;'>
            {markdown_to_html(message) if message else "<span style='color:#949ba4'>No message</span>"}
        </div>
    """

    if e:
        p+=f"""
        <div style='
            margin-top:16px;
            background:#2b2d31;
            border-left:5px solid {embed_color};
            border-radius:6px;
            padding:16px;
        '>
        """

        if a:=e.get("author"):
            p+=f"<div style='margin-bottom:8px;font-weight:600;'>{html.escape(a['name'])}</div>"

        if e.get("title"):
            p+=f"""
            <div style='font-size:17px;font-weight:700;margin-bottom:7px;color:#fff;'>
                {html.escape(e["title"])}
            </div>
            """

        if e.get("description"):
            p+=f"<div style='line-height:1.5;'>{markdown_to_html(e['description'])}</div>"

        if fields:=e.get("fields"):
            p+="<div style='margin-top:12px;'>"

            for f in fields:
                p+=f"""
                <div style='margin-top:9px;'>
                    <b>{html.escape(f["name"])}</b><br>
                    {markdown_to_html(f["value"])}
                </div>
                """

            p+="</div>"

        p+=preview_media(image_url,"Image URL")
        p+=preview_media(thumbnail_url,"Thumbnail URL")

        if e.get("timestamp"):
            p+="<div style='margin-top:10px;color:#949ba4;font-size:11px;'>Timestamp enabled</div>"

        if footer:=e.get("footer"):
            p+=f"""
            <div style='margin-top:12px;color:#949ba4;font-size:11px;'>
                {html.escape(footer["text"])}
            </div>
            """

        p+="</div>"

    preview_window.set_preview(p+"</div>")


def send_webhook():
    url=webhook_input.text().strip()
    username=username_input.text().strip()
    message=message_input.toPlainText().strip()

    if not url:
        set_status("Missing webhook","#faa61a")
        QMessageBox.warning(window,"Missing Webhook","Please enter a Discord webhook URL.")
        return

    if not valid_webhook(url):
        set_status("Invalid webhook","#ed4245")
        QMessageBox.warning(window,"Invalid Webhook","Please enter a valid Discord webhook URL.")
        return

    if len(message)>MAX_CONTENT:
        QMessageBox.warning(window,"Message Too Long","Discord messages can contain up to 2000 characters.")
        return

    image_url=embed_image_input.text().strip()
    thumbnail_url=embed_thumbnail_input.text().strip()

    if image_url and not valid_url(image_url):
        QMessageBox.warning(window,"Invalid Image URL","The embed image must be a valid HTTP or HTTPS URL.")
        return

    if thumbnail_url and not valid_url(thumbnail_url):
        QMessageBox.warning(window,"Invalid Thumbnail URL","The thumbnail must be a valid HTTP or HTTPS URL.")
        return

    e=build_embed(image_url or None,thumbnail_url or None)

    if not message and not e:
        set_status("Nothing to send","#faa61a")
        QMessageBox.warning(window,"Nothing to Send","Enter a message or enable an embed.")
        return

    if e and embed_size(e)>MAX_EMBED_CONTENT:
        set_status("Embed too large","#ed4245")
        QMessageBox.warning(window,"Embed Too Large","Discord embeds can contain up to 6000 characters.")
        return

    payload={"allowed_mentions":{"parse":[]}}

    if message:
        payload["content"]=message

    if username:
        payload["username"]=username

    if e:
        payload["embeds"]=[e]

    send_button.setEnabled(False)
    set_status("Sending webhook...","#faa61a")
    thread=QThread()
    worker=WebhookWorker(url,avatar_path,payload)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(webhook_finished)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.finished.connect(lambda:setattr(window,"_webhook_thread",None))
    window._webhook_thread=thread
    thread.start()


def webhook_finished(result):
    send_button.setEnabled(True)

    if result["kind"]=="avatar":
        set_status("Avatar update failed","#ed4245")
        QMessageBox.critical(window,"Avatar Error",result["error"])
        return

    if result["kind"]=="connection":
        set_status("Connection error","#ed4245")
        QMessageBox.critical(window,"Connection Error",f"Could not contact Discord:\n{result['error']}")
        return

    r=result["response"]
    if r.status_code in (200,204):
        set_status("Sent successfully","#57f287")
        QMessageBox.information(window,"Success","Webhook sent successfully!")
        return

    if r.status_code==429:
        try:
            retry=float(r.json().get("retry_after",1))
        except (ValueError,TypeError):
            try:
                retry=float(r.headers.get("Retry-After",1))
            except (ValueError,TypeError):
                retry=1
        set_status(f"Rate limited — retry after {retry:.1f}s","#faa61a")
        QMessageBox.warning(window,"Rate Limited",f"Discord rate-limited this webhook.\n\nRetry after approximately {retry:.1f} seconds.")
        return

    try:
        error_text=json.dumps(r.json(),indent=2)
    except ValueError:
        error_text=r.text
    set_status(f"Failed ({r.status_code})","#ed4245")
    QMessageBox.critical(window,"Discord Error",f"Discord returned HTTP {r.status_code}.\n\n{error_text}")


def clear_fields():
    global avatar_path,embed_color

    for w in (
        webhook_input,username_input,avatar_input,embed_title,embed_url,
        embed_author,embed_author_url,embed_author_icon,embed_footer,
        embed_footer_icon,embed_image_input,embed_thumbnail_input
    ):
        w.clear()

    message_input.clear()
    embed_description.clear()
    embed_enabled.setChecked(False)
    timestamp_enabled.setChecked(False)

    while fields_layout.count()>1:
        item=fields_layout.takeAt(0)

        if item.widget():
            item.widget().deleteLater()

    avatar_path=""
    embed_color=DEFAULT_COLOR
    color_button.setStyleSheet(button_style())

    set_status("Ready")
    update_preview()


def set_embed_enabled(enabled):
    for w in embed_controls:
        w.setEnabled(enabled)

    update_preview()


def enter_app():
    welcome.raise_()
    builder.raise_()

    start=builder.geometry()
    end=start

    builder.setGeometry(
        start.x()+45,
        start.y(),
        start.width(),
        start.height()
    )

    anim=QPropertyAnimation(builder,b"geometry")
    anim.setDuration(280)
    anim.setStartValue(builder.geometry())
    anim.setEndValue(end)

    welcome_anim=QPropertyAnimation(welcome,b"windowOpacity")
    welcome_anim.setDuration(180)
    welcome_anim.setStartValue(1)
    welcome_anim.setEndValue(0)

    group=QParallelAnimationGroup()
    group.addAnimation(anim)
    group.addAnimation(welcome_anim)

    def finish():
        welcome.hide()
        builder.show()
        builder.setGeometry(end)
        window.setWindowTitle("DisHook")
        window._intro_anim=None

    group.finished.connect(finish)
    window._intro_anim=group
    group.start()


app=QApplication(sys.argv)

app.setStyleSheet("""
QWidget {
    font-family:"Inter","Segoe UI",sans-serif;
    font-size:13px;
    color:#f2f3f5;
}

QWidget#mainWindow,QWidget#builder,QWidget#welcome {
    background:#111214;
}

QGroupBox {
    background:#18191c;
    font-weight:700;
    border:1px solid #292b2f;
    border-radius:12px;
    margin-top:12px;
    padding:14px;
    padding-top:21px;
}

QGroupBox::title {
    subcontrol-origin:margin;
    left:14px;
    padding:0 7px;
    color:#f2f3f5;
}

QLineEdit,QTextEdit,QDateTimeEdit {
    background:#111214;
    color:#f2f3f5;
    padding:9px 10px;
    border:1px solid #303236;
    border-radius:8px;
    selection-background-color:#5865F2;
}

QLineEdit:hover,QTextEdit:hover,QDateTimeEdit:hover {
    border:1px solid #45474d;
}

QLineEdit:focus,QTextEdit:focus,QDateTimeEdit:focus {
    border:1px solid #5865F2;
    background:#151619;
}

QLineEdit:disabled,QTextEdit:disabled,QDateTimeEdit:disabled {
    background:#101113;
    color:#44464b;
    border:1px solid #25272b;
}

QPushButton {
    background:#5865F2;
    color:white;
    padding:9px 13px;
    border:1px solid rgba(255,255,255,.06);
    border-radius:9px;
    font-weight:600;
}

QPushButton:hover {
    background:#6d78ff;
}

QPushButton:pressed {
    background:#4752c4;
}

QPushButton:disabled {
    background:#292b30;
    color:#555;
}

QCheckBox {
    spacing:8px;
    color:#dbdee1;
}

QCheckBox:hover {
    color:white;
}

QScrollArea {
    border:none;
    background:transparent;
}

QScrollBar:vertical {
    background:#111214;
    width:9px;
    margin:2px;
}

QScrollBar::handle:vertical {
    background:#383a40;
    min-height:30px;
    border-radius:4px;
}

QScrollBar::handle:vertical:hover {
    background:#4b4d54;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height:0;
}

QSplitter::handle {
    background:#111214;
}

QSplitter::handle:hover {
    background:#5865F2;
}

QToolTip {
    background:#18191c;
    color:#f2f3f5;
    border:1px solid #5865F2;
    padding:7px 9px;
    border-radius:6px;
}

QMessageBox {
    background:#18191c;
}

QDateTimeEdit::drop-down {
    border:none;
    width:24px;
}
""")

QToolTip.setFont(app.font())

window=QWidget()
window.setObjectName("mainWindow")
window.setWindowTitle("DisHook")
window.resize(1050,740)
window.setMinimumSize(820,620)

# ───────────────────────── Welcome ─────────────────────────

welcome=QWidget(window)
welcome.setObjectName("welcome")
welcome.setGeometry(0,0,1050,740)

welcome_layout=QVBoxLayout(welcome)
welcome_layout.setContentsMargins(30,30,30,30)

welcome_layout.addStretch(2)

logo=QLabel("DisHook")
logo.setAlignment(Qt.AlignCenter)
logo.setStyleSheet("""
    QLabel {
        font-size:58px;
        font-weight:900;
        color:#ffffff;
        letter-spacing:1px;
    }
""")

tagline=QLabel("A simple Discord webhook builder")
tagline.setAlignment(Qt.AlignCenter)
tagline.setStyleSheet("""
    QLabel {
        color:#949ba4;
        font-size:15px;
    }
""")

welcome_layout.addWidget(logo)
welcome_layout.addWidget(tagline)
welcome_layout.addSpacing(28)

enter_button=QPushButton("Enter")
enter_button.setFixedSize(180,48)
enter_button.setStyleSheet("""
    QPushButton {
        background:#5865F2;
        color:white;
        border:none;
        border-radius:10px;
        font-size:14px;
        font-weight:700;
    }
    QPushButton:hover {background:#6d78ff;}
    QPushButton:pressed {background:#4752c4;}
""")

button_row=QHBoxLayout()
button_row.addStretch()
button_row.addWidget(enter_button)
button_row.addStretch()

welcome_layout.addLayout(button_row)
welcome_layout.addSpacing(30)

credit=QLabel()
credit.setAlignment(Qt.AlignCenter)
credit.setText(
    '<span style="color:#949ba4;">Made by </span>'
    '<a href="https://github.com/4Y44N-KH4L3D" '
    'style="color:#7289da;text-decoration:none;">4Y44N-KH4L3D</a>'
)
credit.setOpenExternalLinks(True)
credit.setCursor(Qt.PointingHandCursor)
credit.setStyleSheet("font-size:12px;")

welcome_layout.addWidget(credit)
welcome_layout.addStretch(3)

# ───────────────────────── Builder ─────────────────────────

builder=QWidget(window)
builder.setObjectName("builder")
builder.setGeometry(0,0,1050,740)
builder.hide()

main=QVBoxLayout(builder)
main.setContentsMargins(16,16,16,14)
main.setSpacing(14)

header=QHBoxLayout()

title=QLabel("DisHook")
title.setStyleSheet("""
    QLabel {
        font-size:24px;
        font-weight:900;
        color:#f2f3f5;
    }
""")

subtitle=QLabel("Discord Webhook Builder")
subtitle.setStyleSheet("color:#949ba4;font-size:12px;")

header_text=QVBoxLayout()
header_text.setSpacing(2)
header_text.addWidget(title)
header_text.addWidget(subtitle)

header.addLayout(header_text)
header.addStretch()
main.addLayout(header)

appearance=QGroupBox("Appearance")
al=QGridLayout()
al.setHorizontalSpacing(12)
al.setVerticalSpacing(10)

username_input=QLineEdit()
username_input.setPlaceholderText("Optional — override webhook username")

avatar_input=QLineEdit()
avatar_input.setReadOnly(True)
avatar_input.setPlaceholderText("Optional — choose an image")

avatar_button=QPushButton("Choose Image")
avatar_button.setStyleSheet(button_style("#35373c"))
avatar_button.clicked.connect(choose_avatar)

al.addWidget(QLabel("Username"),0,0)
al.addWidget(username_input,0,1,1,2)
al.addWidget(QLabel("Avatar"),1,0)
al.addWidget(avatar_input,1,1)
al.addWidget(avatar_button,1,2)

appearance.setLayout(al)
main.addWidget(appearance)

webhook=QGroupBox("Webhook")
wl=QVBoxLayout()
wl.setSpacing(10)

webhook_input=QLineEdit()
webhook_input.setPlaceholderText("https://discord.com/api/webhooks/...")

message_input=QTextEdit()
message_input.setPlaceholderText("Write your Discord message...")
message_input.setMinimumHeight(180)

format_layout=QHBoxLayout()
format_layout.setSpacing(6)

for label,start,end in (
    ("Bold","**","**"),
    ("Italic","*","*"),
    ("Underline","__","__"),
    ("Strikethrough","~~","~~"),
    ("Code","`","`"),
    ("Spoiler","||","||")
):
    b=QPushButton(label)
    b.setStyleSheet(button_style("#35373c"))
    b.clicked.connect(lambda _,s=start,e=end:insert_format(s,e))
    format_layout.addWidget(b)

format_layout.addStretch()

wl.addWidget(QLabel("Webhook URL"))
wl.addWidget(webhook_input)
wl.addWidget(QLabel("Message"))
wl.addLayout(format_layout)
wl.addWidget(message_input,1)

webhook.setLayout(wl)

embed=QGroupBox("Embed")
el=QVBoxLayout()
el.setSpacing(12)

embed_enabled=QCheckBox("Enable Embed")
embed_enabled.setStyleSheet("QCheckBox{font-weight:700;}")
el.addWidget(embed_enabled)

basic_group=QGroupBox("Basic")
bl=QVBoxLayout()
bl.setSpacing(9)

embed_title=QLineEdit()
embed_title.setPlaceholderText("Title — max 256 characters")

embed_description=QTextEdit()
embed_description.setPlaceholderText("Description — max 4096 characters")
embed_description.setMaximumHeight(105)

embed_url=QLineEdit()
embed_url.setPlaceholderText("Title URL — optional")

color_button=QPushButton("Choose Colour")
color_button.clicked.connect(choose_color)

cr=QHBoxLayout()
cr.addWidget(QLabel("Colour"))
cr.addWidget(color_button)
cr.addStretch()

bl.addWidget(embed_title)
bl.addWidget(embed_description)
bl.addWidget(embed_url)
bl.addLayout(cr)

basic_group.setLayout(bl)
el.addWidget(basic_group)

author_group=QGroupBox("Author")
ar=QVBoxLayout()
ar.setSpacing(9)

embed_author=QLineEdit()
embed_author.setPlaceholderText("Author name — max 256 characters")

embed_author_url=QLineEdit()
embed_author_url.setPlaceholderText("Author URL — optional")

embed_author_icon=QLineEdit()
embed_author_icon.setPlaceholderText("Author icon URL — optional")

for w in (embed_author,embed_author_url,embed_author_icon):
    ar.addWidget(w)

author_group.setLayout(ar)
el.addWidget(author_group)

media_group=QGroupBox("Media")
mr=QVBoxLayout()
mr.setSpacing(9)

embed_image_input=QLineEdit()
embed_image_input.setPlaceholderText("Image URL — optional")

embed_thumbnail_input=QLineEdit()
embed_thumbnail_input.setPlaceholderText("Thumbnail URL — optional")

tooltip(embed_image_input,"Enter a direct HTTP/HTTPS image URL.")
tooltip(embed_thumbnail_input,"Enter a direct HTTP/HTTPS image URL.")

mr.addWidget(embed_image_input)
mr.addWidget(embed_thumbnail_input)

media_group.setLayout(mr)
el.addWidget(media_group)

footer_group=QGroupBox("Footer")
fr=QVBoxLayout()
fr.setSpacing(9)

embed_footer=QLineEdit()
embed_footer.setPlaceholderText("Footer text — max 2048 characters")

embed_footer_icon=QLineEdit()
embed_footer_icon.setPlaceholderText("Footer icon URL — optional")

fr.addWidget(embed_footer)
fr.addWidget(embed_footer_icon)

footer_group.setLayout(fr)
el.addWidget(footer_group)

timestamp_group=QGroupBox("Timestamp")
tr=QHBoxLayout()

timestamp_enabled=QCheckBox("Enable Timestamp")

timestamp_input=QDateTimeEdit()
timestamp_input.setCalendarPopup(True)
timestamp_input.setEnabled(False)

timestamp_enabled.toggled.connect(timestamp_input.setEnabled)
timestamp_enabled.toggled.connect(update_preview)
timestamp_input.dateTimeChanged.connect(update_preview)

tr.addWidget(timestamp_enabled)
tr.addWidget(timestamp_input)
tr.addStretch()

timestamp_group.setLayout(tr)
el.addWidget(timestamp_group)

fields_group=QGroupBox("Fields")
fgl=QVBoxLayout()
fgl.setSpacing(9)

fields_scroll=QScrollArea()
fields_scroll.setWidgetResizable(True)
fields_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

fields_container=QWidget()
fields_layout=QVBoxLayout(fields_container)
fields_layout.setContentsMargins(0,0,0,0)
fields_layout.setSpacing(6)
fields_layout.addStretch()

fields_scroll.setWidget(fields_container)

add_field_button=QPushButton("+ Add Field")
add_field_button.setStyleSheet(button_style("#35373c"))
add_field_button.clicked.connect(add_field)

fgl.addWidget(fields_scroll,1)
fgl.addWidget(add_field_button)

fields_group.setLayout(fgl)
el.addWidget(fields_group,1)

preview_button=QPushButton("Live Preview")
preview_button.setStyleSheet(button_style("#35373c"))
preview_button.clicked.connect(open_preview)
el.addWidget(preview_button)

embed_content=QWidget()
embed_content.setLayout(el)

embed_scroll=QScrollArea()
embed_scroll.setWidgetResizable(True)
embed_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
embed_scroll.setWidget(embed_content)

embed_layout=QVBoxLayout(embed)
embed_layout.setContentsMargins(0,0,0,0)
embed_layout.addWidget(embed_scroll)

content_layout=QHBoxLayout()
content_layout.setSpacing(14)
content_layout.addWidget(webhook,1)
content_layout.addWidget(embed,1)

main.addLayout(content_layout,1)

controls=QHBoxLayout()
controls.setSpacing(9)

send_button=QPushButton("Send Webhook")
send_button.setMinimumHeight(44)
send_button.clicked.connect(send_webhook)

clear_button=QPushButton("Clear")
clear_button.setMinimumHeight(44)
clear_button.setStyleSheet(button_style("#35373c"))
clear_button.clicked.connect(clear_fields)

controls.addWidget(send_button,2)
controls.addWidget(clear_button,1)

main.addLayout(controls)

status_label=QLabel("●  Ready")
status_label.setStyleSheet("color:#949ba4;font-weight:600;")
main.addWidget(status_label)

embed_controls=[
    basic_group,
    author_group,
    media_group,
    footer_group,
    timestamp_group,
    fields_group,
    preview_button
]

for w in (
    username_input,
    embed_title,
    embed_url,
    embed_author,
    embed_author_url,
    embed_author_icon,
    embed_footer,
    embed_footer_icon,
    embed_image_input,
    embed_thumbnail_input
):
    w.textChanged.connect(update_preview)

message_input.textChanged.connect(update_preview)
embed_description.textChanged.connect(update_preview)
embed_enabled.toggled.connect(set_embed_enabled)

set_embed_enabled(False)

enter_button.clicked.connect(enter_app)

window.show()
sys.exit(app.exec())