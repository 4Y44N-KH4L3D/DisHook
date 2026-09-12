import sys,json,html,os

from PySide6.QtCore import Qt,Signal,Slot,QPropertyAnimation,QParallelAnimationGroup,QThread,QObject,QEvent,QTimer,Property,QEasingCurve,QDateTime,QSignalBlocker,QRegularExpression
from PySide6.QtGui import QColor,QIcon,QPainter,QPixmap,QTransform,QFont,QPen,QSyntaxHighlighter,QTextCharFormat
from PySide6.QtWidgets import (
    QApplication,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,
    QLineEdit,QTextEdit,QPushButton,QMessageBox,QFileDialog,QGroupBox,
    QScrollArea,QScrollBar,QCheckBox,QColorDialog,QDateTimeEdit,QToolTip,
    QStyle,QStyleOptionButton,QFrame,QSizePolicy,QGraphicsDropShadowEffect
)

from discord_logic import (
    DEFAULT_COLOR,MAX_CONTENT,MAX_EMBED_CONTENT,MAX_FIELDS,MAX_FIELD_NAME,MAX_FIELD_VALUE,
    build_embed as build_embed_payload,build_payload,
    payload_errors,valid_url,valid_webhook,color_values,replace_placeholders,
    sanitize_payload,normalize_template,unwrap_payload
)
from network import broadcast_requests

avatar_path=""
embed_color=DEFAULT_COLOR
preview_window=None
webhook_urls_input=None
color_hex_label=None
color_decimal_label=None
json_editor=None
embed_body=None
json_status_label=None
json_length_label=None
json_embeds_label=None
json_group=None
json_focus_button=None
json_fullscreen=False


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


def add_missing_tooltips(root):
    for widget in root.findChildren(QWidget):
        if hasattr(widget,"_tooltip_filter"):
            continue
        text=""
        if isinstance(widget,QGroupBox):
            title=widget.title().replace("▸ ","").replace("▾ ","")
            text=f"{title} section. Expand or collapse it to show or hide its controls."
        elif isinstance(widget,QPushButton):
            text=f"{widget.text().strip()}. Select this button to perform this action."
        elif isinstance(widget,QLineEdit):
            text=widget.placeholderText() or "Enter a single-line value."
        elif isinstance(widget,QTextEdit):
            text=widget.placeholderText() or "Enter multi-line text. You can edit and paste content here."
        elif isinstance(widget,QCheckBox):
            text=f"{widget.text().strip() or 'Toggle this option.'} Turn this on to enable the related feature."
        elif isinstance(widget,QDateTimeEdit):
            text="Choose the date and time to use in the embed timestamp."
        elif isinstance(widget,QScrollArea):
            text="Scroll through the builder to access the Appearance, Webhook, Embed, Actions, and JSON sections."
        if text:
            tooltip(widget,text)


def button_style(color=DEFAULT_COLOR):
    return f"""
    QPushButton {{
        background:{color};
        color:white;
        border:1px solid #3f5f7d;
        border-radius:8px;
        padding:10px 15px;
        font-weight:600;
    }}
    QPushButton:hover {{background:#3f668b;}}
    QPushButton:pressed {{background:#203c58;}}
    QPushButton:disabled {{background:#252b34;color:#68717d;}}
    """


class AnimatedButton(QPushButton):
    def __init__(self,text="",parent=None):
        super().__init__(text,parent)
        self._hover_progress=0.0
        self._hover_animation=QPropertyAnimation(self,b"hoverProgress",self)
        self._hover_animation.setDuration(150)
        self._hover_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.setAttribute(Qt.WA_Hover,True)

    def get_hover_progress(self):
        return self._hover_progress

    def set_hover_progress(self,value):
        self._hover_progress=value
        self.update()

    hoverProgress=Property(float,get_hover_progress,set_hover_progress)

    def _animate_hover(self,value):
        if not self.isEnabled():
            return
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover_progress)
        self._hover_animation.setEndValue(value)
        self._hover_animation.start()

    def enterEvent(self,event):
        if not self.isEnabled():
            self._hover_progress=0.0
            self.update()
            super().enterEvent(event)
            return
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self,event):
        if not self.isEnabled():
            self._hover_progress=0.0
            self.update()
            super().leaveEvent(event)
            return
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def setEnabled(self,enabled):
        super().setEnabled(enabled)
        if not enabled:
            self._hover_animation.stop()
            self._hover_progress=0.0
            self.update()

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        progress=self._hover_progress
        option=QStyleOptionButton()
        self.initStyleOption(option)
        lift=round(2*progress)
        inset=round(1-progress)
        option.rect=self.rect().adjusted(inset,2-lift,-inset,0)
        self.style().drawControl(QStyle.CE_PushButton,option,painter,self)


class PatternedBackground(QWidget):
    def __init__(self,parent=None,patterned=True):
        super().__init__(parent)
        self.patterned=patterned
        self.setAttribute(Qt.WA_StyledBackground,True)
        self._tile=self._make_tile()

    @staticmethod
    def _make_tile():
        source=QPixmap(APP_ICON)
        if source.isNull():
            return QPixmap()
        source=source.scaled(132,132,Qt.KeepAspectRatio,Qt.SmoothTransformation)
        return source.transformed(QTransform().rotate(45),Qt.SmoothTransformation)

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.fillRect(self.rect(),QColor("#000000" if not self.patterned else "#080c14"))
        if not self.patterned or self._tile.isNull():
            return
        painter.setOpacity(0.13)
        step_x=self._tile.width()+150
        step_y=self._tile.height()+125
        for row,y in enumerate(range(-step_y,self.height()+step_y,step_y)):
            offset=step_x//2 if row%2 else 0
            for x in range(-step_x+offset,self.width()+step_x,step_x):
                painter.drawPixmap(x,y,self._tile)


class PanelGroupBox(QGroupBox):
    def __init__(self,title,parent=None):
        super().__init__(title,parent)
        self._title_text=title
        self._collapsible=False
        self._collapsed=False
        self._collapse_animation=QPropertyAnimation(self,b"maximumHeight",self)
        self._collapse_animation.setDuration(220)
        self._collapse_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._collapse_animation.finished.connect(self._collapse_animation_finished)

    def set_collapsible(self,enabled=True):
        self._collapsible=enabled
        if enabled:
            self.setCursor(Qt.PointingHandCursor)
            self.setProperty("collapsed",True)
            self.set_collapsed(True)
            self._update_title()

    def _update_title(self):
        marker="▸ " if self._collapsed else "▾ "
        self.setTitle(marker+self._title_text if self._collapsible else self._title_text)

    def set_collapsed(self,collapsed):
        if collapsed==self._collapsed and not self._collapse_animation.state():
            return
        self._collapse_animation.stop()
        self._collapsed=collapsed
        self.setProperty("collapsed",collapsed)
        self._update_title()
        self.style().unpolish(self)
        self.style().polish(self)
        self.updateGeometry()

        if collapsed:
            start_height=max(48,self.height())
            self._collapse_animation.setStartValue(start_height)
            self._collapse_animation.setEndValue(48)
        else:
            if self.layout():
                for index in range(self.layout().count()):
                    item=self.layout().itemAt(index)
                    if item.widget():
                        item.widget().setVisible(True)
            self.setMaximumHeight(16777215)
            target_height=max(48,self.sizeHint().height())
            self.setMaximumHeight(48)
            self._collapse_animation.setStartValue(48)
            self._collapse_animation.setEndValue(target_height)
        self._collapse_animation.start()

    def _collapse_animation_finished(self):
        if self._collapsed:
            self._hide_collapsed_contents()
        else:
            self._finish_expanded()

    def _hide_collapsed_contents(self):
        if self._collapsed and self.layout():
            for index in range(self.layout().count()):
                item=self.layout().itemAt(index)
                if item.widget():
                    item.widget().setVisible(False)
        self.setMaximumHeight(48)

    def _finish_expanded(self):
        if not self._collapsed:
            self.setMaximumHeight(16777215)

    def mousePressEvent(self,event):
        if self._collapsible and event.position().y()<34:
            self.set_collapsed(not self._collapsed)
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.isEnabled():
            painter.setBrush(QColor("#182536"))
            painter.setPen(QPen(QColor("#3e6388"),2.0))
        else:
            painter.setBrush(QColor("#171b21"))
            painter.setPen(QPen(QColor("#343b45"),2.0))
        painter.drawRoundedRect(self.rect().adjusted(1,8,-2,-2),13,13)
        super().paintEvent(event)


