import curses
import calendar
import json
from datetime import datetime

import pika

# Глобальные переменные
events = {}
current_year = datetime.now().year
current_month = datetime.now().month
highlight_color = curses.COLOR_CYAN
view_mode = "month"  # "month" или "year"
day_positions = []
calc_input = ""
event_page = 0

buttons = [
    ("Добавить", "add"),
    ("Удалить", "delete"),
    ("Цвет", "color"),
    ("Сбросить события", "clear"),
    ("Выход", "quit")
]

prev_month_button = (0, 0, 0, 0)
next_month_button = (0, 0, 0, 0)

calc_keys = [
    ["7", "8", "9", "+"],
    ["4", "5", "6", "-"],
    ["1", "2", "3", "*"],
    ["0", "(", ")", "/"],
    ["<-", "C", "=", ""]
]

# --- Показ сообщения ---
def show_message(msg_win, message):
    msg_win.erase()
    msg_win.box()
    msg_win.addstr(1, 2, message[:msg_win.getmaxyx()[1] - 4], curses.A_BOLD)
    msg_win.refresh()
    curses.napms(2000)
    msg_win.erase()
    msg_win.box()
    msg_win.refresh()

# --- Управление калькулятором ---
def handle_calculator_input(key_label):
    global calc_input
    if key_label == "=":
        try:
            calc_input = str(eval(calc_input))
        except Exception:
            calc_input = "Ошибка"
    elif key_label == "C":
        calc_input = ""
    elif key_label == "<-":
        calc_input = calc_input[:-1]
    else:
        calc_input += key_label


# --- Рисование кнопок и калькулятора ---
def draw_buttons(button_win):
    button_win.erase()
    button_win.box()
    button_win_width = button_win.getmaxyx()[1]

    for idx, (label, _) in enumerate(buttons):
        y = 2 + idx * 3
        text = f"[ {label.center(18)} ]"
        x = (button_win_width - len(text)) // 2
        button_win.addstr(y, x, text)

    calc_start_y = 2 + len(buttons) * 3 + 2
    button_win.addstr(calc_start_y, 2, "Калькулятор", curses.A_BOLD)

    button_win.addstr(calc_start_y + 1, 1, "+" + "-" * (button_win_width - 4) + "+")
    button_win.addstr(calc_start_y + 2, 1, "|" + calc_input.center(button_win_width - 4) + "|")
    button_win.addstr(calc_start_y + 3, 1, "+" + "-" * (button_win_width - 4) + "+")

    for row_idx, row in enumerate(calc_keys):
        for col_idx, key in enumerate(row):
            if key:
                y = calc_start_y + 4 + row_idx * 2
                x = 2 + col_idx * 8
                try:
                    if 0 <= y < button_win.getmaxyx()[0] and 0 <= x < button_win.getmaxyx()[1] - 6:
                        button_win.addstr(y, x, f"[ {key.center(2)} ]")
                except curses.error:
                    pass

    button_win.refresh()

