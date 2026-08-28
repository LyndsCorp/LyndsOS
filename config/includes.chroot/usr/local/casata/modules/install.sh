#!/bin/bash

# /usr/local/casata/modules/install.sh
# Copyright (C) 2026, GPL v3+, Lynds Corp., Aros Legendarios, David Baña Szymaniak
# Script de instalar aplicaciones en Casata 1.2.2

# NOVEDADES DE COMPATIBILIDAD CON SEGURIDAD (1.2.1 → 1.2.2):
#   - Soporte para paquetes autorizados a modificar el sistema mediante GUIDE.sh.
#     Lista blanca en /usr/local/casata/repos/singrepos/PRIORITY.

shopt -s nullglob
set -euo pipefail

GLOBAL_ROOT="/usr/local/casata"
DATA_DIR="$GLOBAL_ROOT/data"
SINGREPOS_PRIORITY="$GLOBAL_ROOT/repos/singrepos/PRIORITY"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

APT_UPDATE_STATUS=0
TEMP_DIR=""
EXTRACT_DIR=""

# ------------------------------------------------------------
# Directorios protegidos donde NUNCA se puede crear un enlace
# ------------------------------------------------------------
PROTECTED_DIRS=(
    "/usr/local/casata"
    "/home"
    "/boot"
    "/root"
    "/dev"
    "/sys"
)

