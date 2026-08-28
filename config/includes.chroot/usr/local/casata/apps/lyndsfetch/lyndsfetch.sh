#!/bin/bash

# Desarrollado por David Baña Szymaniak. Licencia GPL v3, LYNDS Project
# Version 1.2.6

# Ruta del archivo de configuración
CONFIG_FILE="$HOME/.config/LyndsFetch/config.json"

# --- GESTIÓN DE ARGUMENTOS ---
case "$1" in
    -h|--help|--ayuda)
        echo "LyndsFetch - Herramienta de información del sistema"
        echo "Uso: $0 [opciones]"
        echo ""
        echo "Opciones:"
        echo "  --help-color,   --ayuda-color      Muestra los colores disponibles"
        echo "  --help-logo,    --ayuda-logo       Muestra los logos disponibles"
        echo "  --help-modules, --ayuda-modulos    Muestra los módulos disponibles"
        echo "  --edit, --editar, -e               Abre la configuración con nano"
        echo "  --see, --ver                       Muestra el contenido de la configuración"
        echo "  -v, --version                      Muestra la versión de LyndsFetch"
        exit 0
        ;;
    --help-color|--ayuda-color)
        echo "Colores disponibles:"
        echo "  green, blue, red, cyan, magenta, yellow, white"
        exit 0
        ;;
    --help-logo|--ayuda-logo)
        echo "Logos disponibles:"
        echo "  lyndsos, lyndsos-logo, lyndsos-love, lyndsgo, lyndsgo-enter,"
        echo "  debian, debian-love, gnu, gnu-logo, gnu-love, gnu-logo-love,"
        echo "  67, linux, linux-logo, linux-big-logo, ubuntu, kubuntu,"
        echo "  xubuntu, lubuntu, arch, arch-logo, i-use-arch-btw, nyarch,"
        echo "  i-use-nyarch-btw, kali, kali-logo"
        exit 0
        ;;
    --help-modules|--ayuda-modulos)
        echo "Módulos disponibles (se pueden incluir en la configuración):"
        echo "  user, host, hora, date, separator, colours, colors,"
        echo "  os, arch, kernel, uptime, shell, terminal, pkgs,"
        echo "  display-manager, theme, locale, resolution,"
        echo "  cpu, gpu, ram, swap, disk, battery, local-ip, apt-updates,"
        echo "  cpu-temperature, gpu-temperature, session,"
        echo "  os-codename, os-version, os-based, ram-type,"
        echo "  casata-version, casata-int-apps, casata-apps, global-ip"
        exit 0
        ;;
    --edit|--editar|-e)
        nano "$CONFIG_FILE" || ${EDITOR:-vi} "$CONFIG_FILE"
        exit 0
        ;;
    --see|--ver)
        cat "$CONFIG_FILE"
        exit 0
        ;;
    -v|--version)
        cat /usr/local/casata/apps/lyndsfetch/VERSION
        exit 0
        ;;
esac

# --- GENERADOR AUTOMÁTICO DE CONFIGURACIÓN ---
if [ ! -f "$CONFIG_FILE" ]; then
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID=$(echo "$ID" | tr '[:upper:]' '[:lower:]')
        OS_NAME=$(echo "$NAME" | tr '[:upper:]' '[:lower:]')
    else
        OS_ID="unknown"
        OS_NAME="unknown"
    fi

    DEFAULT_LOGO="default"
    DEFAULT_COLOR="green"

    if [[ "$OS_ID" == *"lyndsos"* || "$OS_NAME" == *"lyndsos"* ]]; then
        DEFAULT_LOGO="lyndsos"
        DEFAULT_COLOR="green"
    elif [[ "$OS_ID" == *"lyndsgo"* || "$OS_NAME" == *"lyndsgo"* ]]; then
        DEFAULT_LOGO="lyndsgo-enter"
        DEFAULT_COLOR="magenta"
    elif [[ "$OS_ID" == *"debian"* || "$OS_NAME" == *"debian"* ]]; then
        DEFAULT_LOGO="debian"
        DEFAULT_COLOR="red"
    elif [[ "$OS_ID" == *"ubuntu"* || "$OS_NAME" == *"ubuntu"* ]]; then
        if [[ "$OS_ID" == *"kubuntu"* ]]; then
            DEFAULT_LOGO="kubuntu"
            DEFAULT_COLOR="blue"
        elif [[ "$OS_ID" == *"xubuntu"* ]]; then
            DEFAULT_LOGO="xubuntu"
            DEFAULT_COLOR="blue"
        elif [[ "$OS_ID" == *"lubuntu"* ]]; then
            DEFAULT_LOGO="lubuntu"
            DEFAULT_COLOR="blue"
        else
            DEFAULT_LOGO="ubuntu"
            DEFAULT_COLOR="yellow"
        fi
    elif [[ "$OS_ID" == *"arch"* && "$OS_NAME" == *"arch"* ]]; then
        DEFAULT_LOGO="arch-logo"
        DEFAULT_COLOR="blue"
    elif [[ "$OS_ID" == *"arch"* && "$OS_NAME" == "Nyarch"* ]]; then
        DEFAULT_LOGO="i-use-nyarch-btw"
        DEFAULT_COLOR="blue"
    fi

    mkdir -p "$(dirname "$CONFIG_FILE")"
    cat <<EOF > "$CONFIG_FILE"
{
    "logo": "$DEFAULT_LOGO",
    "color": "$DEFAULT_COLOR",
    "modules": [
        "user",
        "host",
        "separator",
        "os",
        "arch",
        "kernel",
        "uptime",
        "separator",
        "session-type",
        "display-manager",
        "separator",
        "disk",
        "ram"
    ],
    "Modulos existentes para usar (puedes borrar esta parte)": [
        "user", "host", "hora", "date", "separator", "colours", "colors",
        "os", "arch", "kernel", "uptime", "shell", "terminal", "pkgs",
        "display-manager", "theme", "locale", "resolution",
        "cpu", "gpu", "ram", "swap", "disk", "battery", "local-ip", "apt-updates",
        "cpu-temperature", "gpu-temperature", "session-type", "session",
        "os-codename", "os-version", "os-based", "ram-type",
        "casata-version", "casata-int-apps", "casata-apps", "global-ip"
    ]
}
EOF
    echo "Configuración generada con: $DEFAULT_LOGO ($DEFAULT_COLOR)"
