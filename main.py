"""Главный модуль графического интерфейса приложения WorkoutИИ."""

import json
import os
import threading
from tkinter import *
from tkinter import messagebox
from tkinter.ttk import Combobox
import sys
from database import (
    WorkoutLimitError,
    add_profile,
    clean_week,
    delete_workout,
    get_day,
    get_user,
    get_week,
    save_workout,
)
from dotenv import load_dotenv
from gigachat import GigaChat  # Подключаем библиотеку Сбера
import ctypes

if getattr(sys, "frozen", False):
    env_path = os.path.join(os.path.dirname(sys.executable), ".env")
else:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(env_path)

bg_color = "#1c1f2b"
dark_bg_color = "#101219"
font_color = "white"
font2_color = "#a3b3d7"
red_color = "#640b0f"

DAYS_SHORT = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
DAYS_FULL = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]

# ----------------- НАСТРОЙКА GIGACHAT -----------------
GIGA_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")

giga = GigaChat(
    credentials=GIGA_CREDENTIALS,
    scope="GIGACHAT_API_PERS",  # Обязательно для физлиц (бесплатный тариф)
    verify_ssl_certs=False,  # Чтобы не ругался на сертификаты Минцифры
)
# ------------------------------------------------------

def resource_path(relative_path):
    """Возвращает корректный путь к ресурсам для .py и для собранного .exe."""
    if getattr(sys, "frozen", False):
        # Сначала проверяем рядом с .exe, затем во временной папке PyInstaller
        exe_dir = os.path.dirname(sys.executable)
        local_path = os.path.join(exe_dir, relative_path)
        if os.path.exists(local_path):
            return local_path
        base_path = getattr(sys, "_MEIPASS", exe_dir)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

class ScrollableFrame(Frame):
    """Контейнер Frame с поддержкой вертикальной прокрутки колесиком мыши."""

    def __init__(self, container, height=150, *args, **kwargs):
        """Инициализирует область прокрутки Canvas и полосу Scrollbar."""
        super().__init__(container, *args, **kwargs)
        self.canvas = Canvas(
            self, bg=bg_color, highlightthickness=0, height=height
        )
        scrollbar = Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )

        self.scrollable_frame = Frame(self.canvas, bg=bg_color)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            ),
        )

        self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.bind("<Enter>", self._bind_wheel)
        self.bind("<Leave>", self._unbind_wheel)

    def _bind_wheel(self, event=None):
        """Привязывает события прокрутки колесика мыши при наведении курсора."""
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_wheel(self, event=None):
        """Отвязывает события прокрутки при уходе курсора за пределы области."""
        w = self.winfo_containing(*self.winfo_pointerxy())
        if w is not None and str(w).startswith(str(self)):
            return
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        """Обрабатывает прокрутку содержимого Canvas колесиком мыши."""
        if not self.canvas.winfo_exists():
            return
        if self.scrollable_frame.winfo_height() <= self.canvas.winfo_height():
            return

        if event.num == 4:
            step = -1
        elif event.num == 5:
            step = 1
        elif abs(event.delta) >= 120:
            step = int(-event.delta / 120)
        else:
            step = -event.delta
        self.canvas.yview_scroll(step, "units")


class App(Tk):
    """Главное окно приложения, управляющее переключением экранов."""

    def __init__(self):
        """Инициализирует главное окно и открывает стартовый экран."""
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "kamil.workoutai.app.1"
            )
        except Exception:
            pass

        super().__init__()
        self.title("WorkoutИИ")
        self.geometry("700x400")
        self.resizable(False, False)
        self.configure(bg=bg_color)

        try:
            self.iconbitmap(default=resource_path("icon.ico"))
        except Exception:
            pass

        self.username = None
        self.current_screen = None
        user = get_user()
        if user:
            self.username = user
            self.show_screen(WeekScreen)
        else:
            self.show_screen(LoginScreen)

    def show_screen(self, screen_class, *args, **kwargs):
        """Уничтожает текущий экран и отображает новый."""
        if self.current_screen:
            self.current_screen.destroy()
        self.current_screen = screen_class(self, *args, **kwargs)
        self.current_screen.pack(fill="both", expand=True, padx=20, pady=20)


