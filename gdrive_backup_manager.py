#!/usr/bin/env python3
import subprocess
import json
import sys
import os
import logging

# Настройка сквозного логирования в файл gdrive_backup_log.txt
LOG_FILE = os.path.expanduser("~/gdrive_backup_log.txt")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def log_and_print(message, level="info", console_prefix="[ИНФО]"):
    """Запись события в лог-файл и вывода информативного статуса в консоль."""
    if level == "error":
        logging.error(message)
        print(f"\033[31m[ОШИБКА]\033[0m {message}")
    elif level == "warning":
        logging.warning(message)
        print(f"\033[33m[ПРЕДУПРЕЖДЕНИЕ]\033[0m {message}")
    elif level == "success":
        logging.info(message)
        print(f"\033[32m[УСПЕХ]\033[0m {message}")
    else:
        logging.info(message)
        print(f"{console_prefix} {message}")

try:
    import questionary
except ImportError:
    msg = "Библиотека 'questionary' не установлена. Выполните: pip3 install questionary"
    print(f"\033[31m[ОШИБКА]\033[0m {msg}")
    logging.error(msg)
    sys.exit(1)

CONFIG_PATH = os.path.expanduser("~/.config/rclone/rclone.conf")
BASE_MOUNT_DIR = "/mnt/gdrive_mount"
DEFAULT_TARGET_DIR = "/mnt/encrypted_backup"
BASE_REMOTE = "gdrive_ws"