class SurfaceFrame(QFrame):
    def __init__(self,color,border,radius=20,parent=None):
        super().__init__(parent)
        self.surface_color=color
        self.border_color=border
        self.radius=radius
        self.setAttribute(Qt.WA_TranslucentBackground,True)

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect=self.rect().adjusted(1,1,-2,-2)
        painter.setBrush(self.surface_color)
        painter.setPen(QPen(self.border_color,2.0))
        painter.drawRoundedRect(rect,self.radius,self.radius)


class JsonSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self,document):
        super().__init__(document)
        self.rules=[]

        def format_text(color,bold=False):
            text_format=QTextCharFormat()
            text_format.setForeground(QColor(color))
            if bold:
                text_format.setFontWeight(QFont.Bold)
            return text_format

        self.rules.extend((
            (QRegularExpression(r'"(?:\\.|[^"\\])*"(?=\s*:)'),format_text("#78b9f2",True)),
            (QRegularExpression(r'"(?:\\.|[^"\\])*"'),format_text("#d6e7ff")),
            (QRegularExpression(r'\b(?:true|false)\b'),format_text("#c5a4f5",True)),
            (QRegularExpression(r'\bnull\b'),format_text("#8d98a8",True)),
            (QRegularExpression(r'-?\b\d+(?:\.\d+)?\b'),format_text("#9ed6a8")),
            (QRegularExpression(r'[\{\}\[\],:]'),format_text("#718096")),
        ))

    def highlightBlock(self,text):
        for expression,text_format in self.rules:
            match=expression.match(text)
            while match.hasMatch():
                self.setFormat(match.capturedStart(),match.capturedLength(),text_format)
                match=expression.match(text,match.capturedEnd())


def add_subtle_shadows(root,excluded=()):
    excluded=set(excluded)
    shadow_types=(QScrollBar,SurfaceFrame)
    for widget in root.findChildren(QWidget):
        if widget in excluded or not isinstance(widget,shadow_types):
            continue
        effect=QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(16)
        effect.setOffset(0,4)
        effect.setColor(QColor(0,0,0,155))
        widget.setGraphicsEffect(effect)


def set_status(text,color="#949ba4"):
    status_label.setText(f"●  {text}")
    status_label.setStyleSheet(
        f"color:{color};font-family:\"Inter\",\"Geist Sans\",\"Segoe UI\",system-ui,sans-serif;"
        "font-size:13px;font-weight:700;"
    )


def webhook_urls():
    return [line.strip() for line in webhook_input.toPlainText().splitlines() if line.strip()]


def insert_helper(text):
    message_input.textCursor().insertText(text)
    message_input.setFocus()


def current_payload():
    image_url=embed_image_input.text().strip()
    thumbnail_url=embed_thumbnail_input.text().strip()
    embed=build_embed(image_url or None,thumbnail_url or None)
    return build_payload(message_input.toPlainText(),username_input.text().strip(),embed)


def apply_payload_to_form(payload,avatar_url=""):
    form_widgets=[
        username_input,avatar_input,message_input,embed_enabled,embed_title,
        embed_description,embed_url,embed_author,embed_author_url,
        embed_author_icon,embed_image_input,embed_thumbnail_input,embed_footer,
        embed_footer_icon,timestamp_enabled,timestamp_input
    ]
    blockers=[QSignalBlocker(widget) for widget in form_widgets]
    try:
        reset_editor_state()
        username_input.setText(payload.get("username",""))
        message_input.setPlainText(payload.get("content",""))
        if avatar_url and os.path.isfile(avatar_url):
            global avatar_path
            avatar_path=avatar_url
            avatar_input.setText(avatar_url)
        embeds=payload.get("embeds",[])
        embed_enabled.setChecked(bool(embeds))
        if embeds:
            e=embeds[0]
            embed_title.setText(e.get("title",""))
            embed_description.setPlainText(e.get("description",""))
            embed_url.setText(e.get("url",""))
            author=e.get("author",{})
            embed_author.setText(author.get("name",""))
            embed_author_url.setText(author.get("url",""))
            embed_author_icon.setText(author.get("icon_url",""))
            footer=e.get("footer",{})
            embed_footer.setText(footer.get("text",""))
            embed_footer_icon.setText(footer.get("icon_url",""))
            embed_image_input.setText(e.get("image",{}).get("url",""))
            embed_thumbnail_input.setText(e.get("thumbnail",{}).get("url",""))
            set_color(f"#{int(e['color']):06X}" if "color" in e else DEFAULT_COLOR)
            if e.get("timestamp"):
                parsed=QDateTime.fromString(str(e["timestamp"]),Qt.ISODate)
                if parsed.isValid():
                    timestamp_input.setDateTime(parsed.toLocalTime())
                    timestamp_enabled.setChecked(True)
            for field in e.get("fields",[])[:MAX_FIELDS]:
                add_field()
                widget=fields_layout.itemAt(fields_layout.count()-2).widget()
                widget.name_input.setText(field.get("name",""))
                widget.value_input.setText(field.get("value",""))
                widget.inline.setChecked(bool(field.get("inline",False)))
        update_preview()
    finally:
        del blockers
    set_embed_enabled(embed_enabled.isChecked())
    if json_editor is not None:
        load_current_json()


def set_json_status(valid):
    if valid:
        json_status_label.setText("✓ VALID JSON")
        json_status_label.setStyleSheet(
            "color:#9bc4e8;background:#17324a;border:1px solid #37658d;"
            "border-radius:5px;padding:4px 8px;font-family:\"JetBrains Mono\","
            "\"Fira Code\",\"DejaVu Sans Mono\",monospace;font-size:11px;font-weight:700;"
        )
    else:
        json_status_label.setText("⚠ INVALID SYNTAX")
        json_status_label.setStyleSheet(
            "color:#e4aaaa;background:#43272d;border:1px solid #87505a;"
            "border-radius:5px;padding:4px 8px;font-family:\"JetBrains Mono\","
            "\"Fira Code\",\"DejaVu Sans Mono\",monospace;font-size:11px;font-weight:700;"
        )