class LoginScreen(Frame):
    """Экран первичного ввода имени пользователя при первом запуске."""

    def __init__(self, app):
        """Инициализирует экран регистрации."""
        super().__init__(app)
        self.app = app
        self.username_var = StringVar()
        self.configure(bg=bg_color)
        self._build()

    def _build(self):
        """Создает и размещает виджеты экрана входа."""
        Label(
            self,
            text="WorkoutИИ: Журнал тренировок",
            font=("Arial", 14, "bold"),
            bg=bg_color,
            fg=font_color,
        ).pack(pady=20)
        Label(
            self,
            text="Как тебя зовут?",
            bg=bg_color,
            fg=font_color,
            font=("Arial", 10),
        ).pack(pady=8)
        self.name_entry = Entry(self, textvariable=self.username_var)
        self.name_entry.pack(pady=10)
        self.name_entry.focus_set()
        self.name_entry.bind("<Return>", lambda e: self._login())
        Button(
            self,
            text="Продолжить",
            command=self._login,
            bg="white",
            font=("Arial", 10),
        ).pack()

    def _login(self):
        """Проверяет введенное имя, сохраняет профиль и переходит далее."""
        name = self.username_var.get().strip()
        if not name:
            messagebox.showerror("Ошибка", "Поле имени не может быть пустым")
            return
        add_profile(name)
        self.app.username = name
        self.app.show_screen(CreateWeekScreen)


class CreateWeekScreen(Frame):
    """Экран выбора способа создания расписания (вручную или через ИИ)."""

    def __init__(self, app):
        """Инициализирует экран выбора способа планирования."""
        super().__init__(app)
        self.app = app
        self.configure(bg=bg_color)
        self._build()

    def _build(self):
        """Создает кнопки выбора режима создания расписания."""
        Label(
            self,
            text=f"Привет, {self.app.username}",
            font=("Arial", 10),
            bg=bg_color,
            fg=font_color,
        ).pack()
        Label(
            self,
            text="Как создашь свое расписание?",
            font=("Arial", 14),
            bg=bg_color,
            fg=font_color,
        ).pack(pady=20)

        Button(
            self,
            text="✍ Заполнить вручную",
            font=("Arial", 10, "bold"),
            height=2,
            bg=font2_color,
            width=40,
            command=lambda: self.app.show_screen(WeekScreen),
        ).pack(pady=0)
        Label(
            self,
            text="Сам добавишь тренировки на каждый день",
            font=("Arial", 10),
            bg=bg_color,
            fg=font_color,
        ).pack()

        Button(
            self,
            text="🤖 Составить с помощью ИИ",
            font=("Arial", 10, "bold"),
            height=2,
            bg=font2_color,
            width=40,
            command=lambda: self.app.show_screen(CreateAiScreen),
        ).pack(pady=(20, 0))
        Label(
            self,
            text="Заполняешь анкеты - ИИ расставит план",
            font=("Arial", 10),
            bg=bg_color,
            fg=font_color,
        ).pack()

        Label(
            self,
            text="План всегда можно будет пересоздать",
            font=("Arial", 8),
            bg=bg_color,
            fg=font2_color,
        ).pack(pady=26)


