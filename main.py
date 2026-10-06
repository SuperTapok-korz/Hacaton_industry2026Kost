"""Local proctoring demo for Qostanai Industry Hackathon 2026."""
from __future__ import annotations

import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QDialog, QHBoxLayout, QLabel, QListWidget,
    QMainWindow, QMessageBox, QPushButton, QRadioButton, QVBoxLayout, QWidget,
)


APP_DIR = Path(__file__).resolve().parent
MODEL_PATH = APP_DIR / "yolov8n.pt"
PHONE_CLASS_ID = 67  # COCO class: cell phone


class DemoTestDialog(QDialog):
    """Full-screen sample quiz with app-level shortcut handling."""
    QUESTIONS = [
        ("Что показывает термометр?", ["Температуру", "Скорость", "Давление"], 0),
        ("Сколько будет 7 × 8?", ["54", "56", "64"], 1),
        ("Какой газ нужен человеку для дыхания?", ["Кислород", "Водород", "Гелий"], 0),
    ]

    def __init__(self, proctor: "ProctorWindow") -> None:
        super().__init__(proctor)
        self.proctor = proctor
        self.question_index = 0
        self.answers: list[int | None] = [None] * len(self.QUESTIONS)
        self.setWindowTitle("Пробный тест")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setStyleSheet("QDialog { background:#f8fafc; } QLabel { color:#0f172a; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(90, 60, 90, 60)
        self.header = QLabel("ДЕМО-ТЕСТ • РЕЖИМ НАБЛЮДЕНИЯ")
        self.header.setStyleSheet("font-size:16px;color:#475569;font-weight:700")
        self.progress = QLabel()
        self.progress.setStyleSheet("font-size:15px;color:#64748b")
        self.question = QLabel()
        self.question.setWordWrap(True)
        self.question.setStyleSheet("font-size:30px;font-weight:700")
        self.choices = QButtonGroup(self)
        self.choice_buttons = [QRadioButton() for _ in range(3)]
        for i, button in enumerate(self.choice_buttons):
            button.setStyleSheet("font-size:22px;padding:12px;color:#1e293b")
            self.choices.addButton(button, i)
            layout.addWidget(button)
        self.notice = QLabel("Копирование и вставка в окне теста отключены. Выход из окна фиксируется.")
        self.notice.setStyleSheet("font-size:14px;color:#64748b")
        layout.insertWidget(0, self.header)
        layout.insertWidget(1, self.progress)
        layout.insertWidget(2, self.question)
        layout.addStretch(1)
        layout.addWidget(self.notice)
        buttons = QHBoxLayout()
        self.next_button = QPushButton("Далее")
        self.finish_button = QPushButton("Завершить тест")
        self.next_button.clicked.connect(self.next_question)
        self.finish_button.clicked.connect(self.finish_test)
        buttons.addWidget(self.next_button)
        buttons.addWidget(self.finish_button)
        layout.addLayout(buttons)
        self.render_question()

    def render_question(self) -> None:
        if self.question_index >= len(self.QUESTIONS):
            return
        prompt, options, _ = self.QUESTIONS[self.question_index]
        self.progress.setText(f"Вопрос {self.question_index + 1} из {len(self.QUESTIONS)}")
        self.question.setText(prompt)
        self.choices.setExclusive(False)
        for i, (button, option) in enumerate(zip(self.choice_buttons, options)):
            button.setText(option)
            button.setChecked(self.answers[self.question_index] == i)
        self.choices.setExclusive(True)
        self.next_button.setText("Завершить" if self.question_index == len(self.QUESTIONS) - 1 else "Далее")

    def next_question(self) -> None:
        selected = self.choices.checkedId()
        self.answers[self.question_index] = selected if selected >= 0 else None
        if self.question_index == len(self.QUESTIONS) - 1:
            self.finish_test()
            return
        self.question_index += 1
        self.render_question()

    def finish_test(self) -> None:
        if QMessageBox.question(self, "Завершить тест", "Завершить пробный тест?") == QMessageBox.StandardButton.Yes:
            self.proctor.log_event("Пробный тест завершён", "test_end", 0)
            self.accept()

    def keyPressEvent(self, event) -> None:
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if ctrl and event.key() in (Qt.Key.Key_C, Qt.Key.Key_V, Qt.Key.Key_Insert):
            self.proctor.log_event("Попытка копирования или вставки в тесте", "blocked_copy_paste", 2)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Print:
            self.proctor.log_event("Нажата клавиша снимка экрана", "print_screen", 2)
            event.accept()
            return
        super().keyPressEvent(event)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.ActivationChange and not self.isActiveWindow():
            self.proctor.log_event("Тестовое окно потеряло фокус", "test_focus", 2)
        super().changeEvent(event)

    def closeEvent(self, event) -> None:
        if self.result() == QDialog.DialogCode.Accepted:
            event.accept()
            return
        answer = QMessageBox.question(self, "Выйти из теста", "Завершить тест и закрыть окно?")
        if answer == QMessageBox.StandardButton.Yes:
            self.proctor.log_event("Тестовое окно закрыто", "test_closed", 0)
            event.accept()
        else:
            event.ignore()


class ProctorWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Qostanai Proctor — локальный прототип")
        self.resize(1120, 720)
        self.capture: cv2.VideoCapture | None = None
        self.detector = None
        self.face_mesh = None
        self.last_event: dict[str, float] = {}
        self.gaze_samples: list[tuple[float, float, float, float]] = []
        self.gaze_baseline: tuple[float, float, float, float] | None = None
        self.gaze_metrics_history: deque[tuple[float, float, float, float]] = deque(maxlen=7)
        self.gaze_candidate = ""
        self.gaze_candidate_since = 0.0
        self.gaze_state = ""
        self.started = False

        self.video = QLabel("Нажмите «Начать проверку», чтобы включить камеру")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setMinimumSize(720, 480)
        self.video.setStyleSheet("background:#111827;color:#cbd5e1;border-radius:12px;font-size:16px")
        self.status = QLabel("● Ожидание запуска")
        self.status.setStyleSheet("color:#64748b;font-size:16px;font-weight:600")
        self.events = QListWidget()
        self.events.addItem("Журнал событий появится здесь")
        self.start_button = QPushButton("Начать проверку")
        self.test_button = QPushButton("Открыть пробный тест")
        self.test_button.setEnabled(False)
        self.test_button.clicked.connect(self.open_demo_test)
        self.stop_button = QPushButton("Завершить")
        self.camera_picker = QComboBox()
        self.camera_picker.addItem("Камера Windows по умолчанию", 0)
        self.scan_button = QPushButton("Найти камеры")
        self.scan_button.clicked.connect(self.scan_cameras)
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_session)
        self.stop_button.clicked.connect(self.stop_session)
        self.hint = QLabel("Видео обрабатывается на этом компьютере. Запись не сохраняется.")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color:#64748b")

        side = QVBoxLayout()
        side.addWidget(self.status)
        side.addWidget(QLabel("События контроля"))
        side.addWidget(self.events, 1)
        side.addWidget(self.hint)
        side.insertWidget(1, QLabel("Источник видео"))
        side.insertWidget(2, self.camera_picker)
        side.insertWidget(3, self.scan_button)
        side.addWidget(self.start_button)
        side.addWidget(self.test_button)
        side.addWidget(self.stop_button)
        layout = QHBoxLayout()
        layout.addWidget(self.video, 3)
        panel = QWidget()
        panel.setLayout(side)
        panel.setMinimumWidth(280)
        layout.addWidget(panel, 1)
        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.process_frame)
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.ApplicationDeactivate and self.started:
            self.log_event("Приложение прокторинга потеряло фокус", "app_focus", 2)
        return super().eventFilter(watched, event)

    def open_demo_test(self) -> None:
        if not self.started:
            return
        self.log_event("Пробный тест открыт", "test_start", 0)
        dialog = DemoTestDialog(self)
        dialog.showFullScreen()
        dialog.exec()

    def scan_cameras(self) -> None:
        self.scan_button.setEnabled(False)
        self.scan_button.setText("Поиск...")
        QApplication.processEvents()
        found: list[int] = []
        for index in range(10):
            camera = self.open_camera(index)
            ok, sample = camera.read() if camera.isOpened() else (False, None)
            camera.release()
            if ok and sample is not None and sample.size:
                found.append(index)
        current = self.camera_picker.currentData()
        self.camera_picker.clear()
        if not found:
            self.camera_picker.addItem("Камеры не найдены", 0)
            self.log_event("Камеры не найдены. Проверьте, что DroidCam Client запущен в Windows", "no_cameras", 0)
        else:
            for index in found:
                label = "Камера Windows по умолчанию" if index == 0 else f"Камера {index}"
                self.camera_picker.addItem(label, index)
            match = self.camera_picker.findData(current)
            if match >= 0:
                self.camera_picker.setCurrentIndex(match)
            self.log_event(f"Найдено видеоустройств: {len(found)}. Выберите DroidCam из списка", "cameras_found", 0)
        self.scan_button.setEnabled(True)
        self.scan_button.setText("Найти камеры")

    def log_event(self, message: str, key: str, cooldown: float = 3.0) -> None:
        now = time.monotonic()
        if now - self.last_event.get(key, 0) < cooldown:
            return
        self.last_event[key] = now
        self.events.insertItem(0, f"{datetime.now():%H:%M:%S}  {message}")

    def start_session(self) -> None:
        # Load optional detectors only when the session starts, so startup remains quick.
        try:
            import mediapipe as mp
            self.face_mesh = mp.solutions.face_mesh.FaceMesh(
                max_num_faces=3, refine_landmarks=True, min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        except Exception as exc:
            QMessageBox.critical(self, "MediaPipe недоступен", f"Не удалось запустить анализ лица:\n{exc}")
            return
        try:
            from ultralytics import YOLO
            # An explicit local model is preferred; otherwise Ultralytics fetches yolov8n.pt.
            self.detector = YOLO(str(MODEL_PATH) if MODEL_PATH.exists() else "yolov8n.pt")
        except Exception as exc:
            self.face_mesh.close()
            self.face_mesh = None
            QMessageBox.critical(
                self, "YOLO недоступен",
                "Не удалось загрузить модель YOLO. Проверьте установку ultralytics и наличие "
                f"yolov8n.pt (при первом запуске нужен интернет).\n\n{exc}",
            )
            return
        camera_index = int(self.camera_picker.currentData() or 0)
        self.capture = self.open_camera(camera_index)
        if not self.capture.isOpened():
            self.capture = None
            self.face_mesh.close()
            self.face_mesh = None
            QMessageBox.critical(self, "Камера недоступна", "Не удалось открыть выбранную камеру. Выберите другой источник видео и проверьте, что DroidCam запущен на компьютере.")
            return
        self.started = True
        self.start_button.setEnabled(False)
        self.test_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.status.setText("● Проверка идёт")
        self.status.setStyleSheet("color:#16a34a;font-size:16px;font-weight:600")
        self.events.clear()
        self.gaze_samples.clear()
        self.gaze_baseline = None
        self.gaze_metrics_history.clear()
        self.gaze_candidate = ""
        self.gaze_state = ""
        self.log_event("Сессия начата", "start", 0)
        self.timer.start(80)

    @staticmethod
    def open_camera(index: int) -> cv2.VideoCapture:
        """Try Windows Media Foundation first; DirectShow can return corrupted
        frames from some virtual-camera drivers (including USB phone cameras).
        """
        for backend in (cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY):
            cap = cv2.VideoCapture(index, backend)
            if not cap.isOpened():
                cap.release()
                continue
            # Prefer a common webcam mode and allow the driver to negotiate it.
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            # MJPG avoids incorrect YUY2 decoding on a number of virtual-camera
            # paths. Unsupported drivers simply ignore this hint.
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            ok, sample = cap.read()
            if ok and sample is not None and sample.size:
                return cap
            cap.release()
        return cv2.VideoCapture()

    def process_frame(self) -> None:
        if not self.capture:
            return
        ok, frame = self.capture.read()
        if not ok:
            self.log_event("Не удалось получить кадр с камеры", "camera")
            return
        # Some virtual-camera drivers return a uniform green frame when the
        # phone stream is not connected or the selected device is incorrect.
        if frame is None or frame.size == 0 or float(np.std(frame)) < 4.0:
            self.log_event("Пустой или однотонный кадр — проверьте выбранную камеру и подключение DroidCam", "blank_frame", 5)
            self.video.setText("Нет видеосигнала. Проверьте DroidCam и выберите его камеру в источниках видео.")
            return
        frame = cv2.flip(frame, 1)
        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if self.face_mesh:
            result = self.face_mesh.process(rgb)
            faces = result.multi_face_landmarks or []
            if not faces:
                self.log_event("Лицо не обнаружено", "no_face", 5)
            else:
                if len(faces) > 1:
                    self.log_event(f"В кадре обнаружено лиц: {len(faces)}", "multiple_faces", 5)
                ordered_faces = sorted(
                    faces,
                    key=lambda face: (
                        max(point.x for point in face.landmark) - min(point.x for point in face.landmark)
                    ) * (
                        max(point.y for point in face.landmark) - min(point.y for point in face.landmark)
                    ),
                    reverse=True,
                )
                primary_metrics = None
                for face_index, face in enumerate(ordered_faces):
                    pts = face.landmark
                    xs = [p.x * width for p in pts]
                    ys = [p.y * height for p in pts]
                    x1, x2 = max(0, int(min(xs))), min(width - 1, int(max(xs)))
                    y1, y2 = max(0, int(min(ys))), min(height - 1, int(max(ys)))
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (34, 197, 94), 2)
                    if face_index == 0:
                        primary_metrics = self.measure_face(pts)
                if primary_metrics is not None:
                    state = self.update_gaze_state(primary_metrics)
                    cv2.putText(frame, state, (24, 34), cv2.FONT_HERSHEY_SIMPLEX,
                                .7, (34, 197, 94), 2)
        else:
            self.log_event("Анализ лица не запущен", "face_error")

        if self.detector:
            try:
                prediction = self.detector.predict(frame, imgsz=640, conf=0.35, verbose=False)[0]
                for box in prediction.boxes:
                    if int(box.cls[0]) == PHONE_CLASS_ID:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        conf = float(box.conf[0])
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (239, 68, 68), 2)
                        cv2.putText(frame, f"Телефон {conf:.0%}", (x1, max(24, y1 - 8)),
                                    cv2.FONT_HERSHEY_SIMPLEX, .65, (239, 68, 68), 2)
                        self.log_event("Обнаружен возможный смартфон", "phone", 4)
            except Exception as exc:
                self.log_event(f"Ошибка детектора: {exc}", "detector_error", 10)

        image = QImage(frame.data, width, height, frame.strides[0], QImage.Format.Format_BGR888)
        self.video.setPixmap(QPixmap.fromImage(image.copy()).scaled(
            self.video.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        ))

    @staticmethod
    def measure_face(landmarks) -> tuple[float, float, float, float]:
        """Return normalized iris and head offsets; all values are relative to eye size."""
        eye_pairs = ((33, 133, 468, 159, 145), (362, 263, 473, 386, 374))
        horizontal_iris = []
        vertical_iris = []
        for outer, inner, iris, upper, lower in eye_pairs:
            span = landmarks[inner].x - landmarks[outer].x
            if abs(span) < 1e-5:
                continue
            horizontal_iris.append((landmarks[iris].x - landmarks[outer].x) / span)
            eye_mid_y = (landmarks[upper].y + landmarks[lower].y) / 2
            vertical_iris.append((landmarks[iris].y - eye_mid_y) / abs(span))
        if not horizontal_iris:
            return (0.5, 0.0, 0.5, 0.0)

        # Nose position relative to the eye line estimates head turn and tilt.
        face_left, face_right = landmarks[33], landmarks[263]
        eye_width = max(abs(face_right.x - face_left.x), 1e-5)
        nose = landmarks[1]
        head_horizontal = (nose.x - face_left.x) / (face_right.x - face_left.x or 1e-5)
        eye_line_y = (face_left.y + face_right.y) / 2
        head_vertical = (nose.y - eye_line_y) / eye_width
        return (
            float(np.mean(horizontal_iris)),
            float(np.mean(vertical_iris)),
            float(head_horizontal),
            float(head_vertical),
        )

    def update_gaze_state(self, metrics: tuple[float, float, float, float]) -> str:
        """Calibrate to the student's neutral pose, smooth noise, then use two severity bands."""
        if self.gaze_baseline is None:
            self.gaze_samples.append(metrics)
            if len(self.gaze_samples) < 24:
                return "Калибровка — смотрите на экран"
            self.gaze_baseline = tuple(float(x) for x in np.median(self.gaze_samples, axis=0))
            self.gaze_metrics_history.clear()
            self.gaze_candidate = "на экран"
            self.gaze_candidate_since = time.monotonic()
            self.gaze_state = "на экран"
            return "Калибровка готова — смотрите на экран"

        self.gaze_metrics_history.append(metrics)
        smoothed = np.median(np.asarray(self.gaze_metrics_history), axis=0)
        delta = smoothed - np.asarray(self.gaze_baseline)
        eye_x, eye_y, head_x, head_y = map(float, delta)

        # Eye movement and head movement have separate thresholds. Small natural
        # movements are shown as slight; only persistent larger deviations alert.
        candidates = [
            (abs(eye_x) / 0.40, "влево" if eye_x > 0 else "вправо", abs(eye_x), 0.15, 0.40),
            (abs(eye_y) / 0.33, "вниз" if eye_y > 0 else "вверх", abs(eye_y), 0.13, 0.33),
            (abs(head_x) / 0.28, "поворот головы влево" if head_x > 0 else "поворот головы вправо", abs(head_x), 0.10, 0.28),
            (abs(head_y) / 0.40, "наклон головы вниз" if head_y > 0 else "наклон головы вверх", abs(head_y), 0.16, 0.40),
        ]
        strongest = max(candidates, key=lambda item: item[0])
        _, direction, amount, slight_threshold, strong_threshold = strongest
        if amount < slight_threshold:
            proposed = "на экран"
        else:
            severity = "сильный" if amount >= strong_threshold else "небольшой"
            proposed = f"{severity} отвод: {direction}"

        now = time.monotonic()
        if proposed != self.gaze_candidate:
            self.gaze_candidate = proposed
            self.gaze_candidate_since = now
        dwell = 0.65 if proposed.startswith("сильный") else 0.9
        if proposed != self.gaze_state and now - self.gaze_candidate_since >= dwell:
            self.gaze_state = proposed
            if proposed != "на экран":
                key = "gaze_strong" if proposed.startswith("сильный") else "gaze_slight"
                self.log_event(
                    "Сильный отвод взгляда: " + direction if key == "gaze_strong"
                    else "Небольшой отвод взгляда: " + direction,
                    key,
                    1.0,
                )
        return self.gaze_state or proposed

    def stop_session(self) -> None:
        self.timer.stop()
        if self.capture:
            self.capture.release()
            self.capture = None
        if self.face_mesh:
            self.face_mesh.close()
            self.face_mesh = None
        self.gaze_samples.clear()
        self.gaze_baseline = None
        self.gaze_metrics_history.clear()
        self.gaze_candidate = ""
        self.gaze_state = ""
        self.detector = None
        self.started = False
        self.start_button.setEnabled(True)
        self.test_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.status.setText("● Проверка завершена")
        self.status.setStyleSheet("color:#64748b;font-size:16px;font-weight:600")
        self.video.setPixmap(QPixmap())
        self.video.setText("Проверка завершена")
        self.log_event("Сессия завершена", "stop", 0)

    def closeEvent(self, event) -> None:
        self.stop_session()
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    window = ProctorWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
