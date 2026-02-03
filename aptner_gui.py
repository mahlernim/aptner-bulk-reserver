"""
Aptner Visitor Vehicle Registration GUI (PyQt6 Version)
Features:
- Car number input with saved history (paired with phone)
- Recurring schedule selector (weekdays + weeks)
- Current reservations display with delete button
- Duplicate prevention
"""

import sys
from pathlib import Path
from datetime import date, timedelta
from typing import Optional
import yaml

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QTextEdit,
    QMessageBox, QFrame, QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from aptner_api import (
    AptnerClient,
    AptnerError,
    AptnerAuthError,
    create_client_from_env,
    PURPOSE_OPTIONS,
)

# File paths
SCRIPT_DIR = Path(__file__).parent
CAR_HISTORY_FILE = SCRIPT_DIR / "car_history.yaml"
ENV_FILE = SCRIPT_DIR / ".env"

# Days of week
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def load_car_history() -> list[dict]:
    """Load car history from YAML file."""
    if not CAR_HISTORY_FILE.exists():
        return []
    try:
        with open(CAR_HISTORY_FILE, "r", encoding="utf-8-sig") as f:
            data = yaml.safe_load(f) or {}
        return data.get("cars", [])
    except Exception:
        return []


def save_car_history(cars: list[dict]):
    """Save car history to YAML file."""
    with open(CAR_HISTORY_FILE, "w", encoding="utf-8-sig") as f:
        yaml.dump({"cars": cars}, f, allow_unicode=True)


def add_car_to_history(car_no: str, phone: str):
    """Add or update car in history."""
    cars = load_car_history()
    for car in cars:
        if car.get("carNo") == car_no:
            car["phone"] = phone
            save_car_history(cars)
            return
    cars.append({"carNo": car_no, "phone": phone})
    save_car_history(cars)