class CreateAiScreen(Frame):
    """Экран заполнения анкеты пользователя для генерации плана через GigaChat."""

    def __init__(self, app):
        """Инициализирует переменные формы анкеты и строит интерфейс."""
        super().__init__(app)
        self.app = app

        self.height_var = IntVar()
        self.weight_var = IntVar()
        self.age_var = IntVar()
        self.aim_var = StringVar(value="Поддержание формы")
        self.experience_var = StringVar(value="Новичок")
        self.equipment_var = StringVar(value="Зал (всё есть)")
        self.per_week_var = IntVar(value=3)
        self.duration_var = IntVar(value=60)

        self.configure(bg=bg_color)
        self._build()

    def _label(self, parent, text, row, column, padx=0):
        """Вспомогательный метод для создания текстовой метки в сетке Grid."""
        Label(
            parent, text=text, bg=bg_color, font=("Arial", 10), fg=font_color
        ).grid(row=row, column=column, sticky="w", pady=2, padx=padx)

    def _build(self):
        """Создает поля ввода анкеты и кнопки управления."""
        header = Frame(self, bg=bg_color)
        header.pack()
        Label(
            header,
            text="Генерация плана с помощью ИИ",
            font=("Arial", 14),
            bg=bg_color,
            fg=font_color,
        ).pack(anchor="w")

        main = Frame(self, bg=bg_color)
        main.pack(anchor="w", fill="both", expand=True, pady=(20, 0))

        # --- ЛЕВАЯ КОЛОНКА ---
        self._label(main, "Рост, см: ", 1, 0)
        Entry(main, textvariable=self.height_var, width=8).grid(
            row=1, column=1, sticky="w", padx=5, pady=2
        )

        self._label(main, "Вес, кг: ", 2, 0)
        Entry(main, textvariable=self.weight_var, width=8).grid(
            row=2, column=1, sticky="w", padx=5, pady=2
        )

        self._label(main, "Возраст: ", 3, 0)
        Entry(main, textvariable=self.age_var, width=8).grid(
            row=3, column=1, sticky="w", padx=5, pady=2
        )

        self._label(main, "Цель: ", 4, 0)
        Combobox(
            main,
            textvariable=self.aim_var,
            values=[
                "Похудение",
                "Набор массы",
                "Поддержание формы",
                "Сила",
                "Выносливость",
            ],
            state="readonly",
            width=18,
        ).grid(row=4, column=1, sticky="w", padx=5, pady=2)

        # --- ПРАВАЯ КОЛОНКА ---
        self._label(main, "Опыт: ", 1, 2, padx=(20, 0))
        Combobox(
            main,
            state="readonly",
            textvariable=self.experience_var,
            width=18,
            values=["Новичок", "Средний", "Продвинутый"],
        ).grid(row=1, column=3, sticky="w", padx=5, pady=2)

        self._label(main, "Оборудование: ", 2, 2, padx=(20, 0))
        Combobox(
            main,
            state="readonly",
            textvariable=self.equipment_var,
            values=["Зал (всё есть)", "Дом (без инвентаря)", "Улица"],
            width=18,
        ).grid(row=2, column=3, sticky="w", padx=5, pady=2)

        self._label(main, "Тренировок в нед.: ", 3, 2, padx=(20, 0))
        Entry(main, textvariable=self.per_week_var, width=8).grid(
            row=3, column=3, sticky="w", padx=5, pady=2
        )

        self._label(main, "Длительность, мин: ", 4, 2, padx=(20, 0))
        Entry(main, textvariable=self.duration_var, width=8).grid(
            row=4, column=3, sticky="w", padx=5, pady=2
        )

        Label(
            main,
            text="Пожелания, ограничения и тд:",
            bg=bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).grid(row=7, column=0, columnspan=4, sticky="w", pady=(15, 2))

        self.wishes_text = Text(main, height=4, width=40)
        self.wishes_text.grid(row=8, column=0, columnspan=3, sticky="ew", pady=5)

        btn_frame = Frame(main, bg=bg_color)
        btn_frame.grid(row=8, column=3, columnspan=2, sticky="w", padx=10)

        self.generate_btn = Button(
            btn_frame,
            text="Сгенерировать",
            bg=font2_color,
            font=("Arial", 10),
            command=self._generate,
        )
        self.generate_btn.pack(side="left", padx=(36, 5))
        self.cancel_button = Button(
            btn_frame,
            text="Отмена",
            bg=font2_color,
            font=("Arial", 10),
            command=lambda: self.app.show_screen(WeekScreen),
        )
        self.cancel_button.pack(side="left")

    def _generate(self):
        """Проверяет данные анкеты, формирует промпт и запускает поток обращения к ИИ."""
        try:
            height = self.height_var.get()
            weight = self.weight_var.get()
            age = self.age_var.get()
            per_week = self.per_week_var.get()
            duration = self.duration_var.get()
        except Exception:
            messagebox.showerror(
                "Ошибка", "Во все числовые поля нужно вводить целые числа"
            )
            return

        if height <= 0 or weight <= 0 or age <= 0 or duration <= 0:
            messagebox.showerror(
                "Ошибка",
                "Рост, вес, возраст и длительность должны быть больше нуля",
            )
            return

        if not 1 <= per_week <= 14:
            messagebox.showerror(
                "Ошибка", "Тренировок в неделю может быть от 1 до 14"
            )
            return

        aim = self.aim_var.get()
        experience = self.experience_var.get()
        equipment = self.equipment_var.get()

        if not aim or not experience or not equipment:
            messagebox.showerror(
                "Ошибка", "Выберите цель, опыт и оборудование из списков"
            )
            return

        wishes = self.wishes_text.get("1.0", END).strip()

        # 1. Собираем текст для ИИ ЗДЕСЬ, пока переменные height, weight и т.д. доступны
        data_to_ai = f"""
        Параметры пользователя:
        - Рост: {height} см, Вес: {weight} кг, Возраст: {age} лет
        - Цель: {aim}, Опыт: {experience}, Инвентарь: {equipment}
        - Тренировок: {per_week} в неделю, Длительность: {duration} мин.
        - Пожелания: {wishes if wishes else 'нет'}
        """

        system_prompt = f"""Ты опытный персональный фитнес-тренер. 
                Составь грамотный и разнообразный тренировочный план строго из {per_week} тренировок на неделю.
                Ответь ТОЛЬКО чистым JSON без лишних слов, без пояснений и без markdown-разметки (не пиши ```json).

                Схема ответа:
                {{
                    "workouts": [
                        {{
                            "day_index": 0, 
                            "kind": "Силовая",
                            "exercises": [
                                {{"name": "Подтягивания", "sets": 3, "reps": 8, "weight": 0}}
                            ]
                        }}
                    ]
                }}

                ПРАВИЛА:
                1. ИНВЕНТАРЬ И ПОЖЕЛАНИЯ (НАИВЫСШИЙ ПРИОРИТЕТ):
                   - Внимательно изучи пожелания! Если указан турник, гриф, гантели, груша и тд — ОБЯЗАТЕЛЬНО включи упражнения с ними.
                2. РАЗНООБРАЗИЕ ТРЕНИРОВОК:
                   - ЗАПРЕЩЕНО делать все тренировки одинаковыми. Разделяй нагрузку (например: спина/тяги, ноги, грудь/руки, кардио).
                3. НАЗВАНИЯ И ЗНАЧЕНИЯ:
                   - Только короткие названия (1-3 слова). Например: «Подтягивания», «Отжимания», «Жим грифа».
                   - Строго ОДНО упражнение (никаких вариантов через «или» и скобок).
                   - Не пиши «(с собственным весом)». Если вес не нужен — ставь "weight": 0.
                   - Поле "kind" может принимать СТРОГО одно из 4 значений: "Силовая", "Кардио", "Функциональная", "Растяжка".
                   - Поля "sets" и "reps" — СТРОГО целые числа больше 0 (никаких диапазонов вроде "8-12" или слов, пиши одно конкретное число). Поле "weight" — число >= 0.
                   - Для упражнений на время (бег, кардио, планка, растяжка, груша) пиши время прямо в названии без скобок, а в "reps" ставь 1. Примеры: {{"name": "Бег 25 мин", "sets": 1, "reps": 1, "weight": 0}} или {{"name": "Планка 1 мин", "sets": 3, "reps": 1, "weight": 0}}.
                4. СТРУКТУРА И ДНИ:
                   - "day_index" — число от 0 до 6 (0-ПН, 1-ВТ, 2-СР, 3-ЧТ, 4-ПТ, 5-СБ, 6-ВС).
                   - В один день (одинаковый "day_index") можно ставить МАКСИМУМ 2 тренировки (например, силовая и кардио). Больше 2 тренировок в один день ставить ЗАПРЕЩЕНО.
                   - Ровно {per_week} тренировки(ок) в массиве "workouts". От 1 до 10 упражнений на тренировку.
                """

        # 2. Блокируем кнопку и запускаем поток
        self.generate_btn.config(state=DISABLED, text="Генерация...")
        self.cancel_button.config(state=DISABLED)

        thread = threading.Thread(
            target=self._fetch_ai_plan,
            args=(data_to_ai, system_prompt),
            daemon=True,
        )
        thread.start()

    def _fetch_ai_plan(self, data_to_ai, system_prompt):
        """Отправляет запрос к API GigaChat в фоновом потоке и парсит JSON-ответ."""
        try:
            # Стучимся к GigaChat
            response = giga.chat(
                {
                    "model": "GigaChat-3-Pro",
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": data_to_ai},
                    ],
                }
            )

            raw_text = response.choices[0].message.content
            start_idx = raw_text.find("{")
            end_idx = raw_text.rfind("}")
            if start_idx == -1 or end_idx == -1:
                raise ValueError(
                    "ИИ вернул ответ в неверном формате (не найден JSON)"
                )
            clean_json = raw_text[start_idx : end_idx + 1]
            result = json.loads(clean_json)

            # 4. ВАЖНО: Возвращаемся в главный поток (self.after) для сохранения в БД
            self.after(0, self._on_ai_success, result)

        except Exception as e:
            # Если ошибка — тоже возвращаемся в главный поток, чтобы показать сообщение
            self.after(0, self._on_ai_error, str(e))

    def _on_ai_success(self, result):
        """Сохраняет сгенерированный ИИ план в БД и открывает экран недели."""
        self.generate_btn.config(state=NORMAL, text="Сгенерировать")
        self.cancel_button.config(state=NORMAL, text="Отмена")
        try:
            clean_week()
            for w in result["workouts"]:
                save_workout(
                    None, w["day_index"], w["kind"], "planned", w["exercises"]
                )

            messagebox.showinfo("Успех", "План успешно составлен!")
            self.app.show_screen(WeekScreen)
        except Exception as e:
            messagebox.showerror(
                "Ошибка БД", f"Не удалось сохранить план: {e}"
            )

    def _on_ai_error(self, error_msg):
        """Разблокирует кнопки и выводит сообщение об ошибке генерации ИИ."""
        self.generate_btn.config(state=NORMAL, text="Сгенерировать")
        self.cancel_button.config(state=NORMAL, text="Отмена")
        messagebox.showerror(
            "Ошибка ИИ", f"Не удалось сгенерировать план: {error_msg}"
        )


