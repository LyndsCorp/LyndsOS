#!/bin/bash
# /usr/local/casata/modules/show.sh
# Muestra información técnica de las aplicaciones instaladas globalmente
# incluyendo tamaños, metadatos y metarepo de origen.
# Ahora también permite leer README y LICENCIAS.

shopt -s nullglob

CASATA_ROOT="/usr/local/casata"
SYS_DIR="$CASATA_ROOT/apps"
DATA_DIR="$CASATA_ROOT/data"
METAREPOS_DIR="$CASATA_ROOT/repos/metarepos"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ------------------------------------------------------------
# Convierte bytes a formato legible (KiB, MiB, GiB)
# ------------------------------------------------------------
human_readable() {
    local bytes="$1"
    if [ -z "$bytes" ] || [ "$bytes" -eq 0 ]; then
        echo "0 bytes"
        return
    fi
    local units=("bytes" "KiB" "MiB" "GiB" "TiB")
    local i=0
    local size=$bytes
    while [ "$size" -gt 1024 ] && [ $i -lt 4 ]; do
        size=$((size / 1024))
        i=$((i + 1))
    done
    echo "$size ${units[$i]}"
}

# ------------------------------------------------------------
# Busca en qué metarepo está definido el paquete (solo uno)
# Devuelve el nombre del metarepo o "desconocido"
# ------------------------------------------------------------
find_metarepo_for_pkg() {
    local pkg_name="$1"
    local found=""
    if [ -d "$METAREPOS_DIR" ]; then
        for meta_file in "$METAREPOS_DIR"/*.json; do
            [ -f "$meta_file" ] || continue
            if jq -e --arg pkg "$pkg_name" 'has($pkg)' "$meta_file" >/dev/null 2>&1; then
                local repo_name=$(jq -r '.name // ""' "$meta_file" 2>/dev/null)
                if [ -z "$repo_name" ]; then
                    repo_name=$(basename "$meta_file" .json)
                fi
                found="$repo_name"
                break
            fi
        done
    fi
    if [ -z "$found" ]; then
        echo "desconocido"
    else
        echo "$found"
    fi
}

# Función para mostrar detalles de una app
show_app_info() {
    local app_dir="$1"
    local pkg_name=$(basename "$app_dir")

    echo -e "${BLUE}────────────────────────────────────────────${NC}"
    echo -e "${GREEN}📦 $pkg_name${NC}"
    echo -e "  ${YELLOW}Ruta:${NC} $app_dir"

    # --- Tamaño lógico (suma de bytes) ---
    if [ -d "$app_dir" ]; then
        size_logical_bytes=$(du -sb --apparent-size "$app_dir" 2>/dev/null | cut -f1)
        if [ -n "$size_logical_bytes" ] && [ "$size_logical_bytes" -gt 0 ]; then
            size_logical_human=$(human_readable "$size_logical_bytes")
            echo -e "  ${YELLOW}Tamaño lógico:${NC} $size_logical_bytes bytes ($size_logical_human)"
        else
            echo -e "  ${YELLOW}Tamaño lógico:${NC} (no disponible)"
        fi

        # --- Tamaño en disco ---
        size_disk_human=$(du -sh "$app_dir" 2>/dev/null | cut -f1)
        if [ -n "$size_disk_human" ]; then
            echo -e "  ${YELLOW}Tamaño en disco:${NC} $size_disk_human"
        else
            echo -e "  ${YELLOW}Tamaño en disco:${NC} (no disponible)"
        fi
    else
        echo -e "  ${YELLOW}Tamaño lógico:${NC} (directorio no accesible)"
        echo -e "  ${YELLOW}Tamaño en disco:${NC} (directorio no accesible)"
    fi

    # --- Tamaño según metadatos ---
    local meta_file="$DATA_DIR/${pkg_name}.json"
    if [ -f "$meta_file" ]; then
        size_meta=$(jq -r '.size // ""' "$meta_file" 2>/dev/null)
        if [ -n "$size_meta" ]; then
            echo -e "  ${YELLOW}Tamaño según metadatos:${NC} $size_meta"
        else
            echo -e "  ${YELLOW}Tamaño según metadatos:${NC} (no especificado)"
        fi
    else
        echo -e "  ${YELLOW}Tamaño según metadatos:${NC} (no hay metadatos)"
    fi

    # Versión
    if [ -f "$app_dir/VERSION" ]; then
        version=$(cat "$app_dir/VERSION")
        echo -e "  ${YELLOW}Versión:${NC} $version"
    else
        echo -e "  ${YELLOW}Versión:${NC} (desconocida)"
    fi

    # Metarepo de origen
    local metarepo=$(find_metarepo_for_pkg "$pkg_name")
    echo -e "  ${YELLOW}Metarepo:${NC} $metarepo"

    # Enlaces simbólicos desde GUIDE.json
    local guide_file="$app_dir/GUIDE.json"
    if [ -f "$guide_file" ]; then
        echo -e "  ${YELLOW}Enlaces simbólicos:${NC}"
        jq -c '.links[]' "$guide_file" 2>/dev/null | while read -r item; do
            dest=$(echo "$item" | jq -r '.dest // ""')
            name=$(echo "$item" | jq -r '.name // ""')
            if [ -n "$dest" ] && [ -n "$name" ]; then
                dest_expanded="${dest/#\~/$HOME}"
                dest_expanded="${dest_expanded//\$HOME/$HOME}"
                echo -e "    → $name ${GREEN}->${NC} $dest_expanded"
            fi
        done
    else
        echo -e "  ${YELLOW}Enlaces simbólicos:${NC} (no definidos)"
    fi

    # ---- Mostrar metadatos del repositorio si existen ----
    if [ -f "$meta_file" ]; then
        echo -e "  ${YELLOW}Metadatos del repositorio:${NC}"
        local project=$(jq -r '.project // ""' "$meta_file" 2>/dev/null)
        local is_open=$(jq -r '.is_open_source // ""' "$meta_file" 2>/dev/null)
        local source_code=$(jq -r '.source_code // ""' "$meta_file" 2>/dev/null)
        local license=$(jq -r '.license // ""' "$meta_file" 2>/dev/null)
        local origin=$(jq -r '.origin // ""' "$meta_file" 2>/dev/null)
        local developer=$(jq -r '.developer // ""' "$meta_file" 2>/dev/null)
        local copyright_title=$(jq -r '.copyright_title // ""' "$meta_file" 2>/dev/null)
        local copyright_year=$(jq -r '.copyright_year // ""' "$meta_file" 2>/dev/null)

        # Proyecto
        [ -n "$project" ] && echo -e "    Proyecto: $project" || echo -e "    Proyecto: ${YELLOW}(no especificado)${NC}"

        [ -n "$license" ] && echo -e "    Licencia: $license" || echo -e "    Licencia: ${YELLOW}(no especificada)${NC}"

        # Código fuente: si is_open es false o 0 -> "No es de código abierto"
        # si is_open es true o 1 -> mostrar source_code o "no especificado"
        # si no está definido -> mostrar source_code si existe, sino "no especificado"
        if [ "$is_open" = "false" ] || [ "$is_open" = "0" ]; then
            echo -e "    Código fuente: ${RED}No es de código abierto${NC}"
        else
            if [ -n "$source_code" ]; then
                echo -e "    Código fuente: $source_code"
            else
                echo -e "    Código fuente: ${YELLOW}(no especificado)${NC}"
            fi
        fi

        [ -n "$origin" ] && echo -e "    Origen: $origin" || echo -e "    Origen: ${YELLOW}(no especificado)${NC}"
        [ -n "$developer" ] && echo -e "    Desarrollador: $developer" || echo -e "    Desarrollador: ${YELLOW}(no especificado)${NC}"

        if [ -n "$copyright_title" ] && [ -n "$copyright_year" ]; then
            echo -e "    Copyright: $copyright_year $copyright_title"
        elif [ -n "$copyright_title" ]; then
            echo -e "    Copyright: $copyright_title (año no especificado)"
        elif [ -n "$copyright_year" ]; then
            echo -e "    Copyright: $copyright_year (titular no especificado)"
        else
            echo -e "    Copyright: ${YELLOW}(no especificado)${NC}"
        fi
    fi

    echo ""
}

# ------------------------------------------------------------
# Parseo de argumentos (permite flag antes o después del nombre)
# ------------------------------------------------------------
FLAG=""
PKG_NAME=""
for arg in "$@"; do
    case "$arg" in
        -r|--readme)
            if [ -n "$FLAG" ]; then
                echo -e "${RED}Error: Solo se permite un flag.${NC}" >&2
                exit 1
            fi
            FLAG="readme"
            ;;
        -l|--license-short)
            if [ -n "$FLAG" ]; then
                echo -e "${RED}Error: Solo se permite un flag.${NC}" >&2
                exit 1
            fi
            FLAG="license-short"
            ;;
        -L|--license-full)
            if [ -n "$FLAG" ]; then
                echo -e "${RED}Error: Solo se permite un flag.${NC}" >&2
                exit 1
            fi
            FLAG="license-full"
            ;;
        -*)
            echo -e "${RED}Error: Opción desconocida: $arg${NC}" >&2
            exit 1
            ;;
        *)
            if [ -n "$PKG_NAME" ]; then
                echo -e "${RED}Error: Demasiados argumentos.${NC}" >&2
                exit 1
            fi
            PKG_NAME="$arg"
            ;;
    esac
done

# ------------------------------------------------------------
# Manejo de flags: mostrar archivos solicitados
# ------------------------------------------------------------
if [ -n "$FLAG" ]; then
    if [ -z "$PKG_NAME" ]; then
        echo -e "${RED}Error: Se requiere el nombre del paquete.${NC}" >&2
        exit 1
    fi
    APP_DIR="$SYS_DIR/$PKG_NAME"
    if [ ! -d "$APP_DIR" ]; then
        echo -e "${RED}Error: La aplicación '$PKG_NAME' no está instalada globalmente.${NC}"
        exit 1
    fi

    case "$FLAG" in
        "readme")
            if [ -f "$APP_DIR/README.md" ]; then
                echo -e "${YELLOW}=== README de $PKG_NAME ===${NC}"
                cat "$APP_DIR/README.md"
                exit 0
            else
                echo -e "${RED}No se encontró el archivo README.md en $PKG_NAME.${NC}"
                exit 1
            fi
            ;;
        "license-short")
            if [ -f "$APP_DIR/LICENSE" ]; then
                echo -e "${YELLOW}=== LICENCIA (primera línea, -L para entera) de $PKG_NAME ===${NC}"
                head -n 1 "$APP_DIR/LICENSE"
                exit 0
            else
                echo -e "${RED}No se encontró el archivo LICENSE en $PKG_NAME.${NC}"
                exit 1
            fi
            ;;
        "license-full")
            if [ -f "$APP_DIR/LICENSE" ]; then
                echo -e "${YELLOW}=== LICENCIA completa de $PKG_NAME ===${NC}"
                cat "$APP_DIR/LICENSE"
                exit 0
            else
                echo -e "${RED}No se encontró el archivo LICENSE en $PKG_NAME.${NC}"
                exit 1
            fi
            ;;
    esac
fi

# ------------------------------------------------------------
# Sin flags: comportamiento original
# ------------------------------------------------------------
# Si se pasa un argumento (nombre de paquete), mostrar solo esa app
if [ -n "$PKG_NAME" ]; then
    app_dir="$SYS_DIR/$PKG_NAME"
    if [ -d "$app_dir" ]; then
        show_app_info "$app_dir"
    else
        echo -e "${RED}Error: La aplicación '$PKG_NAME' no está instalada globalmente.${NC}"
        exit 1
    fi
    exit 0
fi

# Sin argumentos: mostrar todas las apps globales
if [ ! -d "$SYS_DIR" ] || [ -z "$(ls -A "$SYS_DIR" 2>/dev/null)" ]; then
    echo -e "${YELLOW}No hay aplicaciones instaladas globalmente.${NC}"
    exit 0
fi

echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Aplicaciones instaladas (sistema global)${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"

count=0
for app_dir in "$SYS_DIR"/*; do
    [ -d "$app_dir" ] || continue
    show_app_info "$app_dir"
    count=$((count + 1))
done

echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Total: $count aplicación(es) instalada(s).${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
