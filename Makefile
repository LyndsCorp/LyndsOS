all:
	@if [ "$$(id -u)" -ne 0 ]; then \
		echo "Tienes que ejecutar 'make' con sudo"; \
		exit 2; \
	fi
	@lb config \
		--distribution trixie \
		--architectures amd64 \
		--archive-areas "main contrib non-free non-free-firmware" \
		--binary-images iso-hybrid \
		--iso-application "LyndsOS GNU/Linux" \
		--iso-preparer "David Bana Szymaniak" \
		--iso-publisher "LyndsOS Project" \
		--iso-volume "LyndsOS 1.26.08 Light"
	@lb build

get-zen:
	@infernal ./get-zen.inf

clean:
	@if [ "$$(id -u)" -ne 0 ]; then \
		echo "Tienes que ejecutar 'make clean' con sudo"; \
		exit 2; \
	fi
	@lb clean

distclean:
	@if [ "$$(id -u)" -ne 0 ]; then \
		echo "Tienes que ejecutar 'make clean' con sudo"; \
		exit 2; \
	fi
	@lb clean --purge
	@rm -r ./config/includes.chroot/usr/local/casata/apps/zen-browser-amd64/
