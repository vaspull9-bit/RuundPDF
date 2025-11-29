import pyttsx3
import threading
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QSlider, QLabel, QDialog, QLineEdit, QRadioButton, 
                             QGroupBox, QFormLayout, QDialogButtonBox, 
                             QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal, QObject

class TTSPlayer(QObject):
    """Класс, управляющий логикой TTS в отдельном потоке."""
    # Сигнал для обновления интерфейса (например, когда озвучка завершена)
    finished = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.engine = pyttsx3.init()
        self._text_queue = []
        self._current_page = 0
        self._total_pages = 0
        self._is_playing = False
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._thread = None
        self._voice_id = None
        self._read_mode = 'all' # 'all', 'current', 'from'

        self._load_settings()

    def _load_settings(self):
        # Базовые настройки голоса (мужской/женский определяется при запуске)
        voices = self.engine.getProperty('voices')
        # Попытка найти женский голос по умолчанию
        self._voice_id = next((v.id for v in voices if 'female' in v.name.lower()), voices[0].id)
        self.engine.setProperty('voice', self._voice_id)

    def set_content(self, text_list, start_page=0):
        self._text_queue = text_list
        self._total_pages = len(text_list)
        self._current_page = start_page

    def play(self):
        if not self._text_queue:
            return

        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._pause_event.clear()
            self._thread = threading.Thread(target=self._run)
            self._thread.start()
            self._is_playing = True
        elif self._is_playing is False:
            self.resume()

    def _run(self):
        while self._current_page < self._total_pages and not self._stop_event.is_set():
            if self._pause_event.is_set():
                self._pause_event.wait()
            
            text = self._text_queue[self._current_page]
            self.engine.say(text)
            self.engine.runAndWait()
            
            if self._read_mode == 'current':
                self.stop()
                break
            
            self._current_page += 1

        self._is_playing = False
        self.finished.emit()

    def pause(self):
        self._pause_event.set()
        self._is_playing = False
        self.engine.stop() # Остановка текущей фразы

    def resume(self):
        self._pause_event.clear()
        self._is_playing = True

    def stop(self):
        self._stop_event.set()
        self._is_playing = False
        self.engine.stop()

    def next_page(self):
        if self._current_page < self._total_pages - 1:
            self._current_page += 1
            self.play() # Начать читать с новой страницы

    def prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self.play()

    def first_page(self):
        self._current_page = 0
        self.play()

    def last_page(self):
        self._current_page = self._total_pages - 1
        self.play()

    def get_status(self):
        return self._is_playing, self._current_page + 1, self._total_pages

# Класс виджета для интерфейса плеера
class PlayerWidget(QWidget):
    def __init__(self, tts_player_logic, parent=None):
        super().__init__(parent)
        self.player_logic = tts_player_logic
        self.initUI()
        self.player_logic.finished.connect(self.update_ui_on_finish)

    def initUI(self):
        layout = QHBoxLayout()
        self.btn_first = QPushButton("|<")
        self.btn_prev = QPushButton("<")
        self.btn_play_pause = QPushButton("Play")
        self.btn_stop = QPushButton("Stop")
        self.btn_next = QPushButton(">")
        self.btn_last = QPushButton(">|")
        self.btn_settings = QPushButton("Настройки")
        self.status_label = QLabel("Готов")

        self.btn_first.clicked.connect(self.player_logic.first_page)
        self.btn_prev.clicked.connect(self.player_logic.prev_page)
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        self.btn_stop.clicked.connect(self.stop_playback)
        self.btn_next.clicked.connect(self.player_logic.next_page)
        self.btn_last.clicked.connect(self.player_logic.last_page)
        self.btn_settings.clicked.connect(self.show_settings)

        layout.addWidget(self.btn_first)
        layout.addWidget(self.btn_prev)
        layout.addWidget(self.btn_play_pause)
        layout.addWidget(self.btn_stop)
        layout.addWidget(self.btn_next)
        layout.addWidget(self.btn_last)
        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(self.btn_settings)

        self.setLayout(layout)
        self.update_ui_state()

    def toggle_play_pause(self):
        is_playing, _, _ = self.player_logic.get_status()
        if is_playing:
            self.player_logic.pause()
            self.btn_play_pause.setText("Play")
        else:
            self.player_logic.play()
            self.btn_play_pause.setText("Pause")
        self.update_ui_state()
    
    def stop_playback(self):
        self.player_logic.stop()
        self.btn_play_pause.setText("Play")
        self.update_ui_state()

    def update_ui_on_finish(self):
        self.btn_play_pause.setText("Play")
        self.update_ui_state()

    def update_ui_state(self):
        is_playing, current, total = self.player_logic.get_status()
        status_text = f"Страница {current}/{total} ({'Играет' if is_playing else 'Пауза/Стоп'})"
        if total == 0:
            status_text = "Нет контента"
        self.status_label.setText(status_text)
    
    def show_settings(self):
        settings_dialog = SettingsDialog(self.player_logic, self)
        settings_dialog.exec()

