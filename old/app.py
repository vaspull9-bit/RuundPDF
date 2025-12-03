import sys
import fitz  # PyMuPDF
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QPushButton, QFileDialog, QLabel, QScrollArea, 
                             QHBoxLayout, QSlider, QFrame, QMenu, QGraphicsScene, 
                             QGraphicsView, QGraphicsPixmapItem)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QCursor, QAction
from PyQt6.QtCore import Qt, QTimer
import pyttsx3
import threading

class PDFViewerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RuundPDF - Величайший PDF Reader")
        self.setGeometry(100, 100, 1200, 800)
        
        self.document = None
        self.current_page_num = 0
        self.zoom_factor = 1.0
        self.rotation_angle = 0 # 0, 90, 180, 270
        self.tts_engine = pyttsx3.init()

        self.initUI()

    def initUI(self):
        # --- Основной макет ---
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # --- Панель инструментов (Кнопки управления) ---
        toolbar_layout = QHBoxLayout()
        
        self.btn_open = QPushButton("Открыть PDF")
        self.btn_open.clicked.connect(self.open_file)
        
        self.btn_prev = QPushButton("Пред. стр.")
        self.btn_prev.clicked.connect(self.prev_page)
        self.page_label = QLabel("Страница: --/--")
        self.btn_next = QPushButton("След. стр.")
        self.btn_next.clicked.connect(self.next_page)

        self.btn_rotate_left = QPushButton("Повернуть влево (90°)")
        self.btn_rotate_left.clicked.connect(lambda: self.rotate_page(-90))
        self.btn_rotate_right = QPushButton("Повернуть вправо (90°)")
        self.btn_rotate_right.clicked.connect(lambda: self.rotate_page(90))

        toolbar_layout.addWidget(self.btn_open)
        toolbar_layout.addWidget(self.btn_prev)
        toolbar_layout.addWidget(self.page_label)
        toolbar_layout.addWidget(self.btn_next)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.btn_rotate_left)
        toolbar_layout.addWidget(self.btn_rotate_right)
        
        main_layout.addLayout(toolbar_layout)

        # --- Панель зума (слайдер) ---
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Зум:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(50) # 0.5x
        self.zoom_slider.setMaximum(300) # 3.0x
        self.zoom_slider.setValue(100) # 1.0x
        self.zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.zoom_slider.setTickInterval(25)
        self.zoom_slider.valueChanged.connect(self.change_zoom)
        self.zoom_value_label = QLabel("100%")
        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addWidget(self.zoom_value_label)
        main_layout.addLayout(zoom_layout)

        # --- Область отображения PDF ---
        # Используем QGraphicsView для лучшей обработки масштабирования и поворотов
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag) # Перетаскивание мышкой
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.show_context_menu)
        main_layout.addWidget(self.view)
        
        self.current_pixmap_item = None
        self.disable_controls()

    def disable_controls(self):
        """Отключает кнопки до загрузки файла."""
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.btn_rotate_left.setEnabled(False)
        self.btn_rotate_right.setEnabled(False)
        self.zoom_slider.setEnabled(False)

    def enable_controls(self):
        """Включает кнопки после загрузки файла."""
        self.btn_prev.setEnabled(True)
        self.btn_next.setEnabled(True)
        self.btn_rotate_left.setEnabled(True)
        self.btn_rotate_right.setEnabled(True)
        self.zoom_slider.setEnabled(True)

    def open_file(self):
        """Функция: Открытие PDF файла."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Открыть PDF файл", "", "PDF Files (*.pdf)")
        if file_path:
            try:
                self.document = fitz.open(file_path)
                self.current_page_num = 0
                self.rotation_angle = 0
                self.zoom_slider.setValue(100)
                self.zoom_factor = 1.0
                self.render_page()
                self.enable_controls()
            except Exception as e:
                print(f"Ошибка при открытии файла: {e}")

    def render_page(self):
        """Отрисовка текущей страницы с учетом зума и поворота."""
        if not self.document:
            return

        page = self.document.load_page(self.current_page_num)
        
        # Создаем матрицу трансформации для зума и поворота
        # Угол поворота должен быть в градусах для матрицы fitz
        matrix = fitz.Matrix(self.zoom_factor, self.zoom_factor) * fitz.Matrix(1, 0, 0, 1, 0, 0, self.rotation_angle)
        
        # Рендеринг страницы в Pixmap
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        
        # Преобразование Pixmap в формат, понятный PyQt6
        qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        qpixmap = QPixmap.fromImage(qimage)

        # Отображение в QGraphicsView
        self.scene.clear()
        self.current_pixmap_item = QGraphicsPixmapItem(qpixmap)
        self.scene.addItem(self.current_pixmap_item)
        self.view.setSceneRect(self.current_pixmap_item.boundingRect())
        
        # Обновление метки страницы
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
        """Получение выделенного текста (базовая реализация)."""
        if not self.document:
            return ""
        
        # В реальном приложении QGraphicsView требует сложной логики для 
        # точного определения координат выделения на повернутом/масштабированном изображении.
        # Для простоты, этот метод просто возвращает весь текст текущей страницы.
        # Более точное выделение требует глубокой интеграции с API PyQt selection tools.
        
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
            # Запускаем озвучивание в отдельном потоке, чтобы не блокировать GUI
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


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = PDFViewerApp()
    ex.show()
    sys.exit(app.exec())