def update_json_status():
    text=json_editor.toPlainText()
    json_length_label.setText(f"LENGTH: {len(text)}/2000")
    try:
        data=json.loads(text)
    except json.JSONDecodeError:
        set_json_status(False)
        json_embeds_label.setText("EMBEDS: 0/10")
        return
    set_json_status(True)
    try:
        payload=unwrap_payload(data)
        embeds=payload.get("embeds") if isinstance(payload,dict) else None
        count=len(embeds) if isinstance(embeds,list) else 0
    except (TypeError,ValueError):
        count=0
    json_embeds_label.setText(f"EMBEDS: {count}/10")


def load_form_to_json():
    data=current_payload()
    data["avatar_url"]=avatar_path
    json_editor.setPlainText(json.dumps(data,indent=4,ensure_ascii=False))


def load_current_json():
    load_form_to_json()


def toggle_json_focus():
    global json_fullscreen
    json_fullscreen=not json_fullscreen
    for widget in (appearance,webhook,embed,actions_group):
        widget.setVisible(not json_fullscreen)
    json_focus_button.setText("Exit Editor Focus" if json_fullscreen else "Expand Editor")
    json_group.setTitle("JSON Payload — Focus Mode" if json_fullscreen else "JSON Payload")
    sync_external_scrollbar()


def format_json():
    try:
        data=json.loads(json_editor.toPlainText())
        json_editor.setPlainText(json.dumps(data,indent=4,ensure_ascii=False))
    except json.JSONDecodeError:
        update_json_status()


def minify_json():
    try:
        data=json.loads(json_editor.toPlainText())
        json_editor.setPlainText(json.dumps(data,separators=(",",":"),ensure_ascii=False))
    except json.JSONDecodeError:
        update_json_status()


def apply_json_editor():
    try:
        data=json.loads(json_editor.toPlainText())
        avatar_url=data.pop("avatar_url","") if isinstance(data,dict) else ""
        payload=sanitize_payload(unwrap_payload(data))
        apply_payload_to_form(payload,avatar_url if isinstance(avatar_url,str) else "")
        set_status("JSON applied","#57f287")
    except (ValueError,TypeError,json.JSONDecodeError) as error:
        QMessageBox.critical(window,"Invalid JSON Payload",str(error))


def template_data():
    data={
        "version": 1,
        "username": username_input.text(),
        "avatar_path": avatar_path,
        "message": message_input.toPlainText(),
        "embed_enabled": embed_enabled.isChecked(),
        "embed": {
            "title": embed_title.text(), "description": embed_description.toPlainText(),
            "url": embed_url.text(), "author": embed_author.text(),
            "author_url": embed_author_url.text(), "author_icon": embed_author_icon.text(),
            "image": embed_image_input.text(), "thumbnail": embed_thumbnail_input.text(),
            "footer": embed_footer.text(), "footer_icon": embed_footer_icon.text(),
            "timestamp_enabled": timestamp_enabled.isChecked(),
            "timestamp": timestamp_input.dateTime().toString(Qt.ISODate),
            "color": embed_color, "fields": get_fields(),
        },
        "note": "Webhook URLs are intentionally omitted from templates.",
    }
    return data


def save_template():
    path,_=QFileDialog.getSaveFileName(window,"Save Template","","JSON files (*.json)")
    if not path:
        return
    try:
        with open(path,"w",encoding="utf-8") as output:
            json.dump(template_data(),output,indent=2)
        set_status("Template saved","#57f287")
    except (OSError,TypeError) as error:
        QMessageBox.critical(window,"Template Error",f"Could not save template:\n{error}")


def load_template():
    path,_=QFileDialog.getOpenFileName(window,"Load Template","","JSON files (*.json)")
    if not path:
        return
    try:
        with open(path,encoding="utf-8") as source:
            data=json.load(source)
        data=normalize_template(data)
        reset_editor_state()
        username_input.setText(data["username"])
        message_input.setPlainText(data["message"])
        embed_enabled.setChecked(data["embed_enabled"])
        e=data["embed"]
        for widget,key in (
            (embed_title,"title"),(embed_url,"url"),(embed_author,"author"),
            (embed_author_url,"author_url"),(embed_author_icon,"author_icon"),
            (embed_image_input,"image"),(embed_thumbnail_input,"thumbnail"),
            (embed_footer,"footer"),(embed_footer_icon,"footer_icon")
        ):
            widget.setText(e[key])
        embed_description.setPlainText(e["description"])
        timestamp_enabled.setChecked(e["timestamp_enabled"])
        if e["timestamp"]:
            parsed=QDateTime.fromString(e["timestamp"],Qt.ISODate)
            if parsed.isValid():
                timestamp_input.setDateTime(parsed)
        set_color(e["color"])
        for field in e["fields"]:
            add_field()
            widget=fields_layout.itemAt(fields_layout.count()-2).widget()
            if isinstance(widget,EmbedField):
                widget.name_input.setText(field["name"])
                widget.value_input.setText(field["value"])
                widget.inline.setChecked(field["inline"])
        global avatar_path
        avatar_path=data["avatar_path"] if data["avatar_path"] and os.path.isfile(data["avatar_path"]) else ""
        avatar_input.setText(avatar_path)
        set_status("Template loaded","#57f287")
        update_preview()
        load_current_json()
    except (OSError,ValueError,TypeError,json.JSONDecodeError) as error:
        QMessageBox.critical(window,"Template Error",f"Could not load template:\n{error}")


def export_payload():
    path,_=QFileDialog.getSaveFileName(window,"Export Payload","","JSON files (*.json)")
    if not path:
        return
    try:
        with open(path,"w",encoding="utf-8") as output:
            json.dump(current_payload(),output,indent=2)
        set_status("Payload exported","#57f287")
    except OSError as error:
        QMessageBox.critical(window,"JSON Error",f"Could not export payload:\n{error}")


def import_payload():
    path,_=QFileDialog.getOpenFileName(window,"Import Payload","","JSON files (*.json)")
    if not path:
        return
    try:
        with open(path,encoding="utf-8") as source:
            payload=sanitize_payload(unwrap_payload(json.load(source)))
        apply_payload_to_form(payload)
        set_status("Payload imported","#57f287")
    except (OSError,ValueError,TypeError,json.JSONDecodeError) as error:
        QMessageBox.critical(window,"Invalid JSON Payload",str(error))


def choose_image(title):
    return QFileDialog.getOpenFileName(
        window,title,"","Images (*.png *.jpg *.jpeg *.gif *.webp)"
    )[0]


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

        remove=AnimatedButton("Remove")
        remove.setStyleSheet(button_style("#22364d"))

        tooltip(self.name_input,"Enter the field heading shown in the embed. Discord allows up to 256 characters.")
        tooltip(self.value_input,"Enter the field body shown below its heading. Discord allows up to 1,024 characters.")
        tooltip(self.inline,"Place this field beside other inline fields when Discord has enough horizontal space.")
        tooltip(remove,"Remove this field from the current embed.")

        l.addWidget(self.name_input,0,0)
        l.addWidget(self.value_input,0,1)
        l.addWidget(self.inline,0,2)
        l.addWidget(remove,0,3)

        self.name_input.textChanged.connect(lambda: self.changed.emit())
        self.value_input.textChanged.connect(lambda: self.changed.emit())
        self.inline.stateChanged.connect(lambda: self.changed.emit())
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
    QTimer.singleShot(0,sync_external_scrollbar)