def get_mounted_drives():
    """Получает список смонтированных дисков в /mnt/gdrive_mount."""
    mounted = []
    if not os.path.exists(BASE_MOUNT_DIR):
        return mounted
    try:
        result = subprocess.run(["df", "-h"], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if BASE_MOUNT_DIR in line:
                parts = line.split()
                mount_point = parts[-1]
                folder_name = os.path.basename(mount_point)
                mounted.append({"name": folder_name, "path": mount_point})
    except Exception as e:
        log_and_print(f"Ошибка получения списка смонтированных дисков: {e}", level="error")
    return mounted

def get_disk_space_info(path):
    """Возвращает свободное и общее место на целевом диске в ГБ."""
    try:
        st = os.statvfs(path)
        free_gb = (st.f_bavail * st.f_frsize) / (1024 ** 3)
        total_gb = (st.f_blocks * st.f_frsize) / (1024 ** 3)
        used_gb = total_gb - free_gb
        return {"total_gb": round(total_gb, 2), "used_gb": round(used_gb, 2), "free_gb": round(free_gb, 2)}
    except Exception as e:
        logging.error(f"Ошибка получения свободной памяти для {path}: {e}")
        return None

def show_status_menu():
    """Меню 1: Просмотр смонтированных источников и целевых носителей."""
    print("\n=======================================================")
    print("      СТАТУС ИСТОЧНИКОВ И НАКОПИТЕЛЕЙ ДЛЯ БЭКАПА       ")
    print("=======================================================\n")
    
    # 1. Смонтированные Google Drives
    mounted = get_mounted_drives()
    print("1. Смонтированные источники Google Drives (/mnt/gdrive_mount):")
    if not mounted:
        print("   \033[33m[!] Нет активных смонтированных дисков.\033[0m")
    else:
        for idx, d in enumerate(mounted, 1):
            print(f"   {idx}. \033[36m{d['name']}\033[0m -> {d['path']}")

    print("\n-------------------------------------------------------")
    # 2. Целевые локальные накопители
    print("2. Целевой локальный диск резервного копирования:")
    target_path = DEFAULT_TARGET_DIR
    print(f"   Путь: \033[35m{target_path}\033[0m")
    
    space = get_disk_space_info(target_path)
    if space:
        print(f"   Всего места:    \033[36m{space['total_gb']} ГБ\033[0m")
        print(f"   Использовано:   \033[33m{space['used_gb']} ГБ\033[0m")
        print(f"   Свободно:       \033[32m{space['free_gb']} ГБ\033[0m")
    else:
        print("   \033[31m[!] Не удалось получить информацию о свободной памяти (диск не подключен?)\033[0m")

    input("\nНажмите Enter для возврата в главное меню...")

def backup_execution_menu():
    """Меню 2: Резервное копирование со сжатием/конвертацией документов."""
    print("\n=======================================================")
    print("          РЕЗЕРВНОЕ КОПИРОВАНИЕ ДАННЫХ GOOGLE          ")
    print("=======================================================\n")

    # Получаем список смонтированных источников
    mounted = get_mounted_drives()
    if not mounted:
        log_and_print("Сначала смонтируйте нужные Общие диски через gdrive_manager.py!", level="warning")
        input("\nНажмите Enter для возврата...")
        return

    # Подготавливаем выбор источника
    choices_src = [questionary.Choice(title=f"Все смонтированные диски ({len(mounted)} шт.)", value="ALL")]
    choices_src += [questionary.Choice(title=f"{d['name']} ({d['path']})", value=d) for d in mounted]
    choices_src.append(questionary.Choice(title="← Назад в меню", value="CANCEL"))

    selected_src = questionary.select(
        "Выберите ИСТОЧНИК для бэкапа:",
        choices=choices_src
    ).ask()

    if not selected_src or selected_src == "CANCEL":
        log_and_print("Операция копирования отменена.", level="warning")
        return

    # Выбор целевого пути
    target_base = questionary.text(
        "Укажите целевую директорию для хранения бэкапа:",
        default=DEFAULT_TARGET_DIR
    ).ask()

    if not target_base:
        log_and_print("Целевой путь не зафиксирован. Отмена.", level="warning")
        return

    # Вычисляем список дисков к бэкапу
    drives_to_backup = mounted if selected_src == "ALL" else [selected_src]

    print("\n-------------------------------------------------------")
    log_and_print(f"Начало резервного копирования {len(drives_to_backup)} дисков в {target_base}...", level="info")
    print("Осуществляется автоматическая конвертация:")
    print("  • Google Docs   -> .docx")
    print("  • Google Sheets -> .xlsx")
    print("  • Google Slides -> .pptx / PDF")
    print("-------------------------------------------------------\n")

    for d in drives_to_backup:
        drive_name = d['name']
        src_path = d['path']
        dest_path = os.path.join(target_base, drive_name)

        os.makedirs(dest_path, exist_ok=True)
        log_and_print(f"Копирование: '{drive_name}' -> '{dest_path}'", console_prefix="[--->]")

        # Команда rclone copy с конвертацией Google Workspace документов
        rclone_cmd = [
            "rclone", "copy", src_path, dest_path,
            "--config", CONFIG_PATH,
            "--drive-export-formats", "docx,xlsx,pptx,pdf",
            "--transfers", "4",
            "--checkers", "8",
            "--progress",
            "--stats", "5s",
            "--log-level", "INFO"
        ]

        logging.info(f"Запуск rclone copy: {' '.join(rclone_cmd)}")

        try:
            # Выполняем rclone с выводом прогресса прямо в консоль
            process = subprocess.Popen(rclone_cmd, stderr=subprocess.PIPE, text=True)
            
            # Читаем лог прогресса rclone и записываем в файл логов
            for line in process.stderr:
                print(line, end="")
                if "Transferred:" in line or "ERROR" in line:
                    logging.info(f"[{drive_name}] {line.strip()}")

            process.wait()

            if process.returncode == 0:
                log_and_print(f"Резервная копия диска '{drive_name}' успешно создана!", level="success")
            else:
                log_and_print(f"Копирование диска '{drive_name}' завершено с ошибками.", level="error")

        except Exception as e:
            log_and_print(f"Сбой выполнения rclone copy для {drive_name}: {e}", level="error")

    print("\n-------------------------------------------------------")
    log_and_print("Резервное копирование завершено!", level="success")
    input("\nНажмите Enter для возврата в главное меню...")

def verify_backup_menu():
    """Меню 3: Сравнение и проверка целостности созданных копий."""
    print("\n=======================================================")
    print("         ПРОВЕРКА ЦЕЛОСТНОСТИ РЕЗЕРВНЫХ КОПИЙ          ")
    print("=======================================================\n")

    mounted = get_mounted_drives()
    if not mounted:
        log_and_print("Сначала смонтируйте нужные Общие диски для сверки!", level="warning")
        input("\nНажмите Enter для возврата...")
        return

    choices_src = [questionary.Choice(title=f"{d['name']} ({d['path']})", value=d) for d in mounted]
    choices_src.append(questionary.Choice(title="← Назад в меню", value="CANCEL"))

    selected_src = questionary.select(
        "Выберите диск-источник для сверки:",
        choices=choices_src
    ).ask()

    if not selected_src or selected_src == "CANCEL":
        return

    drive_name = selected_src['name']
    src_path = selected_src['path']
    dest_path = os.path.join(DEFAULT_TARGET_DIR, drive_name)

    if not os.path.exists(dest_path):
        log_and_print(f"Целевая папка {dest_path} не существует! Сначала выполните бэкап.", level="error")
        input("\nНажмите Enter для возврата...")
        return

    log_and_print(f"Запуск сверки данных: {src_path} <---> {dest_path}", console_prefix="[--->]")

    check_cmd = [
        "rclone", "check", src_path, dest_path,
        "--config", CONFIG_PATH,
        "--one-way",
        "--log-level", "INFO"
    ]

    logging.info(f"Запуск rclone check: {' '.join(check_cmd)}")

    try:
        process = subprocess.Popen(check_cmd, stderr=subprocess.PIPE, text=True)
        for line in process.stderr:
            print(line, end="")
            logging.info(f"[CHECK: {drive_name}] {line.strip()}")
        process.wait()

        if process.returncode == 0:
            log_and_print(f"Проверка пройдена! Все файлы на '{drive_name}' совпадают с копией.", level="success")
        else:
            log_and_print(f"Выявлены расхождения при проверке диска '{drive_name}'. Подробности в логе.", level="warning")

    except Exception as e:
        log_and_print(f"Сбой сверки: {e}", level="error")

    input("\nНажмите Enter для возврата в главное меню...")

def main():
    log_and_print("=== Сессия управления бэкапами gdrive_backup_manager.py запущена ===", console_prefix="[СТАРТ]")
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print("\033[1;35m=======================================================\033[0m")
        print("\033[1;35m    МЕНЕДЖЕР РЕЗЕРВНОГО КОПИРОВАНИЯ GOOGLE WORKSPACE   \033[0m")
        print("\033[1;35m=======================================================\033[0m\n")
        
        action = questionary.select(
            "Выберите действие:",
            choices=[
                "1. Проверить статус источников, дисков бэкапа и свободное место",
                "2. Создать полную резервную копию (с конвертацией Google Docs)",
                "3. Провести проверку целостности копий (rclone check)",
                "Выход"
            ]
        ).ask()

        if action is None:
            log_and_print("Скрипт остановлен комбинацией клавиш.", level="warning")
            sys.exit(0)

        if action.startswith("1"):
            show_status_menu()
        elif action.startswith("2"):
            backup_execution_menu()
        elif action.startswith("3"):
            verify_backup_menu()
        else:
            log_and_print("=== Завершение сессии gdrive_backup_manager.py ===", console_prefix="[ВЫХОД]")
            print("\nЗавершение работы.")
            sys.exit(0)

if __name__ == "__main__":
    main()
