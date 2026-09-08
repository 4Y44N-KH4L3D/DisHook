import sys,json,base64,mimetypes,html,os
from urllib.parse import urlparse
import requests

from PySide6.QtCore import Qt,Signal,Slot,QPropertyAnimation,QParallelAnimationGroup,QThread,QObject,QEvent,QTimer
from PySide6.QtGui import QColor,QIcon
from PySide6.QtWidgets import (
    QApplication,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,
    QLineEdit,QTextEdit,QPushButton,QMessageBox,QFileDialog,QGroupBox,
    QScrollArea,QCheckBox,QColorDialog,QDateTimeEdit,QToolTip
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


def resource_path(relative_path):
    base_path=getattr(sys,"_MEIPASS",os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base_path,relative_path)


APP_ICON=resource_path("assets/Icon.png")


class DelayedTooltip(QObject):
    def __init__(self,widget,text):
        super().__init__(widget)
        self.widget=widget
        self.text=text
        self.timer=QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.show)

    def eventFilter(self,obj,event):
        if obj is self.widget:
            if event.type()==QEvent.Enter:
                self.timer.start()
            elif event.type()==QEvent.Leave:
                self.timer.stop()
                QToolTip.hideText()
        return super().eventFilter(obj,event)

    def show(self):
        if self.widget.underMouse():
            QToolTip.showText(
                self.widget.mapToGlobal(self.widget.rect().bottomLeft()),
                self.text,self.widget
            )


def tooltip(w,text):
    w.setToolTip("")
    w.setToolTipDuration(10000)
    w._tooltip_filter=DelayedTooltip(w,text)
    w.installEventFilter(w._tooltip_filter)


def button_style(color=DEFAULT_COLOR):
    return f"""
    QPushButton {{
        background:{color};
        color:white;
        border:1px solid rgba(255,255,255,.08);
        border-radius:8px;
        padding:10px 15px;
        font-weight:600;
    }}
    QPushButton:hover {{background:#6875ff;}}
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
        tooltip(self.inline,"Display this field beside other inline fields.")
        tooltip(remove,"Remove this embed field.")

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

    if not any(key in e for key in (
        "title","description","author","fields","footer","image","thumbnail"
    )):
        return None

    e["color"]=int(embed_color.lstrip("#"),16)
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
        try:
            if self.path:
                ok,error=update_avatar(self.url,self.path)
                if not ok:
                    self.finished.emit({"kind":"avatar","error":error})
                    return
            response=requests.post(self.url,json=self.payload,timeout=20)
            self.finished.emit({"kind":"response","response":response})
        except (requests.RequestException,OSError,ValueError) as error:
            self.finished.emit({"kind":"connection","error":error})


class WebhookReceiver(QObject):
    @Slot(object)
    def handle(self,result):
        try:
            webhook_finished(result)
        finally:
            thread=getattr(window,"_webhook_thread",None)
            if thread is not None:
                thread.quit()


class MainWindow(QWidget):
    def resizeEvent(self,event):
        super().resizeEvent(event)

        for name in ("welcome","builder"):
            child=getattr(self,name,None)
            if child is not None:
                child.setGeometry(self.rect())

    def closeEvent(self,event):
        thread=getattr(self,"_webhook_thread",None)

        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait()

        event.accept()


class PreviewWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("DisHook Preview")
        self.setWindowIcon(QIcon(APP_ICON))
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
    worker.finished.connect(webhook_receiver.handle, Qt.QueuedConnection)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.finished.connect(lambda:setattr(window,"_webhook_thread",None))
    thread.finished.connect(lambda:setattr(window,"_webhook_worker",None))
    window._webhook_thread=thread
    window._webhook_worker=worker
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


def return_to_start():
    if preview_window is not None:
        preview_window.hide()
    builder.hide()
    welcome.setWindowOpacity(1)
    welcome.show()
    welcome.raise_()
    window.setWindowTitle("DisHook")


app=QApplication(sys.argv)
app.setWindowIcon(QIcon(APP_ICON))
webhook_receiver=WebhookReceiver()

app.setStyleSheet("""
QWidget {
    font-family:"Inter","Segoe UI",sans-serif;
    font-size:13px;
    color:#e8eaed;
}

QWidget#mainWindow,QWidget#builder,QWidget#welcome {
    background:#0f1115;
}

QGroupBox {
    background:#171a21;
    font-weight:700;
    border:1px solid #272c36;
    border-radius:10px;
    margin-top:11px;
    padding:13px;
    padding-top:20px;
}

QGroupBox::title {
    subcontrol-origin:margin;
    left:14px;
    padding:0 7px;
    color:#f1f3f5;
}

QLineEdit,QTextEdit,QDateTimeEdit {
    background:#0d1015;
    color:#f1f3f5;
    padding:10px 11px;
    border:1px solid #2a303b;
    border-radius:7px;
    selection-background-color:#5865F2;
}