def remove_field(field):
    field.deleteLater()
    update_preview()
    QTimer.singleShot(0,sync_external_scrollbar)


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
        set_color(c.name())


def set_color(value):
    global embed_color
    try:
        embed_color, decimal=color_values(value)
    except ValueError:
        return
    color_button.setStyleSheet(button_style(embed_color))
    color_hex_label.setText(embed_color)
    color_decimal_label.setText(f"Decimal: {decimal}")
    update_preview()


def get_timestamp():
    if not timestamp_enabled.isChecked():
        return None

    return timestamp_input.dateTime().toUTC().toString("yyyy-MM-ddTHH:mm:ssZ")


def build_embed(image_url=None,thumbnail_url=None):
    return build_embed_payload(
        enabled=embed_enabled.isChecked(),
        title=embed_title.text(),
        description=embed_description.toPlainText(),
        url=embed_url.text(),
        author=embed_author.text(),
        author_url=embed_author_url.text(),
        author_icon=embed_author_icon.text(),
        footer=embed_footer.text(),
        footer_icon=embed_footer_icon.text(),
        fields=get_fields(),
        image_url=image_url,
        thumbnail_url=thumbnail_url,
        timestamp=get_timestamp(),
        color=embed_color,
    )


class WebhookWorker(QObject):
    finished=Signal(object)

    def __init__(self,urls,path,payload):
        super().__init__()
        self.urls=urls
        self.path=path
        self.payload=payload

    def run(self):
        thread=QThread.currentThread()
        try:
            result=broadcast_requests(
                self.urls,
                avatar_path=self.path,
                payload_factory=lambda: sanitize_payload(replace_placeholders(self.payload)),
                should_continue=lambda: not thread.isInterruptionRequested(),
            )
        except ValueError as error:
            result=[{"ok":False,"error":str(error)}]
        self.finished.emit(result)


class WebhookReceiver(QObject):
    @Slot(object)
    def handle(self,result):
        thread=getattr(window,"_webhook_thread",None)
        try:
            if not getattr(window,"_closing",False):
                webhook_finished(result)
        finally:
            if thread is not None:
                thread.quit()


class MainWindow(QWidget):
    def resizeEvent(self,event):
        super().resizeEvent(event)

        for name in ("welcome","builder"):
            child=getattr(self,name,None)
            if child is not None:
                child.setGeometry(self.rect())
        QTimer.singleShot(0,sync_external_scrollbar)

    def closeEvent(self,event):
        self._closing=True
        thread=getattr(self,"_webhook_thread",None)

        if thread is not None and thread.isRunning():
            thread.requestInterruption()
            event.ignore()
            if not getattr(self,"_close_waiting",False):
                self._close_waiting=True
                thread.finished.connect(lambda: QTimer.singleShot(0,self.close))
            return
        if preview_window is not None:
            preview_window.close()
        event.accept()


