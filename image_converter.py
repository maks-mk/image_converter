import argparse
from PIL import Image
import os
import logging
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, 
                            QFileDialog, QMessageBox, QProgressBar, QFrame, QSizePolicy, QGridLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QFont, QPainter, QDragEnterEvent, QDropEvent
# import qtawesome as qta  # Отключено для стабильности

# Configure logging
logging.basicConfig(filename='image_converter.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class ConversionWorker(QThread):
    """Worker thread for image conversion"""
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    conversion_finished = pyqtSignal(bool, str)
    
    def __init__(self, input_path, output_path):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
    
    def run(self):
        try:
            self.status_updated.emit("Начинаем конвертацию...")
            self.progress_updated.emit(20)
            
            if not os.path.exists(self.input_path):
                raise FileNotFoundError(f"Входной файл не найден: {self.input_path}")
            
            self.progress_updated.emit(40)
            img = Image.open(self.input_path)
            
            self.progress_updated.emit(60)
            if self.output_path.lower().endswith('.ico'):
                ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
                img.save(self.output_path, format='ICO', sizes=ico_sizes)
            else:
                img.save(self.output_path)
            
            self.progress_updated.emit(100)
            self.status_updated.emit("Конвертация завершена успешно!")
            logging.info(f"Successfully converted '{self.input_path}' to '{self.output_path}'")
            self.conversion_finished.emit(True, "Изображение успешно конвертировано!")
            
        except Exception as e:
            error_msg = f"Ошибка при конвертации: {str(e)}"
            logging.error(f"An error occurred during conversion: {e}")
            self.status_updated.emit("Ошибка конвертации")
            self.conversion_finished.emit(False, error_msg)

def convert_image(input_path, output_path):
    """Legacy function for CLI compatibility"""
    if not os.path.exists(input_path):
        logging.error(f"Input file not found at '{input_path}'")
        return

    try:
        img = Image.open(input_path)
        
        if output_path.lower().endswith('.ico'):
            ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
            img.save(output_path, format='ICO', sizes=ico_sizes)
        else:
            img.save(output_path)
            
        logging.info(f"Successfully converted '{input_path}' to '{output_path}'")

    except Exception as e:
        logging.error(f"An error occurred during conversion: {e}")
        raise e

class ImageConverterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🖼️ Конвертер изображений")
        self.setGeometry(250, 50, 750, 650)
        self.setMinimumSize(650, 550)
        self.setAcceptDrops(True)
        
        self.input_path = ""
        self.output_path = ""
        
        self.original_image = None
        self.conversion_worker = None
        
        self.setup_dark_theme()
        self.setup_ui()
        self.setup_icons()

        self.resizeEvent = self.on_window_resize

    def setup_dark_theme(self):
        """Настройка темной темы"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QWidget {
                background-color: #1a1a1a;
                color: #ffffff;
                font-size: 13px;
            }
            QFrame {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
                padding: 12px;
            }
            QLabel {
                background-color: transparent;
                color: #ffffff;
                padding: 5px;
                font-size: 13px;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 14px;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #1e88e5;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #3a3a3a;
                color: #808080;
            }
            QProgressBar {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                text-align: center;
                background-color: #252525;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                  stop:0 #0078d4, stop:1 #1e88e5);
                border-radius: 7px;
            }
        """)

    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 6, 8, 6)
        main_layout.setSpacing(4)
        
        self.create_header(main_layout)
        self.create_file_selection_section(main_layout)
        self.create_preview_section(main_layout)
        self.create_conversion_section(main_layout)
        
        # Растягивающийся элемент убран, так как preview_frame теперь расширяется
        # main_layout.addStretch()

    def create_header(self, parent_layout):
        """Создание заголовка"""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.NoFrame)
        header_frame.setStyleSheet("QFrame { border: none; background: transparent; padding: 0px; }")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setSpacing(0)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("🖼️ Конвертер изображений")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("padding: 2px;")
        
        header_layout.addWidget(title_label)
        parent_layout.addWidget(header_frame)

    def create_file_selection_section(self, parent_layout):
        """Создание компактной секции выбора файлов в одну строку"""
        files_frame = QFrame()
        files_frame.setStyleSheet("QFrame { padding: 4px; }")
        files_layout = QHBoxLayout(files_frame)
        files_layout.setContentsMargins(6, 3, 6, 3)
        files_layout.setSpacing(4)
        
        # Входной файл
        input_icon = QLabel("📁")
        input_icon.setStyleSheet("font-size: 14px; padding: 0px;")
        input_icon.setFixedWidth(18)
        
        self.input_path_label = QLabel("Выберите файл")
        self.input_path_label.setStyleSheet("""
            color: #888888; 
            padding: 3px 6px; 
            background-color: #2d2d2d; 
            border: 1px solid #404040; 
            border-radius: 4px; 
            font-size: 9px;
        """)
        self.input_path_label.setMaximumWidth(200)
        
        self.input_browse_btn = QPushButton("Открыть")
        self.input_browse_btn.clicked.connect(self.browse_input_file)
        self.input_browse_btn.setStyleSheet("font-size: 9px; padding: 3px 8px; min-height: 22px;")
        self.input_browse_btn.setMaximumWidth(70)
        
        # Разделитель
        separator = QLabel("|")
        separator.setStyleSheet("color: #404040; font-size: 12px; padding: 0 4px;")
        
        # Выходной файл
        output_icon = QLabel("💾")
        output_icon.setStyleSheet("font-size: 14px; padding: 0px;")
        output_icon.setFixedWidth(18)
        
        self.output_path_label = QLabel("Сохранить как")
        self.output_path_label.setStyleSheet("""
            color: #888888; 
            padding: 3px 6px; 
            background-color: #2d2d2d; 
            border: 1px solid #404040; 
            border-radius: 4px; 
            font-size: 9px;
        """)
        self.output_path_label.setMaximumWidth(200)
        
        self.output_browse_btn = QPushButton("Сохранить")
        self.output_browse_btn.clicked.connect(self.browse_output_file)
        self.output_browse_btn.setStyleSheet("font-size: 9px; padding: 3px 8px; min-height: 22px;")
        self.output_browse_btn.setMaximumWidth(70)
        
        # Добавление элементов в одну строку
        files_layout.addWidget(input_icon)
        files_layout.addWidget(self.input_path_label, 1)
        files_layout.addWidget(self.input_browse_btn)
        files_layout.addWidget(separator)
        files_layout.addWidget(output_icon)
        files_layout.addWidget(self.output_path_label, 1)
        files_layout.addWidget(self.output_browse_btn)
        
        parent_layout.addWidget(files_frame)

    def create_preview_section(self, parent_layout):
        """Создание адаптивной секции предпросмотра"""
        preview_frame = QFrame()
        preview_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        preview_frame.setStyleSheet("""
            QFrame {
                background-color: #1f1f1f;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(3)

        preview_header = QLabel("🖼️ Превью")
        preview_header.setStyleSheet("font-weight: bold; font-size: 9px; background: transparent; border: none; padding: 2px;")
        preview_layout.addWidget(preview_header)

        self.preview_image_label = QLabel()
        self.preview_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image_label.setScaledContents(False)
        self.preview_image_label.setContentsMargins(0, 0, 0, 0)
        self.preview_image_label.setStyleSheet("""
            QLabel {
                background-color: #252525;
                border: 1px dashed #444444;
                border-radius: 4px;
                color: #888888;
                font-size: 10px;
                padding: 10px;
            }
        """)
        self.preview_image_label.setText("🖼️ Перетащите изображение\nили выберите файл")
        self.preview_image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        preview_layout.addWidget(self.preview_image_label, 1)

        self.image_info_label = QLabel("")
        self.image_info_label.setStyleSheet("color: #60a5fa; font-size: 8px; background: transparent; border: none; padding: 2px;")
        self.image_info_label.setWordWrap(True)
        self.image_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.image_info_label)

        parent_layout.addWidget(preview_frame, 1)

    def create_conversion_section(self, parent_layout):
        """Создание секции конвертации"""
        conversion_frame = QFrame()
        conversion_frame.setStyleSheet("QFrame { border: none; background: transparent; }")
        conversion_layout = QVBoxLayout(conversion_frame)
        conversion_layout.setContentsMargins(0, 2, 0, 0)
        conversion_layout.setSpacing(3)

        self.convert_btn = QPushButton("⚡ Конвертировать")
        self.convert_btn.clicked.connect(self.convert_image_threaded)
        self.convert_btn.setEnabled(False)
        self.convert_btn.setMinimumHeight(28)
        self.convert_btn.setStyleSheet("font-size: 10px; padding: 4px 12px;")
        conversion_layout.addWidget(self.convert_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setVisible(False)
        conversion_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Готов к работе")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #888888; font-size: 8px; padding: 2px;")
        conversion_layout.addWidget(self.status_label)

        parent_layout.addWidget(conversion_frame)

    def setup_icons(self):
        """Настройка иконок"""
        QTimer.singleShot(100, self._setup_icons_delayed)

    def _setup_icons_delayed(self):
        """Отложенная установка иконок"""
        logging.info("QtAwesome icons disabled for stability")
        pass
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Обработка перетаскивания файла в окно"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.preview_image_label.setStyleSheet("""
                QLabel {
                    background-color: #2d2d2d;
                    border: 1px dashed #0078d4;
                    border-radius: 4px;
                    color: #0078d4;
                    font-size: 10px;
                    padding: 10px;
                }
            """)
    
    def dragLeaveEvent(self, event):
        """Обработка выхода курсора за пределы окна при перетаскивании"""
        if not self.original_image:
            self.preview_image_label.setStyleSheet("""
                QLabel {
                    background-color: #252525;
                    border: 1px dashed #444444;
                    border-radius: 4px;
                    color: #888888;
                    font-size: 10px;
                    padding: 10px;
                }
            """)
    
    def dropEvent(self, event: QDropEvent):
        """Обработка отпускания файла в окно"""
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        if files:
            file_path = files[0]
            # Проверяем, что это изображение
            valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp', '.ico')
            if file_path.lower().endswith(valid_extensions):
                self.input_path = file_path
                display_name = os.path.basename(file_path)
                self.input_path_label.setText(display_name)
                self.input_path_label.setToolTip(file_path)
                self.input_path_label.setStyleSheet("""
                    color: #ffffff; 
                    padding: 3px 6px; 
                    background-color: #2d2d2d; 
                    border: 1px solid #0078d4; 
                    border-radius: 4px; 
                    font-size: 9px;
                """)
                self.status_label.setText("✅ Файл выбран")
                self.status_label.setStyleSheet("color: #10b981; font-size: 8px;")
                
                self.load_preview_image(file_path)
                self.update_convert_button_state()
            else:
                QMessageBox.warning(self, "Неверный формат", "Пожалуйста, перетащите файл изображения (PNG, JPG, GIF и т.д.)")
        
        event.acceptProposedAction()

    def on_window_resize(self, event):
        """Обработчик изменения размеров окна"""
        super().resizeEvent(event)
        # Обновляем превью при любом изменении размера окна
        if hasattr(self, 'original_image') and self.original_image:
            self.update_preview_image_size()

    def update_preview_image_size(self):
        """Обновление размера изображения превью"""
        if not self.original_image:
            return

        try:
            # Масштабируем оригинальное изображение под размер QLabel
            scaled_pixmap = QPixmap.fromImage(self.original_image_qt).scaled(
                self.preview_image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.preview_image_label.setPixmap(scaled_pixmap)
        except Exception as e:
            logging.error(f"Error updating preview image size: {e}")

    def browse_input_file(self):
        """Выбор входного файла"""
        file_filter = "Изображения (*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.webp);;Все файлы (*.*)"
        filename, _ = QFileDialog.getOpenFileName(self, "Выберите изображение", "", file_filter)

        if filename:
            self.input_path = filename
            display_name = os.path.basename(filename)
            self.input_path_label.setText(display_name)
            self.input_path_label.setToolTip(filename)
            self.input_path_label.setStyleSheet("""
                color: #ffffff; 
                padding: 3px 6px; 
                background-color: #2d2d2d; 
                border: 1px solid #0078d4; 
                border-radius: 4px; 
                font-size: 9px;
            """)
            self.status_label.setText("✅ Файл выбран")
            self.status_label.setStyleSheet("color: #10b981; font-size: 8px;")

            self.load_preview_image(filename)
            self.update_convert_button_state()

    def browse_output_file(self):
        """Выбор выходного файла с автоматическим добавлением расширения."""
        file_filter = "PNG (*.png);;JPEG (*.jpg);;ICO (*.ico);;GIF (*.gif);;BMP (*.bmp);;TIFF (*.tiff);;WebP (*.webp)"
        
        # Предлагаем имя файла по умолчанию на основе входного файла
        default_name = ""
        if self.input_path:
            base_name = os.path.splitext(os.path.basename(self.input_path))[0]
            default_name = f"{base_name}_converted"

        filename, selected_filter = QFileDialog.getSaveFileName(
            self, 
            "Сохранить как", 
            default_name, 
            file_filter
        )

        if filename:
            # Извлекаем расширение из выбранного фильтра
            # Пример фильтра: "PNG (*.png)" -> ".png"
            import re
            ext_match = re.search(r'\(\*\.(.*?)\)', selected_filter)
            if ext_match:
                ext = f".{ext_match.group(1)}"
                # Добавляем расширение, если его нет
                if not filename.lower().endswith(ext):
                    filename += ext
            
            self.output_path = filename
            display_name = os.path.basename(filename)
            self.output_path_label.setText(display_name)
            self.output_path_label.setToolTip(filename)
            self.output_path_label.setStyleSheet("""
                color: #ffffff; 
                padding: 3px 6px; 
                background-color: #2d2d2d; 
                border: 1px solid #0078d4; 
                border-radius: 4px; 
                font-size: 9px;
            """)
            self.status_label.setText("✅ Готово")
            self.status_label.setStyleSheet("color: #10b981; font-size: 8px;")
            self.update_convert_button_state()

    def update_convert_button_state(self):
        """Обновление состояния кнопки конвертации"""
        if self.input_path and self.output_path:
            self.convert_btn.setEnabled(True)
            self.status_label.setText("🚀 Готово!")
            self.status_label.setStyleSheet("color: #0078d4; font-size: 8px;")
        else:
            self.convert_btn.setEnabled(False)

    def load_preview_image(self, image_path):
        """Загружает и отображает предпросмотр изображения"""
        try:
            from PyQt6.QtGui import QImage
            self.original_image_qt = QImage(image_path)
            if self.original_image_qt.isNull():
                raise ValueError("Не удалось загрузить изображение с помощью Qt")
            
            # Получаем информацию через Pillow для надежности
            with Image.open(image_path) as img:
                width, height = img.size
                format_name = img.format or "Unknown"
                mode = img.mode

            file_size = os.path.getsize(image_path)
            size_str = f"{file_size / 1024:.1f} КБ" if file_size >= 1024 else f"{file_size} байт"
            if file_size >= 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.1f} МБ"

            info_text = f"📏 {width}×{height}  •  📁 {format_name}  •  💾 {size_str}  •  🎨 {mode}"
            self.image_info_label.setText(info_text)
            self.image_info_label.setStyleSheet("color: #60a5fa; font-size: 8px; background: transparent; border: none; padding: 2px;")

            self.original_image = True # Флаг, что изображение загружено
            self.update_preview_image_size() # Первичное отображение
            
            self.preview_image_label.setStyleSheet("""
                QLabel {
                    background-color: #252525;
                    border: 1px solid #0078d4;
                    border-radius: 4px;
                    padding: 5px;
                }
            """)
            self.status_label.setText("🖼️ Загружено")
            self.status_label.setStyleSheet("color: #10b981; font-size: 8px;")

        except Exception as e:
            error_msg = f"❌ Ошибка загрузки:\n{str(e)}"
            self.preview_image_label.clear()
            self.preview_image_label.setText(error_msg)
            self.preview_image_label.setStyleSheet("""
                QLabel {
                    background-color: #252525;
                    border: 1px dashed #ef4444;
                    border-radius: 4px;
                    color: #ef4444;
                    font-size: 10px;
                    padding: 10px;
                }
            """)
            self.image_info_label.setText("")
            self.status_label.setText("❌ Ошибка")
            self.status_label.setStyleSheet("color: #ef4444; font-size: 8px;")
            logging.error(f"Error loading preview image: {e}")
            self.original_image = None

    def convert_image_threaded(self):
        """Запуск конвертации в отдельном потоке"""
        if not self.input_path or not self.output_path:
            QMessageBox.critical(self, "Ошибка", "Пожалуйста, выберите входной и выходной файлы.")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.convert_btn.setEnabled(False)
        self.status_label.setText("⚡ Конвертация...")
        self.status_label.setStyleSheet("color: #f59e0b; font-size: 8px;")

        self.conversion_worker = ConversionWorker(self.input_path, self.output_path)
        self.conversion_worker.progress_updated.connect(self.progress_bar.setValue)
        self.conversion_worker.status_updated.connect(self.update_status)
        self.conversion_worker.conversion_finished.connect(self.on_conversion_finished)
        self.conversion_worker.start()

    def update_status(self, status_text):
        """Обновление статуса"""
        self.status_label.setText(status_text)

    def on_conversion_finished(self, success, message):
        """Обработка завершения конвертации"""
        self.progress_bar.setVisible(False)
        self.convert_btn.setEnabled(True)

        if success:
            self.status_label.setText("🎉 Успешно!")
            self.status_label.setStyleSheet("color: #10b981; font-size: 8px;")
            QMessageBox.information(self, "Успех", message)
        else:
            self.status_label.setText("❌ Ошибка")
            self.status_label.setStyleSheet("color: #ef4444; font-size: 8px;")
            QMessageBox.critical(self, "Ошибка", message)

    def run(self):
        """Запуск GUI приложения"""
        self.show()
        return QApplication.instance().exec()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert an image from one format to another.",
        epilog="Example: image_converter.py image.png image.jpg"
    )
    parser.add_argument("input_file", nargs='?', help="The path to the input image file.")
    parser.add_argument("output_file", nargs='?', help="The path to save the output image file.")
    parser.add_argument("--gui", action="store_true", help="Launch GUI mode")
    args = parser.parse_args()

    if args.gui or (not args.input_file and not args.output_file):
        try:
            app = QApplication(sys.argv)
            app.setStyle('Fusion')
            window = ImageConverterGUI()
            sys.exit(window.run())
        except ImportError as e:
            print(f"Ошибка: Не установлены необходимые библиотеки: {e}")
            print("Установите их командой: pip install PyQt6 pillow")
        except Exception as e:
            print(f"Ошибка запуска GUI: {e}")
    else:
        if not args.input_file or not args.output_file:
            parser.print_help()
        else:
            convert_image(args.input_file, args.output_file)