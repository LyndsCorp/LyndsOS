#!/bin/bash
# /usr/local/casata/lib/history-lib.sh
# Librería central de logging de Casata
# Formato humano, legible y ordenado del más reciente al más antiguo

# Copyright (C) 2026 David Baña Szymaniak

CASATA_ROOT="${CASATA_ROOT:-/usr/local/casata}"

get_log_file() {
    if [ "${EUID:-$(id -u)}" -eq 0 ]; then
        echo "/usr/local/casata/HISTORY.log"
    else
        echo "$HOME/.local/share/casata/HISTORY.log"
    fi
}

get_no_log_flag() {
    if [ "${EUID:-$(id -u)}" -eq 0 ]; then
        echo "/usr/local/casata/NO_LOG"
    else
        echo "$HOME/.local/share/casata/NO_LOG"
    fi
}

# Devuelve una descripción del usuario actual
get_user_description() {
    if [ "${EUID:-$(id -u)}" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
        echo "root (ejecutado por ${SUDO_USER})"
    elif [ -n "${SUDO_USER:-}" ]; then
        echo "${SUDO_USER}"
    else
        echo "${USER:-desconocido}"
    fi
}

# Escribe una entrada al principio del archivo (más reciente arriba)
write_log_line() {
    local line="$1"
    local log_file no_log_flag
    log_file="$(get_log_file)"
    no_log_flag="$(get_no_log_flag)"

    [ -f "$no_log_flag" ] && return 0
    mkdir -p "$(dirname "$log_file")" 2>/dev/null || true

    if [ -f "$log_file" ]; then
        local tmp
        tmp="$(mktemp)"
        echo "$line" > "$tmp"
        cat "$log_file" >> "$tmp" 2>/dev/null
        mv "$tmp" "$log_file"
    else
        echo "$line" > "$log_file"
    fi
    chmod 644 "$log_file" 2>/dev/null
}

# Evento genérico con etiqueta
log_event() {
    local type="$1"; shift
    local message="$*"
    local user_desc timestamp
    user_desc="$(get_user_description)"
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    write_log_line "[$timestamp] 👤 $user_desc [$type] $message"
}

# Inicio de comando
log_command_start() {
    local cmd="$*"
    local user_desc timestamp
    user_desc="$(get_user_description)"
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    write_log_line "[$timestamp] 🚀 $user_desc ejecutó: $cmd"
}

# Fin de comando con resultado
log_command_end() {
    local exit_code="$1"; shift
    local cmd="$*"
    local user_desc timestamp
    user_desc="$(get_user_description)"
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"

    if [ "$exit_code" -eq 0 ]; then
        write_log_line "[$timestamp] ✅ $user_desc completó con éxito: $cmd"
    else
        write_log_line "[$timestamp] ❌ $user_desc tuvo un fallo (código $exit_code) en: $cmd"
    fi
}

# Salida combinada de un comando
log_output() {
    local cmd="$1"; local output="$2"
    [ -z "$output" ] && return 0
    local timestamp user_desc
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    user_desc="$(get_user_description)"
    write_log_line "[$timestamp] 📤 Salida de '$cmd' ($user_desc):"
    # Se añade la salida indentada
    local log_file
    log_file="$(get_log_file)"
    if [ -f "$log_file" ]; then
        local tmp
        tmp="$(mktemp)"
        {
            echo "$output" | sed -r 's/\x1B\[[0-9;]*[mK]//g' | sed 's/^/    /'
            cat "$log_file"
        } > "$tmp"
        mv "$tmp" "$log_file"
    fi
}

# Errores de un comando (se usa la misma salida combinada)
log_error_output() {
    local cmd="$1"; local output="$2"
    [ -z "$output" ] && return 0
    local timestamp user_desc
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    user_desc="$(get_user_description)"
    write_log_line "[$timestamp] ⚠️ Errores de '$cmd' ($user_desc):"
    local log_file
    log_file="$(get_log_file)"
    if [ -f "$log_file" ]; then
        local tmp
        tmp="$(mktemp)"
        {
            echo "$output" | sed -r 's/\x1B\[[0-9;]*[mK]//g' | sed 's/^/    /'
            cat "$log_file"
        } > "$tmp"
        mv "$tmp" "$log_file"
    fi
}

log_dependencies_system() {
    local manager="$1"; shift
    local packages="$*"
    log_event "DEPENDENCIAS_SISTEMA" "Paquetes instalados con $manager: $packages"
}

log_dependencies_pip() {
    log_event "DEPENDENCIAS_PIP" "Paquetes Python instalados: $*"
}

log_dependencies_casata() {
    log_event "DEPENDENCIAS_CASATA" "Dependencia Casata instalada: $*"
}

log_download() {
    local url="$1"; local dest="$2"; local status="$3"
    if [ "$status" = "OK" ]; then
        log_event "DESCARGA" "Descargado correctamente $url → $dest"
    else
        log_event "DESCARGA" "Error al descargar $url → $dest"
    fi
}

log_sha256() {
    local file="$1"; local status="$2"
    if [ "$status" = "OK" ]; then
        log_event "SHA256" "Suma de verificación correcta para $file"
    else
        log_event "SHA256" "Error de suma de verificación para $file"
    fi
}

log_symlink_created() {
    local name="$1"; local target="$2"; local dest="$3"
    log_event "ENLACE_CREADO" "Enlace '$name' → $target (en $dest)"
}

log_symlink_removed() {
    local name="$1"; local target="$2"
    log_event "ENLACE_ELIMINADO" "Enlace eliminado '$name' (apuntaba a $target)"
}

log_package_installed() {
    local pkg="$1"; local version="$2"; local result="$3"
    if [ "$result" = "SUCCESS" ]; then
        log_event "PAQUETE_INSTALADO" "Paquete $pkg versión $version instalado correctamente"
    else
        log_event "PAQUETE_INSTALADO" "Error al instalar el paquete $pkg versión $version"
    fi
}

log_package_removed() {
    local pkg="$1"; local scope="$2"; local result="$3"
    if [ "$result" = "SUCCESS" ]; then
        log_event "PAQUETE_ELIMINADO" "Paquete $pkg ($scope) desinstalado correctamente"
    else
        log_event "PAQUETE_ELIMINADO" "Error al desinstalar el paquete $pkg ($scope)"
    fi
}

log_repo_updated() {
    local repo="$1"; local status="$2"
    if [ "$status" = "OK" ]; then
        log_event "REPO_ACTUALIZADO" "Repositorio '$repo' actualizado correctamente"
    else
        log_event "REPO_ACTUALIZADO" "Error al actualizar el repositorio '$repo'"
    fi
}

log_repo_added() {
    local repo="$1"; local status="$2"
    if [ "$status" = "OK" ]; then
        log_event "REPO_AGREGADO" "Repositorio '$repo' añadido correctamente"
    else
        log_event "REPO_AGREGADO" "Error al añadir el repositorio '$repo'"
    fi
}

log_cleanup_path() {
    local path="$1"
    log_event "LIMPIEZA" "Elemento eliminado durante la limpieza: $path"
}

log_external_file() {
    local url="$1"; local dest="$2"
    log_event "ARCHIVO_EXTERNO" "Descargado archivo externo $url → $dest"
}
