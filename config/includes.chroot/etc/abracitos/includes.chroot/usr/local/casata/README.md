# Casata

Gestor de aplicaciones para LyndsOS  
Desarrollado por David Baña Szymaniak

---

## 📌 Descripción

Casata es un sistema de instalación y gestión de aplicaciones diseñado para LyndsOS. Su objetivo es ofrecer una forma simple, estructurada y controlada de instalar software sin depender directamente del formato `.deb` ni de interacción manual con el sistema base. Desarrollado por David Baña Szymaniak, Lynds Corp.

Casata organiza las aplicaciones como unidades autocontenidas y gestiona su integración en el sistema mediante enlaces simbólicos y un modelo de repositorios.

---

## 🧠 Filosofía del sistema

- Las aplicaciones deben ser simples de instalar y eliminar
- El usuario no interactúa con formatos complejos
- El sistema base permanece protegido
- Las apps se integran mediante enlaces controlados
- Todo se gestiona desde repositorios Casata

---

## 📁 Estructura del sistema

Casata utiliza la siguiente estructura base:

```
/usr/local/casata/
│
├── apps/              # Aplicaciones instaladas (modo global)
├── repos/             # Repositorios y metarepos
│   ├── metarepos/
│   └── singrepos/
├── db/                # Base de datos local de paquetes
└── modules/           # Núcleo del sistema Casata

Modo usuario:

~/.local/casata/
├── apps/              # Aplicaciones instaladas por usuario
└── db/                # Base de datos del usuario
```

---

📦 Estructura de una aplicación Casata

Una aplicación Casata es una carpeta simple con los siguientes elementos:

```
mc-lan/
├── main.py
├── icon.png
├── mc-lan.desktop
└── GUIDE.json
```

---

📄 GUIDE.json (formato de enlaces)

Define cómo se integra la aplicación en el sistema:

```
{
  "links": [
    {
      "file": "mc-lan-cli",
      "dest": "/usr/bin",
      "name": "mc-lan-cli"
    },
    {
      "file": "server.py",
      "dest": "/usr/bin",
      "name": "mc-lan-ser"
    },
    {
      "file": "icon.png",
      "dest": "/usr/share/icons/Monojo",
      "name": "mc-lan.png"
    }
  ]
}
```

---

⚙️ Instalación de Casata

Instalación global:
```

sudo casata install mc-lan
```

Instalación de usuario:
```

casata install --user mc-lan
```

---

🔍 Buscar paquetes

casata search monojo

Ejemplo de salida:

Monojo Chats LAN (mc-lan)
Monojo Music Player (monojo-music)


---

ℹ️ Información de un paquete

casata info mc-lan

Ejemplo:

Paquete: mc-lan
Estado: Instalado
Versión: 2.0
Descripción: Chats en LAN sin servidores externos
Dependencias: python3, python3-pil


---

❌ Eliminar paquetes

sudo casata remove mc-lan


---

🔄 Actualizar repositorios

sudo casata update


---

📡 Sistema de repositorios

Casata utiliza dos tipos de repositorios:

🔹 Metarepos

Contienen múltiples paquetes:

Monojo-Project → apunta a varios singrepos

Ejemplo:

casata add repo https://example.com/METAREPO.json


---

🔹 Singrepos

Contienen un solo paquete:

mc-lan.json

Ejemplo:

casata add singrepo https://example.com/mc-lan.json


---

🧪 Flujo de instalación

1. Buscar paquete en repositorios


2. Descargar singrepo


3. Descargar aplicación


4. Extraer archivos


5. Crear estructura en /usr/local/casata/apps


6. Crear enlaces definidos en GUIDE.json


7. Registrar en base de datos




---

🔐 Seguridad

Casata incluye validaciones básicas:

Prevención de sobrescritura de archivos del sistema

Verificación de enlaces existentes

Abortado automático en conflictos

Separación entre instalación global y usuario



---

🚀 Objetivo del proyecto

Casata busca convertirse en una capa de gestión de aplicaciones para LyndsOS que:

Simplifica la instalación de software

Evita complejidad de paquetes tradicionales

Mantiene el sistema base estable

Permite un ecosistema propio de aplicaciones



---

📌 Futuro del proyecto

Sandbox de aplicaciones con usuario casata

Sistema de permisos por app

Runtime Python aislado opcional

Verificación de repositorios firmados

Tienda central de aplicaciones Monojo



---

👤 Autor

David Baña Szymaniak,
LYNDS Project
