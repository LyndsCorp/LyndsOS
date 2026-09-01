#!/bin/bash

# Módulo motd para Casata
# El casata motd list ahora te lo muestra de forma ordenada
# Copyright (C) 2026 David Baña Szymaniak

set -euo pipefail
shopt -s nullglob

# Cargar librería de historial
if [ -f "/usr/local/casata/lib/history-lib.sh" ]; then
    source "/usr/local/casata/lib/history-lib.sh"
fi

CASATA_ROOT="/usr/local/casata"
NEWS_DIR="$CASATA_ROOT/news"
MOTD_URL="https://github.com/LyndsCorp/Lynds-MOTD/raw/refs/heads/main/today.txt"

# Colores (se heredan del script principal, pero nos aseguramos)
if [ -z "$GREEN" ]; then GREEN='\033[0;32m'; fi
if [ -z "$RED" ]; then RED='\033[0;31m'; fi
if [ -z "$NC" ]; then NC='\033[0m'; fi

# Normaliza una fecha a formato DD-MM-YYYY
# Acepta D-M-YYYY, DD/MM/YYYY, DD.MM.YYYY, etc.
normalize_date() {
    local input="$1"
    # Reemplazar separadores comunes por '-'
    input="${input//\//-}"
    input="${input//./-}"
    IFS='-' read -ra parts <<< "$input"
    if [ ${#parts[@]} -ne 3 ]; then
        return 1
    fi
    # Forzar base decimal para evitar que 08/09 se interpreten como octales
    local day=$(printf "%02d" "$((10#${parts[0]}))" 2>/dev/null)
    local month=$(printf "%02d" "$((10#${parts[1]}))" 2>/dev/null)
    local year="${parts[2]}"
    if [ -z "$day" ] || [ -z "$month" ] || ! [[ "$year" =~ ^[0-9]{4}$ ]]; then
        return 1
    fi
    echo "${day}-${month}-${year}"
}

# Obtiene la fecha actual del sistema en formato DD-MM-YYYY
today=$(date +%d-%m-%Y)

# Devuelve la ruta del archivo más reciente (por fecha en el nombre) dentro de NEWS_DIR
get_latest_file() {
    local latest=""
    local latest_num=""
    if [ -d "$NEWS_DIR" ]; then
        for file in "$NEWS_DIR"/*.txt; do
            [ -e "$file" ] || continue
            local filename=$(basename "$file" .txt)
            local normalized=$(normalize_date "$filename")
            if [ -n "$normalized" ]; then
                # Convertir a YYYYMMDD para comparación numérica
                local date_num=$(echo "$normalized" | awk -F- '{print $3$2$1}')
                if [ -z "$latest_num" ] || [ "$date_num" -gt "$latest_num" ]; then
                    latest_num="$date_num"
                    latest="$file"
                fi
            fi
        done
    fi
    echo "$latest"
}

# Muestra el contenido del archivo para una fecha dada
show_motd_for_date() {
    local date_str="$1"
    local normalized=$(normalize_date "$date_str")
    if [ -z "$normalized" ]; then
        echo -e "${RED}Error: Formato de fecha inválido. Use DD-MM-YYYY o D-M-YYYY.${NC}"
        exit 1
    fi
    local file="$NEWS_DIR/${normalized}.txt"
    if [ -f "$file" ]; then
        cat "$file"
    else
        echo -e "${RED}No hay mensaje del día para la fecha ${normalized}.${NC}"
        exit 1
    fi
}

# Descarga el mensaje actual y lo guarda con la fecha de hoy (solo root)
download_today_motd() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}Error: Se requieren privilegios de root para actualizar el mensaje del día.${NC}"
        exit 1
    fi
    mkdir -p "$NEWS_DIR"
    chmod 755 "$NEWS_DIR"
    local temp_file=$(mktemp)
    if command -v curl &> /dev/null; then
        curl -s -L -o "$temp_file" "$MOTD_URL"
    elif command -v wget &> /dev/null; then
        wget -q -O "$temp_file" "$MOTD_URL"
    else
        echo -e "${RED}Error: No se encontró curl ni wget para descargar.${NC}"
        rm -f "$temp_file"
        exit 1
    fi
    if [ ! -s "$temp_file" ]; then
        echo -e "${RED}Error: Fallo al descargar el mensaje del día.${NC}"
        rm -f "$temp_file"
        exit 1
    fi
    local dest_file="$NEWS_DIR/${today}.txt"
    mv "$temp_file" "$dest_file"
    chmod 644 "$dest_file"
    echo -e "${GREEN}Mensaje del día actualizado a ${today}.${NC}"
    log_event "MOTD" "date=\"$today\" status=UPDATED"
    cat "$dest_file"
}

# ----------------------------------------------------------------------
# Nuevas funciones para random, list y alias de días
# ----------------------------------------------------------------------

# Resuelve un alias de día (nombre en español/inglés, o relativo) a DD-MM-YYYY
# Devuelve 1 si no se reconoce el alias
resolve_day_alias() {
    local input="$1"
    input=$(echo "$input" | tr '[:upper:]' '[:lower:]')

    case "$input" in
        hoy|today)
            date +%d-%m-%Y
            return 0
            ;;
        ayer|yesterday)
            date -d "1 day ago" +%d-%m-%Y
            return 0
            ;;
        anteayer)
            date -d "2 days ago" +%d-%m-%Y
            return 0
            ;;
    esac

    local day_num
    case "$input" in
        sunday|domingo)            day_num=0 ;;
        monday|lunes)              day_num=1 ;;
        tuesday|martes)            day_num=2 ;;
        wednesday|miércoles|miercoles) day_num=3 ;;
        thursday|jueves)           day_num=4 ;;
        friday|viernes)            day_num=5 ;;
        saturday|sábado|sabado)    day_num=6 ;;
        *) return 1 ;;
    esac

    local today_epoch=$(date +%s)
    local today_wday=$(date +%w)
    local target_wday=$day_num

    local days_ago=$(( (today_wday - target_wday + 7) % 7 ))
    local target_epoch=$(( today_epoch - days_ago * 86400 ))
    date -d "@$target_epoch" +%d-%m-%Y
    return 0
}

# Muestra un MOTD aleatorio
show_random_motd() {
    if [ ! -d "$NEWS_DIR" ]; then
        echo -e "${RED}No hay mensajes del día disponibles.${NC}"
        exit 1
    fi
    local files=("$NEWS_DIR"/*.txt)
    if [ ${#files[@]} -eq 0 ]; then
        echo -e "${RED}No hay mensajes del día disponibles.${NC}"
        exit 1
    fi
    local idx=$(( RANDOM % ${#files[@]} ))
    local file="${files[$idx]}"
    local date_str=$(basename "$file" .txt)
    echo -e "${GREEN}Mensaje del día aleatorio (${date_str}):${NC}"
    cat "$file"
}

# Lista todos los días con MOTD almacenados (ordenados del más reciente al más antiguo)
list_available_days() {
    if [ ! -d "$NEWS_DIR" ]; then
        echo "No hay mensajes del día disponibles."
        exit 0
    fi
    local files=("$NEWS_DIR"/*.txt)
    if [ ${#files[@]} -eq 0 ]; then
        echo "No hay mensajes del día disponibles."
        exit 0
    fi
    echo "Días disponibles:"
<<<<<<< HEAD
=======
    # Extraer fechas, convertir a YYYYMMDD y ordenar descendentemente
>>>>>>> d9e56a2 (casata motd list ahora te los muestra de forma ordenada)
    for f in "${files[@]}"; do
        base=$(basename "$f" .txt)
        IFS='-' read -ra parts <<< "$base"
        if [ ${#parts[@]} -eq 3 ]; then
            # Forzar base 10 para días/meses con ceros delante
            printf "%04d%02d%02d %s\n" "$((10#${parts[2]}))" "$((10#${parts[1]}))" "$((10#${parts[0]}))" "$base"
        fi
    done | sort -rn | while read -r sortkey original; do
        echo "  $original"
    done
}

# ----------------------------------------------------------------------
# Lógica principal
# ----------------------------------------------------------------------

if [ $# -eq 0 ]; then
    if [ "$EUID" -eq 0 ]; then
        download_today_motd
    else
        latest_file=$(get_latest_file)
        if [ -z "$latest_file" ]; then
            echo "No hay mensajes del día disponibles."
            echo -e "${RED}¡Recuerda pedirle a tu administrador que ejecute sudo casata motd!${NC}"
            exit 0
        fi
        latest_date=$(basename "$latest_file" .txt)
        cat "$latest_file"
        if [ "$latest_date" != "$today" ]; then
            echo -e "\n${RED}¡Recuerda pedirle a tu administrador que ejecute 'sudo casata motd'!${NC}"
        fi
    fi
else
    arg="$1"
    case "$arg" in
        random)
            show_random_motd
            ;;
        list)
            list_available_days
            ;;
        *)
            resolved_date=$(resolve_day_alias "$arg" || true)
            if [ -n "$resolved_date" ]; then
                show_motd_for_date "$resolved_date"
            else
                show_motd_for_date "$arg"
            fi
            ;;
    esac
fi
