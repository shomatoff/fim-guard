# FIM Guard — o‘zbekcha qo‘llanma

FIM faqat o‘zingiz tanlagan jildlardagi fayllarni tekshiradi. SHA-256 boshlang‘ich holati yaratiladi; qo‘shilgan, o‘zgargan va o‘chirilgan fayllar SQLite’da saqlanadi. Dastur qo‘lda va jonli tekshiruv, pauza, hodisalar tarixi hamda JSON/CSV hisobotlarini qo‘llaydi.

## O‘rnatish

Python 3.12 kerak. `python -m venv .venv` bilan virtual muhit yarating, uni ishga tushiring, `python -m pip install -r requirements.txt` va `python main.py` buyruqlarini bajaring. Linuxda Qt XCB kutubxonalari yetishmasa, distributivingiz paket menejeri orqali `libgl1`, `libegl1`, `libx11-xcb1`, `libxcb-cursor0`, `libxkbcommon-x11-0`, `libdbus-1-3` ni o‘rnating. Windows PowerShell’da muhitni `.venv\Scripts\Activate.ps1` bilan yoqing.

## Foydalanish

Jildni tanlang, boshlang‘ich holat yarating, so‘ng qo‘lda tekshiring yoki jonli kuzatuvni yoqing. Hodisalarda UTC vaqti va fayl manzili ko‘rsatiladi. Pauzadan keyin davom ettirish yangi tekshiruvni boshlaydi. So‘nggi skan xulosasi va hodisalarini bosh sahifadan JSON yoki CSV sifatida saqlang. Yuqori o‘ngdagi til tanlovi qayta ishga tushganda saqlanadi.

Ma’lumotlar bazasi va ogohlantirish jurnali tizimning ilova ma’lumotlari jildida saqlanadi. Fayl mazmuni saqlanmaydi. Hisobotda sezgir manzillar va xeshlar bo‘lishi mumkin; ulashishdan oldin tekshiring.

Test: `python -m pytest -q`. Tuzilma: [Architecture](ARCHITECTURE.md). Xavfsizlik: [Security](SECURITY.md).
