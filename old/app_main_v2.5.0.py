"""
RuundPDF v2.5.0 - Полностью переписанный и исправленный PDF Reader
Author: DeeR Tuund (c) 2025
"""

import sys
import fitz
import os
import threading
import pyttsx3
import time
import winreg
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QFileDialog,
    QLabel, QHBoxLayout, QSlider, QGraphicsScene, QGraphicsView, QGraphicsPixmapItem,
    QDialog, QTextEdit, QMessageBox, QToolBar, QFrame, QMenu, QTabWidget,
    QGroupBox, QRadioButton, QLineEdit, QCheckBox, QInputDialog, QListWidget,
    QProgressBar
)
from PyQt6.QtGui import (
    QPixmap, QImage, QIcon, QAction, QPainter, QPageLayout, QPageSize,
    QDropEvent, QDragEnterEvent, QFont, QBrush, QColor, QCursor, QTransform
)
from PyQt6.QtCore import Qt, QSize, QFileInfo, QSettings, QTimer, QRectF, QPointF, QRect
from PyQt6.QtPrintSupport import QPrintDialog

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================
def resource_path(relative_path):
    """Получает абсолютный путь к ресурсу."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def create_text_icon(text, size=32):
    """Создает QIcon из символа Unicode."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setPen(Qt.GlobalColor.black)
    painter.setFont(QFont("Segoe UI Symbol", size // 2))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()
    return QIcon(pixmap)

def register_file_association():
    """Регистрирует программу как ассоциацию для PDF файлов."""
    try:
        if getattr(sys, 'frozen', False):
            app_path = sys.executable
        else:
            app_path = sys.argv[0]
        
        app_path = f'"{sys.executable}" "{app_path}"'
        app_name = "RuundPDF"
        file_type = "RuundPDF.Document"
        
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\.pdf") as key:
            winreg.SetValue(key, "", winreg.REG_SZ, file_type)
        
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{file_type}") as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "PDF Document")
        
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{file_type}\\DefaultIcon") as key:
            winreg.SetValue(key, "", winreg.REG_SZ, f"{app_path},0")
        
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{file_type}\\shell\\open\\command") as key:
            winreg.SetValue(key, "", winreg.REG_SZ, f'"{app_path}" "%1"')
        
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\{app_name}") as key:
            winreg.SetValueEx(key, "InstallPath", 0, winreg.REG_SZ, os.path.dirname(app_path))
        
        return True
    except Exception as e:
        print(f"Ошибка регистрации: {e}")
        return False

# ============================================================================
# КЛАСС О ПРОГРАММЕ
# ============================================================================
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе RuundPDF")
        self.setGeometry(100, 100, 400, 250)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Иконка
        label_icon = QLabel(self)
        def get_icon_path():
            if getattr(sys, 'frozen', False):
                base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
            else:
                base_path = os.path.abspath(".")
            return os.path.join(base_path, 'icon.png')
        
        icon_path = get_icon_path()
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio)
            label_icon.setPixmap(pixmap)
            label_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label_icon)
        
        # Информация
        info_text = QTextEdit(self)
        info_text.setReadOnly(True)
        info_text.setHtml("""
            <p align='center'><strong>RuundPDF v2.5.0</strong></p>
            <p align='center'>© DeeR Tuund 2025</p>
            <p>Полнофункциональный PDF ридер с озвучкой текста</p>
        """)
        layout.addWidget(info_text)
        
        # Кнопка
        btn_ok = QPushButton("ОК")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)
        
        self.setLayout(layout)

# ============================================================================
# КЛАСС НАСТРОЕК ПЛЕЕРА (УПРОЩЕННЫЙ)
# ============================================================================
class TTSConfigDialog(QDialog):
    def __init__(self, parent=None, player=None):
        super().__init__(parent)
        self.player = player
        self.setWindowTitle("Настройки озвучки")
        self.setGeometry(250, 250, 300, 200)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Режим чтения
        group_mode = QGroupBox("Режим чтения")
        layout_mode = QVBoxLayout()
        
        self.radio_current = QRadioButton("С текущей страницы")
        self.radio_all = QRadioButton("Весь документ")
        self.radio_one = QRadioButton("Только текущая страница")
        
        layout_mode.addWidget(self.radio_current)
        layout_mode.addWidget(self.radio_all)
        layout_mode.addWidget(self.radio_one)
        group_mode.setLayout(layout_mode)
        layout.addWidget(group_mode)
        
        # Голос
        group_voice = QGroupBox("Голос")
        layout_voice = QVBoxLayout()
        
        self.radio_male = QRadioButton("Мужской")
        self.radio_female = QRadioButton("Женский")
        
        layout_voice.addWidget(self.radio_male)
        layout_voice.addWidget(self.radio_female)
        group_voice.setLayout(layout_voice)
        layout.addWidget(group_voice)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