PROTECTED_FILES=(
    # --- Instaladores ---
    "/usr/bin/casata"
    "/usr/bin/apt"
    "/usr/bin/pacman"
    "/usr/bin/dnf"
    "/usr/bin/wget"
    "/usr/bin/curl"

    # --- Dependencias de Casata ---
    "/usr/bin/jq"
    "/usr/bin/tar"
    "/usr/bin/unzip"
    "/usr/bin/zip"

    # --- GNU coreutils ---
    "/usr/bin/basename"
    "/usr/bin/cat"
    "/usr/bin/chgrp"
    "/usr/bin/chmod"
    "/usr/bin/chown"
    "/usr/bin/cksum"
    "/usr/bin/comm"
    "/usr/bin/cp"
    "/usr/bin/csplit"
    "/usr/bin/cut"
    "/usr/bin/date"
    "/usr/bin/dd"
    "/usr/bin/df"
    "/usr/bin/dir"
    "/usr/bin/dircolors"
    "/usr/bin/dirname"
    "/usr/bin/du"
    "/usr/bin/echo"
    "/usr/bin/env"
    "/usr/bin/expand"
    "/usr/bin/expr"
    "/usr/bin/factor"
    "/usr/bin/false"
    "/usr/bin/fmt"
    "/usr/bin/fold"
    "/usr/bin/groups"
    "/usr/bin/head"
    "/usr/bin/hostid"
    "/usr/bin/id"
    "/usr/bin/install"
    "/usr/bin/join"
    "/usr/bin/kill"
    "/usr/bin/link"
    "/usr/bin/ln"
    "/usr/bin/logname"
    "/usr/bin/ls"
    "/usr/bin/md5sum"
    "/usr/bin/mkdir"
    "/usr/bin/mkfifo"
    "/usr/bin/mknod"
    "/usr/bin/mktemp"
    "/usr/bin/mv"
    "/usr/bin/nice"
    "/usr/bin/nl"
    "/usr/bin/nohup"
    "/usr/bin/nproc"
    "/usr/bin/numfmt"
    "/usr/bin/od"
    "/usr/bin/paste"
    "/usr/bin/pathchk"
    "/usr/bin/pinky"
    "/usr/bin/pr"
    "/usr/bin/printenv"
    "/usr/bin/printf"
    "/usr/bin/ptx"
    "/usr/bin/pwd"
    "/usr/bin/readlink"
    "/usr/bin/realpath"
    "/usr/bin/rm"
    "/usr/bin/rmdir"
    "/usr/bin/runcon"
    "/usr/bin/seq"
    "/usr/bin/sha1sum"
    "/usr/bin/sha224sum"
    "/usr/bin/sha256sum"
    "/usr/bin/sha384sum"
    "/usr/bin/sha512sum"
    "/usr/bin/shred"
    "/usr/bin/shuf"
    "/usr/bin/sleep"
    "/usr/bin/sort"
    "/usr/bin/split"
    "/usr/bin/stat"
    "/usr/bin/stdbuf"
    "/usr/bin/stty"
    "/usr/bin/sum"
    "/usr/bin/tac"
    "/usr/bin/tail"
    "/usr/bin/tee"
    "/usr/bin/test"
    "/usr/bin/timeout"
    "/usr/bin/touch"
    "/usr/bin/tr"
    "/usr/bin/true"
    "/usr/bin/tsort"
    "/usr/bin/tty"
    "/usr/bin/uname"
    "/usr/bin/unexpand"
    "/usr/bin/uniq"
    "/usr/bin/unlink"
    "/usr/bin/users"
    "/usr/bin/vdir"
    "/usr/bin/wc"
    "/usr/bin/who"
    "/usr/bin/whoami"
    "/usr/bin/yes"
    "/usr/bin/["

    # --- util-linux ---
    "/usr/bin/addpart"
    "/usr/bin/agetty"
    "/usr/bin/blkdiscard"
    "/usr/bin/blkid"
    "/usr/bin/blockdev"
    "/usr/bin/cal"
    "/usr/bin/chcpu"
    "/usr/bin/chmem"
    "/usr/bin/choom"
    "/usr/bin/chrt"
    "/usr/bin/col"
    "/usr/bin/colcrt"
    "/usr/bin/colrm"
    "/usr/bin/column"
    "/usr/bin/ctrlaltdel"
    "/usr/bin/dmesg"
    "/usr/bin/eject"
    "/usr/bin/fallocate"
    "/usr/bin/fincore"
    "/usr/bin/findmnt"
    "/usr/bin/flock"
    "/usr/bin/getopt"
    "/usr/bin/hexdump"
    "/usr/bin/hwclock"
    "/usr/bin/ionice"
    "/usr/bin/ipcmk"
    "/usr/bin/ipcrm"
    "/usr/bin/ipcs"
    "/usr/bin/isosize"
    "/usr/bin/killall"
    "/usr/bin/last"
    "/usr/bin/lastb"
    "/usr/bin/ldattach"
    "/usr/bin/logger"
    "/usr/bin/login"
    "/usr/bin/look"
    "/usr/bin/lsblk"
    "/usr/bin/lscpu"
    "/usr/bin/lsipc"
    "/usr/bin/lslocks"
    "/usr/bin/lslogins"
    "/usr/bin/lsns"
    "/usr/bin/mcookie"
    "/usr/bin/mesg"
    "/usr/bin/mkfs"
    "/usr/bin/mkswap"
    "/usr/bin/mount"
    "/usr/bin/mountpoint"
    "/usr/bin/namei"
    "/usr/bin/nsenter"
    "/usr/bin/pivot_root"
    "/usr/bin/partx"
    "/usr/bin/prlimit"
    "/usr/bin/raw"
    "/usr/bin/readprofile"
    "/usr/bin/rename"
    "/usr/bin/renice"
    "/usr/bin/rev"
    "/usr/bin/rfkill"
    "/usr/bin/runuser"
    "/usr/bin/script"
    "/usr/bin/scriptreplay"
    "/usr/bin/setarch"
    "/usr/bin/setpriv"
    "/usr/bin/setterm"
    "/usr/bin/su"
    "/usr/bin/swaplabel"
    "/usr/bin/swapoff"
    "/usr/bin/swapon"
    "/usr/bin/taskset"
    "/usr/bin/ul"
    "/usr/bin/unshare"
    "/usr/bin/utmpdump"
    "/usr/bin/uclampset"
    "/usr/bin/wall"
    "/usr/bin/wdctl"
    "/usr/bin/whereis"
    "/usr/bin/wipefs"
    "/usr/bin/write"
    "/usr/bin/zramctl"
)

