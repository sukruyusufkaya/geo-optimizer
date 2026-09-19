# Sunucuya kurulum (tek VPS, Docker + nginx)

Doğrulanmış durum: `Dockerfile.web` yerelde temiz derleniyor (476 MB),
`/health` 200 dönüyor, frontend ve gerçek bir audit uçtan uca çalışıyor.

## Gereksinimler

- Ubuntu/Debian bir sunucu, root ya da sudo erişimi
- Docker Engine + Compose eklentisi, nginx, certbot
- Alan adının A kaydı sunucunun IP'sine bakıyor olmalı (TLS için şart)
- Derleme sırasında sunucunun dışa erişimi: Astro aşaması `sitemap.xml` ve
  `llms.txt` dosyalarını canlı Sanity veri setinden üretir ve Sanity'ye
  ulaşamazsa derlemeyi bilerek başarısız sayar.

## 1. Kurulum

```bash
sudo mkdir -p /opt/geo-optimizer && sudo chown "$USER" /opt/geo-optimizer
git clone <REPO_URL> /opt/geo-optimizer
cd /opt/geo-optimizer
cp deploy/.env.example deploy/.env
```

`deploy/.env` içinde en azından şu ikisini doldur:

- `ALLOWED_ORIGINS` — kendi alan adın. Varsayılan `*`, herkese açık demo içindir.
- `TRUSTED_PROXIES=127.0.0.1` — nginx önde olduğu için gerekli; bu olmadan
  IP başına hız sınırı tek bir kovaya çöker.

Geri kalan değişkenler isteğe bağlı; ayrıntılar `.env.example` içinde.

## 2. Çalıştırma

```bash
./deploy/deploy.sh
```

Konteyner yalnızca `127.0.0.1:8000` üzerinde dinler — internete doğrudan açık
değildir. Doğrulama:

```bash
curl -s localhost:8000/health   # {"status":"ok","version":"..."}
```

## 3. nginx + TLS

```bash
sudo cp deploy/nginx/geo-optimizer.conf /etc/nginx/sites-available/geo-optimizer
sudo sed -i 's/DOMAIN/alanadin.com/g' /etc/nginx/sites-available/geo-optimizer
sudo ln -sf /etc/nginx/sites-available/geo-optimizer /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d alanadin.com -d www.alanadin.com
```

certbot TLS bloğunu ve HTTP→HTTPS yönlendirmesini kendisi ekler; dosyayı
elle HTTPS'e çevirmeye gerek yok.

## 4. Güncelleme

```bash
cd /opt/geo-optimizer && ./deploy/deploy.sh
```

Yeni imaj derlenene kadar eski konteyner yayına devam eder; derleme
başarısız olursa çalışan sürüme dokunulmaz.

## Dağıtıma özel notlar

- **`site:` alan adı sabit.** `frontend/astro.config.mjs` içinde
  `site: 'https://geoready.dev'` gömülü. Kendi alan adında yayınlıyorsan
  canonical etiketleri ve sitemap hâlâ geoready.dev'i gösterir — derlemeden
  önce bu değeri değiştir.
- **İçerik yukarı akıştan gelir.** Frontend, upstream'in Sanity projesinden
  (`uvzrnk4t`) okur. Kendi içeriğin için kendi Sanity projeni açıp
  `PUBLIC_SANITY_PROJECT_ID` / `PUBLIC_SANITY_DATASET` değerlerini ver.
- **Stats varsayılanı üçüncü tarafa gider.** `GEO_STATS_API_URL` varsayılanı
  upstream'in `agencypilot.it` uç noktasıdır. Anahtar verilmediğinde hiçbir
  istek atılmaz, bu yüzden ikisini de boş bırak.
- **Lisans.** Proje MIT; `LICENSE` ve telif satırlarını olduğu gibi koru.
