import sys
import fitz
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QPushButton, QFileDialog, QLabel, QHBoxLayout, 
                             QSlider, QGraphicsScene, QGraphicsView, 
                             QGraphicsPixmapItem, QDialog, QTextEdit, 
                             QMessageBox, QToolBar, QFrame, QMenu,
                             QTabWidget, QGroupBox, QRadioButton, QLineEdit,
                             QCheckBox, QInputDialog) # Добавил QInputDialog, который использовался внизу

from PyQt6.QtGui import (QPixmap, QImage, QIcon, QAction, QPainter, 
                         QPageLayout, QPageSize, QDropEvent, QDragEnterEvent)

from PyQt6.QtCore import Qt, QSize, QFileInfo, QSettings
# Добавляем правильный импорт QPrintDialog
from PyQt6.QtPrintSupport import QPrintDialog
import pyttsx3
import threading
import os

# --- Класс О программе ---

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе RuundPDF")
        self.setGeometry(100, 100, 400, 250)
        layout = QVBoxLayout()
        label_icon = QLabel(self)
        pixmap = QPixmap("icon.png").scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio)
        label_icon.setPixmap(pixmap)
        label_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label_icon)
        info_text = QTextEdit(self)
        info_text.setReadOnly(True)
        info_text.setHtml("""
            <p align='center'><strong>Программа RuundPDF v1.0.0</strong></p>
            <p align='center'>Права принадлежат DeeR Tuund (c) 2025 г.</p>
            <p>Описание возможностей:</p>
            <ul>
                <li>Чтение PDF файлов</li>
                <li>Выделение и копирование текста (через ПКМ)</li>
                <li>Озвучивание текста (полноценный плеер)</li>
                <li>Режим Зум (слайдер)</li>
                <li>Поворот страницы</li>
                <li>Печать файла</li>
                <li>Сохранение копии файла</li>
                <li>Листание страниц колесом мыши</li>
                <li>Drag-and-Drop загрузка</li>
            </ul>
        """)
        layout.addWidget(info_text)
        btn_ok = QPushButton("ОК")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)
        self.setLayout(layout)

# --- Класс Плеера Озвучки ---

