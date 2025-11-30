import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt6.QtCore import Qt

class DragDropTestApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Drag & Drop Test")
        self.setGeometry(100, 100, 400, 300)
        self.setAcceptDrops(True) # Включаем D&D

        self.label = QLabel("Перетащите PDF сюда", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(self.label)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.label.setText("Можно отпускать файл")
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith('.pdf'):
                self.label.setText(f"Файл открыт: {file_path}")
                # Здесь в вашем реальном коде вызывается self.open_file(file_path)
                return
        self.label.setText("Это не PDF файл!")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = DragDropTestApp()
    ex.show()
    sys.exit(app.exec())