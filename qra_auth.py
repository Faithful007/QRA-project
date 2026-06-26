"""
qra_auth.py
====================================================================
Lightweight authentication for the QRA System launcher.

Provides:
  * AuthStore           — JSON-backed user store with PBKDF2-hashed
                          passwords (stdlib only, no external deps).
  * SplashScreen        — quick frameless loading splash.
  * LoginDialog         — sign-in page for users and admins.
  * CreateUserDialog    — admin-only "create user".
  * ChangePasswordDialog— any user changes their own password.
  * install_account_menu— adds an "Account" menu to a QMainWindow.

A default admin account (admin / admin) is seeded on first run.

This module is self-contained and does not touch qra_main_app.py.
"""

from __future__ import annotations

import os
import json
import time
import hmac
import hashlib

from PyQt5.QtWidgets import (
    QDialog, QWidget, QLabel, QLineEdit, QPushButton, QComboBox,
    QVBoxLayout, QHBoxLayout, QFormLayout, QProgressBar, QMessageBox,
    QApplication, QFrame,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont


# ====================================================================
#  Credential store
# ====================================================================
_ITERATIONS = 200_000
_DEFAULT_ADMIN = ("admin", "admin")


class AuthStore:
    """JSON-backed user store with salted PBKDF2-SHA256 password hashes."""

    def __init__(self, path):
        self.path = path
        self.data = {"version": 1, "users": {}}
        self._load()
        if not self.data["users"]:
            # first run -> seed a default admin
            self._add(_DEFAULT_ADMIN[0], _DEFAULT_ADMIN[1], "admin")
            self._save()

    # ---- persistence ----------------------------------------------
    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            if isinstance(d, dict) and isinstance(d.get("users"), dict):
                self.data = d
        except Exception:
            # missing or corrupt -> start fresh (admin seeded by __init__)
            self.data = {"version": 1, "users": {}}

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2)
        os.replace(tmp, self.path)

    # ---- hashing --------------------------------------------------
    @staticmethod
    def _hash(password, salt, iterations=_ITERATIONS):
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations)

    def _add(self, username, password, role):
        salt = os.urandom(16)
        self.data["users"][username] = {
            "role": role,
            "salt": salt.hex(),
            "hash": self._hash(password, salt).hex(),
            "iterations": _ITERATIONS,
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    # ---- lookup helpers -------------------------------------------
    def _find_key(self, username):
        """Case-insensitive username lookup -> stored key or None."""
        u = (username or "").strip()
        if u in self.data["users"]:
            return u
        low = u.lower()
        for k in self.data["users"]:
            if k.lower() == low:
                return k
        return None

    def user_exists(self, username):
        return self._find_key(username) is not None

    def list_users(self):
        return [
            {"username": k, "role": v.get("role", "user"),
             "created": v.get("created", "")}
            for k, v in sorted(self.data["users"].items())
        ]

    # ---- core operations ------------------------------------------
    def verify(self, username, password):
        """Return the user's role on success, else None."""
        key = self._find_key(username)
        if key is None:
            return None
        rec = self.data["users"][key]
        try:
            salt = bytes.fromhex(rec["salt"])
            expected = bytes.fromhex(rec["hash"])
        except Exception:
            return None
        test = self._hash(password, salt, rec.get("iterations", _ITERATIONS))
        if hmac.compare_digest(test, expected):
            return rec.get("role", "user")
        return None

    def create_user(self, username, password, role="user"):
        """(ok, message)."""
        u = (username or "").strip()
        if not u:
            return False, "Username cannot be empty."
        if self.user_exists(u):
            return False, f"A user named '{u}' already exists."
        ok, msg = self._check_password(password)
        if not ok:
            return False, msg
        if role not in ("user", "admin"):
            role = "user"
        self._add(u, password, role)
        self._save()
        return True, f"User '{u}' created."

    def change_password(self, username, old_pw, new_pw):
        """(ok, message)."""
        key = self._find_key(username)
        if key is None:
            return False, "User not found."
        if self.verify(key, old_pw) is None:
            return False, "Current password is incorrect."
        ok, msg = self._check_password(new_pw)
        if not ok:
            return False, msg
        rec = self.data["users"][key]
        salt = os.urandom(16)
        rec["salt"] = salt.hex()
        rec["hash"] = self._hash(new_pw, salt).hex()
        rec["iterations"] = _ITERATIONS
        self._save()
        return True, "Password changed."

    def delete_user(self, username):
        key = self._find_key(username)
        if key is None:
            return False, "User not found."
        del self.data["users"][key]
        self._save()
        return True, f"User '{key}' deleted."

    @staticmethod
    def _check_password(pw):
        if pw is None or len(pw) < 4:
            return False, "Password must be at least 4 characters."
        return True, ""

    def default_admin_active(self):
        """True if the seeded admin still uses the default password."""
        return self.verify(_DEFAULT_ADMIN[0], _DEFAULT_ADMIN[1]) == "admin"


# ====================================================================
#  Splash / loading
# ====================================================================
class SplashScreen(QWidget):
    """Frameless centered splash with a progress bar."""

    def __init__(self, title="QRA System", message="Loading\u2026", parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setFixedSize(440, 200)
        card = QFrame(self)
        card.setGeometry(0, 0, 440, 200)
        card.setStyleSheet(
            "QFrame{background:#0f1b2d;border:1px solid #24405f;border-radius:14px;}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 26, 28, 24)
        lay.setSpacing(10)

        t = QLabel(title)
        f = QFont(); f.setPointSize(18); f.setBold(True)
        t.setFont(f)
        t.setStyleSheet("color:#eaf2fb;")
        t.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)

        sub = QLabel("Quantitative Risk Assessment")
        sub.setStyleSheet("color:#6f8aa8;font-size:12px;")
        sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(sub)

        lay.addStretch(1)
        self.msg = QLabel(message)
        self.msg.setStyleSheet("color:#9fb4cc;font-size:11px;")
        self.msg.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.msg)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.setStyleSheet(
            "QProgressBar{background:#0b1119;border:1px solid #24405f;border-radius:4px;}"
            "QProgressBar::chunk{background:#3a9ec2;border-radius:4px;}")
        lay.addWidget(self.bar)
        self._center()

    def _center(self):
        try:
            scr = QApplication.primaryScreen().geometry()
            self.move(scr.center().x() - self.width() // 2,
                      scr.center().y() - self.height() // 2)
        except Exception:
            pass

    def set_message(self, text):
        self.msg.setText(text)

    def run(self, app, duration_ms=900, message=None):
        """Show and animate the progress bar to 100% over duration_ms."""
        if message:
            self.set_message(message)
        self.show()
        steps = 24
        delay = max(1, int(duration_ms / steps))
        for i in range(steps + 1):
            self.bar.setValue(int(i * 100 / steps))
            app.processEvents()
            t = time.time() + delay / 1000.0
            while time.time() < t:
                app.processEvents()
        app.processEvents()


# ====================================================================
#  Dialogs
# ====================================================================
_FIELD_SS = (
    "QLineEdit{background:#0b1119;color:#e8eef6;border:1px solid #2a3b52;"
    "border-radius:6px;padding:7px;}")
_PRIMARY_BTN = (
    "QPushButton{background:#3a9ec2;color:white;font-weight:bold;"
    "border-radius:6px;padding:8px 16px;} QPushButton:hover{background:#2f86a6;}")
_PLAIN_BTN = (
    "QPushButton{background:#3a4250;color:#cdd9e6;border-radius:6px;padding:8px 16px;}")


class LoginDialog(QDialog):
    """Sign-in page for users and admins."""

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.username = None
        self.role = None
        self.setWindowTitle("QRA System \u2014 Sign In")
        self.setModal(True)
        self.setMinimumWidth(360)
        self.setStyleSheet("QDialog{background:#101a27;} QLabel{color:#cdd9e6;}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(10)

        head = QLabel("Sign In")
        hf = QFont(); hf.setPointSize(15); hf.setBold(True)
        head.setFont(hf)
        head.setStyleSheet("color:#eaf2fb;")
        lay.addWidget(head)

        form = QFormLayout()
        form.setSpacing(8)
        self.in_user = QLineEdit()
        self.in_user.setStyleSheet(_FIELD_SS)
        self.in_user.setPlaceholderText("username")
        self.in_pw = QLineEdit()
        self.in_pw.setStyleSheet(_FIELD_SS)
        self.in_pw.setEchoMode(QLineEdit.Password)
        self.in_pw.setPlaceholderText("password")
        form.addRow(self._lbl("Username"), self.in_user)
        form.addRow(self._lbl("Password"), self.in_pw)
        lay.addLayout(form)

        self.err = QLabel("")
        self.err.setStyleSheet("color:#e67e7e;font-size:11px;")
        self.err.setWordWrap(True)
        lay.addWidget(self.err)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet(_PLAIN_BTN)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_login = QPushButton("Sign In")
        self.btn_login.setStyleSheet(_PRIMARY_BTN)
        self.btn_login.setDefault(True)
        self.btn_login.clicked.connect(self._try_login)
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_login)
        lay.addLayout(btns)

        if store.default_admin_active():
            hint = QLabel("First run \u2014 default admin:  admin / admin")
            hint.setStyleSheet("color:#6f8aa8;font-size:11px;padding-top:4px;")
            lay.addWidget(hint)

        self.in_pw.returnPressed.connect(self._try_login)
        self.in_user.returnPressed.connect(lambda: self.in_pw.setFocus())
        self.in_user.setFocus()

    def _lbl(self, t):
        l = QLabel(t)
        l.setStyleSheet("color:#9fb4cc;font-size:11px;")
        return l

    def _try_login(self):
        u = self.in_user.text().strip()
        p = self.in_pw.text()
        if not u or not p:
            self.err.setText("Enter both username and password.")
            return
        role = self.store.verify(u, p)
        if role is None:
            self.err.setText("Invalid username or password.")
            self.in_pw.clear()
            self.in_pw.setFocus()
            return
        # resolve canonical username casing
        key = self.store._find_key(u) or u
        self.username = key
        self.role = role
        self.accept()


class CreateUserDialog(QDialog):
    """Admin-only: create a new user or admin account."""

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Create User")
        self.setModal(True)
        self.setMinimumWidth(360)
        self.setStyleSheet("QDialog{background:#101a27;} QLabel{color:#cdd9e6;}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(10)
        head = QLabel("Create User")
        hf = QFont(); hf.setPointSize(14); hf.setBold(True)
        head.setFont(hf); head.setStyleSheet("color:#eaf2fb;")
        lay.addWidget(head)

        form = QFormLayout(); form.setSpacing(8)
        self.in_user = QLineEdit(); self.in_user.setStyleSheet(_FIELD_SS)
        self.in_pw = QLineEdit(); self.in_pw.setStyleSheet(_FIELD_SS)
        self.in_pw.setEchoMode(QLineEdit.Password)
        self.in_pw2 = QLineEdit(); self.in_pw2.setStyleSheet(_FIELD_SS)
        self.in_pw2.setEchoMode(QLineEdit.Password)
        self.cmb_role = QComboBox(); self.cmb_role.addItems(["user", "admin"])
        self.cmb_role.setStyleSheet(
            "QComboBox{background:#0b1119;color:#e8eef6;border:1px solid #2a3b52;"
            "border-radius:6px;padding:6px;}")
        form.addRow(self._lbl("Username"), self.in_user)
        form.addRow(self._lbl("Password"), self.in_pw)
        form.addRow(self._lbl("Confirm"), self.in_pw2)
        form.addRow(self._lbl("Role"), self.cmb_role)
        lay.addLayout(form)

        self.err = QLabel(""); self.err.setStyleSheet("color:#e67e7e;font-size:11px;")
        self.err.setWordWrap(True); lay.addWidget(self.err)

        btns = QHBoxLayout(); btns.addStretch(1)
        b_cancel = QPushButton("Cancel"); b_cancel.setStyleSheet(_PLAIN_BTN)
        b_cancel.clicked.connect(self.reject)
        b_ok = QPushButton("Create"); b_ok.setStyleSheet(_PRIMARY_BTN)
        b_ok.setDefault(True); b_ok.clicked.connect(self._create)
        btns.addWidget(b_cancel); btns.addWidget(b_ok)
        lay.addLayout(btns)
        self.in_user.setFocus()

    def _lbl(self, t):
        l = QLabel(t); l.setStyleSheet("color:#9fb4cc;font-size:11px;")
        return l

    def _create(self):
        if self.in_pw.text() != self.in_pw2.text():
            self.err.setText("Passwords do not match.")
            return
        ok, msg = self.store.create_user(
            self.in_user.text(), self.in_pw.text(), self.cmb_role.currentText())
        if not ok:
            self.err.setText(msg)
            return
        QMessageBox.information(self, "User created", msg)
        self.accept()


class ChangePasswordDialog(QDialog):
    """Any signed-in user changes their own password."""

    def __init__(self, store, username, parent=None):
        super().__init__(parent)
        self.store = store
        self.username = username
        self.setWindowTitle("Change Password")
        self.setModal(True)
        self.setMinimumWidth(360)
        self.setStyleSheet("QDialog{background:#101a27;} QLabel{color:#cdd9e6;}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(10)
        head = QLabel(f"Change Password \u2014 {username}")
        hf = QFont(); hf.setPointSize(14); hf.setBold(True)
        head.setFont(hf); head.setStyleSheet("color:#eaf2fb;")
        lay.addWidget(head)

        form = QFormLayout(); form.setSpacing(8)
        self.in_old = QLineEdit(); self.in_old.setStyleSheet(_FIELD_SS)
        self.in_old.setEchoMode(QLineEdit.Password)
        self.in_new = QLineEdit(); self.in_new.setStyleSheet(_FIELD_SS)
        self.in_new.setEchoMode(QLineEdit.Password)
        self.in_new2 = QLineEdit(); self.in_new2.setStyleSheet(_FIELD_SS)
        self.in_new2.setEchoMode(QLineEdit.Password)
        form.addRow(self._lbl("Current"), self.in_old)
        form.addRow(self._lbl("New"), self.in_new)
        form.addRow(self._lbl("Confirm"), self.in_new2)
        lay.addLayout(form)

        self.err = QLabel(""); self.err.setStyleSheet("color:#e67e7e;font-size:11px;")
        self.err.setWordWrap(True); lay.addWidget(self.err)

        btns = QHBoxLayout(); btns.addStretch(1)
        b_cancel = QPushButton("Cancel"); b_cancel.setStyleSheet(_PLAIN_BTN)
        b_cancel.clicked.connect(self.reject)
        b_ok = QPushButton("Update"); b_ok.setStyleSheet(_PRIMARY_BTN)
        b_ok.setDefault(True); b_ok.clicked.connect(self._change)
        btns.addWidget(b_cancel); btns.addWidget(b_ok)
        lay.addLayout(btns)
        self.in_old.setFocus()

    def _lbl(self, t):
        l = QLabel(t); l.setStyleSheet("color:#9fb4cc;font-size:11px;")
        return l

    def _change(self):
        if self.in_new.text() != self.in_new2.text():
            self.err.setText("New passwords do not match.")
            return
        ok, msg = self.store.change_password(
            self.username, self.in_old.text(), self.in_new.text())
        if not ok:
            self.err.setText(msg)
            return
        QMessageBox.information(self, "Password changed", msg)
        self.accept()


# ====================================================================
#  Account menu
# ====================================================================
def install_account_menu(window, store, username, role, on_sign_out=None):
    """Add an 'Account' menu to a QMainWindow with role-appropriate actions."""
    try:
        bar = window.menuBar()
    except Exception:
        return
    menu = bar.addMenu("Account")

    who = menu.addAction(f"Signed in as {username}  ({role})")
    who.setEnabled(False)
    menu.addSeparator()

    act_pw = menu.addAction("Change Password\u2026")
    act_pw.triggered.connect(
        lambda: ChangePasswordDialog(store, username, window).exec_())

    if role == "admin":
        act_new = menu.addAction("Create User\u2026")
        act_new.triggered.connect(
            lambda: CreateUserDialog(store, window).exec_())

    if on_sign_out is not None:
        menu.addSeparator()
        act_out = menu.addAction("Sign Out")
        act_out.triggered.connect(on_sign_out)
    return menu