class TTSPlayerDialog(QDialog):
    def __init__(self, parent=None, text_provider=None, document_info=None):
        super().__init__(parent)
        self.setWindowTitle("Плеер Озвучки")
        self.setGeometry(200, 200, 450, 400) # Увеличиваем высоту окна
        self.text_provider = text_provider
        self.document_info = document_info
        self.tts_engine = pyttsx3.init()
        self.is_playing = False
        self.is_paused = False
        self.total_pages = document_info['total_pages']
        self.current_read_page = document_info['current_page']
        self.settings = QSettings("DeeRTuund", "RuundPDF")

        self.initUI()
        self.load_settings()

    def initUI(self):
        main_layout = QVBoxLayout()

        # --- Блок управления плеером (Кнопки Плей/Пауза/Стоп) ---
        player_layout = QHBoxLayout()
        self.btn_start = QPushButton("▶️ Начать/Продолжить")
        self.btn_pause = QPushButton("⏸️ Пауза")
        self.btn_stop = QPushButton("⏹️ Стоп")
        self.btn_start.clicked.connect(self.play_pause_resume)
        self.btn_pause.clicked.connect(self.pause_speech)
        self.btn_stop.clicked.connect(self.stop_speech)
        player_layout.addWidget(self.btn_start)
        player_layout.addWidget(self.btn_pause)
        player_layout.addWidget(self.btn_stop)
        main_layout.addLayout(player_layout)

        # --- Блок навигации по страницам (внутри плеера) ---
        nav_layout = QHBoxLayout()
        self.btn_first = QPushButton("⏮️ В начало")
        self.btn_prev_page = QPushButton("⬅️ Стр. назад")
        self.btn_next_page = QPushButton("➡️ Стр. вперед")
        self.btn_last = QPushButton("⏭️ В конец")
        # Эти кнопки просто меняют страницу, не запуская воспроизведение сразу
        self.btn_first.clicked.connect(lambda: self._set_current_read_page(0))
        self.btn_prev_page.clicked.connect(lambda: self._set_current_read_page(self.current_read_page - 1))
        self.btn_next_page.clicked.connect(lambda: self._set_current_read_page(self.current_read_page + 1))
        self.btn_last.clicked.connect(lambda: self._set_current_read_page(self.total_pages - 1))
        nav_layout.addWidget(self.btn_first)
        nav_layout.addWidget(self.btn_prev_page)
        nav_layout.addWidget(self.btn_next_page)
        nav_layout.addWidget(self.btn_last)
        main_layout.addLayout(nav_layout)
        
        # --- Настройки Диапазона Чтения (Группа 1) ---
        read_range_group = QGroupBox("Диапазон чтения")
        read_range_layout = QVBoxLayout()
        
        self.radio_current = QRadioButton("Читать с текущей страницы")
        self.radio_start = QRadioButton("Читать сначала до конца")
        self.radio_specific = QRadioButton("Читать со страницы номер:")
        self.page_num_edit = QLineEdit(str(self.current_read_page + 1))
        page_num_layout = QHBoxLayout()
        page_num_layout.addWidget(self.radio_specific)
        page_num_layout.addWidget(self.page_num_edit)
        
        read_range_layout.addWidget(self.radio_current)
        read_range_layout.addWidget(self.radio_start)
        read_range_layout.addLayout(page_num_layout)
        
        read_range_group.setLayout(read_range_layout)
        main_layout.addWidget(read_range_group)

        # --- Настройки Голоса (Группа 2, отдельная) ---
        voice_group = QGroupBox("Настройки голоса")
        voice_layout = QHBoxLayout()
        
        self.radio_voice_m = QRadioButton("Мужской")
        self.radio_voice_f = QRadioButton("Женский")
        self.radio_voice_m.toggled.connect(self.save_settings)
        self.radio_voice_f.toggled.connect(self.save_settings)

        voice_layout.addWidget(self.radio_voice_m)
        voice_layout.addWidget(self.radio_voice_f)
        voice_group.setLayout(voice_layout)
        main_layout.addWidget(voice_group)
        
        self.setLayout(main_layout)
        self.radio_current.setChecked(True) # По умолчанию читаем с текущей страницы

    def _set_current_read_page(self, page_num):
        """Вспомогательная функция для навигации."""
        if 0 <= page_num < self.total_pages:
            self.current_read_page = page_num
            self.page_num_edit.setText(str(page_num + 1))
            QMessageBox.information(self, "Навигация", f"Перешли на страницу {page_num + 1}. Нажмите Play для чтения.")

    def load_settings(self):
        # ... (логика загрузки голоса остается прежней) ...
        voice_id = self.settings.value("tts_voice_id", None)
        voices = self.tts_engine.getProperty('voices')
        for voice in voices:
            if voice.id == voice_id:
                if 'male' in voice.name.lower():
                    self.radio_voice_m.setChecked(True)
                elif 'female' in voice.name.lower():
                    self.radio_voice_f.setChecked(True)
                break
        else:
             self.radio_voice_m.setChecked(True)

    def save_settings(self):
        # ... (логика сохранения голоса остается прежней) ...
        voices = self.tts_engine.getProperty('voices')
        for voice in voices:
            is_male = 'male' in voice.name.lower()
            is_female = 'female' in voice.name.lower()
            if self.radio_voice_m.isChecked() and is_male:
                self.settings.setValue("tts_voice_id", voice.id)
                self.tts_engine.setProperty('voice', voice.id) # Применяем сразу
                break
            if self.radio_voice_f.isChecked() and is_female:
                 self.settings.setValue("tts_voice_id", voice.id)
                 self.tts_engine.setProperty('voice', voice.id) # Применяем сразу
                 break

    def get_voice_id(self):
        """Получение ID выбранного голоса."""
        voices = self.tts_engine.getProperty('voices')
        
        for voice in voices:
            is_male = 'male' in voice.name.lower()
            is_female = 'female' in voice.name.lower()
            if self.radio_voice_m.isChecked() and is_male:
                return voice.id
            if self.radio_voice_f.isChecked() and is_female:
                return voice.id
        
        # Если не нашли подходящий голос по критериям, возвращаем ID первого доступного голоса
        return voices[0].id if voices else None

    def play_pause_resume(self):
        # Применяем выбранный голос перед началом
        voice_id = self.get_voice_id()
        if voice_id:
            self.tts_engine.setProperty('voice', voice_id)

        if not self.is_playing or self.is_paused:
            # Определяем, откуда читать, только при первом запуске или если не было паузы
            if not self.is_playing: 
                if self.radio_start.isChecked():
                    self.current_read_page = 0
                elif self.radio_specific.isChecked():
                    try:
                        start_page = int(self.page_num_edit.text()) - 1
                        if not (0 <= start_page < self.total_pages): raise ValueError
                        self.current_read_page = start_page
                    except ValueError:
                        QMessageBox.warning(self, "Ошибка ввода", "Неверный номер страницы.")
                        return
                # self.radio_current уже установлен как стартовая страница при открытии плеера

            if not self.is_playing and not self.is_paused:
                # Запуск нового потока
                self.is_playing = True
                threading.Thread(target=self._run_tts_loop).start()
            elif self.is_paused:
                # Продолжение
                self.tts_engine.resume()
                self.is_paused = False

            self.btn_start.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_stop.setEnabled(True)
        
    def pause_speech(self):
        if self.is_playing and not self.is_paused:
            self.tts_engine.pause()
            self.is_paused = True
            self.btn_start.setEnabled(True)
            self.btn_pause.setEnabled(False)

    def stop_speech(self):
        self.tts_engine.stop()
        self.is_playing = False
        self.is_paused = False
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)

    def _run_tts_loop(self):
        # Цикл чтения документа
        try:
            # Используем self.current_read_page как стартовую точку
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


