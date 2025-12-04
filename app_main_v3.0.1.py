"""
RuundPDF v3.0.0 - PDF Reader с РАБОЧИМ управлением озвучкой и АКТИВНЫМИ ссылками
ИСПРАВЛЕНО: Чтение ВСЕЙ страницы (а не только первых слов)
Author: DeeR Tuund (c) 2025
"""

import sys
import fitz
import os
import threading
import pyttsx3
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QFileDialog,
    QLabel, QHBoxLayout, QSlider, QGraphicsScene, QGraphicsView, QGraphicsPixmapItem,
    QDialog, QTextEdit, QMessageBox, QToolBar, QFrame, QMenu,
    QGroupBox, QRadioButton, QLineEdit, QCheckBox, QInputDialog, QListWidget,
    QProgressBar, QGraphicsRectItem, QTextBrowser
)
from PyQt6.QtGui import (
    QPixmap, QImage, QIcon, QAction, QPainter, QPageLayout, QPageSize,
    QDropEvent, QDragEnterEvent, QFont, QBrush, QColor, QCursor, QTransform, QPen
)
from PyQt6.QtCore import Qt, QSize, QFileInfo, QSettings, QTimer, QRectF, QPointF, QRect, pyqtSignal, QObject, QUrl
from PyQt6.QtPrintSupport import QPrintDialog
from PyQt6.QtGui import QDesktopServices
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0  # Для воспроизводимости результатов

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def create_text_icon(text, size=32):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setPen(Qt.GlobalColor.black)
    painter.setFont(QFont("Segoe UI Symbol", size // 2))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()
    return QIcon(pixmap)

# ============================================================================
# КЛАСС ДЛЯ УПРАВЛЕНИЯ ОЗВУЧКОЙ (ВОССТАНОВЛЕННЫЙ РАБОЧИЙ ВАРИАНТ)
# ============================================================================
class TTSController(QObject):
    """Контроллер для управления озвучкой - ПРОСТОЙ И РАБОЧИЙ"""
    progress = pyqtSignal(int)      # Текущая страница
    started = pyqtSignal()          # Чтение началось
    paused = pyqtSignal()           # Чтение на паузе
    resumed = pyqtSignal()          # Чтение продолжено
    stopped = pyqtSignal()          # Чтение остановлено
    finished = pyqtSignal()         # Чтение завершено
    error = pyqtSignal(str)         # Ошибка
    
    def __init__(self, text_provider, total_pages):
        super().__init__()
        self.text_provider = text_provider
        self.total_pages = total_pages
        
        # Состояние плеера
        self.is_running = False
        self.is_paused = False
        self.should_stop = False
        
        # Текущее состояние чтения
        self.current_page = 0           # Страница, которую сейчас читаем
        self.read_from_page = 0        # Страница, с которой начали читать
        self.read_to_page = total_pages - 1
        
        # Для сохранения позиции при паузе
        self.paused_at_page = None     # На какой странице была пауза
        
        # Чтение в цикле
        self.loop_reading = False
        
        # TTS движок и состояние
        self.tts_engine = None
        self.tts_thread = None
        
        # Для контроля потока чтения
        self.pause_event = threading.Event()
        self.resume_event = threading.Event()
        self.stop_event = threading.Event()
        
    def set_read_range(self, from_page, to_page=None):
        """Устанавливает диапазон чтения"""
        self.read_from_page = max(0, min(from_page, self.total_pages - 1))
        
        if to_page is None:
            self.read_to_page = self.total_pages - 1
        else:
            self.read_to_page = max(self.read_from_page, min(to_page, self.total_pages - 1))
    
    def set_loop_reading(self, loop):
        """Устанавливает режим чтения в цикле"""
        self.loop_reading = loop
    
    def start_reading(self):
        """Начинает чтение"""
        if self.is_running:
            return
        
        self.is_running = True
        self.is_paused = False
        self.should_stop = False
        self.current_page = self.read_from_page
        
        # Сбрасываем флаги
        self.pause_event.clear()
        self.resume_event.clear()
        self.stop_event.clear()
        
        # Запускаем поток чтения
        self.tts_thread = threading.Thread(target=self._read_document)
        self.tts_thread.daemon = True
        self.tts_thread.start()
        
        self.started.emit()
    
    def pause_reading(self):
        """Ставит чтение на паузу - сохраняет текущую страницу"""
        if self.is_running and not self.is_paused:
            self.is_paused = True
            
            # Сохраняем текущую страницу
            self.paused_at_page = self.current_page
            print(f"Пауза на странице {self.paused_at_page + 1}")
            
            # Останавливаем TTS движок
            if self.tts_engine:
                try:
                    self.tts_engine.stop()
                    self.tts_engine.endLoop()
                except:
                    pass
            
            self.pause_event.set()
            self.paused.emit()
            print(f"Чтение ПАУЗА - сохранена страница {self.paused_at_page + 1}")
    
    def resume_reading(self):
        """Продолжает чтение с паузы - с той же страницы"""
        if self.is_running and self.is_paused:
            self.is_paused = False
            
            # Если была сохранена страница паузы, возвращаемся к ней
            if self.paused_at_page is not None:
                self.current_page = self.paused_at_page
                print(f"Продолжение с сохраненной страницы {self.current_page + 1}")
                self.paused_at_page = None
            
            self.pause_event.clear()
            self.resume_event.set()
            self.resumed.emit()
            print("Чтение ПРОДОЛЖЕНО")
    
    def stop_reading(self):
        """Полностью останавливает чтение"""
        if self.is_running:
            self.should_stop = True
            self.is_running = False
            self.is_paused = False
            
            # Устанавливаем все события для выхода из блокировок
            self.stop_event.set()
            self.pause_event.set()
            self.resume_event.set()
            
            # Останавливаем TTS движок
            if self.tts_engine:
                try:
                    self.tts_engine.stop()
                    self.tts_engine.endLoop()  # Добавьте эту строку
                except:
                    pass
                self.tts_engine = None
            
            # Ждем завершения потока
            if self.tts_thread and self.tts_thread.is_alive():
                self.tts_thread.join(timeout=2.0)
            
            self.stopped.emit()
    
    def _read_document(self):
        """Основная функция чтения документа - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            while not self.should_stop:
                # Начинаем с текущей страницы (может быть восстановлена после паузы)
                start_page = self.current_page
                
                # Читаем страницы в заданном диапазоне
                for page_num in range(start_page, self.read_to_page + 1):
                    if self.should_stop:
                        break
                    
                    # Проверяем паузу перед началом чтения страницы
                    if self.pause_event.is_set():
                        print(f"Пауза перед чтением страницы {page_num + 1}")
                        self.resume_event.wait()  # Ждем снятия паузы
                        self.resume_event.clear()
                        
                        # После снятия паузы начинаем снова с этой же страницы
                        if self.should_stop:
                            break
                        
                        # Обновляем текущую страницу (на случай если она изменилась при паузе)
                        page_num = self.current_page
                    
                    # Обновляем текущую страницу
                    self.current_page = page_num
                    self.progress.emit(page_num)
                    
                    # Получаем текст страницы
                    text = self.text_provider(page_num)
                    if not text or not text.strip():
                        continue
                    
                    try:
                        print(f"Чтение страницы {page_num + 1}: {len(text)} символов")
                        
                        # Для каждой страницы создаем НОВЫЙ движок TTS
                        self.tts_engine = pyttsx3.init()
                        self._setup_voice(self.tts_engine)
                        
                        # Читаем ВСЮ страницу целиком
                        self.tts_engine.say(text)
                        self.tts_engine.runAndWait()
                        
                        # Проверяем паузу во время чтения
                        if self.pause_event.is_set():
                            # Пауза во время чтения страницы
                            print(f"Пауза во время чтения страницы {page_num + 1}")
                            # Движок уже остановится автоматически
                            continue
                        
                    except Exception as e:
                        print(f"Ошибка при чтении страницы {page_num}: {e}")
                    
                    finally:
                        # Всегда останавливаем и удаляем движок
                        if self.tts_engine:
                            try:
                                self.tts_engine.stop()
                            except:
                                pass
                            self.tts_engine = None
                    
                    # Небольшая пауза между страницами
                    if not self.should_stop and page_num < self.read_to_page:
                        time.sleep(0.1)
                
                # Если не цикл и не остановка - завершаем
                if not self.loop_reading or self.should_stop:
                    break
                
                # Для цикла - начинаем сначала
                print("Начинаем чтение заново (цикл)")
                self.current_page = self.read_from_page
            
            # Завершаем чтение
            if not self.should_stop:
                self.finished.emit()
            
        except Exception as e:
            self.error.emit(str(e))
        
        finally:
            # Очищаем ресурсы
            if self.tts_engine:
                try:
                    self.tts_engine.stop()
                except:
                    pass
                self.tts_engine = None
            
            self.is_running = False
            self.is_paused = False
    
    def _setup_voice(self, tts_engine):
        """НАДЕЖНЫЙ выбор голоса с понятной логикой и отладкой"""
        settings = QSettings("DeeRTuund", "RuundPDF")
        use_female = settings.value("tts_use_female", False, type=bool)
        auto_lang = settings.value("tts_auto_language", True, type=bool)

        # 1. Определяем язык текста
        text = self._get_current_text()
        language = 'ru'  # По умолчанию русский
        
        if auto_lang and text and text.strip():
            # Простой детект по кириллице
            text_sample = text[:500]
            russian_count = sum(1 for c in text_sample if 'а' <= c.lower() <= 'я' or c == 'ё')
            english_count = sum(1 for c in text_sample if 'a' <= c.lower() <= 'z')
            
            if russian_count > english_count:
                language = 'ru'
            elif english_count > russian_count:
                language = 'en'
            # Если оба счетчика 0 или равны, оставляем язык по умолчанию
        
        print(f"РЕЖИМ: текст={language}, пол={'женский' if use_female else 'мужской'}")

        # 2. Получаем ВСЕ голоса и логируем их
        voices = tts_engine.getProperty('voices')
        print(f"Всего голосов в системе: {len(voices)}")
        for i, v in enumerate(voices):
            print(f"  {i+1:2d}. {v.name}")
            print(f"      ID: {v.id[:60]}...")

        # 3. ИДЕАЛЬНЫЙ ВЫБОР: ищем голос, который ТОЧНО подходит
        selected_voice = None
        
        if language == 'ru' and use_female:
            print("\n→ Ищу русский женский голос (Ирина)...")
            # Ищем Ирину
            for v in voices:
                v_lower = v.name.lower()
                v_id_upper = v.id.upper()
                # Русская Ирина имеет в ID 'TTS_MS_RU-RU_IRINA'
                if ('irina' in v_lower or 'ирина' in v_lower or 
                    'TTS_MS_RU-RU_IRINA' in v_id_upper):
                    selected_voice = v
                    print(f"   ✓ Найдена Ирина: {v.name}")
                    break

        elif language == 'ru' and not use_female:
            print("\n→ Ищу русский мужской голос (Павел/Максим)...")
            # Сначала ищем Павел
            for v in voices:
                v_lower = v.name.lower()
                v_id_upper = v.id.upper()
                if ('pavel' in v_lower or 'павел' in v_lower or 
                    'TTS_MS_RU-RU_PAVEL' in v_id_upper):
                    selected_voice = v
                    print(f"   ✓ Найден Павел: {v.name}")
                    break
            
            # Если Павел не найден, ищем Максим
            if not selected_voice:
                for v in voices:
                    v_lower = v.name.lower()
                    if ('maxim' in v_lower or 'максим' in v_lower):
                        selected_voice = v
                        print(f"   ✓ Найден Максим: {v.name}")
                        break
            
            # КРИТИЧНО: Если русского мужского нет - используем русский женский
            if not selected_voice:
                print("   ⚠️ Русский мужской голос не найден!")
                print("   🔄 Использую русский женский голос (Ирина) как запасной вариант")
                # Ищем Ирину как запасной вариант
                for v in voices:
                    v_lower = v.name.lower()
                    if 'irina' in v_lower or 'ирина' in v_lower:
                        selected_voice = v
                        print(f"   → Запасной: {v.name}")
                        break

        elif language == 'en' and use_female:
            print("\n→ Ищу английский женский голос (Зира)...")
            # Ищем Зиру
            for v in voices:
                v_lower = v.name.lower()
                v_id_upper = v.id.upper()
                if ('zira' in v_lower or 'TTS_MS_EN-US_ZIRA' in v_id_upper):
                    selected_voice = v
                    print(f"   ✓ Найдена Зира: {v.name}")
                    break

        elif language == 'en' and not use_female:
            print("\n→ Ищу английский мужской голос (Дэвид)...")
            # Ищем Дэвида
            for v in voices:
                v_lower = v.name.lower()
                v_id_upper = v.id.upper()
                if ('david' in v_lower or 'TTS_MS_EN-US_DAVID' in v_id_upper):
                    selected_voice = v
                    print(f"   ✓ Найден Дэвид: {v.name}")
                    break

        # 4. Устанавливаем выбранный голос
        if selected_voice:
            try:
                tts_engine.setProperty('voice', selected_voice.id)
                print(f"\n✅ УСТАНОВЛЕН ГОЛОС: {selected_voice.name}")
                
                # Короткий тест произношения
                test_text = "Привет" if language == 'ru' else "Hello"
                print(f"   Тест произношения: '{test_text}'")
                
            except Exception as e:
                print(f"\n❌ Ошибка установки голоса: {e}")
                # Фолбэк на первый голос
                if voices:
                    tts_engine.setProperty('voice', voices[0].id)
                    print(f"   Использую первый доступный голос: {voices[0].name}")
        else:
            print("\n⚠️ Подходящий голос не найден!")
            # Используем первый доступный голос
            if voices:
                tts_engine.setProperty('voice', voices[0].id)
                print(f"   Использую: {voices[0].name}")
            else:
                print("   ❌ Нет доступных голосов!")
        
        print("=" * 60)

    def _detect_language(self, text):
        """Определяет язык текста"""
        if not text or len(text.strip()) < 10:
            return 'ru'  # По умолчанию русский
        
        try:
            # Берем первые 200 символов для определения
            sample = text[:200].strip()
            if sample:
                return detect(sample)
        except:
            pass
        
        return 'ru'  # По умолчанию русский

    def _get_current_text(self):
        """Получает текущий текст для анализа языка"""
        try:
            # Получаем текст текущей страницы
            if hasattr(self, 'text_provider') and hasattr(self, 'current_page'):
                return self.text_provider(self.current_page)
        except:
            pass
        return ""

# ============================================================================
# КЛАССЫ НАСТРОЕК И ПЛЕЕРА (без изменений)
# ============================================================================

class TTSConfigDialog(QDialog):
    """Диалог настроек плеера - ВСЕ настройки здесь"""
    def __init__(self, parent=None, player=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки озвучки")
        self.player = player
        self.setGeometry(300, 300, 400, 350)
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        """Инициализация пользовательского интерфейса"""
        main_layout = QVBoxLayout()
        
        # Группа диапазона чтения
        read_range_group = QGroupBox("Диапазон чтения")
        read_range_layout = QVBoxLayout()
        
        self.radio_current = QRadioButton("С текущей страницы")
        self.radio_only_current = QRadioButton("Только текущая страница")
        self.radio_all = QRadioButton("Весь документ (с начала)")
        self.radio_range = QRadioButton("Произвольный диапазон:")
        
        # Поля для ввода диапазона
        range_layout = QHBoxLayout()
        self.from_label = QLabel("Страница:")
        self.from_edit = QLineEdit()
        self.from_edit.setFixedWidth(50)
        self.to_label = QLabel("до")
        self.to_edit = QLineEdit()
        self.to_edit.setFixedWidth(50)
        self.to_hint = QLabel("(оставьте пустым для чтения до конца)")
        
        range_layout.addWidget(self.from_label)
        range_layout.addWidget(self.from_edit)
        range_layout.addWidget(self.to_label)
        range_layout.addWidget(self.to_edit)
        range_layout.addStretch()
        
        read_range_layout.addWidget(self.radio_current)
        read_range_layout.addWidget(self.radio_only_current)
        read_range_layout.addWidget(self.radio_all)
        read_range_layout.addWidget(self.radio_range)
        read_range_layout.addLayout(range_layout)
        read_range_layout.addWidget(self.to_hint)
        
        read_range_group.setLayout(read_range_layout)
        main_layout.addWidget(read_range_group)

        # Группа выбора голоса
        voice_group = QGroupBox("Настройки голоса")
        voice_layout = QVBoxLayout()
        
        self.radio_male = QRadioButton("Мужской голос")
        self.radio_female = QRadioButton("Женский голос")
        
        voice_layout.addWidget(self.radio_male)
        voice_layout.addWidget(self.radio_female)
        
        voice_group.setLayout(voice_layout)
        main_layout.addWidget(voice_group)

        # Группа языковых настроек (ДОБАВЛЯЕМ ЭТОТ БЛОК)
        language_group = QGroupBox("Языковые настройки")
        language_layout = QVBoxLayout()
        
        self.check_auto_lang = QCheckBox("Автоматическое определение языка")
        self.check_auto_lang.setToolTip("Автоматически определять язык текста и выбирать соответствующий голос")
        self.check_auto_lang.setChecked(True)
        
        language_layout.addWidget(self.check_auto_lang)
        language_group.setLayout(language_layout)
        main_layout.addWidget(language_group)

        
        # Дополнительные настройки
        extra_group = QGroupBox("Дополнительные настройки")
        extra_layout = QVBoxLayout()
        
        self.check_loop = QCheckBox("Чтение в цикле (повтор документа)")
        self.check_loop.setToolTip("После окончания документа начнет читать его снова")
        
        extra_layout.addWidget(self.check_loop)
        extra_group.setLayout(extra_layout)
        main_layout.addWidget(extra_group)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        btn_apply = QPushButton("Применить")
        btn_apply.clicked.connect(self.apply_settings)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_apply)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addStretch()
        
        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)
        
        # Устанавливаем текущий режим чтения
        if hasattr(self.player, 'read_mode'):
            if self.player.read_mode == 'all':
                self.radio_all.setChecked(True)
            elif self.player.read_mode == 'only_current':
                self.radio_only_current.setChecked(True)
            elif self.player.read_mode == 'range':
                self.radio_range.setChecked(True)
            else:
                self.radio_current.setChecked(True)
        
        # Заполняем поля диапазона
        if hasattr(self.player, 'read_from_page'):
            if self.player.read_mode == 'range':
                self.from_edit.setText(str(self.player.read_from_page + 1))
                if self.player.read_to_page != self.player.total_pages - 1:
                    self.to_edit.setText(str(self.player.read_to_page + 1))
                else:
                    self.to_edit.setText("")
            else:
                self.from_edit.setText(str(self.player.current_page + 1))
                self.to_edit.setText("")
        
        # Заполняем чекбокс цикла
        if hasattr(self.player, 'loop_reading'):
            self.check_loop.setChecked(self.player.loop_reading)
    
    def load_settings(self):
        """Загружает настройки из реестра"""
        settings = QSettings("DeeRTuund", "RuundPDF")
        use_female = settings.value("tts_use_female", False, type=bool)
        auto_lang = settings.value("tts_auto_language", True, type=bool)
        
        if use_female:
            self.radio_female.setChecked(True)
        else:
            self.radio_male.setChecked(True)
        
        self.check_auto_lang.setChecked(auto_lang)
    
    def apply_settings(self):
        """Применяет выбранные настройки"""
        # Сохраняем выбор голоса

        settings = QSettings("DeeRTuund", "RuundPDF")
        settings.setValue("tts_use_female", self.radio_female.isChecked())
        settings.setValue("tts_auto_language", self.check_auto_lang.isChecked())

               
        # Устанавливаем режим чтения
        if self.radio_all.isChecked():
            self.player.set_read_mode('all')
        elif self.radio_only_current.isChecked():
            self.player.set_read_mode('only_current')
        elif self.radio_range.isChecked():
            try:
                from_page = int(self.from_edit.text()) - 1
                to_text = self.to_edit.text().strip()
                
                if to_text:
                    to_page = int(to_text) - 1
                else:
                    to_page = None
                
                if 0 <= from_page < self.player.total_pages:
                    self.player.set_read_mode('range', from_page, to_page)
                else:
                    QMessageBox.warning(self, "Ошибка", "Номер страницы вне диапазона.")
                    return
            except ValueError:
                QMessageBox.warning(self, "Ошибка ввода", "Введите корректные номера страниц.")
                return
        else:  # current
            self.player.set_read_mode('current')
        
        # Устанавливаем режим цикла
        self.player.set_loop_reading(self.check_loop.isChecked())
        
        QMessageBox.information(self, "Настройки", "Настройки применены успешно.")
        self.accept()

class TTSPlayerWidget(QWidget):
    """Плеер озвучки - ТОЛЬКО кнопки управления, все настройки в диалоге"""
    def __init__(self, parent=None, text_provider=None, doc_info=None):
        super().__init__(parent)
        self.text_provider = text_provider
        self.total_pages = doc_info['total_pages']
        self.current_page = doc_info['current_page']  # Текущая страница в главном окне
        
        # Связь с главным окном для отслеживания изменений страниц
        self.main_window = parent
        if self.main_window:
            self.main_window.current_page_changed.connect(self.on_main_page_changed)
        
        # Режим чтения (по умолчанию)
        self.read_mode = 'current'  # current, only_current, all, range
        self.read_from_page = self.current_page
        self.read_to_page = self.total_pages - 1
        self.loop_reading = False
        
        # Создаем контроллер
        self.controller = TTSController(text_provider, self.total_pages)
        
        # Подключаем сигналы контроллера
        self.controller.progress.connect(self.on_progress)
        self.controller.started.connect(self.on_started)
        self.controller.paused.connect(self.on_paused)
        self.controller.resumed.connect(self.on_resumed)
        self.controller.stopped.connect(self.on_stopped)
        self.controller.finished.connect(self.on_finished)
        self.controller.error.connect(self.on_error)
        
        self.setup_ui()
        self.setWindowTitle("Плеер озвучки")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.Tool)
        self.setMinimumWidth(400)
        
        # Обновляем информацию
        self.update_display()
    
    def setup_ui(self):
        """Инициализация пользовательского интерфейса - ТОЛЬКО КНОПКИ"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Статус чтения
        self.status_label = QLabel("Готов к чтению")
        self.status_label.setStyleSheet("""
            QLabel {
                font-weight: bold; 
                font-size: 12pt; 
                color: #333333;
                padding: 5px;
            }
        """)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)
        
        # Информация о текущей странице и диапазоне
        self.info_label = QLabel()
        self.info_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 10pt;
                padding: 3px;
            }
        """)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.info_label)
        
        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.total_pages)
        self.progress_bar.setValue(self.current_page + 1)
        main_layout.addWidget(self.progress_bar)
        
        # Кнопки управления (горизонтально)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.btn_start = QPushButton("▶ Начать чтение")
        self.btn_pause = QPushButton("⏸ Пауза")
        self.btn_resume = QPushButton("⏵ Продолжить")
        self.btn_stop = QPushButton("⏹ Остановить")
        
        # Стили кнопок
        button_style = """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QPushButton#pause {
                background-color: #ff9800;
            }
            QPushButton#pause:hover {
                background-color: #e68900;
            }
            QPushButton#stop {
                background-color: #f44336;
            }
            QPushButton#stop:hover {
                background-color: #d32f2f;
            }
        """
        
        self.btn_start.setStyleSheet(button_style)
        self.btn_pause.setStyleSheet(button_style + "QPushButton#pause")
        self.btn_resume.setStyleSheet(button_style)
        self.btn_stop.setStyleSheet(button_style + "QPushButton#stop")
        
        self.btn_start.clicked.connect(self.start_reading)
        self.btn_pause.clicked.connect(self.pause_reading)
        self.btn_resume.clicked.connect(self.resume_reading)
        self.btn_stop.clicked.connect(self.stop_reading)
        
        button_layout.addWidget(self.btn_start)
        button_layout.addWidget(self.btn_pause)
        button_layout.addWidget(self.btn_resume)
        button_layout.addWidget(self.btn_stop)
        
        main_layout.addLayout(button_layout)
        
        # Кнопка настроек (отдельно)
        settings_layout = QHBoxLayout()
        self.btn_settings = QPushButton("⚙ Настройки чтения")
        self.btn_settings.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        self.btn_settings.clicked.connect(self.show_settings)
        settings_layout.addStretch()
        settings_layout.addWidget(self.btn_settings)
        settings_layout.addStretch()
        
        main_layout.addLayout(settings_layout)
        
        # Добавляем растягивающийся элемент
        main_layout.addStretch()
        
        self.setLayout(main_layout)
        self.update_buttons()
    
    def update_display(self):
        """Обновляет отображение информации"""
        # Обновляем информацию о текущей странице
        if self.main_window and self.main_window.document:
            self.current_page = self.main_window.current_page_num
            page_info = f"Текущая страница: {self.current_page + 1} из {self.total_pages}"
            
            # Добавляем информацию о режиме чтения
            if self.read_mode == 'current':
                range_info = f"Чтение: с {self.current_page + 1} до конца"
            elif self.read_mode == 'only_current':
                range_info = f"Чтение: только стр. {self.current_page + 1}"
            elif self.read_mode == 'all':
                range_info = "Чтение: весь документ"
            else:  # range
                to_page = f"{self.read_to_page + 1}" if self.read_to_page != self.total_pages - 1 else "конца"
                range_info = f"Чтение: с {self.read_from_page + 1} до {to_page}"
            
            if self.loop_reading:
                range_info += " (цикл)"
            
            self.info_label.setText(f"{page_info}\n{range_info}")
    
    def on_main_page_changed(self, page_num):
        """Вызывается при изменении страницы в главном окне"""
        self.current_page = page_num
        self.update_display()
    
    def set_read_mode(self, mode, from_page=None, to_page=None):
        """Устанавливает режим чтения"""
        self.read_mode = mode
        
        if mode == 'all':
            self.read_from_page = 0
            self.read_to_page = self.total_pages - 1
        elif mode == 'only_current':
            self.read_from_page = self.current_page
            self.read_to_page = self.current_page
        elif mode == 'range':
            if from_page is not None:
                self.read_from_page = max(0, min(from_page, self.total_pages - 1))
            if to_page is not None:
                self.read_to_page = max(self.read_from_page, min(to_page, self.total_pages - 1))
            else:
                self.read_to_page = self.total_pages - 1
        else:  # 'current'
            self.read_from_page = self.current_page
            self.read_to_page = self.total_pages - 1
        
        self.update_display()
    
    def set_loop_reading(self, loop):
        """Устанавливает режим чтения в цикле"""
        self.loop_reading = loop
        self.controller.set_loop_reading(loop)
        self.update_display()
    
    def update_buttons(self):
        """Обновляет состояние кнопок"""
        is_running = self.controller.is_running
        is_paused = self.controller.is_paused
        
        self.btn_start.setEnabled(not is_running)
        self.btn_pause.setEnabled(is_running and not is_paused)
        self.btn_resume.setEnabled(is_running and is_paused)
        self.btn_stop.setEnabled(is_running)
        
        # Кнопка настроек доступна всегда, кроме времени чтения
        self.btn_settings.setEnabled(not is_running)
    
    def start_reading(self):
        """Начинает чтение"""
        # Устанавливаем диапазон в контроллере
        self.controller.set_read_range(self.read_from_page, self.read_to_page)
        
        # Устанавливаем режим цикла
        self.controller.set_loop_reading(self.loop_reading)
        
        # Запускаем чтение
        self.controller.start_reading()
    
    def pause_reading(self):
        """Ставит чтение на паузу"""
        print("Нажата кнопка ПАУЗА")
        self.controller.pause_reading()
    
    def resume_reading(self):
        """Продолжает чтение с паузы"""
        print("Нажата кнопка ПРОДОЛЖИТЬ")
        self.controller.resume_reading()
    
    def stop_reading(self):
        """Полностью останавливает чтение"""
        print("Нажата кнопка ОСТАНОВИТЬ")
        self.controller.stop_reading()
        self.update_display()
    
    def on_progress(self, page_num):
        """Обновляет прогресс чтения"""
        self.progress_bar.setValue(page_num + 1)
        
        # Если есть главное окно, обновляем текущую страницу в нем
        if self.main_window:
            self.main_window.current_page_num = page_num
            self.main_window.render_page()
    
    def on_started(self):
        """Вызывается при начале чтения"""
        self.status_label.setText("ЧТЕНИЕ...")
        self.status_label.setStyleSheet("color: green; font-weight: bold; font-size: 12pt;")
        self.update_buttons()
    
    def on_paused(self):
        """Вызывается при паузе"""
        self.status_label.setText("ПАУЗА")
        self.status_label.setStyleSheet("color: orange; font-weight: bold; font-size: 12pt;")
        self.update_buttons()
    
    def on_resumed(self):
        """Вызывается при продолжении чтения"""
        self.status_label.setText("ЧТЕНИЕ...")
        self.status_label.setStyleSheet("color: green; font-weight: bold; font-size: 12pt;")
        self.update_buttons()
    
    def on_stopped(self):
        """Вызывается при остановке"""
        self.status_label.setText("ОСТАНОВЛЕНО")
        self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 12pt;")
        self.update_buttons()
    
    def on_finished(self):
        """Вызывается при завершении чтения"""
        self.status_label.setText("ЗАВЕРШЕНО")
        self.status_label.setStyleSheet("color: blue; font-weight: bold; font-size: 12pt;")
        self.controller.is_running = False
        self.update_buttons()
    
    def on_error(self, error_msg):
        """Вызывается при ошибке"""
        self.status_label.setText("ОШИБКА")
        self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 12pt;")
        QMessageBox.warning(self, "Ошибка озвучки", f"Произошла ошибка:\n{error_msg}")
        self.controller.is_running = False
        self.update_buttons()
    
    def show_settings(self):
        """Показывает настройки чтения"""
        dialog = TTSConfigDialog(self, self)
        if dialog.exec():
            # После применения настроек обновляем информацию
            self.update_display()
    
    def closeEvent(self, event):
        """Обработчик закрытия окна - останавливает чтение"""
        self.controller.stop_reading()
        
        # Отключаем сигнал
        if self.main_window:
            try:
                self.main_window.current_page_changed.disconnect(self.on_main_page_changed)
            except:
                pass
        
        event.accept()

# ============================================================================
# КЛАССЫ ПОИСКА И ПРОСМОТРА С АКТИВНЫМИ ССЫЛКАМИ
# ============================================================================

class SearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.search_results = []
        self.current_result = -1
        
        self.setWindowTitle("Поиск в документе")
        self.setGeometry(300, 300, 500, 400)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите текст для поиска...")
        self.btn_search = QPushButton("Найти")
        self.btn_search.clicked.connect(self.perform_search)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.btn_search)
        layout.addLayout(search_layout)
        
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.go_to_result)
        layout.addWidget(self.results_list)
        
        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton("◀ Предыдущий")
        self.btn_next = QPushButton("Следующий ▶")
        self.btn_close = QPushButton("Закрыть")
        
        self.btn_prev.clicked.connect(self.prev_result)
        self.btn_next.clicked.connect(self.next_result)
        self.btn_close.clicked.connect(self.accept)
        
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        nav_layout.addStretch()
        nav_layout.addWidget(self.btn_close)
        
        layout.addLayout(nav_layout)
        self.setLayout(layout)
    
    def perform_search(self):
        search_text = self.search_input.text().strip()
        if not search_text or not self.parent_app.document:
            return
        
        self.search_results = []
        self.results_list.clear()
        
        for page_num in range(self.parent_app.document.page_count):
            page = self.parent_app.document.load_page(page_num)
            text_instances = page.search_for(search_text)
            
            for inst in text_instances:
                self.search_results.append({
                    'page': page_num,
                    'rect': inst,
                    'text': search_text
                })
                
                item_text = f"Страница {page_num + 1}: найдено '{search_text}'"
                self.results_list.addItem(item_text)
        
        if self.search_results:
            self.current_result = 0
            self.highlight_current_result()
            self.parent_app.status_bar.showMessage(f"Найдено результатов: {len(self.search_results)}")
        else:
            self.parent_app.status_bar.showMessage("Текст не найден")
    
    def highlight_current_result(self):
        if not self.search_results or self.current_result < 0:
            return
        
        result = self.search_results[self.current_result]
        self.parent_app.current_page_num = result['page']
        self.parent_app.render_page()
        self.parent_app.highlight_search_result(result['rect'], result['text'])
        self.results_list.setCurrentRow(self.current_result)
    
    def prev_result(self):
        if self.search_results and self.current_result > 0:
            self.current_result -= 1
            self.highlight_current_result()
    
    def next_result(self):
        if self.search_results and self.current_result < len(self.search_results) - 1:
            self.current_result += 1
            self.highlight_current_result()
    
    def go_to_result(self, item):
        row = self.results_list.row(item)
        if 0 <= row < len(self.search_results):
            self.current_result = row
            self.highlight_current_result()

class PDFGraphicsView(QGraphicsView):
    def __init__(self, scene, main_app):
        super().__init__(scene)
        self.main_app = main_app
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setAcceptDrops(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMouseTracking(True)
        
        # Для обработки кликов по ссылкам
        self.clickable_links = []  # Список активных ссылок на текущей странице
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith('.pdf'):
                event.acceptProposedAction()
                self.setStyleSheet("border: 2px dashed blue;")
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet("")
        super().dragLeaveEvent(event)
    
    def dropEvent(self, event):
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
    
    def mousePressEvent(self, event):
        """Обработка кликов по активным ссылкам"""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            scene_pos = self.mapToScene(pos)
            
            # Проверяем, кликнули ли на активную ссылку
            for link in self.clickable_links:
                if link['rect'].contains(scene_pos):
                    print(f"Клик по ссылке: {link['uri']}")
                    # Открываем ссылку в браузере (БЕЗОПАСНО, с обработкой ошибок)
                    try:
                        # Проверяем, является ли ссылка валидным URL
                        url = QUrl(link['uri'])
                        if url.isValid():
                            QDesktopServices.openUrl(url)
                            self.main_app.status_bar.showMessage(f"Открыта ссылка: {link['uri'][:50]}...")
                        else:
                            print(f"Неверный URL: {link['uri']}")
                            self.main_app.status_bar.showMessage(f"Неверная ссылка: {link['uri'][:50]}...")
                    except Exception as e:
                        print(f"Ошибка при открытии ссылки: {e}")
                        self.main_app.status_bar.showMessage("Ошибка при открытии ссылки")
                    return
            
            # Если не кликнули на ссылку, вызываем стандартную обработку
            if self.main_app.is_text_select_mode:
                # Обработка для выделения текста
                self.main_app.selection_start = pos
                self.main_app.selection_end = pos
                self.main_app.selection_rect = None
                self.main_app.selected_text = ""
                self.main_app.action_copy_text.setEnabled(False)
                self.update()
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Обработка движения мыши для выделения текста и показа курсора-ссылки"""
        pos = event.pos()
        scene_pos = self.mapToScene(pos)
        
        # Проверяем, находимся ли над ссылкой
        cursor_over_link = False
        for link in self.clickable_links:
            if link['rect'].contains(scene_pos):
                cursor_over_link = True
                break
        
        # Меняем курсор если над ссылкой
        if cursor_over_link:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        elif self.main_app.is_text_select_mode:
            self.setCursor(Qt.CursorShape.IBeamCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        
        # Стандартная обработка для выделения текста
        if (self.main_app.is_text_select_mode and 
            self.main_app.selection_start is not None and 
            event.buttons() & Qt.MouseButton.LeftButton):
            
            self.main_app.selection_end = event.pos()
            
            x1, y1 = self.main_app.selection_start.x(), self.main_app.selection_start.y()
            x2, y2 = self.main_app.selection_end.x(), self.main_app.selection_end.y()
            self.main_app.selection_rect = QRectF(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
            
            if self.main_app.selection_rect.width() > 5 and self.main_app.selection_rect.height() > 5:
                try:
                    self.main_app.selected_text = self.main_app.get_text_in_rectangle(self.main_app.selection_rect)
                    if self.main_app.selected_text:
                        self.main_app.action_copy_text.setEnabled(True)
                        preview = self.main_app.selected_text[:100] + "..." if len(self.main_app.selected_text) > 100 else self.main_app.selected_text
                        self.main_app.status_bar.showMessage(f"Выделено: {preview}")
                    else:
                        self.main_app.status_bar.showMessage("Выделение... (текст не найден)")
                except Exception as e:
                    print(f"Ошибка при получении текста: {e}")
                    self.main_app.status_bar.showMessage("Ошибка при выделении текста")
            else:
                self.main_app.status_bar.showMessage("Выделение...")
            
            self.update()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Обработка отпускания мыши"""
        if (self.main_app.is_text_select_mode and 
            event.button() == Qt.MouseButton.LeftButton and 
            self.main_app.selection_start is not None):
            
            self.main_app.selection_end = event.pos()
            
            x1, y1 = self.main_app.selection_start.x(), self.main_app.selection_start.y()
            x2, y2 = self.main_app.selection_end.x(), self.main_app.selection_end.y()
            self.main_app.selection_rect = QRectF(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
            
            if self.main_app.selection_rect.width() > 5 and self.main_app.selection_rect.height() > 5:
                try:
                    self.main_app.selected_text = self.main_app.get_text_in_rectangle(self.main_app.selection_rect)
                    if self.main_app.selected_text:
                        self.main_app.action_copy_text.setEnabled(True)
                        char_count = len(self.main_app.selected_text)
                        word_count = len(self.main_app.selected_text.split())
                        self.main_app.status_bar.showMessage(f"Текст выделен: {char_count} символов, {word_count} слов. Ctrl+C для копирования")
                    else:
                        self.main_app.status_bar.showMessage("Текст не найден в выделенной области")
                        self.main_app.clear_selection()
                except Exception as e:
                    print(f"Ошибка при окончательном получении текста: {e}")
                    self.main_app.status_bar.showMessage("Ошибка при выделении текста")
                    self.main_app.clear_selection()
            else:
                self.main_app.clear_selection()
            
            self.update()
        else:
            super().mouseReleaseEvent(event)
    
    def paintEvent(self, event):
        """
        ВОССТАНОВЛЕННЫЙ метод из v2.4.4 - отрисовка выделения текста
        """
        super().paintEvent(event)
        
        # Отрисовка выделения текста
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

# ============================================================================
# ОСНОВНОЙ КЛАСС ПРИЛОЖЕНИЯ С АКТИВНЫМИ ССЫЛКАМИ
# ============================================================================
class PDFViewerApp(QMainWindow):
    # Сигнал изменения текущей страницы
    current_page_changed = pyqtSignal(int)
    
    def __init__(self, file_to_open=None):
        super().__init__()
        self.setWindowTitle("RuundPDF v3.0.1 - PDF Reader с активными ссылками")
        self.setGeometry(100, 100, 1200, 800)
        
        def get_icon_path():
            if getattr(sys, 'frozen', False):
                base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
            else:
                base_path = os.path.abspath(".")
            return os.path.join(base_path, 'icon.png')
        
        self.setWindowIcon(QIcon(get_icon_path()))
        self.setAcceptDrops(True)
        
        # Инициализация переменных
        self.document = None
        self.file_path = None
        self.current_page_num = 0
        self.zoom_factor = 1.0
        self.rotation_angle = 0
        self.bookmarks = {}
        self.tts_player = None
        self.search_dialog = None
        self.is_text_select_mode = True
        self.selection_start = None
        self.selection_end = None
        self.selection_rect = None
        self.text_blocks = []
        self.page_pixmap = None
        self.selected_text = ""
        
        self.search_highlights = []
        self.current_search_highlight = None
        
        # Для активных ссылок
        self.active_links = []  # Ссылки на текущей странице
        
        self.file_to_open_on_start = file_to_open
        
        self.setup_ui()
        self.apply_styles()
        self.disable_controls()
        self.load_bookmarks()
        
        if self.file_to_open_on_start and os.path.exists(self.file_to_open_on_start):
            QTimer.singleShot(100, lambda: self.open_file(self.file_to_open_on_start))
    
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

        # ★ ДОБАВЬТЕ ЭТУ СТРОКУ - Восстановление кнопки "Сохранить как"
        self.action_save_as = QAction(create_text_icon("💽"), "Сохранить как", self)  # Можно использовать другой значок
        self.action_save_as.triggered.connect(self.save_file_as)  # Используем существующий метод
        toolbar.addAction(self.action_save_as)

        toolbar.addSeparator()

        
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
        
        self.action_goto = QAction(create_text_icon("🔢"), "Перейти", self)
        self.action_goto.triggered.connect(self.goto_page_dialog)
        toolbar.addAction(self.action_goto)
        
        self.action_search = QAction(create_text_icon("🔍"), "Поиск", self)
        self.action_search.triggered.connect(self.show_search_dialog)
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
        
        # Меню
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
        
        # Поле просмотра
        self.scene = QGraphicsScene(self)
        self.view = PDFGraphicsView(self.scene, self)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.show_context_menu)
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.view.setCursor(Qt.CursorShape.IBeamCursor)
        
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
        elif event.key() == Qt.Key.Key_F and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.show_search_dialog()
            event.accept()
        elif event.key() == Qt.Key.Key_C and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.copy_selected_text_to_clipboard()
            event.accept()
        else:
            super().keyPressEvent(event)
    
    def show_search_dialog(self):
        if not self.document:
            QMessageBox.warning(self, "Поиск", "Сначала откройте PDF файл.")
            return
        
        if not self.search_dialog:
            self.search_dialog = SearchDialog(self)
        
        self.search_dialog.show()
        self.search_dialog.raise_()
        self.search_dialog.activateWindow()
    
    def highlight_search_result(self, rect, text):
        for item in self.search_highlights:
            self.scene.removeItem(item)
        self.search_highlights.clear()
        
        if hasattr(rect, 'x0') and hasattr(rect, 'y0') and hasattr(rect, 'x1') and hasattr(rect, 'y1'):
            highlight = QGraphicsRectItem(
                rect.x0 * self.zoom_factor,
                rect.y0 * self.zoom_factor,
                (rect.x1 - rect.x0) * self.zoom_factor,
                (rect.y1 - rect.y0) * self.zoom_factor
            )
            
            highlight.setPen(QPen(Qt.PenStyle.NoPen))
            highlight.setBrush(QBrush(QColor(255, 255, 0, 100)))
            
            self.scene.addItem(highlight)
            self.search_highlights.append(highlight)
            self.current_search_highlight = highlight
            
            self.status_bar.showMessage(f"Найден текст: '{text}'")
    
    def goto_page_dialog(self):
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
            # Отправляем сигнал об изменении страницы
            self.current_page_changed.emit(self.current_page_num)
    
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
                self.setWindowTitle(f"RuundPDF v3.0.1 - {QFileInfo(file_path).fileName()} (активные ссылки)")
                self.update_bookmarks_menu()
                self.status_bar.showMessage(f"Загружен: {QFileInfo(file_path).fileName()}")
                
                if self.search_dialog:
                    self.search_dialog.search_results.clear()
                    self.search_dialog.results_list.clear()
                
                # Отправляем сигнал об изменении страницы
                self.current_page_changed.emit(self.current_page_num)
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл: {e}")
    
    def render_page(self):
        if not self.document:
            return
        
        for item in self.search_highlights:
            self.scene.removeItem(item)
        self.search_highlights.clear()
        
        page = self.document.load_page(self.current_page_num)
        matrix = fitz.Matrix(self.zoom_factor, self.zoom_factor) * fitz.Matrix(self.rotation_angle)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        
        qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        self.page_pixmap = QPixmap.fromImage(qimage)
        
        self.scene.clear()
        self.current_pixmap_item = QGraphicsPixmapItem(self.page_pixmap)
        self.scene.addItem(self.current_pixmap_item)
        self.view.setSceneRect(self.current_pixmap_item.boundingRect())
        
        # Получаем активные ссылки с текущей страницы
        self.extract_active_links(page)
        
        # Обновляем список ссылок в view
        self.view.clickable_links = self.active_links.copy()
        
        if self.document:
            self.page_label.setText(f"Страница: {self.current_page_num + 1}/{self.document.page_count}")
        
        # Получаем текстовые блоки для выделения
        self.text_blocks = self.extract_text_with_rectangles(page)
        self.clear_selection()
        
        if self.search_dialog and self.search_dialog.search_results:
            for result in self.search_dialog.search_results:
                if result['page'] == self.current_page_num:
                    self.highlight_search_result(result['rect'], result['text'])
        
        # Перерисовываем view для отображения ссылок
        self.view.update()
        
        # Отправляем сигнал об изменении страницы
        self.current_page_changed.emit(self.current_page_num)
    
    def extract_active_links(self, page):
        """Извлекает активные ссылки с текущей страницы"""
        self.active_links = []
        
        try:
            # Получаем все ссылки с страницы
            links = page.get_links()
            
            for link in links:
                if 'uri' in link:  # Это внешняя ссылка
                    rect = link['from']  # Прямоугольник ссылки
                    
                    # Применяем масштабирование и поворот
                    scaled_rect = QRectF(
                        rect.x0 * self.zoom_factor,
                        rect.y0 * self.zoom_factor,
                        (rect.x1 - rect.x0) * self.zoom_factor,
                        (rect.y1 - rect.y0) * self.zoom_factor
                    )
                    
                    # Применяем поворот
                    if self.rotation_angle != 0:
                        center_x = (scaled_rect.left() + scaled_rect.right()) / 2
                        center_y = (scaled_rect.top() + scaled_rect.bottom()) / 2
                        
                        if self.rotation_angle == 90:
                            new_rect = QRectF(
                                -scaled_rect.top() + center_x + center_y,
                                scaled_rect.left() - center_x + center_y,
                                scaled_rect.height(),
                                scaled_rect.width()
                            )
                            scaled_rect = new_rect
                    
                    self.active_links.append({
                        'rect': scaled_rect,
                        'uri': link['uri'],
                        'type': 'external'
                    })
                
                elif 'page' in link:  # Это внутренняя ссылка на страницу
                    # Можно добавить обработку внутренних ссылок
                    pass
        
        except Exception as e:
            print(f"Ошибка при извлечении ссылок: {e}")
    
    def extract_text_with_rectangles(self, page):
        """Извлечение текста с координатами"""
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
                                center_x = (scaled_bbox[0] + scaled_bbox[2]) / 2
                                center_y = (scaled_bbox[1] + scaled_bbox[3]) / 2
                                
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
    
    def get_text_for_page(self, page_num):
        """ПОЛНОСТЬЮ ПЕРЕРАБОТАННЫЙ МЕТОД - с определением языка"""
        if self.document and 0 <= page_num < self.document.page_count:
            page = self.document.load_page(page_num)
            text = page.get_text()
            
            if text and text.strip():
                # Определяем язык текста
                try:
                    # Берем первые 500 символов для определения языка
                    sample_text = text[:500].strip()
                    if sample_text:
                        language = detect(sample_text)
                        print(f"Страница {page_num + 1}: язык определен как '{language}'")
                        
                        # Добавляем метку языка для TTS (если поддерживается)
                        if language == 'en':
                            text = "[lang en]" + text
                        elif language == 'ru':
                            text = "[lang ru]" + text
                        # Можно добавить другие языки
                except Exception as e:
                    print(f"Не удалось определить язык: {e}")
            
            print(f"Извлечен текст страницы {page_num + 1}: {len(text or '')} символов")
            return text if text and text.strip() else " "
        return " "
    
    def get_text_in_rectangle(self, selection_rect):
        """Получение текста в выделенной области"""
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
            # Отправляем сигнал об изменении страницы
            self.current_page_changed.emit(self.current_page_num)
    
    def prev_page(self):
        if self.document and self.current_page_num > 0:
            self.current_page_num -= 1
            self.render_page()
            # Отправляем сигнал об изменении страницы
            self.current_page_changed.emit(self.current_page_num)
    
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
        self.current_page_num = page_num
        self.render_page()
        # Отправляем сигнал об изменении страницы
        self.current_page_changed.emit(self.current_page_num)
        self.status_bar.showMessage(f"Переход к закладке: {self.bookmarks.get(page_num, '')}")
    
    def manage_bookmarks(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Управление закладками")
        dialog.setGeometry(200, 200, 500, 400)
        
        layout = QVBoxLayout()
        
        self.bookmarks_list = QListWidget()
        
        if not self.bookmarks:
            self.bookmarks_list.addItem("Нет закладок")
            self.bookmarks_list.setEnabled(False)
        else:
            for page_num, name in sorted(self.bookmarks.items()):
                self.bookmarks_list.addItem(f"Страница {page_num + 1}: {name}")
        
        layout.addWidget(QLabel("Ваши закладки:"))
        layout.addWidget(self.bookmarks_list)
        
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
                # Отправляем сигнал об изменении страницы
                self.current_page_changed.emit(self.current_page_num)
                parent_dialog.accept()
                self.status_bar.showMessage(f"Переход к закладке: {self.bookmarks[page_num]}")
            except ValueError:
                QMessageBox.warning(parent_dialog, "Ошибка", "Неверный формат закладки.")
    
    def delete_selected_bookmark(self, parent_dialog):
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
        """Контекстное меню"""
        context_menu = QMenu(self)
        
        if self.selected_text:
            action_copy = QAction(f"Копировать выделенный текст ({len(self.selected_text)} симв.)", self)
            action_copy.triggered.connect(self.copy_selected_text_to_clipboard)
            context_menu.addAction(action_copy)
            context_menu.addSeparator()
        
        action_copy_all = QAction("Копировать весь текст страницы", self)
        action_copy_all.triggered.connect(self.copy_all_text)
        context_menu.addAction(action_copy_all)

        action_speak_all = QAction("Озвучить весь текст страницы", self)
        action_speak_all.triggered.connect(self.show_tts_player) 
        context_menu.addAction(action_speak_all)
        
        context_menu.addSeparator()
        
        action_add_bookmark = QAction("Добавить закладку на эту страницу", self)
        action_add_bookmark.triggered.connect(self.add_bookmark)
        context_menu.addAction(action_add_bookmark)
        
        action_toggle_cursor = QAction("Переключить режим курсора", self)
        action_toggle_cursor.triggered.connect(self.toggle_cursor_mode)
        context_menu.addAction(action_toggle_cursor)
        
        context_menu.exec(self.view.mapToGlobal(pos))
    
    def copy_all_text(self):
        """Копирует весь текст текущей страницы в буфер обмена."""
        text = self.get_text_for_page(self.current_page_num)
        if text:
            QApplication.clipboard().setText(text)
            self.status_bar.showMessage("Весь текст страницы скопирован в буфер обмена")
    
    def toggle_cursor_mode(self):
        """Переключает режим курсора между выделением текста и прокруткой."""
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
    
    def clear_selection(self):
        """Очищает текущее выделение текста."""
        self.selection_start = None
        self.selection_end = None
        self.selection_rect = None
        self.selected_text = ""
        self.action_copy_text.setEnabled(False)
        self.view.update()
    
    def copy_selected_text_to_clipboard(self):
        """Копирует выделенный текст в буфер обмена."""
        if self.selected_text:
            QApplication.clipboard().setText(self.selected_text)
            char_count = len(self.selected_text)
            word_count = len(self.selected_text.split())
            self.status_bar.showMessage(f"Текст скопирован: {char_count} символов, {word_count} слов")
            
            QTimer.singleShot(1000, self.clear_selection)
        else:
            self.status_bar.showMessage("Нет выделенного текста для копирования")
    
    def show_about_dialog(self):
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle("О программе RuundPDF")
        about_dialog.setGeometry(100, 100, 500, 250)
        
        layout = QVBoxLayout()
        
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setHtml("""
            <p align='center'><strong>RuundPDF v3.0.1</strong></p>
            <p align='center'>Права принадлежат © DeeR Tuund 2025</p>
            <p>PDF ридер с АКТИВНЫМИ ССЫЛКАМИ и полностью рабочей озвучкой</p>
            <p><strong>Функции:</strong></p>
            <ul>
                <li>✅ Чтение всего документа и одной страницы, диапазона страниц, циклическое чтение</li>
                <li>✅ Мультиязычная озвучка, муж/жен голоса</li>          
                <li>✅ Пауза/продолжение озвучки </li>
                <li>✅ Активные ссылки в PDF - кликабельные и открываются в браузере</li>
                <li>✅ Все настройки в одном месте (без дублирования)</li>
                <li>✅ Поворот текста</li>
                <li>✅ Закладки</li>
                <li>✅ Копирование текста</li>
                <li>✅ Поиск текста</li>
                <li>✅ Сохранение файла</li>                              
                <li>✅ Безопасное открытие ссылок (с обработкой ошибок)</li>
            </ul>
            <p><strong>Использование:</strong></p>
            <ul>
                <li>Кликните по любой ссылке в PDF - она откроется в браузере</li>
                <li>Курсор меняется на "руку" при наведении на ссылку</li>
                <li>Пауза/продолжение озвучки работает корректно</li>
            </ul>
        """)
        
        layout.addWidget(info_text)
        
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(about_dialog.accept)
        layout.addWidget(btn_ok)
        
        about_dialog.setLayout(layout)
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
