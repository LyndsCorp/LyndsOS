#!/bin/bash
# /usr/local/casata/modules/history.sh

CASATA_ROOT="/usr/local/casata"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

show_help() {
    cat <<EOF
Uso: casata history [OPCIONES]

Opciones:
  --user <nombre>   Ver historial de un usuario específico (solo root)
  --disable         Desactivar el registro de historial
  --enable          Reactivar el registro de historial
  --clear           Limpiar el historial (pide confirmación)
  --lines N         Mostrar solo las últimas N líneas
  --help            Mostrar esta ayuda

Sin opciones, muestra el historial del usuario actual (o global si se ejecuta con sudo).
EOF
}

# Determinar si estamos en modo root
IS_ROOT=0
if [ "$EUID" -eq 0 ]; then
    IS_ROOT=1
fi

# Archivos de log y flags
if [ $IS_ROOT -eq 1 ]; then
    LOG_FILE="/usr/local/casata/HISTORY.log"
    NO_LOG_FLAG="/usr/local/casata/NO_LOG"
else
    LOG_FILE="$HOME/.local/casata/HISTORY.log"
    NO_LOG_FLAG="$HOME/.local/casata/NO_LOG"
fi

USER_SPEC=""
DISABLE=0
ENABLE=0
CLEAR=0
LINES=""
SHOW_HELP=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --user)
            if [ $IS_ROOT -eq 0 ]; then
                echo -e "${RED}Error: --user solo está disponible con sudo (root).${NC}"
                exit 1
            fi
            USER_SPEC="$2"
            shift 2
            ;;
        --disable)
            DISABLE=1
            shift
            ;;
        --enable)
            ENABLE=1
            shift
            ;;
        --clear)
            CLEAR=1
            shift
            ;;
        --lines)
            LINES="$2"
            shift 2
            ;;
        --help)
            SHOW_HELP=1
            shift
            ;;
        *)
            echo -e "${RED}Opción desconocida: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

if [ $SHOW_HELP -eq 1 ]; then
    show_help
    exit 0
fi

# Desactivar / Activar
if [ $DISABLE -eq 1 ]; then
    touch "$NO_LOG_FLAG"
    echo -e "${GREEN}Historial desactivado para este ámbito.${NC}"
    exit 0
fi

if [ $ENABLE -eq 1 ]; then
    rm -f "$NO_LOG_FLAG"
    echo -e "${GREEN}Historial reactivado para este ámbito.${NC}"
    exit 0
fi

# Limpiar
if [ $CLEAR -eq 1 ]; then
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${YELLOW}El archivo de historial no existe.${NC}"
        exit 0
    fi
    read -p "¿Seguro que quieres borrar el historial? [s/N] " resp
    if [[ "$resp" =~ ^[sSyY] ]]; then
        > "$LOG_FILE"
        echo -e "${GREEN}Historial limpiado.${NC}"
    else
        echo -e "${YELLOW}Operación cancelada.${NC}"
    fi
    exit 0
fi

# Determinar archivo a mostrar
TARGET_LOG="$LOG_FILE"
if [ $IS_ROOT -eq 1 ] && [ -n "$USER_SPEC" ]; then
    USER_HOME=$(getent passwd "$USER_SPEC" | cut -d: -f6)
    if [ -z "$USER_HOME" ]; then
        echo -e "${RED}Error: Usuario '$USER_SPEC' no encontrado.${NC}"
        exit 1
    fi
    TARGET_LOG="$USER_HOME/.local/casata/HISTORY.log"
fi

if [ ! -f "$TARGET_LOG" ]; then
    echo -e "${YELLOW}No hay historial disponible.${NC}"
    exit 0
fi

# Mostrar historial
if [ -n "$LINES" ]; then
    if ! [[ "$LINES" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}Error: --lines debe ser un número positivo.${NC}"
        exit 1
    fi
    tail -n "$LINES" "$TARGET_LOG"
else
    cat "$TARGET_LOG"
fi