# ============================================================================
# НОВЫЙ КЛАСС ПЛЕЕРА (ПЕРЕПИСАННЫЙ)
# ============================================================================
class TTSPlayerWidget(QWidget):
    """Переписанный плеер с правильной работой"""
    def __init__(self, parent=None, text_provider=None, doc_info=None):
        super().__init__(parent)
        self.parent_app = parent
        self.text_provider = text_provider
        self.total_pages = doc_info['total_pages']
        self.current_page = doc_info['current_page']
        
        # Состояние плеера
        self.is_playing = False
        self.is_paused = False
        self.stop_requested = False
        
        # TTS движок
        self.tts_engine = pyttsx3.init()
        self.voice_id = None
        
        # Поток для воспроизведения
        self.playback_thread = None
        
        self.setup_ui()
        self.setWindowTitle("Плеер озвучки")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.Tool)
        self.load_voice_settings()
    
    def setup_ui(self):
        """Настройка интерфейса плеера"""
        main_layout = QVBoxLayout()
        
        # Панель управления
        control_layout = QHBoxLayout()
        
        self.btn_play = QPushButton("▶")
        self.btn_pause = QPushButton("⏸")
        self.btn_stop = QPushButton("⏹")
        self.btn_config = QPushButton("⚙")
        
        self.btn_play.setToolTip("Начать воспроизведение")
        self.btn_pause.setToolTip("Пауза")
        self.btn_stop.setToolTip("Остановить")
        self.btn_config.setToolTip("Настройки")
        
        self.btn_play.clicked.connect(self.start_playback)
        self.btn_pause.clicked.connect(self.pause_playback)
        self.btn_stop.clicked.connect(self.stop_playback)
        self.btn_config.clicked.connect(self.show_config)
        
        control_layout.addWidget(self.btn_play)
        control_layout.addWidget(self.btn_pause)
        control_layout.addWidget(self.btn_stop)
        control_layout.addWidget(self.btn_config)
        
        # Информация о странице
        self.page_label = QLabel(f"Страница: {self.current_page + 1}/{self.total_pages}")
        control_layout.addWidget(self.page_label)
        
        main_layout.addLayout(control_layout)
        
        # Прогресс
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.total_pages)
        self.progress_bar.setValue(self.current_page)
        main_layout.addWidget(self.progress_bar)
        
        # Статус
        self.status_label = QLabel("Готово")
        main_layout.addWidget(self.status_label)
        
        self.setLayout(main_layout)
        self.update_buttons()
    
    def load_voice_settings(self):
        """Загружает настройки голоса"""
        settings = QSettings("DeeRTuund", "RuundPDF")
        use_female = settings.value("tts_use_female", False, type=bool)
        
        voices = self.tts_engine.getProperty('voices')
        
        if use_female:
            # Ищем женский голос
            for voice in voices:
                if 'female' in voice.name.lower() or 'женск' in voice.name.lower():
                    self.tts_engine.setProperty('voice', voice.id)
                    self.voice_id = voice.id
                    return
        else:
            # Ищем мужской голос
            for voice in voices:
                if 'male' in voice.name.lower() or 'мужск' in voice.name.lower():
                    self.tts_engine.setProperty('voice', voice.id)
                    self.voice_id = voice.id
                    return
        
        # По умолчанию первый доступный голос
        if voices:
            self.tts_engine.setProperty('voice', voices[0].id)
            self.voice_id = voices[0].id
    
    def update_buttons(self):
        """Обновляет состояние кнопок"""
        self.btn_play.setEnabled(not self.is_playing or self.is_paused)
        self.btn_pause.setEnabled(self.is_playing and not self.is_paused)
        self.btn_stop.setEnabled(self.is_playing)
        
        if self.is_playing:
            self.status_label.setText("Воспроизведение...")
        elif self.is_paused:
            self.status_label.setText("Пауза")
        else:
            self.status_label.setText("Готово")
    
    def start_playback(self):
        """Начинает воспроизведение всего документа"""
        if self.is_playing:
            return
        
        self.is_playing = True
        self.is_paused = False
        self.stop_requested = False
        
        # Запускаем поток воспроизведения
        self.playback_thread = threading.Thread(target=self.play_document)
        self.playback_thread.daemon = True
        self.playback_thread.start()
        
        self.update_buttons()
    
    def pause_playback(self):
        """Ставит воспроизведение на паузу"""
        if self.is_playing and not self.is_paused:
            self.is_paused = True
            self.update_buttons()
    
    def stop_playback(self):
        """Останавливает воспроизведение"""
        self.stop_requested = True
        self.is_playing = False
        self.is_paused = False
        
        if self.tts_engine:
            try:
                self.tts_engine.stop()
            except:
                pass
        
        self.update_buttons()
    
    def play_document(self):
        """Основная функция воспроизведения документа"""
        try:
            # Читаем все страницы с текущей до конца
            for page_num in range(self.current_page, self.total_pages):
                if self.stop_requested:
                    break
                
                # Обработка паузы
                while self.is_paused and not self.stop_requested:
                    time.sleep(0.1)
                
                if self.stop_requested:
                    break
                
                # Получаем текст страницы
                text = self.text_provider(page_num)
                if text:
                    # Обновляем UI в основном потоке
                    self.parent_app.app.processEvents()
                    
                    # Обновляем текущую страницу
                    self.current_page = page_num
                    self.page_label.setText(f"Страница: {page_num + 1}/{self.total_pages}")
                    self.progress_bar.setValue(page_num + 1)
                    
                    # Озвучиваем текст
                    self.tts_engine.say(text)
                    self.tts_engine.runAndWait()
                else:
                    break
        
        except Exception as e:
            print(f"Ошибка воспроизведения: {e}")
        
        finally:
            self.is_playing = False
            self.is_paused = False
            self.update_buttons()
    
    def show_config(self):
        """Показывает диалог настроек"""
        dialog = TTSConfigDialog(self, self)
        if dialog.exec():
            # Сохраняем настройки голоса
            settings = QSettings("DeeRTuund", "RuundPDF")
            settings.setValue("tts_use_female", dialog.radio_female.isChecked())
            
            # Применяем настройки
            self.load_voice_settings()
    
    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        self.stop_playback()
        event.accept()

