#!/bin/bash
BASE_DIR="/mnt/gdrive_shared"
CONFIG_PATH="/home/sudou/.config/rclone/rclone.conf"

# Создаем основную директорию
mkdir -p "$BASE_DIR"

# Получаем список всех созданных remotes, начинающихся на drive_
remotes=$(rclone listremotes --config="$CONFIG_PATH" | grep '^drive_')

for remote in $remotes; do
    # Убираем двоеточие в конце имени
    clean_remote="${remote%:}"
    # Имя папки совпадает с именем remote без префикса drive_
    folder_name="${clean_remote#drive_}"
    target_dir="$BASE_DIR/$folder_name"

    mkdir -p "$target_dir"

    # Сбрасываем старый монтированный FUSE если был
    fusermount -uz "$target_dir" 2>/dev/null

    echo "Монтируем $clean_remote в $target_dir ..."

    # Внутри цикла скрипта mount_all.sh вызовите rclone так:
    rclone mount "$remote" "$target_dir" \
    --config="$CONFIG_PATH" \
    --vfs-cache-mode full \
    --vfs-cache-max-size 50G \
    --cache-dir /mnt/encrypted_backup/rclone_cache \
    --allow-other \
    --daemon
done

echo "Все диски смонтированы!"