# Класс диалога настроек плеера
class SettingsDialog(QDialog):
    def __init__(self, player_logic, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки озвучки")
        self.player_logic = player_logic
        layout = QVBoxLayout()

        # Режим чтения
        mode_group = QGroupBox("Режим чтения")
        mode_layout = QVBoxLayout()
        
        self.rb_all = QRadioButton("Читать от начала до конца")
        self.rb_current = QRadioButton("Читать только текущую страницу")
        self.rb_from = QRadioButton("Читать со страницы номер:")
        self.le_from_page = QLineEdit()
        self.le_from_page.setValidator(QIntValidator(1, 9999, self))
        
        mode_layout.addWidget(self.rb_all)
        mode_layout.addWidget(self.rb_current)
        
        from_layout = QHBoxLayout()
        from_layout.addWidget(self.rb_from)
        from_layout.addWidget(self.le_from_page)
        from_layout.addStretch()
        mode_layout.addLayout(from_layout)
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # Выбор голоса (муж/жен)
        voice_group = QGroupBox("Выбор голоса")
        voice_layout = QFormLayout()
        self.cb_voices = QComboBox()
        voices = self.player_logic.engine.getProperty('voices')
        for voice in voices:
            gender = "Мужской" if voice.gender == 'male' else "Женский"
            self.cb_voices.addItem(f"{voice.name} ({gender})", userData=voice.id)
        
        # Выбираем текущий голос
        self.cb_voices.setCurrentIndex(self.cb_voices.findData(self.player_logic._voice_id))

        voice_layout.addRow("Голос:", self.cb_voices)
        voice_group.setLayout(voice_layout)
        layout.addWidget(voice_group)


        # Кнопки ОК/Отмена
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)
        self.load_current_settings_ui()

    def load_current_settings_ui(self):
        mode = self.player_logic._read_mode
        if mode == 'all':
            self.rb_all.setChecked(True)
        elif mode == 'current':
            self.rb_current.setChecked(True)
        elif mode == 'from':
            self.rb_from.setChecked(True)
        
        _, current_page, _ = self.player_logic.get_status()
        self.le_from_page.setText(str(current_page))

    def save_settings(self):
        if self.rb_all.isChecked():
            self.player_logic._read_mode = 'all'
        elif self.rb_current.isChecked():
            self.player_logic._read_mode = 'current'
        elif self.rb_from.isChecked():
            self.player_logic._read_mode = 'from'
            try:
                start_page = int(self.le_from_page.text())
                if 1 <= start_page <= self.player_logic._total_pages:
                    self.player_logic._current_page = start_page - 1
            except ValueError:
                pass # Игнорируем неверный ввод
        
        # Сохраняем выбранный голос
        self.player_logic._voice_id = self.cb_voices.currentData()
        self.player_logic.engine.setProperty('voice', self.player_logic._voice_id)

        self.accept()