fi

# --- FUNCIONES DE LECTURA JSON (jq si está disponible, sino método clásico) ---
get_json_val() {
    local key="$1"
    if command -v jq &>/dev/null; then
        jq -r ".$key // empty" "$CONFIG_FILE" 2>/dev/null
    else
        grep -w "$key" "$CONFIG_FILE" | head -n 1 | cut -d':' -f2 | tr -d '", '
    fi
}

get_modules() {
    if command -v jq &>/dev/null; then
        jq -r '.modules[]' "$CONFIG_FILE" 2>/dev/null
    else
        sed -n '/"modules":\s*\[/,/\]/p' "$CONFIG_FILE" | tr -d '[]", '
    fi
}

LOGO_SELECTION=$(get_json_val "logo")
COLOR_SELECTION=$(get_json_val "color")

# Definición de Colores ANSI (Usando \x1b para máxima compatibilidad)
case "$COLOR_SELECTION" in
    green)   COLOR='\x1b[32m' ;;
    blue)    COLOR='\x1b[34m' ;;
    red)     COLOR='\x1b[31m' ;;
    cyan)    COLOR='\x1b[36m' ;;
    magenta) COLOR='\x1b[35m' ;;
    yellow)  COLOR='\x1b[33m' ;;
    white)   COLOR='\x1b[37m' ;;
    *)       COLOR='\x1b[32m' ;;
esac
NC='\x1b[0m'
BOLD='\x1b[1m'
GREEN='\x1b[32m'
YELLOW='\x1b[33m'
RED='\x1b[31m'

if [ "$LOGO_SELECTION" == "lyndsos-logo" ]; then
    mapfile -t logo << "EOF"
                      &&#BBBBBBB&
           &#BBBBBB###&&#BBGPPP5Y5G&
       GG5YJ????????JJ5PB&   #PYYYJ5
  PPY?????????????????JJ5B #5YYYYY&
  PPJ?????????????????JJJJJJYYYYYYYB
 .YY????????????????????JJYYYYYYYYP#
JJJJ????????????????JJJYYYYYYYY5#.
YYJJJ????????????JJJYYYYYYYYYY555B
BJJJJJJ???????JJYYYYYYYYYYYYYYYYY5
PJJJJJJJ??JJJYYYYYYYYYYYYYYJJJYYYY&
GJJJJJJJJYYYYYYYYYYYYYJJJJJJYYYYY5&
YYYYJJYYYYYYYYYYYYYJJJJJJJJYYYYYYP
 GYYYYYYYYYYYYYYYYYYYYYYYYYYYY555&
 &YYYYYYY55YYYYYY55YYYYYYYYYY555#'
 PYYYYY555555YY55YYYYYYYYY5555P&'
 5YYYGP55P5YY555YYYYYYY55555P#'
 YYJG  BP5YY555YY55555555PB&'
  &PG  #PYYGBGGPPPPPGGB#&
    &&  #PY5B#&'
          BBGGGBB##&
EOF