# ------------------------------------------------------------
# Función auxiliar: resolver ruta canónica (con fallback)
# ------------------------------------------------------------
canonical_path() {
    local path="$1"
    if command -v realpath &>/dev/null; then
        realpath -m "$path" 2>/dev/null || echo "$path"
    else
        echo "$path"
    fi
}

cleanup() {
    if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
    if [ -n "$EXTRACT_DIR" ] && [ -d "$EXTRACT_DIR" ]; then
        rm -rf "$EXTRACT_DIR"
    fi
}
trap cleanup EXIT

install_system_deps() {
    local deps="$1"
    echo -e "${YELLOW}Intentando instalar dependencias: $deps${NC}"
    if ! command -v apt &>/dev/null; then
        echo -e "${RED}Error: APT no está disponible.${NC}"
        return 1
    fi
    if [ $APT_UPDATE_STATUS -eq 0 ]; then
        echo -e "${YELLOW}Ejecutando apt update...${NC}"
        if apt update; then
            APT_UPDATE_STATUS=1
        else
            APT_UPDATE_STATUS=2
            echo -e "${RED}ERROR DEL CLIENTE: apt update falló. No se instalarán dependencias del sistema.${NC}"
            return 1
        fi
    elif [ $APT_UPDATE_STATUS -eq 2 ]; then
        echo -e "${RED}No se intenta instalar dependencias porque apt update falló.${NC}"
        return 1
    fi
    if apt install -y $deps; then
        return 0
    else
        echo -e "${RED}ERROR DE CLIENTE: No se pudieron instalar las dependencias automáticamente con APT. Por favor, instálalas manualmente: $deps${NC}"
        return 1
    fi
}

