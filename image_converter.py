import argparse
import os
import logging
import sys
import re
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, 
                            QFileDialog, QMessageBox, QProgressBar, QFrame, QSizePolicy, QGridLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QFont, QImage

# ==================== КОНФИГУРАЦИЯ ====================
class Config:
    """Централизованная конфигурация приложения"""
    # Размеры окна
    WINDOW_WIDTH = 750
    WINDOW_HEIGHT = 650
    MIN_WIDTH = 650
    MIN_HEIGHT = 550
    
    # Размеры ICO иконки
    ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    
    # Поддерживаемые форматы
    VALID_IMAGE_FORMATS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp', '.ico')
    
    # Ограничения
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
    RESIZE_DEBOUNCE_MS = 500
    CONVERSION_TIMEOUT_MS = 300000  # 5 минут
    
    # Стили
    STYLE_MAIN = """
        QMainWindow { background-color: #1a1a1a; color: #ffffff; }
        QWidget { background-color: #1a1a1a; color: #ffffff; font-size: 13px; }
        QFrame { background-color: #252525; border: 1px solid #3a3a3a; border-radius: 10px; padding: 12px; }
        QLabel { background-color: transparent; color: #ffffff; padding: 5px; font-size: 13px; }
        QPushButton { background-color: #0078d4; color: white; border: none; border-radius: 8px; 
                     padding: 12px 24px; font-weight: bold; font-size: 14px; min-height: 40px; }
        QPushButton:hover { background-color: #1e88e5; }
        QPushButton:pressed { background-color: #005a9e; }
        QPushButton:disabled { background-color: #3a3a3a; color: #808080; }
        QProgressBar { border: 1px solid #3a3a3a; border-radius: 8px; text-align: center;
                      background-color: #252525; font-size: 12px; }
        QProgressBar::chunk { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                             stop:0 #0078d4, stop:1 #1e88e5); border-radius: 7px; }
    """
    
    # Стили для элементов
    STYLE_PATH_LABEL_INACTIVE = """
        color: #888888; padding: 3px 6px; background-color: #2d2d2d;
        border: 1px solid #404040; border-radius: 4px; font-size: 9px;
    """
    
    STYLE_PATH_LABEL_ACTIVE = """
        color: #ffffff; padding: 3px 6px; background-color: #2d2d2d;
        border: 1px solid #0078d4; border-radius: 4px; font-size: 9px;
    """
    
    STYLE_BUTTON_SMALL = "font-size: 9px; padding: 3px 8px; min-height: 22px; max-width: 70px;"
    
    STYLE_PREVIEW_EMPTY = """
        QLabel { background-color: #252525; border: 1px dashed #444444; border-radius: 4px;
                color: #888888; font-size: 10px; padding: 10px; }
    """
    
    STYLE_PREVIEW_LOADED = """
        QLabel { background-color: #252525; border: 1px solid #0078d4;
                border-radius: 4px; padding: 5px; }
    """
    
    STYLE_PREVIEW_DRAGGING = """
        QLabel { background-color: #2d2d2d; border: 1px dashed #0078d4; border-radius: 4px;
                color: #0078d4; font-size: 10px; padding: 10px; }
    """
    
    STYLE_PREVIEW_ERROR = """
        QLabel { background-color: #252525; border: 1px dashed #ef4444; border-radius: 4px;
                color: #ef4444; font-size: 10px; padding: 10px; }
    """