elif [ "$LOGO_SELECTION" == "lyndsos" ]; then
    mapfile -t logo << "EOF"
  _                     _      ____   _____
 | |                   | |    / __ \ / ____|
 | |    _   _ _ __   __| |___| |  | | (__
 | |   | | | | '_ \ / _` / __| |  | |\___ \
 | |___| |_| | | | | (_| \__ \ |__| |____) |
 |______\__, |_| |_|\__,_|___/\____/|_____/
         __/ |
        |___/
EOF

elif [ "$LOGO_SELECTION" == "lyndsos-love" ]; then
    mapfile -t logo << "EOF"
  _                     _      ____   _____
 | |                   | |    / __ \ / ____|
 | |    _   _ _ __   __| |___| |  | | (__
 | |   | | | | '_ \ / _` / __| |  | |\___ \
 | |___| |_| | | | | (_| \__ \ |__| |____) |
 |______\__, |_| |_|\__,_|___/\____/|_____/
         __/ |
        |___/

       //\     /\\
      /   \   /   \
     |     \ /     |
     |      V      |
      \           /
       \         /
        \       /
         \     /
          \   /
           \ /
EOF

elif [ "$LOGO_SELECTION" == "lyndsgo" ]; then
    mapfile -t logo << "EOF"
  _                     _      _____  ____
 | |                   | |    / ____|/ __ \
 | |    _   _ _ __   __| |___| |  __| |  | |
 | |   | | | | '_ \ / _` / __| | |_ | |  | |
 | |___| |_| | | | | (_| \__ \ |__| | |__| |
 |______\__, |_| |_|\__,_|___/\_____|\____/
         __/ |
        |___/
EOF

elif [ "$LOGO_SELECTION" == "lyndsgo-enter" ]; then
    mapfile -t logo << "EOF"
  _                     _
 | |                   | |
 | |    _   _ _ __   __| |___
 | |   | | | | '_ \ / _` / __|
 | |___| |_| | | | | (_| \__ \
 |______\__, |_| |_|\__,_|___/
         __/ |
   _____|___/_
  / ____|/ __ \
 | |  __| |  | |
 | | |_ | |  | |
 | |__| | |__| |
  \_____|\____/
EOF

elif [ "$LOGO_SELECTION" == "debian" ]; then
    mapfile -t logo << "EOF"
  _____       _     _
 |  __ \     | |   (_)
 | |  | | ___| |__  _  __ _ _ __
 | |  | |/ _ \ '_ \| |/ _` | '_ \
 | |__| |  __/ |_) | | (_| | | | |
 |_____/ \___|_.__/|_|\__,_|_| |_|
EOF

elif [ "$LOGO_SELECTION" == "debian-love" ]; then
    mapfile -t logo << "EOF"
  _____       _     _
 |  __ \     | |   (_)
 | |  | | ___| |__  _  __ _ _ __
 | |  | |/ _ \ '_ \| |/ _` | '_ \
 | |__| |  __/ |_) | | (_| | | | |
 |_____/ \___|_.__/|_|\__,_|_| |_|

       //\     /\\
      /   \   /   \
     |     \ /     |
     |      V      |
      \           /
       \         /
        \       /
         \     /
          \   /
           \ /
EOF

elif [ "$LOGO_SELECTION" == "gnu" ]; then
    mapfile -t logo << "EOF"
   _____ _   _ _    _
  / ____| \ | | |  | |
 | |  __|  \| | |  | |
 | | |_ | . ` | |  | |
 | |__| | |\  | |__| |
  \_____|_| \_|\____/
EOF

elif [ "$LOGO_SELECTION" == "gnu-logo" ]; then
    mapfile -t logo << "EOF"
    _-`````-,           ,- '- .
  .'   .- - |          | - -.  `.
 /.'  /                     `.   \
:/   :      _...   ..._      ``   :
::   :     /._ .`:'_.._\.    ||   :
::    `._ ./  ,`  :    \ . _.''   .
`:.      /   |  -.  \-. \\_      /
  \:._ _/  .'   .@)  \@) ` `\ ,.'
     _/,--'       .- .\,-.`--`.
       ,'/''     (( \ `  )
        /'/'  \    `-'  (
         '/''  `._,-----'
          ''/'    .,---'
           ''/'      ;:
             ''/''  ''/
               ''/''/''
                 '/'/'
                  `;
EOF

elif [ "$LOGO_SELECTION" == "gnu-love" ]; then
    mapfile -t logo << "EOF"
   _____ _   _ _    _
  / ____| \ | | |  | |
 | |  __|  \| | |  | |
 | | |_ | . ` | |  | |
 | |__| | |\  | |__| |
  \_____|_| \_|\____/

       //\     /\\
      /   \   /   \
     |     \ /     |
     |      V      |
      \           /
       \         /
        \       /
         \     /
          \   /
           \ /
EOF

elif [ "$LOGO_SELECTION" == "gnu-logo-love" ]; then
    mapfile -t logo << "EOF"
  _____   _
 |_   _| | |               _
   | |   | | _____   _____(_)
   | |   | |/ _ \ \ / / _ \
  _| |_  | | (_) \ V /  __/_
 |_____| |_|\___/ \_/ \___(_)


    _-`````-,           ,- '- .
  .'   .- - |          | - -.  `.
 /.'  /                     `.   \
:/   :      _...   ..._      ``   :
::   :     /._ .`:'_.._\.    ||   :
::    `._ ./  ,`  :    \ . _.''   .
`:.      /   |  -.  \-. \\_      /
  \:._ _/  .'   .@)  \@) ` `\ ,.'
     _/,--'       .- .\,-.`--`.
       ,'/''     (( \ `  )
        /'/'  \    `-'  (
         '/''  `._,-----'
          ''/'    .,---'
           ''/'      ;:
             ''/''  ''/
               ''/''/''
                 '/'/'
                  `;
EOF

elif [ "$LOGO_SELECTION" == "67" ]; then
    mapfile -t logo << "EOF"
    ________
   / /____  |
  / /_   / /
 | '_ \ / /
 | (_) / /
  \___/_/
EOF

elif [ "$LOGO_SELECTION" == "linux" ]; then
    mapfile -t logo << "EOF"
  _      _
 | |    (_)
 | |     _ _ __  _   ___  __
 | |    | | '_ \| | | \ \/ /
 | |____| | | | | |_| |>  <
 |______|_|_| |_|\__,_/_/\_\
EOF

elif [ "$LOGO_SELECTION" == "linux-logo" ]; then
    mapfile -t logo << "EOF"
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣠⣤⣤⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣾⣿⣿⣿⣿⣿⣿⣷⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⣽⢫⡌⣿⣿⢉⣤⠹⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣜⠗⠉⠙⠘⠻⢡⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣥⡀⠀⢀⡠⣐⣸⣿⡿⣷⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢀⣾⠇⠉⠒⠶⠉⠀⠀⢻⣿⣿⣷⡀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⣠⣿⠃⠀⠀⠀⠁⠀⠀⠀⠀⢻⣿⣿⣷⡄⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⣼⣿⡏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⢿⣿⣿⣿⣦⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⢠⣿⡿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⢿⣿⣿⣿⡆⠀⠀⠀⠀
⠀⠀⠀⠀⢀⣾⡿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⡀⠀⠀⠀
⠀⠀⠀⢀⣾⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⡇⠀⠀⠀
⠀⠀⠀⡸⠋⠛⣧⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠤⢼⣿⣿⣿⣿⠃⠀⠀⠀
⡐·⠈⠀⠀⠀⠈⢻⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠸⢿⡿⠿⠃⠀⠀⠀⠀
⢡⠀⠀⠀⠀⠀⠀⠀⠻⣿⠷⠀⠀⠀⠀⠀⠀⠀⣠⠃⠀⠀⠀⠀ ⠐⠠⡀
⡄⠀⠀⠀⠀⠀⠀⠀⠀⠑⣄⠀⠀⠀⠀⣀⣤⣾⣿⠀⠀⠀⠀⠀⠀⠀⣀⡠⠃
⠒⠠⠤⣀⣄⡀⠀⠀⢀⣰⣿⠿⠿⠿⠿⠿⠿⠿⣿⡄⠀⠀⢀⡠⠔⠉⠀⠀⠀
⠀⠀⠀⠀⠀⠉⠙⠻⠿⠛⠁⠀⠀⠀⠀⠀⠀⠀⠈⠻⠷⠿⠋⠀⠀⠀⠀⠀⠀
EOF

elif [ "$LOGO_SELECTION" == "linux-big-logo" ]; then
    mapfile -t logo << "EOF"
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣠⣤⣤⣤⣤⣤⣤⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣴⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣤⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡟⠁⠀⠀⠙⢿⣿⣿⣿⡿⠋⠀⠀⠀⠀⠙⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢹⡀⠀⠀⠀⠀⠈⣿⣿⣿⠁⠀⠀⠀⠀⠀⠀⠸⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢨⠁⢠⣾⣶⣦⠀⢸⣿⣿⢠⣾⣿⣶⡀⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⠀⢸⣿⣿⣿⠤⠘⠀⠘⠼⣿⣿⣿⡇⠀⠀⢀⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣧⡀⢹⠟⠁⠀⠀⠀⠀⠀⠈⠙⢟⣁⠀⢀⣼⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡟⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠉⠉⠻⣿⣿⣿⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡆⠣⡀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⡤⠖⠀⠀⣠⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣦⡘⠢⠤⠤⠤⠤⠤⠒⠉⠁⠀⢀⣠⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⠟⠉⠢⣄⣢⠐⣄⠠⣄⢢⣼⠞⠉⠀⠈⠻⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣼⣿⣿⡟⠀⠀⠀⠀⠉⠙⠚⠓⠊⠉⠀⠀⠀⠀⠀⠀⠀⢻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣾⣿⣿⣿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣰⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⡀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣴⣿⣿⣿⣿⣿⡏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⡀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣰⣿⣿⣿⣿⣿⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣰⣿⣿⣿⣿⣿⠏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣇⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣿⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢰⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣾⣿⣿⣿⣿⣿⠂⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠇⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⢰⣿⣿⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠀⠀⠀⠀
⠀⠀⠀ ⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⠀⠀⠀⠀
⠀⠀⠀⡰⠉⠈⠑⠠⢀⢸⣿⣿⣿⣿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡄⠀⠀⠀
⠀⠀⠀⡇⠀⠀⠀⠀⠀⠉⠙⠛⠛⠛⠿⠿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠟⠉⠀⠀⠀⠘⢿⣿⣿⡇⠀⠀⠀
⠀⠀⠀⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣿⣿⣿⣿⣿⣿⣿⣿⠟⠉⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⡇⠀⠀⠀
⠀⠀⢰⠃⠀⠀⢠⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣾⠘⣿⣿⣿⣿⣿⡟⠁⠂⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣿⡇⠀⠀⠀
⠀⡠⠊⠀⢀⠐⡀⠈⠄⠂⡐⠀⢂⠐⠈⠠⢀⠀⠀⢻⡤⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣷⠀⢀⠛⡛⢫⠑⡄⢃⡐⢈⠐⡀⠄⠐⠀⠀⠀⠀⠈⢿⡇⠀⠀
⢠⢁⠀⠄⢂⡐⠠⡁⠌⡐⠠⢁⠂⠌⢠⢁⠂⡐⠀⠘⣿⣳⢤⡀⡀⢀⠀⡀⢀⠀⡀⠠⡀⠤⣁⢿⠀⠄⣂⠑⡂⠥⡘⢠⠐⢂⠰⠀⠌⡐⢈⠐⡀⠀⠀⠀⠑⢄⠀⠀
⠈⢧⡘⡐⢂⠤⠑⡠⢁⠆⡁⠆⠌⣂⠁⡂⠌⡐⠀⠀⢹⣿⣷⣧⣝⣢⠱⡰⣈⢆⢡⢃⠴⡱⣌⣾⠈⡐⢠⠘⡠⢁⠆⡡⢘⠠⡁⠎⡐⡈⢄⠢⢀⠡⢀⠈⠂⠀⠑⡀
⠀⠀⠙⢵⣊⠴⡁⢆⠡⢂⠅⡊⠔⡠⠘⢄⠒⡀⢁⠀⠀⢻⣿⣿⣿⣿⣿⣷⣷⣾⣶⣿⣾⣿⣿⣿⠀⠐⡄⠢⢁⠆⡘⢄⠡⢂⠱⢠⠑⡨⢄⠢⣁⠒⡄⢊⠄⣂⢀⡡
⠀⠀⠀⠀⠉⠲⣍⢢⠱⡈⢆⠱⡈⠔⡉⢄⠒⠄⢂⠀⢀⠀⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡟⠀⠂⢄⠣⠌⣂⠱⡈⢆⠡⢊⠄⢣⠐⢢⠑⡄⢣⡘⢆⡳⣬⠞⠁
⠀⠀⠀ ⠀⠀⠈⢣⡞⡰⢈⠆⡱⢈⠔⡨⢘⡈⠆⢌⠀⡐⠨⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠠⢉⠄⢢⠑⡄⢣⠘⡄⠣⢌⢊⡔⡉⢦⠩⡜⣡⢞⡷⠋⠁⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠙⢶⡉⢆⡱⢈⠆⡑⠢⢌⡘⢄⠣⡐⣡⠏⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⢳⢁⠊⡜⢠⠃⡜⢠⠃⣌⠱⣈⠦⢰⡉⢆⡳⣼⠟⠁⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀ ⠀⠀⠹⣖⡰⢃⡜⢄⠳⣠⠚⣌⠖⣥⡿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣎⠴⡈⢆⠱⡈⢆⠱⡠⢃⠖⣌⠣⣜⢣⠟⠁⠀⠀⠀⠀ ⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠓⢯⡼⣬⣓⣦⣟⣼⡿⠚⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⣶⣉⢆⠳⡌⡜⢢⠱⡩⢜⣤⢻⡼⠋⠀⠀ ⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀ ⠀⠀⠀⠉⠙⠛⠛⠋⠉⠀ ⠀⠀ ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠛⢾⣳⣼⣜⣧⣳⡽⣞⠞⠋⠀⠀⠀⠀ ⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀ ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀ ⠀⠀⠀⠀⠈⠉⣉⢉⣉⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
EOF

elif [ "$LOGO_SELECTION" == "ubuntu" ]; then
    mapfile -t logo << "EOF"
  _    _ _                 _
 | |  | | |               | |
 | |  | | |__  _   _ _ __ | |_ _   _
 | |  | | '_ \| | | | '_ \| __| | | |
 | |__| | |_) | |_| | | | | |_| |_| |
  \____/|_.__/ \__,_|_| |_|\__|\__,_|
EOF

elif [ "$LOGO_SELECTION" == "kubuntu" ]; then
    mapfile -t logo << "EOF"
  _  __     _                 _
 | |/ /    | |               | |
 | ' /_   _| |__  _   _ _ __ | |_ _   _
 |  <| | | | '_ \| | | | '_ \| __| | | |
 | . \ |_| | |_) | |_| | | | | |_| |_| |
 |_|\_\__,_|_.__/ \__,_|_| |_|\__|\__,_|
EOF

elif [ "$LOGO_SELECTION" == "xubuntu" ]; then
    mapfile -t logo << "EOF"
 __   __     _                 _
 \ \ / /    | |               | |
  \ V /_   _| |__  _   _ _ __ | |_ _   _
   > <| | | | '_ \| | | | '_ \| __| | | |
  / . \ |_| | |_) | |_| | | | | |_| |_| |
 /_/ \_\__,_|_.__/ \__,_|_| |_|\__|\__,_|
EOF

elif [ "$LOGO_SELECTION" == "lubuntu" ]; then
    mapfile -t logo << "EOF"
  _           _                 _
 | |         | |               | |
 | |    _   _| |__  _   _ _ __ | |_ _   _
 | |   | | | | '_ \| | | | '_ \| __| | | |
 | |___| |_| | |_) | |_| | | | | |_| |_| |
 |______\__,_|_.__/ \__,_|_| |_|\__|\__,_|
EOF

elif [ "$LOGO_SELECTION" == "arch" ]; then
    mapfile -t logo << "EOF"
                    _
     /\            | |
    /  \   _ __ ___| |__
   / /\ \ | '__/ __| '_ \
  / ____ \| | | (__| | | |
 /_/    \_\_|  \___|_| |_|
EOF

elif [ "$LOGO_SELECTION" == "arch-logo" ]; then
    mapfile -t logo << "EOF"
                  /#\
                 /###\
                /#####\
               /#######\
              /#########\
             /###########\
            /#############\
           /###############\
          /#################\
         /###################\
        /########*"""*########\
       /#######/       \#######\
      /########         ########\
     /#########         #########\
    /##########         ##########\
   /######***             ***######\
  /###**                       **###\
 /**                               **\
EOF

elif [ "$LOGO_SELECTION" == "i-use-arch-btw" ]; then
    mapfile -t logo << "EOF"
  _____
 |_   _|
   | |    _   _ ___  ___
   | |   | | | / __|/ _ \
  _| |_  | |_| \__ \  __/
 |_____|  \__,_|___/\___|
     /\            | |
    /  \   _ __ ___| |__
   / /\ \ | '__/ __| '_ \
  / ____ \| | | (__| | | |
 /_/    \_\_|  \___|_| |_|
 | |   | |
 | |__ | |___      __
 | '_ \| __\ \ /\ / /
 | |_) | |_ \ V  V /
 |_.__/ \__| \_/\_/
EOF

elif [ "$LOGO_SELECTION" == "nyarch" ]; then
    mapfile -t logo << "EOF"
  _   _                      _
 | \ | |                    | |
 |  \| |_   _  __ _ _ __ ___| |__
 | . ` | | | |/ _` | '__/ __| '_ \
 | |\  | |_| | (_| | | | (__| | | |
 |_| \_|\__, |\__,_|_|  \___|_| |_|
         __/ |
        |___/
EOF

elif [ "$LOGO_SELECTION" == "i-use-nyarch-btw" ]; then
    mapfile -t logo << "EOF"
  _____
 |_   _|
   | |    _   _ ___  ___
   | |   | | | / __|/ _ \
  _| |_  | |_| \__ \  __/
 |_____|  \__,_|___/\___|    _
 | \ | |                    | |
 |  \| |_   _  __ _ _ __ ___| |__
 | . ` | | | |/ _` | '__/ __| '_ \
 | |\  | |_| | (_| | | | (__| | | |
 |_| \_|\__, |\__,_|_|  \___|_| |_|
         __/ |
  _     |___/
 | |   | |
 | |__ | |___      __
 | '_ \| __\ \ /\ / /
 | |_) | |_ \ V  V /
 |_.__/ \__| \_/\_/
EOF

elif [ "$LOGO_SELECTION" == "kali" ]; then
    mapfile -t logo << "EOF"
  _  __     _ _
 | |/ /    | (_)
 | ' / __ _| |_
 |  < / _` | | |
 | . \ (_| | | |
 |_|\_\__,_|_|_|
  _      _
 | |    (_)
 | |     _ _ __  _   ___  __
 | |    | | '_ \| | | \ \/ /
 | |____| | | | | |_| |>  <
 |______|_|_| |_|\__,_/_/\_\
EOF

elif [ "$LOGO_SELECTION" == "kali-logo" ]; then
    mapfile -t logo << "EOF"
⠀⠀⠀⠀⠠⠤⠤⠤⠤⠤⣤⣤⣤⣄⣀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠉⠛⠛⠿⢶⣤⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⢀⣀⣀⣠⣤⣤⣴⠶⠶⠶⠶⠶⠶⠶⠶⠶⠿⠿⢿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠚⠛⠉⠉⠉⠀⠀⠀⠀⠀⠀⢀⣀⣀⣤⡴⠶⠶⠿⠿⠿⣧⡀⠀⠀⠀⠤⢄⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⢀⣠⡴⠞⠛⠉⠁⠀⠀⠀⠀⠀⠀⠀⢸⣿⣷⣶⣦⣤⣄⣈⡑⢦⣀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⣠⠔⠚⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣾⡿⠟⠉⠉⠉⠉⠙⠛⠿⣿⣮⣷⣤⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣿⡿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⢻⣯⣧⡀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠻⢷⡤⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⢿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠻⣿⣦⣤⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠙⠛⠛⠻⠿⠿⣿⣶⣶⣦⣄⣀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠻⣿⣯⡛⠻⢦⡀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠙⢿⣆⠀⠙⢆⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⢻⣆⠀⠈⢣
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠻⡆⠀⠈
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⡀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠃⠀
EOF

elif [ "$LOGO_SELECTION" == "default" ]; then
    mapfile -t logo << "EOF"
  _                     _
 | |                   | |
 | |    _   _ _ __   __| |___
 | |   | | | | '_ \ / _` / __|
 | |___| |_| | | | | (_| \__ \
 |______\__, |_| |_|\__,_|___/
         __/ |
  ______|___/      _
 |  ____| | |     | |
 | |__ ___| |_ ___| |__
 |  __/ _ \ __/ __| '_ \
 | | |  __/ || (__| | | |
 |_|  \___|\__\___|_| |_|
EOF

else
    mapfile -t logo << "EOF"
  _                     _
 | |                   | |
 | |    _   _ _ __   __| |___
 | |   | | | | '_ \ / _` / __|
 | |___| |_| | | | | (_| \__ \
 |______\__, |_| |_|\__,_|___/
         __/ |
  ______|___/      _
 |  ____| | |     | |
 | |__ ___| |_ ___| |__
 |  __/ _ \ __/ __| '_ \
 | | |  __/ || (__| | | |
 |_|  \___|\__\___|_| |_|
EOF
fi

# --- RECOLECCIÓN DE INFORMACIÓN DEL SISTEMA ---
get_info() {
    case $1 in
        user)
            info_label="User"
            info_val=$(whoami)
            ;;
        host)
            info_label="Host"
            info_val=$(hostname)
            ;;
        hora)
            info_label="Hora"
            info_val=$(date +"%T")
            ;;
        date)
            info_label="Fecha"
            info_val=$(date +"%d/%m/%Y")
            ;;
        separator)
            echo "SEPARATOR"
            return 0
            ;;
        colours|colors)
            echo "COLORS"
            return 0
            ;;
        os)
            info_label="SO"
            info_val=$(grep '^PRETTY_NAME' /etc/os-release | cut -d'"' -f2)
            ;;
        arch)
            info_label="Arquitectura"
            info_val=$(uname -m)
            ;;
        kernel)
            info_label="Kernel"
            info_val=$(uname -r)
            ;;
        uptime)
            info_label="Uptime"
            info_val=$(uptime -p | sed 's/up //')
            ;;
        shell)
            info_label="Shell"
            info_val=$(basename "$SHELL")
            ;;
        terminal)
            info_label="Terminal"
            info_val="$TERM"
            ;;
        pkgs)
            info_label="Paquetes"
            if command -v dpkg &>/dev/null; then
                info_val="$(dpkg -l | grep -c "^ii") (dpkg)"
            elif command -v pacman &>/dev/null; then
                info_val="$(pacman -Q | wc -l) (pacman)"
            else
                info_val="Desconocido"
            fi
            ;;
        display-manager)
            info_label="Login (DM)"
            dm=$(basename "$(cat /etc/X11/default-display-manager 2>/dev/null)" 2>/dev/null)
            [ -z "$dm" ] && dm=$(pgrep -l -x 'sddm|gdm|gdm3|lightdm|lxdm|xdm' | awk '{print $2}' | head -n 1)
            [ -z "$dm" ] && dm="No detectado"
            # Capitalizar correctamente los DMs conocidos
            case "$dm" in
                sddm)    dm="SDDM" ;;
                gdm|gdm3) dm="GDM" ;;
                lightdm) dm="LightDM" ;;
                lxdm)    dm="LXDM" ;;
                xdm)     dm="XDM" ;;
            esac
            info_val="$dm"
            ;;
        theme)