class WorkerThread(QThread):
    """Background worker for API calls."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class AptnerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.client: Optional[AptnerClient] = None
        self.reservations: list[dict] = []
        self.reserved_dates: set = set()
        self._car_data: dict = {}
        self._workers: list[WorkerThread] = []
        
        self.setWindowTitle("Aptner 방문차량 예약")
        self.setMinimumSize(900, 700)
        
        self._setup_ui()
        self._load_car_history()
        self._auto_login()
    
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        
        # === Status Bar ===
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)
        
        self.status_label = QLabel("⏳ 연결 중...")
        self.status_label.setFont(QFont("맑은 고딕", 10))
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 새로고침")
        refresh_btn.clicked.connect(self._refresh_reservations)
        status_layout.addWidget(refresh_btn)
        
        layout.addWidget(status_frame)
        
        # === Car Info Group ===
        car_group = QGroupBox("차량 정보")
        car_layout = QVBoxLayout(car_group)
        
        # Car number row
        car_row = QHBoxLayout()
        car_row.addWidget(QLabel("차량번호:"))
        self.car_combo = QComboBox()
        self.car_combo.setEditable(True)
        self.car_combo.setMinimumWidth(180)
        self.car_combo.currentTextChanged.connect(self._on_car_changed)
        car_row.addWidget(self.car_combo)
        car_row.addStretch()
        car_layout.addLayout(car_row)
        
        # Phone row
        phone_row = QHBoxLayout()
        phone_row.addWidget(QLabel("연락처:"))
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("010-0000-0000")
        self.phone_edit.setMaximumWidth(180)
        phone_row.addWidget(self.phone_edit)
        phone_row.addStretch()
        car_layout.addLayout(phone_row)
        
        # Purpose row
        purpose_row = QHBoxLayout()
        purpose_row.addWidget(QLabel("방문목적:"))
        self.purpose_combo = QComboBox()
        self.purpose_combo.addItems(PURPOSE_OPTIONS)
        self.purpose_combo.setMinimumWidth(150)
        purpose_row.addWidget(self.purpose_combo)
        purpose_row.addStretch()
        car_layout.addLayout(purpose_row)
        
        layout.addWidget(car_group)
        
        # === Schedule Group ===
        schedule_group = QGroupBox("예약 일정")
        schedule_layout = QVBoxLayout(schedule_group)
        
        # Weekday checkboxes
        days_row = QHBoxLayout()
        days_row.addWidget(QLabel("요일 선택:"))
        self.day_checks = []
        for day in WEEKDAYS:
            cb = QCheckBox(day)
            self.day_checks.append(cb)
            days_row.addWidget(cb)
        days_row.addStretch()
        schedule_layout.addLayout(days_row)
        
        # Weeks spinner
        weeks_row = QHBoxLayout()
        weeks_row.addWidget(QLabel("기간:"))
        self.weeks_spin = QSpinBox()
        self.weeks_spin.setRange(1, 12)
        self.weeks_spin.setValue(4)
        self.weeks_spin.setSuffix(" 주")
        weeks_row.addWidget(self.weeks_spin)
        weeks_row.addStretch()
        schedule_layout.addLayout(weeks_row)
        
        # Action buttons
        btn_row = QHBoxLayout()
        preview_btn = QPushButton("📅 예약 날짜 미리보기")
        preview_btn.clicked.connect(self._preview_dates)
        btn_row.addWidget(preview_btn)
        
        self.preview_label = QLabel("")
        btn_row.addWidget(self.preview_label)
        btn_row.addStretch()
        
        register_btn = QPushButton("✅ 예약 등록")
        register_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px 16px;")
        register_btn.clicked.connect(self._register_reservations)
        btn_row.addWidget(register_btn)
        
        schedule_layout.addLayout(btn_row)
        layout.addWidget(schedule_group)
        
        # === Reservations Table ===
        table_group = QGroupBox("현재 예약 현황")
        table_layout = QVBoxLayout(table_group)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["방문일", "차량번호", "목적", "연락처", "기간", "삭제"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 80)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        table_layout.addWidget(self.table)
        layout.addWidget(table_group, stretch=1)
        
        # === Log ===
        log_group = QGroupBox("로그")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)
    
    def _log(self, msg: str):
        self.log_text.append(msg)
    
    def _load_car_history(self):
        cars = load_car_history()
        self._car_data = {c.get("carNo"): c.get("phone", "") for c in cars}
        self.car_combo.clear()
        self.car_combo.addItems(list(self._car_data.keys()))
    
    def _on_car_changed(self, car_no: str):
        phone = self._car_data.get(car_no, "")
        if phone:
            self.phone_edit.setText(phone)
    
    def _update_status(self, text: str, color: str = "black"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color};")
    
    def _auto_login(self):
        def login():
            client = create_client_from_env(str(ENV_FILE))
            client.authenticate()
            return client
        
        worker = WorkerThread(login)
        worker.finished.connect(self._on_login_success)
        worker.error.connect(self._on_login_error)
        self._workers.append(worker)
        worker.start()
    
    def _on_login_success(self, client):
        self.client = client
        self._update_status("✅ 연결됨", "green")
        self._refresh_reservations()
    
    def _on_login_error(self, error):
        self._update_status("❌ 연결 실패", "red")
        self._log(f"로그인 오류: {error}")
    
    def _refresh_reservations(self):
        if not self.client:
            return
        
        def fetch():
            reservations = self.client.get_reservations()
            reserved = self.client.get_reserved_dates()
            return reservations, reserved
        
        worker = WorkerThread(fetch)
        worker.finished.connect(self._on_reservations_fetched)
        worker.error.connect(lambda e: self._log(f"조회 오류: {e}"))
        self._workers.append(worker)
        worker.start()
    
    def _on_reservations_fetched(self, result):
        self.reservations, self.reserved_dates = result
        self._update_table()
        self._log(f"예약 {len(self.reservations)}건 조회됨")
    
    def _update_table(self):
        self.table.setRowCount(len(self.reservations))
        
        for row, r in enumerate(self.reservations):
            self.table.setItem(row, 0, QTableWidgetItem(r["visitDateStr"]))
            self.table.setItem(row, 1, QTableWidgetItem(r["carNo"]))
            self.table.setItem(row, 2, QTableWidgetItem(r.get("purpose", "")))
            self.table.setItem(row, 3, QTableWidgetItem(r.get("phone", "")))
            self.table.setItem(row, 4, QTableWidgetItem(str(r.get("days", 1))))
            
            # Delete button
            del_btn = QPushButton("🗑️ 삭제")
            del_btn.setStyleSheet("background-color: #f44336; color: white;")
            del_btn.clicked.connect(lambda checked, idx=r.get("idx"): self._delete_reservation(idx))
            self.table.setCellWidget(row, 5, del_btn)
    
    def _delete_reservation(self, idx: int):
        if not idx:
            self._log("삭제 불가: ID 없음")
            return
        
        reply = QMessageBox.question(
            self, "예약 삭제",
            "이 예약을 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        def delete():
            return self.client.delete_reservation(idx)
        
        worker = WorkerThread(delete)
        worker.finished.connect(lambda _: self._on_delete_success())
        worker.error.connect(lambda e: self._log(f"삭제 오류: {e}"))
        self._workers.append(worker)
        worker.start()
    
    def _on_delete_success(self):
        self._log("예약 삭제 완료")
        self._refresh_reservations()
    
    def _get_schedule_dates(self) -> list[date]:
        selected_days = [i for i, cb in enumerate(self.day_checks) if cb.isChecked()]
        if not selected_days:
            return []
        
        weeks = self.weeks_spin.value()
        today = date.today()
        end_date = today + timedelta(weeks=weeks)
        
        dates = []
        current = today
        while current <= end_date:
            if current.weekday() in selected_days:
                dates.append(current)
            current += timedelta(days=1)
        
        return dates
    
    def _preview_dates(self):
        dates = self._get_schedule_dates()
        if not dates:
            self.preview_label.setText("선택된 요일이 없습니다")
            return
        
        car_no = self.car_combo.currentText().strip()
        duplicates = 0
        if car_no and self.reserved_dates:
            for d in dates:
                if (car_no, d) in self.reserved_dates:
                    duplicates += 1
        
        new_count = len(dates) - duplicates
        text = f"총 {len(dates)}일 ({dates[0]} ~ {dates[-1]})"
        if duplicates > 0:
            text += f" / 중복 {duplicates}건 제외 → {new_count}건"
        
        self.preview_label.setText(text)
    
    def _register_reservations(self):
        car_no = self.car_combo.currentText().strip()
        phone = self.phone_edit.text().strip()
        purpose = self.purpose_combo.currentText()
        
        if not car_no:
            QMessageBox.warning(self, "오류", "차량번호를 입력해주세요")
            return
        
        if not phone or len(phone) < 10:
            QMessageBox.warning(self, "오류", "연락처를 입력해주세요")
            return
        
        dates = self._get_schedule_dates()
        if not dates:
            QMessageBox.warning(self, "오류", "요일을 선택해주세요")
            return
        
        new_dates = [d for d in dates if (car_no, d) not in self.reserved_dates]
        if not new_dates:
            QMessageBox.information(self, "알림", "모든 날짜가 이미 예약되어 있습니다")
            return
        
        msg = f"차량번호: {car_no}\n연락처: {phone}\n목적: {purpose}\n예약일: {len(new_dates)}건\n\n예약하시겠습니까?"
        reply = QMessageBox.question(
            self, "예약 확인", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Save to history
        add_car_to_history(car_no, phone)
        self._load_car_history()
        
        def register_all():
            success, failed = 0, 0
            for d in new_dates:
                try:
                    self.client.reserve_car(
                        car_no=car_no,
                        visit_date=d,
                        phone=phone,
                        purpose=purpose,
                        days=1
                    )
                    success += 1
                except Exception:
                    failed += 1
            return success, failed
        
        worker = WorkerThread(register_all)
        worker.finished.connect(lambda r: self._on_register_complete(r[0], r[1]))
        worker.error.connect(lambda e: self._log(f"등록 오류: {e}"))
        self._workers.append(worker)
        worker.start()
        self._log("예약 등록 중...")
    
    def _on_register_complete(self, success: int, failed: int):
        self._log(f"완료: 성공 {success}건, 실패 {failed}건")
        self._refresh_reservations()
        QMessageBox.information(
            self, "완료",
            f"예약이 완료되었습니다.\n성공: {success}건, 실패: {failed}건"
        )


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Set Korean font
    font = QFont("맑은 고딕", 9)
    app.setFont(font)
    
    window = AptnerApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