class WeekScreen(Frame):
    """Главный экран обзора расписания тренировок на всю неделю."""

    def __init__(self, app):
        """Загружает количество тренировок по дням недели и строит интерфейс."""
        super().__init__(app)
        self.app = app
        self.configure(bg=bg_color)
        self.counts = get_week()
        self._build()

    def _build(self):
        """Создает шапку профиля и карточки 7 дней недели."""
        header = Frame(self, bg=bg_color)
        header.pack(fill="x", pady=(0, 40))
        Label(
            header,
            text=f"Привет {self.app.username}!",
            bg=bg_color,
            font=("Arial", 12, "bold"),
            fg=font_color,
        ).pack(side="left")

        btn_frame = Frame(header, bg=bg_color)
        btn_frame.pack(side="right")
        Button(
            btn_frame,
            text="Сгенерировать с ИИ",
            bg=bg_color,
            fg=font_color,
            relief="groove",
            borderwidth=2,
            highlightthickness=0,
            activebackground=bg_color,
            activeforeground="white",
            font=("Arial", 10),
            command=lambda: self.app.show_screen(CreateAiScreen),
        ).pack(anchor="e")
        Button(
            btn_frame,
            text="О программе",
            bg=bg_color,
            fg=font_color,
            relief="groove",
            borderwidth=2,
            activebackground=bg_color,
            activeforeground="white",
            font=("Arial", 10),
            command=self._about_program,
        ).pack(anchor="e")

        main = Frame(self, bg=bg_color)
        center_container = Frame(main, bg=bg_color)
        center_container.pack(expand=True)

        for i in range(len(DAYS_SHORT)):
            day_box = Frame(center_container, bg=bg_color)
            day_box.pack(side="left")
            Label(
                day_box,
                text=DAYS_SHORT[i],
                bg=bg_color,
                font=("Arial", 10),
                fg=font_color,
            ).pack()
            Label(
                day_box,
                text=f"{self.counts[i]} тр",
                bg=bg_color,
                font=("Arial", 10),
                fg=font_color,
            ).pack(pady=10)
            Button(
                day_box,
                text="Подробнее",
                font=("Arial", 10),
                bg=font2_color,
                fg=bg_color,
                command=lambda i=i: self.app.show_screen(DayScreen, i),
            ).pack(padx=4)
        main.pack(fill="x")

    def _about_program(self):
        """Открывает модальное окно с информацией о программе."""
        dialog = AboutDialog(self)
        self.wait_window(dialog)