install_pip_deps() {
    local pkgs="$1"
    local venv_path="/usr/local/casata/python-venv"
    local lock_file="$venv_path/.install.lock"
    if ! ls "$venv_path/bin/python" >/dev/null 2>&1; then
        echo -e "${YELLOW}Creando entorno virtual compartido en $venv_path...${NC}"
        if command -v python3 &>/dev/null; then
            python3 -m venv "$venv_path" || { echo -e "${RED}Error al crear venv.${NC}"; return 1; }
        else
            echo -e "${RED}Error: python3 no encontrado. No se pueden instalar dependencias pip.${NC}"
            return 1
        fi
    fi
    touch "$lock_file" 2>/dev/null || { echo -e "${RED}Error: No se puede crear lock file en $lock_file.${NC}"; return 1; }
    local pip_pkgs=()
    while IFS= read -r pkg; do
        [[ -n "$pkg" ]] && pip_pkgs+=("$pkg")
    done <<< "$pkgs"
    if [ ${#pip_pkgs[@]} -eq 0 ]; then
        return 0
    fi
    echo -e "${YELLOW}Instalando dependencias Python: ${pip_pkgs[*]}${NC}"
    flock --exclusive "$lock_file" "$venv_path/bin/pip" install "${pip_pkgs[@]}" || {
        echo -e "${RED}Error al instalar dependencias pip.${NC}"
        return 1
    }
    return 0
}

force_remove() {
    local app_dir="$1"
    local guide_target="$2"
    echo -e "${YELLOW}Eliminando instalación anterior/revertiendo enlaces...${NC}"
    if [ -f "$app_dir/$guide_target" ]; then
        jq -c '.links[]' "$app_dir/$guide_target" 2>/dev/null | while read -r item; do
            DEST=$(echo "$item" | jq -r '.dest')
            LINK_NAME=$(echo "$item" | jq -r '.name')
            FILE=$(echo "$item" | jq -r '.file')
            [ "$DEST" == "null" ] || [ "$LINK_NAME" == "null" ] || [ "$FILE" == "null" ] && continue
            DEST="${DEST/#\~/$HOME}"
            DEST="${DEST//\$HOME/$HOME}"
            TARGET_LINK="$DEST/$LINK_NAME"
            if [ -L "$TARGET_LINK" ] && [ "$(readlink "$TARGET_LINK")" == "$app_dir/$FILE" ]; then
                rm -f "$TARGET_LINK"
                echo -e "   [-] Enlace eliminado: $LINK_NAME"
            fi
        done
    fi
    rm -rf "$app_dir"
}

ask_overwrite() {
    local target="$1"
    local app_name="$2"
    local auto_yes="$3"
    if [ "$auto_yes" -eq 1 ]; then
        echo -e "${YELLOW}Usando -y: Sobrescribiendo '$target' automáticamente.${NC}"
        rm -rf "$target"
        return 0
    fi
    echo -e "${YELLOW}Advertencia: '$target' ya existe y no es un enlace a $app_name.${NC}"
    read -p "¿Sobrescribirlo? (perderás el archivo original) [s/N/a (abortar)]: " resp < /dev/tty
    if [[ "$resp" =~ ^[sSyY] ]]; then
        rm -rf "$target"
        echo -e "${GREEN}Archivo eliminado. Continuando...${NC}"
        return 0
    elif [[ "$resp" =~ ^[aA] ]]; then
        echo -e "${RED}Instalación abortada por el usuario.${NC}"
        exit 1
    else
        echo -e "${YELLOW}Omitiendo enlace. No se sobrescribirá.${NC}"
        return 1
    fi
}

install_one() {
    local PKG_NAME="$1"
    local AUTO_YES="$2"
    local DOWNLOAD_ONLY="$3"

    [ "$EUID" -ne 0 ] && { echo -e "${RED}Instalación global requiere root.${NC}"; return 1; }
    APPS_DIR="$GLOBAL_ROOT/apps"
    GUIDE_TARGET="GUIDE.json"

    mkdir -p "$APPS_DIR"
    APP_DIR="$APPS_DIR/${PKG_NAME}"

    SINGREPO_FILE="$GLOBAL_ROOT/repos/singrepos/${PKG_NAME}.json"
    if [ ! -f "$SINGREPO_FILE" ]; then
        echo -e "${RED}Error: El paquete '$PKG_NAME' no está indexado.${NC}"
        return 1
    fi

    DOWNLOAD_URL=$(jq -r '.download_url // empty' "$SINGREPO_FILE")
    if [ -z "$DOWNLOAD_URL" ]; then
        echo -e "${RED}Error: No hay download_url en el singrepo.${NC}"
        return 1
    fi

    PKG_FILE="$DATA_DIR/${PKG_NAME}.json"
    if [ ! -f "$PKG_FILE" ]; then
        echo -e "${RED}Error: Base de datos local no encontrada. Ejecute 'casata update' primero.${NC}"
        return 1
    fi

    REPO_VERSION=$(jq -r '.version // "0.0.0"' "$PKG_FILE")
    APT_DEPS=$(jq -r '.apt[]? // empty' "$PKG_FILE")
    PIP_DEPS=$(jq -r '.pip[]? // empty' "$PKG_FILE")

    INSTALLED_VERSION=""
    NEED_UPDATE=0
    if [ -d "$APP_DIR" ]; then
        if [ -f "$APP_DIR/VERSION" ]; then
            INSTALLED_VERSION=$(cat "$APP_DIR/VERSION")
            echo -e "${YELLOW}Versión instalada: $INSTALLED_VERSION${NC}"
            echo -e "${YELLOW}Versión en repositorio: $REPO_VERSION${NC}"
            OLDER=$(printf '%s\n' "$INSTALLED_VERSION" "$REPO_VERSION" | sort -V | head -n1)
            if [ "$OLDER" = "$INSTALLED_VERSION" ] && [ "$INSTALLED_VERSION" != "$REPO_VERSION" ]; then
                NEED_UPDATE=1
                echo -e "${GREEN}Hay una actualización disponible.${NC}"
            elif [ "$INSTALLED_VERSION" = "$REPO_VERSION" ]; then
                echo -e "${GREEN}Ya tienes la última versión.${NC}"
                if [ $AUTO_YES -eq 0 ]; then
                    read -p "¿Reinstalar igualmente? [s/N] " rein < /dev/tty
                    [[ ! "$rein" =~ ^[sSyY] ]] && return 0
                    NEED_UPDATE=2
                else
                    echo -e "${YELLOW}Usando -y: se reinstalará.${NC}"
                    NEED_UPDATE=2
                fi
            else
                echo -e "${GREEN}La versión instalada es más reciente que la del repositorio. No se hará nada.${NC}"
                return 0
            fi
        else
            echo -e "${YELLOW}Paquete instalado pero sin archivo VERSION. Se reinstalará.${NC}"
            NEED_UPDATE=2
        fi
    fi

    if [ -n "$APT_DEPS" ]; then
        echo -e "\n${YELLOW}Dependencias del sistema para $PKG_NAME:${NC}"
        echo "$APT_DEPS" | sed 's/^/  • /'
        if [ $AUTO_YES -eq 0 ]; then
            read -p "¿Instalar dependencias del sistema? [S/n] " resp < /dev/tty
            if [[ "$resp" =~ ^[Nn] ]]; then
                echo -e "${YELLOW}Se omitió la instalación de dependencias del sistema.${NC}"
            else
                install_system_deps "$(echo "$APT_DEPS" | tr '\n' ' ')" || return 1
            fi
        else
            install_system_deps "$(echo "$APT_DEPS" | tr '\n' ' ')" || return 1
        fi
    fi

    if [ -n "$PIP_DEPS" ]; then
        echo -e "\n${YELLOW}Dependencias Python para $PKG_NAME:${NC}"
        echo "$PIP_DEPS" | sed 's/^/  • /'
        if [ $AUTO_YES -eq 0 ]; then
            read -p "¿Instalar dependencias Python con pip? [S/n] " resp < /dev/tty
            if [[ "$resp" =~ ^[Nn] ]]; then
                echo -e "${YELLOW}Se omitió la instalación de dependencias pip.${NC}"
            else
                install_pip_deps "$PIP_DEPS" || return 1
            fi
        else
            install_pip_deps "$PIP_DEPS" || return 1
        fi
    fi

    if [ $NEED_UPDATE -eq 1 ] || [ $NEED_UPDATE -eq 2 ]; then
        echo -e "${YELLOW}Preparando actualización/reinstalación...${NC}"
        force_remove "$APP_DIR" "$GUIDE_TARGET"
    fi

    mkdir -p "$APP_DIR"
    ARCHIVE_NAME=$(basename "$DOWNLOAD_URL" | cut -d '?' -f1)
    ARCHIVE_PATH="$APP_DIR/$ARCHIVE_NAME"
    EXTRACT_DIR=$(mktemp -d)

    echo -e "${GREEN}Descargando $PKG_NAME...${NC}"
    wget -q --show-progress -O "$ARCHIVE_PATH" "$DOWNLOAD_URL" || { echo -e "${RED}Error descarga.${NC}"; return 1; }

    case "$ARCHIVE_NAME" in
        *.zip) unzip -q "$ARCHIVE_PATH" -d "$EXTRACT_DIR" ;;
        *.tar.gz|*.tgz) tar -xzf "$ARCHIVE_PATH" -C "$EXTRACT_DIR" ;;
        *.tar.xz) tar -xJf "$ARCHIVE_PATH" -C "$EXTRACT_DIR" ;;
        *) echo -e "${RED}Formato no soportado.${NC}"; return 1 ;;
    esac

    SRC_DIR=$(find "$EXTRACT_DIR" -name "VERSION" -exec dirname {} \; | head -1)
    [ -z "$SRC_DIR" ] && SRC_DIR=$(find "$EXTRACT_DIR" -mindepth 1 -maxdepth 1 -type d | head -1)
    [ -z "$SRC_DIR" ] && SRC_DIR="$EXTRACT_DIR"

    mv "$SRC_DIR"/* "$APP_DIR/" 2>/dev/null || mv "$SRC_DIR"/.??* "$APP_DIR/" 2>/dev/null || true
    rm -rf "$EXTRACT_DIR" "$ARCHIVE_PATH"
    EXTRACT_DIR=""

    [ $DOWNLOAD_ONLY -eq 1 ] && { echo -e "${YELLOW}Descargado en $APP_DIR (sin enlaces).${NC}"; return 0; }

    # ------------------------------------------------
    # Crear enlaces simbólicos CON PROTECCIONES ACTIVAS
    # ------------------------------------------------
    echo -e "${YELLOW}Configurando enlaces...${NC}"
    GUIDE_FILE="$APP_DIR/$GUIDE_TARGET"
    if [ -f "$GUIDE_FILE" ]; then
        while read -r item; do
            FILE=$(echo "$item" | jq -r '.file')
            DEST=$(echo "$item" | jq -r '.dest')
            LINK_NAME=$(echo "$item" | jq -r '.name')
            EXECUTABLE=$(echo "$item" | jq -r '.executable // false')
            [ "$FILE" == "null" ] || [ "$DEST" == "null" ] || [ "$LINK_NAME" == "null" ] && continue

            DEST="${DEST/#\~/$HOME}"
            DEST="${DEST//\$HOME/$HOME}"
            mkdir -p "$DEST"
            TARGET_LINK="$DEST/$LINK_NAME"

            # --- RESOLUCIÓN CANÓNICA ---
            real_target=$(canonical_path "$TARGET_LINK")
            link_dir=$(dirname "$TARGET_LINK")
            real_dir=$(canonical_path "$link_dir")

            # --- VERIFICACIÓN DE DIRECTORIOS PROTEGIDOS ---
            skip=false
            for protected in "${PROTECTED_DIRS[@]}"; do
                real_protected=$(canonical_path "$protected")
                if [ "$real_dir" = "$real_protected" ] || [[ "$real_dir" == "$real_protected/"* ]]; then
                    echo -e "${RED}🚫  Error de seguridad: No se permite crear enlaces en '$link_dir' (directorio protegido). Enlace '$LINK_NAME' omitido.${NC}"
                    skip=true
                    break
                fi
            done
            $skip && continue

            # --- VERIFICACIÓN DE ARCHIVOS PROTEGIDOS ---
            for protected in "${PROTECTED_FILES[@]}"; do
                real_protected=$(canonical_path "$protected")
                if [ "$real_target" = "$real_protected" ]; then
                    echo -e "${RED}🚫  Error de seguridad: No se permite sobrescribir el archivo protegido '$protected'. Enlace '$LINK_NAME' omitido.${NC}"
                    skip=true
                    break
                fi
            done
            $skip && continue

            # --- Gestión de sobrescritura normal ---
            if [ -e "$TARGET_LINK" ] || [ -L "$TARGET_LINK" ]; then
                if [ -L "$TARGET_LINK" ] && [ "$(readlink "$TARGET_LINK")" == "$APP_DIR/$FILE" ]; then
                    echo -e "   ${YELLOW}[!] Enlace existente de la misma app: $LINK_NAME → se reemplazará.${NC}"
                    rm -f "$TARGET_LINK"
                else
                    if ! ask_overwrite "$TARGET_LINK" "$PKG_NAME" "$AUTO_YES"; then
                        continue
                    fi
                fi
            fi

            ln -s "$APP_DIR/$FILE" "$TARGET_LINK"
            if [ "$EXECUTABLE" == "true" ]; then
                chmod +x "$APP_DIR/$FILE"
                echo -e "   [+] Enlazado (ejecutable): $LINK_NAME -> $DEST"
            else
                echo -e "   [+] Enlazado: $LINK_NAME -> $DEST"
            fi
        done < <(jq -c '.links[]' "$GUIDE_FILE")
    else
        echo -e "${YELLOW}Aviso: No se encontró $GUIDE_TARGET. No se crearon enlaces.${NC}"
    fi

    # ------------------------------------------------------------
    # NUEVO (Casata 1.2.2): Ejecución de GUIDE.sh para paquetes autorizados
    # ------------------------------------------------------------
    if [ -f "$SINGREPOS_PRIORITY" ]; then
        if grep -qxF "$PKG_NAME" "$SINGREPOS_PRIORITY" 2>/dev/null; then
            echo -e "\n${YELLOW}Este paquete puede modificar archivos del sistema.${NC}"
            echo -e "\nRepositorio autorizado:"
            echo -e "  ${GREEN}$PKG_NAME${NC}"
            echo ""
            if [ $AUTO_YES -eq 1 ]; then
                echo -e "${YELLOW}Usando -y: se ejecutará GUIDE.sh automáticamente.${NC}"
            else
                read -p "¿Continuar? (S/n): " resp < /dev/tty
                if [[ ! "$resp" =~ ^[SsYy]?$ ]]; then
                    echo -e "${YELLOW}Modificaciones del sistema omitidas. Puede ejecutar manualmente GUIDE.sh desde $APP_DIR.${NC}"
                    echo -e "${GREEN}¡$PKG_NAME instalado correctamente! (versión $REPO_VERSION)${NC}"
                    return 0
                fi
            fi

            GUIDE_SCRIPT="$APP_DIR/GUIDE.sh"
            if [ -f "$GUIDE_SCRIPT" ]; then
                echo -e "${YELLOW}Ejecutando GUIDE.sh...${NC}"
                if bash "$GUIDE_SCRIPT"; then
                    echo -e "${GREEN}✓ GUIDE.sh ejecutado correctamente.${NC}"
                else
                    echo -e "${RED}Error al ejecutar GUIDE.sh. La instalación puede estar incompleta.${NC}"
                    return 1
                fi
            else
                echo -e "${RED}Error: No se encontró GUIDE.sh en el paquete.${NC}"
                return 1
            fi
        fi
    fi

    echo -e "${GREEN}¡$PKG_NAME instalado correctamente! (versión $REPO_VERSION)${NC}"
    return 0
}

# --- INICIO DEL SCRIPT (manejo de argumentos y router) ---
if ! command -v jq &>/dev/null || ! command -v wget &>/dev/null; then
    echo -e "${RED}Error: Se requieren 'jq' y 'wget'.${NC}"
    exit 1
fi

AUTO_YES=0
DOWNLOAD_ONLY=0
PACKAGES=()

for arg in "$@"; do
    case "$arg" in
        -y) AUTO_YES=1 ;;
        -d) DOWNLOAD_ONLY=1 ;;
        -*)
            echo -e "${RED}Opción desconocida: $arg${NC}"
            exit 1
            ;;
        *) PACKAGES+=("$arg") ;;
    esac
done

if [ ${#PACKAGES[@]} -eq 0 ]; then
    echo -e "${RED}Error: Falta el nombre del paquete.${NC}"
    exit 1
fi

if [ ${#PACKAGES[@]} -eq 1 ] && [ "${PACKAGES[0]}" == "casata" ]; then
    echo -e "${GREEN}Redirigiendo a la actualización de Casata...${NC}"
    exec "$GLOBAL_ROOT/modules/install-casata.sh" "$@"
    echo -e "${RED}Error: No se pudo ejecutar el módulo de actualización de Casata.${NC}"
    exit 1
fi

FAILED=()
for PKG in "${PACKAGES[@]}"; do
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}Instalando: $PKG${NC}"
    echo -e "${GREEN}========================================${NC}"
    if install_one "$PKG" "$AUTO_YES" "$DOWNLOAD_ONLY"; then
        echo -e "${GREEN}✔ $PKG instalado correctamente.${NC}"
    else
        echo -e "${RED}✖ Falló la instalación de $PKG.${NC}"
        FAILED+=("$PKG")
    fi
done

echo -e "\n${GREEN}════════════════════════════════════════${NC}"
if [ ${#FAILED[@]} -eq 0 ]; then
    echo -e "${GREEN}✓ Todos los paquetes se instalaron correctamente.${NC}"
else
    echo -e "${RED}✖ Los siguientes paquetes fallaron: ${FAILED[*]}${NC}"
fi
echo -e "${GREEN}════════════════════════════════════════${NC}"

if [ ${#FAILED[@]} -gt 0 ]; then
    exit 1
fi
exit 0
