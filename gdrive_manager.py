#!/usr/bin/env python3
import subprocess
import json
import sys
import os
import logging
import time

# Настройка сквозного логирования в файл gdrive_man_log.txt
LOG_FILE = os.path.expanduser("~/gdrive_man_log.txt")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def log_and_print(message, level="info", console_prefix="[ИНФО]"):
    """Запись события в лог-файл и отправка информативного статуса в консоль."""
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
CACHE_DIR = "/mnt/encrypted_backup/rclone_cache"
BASE_REMOTE = "gdrive_ws"

def get_available_drives():
    log_and_print("Запрос списка Общих дисков из Google Workspace...", console_prefix="[--->]")
    try:
        cmd = ["rclone", "backend", "drives", f"{BASE_REMOTE}:", "--config", CONFIG_PATH]
        logging.info(f"Выполнение команды backend drives: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        drives = json.loads(result.stdout)
        sorted_drives = sorted(drives, key=lambda x: x.get('name', ''))
        log_and_print(f"Успешно получено Общих дисков из Google API: {len(sorted_drives)} шт.", level="success")
        return sorted_drives
    except subprocess.CalledProcessError as e:
        err_msg = f"Ошибка выполнения rclone backend drives: {e.stderr.strip() if e.stderr else e}"
        log_and_print(err_msg, level="error")
        return []
    except Exception as e:
        err_msg = f"Сбой при запросе списка дисков: {e}"
        log_and_print(err_msg, level="error")
        return []

def get_mounted_drives():
    mounted = {}
    try:
        result = subprocess.run(["df", "-h"], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if BASE_MOUNT_DIR in line:
                parts = line.split()
                device = parts[0]
                mount_point = parts[-1]
                mounted[mount_point] = device
        logging.info(f"Проверка активных монтирований через df: найдено {len(mounted)} монтированных путей.")
    except Exception as e:
        err_msg = f"Ошибка чтения смонтированных дисков через df -h: {e}"
        log_and_print(err_msg, level="error")
    return mounted

def check_available_menu():
    print("\n=======================================================")
    print("      СПИСОК ДОСТУПНЫХ ОБЩИХ ДИСКОВ GOOGLE WORKSPACE    ")
    print("=======================================================\n")
    drives = get_available_drives()
    if not drives:
        print("\nДиски не найдены или нет доступа.")
        input("\nНажмите Enter для возврата в меню...")
        return
    
    print(f"\nВсего найдено дисков: {len(drives)}\n")
    for idx, d in enumerate(drives, 1):
        print(f" {idx:2d}. \033[36m{d.get('name')}\033[0m (ID: {d.get('id')})")
    
    input("\nНажмите Enter для возврата в главное меню...")

def mount_selected_menu():
    print("\n=======================================================")
    print("          ИНТЕРАКТИВНОЕ МОНТИРОВАНИЕ ДИСКОВ            ")
    print("=======================================================\n")
    drives = get_available_drives()
    if not drives:
        input("\nНажмите Enter для возврата...")
        return

    # Пункт отмены для возврата в меню без выбора
    cancel_option = {"name": "← Назад в главное меню", "id": "CANCEL_BACK"}
    choices = [questionary.Choice(title=f"CANCEL: {cancel_option['name']}", value=cancel_option)]
    choices += [questionary.Choice(title=d['name'], value=d) for d in drives]
    
    print("\n-------------------------------------------------------")
    print(" \033[33mИНСТРУКЦИЯ ПО ВЫБОРУ:\033[0m")
    print("  • Используйте стрелки [\033[32m↑\033[0m / \033[32m↓\033[0m] для перемещения по списку.")
    print("  • Нажмите [\033[32mПРОБЕЛ\033[0m], чтобы поставить галочку [*] на диске.")
    print("  • Нажмите [\033[32mENTER\033[0m], чтобы подтвердить и начать монтирование.")
    print("-------------------------------------------------------\n")
    
    selected = questionary.checkbox(
        "Выберите Общие диски для монтирования в /mnt/gdrive_mount:",
        choices=choices
    ).ask()

    # Фильтруем выбрав отмену, если она попала в список
    if selected:
        selected = [d for d in selected if d['id'] != 'CANCEL_BACK']

    if not selected:
        log_and_print("Возврат в меню: Ни один диск не был выбран.", level="warning")
        return

    log_and_print(f"Выбрано пользователем для монтирования: {len(selected)} шт. -> {[d['name'] for d in selected]}", level="info")

    os.makedirs(BASE_MOUNT_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    print("\n[--->] Запуск процедуры монтирования выбранных дисков...\n")

    for drive in selected:
        raw_name = drive['name']
        safe_name = "".join(c for c in raw_name if c.isalnum() or c in ('_', '-'))
        drive_id = drive['id']
        target_dir = os.path.join(BASE_MOUNT_DIR, safe_name)

        print(f"-------------------------------------------------------")
        print(f"Диск: \033[1;36m{raw_name}\033[0m")
        print(f"ID: \033[33m{drive_id}\033[0m")
        print(f"Целевой путь: \033[35m{target_dir}\033[0m")

        # 1. Сброс старой точки FUSE
        os.makedirs(target_dir, exist_ok=True)
        subprocess.run(["fusermount", "-uz", target_dir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 2. Прямое монтирование через gdrive_ws: (Non-blocking spawn)
        drive_cache = os.path.join(CACHE_DIR, safe_name)
        log_cmd = os.path.expanduser(f"~/rclone_{safe_name}.log")
        
        mount_cmd = [
            "rclone", "mount", f"{BASE_REMOTE}:", target_dir,
            f"--drive-team-drive={drive_id}",
            f"--config={CONFIG_PATH}",
            "--vfs-cache-mode", "full",
            "--vfs-cache-max-size", "10G",
            f"--cache-dir={drive_cache}",
            "--allow-other",
            "--log-level", "INFO",
            f"--log-file={log_cmd}",
            "--daemon"
        ]
        
        logging.info(f"Запуск команды: {' '.join(mount_cmd)}")
        
        # Используем Popen для предотвращения зависания терминала
        proc = subprocess.Popen(mount_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(1.5) # Пауза для инициализации FUSE
        
        if proc.poll() is None or proc.returncode == 0:
            log_and_print(f"Диск '{raw_name}' успешно отдан в монтирование: '{target_dir}'", level="success")
        else:
            stderr_out = proc.stderr.read() if proc.stderr else "Неизвестная ошибка"
            log_and_print(f"Ошибка монтирования '{raw_name}': {stderr_out.strip()}", level="error")

    print("\n-------------------------------------------------------")
    log_and_print("Процесс монтирования завершен!", level="success")
    input("\nНажмите Enter для возврата в главное меню...")

def list_mounted_menu():
    print("\n=======================================================")
    print("      СМОНТИРОВАННЫЕ В ДАННЫЙ МОМЕНТ ДИСКИ             ")
    print("=======================================================\n")
    mounted = get_mounted_drives()
    
    if not mounted:
        print("\033[33mВ настоящий момент нет активных смонтированных дисков в /mnt/gdrive_mount.\033[0m")
    else:
        print(f"Активных точек монтирования: \033[32m{len(mounted)}\033[0m\n")
        print(f"{'№':<3} | {'Имя папки':<25} | {'Полный путь монтирования':<40}")
        print("-" * 75)
        for idx, (path, device) in enumerate(mounted.items(), 1):
            folder_name = os.path.basename(path)
            print(f"{idx:<3} | \033[36m{folder_name:<25}\033[0m | {path}")
            
    input("\nНажмите Enter для возврата в главное меню...")

def unmount_menu():
    print("\n=======================================================")
    print("               РАЗМОНТИРОВАНИЕ ДИСКОВ                  ")
    print("=======================================================\n")
    mounted = get_mounted_drives()
    if not mounted:
        print("\033[33mНет активных смонтированных дисков для размонтирования.\033[0m")
        input("\nНажмите Enter для возврата...")
        return

    cancel_option = "/CANCEL_BACK"
    choices = [questionary.Choice(title="← Назад в главное меню", value=cancel_option)]
    choices += [questionary.Choice(title=f"{os.path.basename(path)}  -->  ({path})", value=path) for path in mounted.keys()]
    
    print("\n-------------------------------------------------------")
    print(" Отметьте [\033[32mПРОБЕЛОМ\033[0m] диски для размонтирования и нажмите [\033[32mENTER\033[0m]:")
    print("-------------------------------------------------------\n")

    selected_paths = questionary.checkbox(
        "Выберите диски для РАЗМОНТИРОВАНИЯ:",
        choices=choices
    ).ask()

    if selected_paths:
        selected_paths = [p for p in selected_paths if p != cancel_option]

    if not selected_paths:
        log_and_print("Возврат в меню: Диски для размонтирования не выбраны.", level="warning")
        return

    print("\n[--->] Запуск отмонтирования выбранных ресурсов...\n")

    for path in selected_paths:
        folder_name = os.path.basename(path)
        logging.info(f"Выполнение fusermount -uz для пути: {path}")
        res = subprocess.run(["fusermount", "-uz", path], capture_output=True, text=True)
        if res.returncode == 0:
            log_and_print(f"Диск '{folder_name}' ({path}) успешно отмонтирован.", level="success")
        else:
            err_msg = f"Ошибка отмонтирования '{path}': {res.stderr.strip()}"
            log_and_print(err_msg, level="error")

    print("\n-------------------------------------------------------")
    log_and_print("Операция размонтирования завершена!", level="success")
    input("\nНажмите Enter для возврата в главное меню...")

def main():
    log_and_print("=== Сессия управления gdrive_manager.py запущена ===", console_prefix="[СТАРТ]")
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print("\033[1;34m=======================================================\033[0m")
        print("\033[1;34m    МЕНЕДЖЕР GOOGLE WORKSPACE SHARED DRIVES (RCLONE)   \033[0m")
        print("\033[1;34m=======================================================\033[0m\n")
        
        action = questionary.select(
            "Выберите действие:",
            choices=[
                "1. Проверить все доступные Общие диски (Google API)",
                "2. Выбрать и смонтировать нужные диски в /mnt/gdrive_mount",
                "3. Показать смонтированные диски и пути",
                "4. Размонтировать выбранные диски",
                "Выход"
            ]
        ).ask()

        if action is None:
            log_and_print("Скрипт остановлен комбинацией клавиш.", level="warning")
            sys.exit(0)

        if action.startswith("1"):
            check_available_menu()
        elif action.startswith("2"):
            mount_selected_menu()
        elif action.startswith("3"):
            list_mounted_menu()
        elif action.startswith("4"):
            unmount_menu()
        else:
            log_and_print("=== Завершение сессии gdrive_manager.py ===", console_prefix="[ВЫХОД]")
            print("\nЗавершение работы.")
            sys.exit(0)

if __name__ == "__main__":
    main()
