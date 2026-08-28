# Monojo-Music
Un reproductor de música de archivos de música local diseñado para escuchar música mientras haces algo más.

Monojo Music utiliza una librería del sistema en vez de una de Python, así que tienes que instalarla.
Puedes escuchar todos estos archivos:
- `.mp3`
- `.wav`
- `.flac`
- `.ogg`
- `.m4a`
- `.opus`
- `.mp4` 
- `.mkv`
  
> (Los archivos de video son solo el audio del video)

## Cómo instalar la dependencia:

Debian/Ubuntu/LyndsOS:
```
sudo apt update && sudo apt install ffmpeg
```

Arch:
```
sudo pacman -S ffmpeg
```

Fedora:
```
sudo dnf install ffmpeg
```


### Dónde se guarda todo
Toda la configuración se guarda en ~/.config/MonojoMusic/.
En ~/.config/MonojoMusic/Musicas/ se copian todos los archivos que añadas.
En ~/.config/MonojoMusic/Playlists hay archivos .txt que representan las playlists creadas y guardan sus canciones.
El ~/.config/MonojoMusic/monojo_amarillo.png es el icono de la ventana.
> El icono monojo_amarillo.png se mueve a esa carpeta en la primera ejecución.