# --- Основной класс приложения ---

class PDFViewerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RuundPDF - Величайший PDF Reader")
        self.setGeometry(100, 100, 1200, 800)
        self.setWindowIcon(QIcon('icon.png'))
        self.setAcceptDrops(True) # Включаем Drag-and-Drop

        self.document = None
        self.file_path = None
        self.current_page_num = 0
        self.zoom_factor = 1.0
        self.rotation_angle = 0
        self.tts_engine = pyttsx3.init()
        self.bookmarks = {} # {page_num: "Bookmark Name"}

        self.initUI()
        self.apply_styles()
        self.disable_controls()

    def initUI(self):
        # --- Панель инструментов ---
        toolbar = QToolBar("Основная панель")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        self.action_open = QAction(QIcon('icon.png'), "Открыть PDF", self)
        self.action_open.triggered.connect(self.open_file)
        toolbar.addAction(self.action_open)

        self.action_save = QAction("Сохранить", self)
        self.action_save.triggered.connect(self.save_file)
        toolbar.addAction(self.action_save)

        self.action_print = QAction("Печать", self)
        self.action_print.triggered.connect(self.print_file)
        toolbar.addAction(self.action_print)

        toolbar.addSeparator()
        
        self.action_prev = QAction("Пред. стр.", self)
        self.action_prev.triggered.connect(self.prev_page)
        toolbar.addAction(self.action_prev)
        self.page_label = QLabel("Страница: --/--")
        toolbar.addWidget(self.page_label)
        self.action_next = QAction("След. стр.", self)
        self.action_next.triggered.connect(self.next_page)
        toolbar.addAction(self.action_next)
        
        toolbar.addSeparator()
        
        self.action_rotate_left = QAction("Повернуть влево (90°)", self)
        self.action_rotate_left.triggered.connect(lambda: self.rotate_page(-90))
        toolbar.addAction(self.action_rotate_left)
        self.action_rotate_right = QAction("Повернуть вправо (90°)", self)
        self.action_rotate_right.triggered.connect(lambda: self.rotate_page(90))
        toolbar.addAction(self.action_rotate_right)

        # Кнопка плеера озвучки
        self.action_speak = QAction("Открыть плеер озвучки", self)
        self.action_speak.triggered.connect(self.show_tts_player)
        toolbar.addAction(self.action_speak)
        
        toolbar.addSeparator()

        self.action_about = QAction("О программе", self)
        self.action_about.triggered.connect(self.show_about_dialog)
        toolbar.addAction(self.action_about)

        # --- Главное меню: Закладки ---
        menubar = self.menuBar()
        bookmarks_menu = menubar.addMenu('&Закладки')
        self.action_add_bookmark = QAction("Добавить закладку на текущую страницу", self)
        self.action_add_bookmark.triggered.connect(self.add_bookmark)
        bookmarks_menu.addAction(self.action_add_bookmark)
        bookmarks_menu.addSeparator()
        self.bookmarks_submenu = QMenu(self) # Submenu for dynamic bookmarks
        bookmarks_menu.addMenu(self.bookmarks_submenu)


        # --- Основной макет и Зум ---
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

        # --- Область отображения PDF ---
        self.scene = QGraphicsScene(self)
        self.view = PDFGraphicsView(self.scene, self) # Используем кастомный класс для обработки колеса
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.show_context_menu)
        main_layout.addWidget(self.view)
        
        self.current_pixmap_item = None

    def apply_styles(self):
        """Серый тулбар, черные символы."""
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
    
    # --- Drag and Drop реализация ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith('.pdf'):
                self.open_file(file_path)
                return

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


    def keyPressEvent(self, event):
        """Обработка нажатий клавиш клавиатуры для навигации."""
        if event.key() == Qt.Key.Key_PageDown or event.key() == Qt.Key.Key_Down:
            self.next_page()
            event.accept()
        elif event.key() == Qt.Key.Key_PageUp or event.key() == Qt.Key.Key_Up:
            self.prev_page()
            event.accept()
        else:
            super().keyPressEvent(event)            

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
        """Callback функция для TTS плеера."""
        if self.document and 0 <= page_num < self.document.page_count:
            page = self.document.load_page(page_num)
            return page.get_text()
        return ""

    def show_tts_player(self):
        """Функция: Открытие плеера озвучки."""
        if not self.document:
            QMessageBox.warning(self, "Плеер", "Сначала откройте PDF-файл.")
            return
        
        doc_info = {
            'total_pages': self.document.page_count,
            'current_page': self.current_page_num
        }
        player_dialog = TTSPlayerDialog(self, self.get_text_for_page, doc_info)
        player_dialog.exec()

    # --- Сохранить и Печать ---
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
        if not self.document: return
        printer = QPainter()
        printDialog = QPrintDialog()
        if printDialog.exec() == QDialog.Accepted:
            # ... (Логика печати остается как в предыдущем коде) ...
            pass # Use previous code logic here

    # --- Закладки ---
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
        # ... (Код контекстного меню остается прежним) ...
        context_menu = QMenu(self)
        action_copy_all = QAction("Копировать весь текст страницы", self)
        action_copy_all.triggered.connect(self.copy_all_text)
        context_menu.addAction(action_copy_all)

        action_speak_all = QAction("Озвучить весь текст страницы (текст)", self)
        # Привязываем к функции открытия плеера для согласованности
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