# ============================================================================
# КЛАСС ДЛЯ ПРОСМОТРА PDF
# ============================================================================
class PDFGraphicsView(QGraphicsView):
    def __init__(self, scene, main_app):
        super().__init__(scene)
        self.main_app = main_app
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setAcceptDrops(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMouseTracking(True)
    
    def dragEnterEvent(self, event):
        """Принимаем PDF файлы"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith('.pdf'):
                event.acceptProposedAction()
                self.setStyleSheet("border: 2px dashed blue;")
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet("")
        super().dragLeaveEvent(event)
    
    def dropEvent(self, event):
        """Обрабатываем drop PDF файла"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith('.pdf'):
                self.main_app.open_file(file_path)
                event.acceptProposedAction()
        self.setStyleSheet("")
    
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
    
    def paintEvent(self, event):
        super().paintEvent(event)
        if (self.main_app.is_text_select_mode and 
            self.main_app.selection_rect is not None):
            painter = QPainter(self.viewport())
            painter.setPen(Qt.GlobalColor.blue)
            painter.setBrush(QBrush(QColor(100, 150, 255, 50)))
            painter.drawRect(self.main_app.selection_rect)

# ============================================================================
# ОСНОВНОЙ КЛАСС ПРИЛОЖЕНИЯ
# ============================================================================
class PDFViewerApp(QMainWindow):
    def __init__(self, file_to_open=None):
        super().__init__()
        self.app = QApplication.instance()
        self.setWindowTitle("RuundPDF - PDF Reader")
        self.setGeometry(100, 100, 1200, 800)
        
        # Иконка
        def get_icon_path():
            if getattr(sys, 'frozen', False):
                base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
            else:
                base_path = os.path.abspath(".")
            return os.path.join(base_path, 'icon.png')
        
        self.setWindowIcon(QIcon(get_icon_path()))
        
        # Включаем drag-and-drop
        self.setAcceptDrops(True)
        
        # Инициализация переменных
        self.document = None
        self.file_path = None
        self.current_page_num = 0
        self.zoom_factor = 1.0
        self.rotation_angle = 0
        self.bookmarks = {}
        self.tts_player = None
        self.is_text_select_mode = True
        self.selection_start = None
        self.selection_end = None
        self.selection_rect = None
        self.text_blocks = []
        self.page_pixmap = None
        self.selected_text = ""
        
        self.file_to_open_on_start = file_to_open
        
        self.setup_ui()
        self.apply_styles()
        self.disable_controls()
        self.load_bookmarks()
        self.register_association()
        
        if self.file_to_open_on_start and os.path.exists(self.file_to_open_on_start):
            QTimer.singleShot(100, lambda: self.open_file(self.file_to_open_on_start))
    
    def register_association(self):
        try:
            settings = QSettings("DeeRTuund", "RuundPDF")
            first_run = settings.value("first_run", True, type=bool)
            if first_run:
                if register_file_association():
                    QMessageBox.information(self, "Ассоциация", "Программа зарегистрирована для PDF файлов.")
                settings.setValue("first_run", False)
        except:
            pass
    
    def load_bookmarks(self):
        try:
            settings = QSettings("DeeRTuund", "RuundPDF")
            bookmarks_data = settings.value("bookmarks", "")
            if bookmarks_data:
                for item in bookmarks_data.split(';'):
                    if ':' in item:
                        page_str, name = item.split(':', 1)
                        try:
                            page_num = int(page_str)
                            self.bookmarks[page_num] = name
                        except:
                            continue
        except:
            pass
    
    def save_bookmarks(self):
        try:
            settings = QSettings("DeeRTuund", "RuundPDF")
            bookmarks_data = []
            for page_num, name in self.bookmarks.items():
                bookmarks_data.append(f"{page_num}:{name}")
            settings.setValue("bookmarks", ';'.join(bookmarks_data))
        except:
            pass
    
    def setup_ui(self):
        # Создаем тулбар
        toolbar = QToolBar("Основная панель")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # Кнопки тулбара
        self.action_open = QAction(QIcon(resource_path('icon.png')), "Открыть", self)
        self.action_open.triggered.connect(self.open_file)
        toolbar.addAction(self.action_open)
        
        self.action_save = QAction(create_text_icon("💾"), "Сохранить", self)
        self.action_save.triggered.connect(self.save_file)
        toolbar.addAction(self.action_save)
        
        self.action_print = QAction(create_text_icon("🖨️"), "Печать", self)
        self.action_print.triggered.connect(self.print_file)
        toolbar.addAction(self.action_print)
        
        toolbar.addSeparator()
        
        self.action_prev = QAction(create_text_icon("⬅️"), "Назад", self)
        self.action_prev.triggered.connect(self.prev_page)
        toolbar.addAction(self.action_prev)
        
        self.page_label = QLabel("Страница: --/--")
        toolbar.addWidget(self.page_label)
        
        self.action_next = QAction(create_text_icon("➡️"), "Вперед", self)
        self.action_next.triggered.connect(self.next_page)
        toolbar.addAction(self.action_next)
        
        toolbar.addSeparator()
        
        # НОВАЯ КНОПКА: Перейти на страницу
        self.action_goto = QAction(create_text_icon("🔢"), "Перейти", self)
        self.action_goto.triggered.connect(self.goto_page_dialog)
        toolbar.addAction(self.action_goto)
        
        # НОВАЯ КНОПКА: Поиск текста
        self.action_search = QAction(create_text_icon("🔍"), "Поиск", self)
        self.action_search.triggered.connect(self.search_text_dialog)
        toolbar.addAction(self.action_search)
        
        toolbar.addSeparator()
        
        self.action_rotate_left = QAction(create_text_icon("↺"), "Повернуть влево", self)
        self.action_rotate_left.triggered.connect(self.rotate_left)
        toolbar.addAction(self.action_rotate_left)
        
        self.action_rotate_right = QAction(create_text_icon("↻"), "Повернуть вправо", self)
        self.action_rotate_right.triggered.connect(self.rotate_right)
        toolbar.addAction(self.action_rotate_right)
        
        toolbar.addSeparator()
        
        self.action_speak = QAction(create_text_icon("🔊"), "Озвучить", self)
        self.action_speak.triggered.connect(self.show_tts_player)
        toolbar.addAction(self.action_speak)
        
        self.action_bookmark = QAction(create_text_icon("🔖"), "Закладки", self)
        self.action_bookmark.triggered.connect(self.manage_bookmarks)
        toolbar.addAction(self.action_bookmark)
        
        self.action_toggle_cursor = QAction(create_text_icon("👆"), "Режим курсора", self)
        self.action_toggle_cursor.triggered.connect(self.toggle_cursor_mode)
        toolbar.addAction(self.action_toggle_cursor)
        
        self.action_copy_text = QAction(create_text_icon("📋"), "Копировать", self)
        self.action_copy_text.triggered.connect(self.copy_selected_text_to_clipboard)
        self.action_copy_text.setEnabled(False)
        toolbar.addAction(self.action_copy_text)
        
        toolbar.addSeparator()
        
        self.action_about = QAction("О программе", self)
        self.action_about.triggered.connect(self.show_about_dialog)
        toolbar.addAction(self.action_about)
        
        # Меню закладок
        menubar = self.menuBar()
        bookmarks_menu = menubar.addMenu('&Закладки')
        
        self.action_add_bookmark = QAction("Добавить закладку", self)
        self.action_add_bookmark.triggered.connect(self.add_bookmark)
        bookmarks_menu.addAction(self.action_add_bookmark)
        
        self.bookmarks_submenu = QMenu("Быстрый переход", self)
        bookmarks_menu.addMenu(self.bookmarks_submenu)
        
        self.action_manage_bookmarks = QAction("Управление закладками...", self)
        self.action_manage_bookmarks.triggered.connect(self.manage_bookmarks)
        bookmarks_menu.addAction(self.action_manage_bookmarks)
        
        # Основной виджет
        central_widget = QWidget()
        central_widget.setAcceptDrops(True)
        
        # Устанавливаем обработчики drag-and-drop для центрального виджета
        central_widget.dragEnterEvent = self.dragEnterEvent
        central_widget.dropEvent = self.dropEvent
        
        main_layout = QVBoxLayout(central_widget)
        self.setCentralWidget(central_widget)
        
        # Панель зума
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Масштаб:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(50)
        self.zoom_slider.setMaximum(300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.change_zoom)
        self.zoom_value_label = QLabel("100%")
        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addWidget(self.zoom_value_label)
        main_layout.addLayout(zoom_layout)
        
        # Поле просмотра PDF
        self.scene = QGraphicsScene(self)
        self.view = PDFGraphicsView(self.scene, self)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.show_context_menu)
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.view.setCursor(Qt.CursorShape.IBeamCursor)
        
        # Переопределяем обработчики мыши
        self.view.mousePressEvent = self.view_mouse_press_event
        self.view.mouseMoveEvent = self.view_mouse_move_event
        self.view.mouseReleaseEvent = self.view_mouse_release_event
        
        main_layout.addWidget(self.view)
        self.current_pixmap_item = None
        
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Готово. Перетащите PDF файл в любое место окна.")
    
    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f0f0; }
            QPushButton {
                background-color: #e0e0e0; 
                border: 1px solid #ccc; 
                border-radius: 4px;
                padding: 5px 10px;
            }
            QPushButton:hover { background-color: #d0d0d0; }
            QToolBar { background-color: #e0e0e0; border-bottom: 1px solid #ccc; }
            QLabel { color: black; }
            QGraphicsView { background-color: #fff; border: 1px solid #ccc; }
        """)
    
    def disable_controls(self):
        controls = [
            self.action_prev, self.action_next, self.action_rotate_left,
            self.action_rotate_right, self.action_speak, self.zoom_slider,
            self.action_save, self.action_print, self.action_add_bookmark,
            self.action_bookmark, self.action_toggle_cursor, self.action_goto,
            self.action_search
        ]
        for control in controls:
            control.setEnabled(False)
    
    def enable_controls(self):
        controls = [
            self.action_prev, self.action_next, self.action_rotate_left,
            self.action_rotate_right, self.action_speak, self.zoom_slider,
            self.action_save, self.action_print, self.action_add_bookmark,
            self.action_bookmark, self.action_toggle_cursor, self.action_goto,
            self.action_search
        ]
        for control in controls:
            control.setEnabled(True)
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith('.pdf'):
                event.acceptProposedAction()
    
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith('.pdf'):
                self.open_file(file_path)
                event.acceptProposedAction()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_PageDown:
            self.next_page()
            event.accept()
        elif event.key() == Qt.Key.Key_PageUp:
            self.prev_page()
            event.accept()
        elif event.key() == Qt.Key.Key_C and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.copy_selected_text_to_clipboard()
            event.accept()
        else:
            super().keyPressEvent(event)
    
    def goto_page_dialog(self):
        """Диалог перехода на страницу"""
        if not self.document:
            return
        
        page, ok = QInputDialog.getInt(
            self, "Перейти на страницу", 
            f"Введите номер страницы (1-{self.document.page_count}):",
            self.current_page_num + 1, 1, self.document.page_count
        )
        
        if ok:
            self.current_page_num = page - 1
            self.render_page()
    
    def search_text_dialog(self):
        """Диалог поиска текста"""
        if not self.document:
            return
        
        text, ok = QInputDialog.getText(self, "Поиск текста", "Введите текст для поиска:")
        
        if ok and text:
            self.search_text(text)
    
    def search_text(self, search_text):
        """Поиск текста в документе"""
        if not self.document or not search_text:
            return
        
        found = False
        start_page = self.current_page_num
        
        # Ищем с текущей страницы до конца
        for page_num in range(start_page, self.document.page_count):
            page = self.document.load_page(page_num)
            page_text = page.get_text()
            
            if search_text.lower() in page_text.lower():
                self.current_page_num = page_num
                self.render_page()
                self.status_bar.showMessage(f"Текст найден на странице {page_num + 1}")
                found = True
                break
        
        if not found:
            # Ищем с начала до текущей страницы
            for page_num in range(0, start_page):
                page = self.document.load_page(page_num)
                page_text = page.get_text()
                
                if search_text.lower() in page_text.lower():
                    self.current_page_num = page_num
                    self.render_page()
                    self.status_bar.showMessage(f"Текст найден на странице {page_num + 1}")
                    found = True
                    break
        
        if not found:
            self.status_bar.showMessage("Текст не найден в документе")
    
    def open_file(self, file_path=None):
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(self, "Открыть PDF", "", "PDF Files (*.pdf)")
        
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
                self.status_bar.showMessage(f"Загружен: {QFileInfo(file_path).fileName()}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл: {e}")
    
    def render_page(self):
        if not self.document:
            return
        
        page = self.document.load_page(self.current_page_num)
        matrix = fitz.Matrix(self.zoom_factor, self.zoom_factor) * fitz.Matrix(self.rotation_angle)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        
        qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        self.page_pixmap = QPixmap.fromImage(qimage)
        
        self.scene.clear()
        self.current_pixmap_item = QGraphicsPixmapItem(self.page_pixmap)
        self.scene.addItem(self.current_pixmap_item)
        self.view.setSceneRect(self.current_pixmap_item.boundingRect())
        
        if self.document:
            self.page_label.setText(f"Страница: {self.current_page_num + 1}/{self.document.page_count}")
        
        self.text_blocks = self.extract_text_with_rectangles(page)
        self.clear_selection()
    
    def extract_text_with_rectangles(self, page):
        text_blocks = []
        try:
            text_dict = page.get_text("dict")
            for block in text_dict.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"]
                            if not text.strip():
                                continue
                            bbox = span["bbox"]
                            scaled_bbox = [
                                bbox[0] * self.zoom_factor,
                                bbox[1] * self.zoom_factor,
                                bbox[2] * self.zoom_factor,
                                bbox[3] * self.zoom_factor
                            ]
                            rect = QRectF(
                                scaled_bbox[0], 
                                scaled_bbox[1], 
                                scaled_bbox[2] - scaled_bbox[0], 
                                scaled_bbox[3] - scaled_bbox[1]
                            )
                            text_blocks.append({'text': text, 'rect': rect})
        except:
            pass
        return text_blocks
    
    def get_text_in_rectangle(self, selection_rect):
        if not self.text_blocks or not selection_rect:
            return ""
        
        selected_text_parts = []
        rect_int = QRect(
            int(selection_rect.x()),
            int(selection_rect.y()),
            int(selection_rect.width()),
            int(selection_rect.height())
        )
        
        top_left_scene = self.view.mapToScene(rect_int.topLeft())
        bottom_right_scene = self.view.mapToScene(rect_int.bottomRight())
        
        scene_rect = QRectF(
            min(top_left_scene.x(), bottom_right_scene.x()),
            min(top_left_scene.y(), bottom_right_scene.y()),
            abs(bottom_right_scene.x() - top_left_scene.x()),
            abs(bottom_right_scene.y() - top_left_scene.y())
        )
        
        for block in self.text_blocks:
            if scene_rect.intersects(block['rect']):
                selected_text_parts.append(block['text'])
        
        return ' '.join(selected_text_parts).strip()
    
    def next_page(self):
        if self.document and self.current_page_num < self.document.page_count - 1:
            self.current_page_num += 1
            self.render_page()
    
    def prev_page(self):
        if self.document and self.current_page_num > 0:
            self.current_page_num -= 1
            self.render_page()
    
    def change_zoom(self, value):
        self.zoom_factor = value / 100.0
        self.zoom_value_label.setText(f"{value}%")
        if self.document:
            self.render_page()
    
    def rotate_left(self):
        self.rotation_angle = (self.rotation_angle - 90) % 360
        if self.document:
            self.render_page()
    
    def rotate_right(self):
        self.rotation_angle = (self.rotation_angle + 90) % 360
        if self.document:
            self.render_page()
    
    def get_text_for_page(self, page_num):
        if self.document and 0 <= page_num < self.document.page_count:
            page = self.document.load_page(page_num)
            return page.get_text()
        return ""
    
    def show_tts_player(self):
        if not self.document:
            QMessageBox.warning(self, "Ошибка", "Сначала откройте PDF файл.")
            return
        
        doc_info = {
            'total_pages': self.document.page_count,
            'current_page': self.current_page_num
        }
        
        self.tts_player = TTSPlayerWidget(self, self.get_text_for_page, doc_info)
        self.tts_player.show()
    
    def save_file(self):
        if self.document and self.file_path:
            try:
                self.document.save(self.file_path, incremental=True, encryption=False)
                QMessageBox.information(self, "Сохранение", "Файл сохранен.")
            except:
                self.save_file_as()
        elif self.document:
            self.save_file_as()
    
    def save_file_as(self):
        if not self.document:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить как", self.file_path, "PDF Files (*.pdf)")
        if file_path:
            try:
                self.document.save(file_path)
                self.file_path = file_path
                QMessageBox.information(self, "Сохранение", "Файл сохранен.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")
    
    def print_file(self):
        if not self.document:
            return
        
        printer = QPainter()
        printDialog = QPrintDialog()
        
        if printDialog.exec() == QDialog.DialogCode.Accepted:
            printer.begin(printDialog.printer())
            
            for i in range(self.document.page_count):
                page = self.document.load_page(i)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
                
                if i > 0:
                    printer.newPage()
                
                printer.drawImage(printer.viewport(), qimage)
            
            printer.end()
            QMessageBox.information(self, "Печать", "Документ отправлен на печать.")
    
    def add_bookmark(self):
        if not self.document:
            return
        
        page_num = self.current_page_num
        
        # Проверяем существующую закладку
        if page_num in self.bookmarks:
            reply = QMessageBox.question(self, "Закладка", 
                                       f"Закладка '{self.bookmarks[page_num]}' уже существует.\nУдалить её?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                del self.bookmarks[page_num]
                self.save_bookmarks()
                self.update_bookmarks_menu()
                self.status_bar.showMessage("Закладка удалена")
            return
        
        # Создаем новую закладку
        name, ok = QInputDialog.getText(self, "Новая закладка", 
                                      "Введите название закладки:",
                                      text=f"Страница {page_num + 1}")
        
        if ok and name:
            self.bookmarks[page_num] = name
            self.save_bookmarks()
            self.update_bookmarks_menu()
            self.status_bar.showMessage(f"Закладка добавлена: {name}")
    
    def update_bookmarks_menu(self):
        self.bookmarks_submenu.clear()
        
        if not self.bookmarks:
            action = QAction("Нет закладок", self)
            action.setEnabled(False)
            self.bookmarks_submenu.addAction(action)
        else:
            for page_num, name in sorted(self.bookmarks.items()):
                action = QAction(f"Стр. {page_num + 1}: {name}", self)
                action.triggered.connect(lambda checked, pn=page_num: self.goto_bookmark(pn))
                self.bookmarks_submenu.addAction(action)
    
    def goto_bookmark(self, page_num):
        """Переход к закладке"""
        self.current_page_num = page_num
        self.render_page()
        self.status_bar.showMessage(f"Переход к закладке: {self.bookmarks.get(page_num, '')}")
    
    def manage_bookmarks(self):
        """Диалог управления закладками с кнопками Перейти и Удалить"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Управление закладками")
        dialog.setGeometry(200, 200, 500, 400)
        
        layout = QVBoxLayout()
        
        # Список закладок
        self.bookmarks_list = QListWidget()
        
        if not self.bookmarks:
            self.bookmarks_list.addItem("Нет закладок")
            self.bookmarks_list.setEnabled(False)
        else:
            for page_num, name in sorted(self.bookmarks.items()):
                self.bookmarks_list.addItem(f"Страница {page_num + 1}: {name}")
        
        layout.addWidget(QLabel("Ваши закладки:"))
        layout.addWidget(self.bookmarks_list)
        
        # Кнопки: Перейти, Удалить, Закрыть
        button_layout = QHBoxLayout()
        
        btn_go = QPushButton("Перейти к закладке")
        btn_go.clicked.connect(lambda: self.go_to_selected_bookmark(dialog))
        button_layout.addWidget(btn_go)
        
        btn_delete = QPushButton("Удалить закладку")
        btn_delete.clicked.connect(lambda: self.delete_selected_bookmark(dialog))
        button_layout.addWidget(btn_delete)
        
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(dialog.accept)
        button_layout.addWidget(btn_close)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()
    
    def go_to_selected_bookmark(self, parent_dialog):
        """Переход к выбранной закладке"""
        if not self.bookmarks_list.currentItem():
            QMessageBox.warning(parent_dialog, "Ошибка", "Выберите закладку.")
            return
        
        item_text = self.bookmarks_list.currentItem().text()
        if "Страница" in item_text and ":" in item_text:
            page_str = item_text.split(':')[0].replace('Страница ', '').strip()
            try:
                page_num = int(page_str) - 1
                self.current_page_num = page_num
                self.render_page()
                parent_dialog.accept()
                self.status_bar.showMessage(f"Переход к закладке: {self.bookmarks[page_num]}")
            except ValueError:
                QMessageBox.warning(parent_dialog, "Ошибка", "Неверный формат закладки.")
    
    def delete_selected_bookmark(self, parent_dialog):
        """Удаление выбранной закладки"""
        if not self.bookmarks_list.currentItem():
            QMessageBox.warning(parent_dialog, "Ошибка", "Выберите закладку для удаления.")
            return
        
        item_text = self.bookmarks_list.currentItem().text()
        if "Страница" in item_text and ":" in item_text:
            page_str = item_text.split(':')[0].replace('Страница ', '').strip()
            try:
                page_num = int(page_str) - 1
                
                reply = QMessageBox.question(parent_dialog, "Подтверждение",
                                           f"Удалить закладку '{self.bookmarks[page_num]}'?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                
                if reply == QMessageBox.StandardButton.Yes:
                    del self.bookmarks[page_num]
                    self.save_bookmarks()
                    self.update_bookmarks_menu()
                    
                    # Обновляем список
                    self.bookmarks_list.clear()
                    for pn, name in sorted(self.bookmarks.items()):
                        self.bookmarks_list.addItem(f"Страница {pn + 1}: {name}")
                    
                    if not self.bookmarks:
                        self.bookmarks_list.addItem("Нет закладок")
                        self.bookmarks_list.setEnabled(False)
                    
                    QMessageBox.information(parent_dialog, "Успех", "Закладка удалена.")
            except (ValueError, KeyError):
                QMessageBox.warning(parent_dialog, "Ошибка", "Не удалось удалить закладку.")
    
    def show_context_menu(self, pos):
        context_menu = QMenu(self)
        
        if self.selected_text:
            action_copy = QAction(f"Копировать текст ({len(self.selected_text)} симв.)", self)
            action_copy.triggered.connect(self.copy_selected_text_to_clipboard)
            context_menu.addAction(action_copy)
            context_menu.addSeparator()
        
        action_copy_all = QAction("Копировать всю страницу", self)
        action_copy_all.triggered.connect(self.copy_all_text)
        context_menu.addAction(action_copy_all)
        
        action_speak = QAction("Озвучить страницу", self)
        action_speak.triggered.connect(self.show_tts_player)
        context_menu.addAction(action_speak)
        
        context_menu.addSeparator()
        
        action_bookmark = QAction("Добавить закладку", self)
        action_bookmark.triggered.connect(self.add_bookmark)
        context_menu.addAction(action_bookmark)
        
        context_menu.exec(self.view.mapToGlobal(pos))
    
    def copy_all_text(self):
        text = self.get_text_for_page(self.current_page_num)
        if text:
            QApplication.clipboard().setText(text)
            self.status_bar.showMessage("Весь текст страницы скопирован")
    
    def toggle_cursor_mode(self):
        self.is_text_select_mode = not self.is_text_select_mode
        
        if self.is_text_select_mode:
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.view.setCursor(Qt.CursorShape.IBeamCursor)
            self.action_toggle_cursor.setIcon(create_text_icon("👆"))
            self.status_bar.showMessage("Режим выделения текста")
        else:
            self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.view.setCursor(Qt.CursorShape.ArrowCursor)
            self.action_toggle_cursor.setIcon(create_text_icon("✋"))
            self.status_bar.showMessage("Режим прокрутки")
        
        self.clear_selection()
    
    def view_mouse_press_event(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_text_select_mode:
            self.selection_start = event.pos()
            self.selection_end = event.pos()
            self.selection_rect = None
            self.selected_text = ""
            self.action_copy_text.setEnabled(False)
            self.view.update()
        else:
            QGraphicsView.mousePressEvent(self.view, event)
    
    def view_mouse_move_event(self, event):
        if (self.is_text_select_mode and 
            self.selection_start is not None and 
            event.buttons() & Qt.MouseButton.LeftButton):
            
            self.selection_end = event.pos()
            x1, y1 = self.selection_start.x(), self.selection_start.y()
            x2, y2 = self.selection_end.x(), self.selection_end.y()
            self.selection_rect = QRectF(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
            
            if self.selection_rect.width() > 5 and self.selection_rect.height() > 5:
                self.selected_text = self.get_text_in_rectangle(self.selection_rect)
                self.action_copy_text.setEnabled(bool(self.selected_text))
            
            self.view.update()
        else:
            QGraphicsView.mouseMoveEvent(self.view, event)
    
    def view_mouse_release_event(self, event):
        if (self.is_text_select_mode and 
            event.button() == Qt.MouseButton.LeftButton and 
            self.selection_start is not None):
            
            self.selection_end = event.pos()
            x1, y1 = self.selection_start.x(), self.selection_start.y()
            x2, y2 = self.selection_end.x(), self.selection_end.y()
            self.selection_rect = QRectF(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
            
            if self.selection_rect.width() > 5 and self.selection_rect.height() > 5:
                self.selected_text = self.get_text_in_rectangle(self.selection_rect)
                if self.selected_text:
                    self.action_copy_text.setEnabled(True)
                    self.status_bar.showMessage(f"Выделено: {len(self.selected_text)} символов")
                else:
                    self.clear_selection()
            else:
                self.clear_selection()
            
            self.view.update()
        else:
            QGraphicsView.mouseReleaseEvent(self.view, event)
    
    def clear_selection(self):
        self.selection_start = None
        self.selection_end = None
        self.selection_rect = None
        self.selected_text = ""
        self.action_copy_text.setEnabled(False)
        self.view.update()
    
    def copy_selected_text_to_clipboard(self):
        if self.selected_text:
            QApplication.clipboard().setText(self.selected_text)
            self.status_bar.showMessage(f"Текст скопирован: {len(self.selected_text)} символов")
            self.clear_selection()
    
    def show_about_dialog(self):
        about_dialog = AboutDialog(self)
        about_dialog.exec()

# ============================================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================================================
if __name__ == '__main__':
    app = QApplication(sys.argv)
    file_to_open = None
    
    if len(sys.argv) > 1:
        file_to_open = sys.argv[1]
        if not os.path.exists(file_to_open):
            file_to_open = None
    
    window = PDFViewerApp(file_to_open)
    window.show()
    sys.exit(app.exec())