QLineEdit:hover,QTextEdit:hover,QDateTimeEdit:hover {
    border:1px solid #414a5a;
}

QLineEdit:focus,QTextEdit:focus,QDateTimeEdit:focus {
    border:1px solid #5865F2;
    background:#11151c;
}

QLineEdit:disabled,QTextEdit:disabled,QDateTimeEdit:disabled {
    background:#101113;
    color:#44464b;
    border:1px solid #25272b;
}

QPushButton {
    background:#5865F2;
    color:white;
    padding:10px 15px;
    border:1px solid rgba(255,255,255,.08);
    border-radius:8px;
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
    background:#0f1115;
    width:8px;
    margin:2px;
}

QScrollBar::handle:vertical {
    background:#343b49;
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
    background:#171a21;
    color:#f2f3f5;
    border:1px solid #5865F2;
    padding:7px 9px;
    border-radius:5px;
}

QMessageBox {
    background:#171a21;
}

QDateTimeEdit::drop-down {
    border:none;
    width:24px;
}
""")

QToolTip.setFont(app.font())

window=MainWindow()
window.setObjectName("mainWindow")
window.setWindowTitle("DisHook")
window.setWindowIcon(QIcon(APP_ICON))
window.resize(1050,740)
window.setMinimumSize(820,620)

welcome=QWidget(window)
welcome.setObjectName("welcome")
welcome.setGeometry(window.rect())
window.welcome=welcome

welcome_layout=QVBoxLayout(welcome)
welcome_layout.setContentsMargins(40,40,40,40)

welcome_layout.addStretch(2)

logo=QLabel("DisHook")
logo.setObjectName("startLogo")
logo.setAlignment(Qt.AlignCenter)
logo.setStyleSheet("""
    QLabel {
        font-size:60px;
        font-weight:900;
        color:#ffffff;
        letter-spacing:2px;
    }
    QLabel:hover {color:#8b96ff;letter-spacing:4px;}
""")

welcome_layout.addWidget(logo)
welcome_layout.addSpacing(48)

enter_button=QPushButton("Enter")
enter_button.setFixedSize(180,48)
tooltip(enter_button,"Open the webhook builder.")
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
welcome_layout.addStretch(5)

credit=QLabel()
credit.setAlignment(Qt.AlignRight)
credit.setText(
    '<span style="color:#949ba4;">Made by </span>'
    '<a href="https://github.com/4Y44N-KH4L3D" '
    'style="color:#7289da;text-decoration:none;">4Y44N-KH4L3D</a>'
)
credit.setOpenExternalLinks(True)
credit.setCursor(Qt.PointingHandCursor)
credit.setStyleSheet("font-size:12px;")

welcome_layout.addWidget(credit,0,Qt.AlignRight|Qt.AlignBottom)

builder=QWidget(window)
builder.setObjectName("builder")
builder.setGeometry(window.rect())
builder.hide()
window.builder=builder

main=QVBoxLayout(builder)
main.setContentsMargins(20,18,20,16)
main.setSpacing(16)

header=QHBoxLayout()

title=QLabel("DisHook")
title.setAlignment(Qt.AlignCenter)
title.setStyleSheet("""
    QLabel {
        font-size:28px;
        font-weight:900;
        color:#f2f3f5;
    }
""")

header_text=QVBoxLayout()
header_text.addWidget(title)

back_button=QPushButton("← Back")
back_button.setStyleSheet(button_style("#35373c"))
tooltip(back_button,"Return to the start screen.")
back_button.clicked.connect(return_to_start)

header.addWidget(back_button)
header.addStretch()
header.addLayout(header_text)
header.addStretch()

main.addLayout(header)

appearance=QGroupBox("Appearance")
al=QGridLayout()
al.setHorizontalSpacing(12)
al.setVerticalSpacing(10)

username_input=QLineEdit()
username_input.setPlaceholderText("Optional — override webhook username")
username_input.setMaxLength(80)

avatar_input=QLineEdit()
avatar_input.setReadOnly(True)
avatar_input.setPlaceholderText("Optional — choose an image")

avatar_button=QPushButton("Choose Image")
avatar_button.setStyleSheet(button_style("#35373c"))
tooltip(avatar_button,"Choose an image to use as the webhook avatar.")
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
webhook_input.setEchoMode(QLineEdit.Password)
webhook_input.setToolTip("Your webhook URL is hidden for safety.")
tooltip(webhook_input,"Enter the Discord webhook URL that will receive the message.")

message_input=QTextEdit()
message_input.setPlaceholderText("Write your Discord message...")
message_input.setMinimumHeight(180)
tooltip(message_input,"Enter the message to send. Discord allows up to 2,000 characters.")

format_layout=QHBoxLayout()
format_layout.setSpacing(3)

for label,start,end in (
    ("Bold","**","**"),
    ("Italic","*","*"),
    ("Underline","__","__"),
    ("Strikethrough","~~","~~"),
    ("Code","`","`"),
    ("Spoiler","||","||")
):
    b=QPushButton(label)
    b.setStyleSheet("""
        QPushButton {
            background:#35373c;
            color:white;
            padding:7px 8px;
            border:1px solid rgba(255,255,255,.08);
            border-radius:7px;
            font-size:12px;
            font-weight:600;
        }
        QPushButton:hover {background:#454951;}
        QPushButton:pressed {background:#292b30;}
    """)
    tooltip(b,f"Add {label.lower()} formatting to the selected message text.")
    b.clicked.connect(lambda _,s=start,e=end:insert_format(s,e))
    format_layout.addWidget(b)

format_layout.addStretch()

wl.addWidget(QLabel("Webhook URL"))
wl.addWidget(webhook_input)
wl.addWidget(QLabel("Message"))
wl.addLayout(format_layout)
wl.addWidget(message_input,1)

webhook_content=QWidget()
webhook_content.setLayout(wl)

webhook_scroll=QScrollArea()
webhook_scroll.setWidgetResizable(True)
webhook_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
webhook_scroll.setStyleSheet("QScrollArea{background:#171a21;border:none;}")
webhook_scroll.viewport().setStyleSheet("background:#171a21;")
webhook_content.setStyleSheet("background:#171a21;")
webhook_scroll.setWidget(webhook_content)

webhook_layout=QVBoxLayout(webhook)
webhook_layout.setContentsMargins(0,0,0,0)
webhook_layout.addWidget(webhook_scroll)

embed=QGroupBox("Embed")
el=QVBoxLayout()
el.setSpacing(12)

embed_enabled=QCheckBox("Enable Embed")
embed_enabled.setStyleSheet("QCheckBox{font-weight:700;}")
tooltip(embed_enabled,"Enable or disable the embed customization options.")
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
tooltip(color_button,"Choose the color shown on the left side of the embed.")
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
tooltip(add_field_button,"Add a name/value field to the embed.")
add_field_button.clicked.connect(add_field)

fgl.addWidget(fields_scroll,1)
fgl.addWidget(add_field_button)

fields_group.setLayout(fgl)
el.addWidget(fields_group,1)

preview_button=QPushButton("Live Preview")
preview_button.setStyleSheet(button_style("#35373c"))
tooltip(preview_button,"Open a live preview of the message and embed.")
preview_button.clicked.connect(open_preview)
el.addWidget(preview_button)

for widget,text in (
    (username_input,"Optional name displayed instead of the webhook's default name."),
    (avatar_input,"Selected image path for the webhook avatar."),
    (embed_title,"Optional embed title. Maximum 256 characters."),
    (embed_description,"Optional embed description. Maximum 4,096 characters."),
    (embed_url,"Optional URL opened when the embed title is clicked."),
    (embed_author,"Optional embed author name. Maximum 256 characters."),
    (embed_author_url,"Optional URL opened when the author is clicked."),
    (embed_author_icon,"Optional HTTP/HTTPS URL for the author icon."),
    (embed_image_input,"Optional HTTP/HTTPS URL for the main embed image."),
    (embed_thumbnail_input,"Optional HTTP/HTTPS URL for the embed thumbnail."),
    (embed_footer,"Optional embed footer text. Maximum 2,048 characters."),
    (embed_footer_icon,"Optional HTTP/HTTPS URL for the footer icon."),
    (timestamp_input,"Choose the timestamp displayed in the embed."),
    (timestamp_enabled,"Include the selected timestamp in the embed.")
):
    tooltip(widget,text)

embed_content=QWidget()
embed_content.setLayout(el)

embed_scroll=QScrollArea()
embed_scroll.setWidgetResizable(True)
embed_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
embed_scroll.setStyleSheet("QScrollArea{background:#171a21;border:none;}")
embed_scroll.viewport().setStyleSheet("background:#171a21;")
embed_content.setStyleSheet("background:#171a21;")
embed_scroll.setWidget(embed_content)

embed_layout=QVBoxLayout(embed)
embed_layout.setContentsMargins(0,0,0,0)
embed_layout.addWidget(embed_scroll)

content_layout=QHBoxLayout()
content_layout.setSpacing(16)
content_layout.addWidget(webhook,1)
content_layout.addWidget(embed,1)

main.addLayout(content_layout,1)

controls=QHBoxLayout()
controls.setSpacing(9)

send_button=QPushButton("Send Webhook")
send_button.setMinimumHeight(44)
tooltip(send_button,"Send the message and embed to the webhook URL.")
send_button.clicked.connect(send_webhook)

clear_button=QPushButton("Clear")
clear_button.setMinimumHeight(44)
clear_button.setStyleSheet(button_style("#35373c"))
tooltip(clear_button,"Clear all message, embed, avatar, and webhook fields.")
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