# --- Кастомный QGraphicsView для обработки колеса мыши ---

class PDFGraphicsView(QGraphicsView):
    def __init__(self, scene, main_app):
        super().__init__(scene)
        self.main_app = main_app
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setAcceptDrops(True) # Включаем Drag-and-Drop для самой области просмотра тоже

    # Обработка колеса мыши для прокрутки/листания
    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Если зажат Ctrl, делаем зум
            delta = event.angleDelta().y()
            if delta > 0:
                self.main_app.zoom_slider.setValue(self.main_app.zoom_slider.value() + 10)
            elif delta < 0:
                self.main_app.zoom_slider.setValue(self.main_app.zoom_slider.value() - 10)
        else:
            # Иначе, листаем страницы
            delta = event.angleDelta().y()
            if delta > 0:
                self.main_app.prev_page()
            elif delta < 0:
                self.main_app.next_page()
            # Важно принять событие, чтобы оно не проваливалось дальше
            event.accept()


if __name__ == '__main__':
    if not os.path.exists('icon.png'):
        print("ВНИМАНИЕ: Файл icon.png не найден! Интерфейс будет работать, но без иконок.")
    
    # Нужен QInputDialog для закладок, его тоже надо импортировать
    from PyQt6.QtWidgets import QInputDialog
    
    app = QApplication(sys.argv)
    ex = PDFViewerApp()
    ex.show()
    sys.exit(app.exec())