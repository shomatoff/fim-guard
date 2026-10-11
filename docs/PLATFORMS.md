# Windows and Linux packages / Windows va Linux paketlari / Пакеты Windows и Linux

Packages are published only after the GitHub Actions jobs succeed. Download them from [Releases](https://github.com/shomatoff/fim-guard/releases); development artifacts are attached to the [Test and build workflow](https://github.com/shomatoff/fim-guard/actions/workflows/ci.yml). The packages are unsigned. Python is not required to run an extracted package, but the executable and its `_internal` directory must stay together.

## Windows x64

**EN:** Download `FIM-Guard-Windows-x64.zip`, extract it, then double-click `FIM-Guard.exe` inside the extracted folder. Choose a directory and create a baseline. The app stores settings and its database in your local application data directory. A Windows CI build is configured; physical Windows display scaling and filesystem notifications have not yet been tested.

**UZ:** ZIP arxivni oching va ichidagi `FIM-Guard.exe` faylini ishga tushiring. Jild tanlab, boshlang‘ich holat yarating. Sozlamalar va baza mahalliy ilova ma’lumotlari jildida saqlanadi. Windows CI yig‘ilishi sozlangan, haqiqiy Windows qurilmasida ekran masshtabi va fayl xabarlari hali sinovdan o‘tmagan.

**RU:** Распакуйте ZIP и запустите `FIM-Guard.exe`. Выберите папку и создайте исходную базу. Настройки и база хранятся в локальном каталоге данных приложения. Сборка Windows настроена в CI; масштабирование и уведомления на реальном компьютере Windows пока не проверены.

## Linux x64

**EN:** Download `FIM-Guard-Linux-x64.tar.gz`, extract it and run `./FIM-Guard/FIM-Guard`. The executable package was built and launched locally on Linux. On other distributions, missing Qt XCB runtime libraries may require installation through the distribution package manager; [source installation](README_EN.md) remains available.

**UZ:** TAR.GZ arxivni oching va `./FIM-Guard/FIM-Guard` ni ishga tushiring. Linux paketi shu tizimda yig‘ilib, ishga tushirilgan. Boshqa distributivlarda Qt XCB kutubxonalari kerak bo‘lishi mumkin; [manbadan o‘rnatish](README_UZ.md) ham mavjud.

**RU:** Распакуйте TAR.GZ и запустите `./FIM-Guard/FIM-Guard`. Пакет Linux собран и запущен локально. В других дистрибутивах могут понадобиться библиотеки Qt XCB; доступна [установка из исходников](README_RU.md).

Run `python scripts/build.py` from a source checkout to build an archive for the **current** operating system. PyInstaller does not cross compile the Windows package from Linux or vice versa. The project has no installer or code signing certificate.
