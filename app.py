#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ООО «Обувь» — Информационная система
Демо-экзамен 2025-26
Специальность: 09.02.07 «Информационные системы и программирование»
Профиль: «Разработка и администрирование баз данных»
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk, ImageOps
import sqlite3
import os
import shutil
import re
from datetime import datetime

# ─── НАСТРОЙКИ ──────────────────────────────────────────────────────────────
DB_PATH = "shoes.db"
IMAGES_DIR = "images"
PLACEHOLDER = os.path.join(IMAGES_DIR, "picture.png")

# Цвета по руководству по стилю
COLOR_BG = "#FFFFFF"
COLOR_BG2 = "#7FFF00"
COLOR_ACCENT = "#00FA9A"
COLOR_DISCOUNT_HIGH = "#2E8B57"
COLOR_NO_STOCK = "#87CEEB"  # голубой

FONT_FAMILY = "Times New Roman"

# Роли
ROLE_ADMIN = 1
ROLE_MANAGER = 2
ROLE_CLIENT = 3
ROLE_GUEST = 0


def get_connection():
    """Возвращает подключение к SQLite."""
    return sqlite3.connect(DB_PATH)


class Database:
    """Класс для работы с базой данных."""

    @staticmethod
    def get_user(login, password):
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """SELECT u.id, u.name, u.role_id, r.name as role_name
               FROM users u JOIN roles r ON u.role_id = r.id
               WHERE u.login = ? AND u.pass = ?""",
            (login, password)
        )
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_all_shoes(search="", supplier_id=None, sort_qty=None):
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        sql = """
            SELECT s.*,
                   c.name as category_name,
                   p.name as producer_name,
                   sup.name as supplier_name,
                   st.name as shoe_type_name,
                   u.name as unit_name
            FROM shoes s
            LEFT JOIN category c ON s.category_id = c.id
            LEFT JOIN producers p ON s.producer_id = p.id
            LEFT JOIN suppliers sup ON s.supplier_id = sup.id
            LEFT JOIN shoe_types st ON s.shoe_type_id = st.id
            LEFT JOIN units u ON s.unit_id = u.id
            WHERE 1=1
        """
        params = []
        if search:
            sql += """ AND (
                s.name LIKE ? OR s.art LIKE ? OR IFNULL(s.description, '') LIKE ?
                OR c.name LIKE ? OR p.name LIKE ? OR sup.name LIKE ?
                OR st.name LIKE ?
            )"""
            like = f"%{search}%"
            params.extend([like, like, like, like, like, like, like])
        if supplier_id:
            sql += " AND s.supplier_id = ?"
            params.append(supplier_id)
        if sort_qty == "asc":
            sql += " ORDER BY s.qty ASC"
        elif sort_qty == "desc":
            sql += " ORDER BY s.qty DESC"
        else:
            sql += " ORDER BY s.id ASC"
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def get_shoe_by_id(shoe_id):
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM shoes WHERE id = ?", (shoe_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def add_shoe(data):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO shoes (art, shoe_type_id, unit_id, price, supplier_id,
                               producer_id, category_id, discount, qty, name, photo, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (data["art"], data["shoe_type_id"], data["unit_id"],
              data["price"], data["supplier_id"], data["producer_id"],
              data["category_id"], data["discount"], data["qty"],
              data["name"], data.get("photo"), data.get("description", "")))
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return new_id

    @staticmethod
    def update_shoe(shoe_id, data):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE shoes SET
                art = ?, shoe_type_id = ?, unit_id = ?, price = ?,
                supplier_id = ?, producer_id = ?, category_id = ?,
                discount = ?, qty = ?, name = ?, photo = ?,
                description = ?
            WHERE id = ?
        """, (data["art"], data["shoe_type_id"], data["unit_id"],
              data["price"], data["supplier_id"], data["producer_id"],
              data["category_id"], data["discount"], data["qty"],
              data["name"], data.get("photo"), data.get("description", ""),
              shoe_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete_shoe(shoe_id):
        conn = get_connection()
        cur = conn.cursor()
        # Проверка на использование в заказах
        cur.execute("SELECT COUNT(*) FROM order_pos WHERE shoe_id = ?", (shoe_id,))
        if cur.fetchone()[0] > 0:
            conn.close()
            return False, "Товар присутствует в заказе. Удаление запрещено."
        # Удаление фото если есть
        cur.execute("SELECT photo FROM shoes WHERE id = ?", (shoe_id,))
        row = cur.fetchone()
        if row and row[0]:
            path = os.path.join(IMAGES_DIR, row[0])
            if os.path.exists(path):
                os.remove(path)
        cur.execute("DELETE FROM shoes WHERE id = ?", (shoe_id,))
        conn.commit()
        conn.close()
        return True, "Товар удалён"

    @staticmethod
    def get_next_shoe_id():
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT MAX(id) FROM shoes")
        row = cur.fetchone()
        conn.close()
        return (row[0] or 0) + 1

    @staticmethod
    def get_reference(table):
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table} ORDER BY id")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def get_orders():
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT o.*,
                   os.name as status_name,
                   pp.index || ', ' || pp.city || ', ' || pp.street || ', ' || pp.home as address,
                   u.name as user_name
            FROM orders o
            LEFT JOIN order_statuses os ON o.order_status_id = os.id
            LEFT JOIN pickup_points pp ON o.pickup_point_id = pp.id
            LEFT JOIN users u ON o.user_id = u.id
            ORDER BY o.id
        """)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def get_order_by_id(order_id):
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def add_order(data):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO orders (order_number, order_date, delivery_date,
                                pickup_point_id, user_id, delivery_code, order_status_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (data["order_number"], data["order_date"], data["delivery_date"],
              data["pickup_point_id"], data["user_id"], data["delivery_code"],
              data["order_status_id"]))
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return new_id

    @staticmethod
    def update_order(order_id, data):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE orders SET
                order_number = ?, order_date = ?, delivery_date = ?,
                pickup_point_id = ?, user_id = ?, delivery_code = ?,
                order_status_id = ?
            WHERE id = ?
        """, (data["order_number"], data["order_date"], data["delivery_date"],
              data["pickup_point_id"], data["user_id"], data["delivery_code"],
              data["order_status_id"], order_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete_order(order_id):
        conn = get_connection()
        cur = conn.cursor()
        # Удаляем позиции заказа
        cur.execute("DELETE FROM order_pos WHERE order_id = ?", (order_id,))
        cur.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()
        return True, "Заказ удалён"

    @staticmethod
    def get_next_order_number():
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT MAX(order_number) FROM orders")
        row = cur.fetchone()
        conn.close()
        return (row[0] or 0) + 1


# ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ─────────────────────────────────────────────────

def resize_image(path, max_w=300, max_h=200):
    """Изменяет размер изображения с сохранением пропорций."""
    if not path or not os.path.exists(path):
        path = PLACEHOLDER
    img = Image.open(path)
    img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(img)


def validate_price(value):
    try:
        v = float(value.replace(",", "."))
        return v >= 0
    except ValueError:
        return False


def validate_int(value):
    try:
        v = int(value)
        return v >= 0
    except ValueError:
        return False


# ─── ГЛАВНОЕ ОКНО ПРИЛОЖЕНИЯ ──────────────────────────────────────────────────

class ShoesApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ООО «Обувь» — Авторизация")
        self.geometry("900x700")
        self.configure(bg=COLOR_BG)
        self.resizable(True, True)
        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        self.current_user = None  # dict с id, name, role_id, role_name
        self.edit_window_open = False

        # Контейнер для фреймов
        self.container = tk.Frame(self, bg=COLOR_BG)
        self.container.pack(fill="both", expand=True)

        self.frames = {}
        for F in (AuthFrame, ProductListFrame, ProductEditFrame, OrderListFrame, OrderEditFrame):
            frame = F(self.container, self)
            self.frames[F] = frame
            frame.place(in_=self.container, x=0, y=0, relwidth=1, relheight=1)

        self.show_frame(AuthFrame)

    def show_frame(self, cls, **kwargs):
        frame = self.frames[cls]
        frame.tkraise()
        if hasattr(frame, "on_raise"):
            frame.on_raise(**kwargs)

    def set_user(self, user):
        self.current_user = user

    def get_role(self):
        if self.current_user is None:
            return ROLE_GUEST
        return self.current_user["role_id"]

    def is_admin(self):
        return self.get_role() == ROLE_ADMIN

    def is_manager(self):
        return self.get_role() == ROLE_MANAGER

    def is_client(self):
        return self.get_role() == ROLE_CLIENT

    def is_guest(self):
        return self.get_role() == ROLE_GUEST

    def logout(self):
        self.current_user = None
        self.title("ООО «Обувь» — Авторизация")
        self.show_frame(AuthFrame)


# ─── ОКНО АВТОРИЗАЦИИ ───────────────────────────────────────────────────────────

class AuthFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller

        # Заголовок
        lbl_title = tk.Label(self, text="ООО «Обувь»", font=(FONT_FAMILY, 24, "bold"),
                             bg=COLOR_BG, fg="#000000")
        lbl_title.pack(pady=20)

        # Логотип (если есть logo.png в images)
        logo_path = os.path.join(IMAGES_DIR, "logo.png")
        if os.path.exists(logo_path):
            img = Image.open(logo_path)
            img = img.resize((200, 100), Image.Resampling.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(img)
            lbl_logo = tk.Label(self, image=self.logo_img, bg=COLOR_BG)
            lbl_logo.pack(pady=5)

        frame_form = tk.Frame(self, bg=COLOR_BG)
        frame_form.pack(pady=30)

        tk.Label(frame_form, text="Логин:", font=(FONT_FAMILY, 14),
                 bg=COLOR_BG).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.entry_login = tk.Entry(frame_form, font=(FONT_FAMILY, 14), width=25)
        self.entry_login.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(frame_form, text="Пароль:", font=(FONT_FAMILY, 14),
                 bg=COLOR_BG).grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.entry_pass = tk.Entry(frame_form, font=(FONT_FAMILY, 14), width=25, show="*")
        self.entry_pass.grid(row=1, column=1, padx=5, pady=5)

        btn_login = tk.Button(frame_form, text="Войти", font=(FONT_FAMILY, 12),
                              bg=COLOR_ACCENT, command=self.do_login)
        btn_login.grid(row=2, column=0, columnspan=2, pady=15)

        btn_guest = tk.Button(frame_form, text="Войти как гость", font=(FONT_FAMILY, 12),
                                bg=COLOR_BG2, command=self.do_guest)
        btn_guest.grid(row=3, column=0, columnspan=2, pady=5)

        self.lbl_error = tk.Label(self, text="", font=(FONT_FAMILY, 12),
                                  bg=COLOR_BG, fg="red")
        self.lbl_error.pack(pady=10)

        # Привязка Enter
        self.entry_login.bind("<Return>", lambda e: self.do_login())
        self.entry_pass.bind("<Return>", lambda e: self.do_login())

    def do_login(self):
        login = self.entry_login.get().strip()
        password = self.entry_pass.get().strip()
        if not login or not password:
            self.lbl_error.config(text="Введите логин и пароль")
            return
        user = Database.get_user(login, password)
        if user:
            self.controller.set_user(user)
            self.lbl_error.config(text="")
            self.entry_login.delete(0, tk.END)
            self.entry_pass.delete(0, tk.END)
            self.controller.show_frame(ProductListFrame)
            self.controller.title(f"ООО «Обувь» — Товары ({user["name"]})")
        else:
            self.lbl_error.config(text="Неверный логин или пароль")

    def do_guest(self):
        self.controller.set_user(None)
        self.lbl_error.config(text="")
        self.controller.show_frame(ProductListFrame)
        self.controller.title("ООО «Обувь» — Товары (Гость)")


# ─── СПИСОК ТОВАРОВ ────────────────────────────────────────────────────────────

class ProductListFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller
        self.shoes = []
        self.photo_refs = []  # чтобы GC не удалил

        # Верхняя панель
        self.frame_top = tk.Frame(self, bg=COLOR_BG2, height=50)
        self.frame_top.pack(fill="x", side="top")
        self.frame_top.pack_propagate(False)

        self.lbl_user = tk.Label(self.frame_top, text="", font=(FONT_FAMILY, 12),
                                 bg=COLOR_BG2)
        self.lbl_user.pack(side="right", padx=10, pady=5)

        btn_back = tk.Button(self.frame_top, text="← Выход", font=(FONT_FAMILY, 11),
                             bg=COLOR_ACCENT, command=self.controller.logout)
        btn_back.pack(side="left", padx=5, pady=5)

        self.btn_orders = tk.Button(self.frame_top, text="Заказы", font=(FONT_FAMILY, 11),
                                    bg=COLOR_ACCENT, command=self.open_orders)
        self.btn_orders.pack(side="left", padx=5, pady=5)

        self.btn_add = tk.Button(self.frame_top, text="Добавить товар", font=(FONT_FAMILY, 11),
                                 bg=COLOR_ACCENT, command=self.add_shoe)
        self.btn_add.pack(side="left", padx=5, pady=5)

        # Панель фильтров (только менеджер/админ)
        self.frame_filters = tk.Frame(self, bg=COLOR_BG)
        self.frame_filters.pack(fill="x", padx=10, pady=5)

        tk.Label(self.frame_filters, text="Поиск:", font=(FONT_FAMILY, 12),
                 bg=COLOR_BG).pack(side="left", padx=2)
        self.entry_search = tk.Entry(self.frame_filters, font=(FONT_FAMILY, 12), width=20)
        self.entry_search.pack(side="left", padx=2)
        self.entry_search.bind("<KeyRelease>", lambda e: self.load_products())

        tk.Label(self.frame_filters, text="Поставщик:", font=(FONT_FAMILY, 12),
                 bg=COLOR_BG).pack(side="left", padx=(15, 2))
        self.combo_supplier = ttk.Combobox(self.frame_filters, font=(FONT_FAMILY, 12),
                                           state="readonly", width=18)
        self.combo_supplier.pack(side="left", padx=2)
        self.combo_supplier.bind("<<ComboboxSelected>>", lambda e: self.load_products())

        tk.Label(self.frame_filters, text="Сортировка по кол-ву:", font=(FONT_FAMILY, 12),
                 bg=COLOR_BG).pack(side="left", padx=(15, 2))
        self.combo_sort = ttk.Combobox(self.frame_filters, font=(FONT_FAMILY, 12),
                                       state="readonly", width=12,
                                       values=["Нет", "По возрастанию", "По убыванию"])
        self.combo_sort.current(0)
        self.combo_sort.pack(side="left", padx=2)
        self.combo_sort.bind("<<ComboboxSelected>>", lambda e: self.load_products())

        # Canvas + Scrollbar для товаров
        self.canvas = tk.Canvas(self, bg=COLOR_BG, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=COLOR_BG)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Привязка колеса мыши
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def on_raise(self, **kwargs):
        role = self.controller.get_role()
        name = self.controller.current_user["name"] if self.controller.current_user else "Гость"
        self.lbl_user.config(text=f"{name}")

        # Видимость элементов по ролям
        if self.controller.is_admin() or self.controller.is_manager():
            self.frame_filters.pack(fill="x", padx=10, pady=5)
            self.btn_orders.pack(side="left", padx=5, pady=5)
            if self.controller.is_admin():
                self.btn_add.pack(side="left", padx=5, pady=5)
            else:
                self.btn_add.pack_forget()
        else:
            self.frame_filters.pack_forget()
            self.btn_orders.pack_forget()
            self.btn_add.pack_forget()

        self.load_suppliers()
        self.load_products()

    def load_suppliers(self):
        suppliers = Database.get_reference("suppliers")
        self.supplier_map = {"Все поставщики": None}
        values = ["Все поставщики"]
        for s in suppliers:
            self.supplier_map[s["name"]] = s["id"]
            values.append(s["name"])
        self.combo_supplier["values"] = values
        self.combo_supplier.current(0)

    def load_products(self):
        # Очистка
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.photo_refs.clear()

        role = self.controller.get_role()
        search = ""
        supplier_id = None
        sort_qty = None

        if role in (ROLE_ADMIN, ROLE_MANAGER):
            search = self.entry_search.get().strip()
            sup_name = self.combo_supplier.get()
            supplier_id = self.supplier_map.get(sup_name)
            sort_text = self.combo_sort.get()
            if sort_text == "По возрастанию":
                sort_qty = "asc"
            elif sort_text == "По убыванию":
                sort_qty = "desc"

        self.shoes = Database.get_all_shoes(search=search, supplier_id=supplier_id, sort_qty=sort_qty)

        if not self.shoes:
            lbl = tk.Label(self.scrollable_frame, text="Товары не найдены",
                             font=(FONT_FAMILY, 14), bg=COLOR_BG)
            lbl.pack(pady=20)
            return

        for shoe in self.shoes:
            self.create_shoe_card(shoe)

    def create_shoe_card(self, shoe):
        discount = shoe["discount"] or 0
        qty = shoe["qty"] or 0
        price = shoe["price"] or 0
        final_price = round(price * (1 - discount/100), 2)

        # Определение фона
        bg_color = COLOR_BG
        if discount > 15:
            bg_color = COLOR_DISCOUNT_HIGH
        elif qty == 0:
            bg_color = COLOR_NO_STOCK

        card = tk.Frame(self.scrollable_frame, bg=bg_color, bd=2, relief="groove")
        card.pack(fill="x", padx=10, pady=5, expand=True)
        card.bind("<Button-1>", lambda e, sid=shoe["id"]: self.edit_shoe(sid))

        # Левая часть — фото
        photo_path = os.path.join(IMAGES_DIR, shoe["photo"]) if shoe["photo"] else PLACEHOLDER
        img = resize_image(photo_path, 120, 120)
        self.photo_refs.append(img)
        lbl_img = tk.Label(card, image=img, bg=bg_color)
        lbl_img.pack(side="left", padx=10, pady=10)
        lbl_img.bind("<Button-1>", lambda e, sid=shoe["id"]: self.edit_shoe(sid))

        # Центральная часть — текст
        info_frame = tk.Frame(card, bg=bg_color)
        info_frame.pack(side="left", fill="both", expand=True, padx=5, pady=10)

        cat_name = shoe.get("category_name", "") or ""
        st_name = shoe.get("shoe_type_name", "") or ""
        header = f"{cat_name} | {shoe["name"]}"
        tk.Label(info_frame, text=header, font=(FONT_FAMILY, 14, "bold"),
                 bg=bg_color, fg="#000000", anchor="w").pack(fill="x")

        desc = shoe.get("description") or "Описание отсутствует"
        tk.Label(info_frame, text=f"Описание: {desc}", font=(FONT_FAMILY, 12),
                 bg=bg_color, anchor="w").pack(fill="x")
        tk.Label(info_frame, text=f"Производитель: {shoe.get("producer_name", "")}",
                 font=(FONT_FAMILY, 12), bg=bg_color, anchor="w").pack(fill="x")
        tk.Label(info_frame, text=f"Поставщик: {shoe.get("supplier_name", "")}",
                 font=(FONT_FAMILY, 12), bg=bg_color, anchor="w").pack(fill="x")

        # Цена
        price_frame = tk.Frame(info_frame, bg=bg_color)
        price_frame.pack(fill="x")
        if discount > 0:
            lbl_old = tk.Label(price_frame, text=f"{price:.2f} ₽",
                               font=(FONT_FAMILY, 12), bg=bg_color, fg="red")
            lbl_old.pack(side="left")
            # перечеркивание
            lbl_old.config(font=(FONT_FAMILY, 12, "overstrike"))
            lbl_new = tk.Label(price_frame, text=f"  {final_price:.2f} ₽",
                               font=(FONT_FAMILY, 12, "bold"), bg=bg_color, fg="#000000")
            lbl_new.pack(side="left")
        else:
            tk.Label(price_frame, text=f"{price:.2f} ₽", font=(FONT_FAMILY, 12),
                     bg=bg_color, fg="#000000").pack(side="left")

        tk.Label(info_frame, text=f"Ед. изм.: {shoe.get("unit_name", "шт.")}",
                 font=(FONT_FAMILY, 12), bg=bg_color, anchor="w").pack(fill="x")
        tk.Label(info_frame, text=f"Кол-во на складе: {qty}",
                 font=(FONT_FAMILY, 12), bg=bg_color, anchor="w").pack(fill="x")

        # Правая часть — скидка
        right_frame = tk.Frame(card, bg=bg_color, width=100)
        right_frame.pack(side="right", fill="y", padx=10, pady=10)
        right_frame.pack_propagate(False)
        tk.Label(right_frame, text=f"Скидка\n{discount}%", font=(FONT_FAMILY, 14, "bold"),
                 bg=bg_color, fg="#000000").pack(expand=True)

    def add_shoe(self):
        if not self.controller.is_admin():
            messagebox.showerror("Ошибка", "Недостаточно прав")
            return
        if self.controller.edit_window_open:
            messagebox.showwarning("Внимание", "Закройте текущее окно редактирования")
            return
        self.controller.show_frame(ProductEditFrame, shoe_id=None)

    def edit_shoe(self, shoe_id):
        if not self.controller.is_admin():
            return
        if self.controller.edit_window_open:
            messagebox.showwarning("Внимание", "Закройте текущее окно редактирования")
            return
        self.controller.show_frame(ProductEditFrame, shoe_id=shoe_id)

    def open_orders(self):
        if self.controller.is_admin() or self.controller.is_manager():
            self.controller.show_frame(OrderListFrame)


# ─── ФОРМА ДОБАВЛЕНИЯ/РЕДАКТИРОВАНИЯ ТОВАРА ───────────────────────────────────

class ProductEditFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller
        self.shoe_id = None
        self.photo_path = None
        self.img_ref = None

        # Верх
        top = tk.Frame(self, bg=COLOR_BG2, height=50)
        top.pack(fill="x", side="top")
        top.pack_propagate(False)
        tk.Label(top, text="Товар", font=(FONT_FAMILY, 14, "bold"), bg=COLOR_BG2).pack(side="left", padx=10, pady=5)
        btn_back = tk.Button(top, text="← Назад", font=(FONT_FAMILY, 11),
                             bg=COLOR_ACCENT, command=self.go_back)
        btn_back.pack(side="left", padx=5, pady=5)

        # Форма
        form = tk.Frame(self, bg=COLOR_BG)
        form.pack(padx=20, pady=20, fill="both", expand=True)

        # Фото
        self.lbl_photo = tk.Label(form, bg="#DDDDDD", width=30, height=10)
        self.lbl_photo.grid(row=0, column=0, rowspan=6, padx=10, pady=5, sticky="nw")
        btn_photo = tk.Button(form, text="Выбрать фото", font=(FONT_FAMILY, 11),
                              bg=COLOR_ACCENT, command=self.choose_photo)
        btn_photo.grid(row=6, column=0, pady=5)

        # Поля
        labels = ["ID:", "Артикул:*", "Наименование:*", "Категория:*", "Тип обуви:*",
                  "Производитель:*", "Поставщик:*", "Ед. изм.:*", "Цена:*",
                  "Скидка (%):*", "Количество:*", "Описание:"]
        self.entries = {}
        self.combos = {}
        row = 0
        col_start = 1

        # ID (только для чтения при редактировании)
        tk.Label(form, text="ID:", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=row, column=col_start, sticky="e", padx=5, pady=3)
        self.lbl_id = tk.Label(form, text="", font=(FONT_FAMILY, 12), bg=COLOR_BG, anchor="w")
        self.lbl_id.grid(row=row, column=col_start+1, sticky="w", padx=5, pady=3)
        row += 1

        # Артикул
        tk.Label(form, text="Артикул:*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=row, column=col_start, sticky="e", padx=5, pady=3)
        self.entry_art = tk.Entry(form, font=(FONT_FAMILY, 12), width=30)
        self.entry_art.grid(row=row, column=col_start+1, sticky="w", padx=5, pady=3)
        row += 1

        # Наименование
        tk.Label(form, text="Наименование:*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=row, column=col_start, sticky="e", padx=5, pady=3)
        self.entry_name = tk.Entry(form, font=(FONT_FAMILY, 12), width=30)
        self.entry_name.grid(row=row, column=col_start+1, sticky="w", padx=5, pady=3)
        row += 1

        # Категория
        tk.Label(form, text="Категория:*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=row, column=col_start, sticky="e", padx=5, pady=3)
        self.combo_category = ttk.Combobox(form, font=(FONT_FAMILY, 12), state="readonly", width=28)
        self.combo_category.grid(row=row, column=col_start+1, sticky="w", padx=5, pady=3)
        row += 1

        # Тип обуви
        tk.Label(form, text="Тип обуви:*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=row, column=col_start, sticky="e", padx=5, pady=3)
        self.combo_type = ttk.Combobox(form, font=(FONT_FAMILY, 12), state="readonly", width=28)
        self.combo_type.grid(row=row, column=col_start+1, sticky="w", padx=5, pady=3)
        row += 1

        # Производитель
        tk.Label(form, text="Производитель:*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=row, column=col_start, sticky="e", padx=5, pady=3)
        self.combo_producer = ttk.Combobox(form, font=(FONT_FAMILY, 12), state="readonly", width=28)
        self.combo_producer.grid(row=row, column=col_start+1, sticky="w", padx=5, pady=3)
        row += 1

        # Поставщик
        tk.Label(form, text="Поставщик:*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=row, column=col_start, sticky="e", padx=5, pady=3)
        self.combo_supplier = ttk.Combobox(form, font=(FONT_FAMILY, 12), state="readonly", width=28)
        self.combo_supplier.grid(row=row, column=col_start+1, sticky="w", padx=5, pady=3)
        row += 1

        # Единица
        tk.Label(form, text="Ед. изм.:*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=row, column=col_start, sticky="e", padx=5, pady=3)
        self.combo_unit = ttk.Combobox(form, font=(FONT_FAMILY, 12), state="readonly", width=28)
        self.combo_unit.grid(row=row, column=col_start+1, sticky="w", padx=5, pady=3)
        row += 1

        # Цена
        tk.Label(form, text="Цена:*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=row, column=col_start, sticky="e", padx=5, pady=3)
        self.entry_price = tk.Entry(form, font=(FONT_FAMILY, 12), width=30)
        self.entry_price.grid(row=row, column=col_start+1, sticky="w", padx=5, pady=3)
        row += 1

        # Скидка
        tk.Label(form, text="Скидка (%):*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=row, column=col_start, sticky="e", padx=5, pady=3)
        self.entry_discount = tk.Entry(form, font=(FONT_FAMILY, 12), width=30)
        self.entry_discount.grid(row=row, column=col_start+1, sticky="w", padx=5, pady=3)
        row += 1

        # Количество
        tk.Label(form, text="Количество:*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=row, column=col_start, sticky="e", padx=5, pady=3)
        self.entry_qty = tk.Entry(form, font=(FONT_FAMILY, 12), width=30)
        self.entry_qty.grid(row=row, column=col_start+1, sticky="w", padx=5, pady=3)
        row += 1

        # Описание
        tk.Label(form, text="Описание:", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=row, column=col_start, sticky="ne", padx=5, pady=3)
        self.text_desc = tk.Text(form, font=(FONT_FAMILY, 12), width=30, height=4)
        self.text_desc.grid(row=row, column=col_start+1, sticky="w", padx=5, pady=3)
        row += 1

        # Кнопки
        btn_frame = tk.Frame(self, bg=COLOR_BG)
        btn_frame.pack(pady=10)
        self.btn_save = tk.Button(btn_frame, text="Сохранить", font=(FONT_FAMILY, 12),
                                  bg=COLOR_ACCENT, command=self.save)
        self.btn_save.pack(side="left", padx=10)
        self.btn_delete = tk.Button(btn_frame, text="Удалить", font=(FONT_FAMILY, 12),
                                    bg="#FF6B6B", command=self.delete)
        self.btn_delete.pack(side="left", padx=10)

    def on_raise(self, shoe_id=None, **kwargs):
        self.controller.edit_window_open = True
        self.shoe_id = shoe_id
        self.load_combos()
        if shoe_id:
            self.controller.title("ООО «Обувь» — Редактирование товара")
            self.lbl_id.config(text=str(shoe_id))
            self.btn_delete.pack(side="left", padx=10)
            self.fill_form(shoe_id)
        else:
            self.controller.title("ООО «Обувь» — Добавление товара")
            new_id = Database.get_next_shoe_id()
            self.lbl_id.config(text=str(new_id))
            self.clear_form()
            self.btn_delete.pack_forget()
            self.photo_path = None
            self.show_photo(PLACEHOLDER)

    def load_combos(self):
        cats = Database.get_reference("category")
        self.combo_category["values"] = [c["name"] for c in cats]
        self.cat_map = {c["name"]: c["id"] for c in cats}

        types = Database.get_reference("shoe_types")
        self.combo_type["values"] = [t["name"] for t in types]
        self.type_map = {t["name"]: t["id"] for t in types}

        prod = Database.get_reference("producers")
        self.combo_producer["values"] = [p["name"] for p in prod]
        self.prod_map = {p["name"]: p["id"] for p in prod}

        sup = Database.get_reference("suppliers")
        self.combo_supplier["values"] = [s["name"] for s in sup]
        self.sup_map = {s["name"]: s["id"] for s in sup}

        units = Database.get_reference("units")
        self.combo_unit["values"] = [u["name"] for u in units]
        self.unit_map = {u["name"]: u["id"] for u in units}

    def fill_form(self, shoe_id):
        shoe = Database.get_shoe_by_id(shoe_id)
        if not shoe:
            return
        self.entry_art.delete(0, tk.END)
        self.entry_art.insert(0, shoe["art"])
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, shoe["name"])
        self.entry_price.delete(0, tk.END)
        self.entry_price.insert(0, str(shoe["price"]))
        self.entry_discount.delete(0, tk.END)
        self.entry_discount.insert(0, str(shoe["discount"]))
        self.entry_qty.delete(0, tk.END)
        self.entry_qty.insert(0, str(shoe["qty"]))
        self.text_desc.delete("1.0", tk.END)
        self.text_desc.insert("1.0", shoe.get("description", ""))

        # Установка комбобоксов
        for combo, map_dict, value_id in [
            (self.combo_category, self.cat_map, shoe["category_id"]),
            (self.combo_type, self.type_map, shoe["shoe_type_id"]),
            (self.combo_producer, self.prod_map, shoe["producer_id"]),
            (self.combo_supplier, self.sup_map, shoe["supplier_id"]),
            (self.combo_unit, self.unit_map, shoe["unit_id"]),
        ]:
            for name, idx in map_dict.items():
                if idx == value_id:
                    combo.set(name)
                    break

        self.photo_path = shoe.get("photo")
        path = os.path.join(IMAGES_DIR, self.photo_path) if self.photo_path else PLACEHOLDER
        self.show_photo(path)

    def clear_form(self):
        for w in [self.entry_art, self.entry_name, self.entry_price,
                  self.entry_discount, self.entry_qty]:
            w.delete(0, tk.END)
        self.text_desc.delete("1.0", tk.END)
        for c in [self.combo_category, self.combo_type, self.combo_producer,
                  self.combo_supplier, self.combo_unit]:
            c.set("")

    def show_photo(self, path):
        if not os.path.exists(path):
            path = PLACEHOLDER
        try:
            img = Image.open(path)
            img.thumbnail((300, 200), Image.Resampling.LANCZOS)
            self.img_ref = ImageTk.PhotoImage(img)
            self.lbl_photo.config(image=self.img_ref, width=300, height=200)
        except Exception:
            self.lbl_photo.config(text="Нет фото", width=30, height=10)

    def choose_photo(self):
        path = filedialog.askopenfilename(
            title="Выберите изображение",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp")]
        )
        if not path:
            return
        # Оптимизация: ресайз до 300x200 и сохранение в images
        try:
            img = Image.open(path)
            img = ImageOps.contain(img, (300, 200))
            ext = os.path.splitext(path)[1].lower()
            if ext not in (".png", ".jpg", ".jpeg"):
                ext = ".png"
            new_name = f"shoe_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
            dest = os.path.join(IMAGES_DIR, new_name)
            # Удаление старого фото если замена
            if self.shoe_id and self.photo_path:
                old = os.path.join(IMAGES_DIR, self.photo_path)
                if os.path.exists(old) and old != PLACEHOLDER:
                    os.remove(old)
            img.save(dest)
            self.photo_path = new_name
            self.show_photo(dest)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обработать фото: {e}")

    def save(self):
        art = self.entry_art.get().strip()
        name = self.entry_name.get().strip()
        price_str = self.entry_price.get().strip()
        disc_str = self.entry_discount.get().strip()
        qty_str = self.entry_qty.get().strip()
        desc = self.text_desc.get("1.0", tk.END).strip()

        if not all([art, name, price_str, disc_str, qty_str]):
            messagebox.showerror("Ошибка", "Заполните обязательные поля")
            return
        if not validate_price(price_str):
            messagebox.showerror("Ошибка", "Цена должна быть неотрицательным числом")
            return
        if not validate_int(disc_str) or not (0 <= int(disc_str) <= 100):
            messagebox.showerror("Ошибка", "Скидка должна быть целым числом 0-100")
            return
        if not validate_int(qty_str):
            messagebox.showerror("Ошибка", "Количество должно быть неотрицательным целым числом")
            return
        if not all([self.combo_category.get(), self.combo_type.get(),
                    self.combo_producer.get(), self.combo_supplier.get(),
                    self.combo_unit.get()]):
            messagebox.showerror("Ошибка", "Выберите все значения из списков")
            return

        data = {
            "art": art,
            "name": name,
            "price": float(price_str.replace(",", ".")),
            "discount": int(disc_str),
            "qty": int(qty_str),
            "description": desc,
            "category_id": self.cat_map[self.combo_category.get()],
            "shoe_type_id": self.type_map[self.combo_type.get()],
            "producer_id": self.prod_map[self.combo_producer.get()],
            "supplier_id": self.sup_map[self.combo_supplier.get()],
            "unit_id": self.unit_map[self.combo_unit.get()],
            "photo": self.photo_path
        }

        try:
            if self.shoe_id:
                Database.update_shoe(self.shoe_id, data)
                messagebox.showinfo("Успех", "Товар обновлён")
            else:
                new_id = Database.add_shoe(data)
                self.shoe_id = new_id
                self.lbl_id.config(text=str(new_id))
                messagebox.showinfo("Успех", "Товар добавлен")
            self.go_back()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка сохранения: {e}")

    def delete(self):
        if not self.shoe_id:
            return
        if not messagebox.askyesno("Подтверждение", "Удалить товар?"):
            return
        ok, msg = Database.delete_shoe(self.shoe_id)
        if ok:
            messagebox.showinfo("Успех", msg)
            self.go_back()
        else:
            messagebox.showerror("Ошибка", msg)

    def go_back(self):
        self.controller.edit_window_open = False
        self.controller.show_frame(ProductListFrame)


# ─── СПИСОК ЗАКАЗОВ ────────────────────────────────────────────────────────────

class OrderListFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller

        top = tk.Frame(self, bg=COLOR_BG2, height=50)
        top.pack(fill="x", side="top")
        top.pack_propagate(False)
        tk.Label(top, text="Заказы", font=(FONT_FAMILY, 14, "bold"), bg=COLOR_BG2).pack(side="left", padx=10, pady=5)
        btn_back = tk.Button(top, text="← Назад", font=(FONT_FAMILY, 11),
                             bg=COLOR_ACCENT, command=lambda: controller.show_frame(ProductListFrame))
        btn_back.pack(side="left", padx=5, pady=5)

        self.btn_add = tk.Button(top, text="Добавить заказ", font=(FONT_FAMILY, 11),
                                 bg=COLOR_ACCENT, command=self.add_order)
        self.btn_add.pack(side="left", padx=5, pady=5)

        self.lbl_user = tk.Label(top, text="", font=(FONT_FAMILY, 12), bg=COLOR_BG2)
        self.lbl_user.pack(side="right", padx=10, pady=5)

        # Canvas для заказов
        self.canvas = tk.Canvas(self, bg=COLOR_BG, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=COLOR_BG)
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def on_raise(self, **kwargs):
        name = self.controller.current_user["name"] if self.controller.current_user else ""
        self.lbl_user.config(text=name)
        if not self.controller.is_admin():
            self.btn_add.pack_forget()
        else:
            self.btn_add.pack(side="left", padx=5, pady=5)
        self.load_orders()

    def load_orders(self):
        for w in self.scrollable_frame.winfo_children():
            w.destroy()
        orders = Database.get_orders()
        if not orders:
            tk.Label(self.scrollable_frame, text="Заказы не найдены",
                     font=(FONT_FAMILY, 14), bg=COLOR_BG).pack(pady=20)
            return
        for o in orders:
            self.create_order_card(o)

    def create_order_card(self, o):
        bg_color = COLOR_BG
        card = tk.Frame(self.scrollable_frame, bg=bg_color, bd=2, relief="groove")
        card.pack(fill="x", padx=10, pady=5, expand=True)
        if self.controller.is_admin():
            card.bind("<Button-1>", lambda e, oid=o["id"]: self.edit_order(oid))

        left = tk.Frame(card, bg=bg_color)
        left.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        tk.Label(left, text=f"Артикул заказа: {o["order_number"]}",
                 font=(FONT_FAMILY, 14, "bold"), bg=bg_color, anchor="w").pack(fill="x")
        tk.Label(left, text=f"Статус заказа: {o.get("status_name", "")}",
                 font=(FONT_FAMILY, 12), bg=bg_color, anchor="w").pack(fill="x")
        tk.Label(left, text=f"Адрес пункта выдачи: {o.get("address", "")}",
                 font=(FONT_FAMILY, 12), bg=bg_color, anchor="w").pack(fill="x")
        tk.Label(left, text=f"Дата заказа: {o["order_date"]}",
                 font=(FONT_FAMILY, 12), bg=bg_color, anchor="w").pack(fill="x")
        tk.Label(left, text=f"Дата выдачи: {o["delivery_date"]}",
                 font=(FONT_FAMILY, 12), bg=bg_color, anchor="w").pack(fill="x")

        right = tk.Frame(card, bg=bg_color, width=120)
        right.pack(side="right", fill="y", padx=10, pady=10)
        right.pack_propagate(False)
        tk.Label(right, text=f"Дата\nдоставки\n{o["delivery_date"]}",
                 font=(FONT_FAMILY, 12), bg=bg_color).pack(expand=True)

    def add_order(self):
        if not self.controller.is_admin():
            return
        self.controller.show_frame(OrderEditFrame, order_id=None)

    def edit_order(self, order_id):
        if not self.controller.is_admin():
            return
        self.controller.show_frame(OrderEditFrame, order_id=order_id)


# ─── ФОРМА ДОБАВЛЕНИЯ/РЕДАКТИРОВАНИЯ ЗАКАЗА ──────────────────────────────────

class OrderEditFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller
        self.order_id = None

        top = tk.Frame(self, bg=COLOR_BG2, height=50)
        top.pack(fill="x", side="top")
        top.pack_propagate(False)
        tk.Label(top, text="Заказ", font=(FONT_FAMILY, 14, "bold"), bg=COLOR_BG2).pack(side="left", padx=10, pady=5)
        btn_back = tk.Button(top, text="← Назад", font=(FONT_FAMILY, 11),
                             bg=COLOR_ACCENT, command=self.go_back)
        btn_back.pack(side="left", padx=5, pady=5)

        form = tk.Frame(self, bg=COLOR_BG)
        form.pack(padx=20, pady=20)

        # ID
        tk.Label(form, text="ID:", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=0, column=0, sticky="e", padx=5, pady=3)
        self.lbl_id = tk.Label(form, text="", font=(FONT_FAMILY, 12), bg=COLOR_BG, anchor="w")
        self.lbl_id.grid(row=0, column=1, sticky="w", padx=5, pady=3)

        # Артикул (номер заказа)
        tk.Label(form, text="Артикул (номер):*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=1, column=0, sticky="e", padx=5, pady=3)
        self.entry_number = tk.Entry(form, font=(FONT_FAMILY, 12), width=30)
        self.entry_number.grid(row=1, column=1, sticky="w", padx=5, pady=3)

        # Статус
        tk.Label(form, text="Статус:*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=2, column=0, sticky="e", padx=5, pady=3)
        self.combo_status = ttk.Combobox(form, font=(FONT_FAMILY, 12), state="readonly", width=28)
        self.combo_status.grid(row=2, column=1, sticky="w", padx=5, pady=3)

        # ПВЗ
        tk.Label(form, text="Пункт выдачи:*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=3, column=0, sticky="e", padx=5, pady=3)
        self.combo_pickup = ttk.Combobox(form, font=(FONT_FAMILY, 12), state="readonly", width=28)
        self.combo_pickup.grid(row=3, column=1, sticky="w", padx=5, pady=3)

        # Пользователь
        tk.Label(form, text="Пользователь:*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=4, column=0, sticky="e", padx=5, pady=3)
        self.combo_user = ttk.Combobox(form, font=(FONT_FAMILY, 12), state="readonly", width=28)
        self.combo_user.grid(row=4, column=1, sticky="w", padx=5, pady=3)

        # Дата заказа
        tk.Label(form, text="Дата заказа (ГГГГ-ММ-ДД):*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=5, column=0, sticky="e", padx=5, pady=3)
        self.entry_order_date = tk.Entry(form, font=(FONT_FAMILY, 12), width=30)
        self.entry_order_date.grid(row=5, column=1, sticky="w", padx=5, pady=3)

        # Дата доставки (выдачи)
        tk.Label(form, text="Дата выдачи (ГГГГ-ММ-ДД):*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=6, column=0, sticky="e", padx=5, pady=3)
        self.entry_delivery_date = tk.Entry(form, font=(FONT_FAMILY, 12), width=30)
        self.entry_delivery_date.grid(row=6, column=1, sticky="w", padx=5, pady=3)

        # Код доставки
        tk.Label(form, text="Код доставки:*", font=(FONT_FAMILY, 12), bg=COLOR_BG).grid(row=7, column=0, sticky="e", padx=5, pady=3)
        self.entry_code = tk.Entry(form, font=(FONT_FAMILY, 12), width=30)
        self.entry_code.grid(row=7, column=1, sticky="w", padx=5, pady=3)

        # Кнопки
        btn_frame = tk.Frame(self, bg=COLOR_BG)
        btn_frame.pack(pady=10)
        self.btn_save = tk.Button(btn_frame, text="Сохранить", font=(FONT_FAMILY, 12),
                                  bg=COLOR_ACCENT, command=self.save)
        self.btn_save.pack(side="left", padx=10)
        self.btn_delete = tk.Button(btn_frame, text="Удалить", font=(FONT_FAMILY, 12),
                                    bg="#FF6B6B", command=self.delete)
        self.btn_delete.pack(side="left", padx=10)

    def on_raise(self, order_id=None, **kwargs):
        self.order_id = order_id
        self.load_combos()
        if order_id:
            self.controller.title("ООО «Обувь» — Редактирование заказа")
            self.lbl_id.config(text=str(order_id))
            self.btn_delete.pack(side="left", padx=10)
            self.fill_form(order_id)
        else:
            self.controller.title("ООО «Обувь» — Добавление заказа")
            next_num = Database.get_next_order_number()
            self.lbl_id.config(text="—")
            self.clear_form()
            self.entry_number.insert(0, str(next_num))
            self.btn_delete.pack_forget()

    def load_combos(self):
        statuses = Database.get_reference("order_statuses")
        self.combo_status["values"] = [s["name"] for s in statuses]
        self.status_map = {s["name"]: s["id"] for s in statuses}

        pickups = Database.get_reference("pickup_points")
        self.combo_pickup["values"] = [f"{p["index"]}, {p["city"]}, {p["street"]}, {p["home"]}" for p in pickups]
        self.pickup_map = {f"{p["index"]}, {p["city"]}, {p["street"]}, {p["home"]}" : p["id"] for p in pickups}

        users = Database.get_reference("users")
        self.combo_user["values"] = [f"{u["name"]} ({u["login"]})" for u in users]
        self.user_map = {f"{u["name"]} ({u["login"]})" : u["id"] for u in users}

    def fill_form(self, order_id):
        o = Database.get_order_by_id(order_id)
        if not o:
            return
        self.entry_number.delete(0, tk.END)
        self.entry_number.insert(0, str(o["order_number"]))
        self.entry_order_date.delete(0, tk.END)
        self.entry_order_date.insert(0, o["order_date"])
        self.entry_delivery_date.delete(0, tk.END)
        self.entry_delivery_date.insert(0, o["delivery_date"])
        self.entry_code.delete(0, tk.END)
        self.entry_code.insert(0, str(o["delivery_code"]))

        for combo, map_dict, value_id in [
            (self.combo_status, self.status_map, o["order_status_id"]),
            (self.combo_pickup, self.pickup_map, o["pickup_point_id"]),
            (self.combo_user, self.user_map, o["user_id"]),
        ]:
            for name, idx in map_dict.items():
                if idx == value_id:
                    combo.set(name)
                    break

    def clear_form(self):
        for w in [self.entry_number, self.entry_order_date, self.entry_delivery_date, self.entry_code]:
            w.delete(0, tk.END)
        for c in [self.combo_status, self.combo_pickup, self.combo_user]:
            c.set("")

    def save(self):
        number_str = self.entry_number.get().strip()
        order_date = self.entry_order_date.get().strip()
        delivery_date = self.entry_delivery_date.get().strip()
        code_str = self.entry_code.get().strip()

        if not all([number_str, order_date, delivery_date, code_str,
                    self.combo_status.get(), self.combo_pickup.get(), self.combo_user.get()]):
            messagebox.showerror("Ошибка", "Заполните все обязательные поля")
            return
        try:
            number = int(number_str)
            code = int(code_str)
        except ValueError:
            messagebox.showerror("Ошибка", "Артикул и код доставки должны быть целыми числами")
            return
        # Простая проверка даты
        if not re.match(r"\d{4}-\d{2}-\d{2}", order_date) or not re.match(r"\d{4}-\d{2}-\d{2}", delivery_date):
            messagebox.showerror("Ошибка", "Дата должна быть в формате ГГГГ-ММ-ДД")
            return

        data = {
            "order_number": number,
            "order_date": order_date,
            "delivery_date": delivery_date,
            "delivery_code": code,
            "order_status_id": self.status_map[self.combo_status.get()],
            "pickup_point_id": self.pickup_map[self.combo_pickup.get()],
            "user_id": self.user_map[self.combo_user.get()]
        }
        try:
            if self.order_id:
                Database.update_order(self.order_id, data)
                messagebox.showinfo("Успех", "Заказ обновлён")
            else:
                Database.add_order(data)
                messagebox.showinfo("Успех", "Заказ добавлен")
            self.go_back()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка сохранения: {e}")

    def delete(self):
        if not self.order_id:
            return
        if not messagebox.askyesno("Подтверждение", "Удалить заказ?"):
            return
        ok, msg = Database.delete_order(self.order_id)
        if ok:
            messagebox.showinfo("Успех", msg)
            self.go_back()
        else:
            messagebox.showerror("Ошибка", msg)

    def go_back(self):
        self.controller.show_frame(OrderListFrame)


# ─── ТОЧКА ВХОДА ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = ShoesApp()
    app.mainloop()
