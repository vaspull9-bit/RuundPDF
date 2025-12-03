# Версия v2.4.0
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
                         QPageLayout, QPageSize, QDropEvent, QDragEnterEvent, 
                         QFont, QBrush, QColor, QCursor, QTransform)
from PyQt6.QtCore import Qt, QSize, QFileInfo, QSettings, QTimer, QRectF, QPointF, QRect
from PyQt6.QtPrintSupport import QPrintDialog

# --- 2.1. ГЛОБАЛЬНАЯ ФУНКЦИЯ СОЗДАНИЯ ИКОНОК ИЗ ТЕКСТА ---
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


# --- 3. КЛАСС О ПРОГРАММЕ (v2.1.0) ---
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
            <p align='center'><strong>Программа RuundPDF v2.4.0</strong></p>
            <p align='center'>Права принадлежат DeeR Tuund (c) 2025 г.</p>
            <p>Описание возможностей:</p>
            <ul>
                <li>Чтение PDF файлов</li>
                <li>Выделение и копирование текста (как в Adobe Reader)</li>
                <li>Озвучивание текста (полноценный плеер с паузой/стопом, мужской/женский голоса)</li>
                <li>Режим Зум</li>
                <li>Поворот страницы</li>
                <li>Печать файла</li>
                <li>Сохранение копии файла</li>
                <li>Листание страниц колесом мыши/клавиатурой (PgUp/PgDn)</li>
                <li>Drag-and-Drop загрузка (все окно программы)</li>
                <li>Система закладок</li>
            </ul>
        """)
        layout.addWidget(info_text)
        btn_ok = QPushButton("ОК")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)
        self.setLayout(layout)

# --- 4. КЛАСС НАСТРОЕК ПЛЕЕРА (УПРОЩЕННЫЙ) ---
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
        
        # Группа диапазона чтения
        read_range_group = QGroupBox("Диапазон чтения")
        read_range_layout = QVBoxLayout()
        
        self.radio_current = QRadioButton("Читать с текущей страницы")
        self.radio_only_current = QRadioButton("Читать только текущую страницу")
        self.radio_start = QRadioButton("Читать сначала до конца")
        self.radio_specific = QRadioButton("Читать со страницы:")
        
        self.page_num_edit = QLineEdit(str(self.player.current_read_page + 1))
        page_num_layout = QHBoxLayout()
        page_num_layout.addWidget(self.radio_specific)
        page_num_layout.addWidget(self.page_num_edit)
        
        read_range_layout.addWidget(self.radio_current)
        read_range_layout.addWidget(self.radio_only_current)
        read_range_layout.addWidget(self.radio_start)
        read_range_layout.addLayout(page_num_layout)
        read_range_group.setLayout(read_range_layout)
        main_layout.addWidget(read_range_group)

        # Группа выбора голоса (упрощенная)
        voice_group = QGroupBox("Выбор голоса")
        voice_layout = QVBoxLayout()
        
        self.radio_male = QRadioButton("Мужской голос")
        self.radio_female = QRadioButton("Женский голос")
        
        voice_layout.addWidget(self.radio_male)
        voice_layout.addWidget(self.radio_female)
        
        voice_group.setLayout(voice_layout)
        main_layout.addWidget(voice_group)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        btn_apply = QPushButton("Применить")
        btn_apply.clicked.connect(self.apply_settings)
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_apply)
        btn_layout.addWidget(btn_close)
        main_layout.addLayout(btn_layout)
        
        self.setLayout(main_layout)
        
        # Устанавливаем текущий режим чтения
        if self.player.read_mode == 'start': 
            self.radio_start.setChecked(True)
        elif self.player.read_mode == 'specific': 
            self.radio_specific.setChecked(True)
        elif self.player.read_mode == 'only_current': 
            self.radio_only_current.setChecked(True)
        else: 
            self.radio_current.setChecked(True)

    def load_settings(self):
        """Загружает сохраненные настройки голоса."""
        use_male = self.player.settings.value("tts_use_male", True, type=bool)
        use_female = self.player.settings.value("tts_use_female", False, type=bool)
        
        if use_female:
            self.radio_female.setChecked(True)
        else:
            self.radio_male.setChecked(True)

    def apply_settings(self):
        """Применяет настройки."""
        # Сохраняем выбор голоса
        self.player.settings.setValue("tts_use_male", self.radio_male.isChecked())
        self.player.settings.setValue("tts_use_female", self.radio_female.isChecked())
        
        # Устанавливаем режим чтения
        if self.radio_start.isChecked():
            self.player.set_read_mode('start')
        elif self.radio_specific.isChecked():
            try:
                page = int(self.page_num_edit.text()) - 1
                if 0 <= page < self.player.total_pages:
                    self.player.set_read_mode('specific', page)
                else:
                    QMessageBox.warning(self, "Ошибка", "Номер страницы вне диапазона.")
                    return
            except ValueError:
                QMessageBox.warning(self, "Ошибка ввода", "Введите корректный номер страницы.")
                return
        elif self.radio_only_current.isChecked():
            self.player.set_read_mode('only_current')
        else:
            self.player.set_read_mode('current')
        
        # Применяем настройки голоса сразу
        self.player.apply_voice_settings()
        
        QMessageBox.information(self, "Настройки", "Настройки применены успешно.")
        self.accept()


# --- 5. КЛАСС ПЛЕЕРА ОЗВУЧКИ (ПОЛНОСТЬЮ ПЕРЕРАБОТАННЫЙ) ---
class TTSPlayerWidget(QWidget):
    def __init__(self, parent=None, text_provider=None, document_info=None):
        super().__init__(parent)
        self.text_provider = text_provider
        self.document_info = document_info
        self.tts_engine = None
        self.is_playing = False
        self.is_paused = False
        self.total_pages = document_info['total_pages']
        self.current_read_page = document_info['current_page']
        self.settings = QSettings("DeeRTuund", "RuundPDF")
        self.read_mode = 'current'
        self.specific_page = 0
        self.voice_id = None
        self.stop_requested = False
        self.current_voice_type = "male"  # male или female
        
        self.initUI()
        self.load_settings()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.Tool) 
        self.setWindowTitle("Плеер RuundPDF")
        
        # Инициализируем движок TTS
        self.init_tts_engine()

    def initUI(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Создаем кнопки
        self.btn_first = QPushButton("⏮️")
        self.btn_prev_page = QPushButton("⬅️")
        self.btn_play_pause = QPushButton("▶️")
        self.btn_next_page = QPushButton("➡️")
        self.btn_last = QPushButton("⏭️")
        self.btn_stop = QPushButton("⏹️")
        self.btn_config = QPushButton("⚙️")
        
        # Устанавливаем всплывающие подсказки
        self.btn_first.setToolTip("Первая страница")
        self.btn_prev_page.setToolTip("Предыдущая страница")
        self.btn_play_pause.setToolTip("Воспроизвести/Пауза")
        self.btn_next_page.setToolTip("Следующая страница")
        self.btn_last.setToolTip("Последняя страница")
        self.btn_stop.setToolTip("Остановить")
        self.btn_config.setToolTip("Настройки")
        
        # Подключаем сигналы
        self.btn_first.clicked.connect(self.go_to_first_page)
        self.btn_prev_page.clicked.connect(self.go_to_prev_page)
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        self.btn_next_page.clicked.connect(self.go_to_next_page)
        self.btn_last.clicked.connect(self.go_to_last_page)
        self.btn_stop.clicked.connect(self.stop_playback)
        self.btn_config.clicked.connect(self.show_config)
        
        # Добавляем кнопки в layout
        layout.addWidget(self.btn_first)
        layout.addWidget(self.btn_prev_page)
        layout.addWidget(self.btn_play_pause)
        layout.addWidget(self.btn_next_page)
        layout.addWidget(self.btn_last)
        layout.addWidget(self.btn_stop)
        layout.addWidget(self.btn_config)
        
        self.setLayout(layout)
        self.update_buttons()

    def init_tts_engine(self):
        """Инициализирует движок TTS."""
        try:
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', 150)  # Скорость речи
            self.tts_engine.setProperty('volume', 0.9)  # Громкость
            self.apply_voice_settings()
        except Exception as e:
            print(f"Ошибка инициализации TTS: {e}")
            QMessageBox.warning(self, "Ошибка", "Не удалось инициализировать движок озвучки.")

    def load_settings(self):
        """Загружает настройки из реестра."""
        use_male = self.settings.value("tts_use_male", True, type=bool)
        use_female = self.settings.value("tts_use_female", False, type=bool)
        
        if use_female:
            self.current_voice_type = "female"
        else:
            self.current_voice_type = "male"

    def save_settings(self):
        """Сохраняет настройки в реестр."""
        self.settings.setValue("tts_use_male", self.current_voice_type == "male")
        self.settings.setValue("tts_use_female", self.current_voice_type == "female")

    def apply_voice_settings(self):
        """Применяет настройки голоса."""
        if not self.tts_engine:
            return
            
        voices = self.tts_engine.getProperty('voices')
        if not voices:
            return
            
        # Ищем подходящий голос
        target_gender = "female" if self.current_voice_type == "female" else "male"
        
        for voice in voices:
            voice_name = voice.name.lower()
            voice_id = voice.id
            
            # Проверяем соответствие полу
            if target_gender == "female" and "female" in voice_name:
                self.tts_engine.setProperty('voice', voice_id)
                self.voice_id = voice_id
                return
            elif target_gender == "male" and "male" in voice_name:
                self.tts_engine.setProperty('voice', voice_id)
                self.voice_id = voice_id
                return
        
        # Если не нашли подходящий голос, используем первый доступный
        if voices:
            self.tts_engine.setProperty('voice', voices[0].id)
            self.voice_id = voices[0].id

    def update_buttons(self):
        """Обновляет состояние кнопок."""
        if self.is_playing and not self.is_paused:
            self.btn_play_pause.setText("⏸️")
            self.btn_play_pause.setToolTip("Пауза")
        else:
            self.btn_play_pause.setText("▶️")
            self.btn_play_pause.setToolTip("Воспроизвести")
        
        # Блокируем кнопки навигации во время воспроизведения
        nav_enabled = not self.is_playing
        self.btn_first.setEnabled(nav_enabled)
        self.btn_prev_page.setEnabled(nav_enabled)
        self.btn_next_page.setEnabled(nav_enabled)
        self.btn_last.setEnabled(nav_enabled)

    def set_read_mode(self, mode, page=0):
        """Устанавливает режим чтения."""
        self.read_mode = mode
        self.specific_page = page

    def go_to_first_page(self):
        """Переходит на первую страницу."""
        self.current_read_page = 0
        if self.is_playing:
            self.stop_playback()

    def go_to_prev_page(self):
        """Переходит на предыдущую страницу."""
        if self.current_read_page > 0:
            self.current_read_page -= 1
            if self.is_playing:
                self.stop_playback()

    def go_to_next_page(self):
        """Переходит на следующую страницу."""
        if self.current_read_page < self.total_pages - 1:
            self.current_read_page += 1
            if self.is_playing:
                self.stop_playback()

    def go_to_last_page(self):
        """Переходит на последнюю страницу."""
        self.current_read_page = self.total_pages - 1
        if self.is_playing:
            self.stop_playback()

    def toggle_play_pause(self):
        """Переключает воспроизведение/паузу."""
        if not self.is_playing:
            self.start_playback()
        elif self.is_paused:
            self.resume_playback()
        else:
            self.pause_playback()

    def start_playback(self):
        """Начинает воспроизведение."""
        if not self.tts_engine:
            self.init_tts_engine()
            if not self.tts_engine:
                return
        
        # Устанавливаем начальную страницу
        if self.read_mode == 'start':
            self.current_read_page = 0
        elif self.read_mode == 'specific':
            self.current_read_page = self.specific_page
        elif self.read_mode == 'only_current':
            pass  # Оставляем текущую страницу
        
        self.is_playing = True
        self.is_paused = False
        self.stop_requested = False
        
        # Запускаем поток воспроизведения
        self.playback_thread = threading.Thread(target=self.playback_worker)
        self.playback_thread.daemon = True
        self.playback_thread.start()
        
        self.update_buttons()

    def pause_playback(self):
        """Ставит воспроизведение на паузу."""
        if self.is_playing and not self.is_paused:
            self.is_paused = True
            self.update_buttons()

    def resume_playback(self):
        """Возобновляет воспроизведение."""
        if self.is_playing and self.is_paused:
            self.is_paused = False
            self.update_buttons()

    def stop_playback(self):
        """Останавливает воспроизведение."""
        self.stop_requested = True
        self.is_playing = False
        self.is_paused = False
        
        # Останавливаем движок TTS
        if self.tts_engine:
            try:
                self.tts_engine.stop()
            except:
                pass
        
        self.update_buttons()

    def playback_worker(self):
        """Рабочий поток для воспроизведения."""
        try:
            # Определяем страницы для чтения
            if self.read_mode == 'only_current':
                pages_to_read = [self.current_read_page]
            elif self.read_mode == 'start':
                pages_to_read = list(range(0, self.total_pages))
            elif self.read_mode == 'specific':
                pages_to_read = list(range(self.specific_page, self.total_pages))
            else:  # current
                pages_to_read = list(range(self.current_read_page, self.total_pages))
            
            # Читаем страницы
            for page_num in pages_to_read:
                if self.stop_requested:
                    break
                
                # Ждем, если на паузе
                while self.is_paused and not self.stop_requested:
                    time.sleep(0.1)
                
                if self.stop_requested:
                    break
                
                # Получаем текст страницы
                text = self.text_provider(page_num)
                if text and not self.stop_requested:
                    self.current_read_page = page_num
                    
                    try:
                        # Озвучиваем текст
                        self.tts_engine.say(text)
                        self.tts_engine.runAndWait()
                    except Exception as e:
                        print(f"Ошибка при озвучивании страницы {page_num}: {e}")
                        break
                
                if self.stop_requested:
                    break
                    
        except Exception as e:
            print(f"Ошибка в потоке воспроизведения: {e}")
        finally:
            # Завершаем воспроизведение
            self.is_playing = False
            self.is_paused = False
            self.stop_requested = False
            self.update_buttons()

    def show_config(self):
        """Показывает диалог настроек."""
        config_dialog = TTSConfigDialog(self, self)
        config_dialog.exec()

    def closeEvent(self, event):
        """Обработчик закрытия окна."""
        self.stop_playback()
        event.accept()


# --- 6. ОСНОВНОЙ КЛАСС ПРИЛОЖЕНИЯ (PDFViewerApp) ---

class PDFViewerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RuundPDF - PDF Reader")
        self.setGeometry(100, 100, 1200, 800)
        self.setWindowIcon(QIcon(resource_path('icon.png')))
        self.setAcceptDrops(True)

        self.document = None
        self.file_path = None
        self.current_page_num = 0
        self.zoom_factor = 1.0
        self.rotation_angle = 0
        self.bookmarks = {}
        self.tts_player_widget = None
        self.is_text_select_mode = True
        self.selection_start = None
        self.selection_end = None
        self.selection_rect = None
        self.text_blocks = []
        self.page_pixmap = None
        self.selected_text = ""

        self.initUI()
        self.apply_styles()
        self.disable_controls()
        
        self.setAcceptDrops(True)
        self.centralWidget().setAcceptDrops(True)

    def initUI(self):
        toolbar = QToolBar("Основная панель")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly) 

        # Кнопки тулбара
        self.action_open = QAction(QIcon(resource_path('icon.png')), "Открыть PDF", self)
        self.action_open.triggered.connect(self.open_file)
        toolbar.addAction(self.action_open)

        self.action_save = QAction(create_text_icon("💾"), "Сохранить", self)
        self.action_save.triggered.connect(self.save_file)
        toolbar.addAction(self.action_save)
        
        self.action_save_as = QAction(create_text_icon("📋"), "Сохранить как...", self)
        self.action_save_as.triggered.connect(self.save_file_as)
        toolbar.addAction(self.action_save_as)

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
        
        # Кнопки поворота (ИСПРАВЛЕНО)
        self.action_rotate_left = QAction(create_text_icon("↺"), "Повернуть влево 90°", self) 
        self.action_rotate_left.triggered.connect(self.rotate_left)
        toolbar.addAction(self.action_rotate_left)

        self.action_rotate_right = QAction(create_text_icon("↻"), "Повернуть вправо 90°", self) 
        self.action_rotate_right.triggered.connect(self.rotate_right)
        toolbar.addAction(self.action_rotate_right)

        toolbar.addSeparator()
        
        self.action_speak = QAction(create_text_icon("📖"), "Открыть плеер озвучки", self)
        self.action_speak.triggered.connect(self.show_tts_player)
        toolbar.addAction(self.action_speak)
        
        self.action_bookmark = QAction(create_text_icon("🔖"), "Управление закладками", self)
        self.action_bookmark.triggered.connect(self.show_bookmarks_menu)
        toolbar.addAction(self.action_bookmark)
        
        self.action_toggle_cursor = QAction(create_text_icon("👆"), "Переключить режим курсора", self)
        self.action_toggle_cursor.triggered.connect(self.toggle_cursor_mode)
        toolbar.addAction(self.action_toggle_cursor)
        
        self.action_copy_text = QAction(create_text_icon("📋"), "Копировать выделенный текст", self)
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
        bookmarks_menu.addSeparator()
        self.bookmarks_submenu = QMenu(self)
        bookmarks_menu.addMenu(self.bookmarks_submenu)

        # Основной layout
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        central_widget.setAcceptDrops(True)
        
        # Панель зума
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
        
        # Поле для просмотра PDF
        self.scene = QGraphicsScene(self)
        self.view = PDFGraphicsView(self.scene, self)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.show_context_menu)
        
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.view.setCursor(Qt.CursorShape.IBeamCursor)
        
        self.view.mousePressEvent = self.view_mouse_press_event
        self.view.mouseMoveEvent = self.view_mouse_move_event
        self.view.mouseReleaseEvent = self.view_mouse_release_event
        
        main_layout.addWidget(self.view)
        self.current_pixmap_item = None
        
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Готово. Выделяйте текст мышью. Ctrl+C для копирования.")
    
    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { 
                background-color: #f0f0f0; 
            }
            QPushButton {
                background-color: #e0e0e0; 
                color: black; 
                padding: 5px 10px;
                border: 1px solid #ccc; 
                border-radius: 4px;
            }
            QPushButton:hover { 
                background-color: #d0d0d0; 
            }
            QToolBar {
                background-color: #e0e0e0; 
                color: black; 
                padding: 5px;
                border-bottom: 1px solid #ccc;
            }
            QLabel { 
                color: black; 
            }
            QGraphicsView { 
                background-color: #fff; 
                border: 1px solid #ccc;
            }
            QGraphicsView:focus {
                border: 2px solid #4A90E2;
            }
        """)

    def disable_controls(self):
        controls = [self.action_prev, self.action_next, self.action_rotate_left, 
                    self.action_rotate_right, self.action_speak, self.zoom_slider,
                    self.action_save, self.action_save_as, self.action_print, 
                    self.action_add_bookmark, self.action_bookmark, self.action_toggle_cursor]
        for control in controls:
            control.setEnabled(False)

    def enable_controls(self):
        controls = [self.action_prev, self.action_next, self.action_rotate_left, 
                    self.action_rotate_right, self.action_speak, self.zoom_slider,
                    self.action_save, self.action_save_as, self.action_print, 
                    self.action_add_bookmark, self.action_bookmark, self.action_toggle_cursor]
        for control in controls:
            control.setEnabled(True)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith('.pdf'):
                event.acceptProposedAction()
                self.setStyleSheet("QMainWindow { background-color: #e0f0ff; }")
            else:
                event.ignore()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.apply_styles()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith('.pdf'):
                self.open_file(file_path)
                event.acceptProposedAction()
            else:
                QMessageBox.warning(self, "Неверный файл", "Поддерживаются только PDF файлы")
                event.ignore()
        
        self.apply_styles()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_PageDown:
            self.next_page()
            event.accept()
        elif event.key() == Qt.Key.Key_PageUp:
            self.prev_page()
            event.accept()
        elif event.key() == Qt.Key.Key_Down:
            self.next_page()
            event.accept()
        elif event.key() == Qt.Key.Key_Up:
            self.prev_page()
            event.accept()
        elif event.key() == Qt.Key.Key_C and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.copy_selected_text_to_clipboard()
            event.accept()
        elif event.key() == Qt.Key.Key_Space:
            self.toggle_cursor_mode()
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
                self.status_bar.showMessage(f"Файл загружен: {QFileInfo(file_path).fileName()}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка загрузки", f"Не удалось открыть файл. Ошибка: {e}")

    def render_page(self):
        if not self.document:
            return
        
        page = self.document.load_page(self.current_page_num)
        
        # Создаем матрицу с учетом зума и поворота
        matrix = fitz.Matrix(self.zoom_factor, self.zoom_factor)
        
        # Применяем поворот через матрицу
        if self.rotation_angle != 0:
            # Поворачиваем на нужный угол
            rotate_matrix = fitz.Matrix().prerotate(self.rotation_angle)
            matrix = rotate_matrix * matrix
        
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        
        # Создаем QImage из данных pixmap
        qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        self.page_pixmap = QPixmap.fromImage(qimage)
        
        # Очищаем сцену и добавляем новый pixmap
        self.scene.clear()
        self.current_pixmap_item = QGraphicsPixmapItem(self.page_pixmap)
        self.scene.addItem(self.current_pixmap_item)
        
        # Устанавливаем размер сцены
        self.view.setSceneRect(self.current_pixmap_item.boundingRect())
        
        # Обновляем метку страницы
        self.page_label.setText(f"Страница: {self.current_page_num + 1}/{self.document.page_count}")
        
        # Извлекаем текстовые блоки
        self.text_blocks = self.extract_text_with_rectangles(page)
        
        # Очищаем выделение
        self.clear_selection()

    def extract_text_with_rectangles(self, page):
        """Извлекает текст с прямоугольниками для выделения."""
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
                            
                            # Применяем масштабирование
                            scaled_bbox = [
                                bbox[0] * self.zoom_factor,
                                bbox[1] * self.zoom_factor,
                                bbox[2] * self.zoom_factor,
                                bbox[3] * self.zoom_factor
                            ]
                            
                            # Применяем поворот
                            if self.rotation_angle != 0:
                                # Для простоты - упрощенная обработка поворота
                                center_x = (scaled_bbox[0] + scaled_bbox[2]) / 2
                                center_y = (scaled_bbox[1] + scaled_bbox[3]) / 2
                                
                                # Просто немного смещаем координаты для демонстрации
                                # В реальном приложении нужна более сложная математика
                                if self.rotation_angle == 90:
                                    scaled_bbox = [
                                        -scaled_bbox[1] + center_x + center_y,
                                        scaled_bbox[0] - center_x + center_y,
                                        -scaled_bbox[3] + center_x + center_y,
                                        scaled_bbox[2] - center_x + center_y
                                    ]
                            
                            rect = QRectF(
                                scaled_bbox[0], 
                                scaled_bbox[1], 
                                scaled_bbox[2] - scaled_bbox[0], 
                                scaled_bbox[3] - scaled_bbox[1]
                            )
                            
                            text_blocks.append({
                                'text': text,
                                'bbox': scaled_bbox,
                                'rect': rect
                            })
        except Exception as e:
            print(f"Ошибка при извлечении текста: {e}")
        
        return text_blocks

    def get_text_in_rectangle(self, selection_rect):
        """Получает текст внутри заданного прямоугольника выделения."""
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
            block_rect = block['rect']
            if scene_rect.intersects(block_rect):
                selected_text_parts.append(block['text'])
        
        result = ' '.join(selected_text_parts)
        return result.strip() if result else ""

    def next_page(self):
        if self.document and self.current_page_num < self.document.page_count - 1:
            self.current_page_num += 1
            self.render_page()
            self.status_bar.showMessage(f"Страница {self.current_page_num + 1} из {self.document.page_count}")

    def prev_page(self):
        if self.document and self.current_page_num > 0:
            self.current_page_num -= 1
            self.render_page()
            self.status_bar.showMessage(f"Страница {self.current_page_num + 1} из {self.document.page_count}")

    def goto_page(self, page_num):
        if self.document and 0 <= page_num < self.document.page_count:
            self.current_page_num = page_num
            self.render_page()

    def change_zoom(self, value):
        self.zoom_factor = value / 100.0
        self.zoom_value_label.setText(f"{value}%")
        if self.document:
            self.render_page()

    def rotate_left(self):
        """Повернуть страницу на 90° влево."""
        self.rotation_angle = (self.rotation_angle - 90) % 360
        if self.document:
            self.render_page()

    def rotate_right(self):
        """Повернуть страницу на 90° вправо."""
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
            try:
                self.document.save(self.file_path, incremental=True, encryption=False)
                QMessageBox.information(self, "Успех", "Файл успешно сохранен.")
                self.status_bar.showMessage("Файл сохранен")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка сохранения", 
                                    f"Не удалось сохранить изменения в исходный файл: {e}")
                self.save_file_as(self.file_path)
        elif self.document:
            self.save_file_as()

    def save_file_as(self, default_path=""):
        if not self.document:
            return
            
        if not default_path and self.file_path:
            default_path = self.file_path
            
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить PDF как...", 
                                                  default_path, "PDF Files (*.pdf)")
        if file_path:
            try:
                self.document.save(file_path)
                self.file_path = file_path
                QMessageBox.information(self, "Успех", 
                                      f"Файл успешно сохранен как {QFileInfo(file_path).fileName()}.")
                self.status_bar.showMessage(f"Файл сохранен как: {QFileInfo(file_path).fileName()}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка сохранения", 
                                  f"Не удалось сохранить файл. Ошибка: {e}")

    def print_file(self):
        if not self.document:
            return

        printer = QPainter()
        printDialog = QPrintDialog()
        
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
                
                width = int(scale * size.width())
                height = int(scale * size.height())
                
                printer.drawImage(
                    int((area.width() - width) / 2), 
                    int((area.height() - height) / 2), 
                    qimage.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )

            printer.end()
            QMessageBox.information(self, "Печать", "Документ отправлен на печать.")

    def add_bookmark(self):
        if not self.document:
            return
        page_num = self.current_page_num
        name, ok = QInputDialog.getText(self, 'Новая закладка', 
                                       'Введите название закладки:',
                                       text=f"Страница {page_num + 1}")
        if ok and name:
            self.bookmarks[page_num] = name
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
                action.triggered.connect(lambda checked, pn=page_num: self.goto_page(pn))
                self.bookmarks_submenu.addAction(action)

    def show_bookmarks_menu(self):
        self.bookmarks_submenu.exec(self.mapToGlobal(self.action_bookmark.parentWidget().pos()))

    def show_context_menu(self, pos):
        context_menu = QMenu(self)
        
        if self.selected_text:
            action_copy_selected = QAction(f"Копировать выделенный текст ({len(self.selected_text)} симв.)", self)
            action_copy_selected.triggered.connect(self.copy_selected_text_to_clipboard)
            context_menu.addAction(action_copy_selected)
            context_menu.addSeparator()
        
        action_copy_all = QAction("Копировать весь текст страницы", self)
        action_copy_all.triggered.connect(self.copy_all_text)
        context_menu.addAction(action_copy_all)

        action_speak_all = QAction("Озвучить весь текст страницы", self)
        action_speak_all.triggered.connect(self.show_tts_player) 
        context_menu.addAction(action_speak_all)
        
        context_menu.addSeparator()
        
        action_toggle_cursor = QAction("Переключить режим курсора", self)
        action_toggle_cursor.triggered.connect(self.toggle_cursor_mode)
        context_menu.addAction(action_toggle_cursor)
        
        context_menu.exec(self.view.mapToGlobal(pos))

    def copy_all_text(self):
        text = self.get_text_for_page(self.current_page_num)
        if text:
            QApplication.clipboard().setText(text)
            self.status_bar.showMessage("Весь текст страницы скопирован в буфер обмена")

    def toggle_cursor_mode(self):
        if self.is_text_select_mode:
            self.is_text_select_mode = False
            self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.view.setCursor(Qt.CursorShape.ArrowCursor)
            self.action_toggle_cursor.setIcon(create_text_icon("✏️"))
            self.action_toggle_cursor.setToolTip("Переключить в режим выделения текста")
            self.status_bar.showMessage("Режим прокрутки: используйте колесо мыши для навигации")
            self.clear_selection()
        else:
            self.is_text_select_mode = True
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.view.setCursor(Qt.CursorShape.IBeamCursor)
            self.action_toggle_cursor.setIcon(create_text_icon("👆"))
            self.action_toggle_cursor.setToolTip("Переключить в режим прокрутки")
            self.status_bar.showMessage("Режим выделения текста: выделяйте текст мышью, Ctrl+C для копирования")

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
                try:
                    self.selected_text = self.get_text_in_rectangle(self.selection_rect)
                    if self.selected_text:
                        self.action_copy_text.setEnabled(True)
                        preview = self.selected_text[:100] + "..." if len(self.selected_text) > 100 else self.selected_text
                        self.status_bar.showMessage(f"Выделено: {preview}")
                    else:
                        self.status_bar.showMessage("Выделение... (текст не найден)")
                except Exception as e:
                    print(f"Ошибка при получении текста: {e}")
                    self.status_bar.showMessage("Ошибка при выделении текста")
            else:
                self.status_bar.showMessage("Выделение...")
            
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
                try:
                    self.selected_text = self.get_text_in_rectangle(self.selection_rect)
                    if self.selected_text:
                        self.action_copy_text.setEnabled(True)
                        char_count = len(self.selected_text)
                        word_count = len(self.selected_text.split())
                        self.status_bar.showMessage(f"Текст выделен: {char_count} символов, {word_count} слов. Ctrl+C для копирования")
                    else:
                        self.status_bar.showMessage("Текст не найден в выделенной области")
                        self.clear_selection()
                except Exception as e:
                    print(f"Ошибка при окончательном получении текста: {e}")
                    self.status_bar.showMessage("Ошибка при выделении текста")
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
            char_count = len(self.selected_text)
            word_count = len(self.selected_text.split())
            self.status_bar.showMessage(f"Текст скопирован: {char_count} символов, {word_count} слов")
            
            QTimer.singleShot(1000, self.clear_selection)
        else:
            self.status_bar.showMessage("Нет выделенного текста для копирования")

    def show_about_dialog(self):
        about_dialog = AboutDialog(self)
        about_dialog.exec()


# --- 7. КАСТОМНЫЙ QGraphicsView ---

class PDFGraphicsView(QGraphicsView):
    def __init__(self, scene, main_app):
        super().__init__(scene)
        self.main_app = main_app
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setAcceptDrops(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMouseTracking(True)

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
            
            if self.main_app.selected_text:
                painter.setPen(Qt.GlobalColor.darkBlue)
                text_info = f"{len(self.main_app.selected_text)} симв."
                painter.drawText(
                    self.main_app.selection_rect.bottomLeft() + QPointF(5, 15), 
                    text_info
                )


# --- 8. БЛОК ЗАПУСКА ---

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = PDFViewerApp()
    ex.show()
    sys.exit(app.exec())