# ---------------------------------------------------------------- День
class DayScreen(Frame):
    """Экран подробного просмотра тренировок выбранного дня недели."""

    def __init__(self, app, week_day_id):
        """Загружает данные тренировок за выбранный день и строит интерфейс."""
        super().__init__(app)
        self.app = app
        self.configure(bg=bg_color)

        self.data = get_day(week_day_id)
        self.week_day_id = week_day_id
        self.week_day = DAYS_FULL[week_day_id]
        self._build()

    def _build(self):
        """Отображает карточки тренировок дня и кнопки управления."""
        header = Frame(self, bg=bg_color)
        header.pack(fill="x")

        Button(
            header,
            text="< Назад к неделе",
            relief="groove",
            borderwidth=0,
            highlightthickness=0,
            bg=bg_color,
            activebackground=bg_color,
            activeforeground="white",
            font=("Arial", 10),
            fg=font_color,
            anchor="w",
            command=lambda: self.app.show_screen(WeekScreen),
        ).pack(side="left")
        Label(
            header,
            text=self.week_day,
            bg=bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).pack(anchor="e")

        main = Frame(self, bg=bg_color)
        main.pack(fill="x")

        trains = Frame(main, bg=bg_color)
        trains.pack(pady=(30, 0), fill="x")

        for index, info in enumerate(self.data, start=1):
            tr_card = Frame(trains, bg=bg_color)
            tr_card.pack(side="left", padx=30, anchor="n")
            status_text = (
                "выполнена ☑" if info["status"] == "done" else "не выполнена ☐"
            )

            Label(
                tr_card,
                text=f"#{index}  {info['kind']}  {status_text}",
                bg=bg_color,
                font=("Arial", 10, "bold"),
                fg=font_color,
            ).pack(anchor="w")

            exercises = info["exercises"]
            for ex in exercises[:5]:
                weight_str = f", {ex['weight']:g}кг" if ex["weight"] > 0 else ""
                Label(
                    tr_card,
                    text=f"• {ex['name']} — {ex['sets']}×{ex['reps']}{weight_str}",
                    bg=bg_color,
                    font=("Arial", 10),
                    fg=font_color,
                    wraplength=260,
                    justify="left",
                ).pack(padx=10, anchor="w")

            if len(exercises) > 5:
                Label(
                    tr_card,
                    text="...",
                    bg=bg_color,
                    font=("Arial", 10),
                    fg=font_color,
                ).pack(padx=10, anchor="w")

            btns = Frame(tr_card, bg=bg_color)
            btns.pack(anchor="w", pady=(10, 0))

            Button(
                btns,
                text="Подробнее",
                font=("Arial", 10),
                bg=font2_color,
                fg=bg_color,
                command=lambda info=info: self.app.show_screen(
                    WorkoutEditScreen, self.week_day_id, info
                ),
            ).pack(side="left")

            Button(
                btns,
                text="Удалить",
                font=("Arial", 10),
                bg=red_color,
                activebackground=red_color,
                fg=font_color,
                activeforeground=font_color,
                command=lambda wid=info["id"]: self._delete_train(wid),
            ).pack(side="left")

        if len(self.data) < 2:
            Button(
                main,
                text="+ Добавить тренировку",
                font=("Arial", 10),
                bg=font2_color,
                fg=bg_color,
                command=lambda: self.app.show_screen(
                    WorkoutEditScreen, self.week_day_id
                ),
            ).pack(anchor="w", pady=(40, 0))
        else:
            Label(
                main,
                text="Максимум 2 тренировки в день",
                font=("Arial", 10),
                bg=bg_color,
                fg=font2_color,
            ).pack(anchor="w", pady=(40, 0))

        btns2 = Frame(main, bg=bg_color)
        btns2.pack(anchor="w", pady=4)
        Button(
            btns2,
            text="Назад",
            bg=font2_color,
            font=("Arial", 10),
            command=lambda: self.app.show_screen(WeekScreen),
        ).pack()

    def _delete_train(self, workout_id):
        """Запрашивает подтверждение и удаляет выбранную тренировку."""
        if messagebox.askyesno("Удаление", "Удалить тренировку?"):
            delete_workout(workout_id)
            self.app.show_screen(DayScreen, self.week_day_id)