# ==================== ЛОГИКА КОНВЕРТАЦИИ ====================
class ImageConverter:
    """Основная логика конвертирования изображений"""
    
    EXTENSION_PATTERN = re.compile(r'\(\*\.(.*?)\)')
    
    @staticmethod
    def validate_file(file_path: str) -> Tuple[bool, str]:
        """Валидация входного файла"""
        if not os.path.exists(file_path):
            return False, f"Файл не найден: {file_path}"
        
        if not file_path.lower().endswith(Config.VALID_IMAGE_FORMATS):
            return False, f"Недопустимый формат. Поддерживаемые: {', '.join(Config.VALID_IMAGE_FORMATS)}"
        
        file_size = os.path.getsize(file_path)
        if file_size > Config.MAX_FILE_SIZE:
            size_mb = file_size / (1024 * 1024)
            return False, f"Файл слишком большой: {size_mb:.1f} МБ (макс: {Config.MAX_FILE_SIZE / (1024 * 1024):.0f} МБ)"
        
        try:
            with Image.open(file_path) as img:
                img.verify()
            return True, "OK"
        except Exception as e:
            return False, f"Повреждённый файл: {str(e)}"
    
    @staticmethod
    def convert(input_path: str, output_path: str) -> Tuple[bool, str]:
        """Конвертирование изображения"""
        try:
            logging.info(f"Starting conversion: {input_path} -> {output_path}")
            with Image.open(input_path) as img:
                # Конвертируем в RGB если нужно (для JPEG)
                if output_path.lower().endswith(('.jpg', '.jpeg')) and img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    rgb_img.save(output_path, quality=95)
                elif output_path.lower().endswith('.ico'):
                    img.save(output_path, format='ICO', sizes=Config.ICO_SIZES)
                else:
                    img.save(output_path)
            logging.info(f"Successfully converted: {output_path}")
            return True, "Изображение успешно конвертировано!"
        except Exception as e:
            error_msg = f"Ошибка при конвертации: {str(e)}"
            logging.error(error_msg)
            return False, error_msg
    
    @staticmethod
    def get_image_info(image_path: str) -> Optional[dict]:
        """Получить информацию об изображении"""
        try:
            with Image.open(image_path) as img:
                file_size = os.path.getsize(image_path)
                size_str = ImageConverter._format_file_size(file_size)
                
                return {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format or "Unknown",
                    'mode': img.mode,
                    'size': size_str
                }
        except Exception as e:
            logging.error(f"Error getting image info: {e}")
            return None
    
    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        """Форматирование размера файла"""
        if size_bytes >= 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} МБ"
        elif size_bytes >= 1024:
            return f"{size_bytes / 1024:.1f} КБ"
        return f"{size_bytes} байт"
    
    @staticmethod
    def extract_extension_from_filter(filter_text: str) -> Optional[str]:
        """Извлечение расширения из фильтра файла"""
        match = ImageConverter.EXTENSION_PATTERN.search(filter_text)
        return f".{match.group(1)}" if match else None


# ==================== WORKER ПОТОКА ====================
class ConversionWorker(QThread):
    """Рабочий поток для конвертации"""
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    conversion_finished = pyqtSignal(bool, str)
    
    def __init__(self, input_path: str, output_path: str):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
    
    def run(self):
        self.status_updated.emit("⚡ Начинаем конвертацию...")
        self.progress_updated.emit(20)
        
        # Валидация
        valid, msg = ImageConverter.validate_file(self.input_path)
        if not valid:
            self.progress_updated.emit(0)
            self.status_updated.emit("❌ Ошибка валидации")
            self.conversion_finished.emit(False, msg)
            return
        
        self.progress_updated.emit(40)
        
        # Конвертация
        success, message = ImageConverter.convert(self.input_path, self.output_path)
        self.progress_updated.emit(100)
        
        if success:
            self.status_updated.emit("✅ Конвертация завершена!")
        else:
            self.status_updated.emit("❌ Ошибка конвертации")
        
        self.conversion_finished.emit(success, message)


