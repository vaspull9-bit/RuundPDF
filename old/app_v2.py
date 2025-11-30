import sys
import fitz
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QPushButton, QFileDialog, QLabel, QHBoxLayout, 
                             QSlider, QGraphicsScene, QGraphicsView, 
                             QGraphicsPixmapItem, QDialog, QTextEdit, 
                             QMessageBox, QToolBar, QFrame, QMenu)
from PyQt6.QtGui import QPixmap, QImage, QIcon, QAction
from PyQt6.QtCore import Qt, QSize
import pyttsx3
import threading

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
                <li>Озвучивание текста (через ПКМ или кнопку)</li>
                <li>Режим Зум (слайдер)</li>
                <li>Поворот страницы на 90, 180, 270 градусов</li>
            </ul>
        """)
        layout.addWidget(info_text)
        
        btn_ok = QPushButton("ОК")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)

        self.setLayout(layout)

class PDFViewerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RuundPDF - Величайший PDF Reader")
        self.setGeometry(100, 100, 1200, 800)
        
        # Устанавливаем иконку приложения
        self.setWindowIcon(QIcon('icon.png'))

        self.document = None
        self.current_page_num = 0
        self.zoom_factor = 1.0
        self.rotation_angle = 0
        self.tts_engine = pyttsx3.init()

        self.initUI()
        self.apply_styles()

    def initUI(self):
        # --- Панель инструментов ---
        toolbar = QToolBar("Основная панель")
        toolbar.setIconSize(QSize(32, 32))
        self.addToolBar(toolbar)

        self.action_open = QAction(QIcon('icon.png'), "Открыть PDF", self) # Используем иконку для кнопки
        self.action_open.triggered.connect(self.open_file)
        toolbar.addAction(self.action_open)

        toolbar.addSeparator()

        self.action_prev = QAction("Пред. стр.", self)
        self.action_prev.triggered.connect(self.prev_page)
        toolbar.addAction(self.action_prev)

        self.page_label = QLabel("Страница: --/--")
        self.page_label.setContentsMargins(10, 0, 10, 0)
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

        # Кнопка озвучки
        self.action_speak = QAction("Озвучить страницу", self)
        self.action_speak.triggered.connect(self.speak_all_text)
        toolbar.addAction(self.action_speak)
        
        toolbar.addSeparator()

        # Кнопка "О программе"
        self.action_about = QAction("О программе", self)
        self.action_about.triggered.connect(self.show_about_dialog)
        toolbar.addAction(self.action_about)


        # --- Основной макет ---
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # --- Панель зума (слайдер) ---
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
        self.view = QGraphicsView(self.scene)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.show_context_menu)
        main_layout.addWidget(self.view)
        
        self.current_pixmap_item = None
        self.disable_controls()

    def apply_styles(self):
        """Функция: Красивый интерфейс (QSS - Qt Style Sheets)."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 12px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QToolBar {
                background-color: #333;
                color: white;
                padding: 5px;
            }
            QLabel {
                color: #333;
            }
            # Это темный стиль для QGraphicsView, чтобы было стильно
            QGraphicsView {
                background-color: #555; 
                border: 1px solid #ccc;
            }
        """)
        # Стили для QLabel на темном тулбаре
        self.page_label.setStyleSheet("color: white;")
        self.zoom_value_label.setStyleSheet("color: #333;")

    def disable_controls(self):
        controls = [self.action_prev, self.action_next, self.action_rotate_left, 
                    self.action_rotate_right, self.action_speak, self.zoom_slider]
        for control in controls:
            control.setEnabled(False)

    def enable_controls(self):
        controls = [self.action_prev, self.action_next, self.action_rotate_left, 
                    self.action_rotate_right, self.action_speak, self.zoom_slider]
        for control in controls:
            control.setEnabled(True)

    def open_file(self):
        """Функция: Окно загрузки файла (plug-and-play) с улучшенной диагностикой."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Открыть PDF файл", "", "PDF Files (*.pdf)")
        if file_path:
            print(f"Попытка открыть файл: {file_path}") # Лог 1
            try:
                self.document = fitz.open(file_path)
                print(f"Файл успешно открыт. Количество страниц: {self.document.page_count}") # Лог 2
                self.current_page_num = 0
                self.rotation_angle = 0
                self.zoom_slider.setValue(100)
                self.render_page()
                self.enable_controls()
                print("Страница отрендерена.") # Лог 3
            except Exception as e:
                # Обработка ошибки открытия файла
                error_message = f"Не удалось открыть файл.\nОшибка: {e}"
                QMessageBox.critical(self, "Ошибка загрузки", error_message)
                print(f"Критическая ошибка при открытии файла: {e}") # Лог 4

    def render_page(self):
        """Отрисовка текущей страницы с учетом зума и поворота (УНИВЕРСАЛЬНАЯ ВЕРСИЯ)."""
        if not self.document:
            return

        page = self.document.load_page(self.current_page_num)
        
        # --- Измененная логика поворота и зума ---
        # Создаем матрицу трансформации: сначала зум, потом поворот
        # Это гарантированно работает с любой версией fitz
        matrix = fitz.Matrix(self.zoom_factor, self.zoom_factor) * fitz.Matrix(self.rotation_angle)
        
        # Рендеринг страницы в Pixmap с использованием матрицы
        # Теперь мы не передаем rotation=... как отдельный аргумент
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        
        # --- Дальше код остается прежним ---
        qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        qpixmap = QPixmap.fromImage(qimage)

        self.scene.clear()
        self.current_pixmap_item = QGraphicsPixmapItem(qpixmap)
        self.scene.addItem(self.current_pixmap_item)
        self.view.setSceneRect(self.current_pixmap_item.boundingRect())
        
        self.page_label.setText(f"Страница: {self.current_page_num + 1}/{self.document.page_count}")

    def next_page(self):
        """Переход на следующую страницу."""
        if self.document and self.current_page_num < self.document.page_count - 1:
            self.current_page_num += 1
            self.render_page()

    def prev_page(self):
        """Переход на предыдущую страницу."""
        if self.document and self.current_page_num > 0:
            self.current_page_num -= 1
            self.render_page()

    def change_zoom(self, value):
        """Функция: Режим зум - увеличение и уменьшение."""
        self.zoom_factor = value / 100.0
        self.zoom_value_label.setText(f"{value}%")
        self.render_page()

    def rotate_page(self, angle_delta):
        """Функция: Поворот страницы взад и вперед на 90 градусов."""
        self.rotation_angle = (self.rotation_angle + angle_delta) % 360
        self.render_page()
    
    def get_selected_text(self):
        """Получение выделенного текста."""
        if not self.document:
            return ""
        page = self.document.load_page(self.current_page_num)
        return page.get_text()

    def show_context_menu(self, pos):
        """Функция: Выделение и копирование текста, Озвучивание текста."""
        context_menu = QMenu(self)
        
        action_copy_all = QAction("Копировать весь текст страницы", self)
        action_copy_all.triggered.connect(self.copy_all_text)
        context_menu.addAction(action_copy_all)

        action_speak_all = QAction("Озвучить весь текст страницы", self)
        action_speak_all.triggered.connect(self.speak_all_text)
        context_menu.addAction(action_speak_all)

        context_menu.exec(self.view.mapToGlobal(pos))

    def copy_all_text(self):
        """Копирует весь текст страницы в буфер обмена."""
        text = self.get_selected_text()
        if text:
            QApplication.clipboard().setText(text)
            print("Текст страницы скопирован в буфер обмена.")
        else:
            print("На странице нет текста для копирования.")

    def speak_all_text(self):
        """Функция: Озвучивание текста (работает в отдельном потоке)."""
        text = self.get_selected_text()
        if text:
            tts_thread = threading.Thread(target=self._run_tts, args=(text,))
            tts_thread.start()
        else:
            print("На странице нет текста для озвучивания.")

    def _run_tts(self, text):
        """Внутренний метод для работы pyttsx3."""
        try:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception as e:
            print(f"Ошибка TTS: {e}")

    def show_about_dialog(self):
        """Функция: Кнопка о программе."""
        about_dialog = AboutDialog(self)
        about_dialog.exec()


if __name__ == '__main__':
    # Убедитесь, что icon.png существует в текущей директории!
    import os
    if not os.path.exists('icon.png'):
        print("ВНИМАНИЕ: Файл icon.png не найден! Интерфейс будет работать, но без иконок.")
    
    app = QApplication(sys.argv)
    ex = PDFViewerApp()
    ex.show()
    sys.exit(app.exec())