#             info_label="Tema"
            info_val=""
            # Intentar obtener tema según el entorno
            if [[ "${XDG_CURRENT_DESKTOP,,}" =~ (gnome|ubuntu.*gnome) ]]; then
                if command -v gsettings &>/dev/null; then
                    info_val=$(gsettings get org.gnome.desktop.interface gtk-theme 2>/dev/null | tr -d "'")
                fi
                [ -z "$info_val" ] && info_val=$(grep 'gtk-theme-name=' ~/.config/gtk-3.0/settings.ini 2>/dev/null | cut -d'=' -f2)
            elif [ -f ~/.config/kdeglobals ]; then
                info_val=$(grep '^ColorScheme=' ~/.config/kdeglobals | head -n 1 | cut -d'=' -f2)
            fi
            [ -z "$info_val" ] && info_val="Default"
            ;;
        locale)
            info_label="Idioma"
            info_val="$LANG"
            ;;
        resolution)
            info_label="Resolución"
            info_val=$(xrandr 2>/dev/null | grep '\*' | awk '{print $1}' | head -n 1)
            [ -z "$info_val" ] && info_val="No detectada"
            ;;
        cpu)
            info_label="CPU"
            info_val=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)
            [ -z "$info_val" ] && info_val=$(lscpu | grep 'Model name' | cut -d: -f2 | xargs)
            ;;
        gpu)
            info_label="GPU"
            info_val=$(lspci 2>/dev/null | grep -E "VGA|3D" | cut -d':' -f3 | xargs | sed 's/\[Radeon.*\]//g')
            [ -z "$info_val" ] && info_val="No detectada"
            ;;
        ram)
            info_label="Memoria RAM"
            info_val=$(free -h | awk '/Mem:/ {print $3 " / " $2}')
            ;;
        swap)
            info_label="Swap"
            info_val=$(free -h | awk '/Swap:/ {print $3 " / " $2}')
            if [[ "$info_val" == *"0B / 0B"* || "$info_val" == *"0.0 B"* || -z "$info_val" ]]; then
                info_val="No configurada"
            fi
            ;;
        disk)
            info_label="Disco (/)"
            used=$(df -h / | awk 'NR==2 {print $3}')
            size=$(df -h / | awk 'NR==2 {print $2}')
            percent=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
            if [ -n "$percent" ]; then
                if [ "$percent" -lt 70 ]; then
                    color_percent="$GREEN"
                elif [ "$percent" -lt 90 ]; then
                    color_percent="$YELLOW"
                else
                    color_percent="$RED"
                fi
                info_val="${used} / ${size} (${color_percent}${percent}%${NC})"
            else
                info_val="${used} / ${size} (desconocido)"
            fi
            ;;
        battery)
            bat_path=$(ls -d /sys/class/power_supply/BAT* 2>/dev/null | head -n 1)
            if [ -n "$bat_path" ]; then
                info_label="Batería"
                capacity=$(cat "$bat_path/capacity")
                status=$(cat "$bat_path/status")
                info_val="${capacity}% (${status})"
            else
                return 0
            fi
            ;;
        local-ip)
            info_label="IP Local"
            info_val=$(hostname -I | awk '{print $1}')
            [ -z "$info_val" ] && info_val="Sin conexión"
            ;;
        global-ip)
            info_label="IP Pública"
            if command -v curl &>/dev/null; then
                info_val=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "No disponible")
            else
                info_val="curl no instalado"
            fi
            [ -z "$info_val" ] && info_val="No disponible"
            ;;
        apt-updates)
            info_label="Actualiz. APT"
            if command -v apt &>/dev/null; then
                count=$(apt list --upgradable 2>/dev/null | grep -c "/" || echo 0)
                info_val="$count disponible(s)"
            else
                info_val="N/A"
            fi
            ;;
        cpu-temperature)
            info_label="Temp. CPU"
            cpu_temp="N/A"
            for zone in /sys/class/thermal/thermal_zone*; do
                if [ -f "$zone/type" ]; then
                    type=$(cat "$zone/type")
                    if [[ "$type" =~ (x86_pkg_temp|cpu|CPU|acpitz) ]]; then
                        temp_raw=$(cat "$zone/temp" 2>/dev/null)
                        if [ -n "$temp_raw" ]; then
                            cpu_temp=$(( temp_raw / 1000 ))°C
                            break
                        fi
                    fi
                fi
            done
            [ "$cpu_temp" = "N/A" ] && info_val="No disponible" || info_val="$cpu_temp"
            ;;
        gpu-temperature)
            info_label="Temp. GPU"
            gpu_temp="N/A"
            if command -v nvidia-smi &>/dev/null; then
                temp=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null)
                [ -n "$temp" ] && gpu_temp="${temp}°C"
            else
                for zone in /sys/class/thermal/thermal_zone*; do
                    if [ -f "$zone/type" ]; then
                        type=$(cat "$zone/type")
                        if [[ "$type" =~ (gpu|GPU|radeon|amdgpu|nvidia) ]]; then
                            temp_raw=$(cat "$zone/temp" 2>/dev/null)
                            if [ -n "$temp_raw" ]; then
                                gpu_temp=$(( temp_raw / 1000 ))°C
                                break
                            fi
                        fi
                    fi
                done
            fi
            [ "$gpu_temp" = "N/A" ] && info_val="No disponible" || info_val="$gpu_temp"
            ;;
        session-type|session)
            info_label="Servidor Gráfico"
            session="${XDG_SESSION_TYPE}"
            if [ -z "$session" ]; then
                if [ -n "$WAYLAND_DISPLAY" ]; then
                    session="Wayland"
                elif [ -n "$DISPLAY" ]; then
                    session="X11"
                else
                    session="No detectada"
                fi
            else
                # Normalizar a mayúsculas correctas
                session=$(echo "$session" | tr '[:upper:]' '[:lower:]')
                case "$session" in
                    wayland) session="Wayland" ;;
                    x11|xorg) session="X11" ;;
                esac
            fi
            info_val="$session"
            ;;
        os-codename)
            info_label="Codename del SO"
            if [ -f /etc/os-release ]; then
            codename=$(grep -E '^(VERSION_CODENAME|UBUNTU_CODENAME)=' /etc/os-release \
                   | head -n 1 | cut -d= -f2 | tr -d '"')
        fi

        [ -z "$codename" ] && codename="N/A"

        # Primera letra en mayúscula
        codename="$(echo "$codename" | sed 's/.*/\u&/')"

        info_val="$codename"
        ;;
        os-version)
            info_label="Versión SO"
            if [ -f /etc/os-release ]; then
                version=$(grep -E '^VERSION_ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
            fi
            [ -z "$version" ] && version="N/A"
            info_val="$version"
            ;;
        os-based)
            info_label="Base SO"
            if command -v apt &>/dev/null; then
                base="Debian"
            elif command -v pacman &>/dev/null; then
                base="Arch"
            elif command -v dnf &>/dev/null; then
                base="Fedora/RHEL"
            else
                base="Desconocida"
            fi
            info_val="$base"
            ;;
        ram-type)
            info_label="RAM Type"
            ram_type="No detectado"
            if command -v dmidecode &>/dev/null; then
                type_line=$(dmidecode -t memory 2>/dev/null | grep -m1 "Type:" | awk -F':' '{print $2}' | xargs)
                if [ -n "$type_line" ]; then
                    case "$type_line" in
                        *DDR4*) ram_type="DDR4" ;;
                        *DDR5*) ram_type="DDR5" ;;
                        *DDR3*) ram_type="DDR3" ;;
                        *DDR2*) ram_type="DDR2" ;;
                        *DDR*) ram_type="DDR" ;;
                        *) ram_type="$type_line" ;;
                    esac
                fi
            fi
            if [ "$ram_type" = "No detectado" ] && command -v lshw &>/dev/null; then
                type_line=$(lshw -c memory 2>/dev/null | grep -m1 "description:" | grep -o 'DDR[0-9]*')
                [ -n "$type_line" ] && ram_type="$type_line"
            fi
            info_val="$ram_type"
            ;;
        casata-version)
            info_label="Casata Versión"
            if [ -f /usr/local/casata/VERSION ]; then
                info_val=$(cat /usr/local/casata/VERSION)
            else
                info_val="N/A"
            fi
            ;;
        casata-int-apps)
            info_label="Casata Apps (Inst.)"
            if [ -d /usr/local/casata/apps ]; then
                info_val=$(find /usr/local/casata/apps/ -maxdepth 1 -type d 2>/dev/null | tail -n +2 | wc -l)
            else
                info_val="0"
            fi
            ;;
        casata-apps)
            info_label="Casata Apps"
            if [ -d /usr/local/casata/apps ]; then
                apps=($(find /usr/local/casata/apps/ -maxdepth 1 -type d 2>/dev/null | tail -n +2 | xargs -I{} basename {}))
                if [ ${#apps[@]} -eq 0 ]; then
                    echo "TEXT:${info_label}:Ninguna"
                else
                    # Primera aplicación
                    echo "TEXT:${info_label}:${apps[0]}"
                    # Resto de aplicaciones con indentación
                    local indent=$((${#info_label} + 2))  # +2 por ": "
                    for (( j=1; j<${#apps[@]}; j++ )); do
                        echo "INDENT:${indent}:${apps[$j]}"
                    done
                fi
                return 0
            else
                info_val="N/A"
            fi
            ;;
        *)
            return 1
            ;;
    esac
    # Solo para módulos que no han hecho return antes
    echo "TEXT:${info_label}:${info_val}"
}

# --- PREPARACIÓN DE MÓDULOS ---
info_lines=()

while IFS= read -r module; do
    [ -z "$module" ] && continue
    while IFS= read -r line_content; do
        [ -n "$line_content" ] && info_lines+=("$line_content")
    done < <(get_info "$module")
done < <(get_modules)

# --- CÁLCULO DE MÁXIMO ANCHO DEL LOGO ---
max_logo_width=0
for line in "${logo[@]}"; do
    if (( ${#line} > max_logo_width )); then
        max_logo_width=${#line}
    fi
done

max_lines=${#logo[@]}
if (( ${#info_lines[@]} > max_lines )); then
    max_lines=${#info_lines[@]}
fi

# --- IMPRESIÓN PANTALLA ---
echo "--------------------------------------------------------------------------------"

# Variable para guardar la indentación actual (usada por líneas INDENT)
indent_spaces=0

for ((i=0; i<max_lines; i++)); do
    # 1. Imprimir línea del logo
    if [ $i -lt ${#logo[@]} ]; then
        printf "${COLOR}%-*s${NC}" "$max_logo_width" "${logo[$i]}"
    else
        printf "%-*s" "$max_logo_width" ""
    fi

    printf "   "

    # 2. Imprimir línea de información interpretando colores o bloques
    if [ $i -lt ${#info_lines[@]} ]; then
        current_line="${info_lines[$i]}"

        if [ "$current_line" == "SEPARATOR" ]; then
            echo -e "${COLOR}----------------------------------${NC}"
            indent_spaces=0

        elif [ "$current_line" == "COLORS" ]; then
            echo -e "\x1b[40m  \x1b[41m  \x1b[42m  \x1b[43m  \x1b[44m  \x1b[45m  \x1b[46m  \x1b[47m  \x1b[0m"
            indent_spaces=0

        elif [[ "$current_line" == INDENT:* ]]; then
            # Línea de indentación (proviene de módulos multilínea como casata-apps)
            spaces=$(echo "$current_line" | cut -d: -f2)
            val=$(echo "$current_line" | cut -d: -f3-)
            printf "%*s%s\n" "$spaces" "" "$val"

        elif [[ "$current_line" == TEXT:* ]]; then
            clean_line="${current_line#TEXT:}"
            label=$(echo "$clean_line" | cut -d':' -f1)
            val=$(echo "$clean_line" | cut -d':' -f2-)
            echo -e "${COLOR}${BOLD}${label}:${NC} ${val}"
            # Guardar indentación para posibles líneas INDENT posteriores
            indent_spaces=$(( ${#label} + 2 ))
        else
            echo "$current_line"
        fi
    else
        echo ""
    fi
done

echo "--------------------------------------------------------------------------------"