def sync_external_scrollbar():
    bar=globals().get("scroll_bar")
    internal=globals().get("internal_scrollbar")
    if bar is not None and internal is not None:
        bar.setRange(internal.minimum(),internal.maximum())
        bar.setPageStep(internal.pageStep())
        bar.setSingleStep(internal.singleStep())


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
        <div style='font-size:15px;line-height:22px;'>
            <span style='display:inline-block;background:#3b82c4;color:white;
                border-radius:14px;padding:2px 7px;font-weight:bold;'>D</span>
            <b>&nbsp;{html.escape(username)}</b>
            <span style='color:#949ba4;font-size:11px;'>&nbsp;Today at just now</span>
        </div>
        <div style='margin:7px 0 0 31px;line-height:1.5;'>
            {markdown_to_html(message) if message else "<span style='color:#949ba4'>No message content</span>"}
        </div>
    """

    if e:
        p+=f"""
        <div style='
            margin:14px 0 0 31px;
            background:#2b2d31;
            border-left:5px solid {embed_color};
            border-radius:6px;
            padding:12px 14px;
        '>
        """

        if a:=e.get("author"):
            p+=f"""
            <div style='margin-bottom:7px;color:#f2f3f5;font-size:12px;font-weight:700;'>
                {html.escape(a['name'])}
            </div>
            """

        if e.get("title"):
            title_html=html.escape(e["title"])
            if e.get("url"):
                title_html=f"<font color='#00a8fc'><u>{title_html}</u></font>"
            p+=f"""
            <div style='font-size:16px;font-weight:700;margin-bottom:7px;color:#fff;'>
                {title_html}
            </div>
            """

        if e.get("description"):
            p+=f"<div style='line-height:1.5;'>{markdown_to_html(e['description'])}</div>"

        if fields:=e.get("fields"):
            p+="<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:10px;'>"
            row=[]
            for field in fields:
                cell=f"""
                <td width='33%' valign='top' style='padding:5px 10px 5px 0;'>
                    <b>{html.escape(field["name"])}</b><br>
                    {markdown_to_html(field["value"])}
                </td>
                """
                if field["inline"]:
                    row.append(cell)
                    if len(row)==3:
                        p+="<tr>"+''.join(row)+"</tr>"
                        row=[]
                else:
                    if row:
                        p+="<tr>"+''.join(row)+"</tr>"
                        row=[]
                    p+="<tr>"+cell.replace("width='33%'","width='100%'")+"</tr>"
            if row:
                p+="<tr>"+''.join(row)+"</tr>"
            p+="</table>"

        if image_url:
            p+=f"""
            <div style='margin-top:12px;background:#202225;border-radius:4px;
                padding:24px 10px;color:#949ba4;text-align:center;'>
                Image preview: {html.escape(image_url)}
            </div>
            """

        if thumbnail_url:
            p+=f"""
            <div style='margin-top:8px;color:#949ba4;font-size:11px;'>
                Thumbnail: {html.escape(thumbnail_url)}
            </div>
            """

        if e.get("timestamp"):
            p+="<div style='margin-top:10px;color:#949ba4;font-size:11px;'>Timestamp</div>"

        if footer:=e.get("footer"):
            p+=f"""
            <div style='margin-top:12px;color:#949ba4;font-size:11px;'>
                {html.escape(footer["text"])}
            </div>
            """

        p+="</div>"

    preview_window.set_preview(p+"</div>")


def send_webhook():
    urls=webhook_urls()
    username=username_input.text().strip()
    message=message_input.toPlainText().strip()

    if not urls:
        set_status("Missing webhook","#faa61a")
        QMessageBox.warning(window,"Missing Webhook","Enter one or more Discord webhook URLs.")
        return

    invalid=[url for url in urls if not valid_webhook(url)]
    if invalid:
        set_status("Invalid webhook","#ed4245")
        QMessageBox.warning(window,"Invalid Webhook","One or more webhook URLs are invalid.")
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

    if e and payload_errors(message,e):
        set_status("Embed too large","#ed4245")
        QMessageBox.warning(window,"Embed Too Large","Discord embeds can contain up to 6000 characters.")
        return

    try:
        payload=sanitize_payload(build_payload(message,username,e))
    except ValueError as error:
        QMessageBox.warning(window,"Invalid Payload",str(error))
        return

    send_button.setEnabled(False)
    set_status("Sending webhook...","#faa61a")
    thread=QThread()
    worker=WebhookWorker(urls,avatar_path,payload)
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
    successes=sum(1 for item in result if item.get("ok"))
    failures=len(result)-successes
    if failures==0:
        set_status("Sent successfully","#57f287")
        QMessageBox.information(window,"Success",f"Sent successfully to {successes} webhook(s).")
        return
    set_status(f"Partial failure: {successes} sent, {failures} failed","#faa61a")
    details="; ".join(
        f"Webhook {index}: HTTP {item['status']}" if "status" in item else
        f"Webhook {index}: {item.get('error','request failed')}"
        for index,item in enumerate(result,1) if not item.get("ok")
    )
    QMessageBox.warning(window,"Partial Failure",f"{successes} webhook(s) sent; {failures} failed.\n\n{details}")


def reset_editor_state():
    global avatar_path,embed_color

    for w in (
        username_input,avatar_input,embed_title,embed_url,
        embed_author,embed_author_url,embed_author_icon,embed_footer,
        embed_footer_icon,embed_image_input,embed_thumbnail_input
    ):
        w.clear()

    message_input.clear()
    embed_description.clear()
    embed_enabled.setChecked(False)
    timestamp_enabled.setChecked(False)
    timestamp_input.setDateTime(QDateTime.currentDateTime())

    while fields_layout.count()>1:
        item=fields_layout.takeAt(0)

        if item.widget():
            item.widget().deleteLater()

    avatar_path=""
    embed_color=DEFAULT_COLOR
    set_color(DEFAULT_COLOR)


def clear_fields():
    reset_editor_state()
    webhook_input.clear()
    set_status("Ready")
    update_preview()
    load_current_json()


def set_embed_enabled(enabled):
    embed_body.setEnabled(enabled)

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


def create_app():
    global app,webhook_receiver,window,welcome,builder,enter_button,username_input,avatar_input,webhook_input,message_input,embed_enabled,embed_title,embed_description,embed_url,color_button,embed_author,embed_author_url,embed_author_icon,embed_image_input,embed_thumbnail_input,embed_footer,embed_footer_icon,timestamp_enabled,timestamp_input,fields_layout,preview_button,send_button,clear_button,status_label,embed_controls,color_hex_label,color_decimal_label,json_editor,embed_body,json_status_label,json_length_label,json_embeds_label

    app=QApplication(sys.argv)
    app.setWindowIcon(QIcon(APP_ICON))
    app.setFont(QFont("Inter",10))
    webhook_receiver=WebhookReceiver()

    app.setStyleSheet("""
    QWidget {
        font-family:"Inter","Geist Sans","Segoe UI",system-ui,sans-serif;
        font-size:13px;
        color:#e8eaed;
    }

    QWidget#mainWindow {
        background:#000000;
    }

    QWidget#builder,QWidget#welcome {
        background:transparent;
    }

    QFrame#contentFrame {
        background-color:#0d1218;
        border:2px solid #294c6b;
        border-radius:20px;
    }

    QFrame#scrollFrame {
        background-color:#0d1218;
        border:2px solid #294c6b;
        border-radius:12px;
    }

    QGroupBox {
        background-color:transparent;
        font-weight:700;
        border:none;
        border-radius:14px;
        margin-top:14px;
        padding:17px;
        padding-top:30px;
    }

    QGroupBox::title {
        subcontrol-origin:padding;
        subcontrol-position:top left;
        left:14px;
        top:6px;
        padding:1px 6px;
        color:#f1f3f5;
        background:transparent;
    }

    QGroupBox[collapsed="true"]::title {
        top:2px;
        padding-top:0px;
        padding-bottom:0px;
    }

    QGroupBox:disabled {
        color:#5e6875;
    }

    QGroupBox:disabled::title {
        color:#5e6875;
    }

    QLineEdit,QTextEdit,QDateTimeEdit {
        background-color:#090d13;
        color:#f1f3f5;
        padding:10px 11px;
        border:2px solid #243b54;
        border-radius:7px;
        selection-background-color:#3b82c4;
    }

    QLineEdit:hover,QTextEdit:hover,QDateTimeEdit:hover {
        border:1px solid #414a5a;
    }

    QLineEdit:focus,QTextEdit:focus,QDateTimeEdit:focus {
        border:2px solid #4d89bd;
        background:#111a25;
    }

    QLineEdit:disabled,QTextEdit:disabled,QDateTimeEdit:disabled {
        background:#101113;
        color:#44464b;
        border:1px solid #25272b;
    }

    QTextEdit#urlInput {
        font-family:"SF Mono","Consolas","DejaVu Sans Mono",monospace;
        font-size:12px;
    }

    QTextEdit#payloadEditor,QTextEdit#jsonEditor {
        font-family:"JetBrains Mono","Fira Code","DejaVu Sans Mono",monospace;
        font-size:12px;
    }

    QPushButton {
        background:#2a4967;
        color:white;
        padding:10px 15px;
        border:1px solid #4b6d8d;
        border-radius:8px;
        font-weight:600;
    }

    QPushButton:hover {
        background:#3f668b;
    }

    QPushButton:pressed {
        background:#203c58;
    }

    QPushButton:disabled {
        background:#252b34;
        color:#68717d;
    }

    QCheckBox {
        spacing:8px;
        color:#dbdee1;
    }

    QCheckBox::indicator {
        width:18px;
        height:18px;
        border:2px solid #496d91;
        border-radius:5px;
        background:rgba(10,14,22,220);
    }

    QCheckBox::indicator:hover {
        border:2px solid #6d9ac3;
        background:rgba(59,130,196,70);
    }

    QCheckBox::indicator:checked {
        border:2px solid #4d89bd;
        background:#2a4967;
        image:none;
    }

    QCheckBox:hover {
        color:white;
    }

    QScrollArea {
        border:none;
        background:transparent;
    }

    QScrollBar:vertical {
        background:#080b11;
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
        background:#2a4967;
    }

    QToolTip {
        background:#1b2030;
        color:#f2f3f5;
        border:2px solid #496d91;
        padding:7px 9px;
        border-radius:5px;
    }

    QFrame#jsonStatusBar {
        background:#080d13;
        border:1px solid #243b54;
        border-radius:7px;
    }

    QFrame#mainStatusBar {
        background:#0a1017;
        border:1px solid #294c6b;
        border-radius:9px;
    }

    QLabel#mainStatusLabel {
        color:#a2afbd;
        font-family:"Inter","Geist Sans","Segoe UI",system-ui,sans-serif;
        font-size:13px;
        font-weight:700;
    }

    QLabel#jsonMetricLabel {
        color:#a2afbd;
        font-family:"JetBrains Mono","Fira Code","DejaVu Sans Mono",monospace;
        font-size:11px;
        font-weight:600;
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

    welcome=PatternedBackground(window)
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
        QLabel:hover {color:#6aa9e8;letter-spacing:4px;}
    """)

    welcome_layout.addWidget(logo)
    welcome_layout.addSpacing(48)

    enter_button=AnimatedButton("Enter")
    enter_button.setFixedSize(180,48)
    tooltip(enter_button,"Open the webhook builder.")
    enter_button.setStyleSheet("""
        QPushButton {
            background:#3b82c4;
            color:white;
            border:none;
            border-radius:10px;
            font-size:14px;
            font-weight:700;
        }
        QPushButton:hover {background:#3f668b;}
        QPushButton:pressed {background:#203c58;}
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
        'style="color:#6d9ac3;text-decoration:none;">4Y44N-KH4L3D</a>'
    )
    credit.setOpenExternalLinks(True)
    credit.setCursor(Qt.PointingHandCursor)
    credit.setStyleSheet("font-size:12px;")

    welcome_layout.addWidget(credit,0,Qt.AlignRight|Qt.AlignBottom)

    builder=PatternedBackground(window,patterned=False)
    builder.setObjectName("builder")
    builder.setGeometry(window.rect())
    builder.show()
    welcome.hide()
    builder.raise_()
    window.builder=builder

    main=QVBoxLayout(builder)
    main.setContentsMargins(24,24,24,24)
    main.setSpacing(16)

    header=QHBoxLayout()
    header.setContentsMargins(8,0,8,0)

    logo=QLabel()
    logo.setFixedSize(46,46)
    logo.setAlignment(Qt.AlignCenter)
    logo_pixmap=QPixmap(APP_ICON)
    if not logo_pixmap.isNull():
        logo.setPixmap(logo_pixmap.scaled(42,42,Qt.KeepAspectRatio,Qt.SmoothTransformation))
    logo_shadow=QGraphicsDropShadowEffect(logo)
    logo_shadow.setBlurRadius(24)
    logo_shadow.setOffset(0,0)
    logo_shadow.setColor(QColor("#3b82c4"))
    logo.setGraphicsEffect(logo_shadow)

    title=QLabel("DisHook")
    title.setAlignment(Qt.AlignCenter)
    title.setStyleSheet("""
        QLabel {
            font-size:30px;
            font-weight:900;
            color:#f2f3f5;
            letter-spacing:1px;
        }
    """)

    header.addWidget(logo,0,Qt.AlignLeft|Qt.AlignVCenter)
    header.addStretch()
    header.addWidget(title,0,Qt.AlignCenter)
    header.addStretch()
    header.addSpacing(46)

    main.addLayout(header)

    appearance=PanelGroupBox("Appearance")
    al=QGridLayout()
    al.setHorizontalSpacing(12)
    al.setVerticalSpacing(10)

    username_input=QLineEdit()
    username_input.setPlaceholderText("Optional — override webhook username")
    username_input.setMaxLength(80)

    avatar_input=QLineEdit()
    avatar_input.setReadOnly(True)
    avatar_input.setPlaceholderText("Optional — choose an image")

    avatar_button=AnimatedButton("Choose Image")
    avatar_button.setStyleSheet(button_style("#22364d"))
    tooltip(avatar_button,"Open an image picker and choose the avatar image Discord should use for this webhook.")
    avatar_button.clicked.connect(choose_avatar)

    al.addWidget(QLabel("Username"),0,0)
    al.addWidget(username_input,0,1,1,2)
    al.addWidget(QLabel("Avatar"),1,0)
    al.addWidget(avatar_input,1,1)
    al.addWidget(avatar_button,1,2)

    appearance.setLayout(al)
    appearance.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)

    webhook=PanelGroupBox("Webhook")
    wl=QVBoxLayout()
    wl.setSpacing(10)

    webhook_input=QTextEdit()
    webhook_input.setObjectName("urlInput")
    webhook_input.setPlaceholderText("https://discord.com/api/webhooks/...")
    webhook_input.setMaximumHeight(68)
    webhook_input.setAcceptRichText(False)
    webhook_input.setToolTip("Your webhook URL is hidden for safety.")
    tooltip(webhook_input,"Paste one Discord webhook URL per line. These URLs are used only when sending and are kept separate from exported JSON.")

    message_input=QTextEdit()
    message_input.setObjectName("payloadEditor")
    message_input.setPlaceholderText("Write your Discord message...")
    message_input.setMinimumHeight(150)
    tooltip(message_input,"Write the message Discord will receive. The limit is 2,000 characters. "
            "You can use {date}, {time}, and {computer_name}; they are replaced immediately before sending.")

    format_layout=QHBoxLayout()
    format_layout.setSpacing(3)

    for label,start,end in (
        ("Bold","**","**"),
        ("Italic","*","*"),
        ("Underline","__","__"),
        ("Strikethrough","~~","~~"),
        ("Code","`","`"),
        ("Code Block","```","```"),
        ("Spoiler","||","||")
    ):
        b=AnimatedButton(label)
        b.setStyleSheet("""
            QPushButton {
                background:#22364d;
                color:white;
                padding:7px 8px;
                border:1px solid #3f5f7d;
                border-radius:7px;
                font-size:12px;
                font-weight:600;
            }
            QPushButton:hover {background:#365a7d;}
            QPushButton:pressed {background:#172a3e;}
        """)
        tooltip(b,f"Wrap the selected message text in {label.lower()} Markdown markers. "
                "If no text is selected, markers are inserted where you can continue typing.")
        b.clicked.connect(lambda _,s=start,e=end:insert_format(s,e))
        format_layout.addWidget(b)

    format_layout.addStretch()

    helper_layout=QHBoxLayout()
    emoji_input=QLineEdit()
    emoji_input.setPlaceholderText("Emoji")
    emoji_button=AnimatedButton("Insert Emoji")
    emoji_button.setStyleSheet(button_style("#22364d"))
    emoji_button.clicked.connect(lambda: insert_helper(emoji_input.text()))
    user_id_input=QLineEdit()
    user_id_input.setPlaceholderText("User ID")
    user_button=AnimatedButton("@User")
    user_button.setStyleSheet(button_style("#22364d"))
    user_button.clicked.connect(lambda: insert_helper(f"<@{user_id_input.text().strip()}>") if user_id_input.text().strip().isdigit() else None)
    role_id_input=QLineEdit()
    role_id_input.setPlaceholderText("Role ID")
    role_button=AnimatedButton("@Role")
    role_button.setStyleSheet(button_style("#22364d"))
    role_button.clicked.connect(lambda: insert_helper(f"<@&{role_id_input.text().strip()}>") if role_id_input.text().strip().isdigit() else None)
    for widget in (emoji_input,emoji_button,user_id_input,user_button,role_id_input,role_button):
        helper_layout.addWidget(widget)

    wl.addWidget(QLabel("Webhook URL(s) — one per line"))
    wl.addWidget(webhook_input)
    wl.addWidget(QLabel("Message"))
    wl.addLayout(format_layout)
    wl.addLayout(helper_layout)
    wl.addWidget(message_input,1)

    webhook_content=QWidget()
    webhook_content.setLayout(wl)

    webhook_layout=QVBoxLayout(webhook)
    webhook_layout.setContentsMargins(0,0,0,0)
    webhook_layout.addWidget(webhook_content)
    webhook.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)

    embed=PanelGroupBox("Embed")
    el=QVBoxLayout()
    el.setSpacing(12)

    embed_enabled=QCheckBox("Enable Embed")
    embed_enabled.setStyleSheet("QCheckBox{font-weight:700;}")
    tooltip(embed_enabled,"Enable this to include the embed configuration in the outgoing payload. "
            "When disabled, embed fields are greyed out but preview and JSON tools remain available.")

    basic_group=PanelGroupBox("Basic")
    bl=QVBoxLayout()
    bl.setSpacing(9)

    embed_title=QLineEdit()
    embed_title.setPlaceholderText("Title — max 256 characters")

    embed_description=QTextEdit()
    embed_description.setPlaceholderText("Description — max 4096 characters")
    embed_description.setMaximumHeight(105)

    embed_url=QLineEdit()
    embed_url.setPlaceholderText("Title URL — optional")

    color_button=AnimatedButton("Choose Colour")
    tooltip(color_button,"Choose the accent color displayed along the left edge of the Discord embed.")
    color_button.clicked.connect(choose_color)

    cr=QHBoxLayout()
    cr.addWidget(QLabel("Colour"))
    cr.addWidget(color_button)
    color_hex_label=QLabel(embed_color)
    color_decimal_label=QLabel("Decimal: 5793266")
    cr.addWidget(color_hex_label)
    cr.addWidget(color_decimal_label)
    cr.addStretch()

    bl.addWidget(embed_title)
    bl.addWidget(embed_description)
    bl.addWidget(embed_url)
    bl.addLayout(cr)

    basic_group.setLayout(bl)
    el.addWidget(basic_group)

    author_group=PanelGroupBox("Author")
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

    media_group=PanelGroupBox("Media")
    mr=QVBoxLayout()
    mr.setSpacing(9)

    embed_image_input=QLineEdit()
    embed_image_input.setPlaceholderText("Image URL — optional")

    embed_thumbnail_input=QLineEdit()
    embed_thumbnail_input.setPlaceholderText("Thumbnail URL — optional")

    tooltip(embed_image_input,"Enter a direct HTTP or HTTPS URL for the large image displayed in the embed.")
    tooltip(embed_thumbnail_input,"Enter a direct HTTP or HTTPS URL for the smaller thumbnail displayed in the embed.")

    mr.addWidget(embed_image_input)
    mr.addWidget(embed_thumbnail_input)

    media_group.setLayout(mr)
    el.addWidget(media_group)

    footer_group=PanelGroupBox("Footer")
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

    timestamp_group=PanelGroupBox("Timestamp")
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

    fields_group=PanelGroupBox("Fields")
    fgl=QVBoxLayout()
    fgl.setSpacing(9)

    fields_container=QWidget()
    fields_layout=QVBoxLayout(fields_container)
    fields_layout.setContentsMargins(0,0,0,0)
    fields_layout.setSpacing(6)
    fields_layout.addStretch()

    add_field_button=AnimatedButton("+ Add Field")
    add_field_button.setStyleSheet(button_style("#22364d"))
    tooltip(add_field_button,"Add another name-and-value field to the embed. Discord permits up to 25 fields.")
    add_field_button.clicked.connect(add_field)

    fgl.addWidget(fields_container)
    fgl.addWidget(add_field_button)

    fields_group.setLayout(fgl)
    el.addWidget(fields_group,1)

    for group in (basic_group,author_group,media_group,footer_group,timestamp_group,fields_group):
        group.set_collapsible()

    embed_body=QWidget()
    embed_body.setLayout(el)

    preview_button=AnimatedButton("Live Preview")
    preview_button.setStyleSheet(button_style("#22364d"))
    tooltip(preview_button,"Open a Discord-style preview of the current message and embed without sending anything.")
    preview_button.clicked.connect(open_preview)

    file_controls=QHBoxLayout()
    for label,callback in (
        ("Save Template",save_template),("Load Template",load_template),
        ("Export JSON",export_payload),("Import JSON",import_payload)
    ):
        button=AnimatedButton(label)
        button.setStyleSheet(button_style("#22364d"))
        button.clicked.connect(callback)
        action_tooltips={
            "Save Template":(
                "Save the visual editor settings as a reusable template. "
                "This stores the username, message, embed settings, fields, timestamp, colour, "
                "and local avatar path, but deliberately excludes webhook URLs."
            ),
            "Load Template":(
                "Load a previously saved template and replace the current visual form values. "
                "Webhook URLs are not restored, and avatar paths are used only if the local file still exists."
            ),
            "Export JSON":(
                "Export the current Discord payload as a JSON file. "
                "The file contains content, username, embeds, and the required safe mention settings; "
                "webhook URLs are never included."
            ),
            "Import JSON":(
                "Import a Discord payload JSON file into the visual builder. "
                "The payload is validated and sanitized before replacing the message and embed fields; "
                "the separate webhook URL field is left unchanged."
            ),
        }
        tooltip(button,action_tooltips[label])
        file_controls.addWidget(button)
    actions_group=PanelGroupBox("Actions")
    actions_layout=QVBoxLayout()
    actions_layout.setSpacing(9)
    actions_layout.addWidget(preview_button)
    actions_layout.addLayout(file_controls)
    actions_group.setLayout(actions_layout)

    for widget,text in (
        (username_input,"Optional display name sent with the webhook instead of its default name. Maximum 80 characters."),
        (avatar_input,"Read-only path of the selected avatar image. Use Choose Image to change it."),
        (embed_title,"Optional title shown at the top of the embed. Maximum 256 characters."),
        (embed_description,"Optional main description shown below the embed title. Maximum 4,096 characters."),
        (embed_url,"Optional URL opened when a user clicks the embed title."),
        (embed_author,"Optional author label displayed above the embed title. Maximum 256 characters."),
        (embed_author_url,"Optional URL opened when the author label is clicked."),
        (embed_author_icon,"Optional direct HTTP/HTTPS URL for the author icon."),
        (embed_image_input,"Optional direct HTTP/HTTPS URL for the large embed image."),
        (embed_thumbnail_input,"Optional direct HTTP/HTTPS URL for the embed thumbnail."),
        (embed_footer,"Optional text displayed at the bottom of the embed. Maximum 2,048 characters."),
        (embed_footer_icon,"Optional direct HTTP/HTTPS URL for the footer icon."),
        (timestamp_input,"Choose the date and time Discord should display in the embed."),
        (timestamp_enabled,"Include the selected date and time in the outgoing embed.")
    ):
        tooltip(widget,text)

    embed_layout=QVBoxLayout(embed)
    embed_layout.setContentsMargins(0,0,0,0)
    embed_layout.addWidget(embed_enabled)
    embed_layout.addWidget(embed_body)
    embed.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)

    json_group=PanelGroupBox("JSON Payload")
    json_layout=QVBoxLayout()
    json_layout.setSpacing(9)

    json_editor=QTextEdit()
    json_editor.setObjectName("jsonEditor")
    json_editor.setAcceptRichText(False)
    json_editor.setUndoRedoEnabled(True)
    json_editor.setMinimumHeight(220)
    json_editor.setPlaceholderText('{\n  "content": "Your message"\n}')
    tooltip(json_editor,"Edit the raw Discord payload directly. Use this for advanced changes that are not exposed by the visual form, then choose Apply to Form to validate and import it.")

    json_description=QLabel("— Edit raw Discord payload JSON here; use this for advanced payload changes.")
    json_description.setStyleSheet("color:#778393;font-size:11px;")
    json_description.setWordWrap(True)

    json_toolbar=QHBoxLayout()
    json_toolbar.setSpacing(6)

    format_json_button=AnimatedButton("Format JSON")
    format_json_button.setStyleSheet(button_style("#22364d"))
    format_json_button.clicked.connect(format_json)

    minify_json_button=AnimatedButton("Minify")
    minify_json_button.setStyleSheet(button_style("#22364d"))
    minify_json_button.clicked.connect(minify_json)

    load_json_button=AnimatedButton("Load Form")
    load_json_button.setStyleSheet(button_style("#22364d"))
    load_json_button.clicked.connect(load_form_to_json)

    apply_json_button=AnimatedButton("Apply to Form")
    apply_json_button.clicked.connect(apply_json_editor)
    tooltip(format_json_button,"Parse the JSON and rewrite it with four-space indentation so nested objects are easier to read.")
    tooltip(minify_json_button,"Parse valid JSON and remove structural whitespace, producing a compact single-line payload.")
    tooltip(load_json_button,"Collect the current form values and replace the editor contents with the corresponding JSON payload.")
    tooltip(apply_json_button,"Validate the edited JSON, reject unsupported or unsafe keys, and copy the payload back into the visual form. Webhook URLs stay separate.")
    for button in (format_json_button,minify_json_button,load_json_button,apply_json_button):
        json_toolbar.addWidget(button)
    json_toolbar.addStretch()

    json_status_frame=QFrame()
    json_status_frame.setObjectName("jsonStatusBar")
    json_status_bar=QHBoxLayout(json_status_frame)
    json_status_bar.setContentsMargins(8,5,8,5)
    json_status_bar.setSpacing(14)
    json_status_label=QLabel("✓ VALID JSON")
    json_status_label.setObjectName("jsonStatusLabel")
    json_length_label=QLabel("LENGTH: 0/2000")
    json_length_label.setObjectName("jsonMetricLabel")
    json_embeds_label=QLabel("EMBEDS: 0/10")
    json_embeds_label.setObjectName("jsonMetricLabel")
    for label in (json_status_label,json_length_label,json_embeds_label):
        label.setStyleSheet("color:#778393;font-family:\"JetBrains Mono\",\"Fira Code\",\"DejaVu Sans Mono\",monospace;font-size:11px;")
        json_status_bar.addWidget(label)
    json_status_bar.addStretch()
    json_editor.textChanged.connect(update_json_status)

    json_layout.addWidget(json_description)
    json_layout.addWidget(json_editor)
    json_layout.addLayout(json_toolbar)
    json_layout.addWidget(json_status_frame)
    json_group.setLayout(json_layout)

    sections=QWidget()
    sections_layout=QVBoxLayout(sections)
    sections_layout.setContentsMargins(0,0,0,0)
    sections_layout.setSpacing(16)
    sections_layout.addWidget(appearance)
    sections_layout.addWidget(webhook)
    sections_layout.addWidget(embed)
    sections_layout.addWidget(actions_group)
    sections_layout.addWidget(json_group)
    sections_layout.addStretch()
    sections.setAttribute(Qt.WA_StyledBackground,True)
    sections.setStyleSheet("background:transparent;")

    sections_scroll=QScrollArea()
    sections_scroll.setWidgetResizable(True)
    sections_scroll.setFrameShape(QFrame.NoFrame)
    sections_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sections_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sections_scroll.verticalScrollBar().setSingleStep(18)
    sections_scroll.viewport().setStyleSheet("background:transparent;")
    sections_scroll.setWidget(sections)

    internal_scrollbar=sections_scroll.verticalScrollBar()
    scroll_bar=QScrollBar(Qt.Vertical)
    scroll_bar.setRange(internal_scrollbar.minimum(),internal_scrollbar.maximum())
    scroll_bar.setPageStep(internal_scrollbar.pageStep())
    scroll_bar.setSingleStep(18)
    scroll_bar.valueChanged.connect(internal_scrollbar.setValue)
    internal_scrollbar.valueChanged.connect(scroll_bar.setValue)
    internal_scrollbar.rangeChanged.connect(lambda *_: sync_external_scrollbar())

    content_frame=SurfaceFrame(QColor(13,18,24,255),QColor(41,76,107,255),20)
    content_frame.setObjectName("contentFrame")
    content_frame.setAttribute(Qt.WA_StyledBackground,True)
    content_frame_layout=QVBoxLayout(content_frame)
    content_frame_layout.setContentsMargins(16,16,16,16)
    content_frame_layout.addWidget(sections_scroll)

    scroll_frame=SurfaceFrame(QColor(13,18,24,255),QColor(41,76,107,255),12)
    scroll_frame.setObjectName("scrollFrame")
    scroll_frame.setAttribute(Qt.WA_StyledBackground,True)
    scroll_frame.setFixedWidth(20)
    scroll_frame_layout=QVBoxLayout(scroll_frame)
    scroll_frame_layout.setContentsMargins(5,5,5,5)
    scroll_frame_layout.addWidget(scroll_bar)

    content_row=QHBoxLayout()
    content_row.setSpacing(16)
    content_row.addWidget(content_frame,1)
    content_row.addWidget(scroll_frame)

    main.addLayout(content_row,1)

    controls=QHBoxLayout()
    controls.setSpacing(9)

    send_button=AnimatedButton("Send Webhook")
    send_button.setMinimumHeight(44)
    tooltip(send_button,"Validate the current message, embed, and webhook URLs, then send the payload to each URL.")
    send_button.clicked.connect(send_webhook)

    clear_button=AnimatedButton("Clear")
    clear_button.setMinimumHeight(44)
    clear_button.setStyleSheet(button_style("#22364d"))
    tooltip(clear_button,"Reset the message, embed, avatar, webhook URL, and JSON editor back to their initial state.")
    clear_button.clicked.connect(clear_fields)

    controls.addWidget(send_button,2)
    controls.addWidget(clear_button,1)

    main.addLayout(controls)

    main_status_frame=QFrame()
    main_status_frame.setObjectName("mainStatusBar")
    main_status_layout=QHBoxLayout(main_status_frame)
    main_status_layout.setContentsMargins(14,8,14,8)
    status_label=QLabel("●  Ready")
    status_label.setObjectName("mainStatusLabel")
    status_label.setWordWrap(True)
    main_status_layout.addWidget(status_label)
    main.addWidget(main_status_frame)

    embed_controls=[
        basic_group,
        author_group,
        media_group,
        footer_group,
        timestamp_group,
        fields_group
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
    sync_external_scrollbar()
    add_missing_tooltips(window)
    load_current_json()
    add_subtle_shadows(window,(content_frame,))

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(create_app())