# ---------------------------------------------------------------- О программе
class AboutDialog(Toplevel):
    """Модальное диалоговое окно со сведениями о программе и авторе."""

    def __init__(self, parent):
        """Инициализирует модальное окно «О программе»."""
        super().__init__(parent)
        self.title("WorkoutИИ")
        self.geometry("400x280")
        self.resizable(False, False)
        self.configure(padx=20, pady=20, bg=bg_color)

        self.transient(parent)
        self.grab_set()
        self._build()

    def _build(self):
        """Размещает текст с описанием версии, автора и ссылкой на GitHub."""
        Label(
            self,
            text="О программе",
            bg=bg_color,
            font=("Arial", 11, "bold"),
            fg=font_color,
        ).pack(anchor="w")
        Label(
            self,
            text="🏋️ WorkoutИИ v0.1",
            bg=bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).pack(pady=(20, 0), anchor="w")
        Label(
            self,
            text="Твой персональный фитнес-помощник",
            bg=bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).pack(pady=(0, 20), anchor="w")
        Label(
            self,
            text="Разработал: Гумеров Камиль",
            bg=bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).pack(anchor="w")
        Label(
            self,
            text="Исходный код на GitHub:",
            bg=bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).pack(pady=(20, 0), anchor="w")
        Label(
            self,
            text="https://github.com/kamil2757/WorkoutAI",
            bg=bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).pack(pady=(0, 20), anchor="w")

        Button(
            self,
            text="Закрыть",
            font=("Arial", 10),
            bg=font2_color,
            fg=bg_color,
            command=self.destroy,
        ).pack()


