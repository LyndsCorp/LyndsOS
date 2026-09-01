#!/bin/bash
# /usr/local/casata/modules/history.sh

CASATA_ROOT="/usr/local/casata"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ -f "$CASATA_ROOT/lib/history-lib.sh" ]; then
    source "$CASATA_ROOT/lib/history-lib.sh"
fi

show_help() {
    cat <<EOF
Uso: casata history [OPCIONES]

Opciones:
  --date <fecha|alias>  Ver solo entradas de una fecha o alias.
                        Fecha: DD-MM-YYYY o D-M-YYYY.
                        Alias: hoy, ayer, anteayer, lunes, martes, ...
                               today, yesterday, monday, tuesday, ...
  --user [nombre]       Ver historial de un usuario. Sin nombre usa el actual.
                        Por defecto se muestra el historial global/root.
  --type <tipo>         Filtrar por tipo (p. ej. PAQUETE_INSTALADO, ENLACE_CREADO, etc.)
  --search <texto>      Buscar texto en las líneas
  --lines N             Mostrar solo las N entradas más recientes
  --exited              Mostrar también la salida capturada de los comandos.
                        Por defecto se oculta para no saturar el historial.
  --disable             Desactivar el registro de historial
  --enable              Reactivar el registro de historial
  --clear               Limpiar el historial (pide confirmación)
  --help                Mostrar esta ayuda

Sin opciones, muestra el historial global (de root) del más reciente al más antiguo.
EOF
}

# Normalizar fecha DD-MM-YYYY a YYYY-MM-DD
normalize_date() {
    local input="$1"
    input="${input//\//-}"
    input="${input//./-}"
    IFS='-' read -ra parts <<< "$input"
    [ ${#parts[@]} -ne 3 ] && return 1
    local day=$(printf "%02d" "$((10#${parts[0]}))" 2>/dev/null)
    local month=$(printf "%02d" "$((10#${parts[1]}))" 2>/dev/null)
    local year="${parts[2]}"
    if [ -z "$day" ] || [ -z "$month" ] || ! [[ "$year" =~ ^[0-9]{4}$ ]]; then
        return 1
    fi
    echo "${year}-${month}-${day}"
}

# Resolver alias de día a DD-MM-YYYY
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
    local today_wday=$(date +%w)   # 0=domingo, 1=lunes, ... 6=sábado
    local target_wday=$day_num

    local days_ago=$(( (today_wday - target_wday + 7) % 7 ))
    local target_epoch=$(( today_epoch - days_ago * 86400 ))
    date -d "@$target_epoch" +%d-%m-%Y
    return 0
}

show_with_pager() {
    if [ -t 1 ]; then
        if command -v less &>/dev/null; then
            less -R
        elif command -v more &>/dev/null; then
            more
        else
            cat
        fi
    else
        cat
    fi
}

USER_SPEC=""
DATE_SPEC=""
TYPE_SPEC=""
SEARCH_SPEC=""
LINES=""
SHOW_EXITED=0
DISABLE=0; ENABLE=0; CLEAR=0; SHOW_HELP=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --user)
            if [ -n "$2" ] && [[ "$2" != -* ]]; then
                USER_SPEC="$2"
                shift 2
            else
                USER_SPEC="$(id -un)"
                shift
            fi
            ;;
        --date|--fecha|--day)
            DATE_SPEC="$2"
            shift 2
            ;;
        --type)
            TYPE_SPEC="$2"
            shift 2
            ;;
        --search)
            SEARCH_SPEC="$2"
            shift 2
            ;;
        --lines)
            LINES="$2"
            shift 2
            ;;
        --exited|--exit|--salida)
            SHOW_EXITED=1
            shift
            ;;
        --disable)
            DISABLE=1; shift ;;
        --enable)
            ENABLE=1; shift ;;
        --clear)
            CLEAR=1; shift ;;
        --help)
            SHOW_HELP=1; shift ;;
        *)
            echo -e "${RED}Opción desconocida: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

if [ $SHOW_HELP -eq 1 ]; then show_help; exit 0; fi

