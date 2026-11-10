#!/bin/bash
# Базовый remote, через который запрашиваем список дисков
BASE_REMOTE="gdrive_ws"
CONFIG_PATH="$HOME/.config/rclone/rclone.conf"

echo "Получаем список всех Общих дисков..."

# Запрашиваем список дисков в формате CSV (ID и Name)
rclone backend drives "$BASE_REMOTE:" 2>/dev/null | jq -r '.[] | "\(.id)\t\(.name)"' | while IFS=$'\t' read -r drive_id drive_name; do
    # Очищаем имя от спецсимволов для безопасности путей
    safe_name=$(echo "$drive_name" | tr -cd 'a-zA-Z0-9_-')
    remote_name="drive_${safe_name}"

    echo "Добавляем remote: $remote_name (ID: $drive_id)"

    # Прописываем конфиг для каждого диска
    rclone config create "$remote_name" drive \
        config_refresh_token=false \
        team_drive="$drive_id" \
        scope="drive" \
        --config="$CONFIG_PATH" >/dev/null
done

echo "Конфигурация успешно обновлена!"