# ---------------------------------------------------------------- Редактирование тренировки
class WorkoutEditScreen(Frame):
    """Экран создания новой или редактирования существующей тренировки."""

    def __init__(self, app, week_day_id, data=None):
        """Инициализирует параметры тренировки и список её упражнений."""
        super().__init__(app)
        self.app = app
        self.configure(bg=bg_color)

        self.week_day = DAYS_FULL[week_day_id]
        self.week_day_id = week_day_id
        self.workout_id = data["id"] if data else None
        self.exercise_data = []

        if data:
            self.type_var = StringVar(value=data["kind"])
            self.status_var = BooleanVar(value=data["status"] == "done")
            for ex in data["exercises"]:
                self.exercise_data.append(
                    {
                        "name": ex["name"],
                        "sets": ex["sets"],
                        "reps": ex["reps"],
                        "weight": ex["weight"],
                    }
                )
        else:
            self.type_var = StringVar(value="Силовая")
            self.status_var = BooleanVar()

        self._build()

    def _build(self):
        """Строит интерфейс выбора типа, статуса и прокручиваемого списка упражнений."""
        header = Frame(self, bg=bg_color)
        header.pack(fill="x")

        Button(
            header,
            text="< Назад ко дню",
            relief="groove",
            borderwidth=0,
            highlightthickness=0,
            bg=bg_color,
            activebackground=bg_color,
            activeforeground="white",
            font=("Arial", 10),
            fg=font_color,
            anchor="w",
            command=lambda: self.app.show_screen(DayScreen, self.week_day_id),
        ).pack(side="left")
        Label(
            header,
            text=self.week_day,
            bg=bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).pack(anchor="e")

        mini_form = Frame(self, bg=bg_color)
        mini_form.pack()
        Label(
            mini_form,
            text="Тип: ",
            bg=bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).grid(row=0, column=0)
        Combobox(
            mini_form,
            state="readonly",
            textvariable=self.type_var,
            values=["Силовая", "Кардио", "Функциональная", "Растяжка"],
            width=16,
        ).grid(row=0, column=1)
        Label(
            mini_form,
            text="Статус: ",
            bg=bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).grid(row=1, column=0)
        Checkbutton(
            mini_form,
            variable=self.status_var,
            text="Выполнена",
            bg=bg_color,
            fg=font_color,
            selectcolor=dark_bg_color,
            activebackground=bg_color,
            activeforeground=font_color,
            highlightthickness=0,
            font=("Arial", 10),
        ).grid(row=1, column=1, sticky="w", padx=5, pady=2)

        exercises = Frame(self, bg=bg_color)
        exercises.pack(fill="both", expand=True, pady=10)
        Label(
            exercises,
            text="Упражнения:",
            bg=bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).pack(anchor="w")

        btns = Frame(exercises, bg=bg_color)
        btns.pack(side="bottom", anchor="w", pady=(10, 0))

        Button(
            btns,
            text="+ Добавить упражнение",
            bg=font2_color,
            font=("Arial", 10),
            command=self._add_exercise,
        ).pack(side="left", padx=2)
        Button(
            btns,
            text="Сохранить",
            bg="white",
            font=("Arial", 10),
            command=self._save,
        ).pack(side="left")

        self.cards_frame = ScrollableFrame(exercises, height=150, bg=bg_color)
        self.cards_frame.pack(fill="both", expand=True, pady=5)
        for ex in self.exercise_data:
            self._add_exercise_card(ex)

    def _add_exercise_card(self, ex):
        """Создает визуальную карточку упражнения с кнопками редактирования и удаления."""
        card = Frame(
            self.cards_frame.scrollable_frame, bg=dark_bg_color, padx=6, pady=2
        )
        card.pack(pady=1, anchor="w")

        weight_str = f' × {ex["weight"]:g}кг' if ex["weight"] > 0 else ""
        text = f'{ex["name"]}: {ex["sets"]} подх. × {ex["reps"]} повт.{weight_str}'

        e_header = Frame(card, bg=dark_bg_color)
        e_header.pack(fill="x")
        Label(
            e_header,
            text=text,
            bg=dark_bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).pack(side="left", anchor="w")

        e_btns = Frame(e_header, bg=dark_bg_color)
        e_btns.pack(side="right", anchor="e", padx=(10, 0))
        Button(
            e_btns,
            text="✎",
            font=("Arial", 7),
            height=0,
            width=0,
            bg=font2_color,
            fg=dark_bg_color,
            command=lambda e=ex: self._edit_exercise(e),
        ).pack(side="left")
        Button(
            e_btns,
            text="✕",
            font=("Arial", 7),
            height=0,
            width=0,
            bg=font2_color,
            fg=dark_bg_color,
            command=lambda c=card, e=ex: self._delete_exercise(c, e),
        ).pack(side="left", padx=(4, 0))

    def _save(self):
        """Проверяет наличие упражнений и сохраняет тренировку в базу данных."""
        if not self.exercise_data:
            messagebox.showerror(
                "Ошибка", "Тренировка не может быть без упражнений"
            )
            return

        kind = self.type_var.get()
        status = "done" if self.status_var.get() else "planned"

        try:
            save_workout(
                self.workout_id,
                self.week_day_id,
                kind,
                status,
                self.exercise_data,
            )
        except WorkoutLimitError as e:
            messagebox.showerror("Ошибка", str(e))
            return
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось сохранить: {e}")
            return

        self.app.show_screen(DayScreen, self.week_day_id)

    def _add_exercise(self):
        """Открывает диалог добавления нового упражнения."""
        dialog = ExerciseDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            self.exercise_data.append(dialog.result)
            self._add_exercise_card(dialog.result)

    def _edit_exercise(self, ex):
        """Открывает диалог редактирования выбранного упражнения и обновляет список."""
        dialog = ExerciseDialog(self, ex)
        self.wait_window(dialog)
        if dialog.result:
            idx = [i for i, e in enumerate(self.exercise_data) if e is ex][0]
            self.exercise_data[idx] = dialog.result
            for w in self.cards_frame.scrollable_frame.winfo_children():
                w.destroy()
            for e in self.exercise_data:
                self._add_exercise_card(e)

    def _delete_exercise(self, card, ex):
        """Удаляет упражнение из текущего списка после подтверждения."""
        if messagebox.askyesno("Удаление", "Удалить упражнение?"):
            self.exercise_data = [
                e for e in self.exercise_data if e is not ex
            ]
            card.destroy()