# Acciones de control
if [ $DISABLE -eq 1 ]; then
    touch "$(get_no_log_flag)"
    echo -e "${GREEN}Historial desactivado.${NC}"
    exit 0
fi

if [ $ENABLE -eq 1 ]; then
    rm -f "$(get_no_log_flag)"
    echo -e "${GREEN}Historial reactivado.${NC}"
    exit 0
fi

if [ $CLEAR -eq 1 ]; then
    LOG_FILE=$(get_log_file)
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${YELLOW}No hay historial.${NC}"
        exit 0
    fi
    read -p "¿Seguro que quieres borrar el historial? [s/N] " resp
    if [[ "$resp" =~ ^[sSyY] ]]; then
        > "$LOG_FILE"
        echo -e "${GREEN}Historial limpiado.${NC}"
    else
        echo -e "${YELLOW}Cancelado.${NC}"
    fi
    exit 0
fi

# Determinar archivo a mostrar
if [ -n "$USER_SPEC" ]; then
    USER_HOME=$(getent passwd "$USER_SPEC" | cut -d: -f6)
    if [ -z "$USER_HOME" ]; then
        echo -e "${RED}Error: Usuario '$USER_SPEC' no encontrado.${NC}"
        exit 1
    fi
    TARGET_LOG="$USER_HOME/.local/share/casata/HISTORY.log"
else
    TARGET_LOG="/usr/local/casata/HISTORY.log"
fi

if [ ! -f "$TARGET_LOG" ]; then
    echo -e "${YELLOW}No hay historial disponible.${NC}"
    exit 0
fi

# Procesar fecha: si es alias, obtener la fecha real
NORMALIZED_DATE=""
if [ -n "$DATE_SPEC" ]; then
    # Intentar primero como alias
    RESOLVED_ALIAS="$(resolve_day_alias "$DATE_SPEC" 2>/dev/null || true)"
    if [ -n "$RESOLVED_ALIAS" ]; then
        DATE_SPEC="$RESOLVED_ALIAS"
    fi

    NORMALIZED_DATE="$(normalize_date "$DATE_SPEC")"
    if [ -z "$NORMALIZED_DATE" ]; then
        echo -e "${RED}Error: Fecha inválida '$DATE_SPEC'. Use DD-MM-YYYY o un alias (hoy, ayer, lunes, ...).${NC}"
        exit 1
    fi
fi

# Límite de líneas (0 = sin límite)
LIMIT=0
if [ -n "$LINES" ]; then
    if ! [[ "$LINES" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}--lines debe ser un número.${NC}"
        exit 1
    fi
    LIMIT="$LINES"
fi

# Mostrar historial aplicando filtros de forma segura
{
    count=0
    in_output=0

    while IFS= read -r line; do
        # Detectar inicio de un bloque de salida
        if [[ "$line" == *"📤 Salida de "* ]] || [[ "$line" == *"⚠️ Errores de "* ]]; then
            in_output=1
            if [ $SHOW_EXITED -eq 0 ]; then
                continue
            fi
        fi

        # Si estamos dentro de un bloque de salida y no queremos mostrarla, saltarla
        if [ $SHOW_EXITED -eq 0 ] && [ $in_output -eq 1 ]; then
            if [[ "$line" =~ ^[[:space:]]+ ]]; then
                # Línea indentada de salida, omitir
                continue
            else
                # El bloque terminó, volver al estado normal
                in_output=0
            fi
        fi

        # Aplicar filtros normales
        if [ -n "$TYPE_SPEC" ] && [[ "$line" != *"[$TYPE_SPEC]"* ]]; then
            continue
        fi

        if [ -n "$SEARCH_SPEC" ] && [[ "$line" != *"$SEARCH_SPEC"* ]]; then
            continue
        fi

        if [ -n "$NORMALIZED_DATE" ] && [[ "$line" != \[$NORMALIZED_DATE\ * ]]; then
            continue
        fi

        # Mostrar la línea
        echo "$line"
        count=$((count + 1))

        if [ "$LIMIT" -gt 0 ] && [ "$count" -ge "$LIMIT" ]; then
            break
        fi
    done < "$TARGET_LOG"
} | show_with_pager
