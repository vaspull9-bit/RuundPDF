import sys
import fitz
import os
import threading
import pyttsx3
import time


# --- 1. ФУНКЦИЯ ОПРЕДЕЛЕНИЯ ПУТИ К РЕСУРСАМ ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- 2. ОБНОВЛЕННЫЕ ИМПОРТЫ ---
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QPushButton, QFileDialog, QLabel, QHBoxLayout, 
                             QSlider, QGraphicsScene, QGraphicsView, 
                             QGraphicsPixmapItem, QDialog, QTextEdit, 
                             QMessageBox, QToolBar, QFrame, QMenu,
                             QTabWidget, QGroupBox, QRadioButton, QLineEdit,
                             QCheckBox, QInputDialog)
from PyQt6.QtGui import (QPixmap, QImage, QIcon, QAction, QPainter, 
                         QPageLayout, QPageSize, QDropEvent, QDragEnterEvent, QFont)
from PyQt6.QtCore import Qt, QSize, QFileInfo, QSettings, QTimer
from PyQt6.QtPrintSupport import QPrintDialog


def create_text_icon(text, size=32):
    """Создает QIcon из символа Unicode."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setPen(Qt.GlobalColor.black)
    painter.setFont(QFont("Segoe UI Symbol", size // 2)) # Используем системный шрифт Windows
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()
    return QIcon(pixmap)



# --- 3. КЛАСС О ПРОГРАММЕ (v1.2.0) ---
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе RuundPDF")
        self.setGeometry(100, 100, 400, 250)
        layout = QVBoxLayout()
        label_icon = QLabel(self)
        
        icon_path = resource_path("icon.png")
        pixmap = QPixmap(icon_path).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio)
        label_icon.setPixmap(pixmap)
        label_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label_icon)
        info_text = QTextEdit(self)
        info_text.setReadOnly(True)
        info_text.setHtml("""
            <p align='center'><strong>Программа RuundPDF v1.2.0</strong></p>
            <p align='center'>Права принадлежат DeeR Tuund (c) 2025 г.</p>
            <p>Описание возможностей:</p>
            <ul>
                <li>Чтение PDF файлов</li>
                <li>Выделение и копирование текста</li>
                <li>Озвучивание текста (полноценный плеер)</li>
                <li>Режим Зум</li>
                <li>Поворот страницы</li>
                <li>Печать файла</li>
                <li>Сохранение копии файла</li>
                <li>Листание страниц колесом мыши/клавиатурой</li>
                <li>Drag-and-Drop загрузка</li>
            </ul>
        """)
        layout.addWidget(info_text)
        btn_ok = QPushButton("ОК")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)
        self.setLayout(layout)

# --- 4. КЛАСС НАСТРОЕК ПЛЕЕРА (Модальный диалог, вызывается из плеера) ---
class TTSConfigDialog(QDialog):
    def __init__(self, parent=None, player=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки плеера")
        self.player = player
        self.setGeometry(250, 250, 300, 250)
        self.initUI()
        self.load_settings()

    def initUI(self):
        main_layout = QVBoxLayout()
        
        read_range_group = QGroupBox("Диапазон чтения")
        read_range_layout = QVBoxLayout()
        self.radio_current = QRadioButton("Читать с текущей страницы")
        self.radio_start = QRadioButton("Читать сначала до конца")
        self.radio_specific = QRadioButton("Читать со страницы номер:")
        self.page_num_edit = QLineEdit(str(self.player.current_read_page + 1))
        page_num_layout = QHBoxLayout()
        page_num_layout.addWidget(self.radio_specific)
        page_num_layout.addWidget(self.page_num_edit)
        read_range_layout.addWidget(self.radio_current)
        read_range_layout.addWidget(self.radio_start)
        read_range_layout.addLayout(page_num_layout)
        read_range_group.setLayout(read_range_layout)
        main_layout.addWidget(read_range_group)

        voice_group = QGroupBox("Настройки голоса")
        voice_layout = QHBoxLayout()
        self.radio_voice_m = QRadioButton("Мужской")
        self.radio_voice_f = QRadioButton("Женский")
        voice_layout.addWidget(self.radio_voice_m)
        voice_layout.addWidget(self.radio_voice_f)
        voice_group.setLayout(voice_layout)
        main_layout.addWidget(voice_group)
        
        btn_ok = QPushButton("Применить и Закрыть")
        btn_ok.clicked.connect(self.apply_settings)
        main_layout.addWidget(btn_ok)
        
        self.setLayout(main_layout)
        self.radio_current.setChecked(True)

    def load_settings(self):
        pass

    def apply_settings(self):
        self.player.settings.setValue("tts_voice_m", self.radio_voice_m.isChecked())
        self.player.settings.setValue("tts_voice_f", self.radio_voice_f.isChecked())
        
        if self.radio_start.isChecked():
            self.player.set_read_mode('start')
        elif self.radio_specific.isChecked():
            try:
                page = int(self.page_num_edit.text()) - 1
                self.player.set_read_mode('specific', page)
            except ValueError:
                QMessageBox.warning(self, "Ошибка ввода", "Неверный номер страницы.")
        else:
            self.player.set_read_mode('current')
            
        self.accept()


# --- 5. КЛАСС ПЛЕЕРА ОЗВУЧКИ (Немодальный тулбар) ---

class TTSPlayerWidget(QWidget):
    def __init__(self, parent=None, text_provider=None, document_info=None):
        super().__init__(parent)
        self.text_provider = text_provider
        self.document_info = document_info
        self.tts_engine = pyttsx3.init()
        self.is_playing = False
        self.is_paused = False
        self.total_pages = document_info['total_pages']
        self.current_read_page = document_info['current_page']
        self.settings = QSettings("DeeRTuund", "RuundPDF")
        self.read_mode = 'current'
        self.specific_page = 0
        self.initUI()
        self.load_settings()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.Tool) 
        self.setWindowTitle("Плеер RuundPDF")

    def initUI(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.btn_first = QPushButton("⏮️")
        self.btn_prev_page = QPushButton("⬅️")
        self.btn_play_pause = QPushButton("▶️")
        self.btn_next_page = QPushButton("➡️")
        self.btn_last = QPushButton("⏭️")
        self.btn_stop_close = QPushButton("⏹️")
        self.btn_config = QPushButton("⚙️")
        
        self.btn_first.clicked.connect(lambda: self.navigate_page(0, absolute=True))
        self.btn_prev_page.clicked.connect(lambda: self.navigate_page(-1))
        self.btn_play_pause.clicked.connect(self.play_pause_resume)
        self.btn_next_page.clicked.connect(lambda: self.navigate_page(1))
        self.btn_last.clicked.connect(lambda: self.navigate_page(self.total_pages - 1, absolute=True))
        self.btn_stop_close.clicked.connect(self.stop_and_close)
        self.btn_config.clicked.connect(self.show_config)

        layout.addWidget(self.btn_first)
        layout.addWidget(self.btn_prev_page)
        layout.addWidget(self.btn_play_pause)
        layout.addWidget(self.btn_next_page)
        layout.addWidget(self.btn_last)
        layout.addWidget(self.btn_config)
        layout.addWidget(self.btn_stop_close)

        self.setLayout(layout)
        self.update_player_buttons()

    def update_player_buttons(self):
        if self.is_playing and not self.is_paused:
            self.btn_play_pause.setText("⏸️")
        else:
            self.btn_play_pause.setText("▶️")

    def load_settings(self):
        pass

    def save_settings(self):
        pass

    def get_voice_id(self):
        voices = self.tts_engine.getProperty('voices')
        use_male = self.settings.value("tts_voice_m", True, type=bool)
        use_female = self.settings.value("tts_voice_f", False, type=bool)

        for voice in voices:
            is_male = 'male' in voice.name.lower()
            is_female = 'female' in voice.name.lower()
            if use_male and is_male: return voice.id
            if use_female and is_female: return voice.id
        return voices[0].id if voices else None # Исправлено здесь

    def set_read_mode(self, mode, page=0):
        self.read_mode = mode
        self.specific_page = page

    def navigate_page(self, delta, absolute=False):
        if absolute:
            new_page = delta
        else:
            new_page = self.current_read_page + delta

        if 0 <= new_page < self.total_pages:
            self.current_read_page = new_page
            if self.is_playing:
                self.tts_engine.stop()

    def play_pause_resume(self):
        voice_id = self.get_voice_id()
        if voice_id:
            self.tts_engine.setProperty('voice', voice_id)

        if not self.is_playing or self.is_paused:
            if not self.is_playing: 
                if self.read_mode == 'start':
                    self.current_read_page = 0
                elif self.read_mode == 'specific':
                    self.current_read_page = self.specific_page

                self.is_playing = True
                threading.Thread(target=self._run_tts_loop).start()
            elif self.is_paused:
                self.tts_engine.resume()
                self.is_paused = False

        else:
            self.tts_engine.pause()
            self.is_paused = True
        
        self.update_player_buttons()

    def pause_speech(self):
        pass

    def stop_speech(self):
        if self.is_playing:
            self.tts_engine.stop()
            self.is_playing = False
            self.is_paused = False
            self.update_player_buttons()

    def stop_and_close(self):
        self.stop_speech()
        self.close()

    def _run_tts_loop(self):
        try:
            for i in range(self.current_read_page, self.total_pages):
                if not self.is_playing: break
                text = self.text_provider(i)
                if text:
                    self.tts_engine.say(text)
                    self.tts_engine.runAndWait()
                    self.current_read_page = i + 1 
            self.stop_speech()
        except Exception as e:
            print(f"Ошибка TTS loop: {e}")
            self.stop_speech()

    def closeEvent(self, event):
        self.stop_speech()
        event.accept()

    def show_config(self):
        config_dialog = TTSConfigDialog(self, self)
        config_dialog.exec()


# --- 6. ОСНОВНОЙ КЛАСС ПРИЛОЖЕНИЯ (PDFViewerApp) ---

class PDFViewerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RuundPDF - Величайший PDF Reader v1.2.0")
        self.setGeometry(100, 100, 1200, 800)
        self.setWindowIcon(QIcon(resource_path('icon.png')))
        self.setAcceptDrops(True)

        self.document = None
        self.file_path = None
        self.current_page_num = 0
        self.zoom_factor = 1.0
        self.rotation_angle = 0
        self.tts_engine = pyttsx3.init()
        self.bookmarks = {}
        self.tts_player_widget = None

        # --- КОРРЕКТНЫЙ ПОРЯДОК ВЫЗОВОВ ---
        self.initUI()         # 1. Сначала инициализируем ВСЕ элементы интерфейса
        self.apply_styles()   # 2. Применяем стили
        self.disable_controls() # 3. Теперь безопасно отключаем элементы

    def initUI(self):
        # --- Панель инструментов (теперь с иконками и рабочим порядком) ---
        toolbar = QToolBar("Основная панель")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        # Устанавливаем режим, чтобы отображались только иконки (или иконки+текст)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly) 

        self.action_open = QAction(QIcon(resource_path('icon.png')), "Открыть PDF", self)
        self.action_open.triggered.connect(self.open_file)
        toolbar.addAction(self.action_open)

        self.action_save = QAction(create_text_icon("💾"), "Сохранить", self)
        self.action_save.triggered.connect(self.save_file)
        toolbar.addAction(self.action_save)

        self.action_print = QAction(create_text_icon("🖨️"), "Печать", self)
        self.action_print.triggered.connect(self.print_file)
        toolbar.addAction(self.action_print)

        toolbar.addSeparator()
        
        self.action_prev = QAction(create_text_icon("⬅️"), "Пред. стр.", self)
        self.action_prev.triggered.connect(self.prev_page)
        toolbar.addAction(self.action_prev)
        self.page_label = QLabel("Стр: --/--")
        toolbar.addWidget(self.page_label)
        self.action_next = QAction(create_text_icon("➡️"), "След. стр.", self)
        self.action_next.triggered.connect(self.next_page)
        toolbar.addAction(self.action_next)
        
        toolbar.addSeparator()
        
        # Поворот с разными иконками
        self.action_rotate_left = QAction(create_text_icon("↺"), "Повернуть влево 90°", self) 
        self.action_rotate_left.triggered.connect(lambda: self.rotate_page(-90))
        toolbar.addAction(self.action_rotate_left)

        self.action_rotate_right = QAction(create_text_icon("↻"), "Повернуть вправо 90°", self) 
        self.action_rotate_right.triggered.connect(lambda: self.rotate_page(90))
        toolbar.addAction(self.action_rotate_right)

        # Кнопка плеера озвучки
        self.action_speak = QAction(create_text_icon("📖"), "Открыть плеер озвучки", self)
        self.action_speak.triggered.connect(self.show_tts_player)
        toolbar.addAction(self.action_speak)
        
        toolbar.addSeparator()

        self.action_about = QAction("О программе", self)
        self.action_about.triggered.connect(self.show_about_dialog)
        toolbar.addAction(self.action_about)

        # --- ГЛАВНОЕ МЕНЮ (MENUBAR) ДЛЯ ЗАКЛАДОК (как и было) ---
        menubar = self.menuBar()
        bookmarks_menu = menubar.addMenu('&Закладки')
        self.action_add_bookmark = QAction("Добавить закладку", self)
        self.action_add_bookmark.triggered.connect(self.add_bookmark)
        bookmarks_menu.addAction(self.action_add_bookmark)
        bookmarks_menu.addSeparator()
        self.bookmarks_submenu = QMenu(self)
        bookmarks_menu.addMenu(self.bookmarks_submenu)


        # --- Основной макет и Зум (остаются без изменений) ---
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Зум:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(50)
        self.zoom_slider.setMaximum(300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.change_zoom)
        self.zoom_value_label = QLabel("100%")
        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addWidget(self.zoom_value_label)
        main_layout.addLayout(zoom_layout)
        self.scene = QGraphicsScene(self)
        self.view = PDFGraphicsView(self.scene, self)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.show_context_menu)
        main_layout.addWidget(self.view)
        self.current_pixmap_item = None
    
    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f0f0; }
            QPushButton {
                background-color: #e0e0e0; color: black; padding: 5px 10px;
                border: 1px solid #ccc; border-radius: 4px;
            }
            QPushButton:hover { background-color: #d0d0d0; }
            QToolBar {
                background-color: #e0e0e0; color: black; padding: 5px;
                border-bottom: 1px solid #ccc;
            }
            QLabel { color: black; }
            QGraphicsView { background-color: #fff; border: 1px solid #ccc; }
        """)

    def disable_controls(self):
        controls = [self.action_prev, self.action_next, self.action_rotate_left, 
                    self.action_rotate_right, self.action_speak, self.zoom_slider,
                    self.action_save, self.action_print, self.action_add_bookmark]
        for control in controls:
            control.setEnabled(False)

    def enable_controls(self):
        controls = [self.action_prev, self.action_next, self.action_rotate_left, 
                    self.action_rotate_right, self.action_speak, self.zoom_slider,
                    self.action_save, self.action_print, self.action_add_bookmark]
        for control in controls:
            control.setEnabled(True)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith('.pdf'):
                self.open_file(file_path)
                return

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_PageDown or event.key() == Qt.Key.Key_Down:
            self.next_page()
            event.accept()
        elif event.key() == Qt.Key.Key_PageUp or event.key() == Qt.Key.Key_Up:
            self.prev_page()
            event.accept()
        else:
            super().keyPressEvent(event)

    def open_file(self, file_path=None):
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(self, "Открыть PDF файл", "", "PDF Files (*.pdf)")
        if file_path:
            try:
                self.document = fitz.open(file_path)
                self.file_path = file_path
                self.current_page_num = 0
                self.rotation_angle = 0
                self.zoom_slider.setValue(100)
                self.render_page()
                self.enable_controls()
                self.setWindowTitle(f"RuundPDF - {QFileInfo(file_path).fileName()}")
                self.update_bookmarks_menu()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка загрузки", f"Не удалось открыть файл. Ошибка: {e}")

    def render_page(self):
        if not self.document:
            return
        page = self.document.load_page(self.current_page_num)
        matrix = fitz.Matrix(self.zoom_factor, self.zoom_factor) * fitz.Matrix(self.rotation_angle)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        qpixmap = QPixmap.fromImage(qimage)
        self.scene.clear()
        self.current_pixmap_item = QGraphicsPixmapItem(qpixmap)
        self.scene.addItem(self.current_pixmap_item)
        self.view.setSceneRect(self.current_pixmap_item.boundingRect())
        self.page_label.setText(f"Страница: {self.current_page_num + 1}/{self.document.page_count}")

    def next_page(self):
        if self.document and self.current_page_num < self.document.page_count - 1:
            self.current_page_num += 1
            self.render_page()

    def prev_page(self):
        if self.document and self.current_page_num > 0:
            self.current_page_num -= 1
            self.render_page()
    
    def goto_page(self, page_num):
        if self.document and 0 <= page_num < self.document.page_count:
            self.current_page_num = page_num
            self.render_page()

    def change_zoom(self, value):
        self.zoom_factor = value / 100.0
        self.zoom_value_label.setText(f"{value}%")
        self.render_page()

    def rotate_page(self, angle_delta):
        self.rotation_angle = (self.rotation_angle + angle_delta) % 360
        self.render_page()
    
    def get_text_for_page(self, page_num):
        if self.document and 0 <= page_num < self.document.page_count:
            page = self.document.load_page(page_num)
            return page.get_text()
        return ""

    def show_tts_player(self):
        if not self.document:
            QMessageBox.warning(self, "Плеер", "Сначала откройте PDF-файл.")
            return
        
        if self.tts_player_widget and self.tts_player_widget.isVisible():
            self.tts_player_widget.raise_()
            self.tts_player_widget.activateWindow()
            return

        doc_info = {
            'total_pages': self.document.page_count,
            'current_page': self.current_page_num
        }
        self.tts_player_widget = TTSPlayerWidget(self, self.get_text_for_page, doc_info)
        self.tts_player_widget.show()

    def save_file(self):
        if self.document and self.file_path:
            self.document.save(self.file_path, garbage=4, deflate=True) 
            QMessageBox.information(self, "Успех", "Файл успешно сохранен.")
        elif self.document:
             self.save_file_as()

    def save_file_as(self, default_path=""):
        if not self.document: return
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить PDF как...", default_path, "PDF Files (*.pdf)")
        if file_path:
            try:
                self.document.save(file_path, garbage=4, deflate=True) 
                self.file_path = file_path
                QMessageBox.information(self, "Успех", f"Файл успешно сохранен как {QFileInfo(file_path).fileName()}.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка сохранения", f"Не удалось сохранить файл. Ошибка: {e}")

    def print_file(self):
        """Функция: Печать на принтере (QPainter метод, исправленный)."""
        if not self.document:
            return

        printer = QPainter()
        printDialog = QPrintDialog()
        
        # Используем QDialog.DialogCode.Accepted
        if printDialog.exec() == QDialog.DialogCode.Accepted:
            printer.begin(printDialog.printer()) 
            
            for i in range(self.document.page_count):
                page = self.document.load_page(i)
                zoom_factor_print = 4
                matrix = fitz.Matrix(zoom_factor_print, zoom_factor_print)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)

                if i > 0:
                    printer.newPage()
                
                area = printer.viewport() 
                size = qimage.size() 
                
                if size.width() > size.height():
                    scale = area.width() / size.width()
                else:
                    scale = area.height() / size.height()
                
                # ИСПРАВЛЕНИЕ ОШИБКИ: Приводим float к int
                width = int(scale * size.width())
                height = int(scale * size.height())
                
                # Рисуем изображение, приводя координаты и размеры к int
                printer.drawImage(
                    int((area.width() - width) / 2), 
                    int((area.height() - height) / 2), 
                    qimage.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )

            printer.end()
            QMessageBox.information(self, "Печать", "Документ отправлен на печать.")

    def add_bookmark(self):
        if not self.document: return
        page_num = self.current_page_num
        name, ok = QInputDialog.getText(self, 'Новая закладка', 'Введите название закладки:')
        if ok and name:
            self.bookmarks[page_num] = name
            self.update_bookmarks_menu()

    def update_bookmarks_menu(self):
        self.bookmarks_submenu.clear()
        for page_num, name in sorted(self.bookmarks.items()):
            action = QAction(f"Стр. {page_num + 1}: {name}", self)
            action.triggered.connect(lambda checked, pn=page_num: self.goto_page(pn))
            self.bookmarks_submenu.addAction(action)

    def show_context_menu(self, pos):
        context_menu = QMenu(self)
        action_copy_all = QAction("Копировать весь текст страницы", self)
        action_copy_all.triggered.connect(self.copy_all_text)
        context_menu.addAction(action_copy_all)

        action_speak_all = QAction("Озвучить весь текст страницы (текст)", self)
        action_speak_all.triggered.connect(self.show_tts_player) 
        context_menu.addAction(action_speak_all)
        context_menu.exec(self.view.mapToGlobal(pos))

    def copy_all_text(self):
        text = self.get_text_for_page(self.current_page_num)
        if text:
            QApplication.clipboard().setText(text)

    def show_about_dialog(self):
        about_dialog = AboutDialog(self)
        about_dialog.exec()

# --- 7. КАСТОМНЫЙ QGraphicsView ДЛЯ КОЛЕСА МЫШИ ---

class PDFGraphicsView(QGraphicsView):
    def __init__(self, scene, main_app):
        super().__init__(scene)
        self.main_app = main_app
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setAcceptDrops(True)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.main_app.zoom_slider.setValue(self.main_app.zoom_slider.value() + 10)
            elif delta < 0:
                self.main_app.zoom_slider.setValue(self.main_app.zoom_slider.value() - 10)
        else:
            delta = event.angleDelta().y()
            if delta > 0:
                self.main_app.prev_page()
            elif delta < 0:
                self.main_app.next_page()
            event.accept()

# --- 8. БЛОК ЗАПУСКА ---

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = PDFViewerApp()
    ex.show()
    sys.exit(app.exec())