class ExerciseDialog(Toplevel):
    """Модальное диалоговое окно для добавления или редактирования упражнения."""

    def __init__(self, parent, exercise=None):
        """Инициализирует поля ввода параметров упражнения."""
        super().__init__(parent)
        self.title("Упражнение")
        self.geometry("400x300")
        self.configure(bg=bg_color, padx=20, pady=20)
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()
        self.result = None
        self.is_edit = exercise is not None

        self.title_var = StringVar()
        self.sets_var = IntVar(value=3)
        self.repetitions_var = IntVar(value=10)
        self.weight_var = DoubleVar(value=0)

        if exercise:
            self.title_var.set(exercise["name"])
            self.sets_var.set(exercise["sets"])
            self.repetitions_var.set(exercise["reps"])
            self.weight_var.set(exercise["weight"])

        self._build()

    def _build(self):
        """Создает элементы формы ввода названия, подходов, повторений и веса."""
        Label(
            self,
            text="Упражнение",
            bg=bg_color,
            font=("Arial", 11, "bold"),
            fg=font_color,
        ).grid(row=0, column=0, sticky="w", pady=(0, 20))

        Label(
            self,
            text="Название:",
            bg=bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).grid(row=1, column=0, sticky="w")
        name_entry = Entry(self, textvariable=self.title_var)
        name_entry.grid(row=1, column=1, sticky="w")
        name_entry.focus_set()
        Label(
            self,
            text="Например: Подтягивания",
            bg=bg_color,
            font=("Arial", 8),
            fg=font2_color,
        ).grid(row=2, column=1, sticky="w")

        Label(
            self,
            text="Подходы: ",
            bg=bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).grid(row=3, column=0, sticky="w", pady=10)
        Entry(self, textvariable=self.sets_var, width=8).grid(
            row=3, column=1, sticky="w"
        )

        Label(
            self,
            text="Повторения: ",
            bg=bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).grid(row=4, column=0, sticky="w")
        Entry(self, textvariable=self.repetitions_var, width=8).grid(
            row=4, column=1, sticky="w"
        )

        Label(
            self,
            text="Вес, кг: ",
            bg=bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).grid(row=5, column=0, sticky="w", pady=10)
        Entry(self, textvariable=self.weight_var, width=8).grid(
            row=5, column=1, sticky="w"
        )
        Label(
            self,
            text="(0 = без веса)",
            bg=bg_color,
            font=("Arial", 10),
            fg=font_color,
        ).grid(row=5, column=2, sticky="w")

        Button(
            self,
            text="Сохранить" if self.is_edit else "Добавить",
            bg=font2_color,
            font=("Arial", 10),
            command=self._add,
            width=10,
        ).grid(row=6, column=0, sticky="w")
        Button(
            self,
            text="Отмена",
            bg=font2_color,
            font=("Arial", 10),
            command=self.destroy,
        ).grid(row=6, column=1, sticky="w")

    def _add(self):
        """Валидирует введенные данные упражнения и закрывает диалоговое окно."""
        try:
            name = self.title_var.get().strip()
            sets = self.sets_var.get()
            reps = self.repetitions_var.get()
            weight = self.weight_var.get()
        except (ValueError, TclError):
            messagebox.showerror(
                "Ошибка",
                "В числовые поля нужно вводить числа (без букв и символов)!",
                parent=self,
            )
            return

        if not name:
            messagebox.showerror(
                "Ошибка", "Название не должно быть пустым", parent=self
            )
            return

        if sets <= 0 or reps <= 0:
            messagebox.showerror(
                "Ошибка",
                "Подходы и повторения должны быть больше нуля",
                parent=self,
            )
            return

        if weight < 0:
            messagebox.showerror(
                "Ошибка", "Вес не может быть отрицательным", parent=self
            )
            return

        self.result = {
            "name": name,
            "sets": sets,
            "reps": reps,
            "weight": weight,
        }
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()