# ==================== ГРАФИЧЕСКИЙ ИНТЕРФЕЙС ====================
class ImageConverterGUI(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self, converter: Optional[ImageConverter] = None):
        super().__init__()
        self.converter = converter or ImageConverter()
        
        self.setWindowTitle("🖼️ Конвертер изображений")
        self.setGeometry(250, 50, Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT)
        self.setMinimumSize(Config.MIN_WIDTH, Config.MIN_HEIGHT)
        self.setAcceptDrops(True)
        
        # Состояние
        self.input_path = ""
        self.output_path = ""
        self.original_image_qt: Optional[QImage] = None
        self.conversion_worker: Optional[ConversionWorker] = None
        self.is_converting = False
        
        # Таймеры
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.update_preview_image_size)
        
        self.setup_ui()
        self.resizeEvent = self._on_window_resize
    
    def setup_ui(self):
        """Инициализация UI"""
        self.setStyleSheet(Config.STYLE_MAIN)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 6, 8, 6)
        main_layout.setSpacing(4)
        
        self._create_header(main_layout)
        self._create_file_selection(main_layout)
        self._create_preview(main_layout)
        self._create_conversion(main_layout)
    
    def _create_header(self, parent_layout):
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
        
        header_layout.addWidget(title_label)
        parent_layout.addWidget(header_frame)
    
    def _create_file_selection(self, parent_layout):
        """Создание секции выбора файлов"""
        files_frame = QFrame()
        files_frame.setStyleSheet("QFrame { padding: 4px; }")
        files_layout = QHBoxLayout(files_frame)
        files_layout.setContentsMargins(6, 3, 6, 3)
        files_layout.setSpacing(4)
        
        # Входной файл
        input_icon = QLabel("📂")
        input_icon.setStyleSheet("font-size: 14px; padding: 0px; max-width: 18px;")
        
        self.input_path_label = QLabel("Выберите файл")
        self.input_path_label.setStyleSheet(Config.STYLE_PATH_LABEL_INACTIVE)
        self.input_path_label.setMaximumWidth(200)
        
        self.input_browse_btn = QPushButton("Открыть")
        self.input_browse_btn.clicked.connect(self.browse_input_file)
        self.input_browse_btn.setStyleSheet(Config.STYLE_BUTTON_SMALL)
        
        # Разделитель
        separator = QLabel("|")
        separator.setStyleSheet("color: #404040; font-size: 12px; padding: 0 4px;")
        
        # Выходной файл
        output_icon = QLabel("💾")
        output_icon.setStyleSheet("font-size: 14px; padding: 0px; max-width: 18px;")
        
        self.output_path_label = QLabel("Сохранить как")
        self.output_path_label.setStyleSheet(Config.STYLE_PATH_LABEL_INACTIVE)
        self.output_path_label.setMaximumWidth(200)
        
        self.output_browse_btn = QPushButton("Сохранить")
        self.output_browse_btn.clicked.connect(self.browse_output_file)
        self.output_browse_btn.setStyleSheet(Config.STYLE_BUTTON_SMALL)
        
        files_layout.addWidget(input_icon)
        files_layout.addWidget(self.input_path_label, 1)
        files_layout.addWidget(self.input_browse_btn)
        files_layout.addWidget(separator)
        files_layout.addWidget(output_icon)
        files_layout.addWidget(self.output_path_label, 1)
        files_layout.addWidget(self.output_browse_btn)
        
        parent_layout.addWidget(files_frame)
    
    def _create_preview(self, parent_layout):
        """Создание превью изображения"""
        preview_frame = QFrame()
        preview_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        preview_frame.setStyleSheet("QFrame { background-color: #1f1f1f; border: 1px solid #3a3a3a; border-radius: 6px; padding: 6px; }")
        
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(3)
        
        preview_header = QLabel("🖼️ Превью")
        preview_header.setStyleSheet("font-weight: bold; font-size: 9px; background: transparent; border: none; padding: 2px;")
        preview_layout.addWidget(preview_header)
        
        self.preview_image_label = QLabel()
        self.preview_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image_label.setScaledContents(False)
        self.preview_image_label.setStyleSheet(Config.STYLE_PREVIEW_EMPTY)
        self.preview_image_label.setText("🖼️ Перетащите изображение\nили выберите файл")
        self.preview_image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        preview_layout.addWidget(self.preview_image_label, 1)
        
        self.image_info_label = QLabel("")
        self.image_info_label.setStyleSheet("color: #60a5fa; font-size: 8px; background: transparent; border: none; padding: 2px;")
        self.image_info_label.setWordWrap(True)
        self.image_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.image_info_label)
        
        parent_layout.addWidget(preview_frame, 1)
    
    def _create_conversion(self, parent_layout):
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
    
    def _on_window_resize(self, event):
        """Обработчик ресайза окна с debounce"""
        super().resizeEvent(event)
        self.resize_timer.stop()
        self.resize_timer.start(Config.RESIZE_DEBOUNCE_MS)
    
    def dragEnterEvent(self, event):
        """Обработка входа файла при перетаскивании"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.preview_image_label.setStyleSheet(Config.STYLE_PREVIEW_DRAGGING)
    
    def dragLeaveEvent(self, event):
        """Обработка выхода файла при перетаскивании"""
        if self.original_image_qt:
            self.preview_image_label.setStyleSheet(Config.STYLE_PREVIEW_LOADED)
        else:
            self.preview_image_label.setStyleSheet(Config.STYLE_PREVIEW_EMPTY)
    
    def dropEvent(self, event):
        """Обработка отпускания файла"""
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        if files:
            file_path = files[0]
            if file_path.lower().endswith(Config.VALID_IMAGE_FORMATS):
                self._load_input_file(file_path)
            else:
                self._show_error("Неверный формат", "Пожалуйста, перетащите файл изображения (PNG, JPG, GIF и т.д.)")
        
        event.acceptProposedAction()
    
    def browse_input_file(self):
        """Выбор входного файла"""
        file_filter = "Изображения (*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.webp);;Все файлы (*.*)"
        filename, _ = QFileDialog.getOpenFileName(self, "Выберите изображение", "", file_filter)
        
        if filename:
            self._load_input_file(filename)
    
    def browse_output_file(self):
        """Выбор выходного файла"""
        file_filter = "PNG (*.png);;JPEG (*.jpg);;ICO (*.ico);;GIF (*.gif);;BMP (*.bmp);;TIFF (*.tiff);;WebP (*.webp)"
        
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
            ext = self.converter.extract_extension_from_filter(selected_filter)
            if ext and not filename.lower().endswith(ext):
                filename += ext
            
            self._set_output_path(filename)
    
    def _load_input_file(self, file_path: str):
        """Загрузка входного файла"""
        valid, msg = self.converter.validate_file(file_path)
        
        if not valid:
            self._show_error("Ошибка файла", msg)
            return
        
        self.input_path = file_path
        display_name = os.path.basename(file_path)
        self.input_path_label.setText(display_name)
        self.input_path_label.setToolTip(file_path)
        self.input_path_label.setStyleSheet(Config.STYLE_PATH_LABEL_ACTIVE)
        
        self._load_preview_image(file_path)
        self._update_convert_button_state()
    
    def _set_output_path(self, file_path: str):
        """Установка выходного пути"""
        self.output_path = file_path
        display_name = os.path.basename(file_path)
        self.output_path_label.setText(display_name)
        self.output_path_label.setToolTip(file_path)
        self.output_path_label.setStyleSheet(Config.STYLE_PATH_LABEL_ACTIVE)
        
        self._show_success_status("✅ Готово")
        self._update_convert_button_state()
    
    def _load_preview_image(self, image_path: str):
        """Загрузка и отображение превью"""
        try:
            logging.info(f"Loading preview image: {image_path}")
            
            # Используем QPixmap для загрузки, так как он лучше поддерживает форматы
            pixmap = QPixmap(image_path)
            
            if pixmap.isNull():
                logging.error(f"Failed to load pixmap from: {image_path}")
                raise ValueError("Не удалось загрузить изображение")
            
            # Преобразуем в QImage для хранения
            self.original_image_qt = pixmap.toImage()
            
            logging.info(f"Image loaded successfully: {pixmap.width()}x{pixmap.height()}")
            
            # Очищаем текст перед установкой пиксмапа
            self.preview_image_label.setText("")
            
            info = self.converter.get_image_info(image_path)
            if info:
                info_text = f"📐 {info['width']}×{info['height']}  •  📋 {info['format']}  •  💾 {info['size']}  •  🎨 {info['mode']}"
                self.image_info_label.setText(info_text)
            
            self.preview_image_label.setStyleSheet(Config.STYLE_PREVIEW_LOADED)
            self.update_preview_image_size()
            self._show_success_status("🖼️ Загружено")
            
        except Exception as e:
            error_msg = f"❌ Ошибка загрузки:\n{str(e)}"
            self.preview_image_label.setText(error_msg)
            self.preview_image_label.setStyleSheet(Config.STYLE_PREVIEW_ERROR)
            self.image_info_label.setText("")
            self._show_error_status("❌ Ошибка")
            logging.error(f"Error loading preview: {e}")
            self.original_image_qt = None
    
    def update_preview_image_size(self):
        """Обновление размера превью при ресайзе"""
        if not self.original_image_qt:
            return
        
        try:
            # Преобразуем QImage в QPixmap для отображения
            pixmap = QPixmap.fromImage(self.original_image_qt)
            
            if pixmap.isNull():
                logging.error("Failed to convert QImage to QPixmap")
                return
            
            label_size = self.preview_image_label.size()
            
            # Если размер label ещё не установлен, используем размер оригинального изображения
            if label_size.width() <= 0 or label_size.height() <= 0:
                # Ограничиваем максимальный размер для превью
                max_width = 400
                max_height = 300
                scaled_pixmap = pixmap.scaledToWidth(
                    max_width,
                    Qt.TransformationMode.SmoothTransformation
                )
                if scaled_pixmap.height() > max_height:
                    scaled_pixmap = scaled_pixmap.scaledToHeight(
                        max_height,
                        Qt.TransformationMode.SmoothTransformation
                    )
            else:
                scaled_pixmap = pixmap.scaled(
                    label_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            
            logging.info(f"Setting pixmap: {scaled_pixmap.width()}x{scaled_pixmap.height()}")
            self.preview_image_label.setPixmap(scaled_pixmap)
        except Exception as e:
            logging.error(f"Error updating preview: {e}")
    
    def _update_convert_button_state(self):
        """Обновление состояния кнопки конвертации"""
        if self.input_path and self.output_path and not self.is_converting:
            self.convert_btn.setEnabled(True)
            self._show_success_status("🚀 Готово!")
        else:
            self.convert_btn.setEnabled(False)
    
    def convert_image_threaded(self):
        """Запуск конвертации в отдельном потоке"""
        if self.is_converting:
            self._show_error("Ошибка", "Конвертация уже в процессе")
            return
        
        if not self.input_path or not self.output_path:
            self._show_error("Ошибка", "Пожалуйста, выберите входной и выходной файлы")
            return
        
        self.is_converting = True
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.convert_btn.setEnabled(False)
        
        self.conversion_worker = ConversionWorker(self.input_path, self.output_path)
        self.conversion_worker.progress_updated.connect(self.progress_bar.setValue)
        self.conversion_worker.status_updated.connect(self.status_label.setText)
        self.conversion_worker.conversion_finished.connect(self._on_conversion_finished)
        self.conversion_worker.start()
    
    def _on_conversion_finished(self, success: bool, message: str):
        """Обработка завершения конвертации"""
        self.progress_bar.setVisible(False)
        self.is_converting = False
        self._update_convert_button_state()
        
        if success:
            self._show_success_status("✅ Успешно!")
            QMessageBox.information(self, "Успех", message)
        else:
            self._show_error_status("❌ Ошибка")
            QMessageBox.critical(self, "Ошибка", message)
    
    def _show_error(self, title: str, message: str):
        """Показать ошибку"""
        QMessageBox.critical(self, title, message)
        self._show_error_status(f"❌ {title}")
    
    def _show_error_status(self, text: str):
        """Обновить статус ошибки"""
        self.status_label.setText(text)
        self.status_label.setStyleSheet("color: #ef4444; font-size: 8px;")
    
    def _show_success_status(self, text: str):
        """Обновить статус успеха"""
        self.status_label.setText(text)
        self.status_label.setStyleSheet("color: #10b981; font-size: 8px;")
    
    def run(self):
        """Запуск GUI приложения"""
        self.show()
        return QApplication.instance().exec()


# ==================== ТОЧКА ВХОДА ====================
def main():
    parser = argparse.ArgumentParser(
        description="Конвертирование изображений из одного формата в другой",
        epilog="Пример: image_converter.py image.png image.jpg"
    )
    parser.add_argument("input_file", nargs='?', help="Путь к входному файлу изображения")
    parser.add_argument("output_file", nargs='?', help="Путь к выходному файлу изображения")
    parser.add_argument("--gui", action="store_true", help="Запустить GUI")
    
    args = parser.parse_args()
    
    # Инициализация логирования
    logging.basicConfig(
        filename='image_converter.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
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
            success, message = ImageConverter.convert(args.input_file, args.output_file)
            if success:
                print(f"✅ {message}")
                logging.info(message)
            else:
                print(f"❌ {message}")
                logging.error(message)
                sys.exit(1)

if __name__ == "__main__":
    main()