# --- Рисование календаря ---
def draw_calendar(cal_win, year, month):
    cal_win.erase()
    cal_win.box()

    global prev_month_button, next_month_button

    curses.init_pair(3, highlight_color, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(6, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_WHITE)

    hcolor = curses.color_pair(3)
    weekdaycolor = curses.color_pair(5) | curses.A_BOLD
    normaldaycolor = curses.color_pair(6)
    todayboxcolor = curses.color_pair(7)

    max_y, max_x = cal_win.getmaxyx()
    day_positions.clear()
    today = datetime.now()

    switch_label = "[ Год ]" if view_mode == "month" else "[ Месяц ]"
    cal_win.addstr(0, 2, switch_label, curses.A_BOLD)

    if view_mode == "month":
        cell_width = 6
        cal = calendar.monthcalendar(year, month)
        total_table_width = 7 * cell_width
        start_x = (max_x - total_table_width) // 2
        start_y = 2

        month_name = f"{calendar.month_name[month]} {year}"
        title = f"[<-] {month_name} [->]"
        start_x_title = max(0, (max_x - len(title)) // 2)
        cal_win.addstr(0, start_x_title, title, curses.A_BOLD)

        prev_month_button = (start_x_title, 0, start_x_title + 4, 0)
        next_month_button = (start_x_title + len(title) - 5, 0, start_x_title + len(title) - 1, 0)

        days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        for idx, day in enumerate(days):
            x = start_x + idx * cell_width
            cal_win.addstr(start_y, x + 1, day.center(cell_width - 2), weekdaycolor)

        for week_idx, week in enumerate(cal):
            for day_idx, day in enumerate(week):
                y = start_y + 2 + week_idx
                x = start_x + day_idx * cell_width
                if day != 0:
                    date_str = f"{year}-{month:02d}-{day:02d}"
                    if today.year == year and today.month == month and today.day == day:
                        style = todayboxcolor
                    elif date_str in events:
                        style = hcolor
                    else:
                        style = normaldaycolor
                    cal_win.addstr(y, x + 1, str(day).center(cell_width - 2), style)
                    day_positions.append((x, y, day))
    else:
        months_per_row = 4
        month_width = 22
        month_height = 8
        total_width = months_per_row * (month_width + 2)
        start_x_global = (max_x - total_width) // 2
        start_y = 2

        year_title = f"[<-] {year} [->]"
        start_x_title = max(0, (max_x - len(year_title)) // 2)
        cal_win.addstr(0, start_x_title, year_title, curses.A_BOLD)

        prev_month_button = (start_x_title, 0, start_x_title + 4, 0)
        next_month_button = (start_x_title + len(year_title) - 5, 0, start_x_title + len(year_title) - 1, 0)

        for m in range(1, 13):
            cal = calendar.monthcalendar(year, m)
            row = (m - 1) // months_per_row
            col = (m - 1) % months_per_row
            box_y = start_y + row * (month_height + 1)
            box_x = start_x_global + col * (month_width + 2)

            cal_win.addstr(box_y, box_x, "+" + "-" * month_width + "+")
            for i in range(1, month_height):
                cal_win.addstr(box_y + i, box_x, "|")
                cal_win.addstr(box_y + i, box_x + month_width + 1, "|")
            cal_win.addstr(box_y + month_height, box_x, "+" + "-" * month_width + "+")

            title = calendar.month_abbr[m]
            cal_win.addstr(box_y, box_x + (month_width // 2) - len(title) // 2, title, curses.A_BOLD)

            days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            for idx, day in enumerate(days):
                x = box_x + 2 + idx * 3
                cal_win.addstr(box_y + 1, x, day[:2], weekdaycolor)

            for week_idx, week in enumerate(cal):
                for day_idx, day in enumerate(week):
                    if day != 0:
                        y = box_y + 2 + week_idx
                        x = box_x + 2 + day_idx * 3
                        date_str = f"{year}-{m:02d}-{day:02d}"
                        if today.year == year and today.month == m and today.day == day:
                            style = todayboxcolor
                        elif date_str in events:
                            style = hcolor
                        else:
                            style = normaldaycolor
                        cal_win.addstr(y, x, f"{day:2}", style)

    cal_win.refresh()

def draw_upcoming_events(event_win, year, month):
    global event_page

    event_win.erase()
    event_win.box()

    line = 1
    event_win.addstr(line, 2, "Ближайшие события (PgUp / PgDn для перелистывания):", curses.A_BOLD)
    line += 2

    col_day_width = 9
    col_time_width = 8
    col_title_width = 25
    total_width = col_day_width + col_time_width + col_title_width + 6
    win_height, win_width = event_win.getmaxyx()

    num_columns = max(1, (win_width - 4) // (total_width + 2))
    start_x_list = [(2 + i * (total_width + 2)) for i in range(num_columns)]

    def hline():
        return "+" + "-" * col_day_width + "+" + "-" * col_time_width + "+" + "-" * col_title_width + "+"

    upcoming = []
    for date_str in sorted(events.keys()):
        event_date = datetime.strptime(date_str, "%Y-%m-%d")
        if event_date.year == year and (view_mode == "year" or event_date.month == month):
            for event in sorted(events[date_str], key=lambda e: e['time']):
                upcoming.append((f"{event_date.day} {calendar.month_abbr[event_date.month]}", event['time'], event['title']))

    events_per_page = (win_height - 8) * num_columns
    total_pages = max(1, (len(upcoming) + events_per_page - 1) // events_per_page)

    if event_page >= total_pages:
        event_page = total_pages - 1
    if event_page < 0:
        event_page = 0

    start_idx = event_page * events_per_page
    end_idx = start_idx + events_per_page
    page_upcoming = upcoming[start_idx:end_idx]

    current_x_idx = 0
    start_x = start_x_list[current_x_idx]
    line_start = line

    event_win.addstr(line, start_x, hline())
    line += 1
    header = "|" + "День".center(col_day_width) + "|" + "Время".center(col_time_width) + "|" + "Описание".center(col_title_width) + "|"
    event_win.addstr(line, start_x, header)
    line += 1
    event_win.addstr(line, start_x, hline())
    line += 1

    # Рисуем события
    for day_month, time, title in page_upcoming:
        if line >= win_height - 5:
            current_x_idx += 1
            if current_x_idx >= len(start_x_list):
                break
            start_x = start_x_list[current_x_idx]
            line = line_start

            event_win.addstr(line, start_x, hline())
            line += 1
            event_win.addstr(line, start_x, header)
            line += 1
            event_win.addstr(line, start_x, hline())
            line += 1

        row = "|" + str(day_month).center(col_day_width) + "|" + time.center(col_time_width) + "|" + title.center(col_title_width)[:col_title_width] + "|"
        event_win.addstr(line, start_x, row)
        line += 1

    if line < win_height - 5:
        event_win.addstr(line, start_x, hline())

    page_info = f"Страница {event_page + 1} из {total_pages}"
    event_win.addstr(win_height - 2, (win_width - len(page_info)) // 2, page_info, curses.A_BOLD)

    event_win.refresh()

def add_event(year, month, day, time, title):
    date_str = f"{year}-{month:02d}-{day:02d}"
    if date_str not in events:
        events[date_str] = []
    events[date_str].append({"time": time, "title": title})

    msg = {
        "action": "add",
        "date": date_str,
        "time": time,
        "title": title
    }
    rabbit_channel.basic_publish(
        exchange=RABBIT_EXCHANGE,
        routing_key='calendar.add',
        body=json.dumps(msg),
        properties=pika.BasicProperties(delivery_mode=2)
    )


def delete_event(year, month, day, msg_win):
    date_str = f"{year}-{month:02d}-{day:02d}"
    if date_str in events:
        del events[date_str]
        msg = {
            "action": "delete",
            "date": date_str
        }
        rabbit_channel.basic_publish(
            exchange=RABBIT_EXCHANGE,
            routing_key='calendar.delete',
            body=json.dumps(msg),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        show_message(msg_win, f"События на {date_str} удалены.")
    else:
        show_message(msg_win, f"На {date_str} событий нет.")

def input_string(stdscr, prompt):
    h, w = stdscr.getmaxyx()
    width = min(w - 10, 60)
    input_win = curses.newwin(5, width, h // 2 - 2, (w - width) // 2)
    input_win.box()
    input_win.addstr(1, 2, prompt[:width - 4])
    input_win.addstr(2, 2, "> ")
    input_win.refresh()

    curses.echo()
    input_win.move(2, 4)
    try:
        user_input = input_win.getstr(2, 4, width - 6).decode("utf-8")
    except Exception:
        user_input = ""
    curses.noecho()

    input_win.erase()
    input_win.refresh()
    del input_win
    return user_input

rabbit_conn = None
rabbit_channel = None
RABBIT_EXCHANGE = "S3"
RABBIT_QUEUE = "events"

def setup_rabbitmq():
    global rabbit_conn, rabbit_channel, events

    params = pika.ConnectionParameters(
        host='localhost',
        port=5672,
        credentials=pika.PlainCredentials('guest', 'guest')
    )
    rabbit_conn = pika.BlockingConnection(params)
    rabbit_channel = rabbit_conn.channel()

    rabbit_channel.exchange_declare(exchange=RABBIT_EXCHANGE, exchange_type='topic', durable=True)
    rabbit_channel.queue_declare(queue=RABBIT_QUEUE, durable=True)
    rabbit_channel.queue_bind(queue=RABBIT_QUEUE, exchange=RABBIT_EXCHANGE, routing_key='#')

    for method_frame, properties, body in rabbit_channel.consume(RABBIT_QUEUE, inactivity_timeout=1):
        if body is None:
            break
        try:
            payload = json.loads(body.decode())
            date = payload.get("date")
            if payload.get("action") == "add":
                ev = {"time": payload.get("time", ""), "title": payload.get("title", "")}
                events.setdefault(date, []).append(ev)
            elif payload.get("action") == "delete":
                events.pop(date, None)
        except:
            continue
    rabbit_channel.cancel()


# --- Главная функция ---
def main(stdscr):
    setup_rabbitmq()

    global current_year, current_month, highlight_color, view_mode, event_page

    curses.curs_set(0)
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    curses.start_color()

    stdscr.nodelay(False)
    stdscr.timeout(100)

    h, w = stdscr.getmaxyx()
    msg_win = curses.newwin(3, w - 35, h - 3, 0)
    msg_win.box()
    msg_win.refresh()

    while True:
        if view_mode == "month":
            cal_height = 10
            event_height = h - cal_height - 3
        else:
            cal_height = h - 40
            event_height = h - cal_height - 3

        cal_win = curses.newwin(cal_height, w - 35, 0, 0)
        button_win = curses.newwin(h, 34, 0, w - 34)
        event_win = curses.newwin(event_height, w - 35, cal_height, 0)

        cal_win.erase()
        button_win.erase()
        event_win.erase()

        draw_calendar(cal_win, current_year, current_month)
        draw_buttons(button_win)
        draw_upcoming_events(event_win, current_year, current_month)

        cal_win.refresh()
        button_win.refresh()
        event_win.refresh()
        msg_win.box()
        msg_win.refresh()

        key = stdscr.getch()

        if key == curses.KEY_MOUSE:
            try:
                id, mx, my, _, bstate = curses.getmouse()
                if bstate & curses.BUTTON1_CLICKED:
                    if 2 <= mx <= 10 and my == 0:
                        if view_mode == "year":
                            view_mode = "month"
                            current_month = datetime.now().month
                            current_year = datetime.now().year
                        else:
                            view_mode = "year"
                        continue

                    if prev_month_button[0] <= mx <= prev_month_button[2] and my == prev_month_button[1]:
                        if view_mode == "month":
                            current_month -= 1
                            if current_month == 0:
                                current_month = 12
                                current_year -= 1
                        else:
                            current_year -= 1
                        continue

                    if next_month_button[0] <= mx <= next_month_button[2] and my == next_month_button[1]:
                        if view_mode == "month":
                            current_month += 1
                            if current_month == 13:
                                current_month = 1
                                current_year += 1
                        else:
                            current_year += 1
                        continue

                    if mx >= w - 34:
                        idx = (my - 2) // 3
                        if 0 <= idx < len(buttons):
                            action = buttons[idx][1]
                            if action == "add":
                                day = int(input_string(stdscr, "Введите день: "))
                                try:
                                    datetime(current_year, current_month, day)
                                except ValueError:
                                    show_message(msg_win, f"В {calendar.month_name[current_month]} нет дня {day}.")
                                    continue

                                time = input_string(stdscr, "Введите время (HH:MM): ")
                                title = input_string(stdscr, "Введите название события: ")
                                add_event(current_year, current_month, day, time, title)

                            elif action == "delete":
                                day = int(input_string(stdscr, "Введите день: "))
                                delete_event(current_year, current_month, day, msg_win)
                            elif action == "color":
                                highlight_color = (highlight_color + 1) % 8 or 1
                            elif action == "clear":
                                events.clear()
                                show_message(msg_win, "Все события сброшены.")
                            elif action == "quit":
                                break

                    calc_start_y = 2 + len(buttons) * 3 + 2 + 3
                    if mx >= w - 34 and my >= calc_start_y:
                        relative_x = mx - (w - 34)
                        col = (relative_x - 2) // 8
                        row = (my - calc_start_y) // 2
                        if 0 <= row < len(calc_keys) and 0 <= col < len(calc_keys[0]):
                            key_label = calc_keys[row][col]
                            if key_label:
                                handle_calculator_input(key_label)

            except Exception:
                pass

        elif key == ord('q'):
            break
        elif key == curses.KEY_NPAGE:  # PgDn
            event_page += 1
        elif key == curses.KEY_PPAGE:  # PgUp
            event_page -= 1
            if event_page < 0:
                event_page = 0

if __name__ == "__main__":
    curses.wrapper(main)
