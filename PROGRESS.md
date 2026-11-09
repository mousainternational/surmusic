# PROGRESS — Sur Music Radio (اگلی نشست میں صرف یہ فائل پڑھیں)

آخری تازہ کاری: 9 نومبر 2026، صبح (پاکستانی وقت)۔ کام کی branch: `stage1-data-safety` (main میں ابھی شامل نہیں)۔

## جانچے ہوئے حقائق (ثبوت کے ساتھ)
- main اس وقت `ff0553f` (6 نومبر، 09:41) پر ہے۔ 7 نومبر کو main پر 61 commits اور 32 PR شامل ہوئے
  (UTC 14:49 سے 18:17، یعنی پاکستانی وقت شام 7:49 سے رات 11:17، زیادہ ٹریفک کے وقت)۔ branch کے نام `codex/...` ہیں، جو OpenAI Codex (ChatGPT) کے ہیں۔
  پھر 7 نومبر UTC 19:28 (8 نومبر رات 12:28 PKT) کو main کو force-push کر کے `ff0553f` پر واپس لایا گیا۔ یعنی 7 نومبر کا سارا کام main سے ہٹ چکا ہے۔
  (ثبوت: GitHub activity API میں `force_push 31f8251->ff0553f`)
- 7 نومبر کو `002bccd` "Fix Python syntax error in database fallback condition" (UTC 15:34): اس سے پہلے کا main کوڈ چل ہی نہیں سکتا تھا۔
- ڈیٹا مٹنے کی وجہ (کوڈ): `app/__init__.py` `_database_or_fallback()` — Neon نہ ملے تو `STORAGE_DIR/surmusic-fallback.db` (SQLite)۔
  Render Free پر ڈسک عارضی ہے: ہر restart، deploy اور 15 منٹ بعد سونے پر فائل مٹتی ہے (Render docs: render.com/docs/free)۔
  ہر نئی شروعات = خالی ڈیٹا بیس = اکاؤنٹ، ایڈمن، 2FA، AdSense سیٹنگز غائب۔
- ری سیٹ ای میل نہ آنے کی وجہ: `auth.forgot()` صرف موجود اکاؤنٹ کو ای میل بھیجتا ہے۔ اکاؤنٹ مٹ چکا تھا، اس لیے ای میل نہیں گئی۔ تصدیقی ای میلز آئیں، یعنی Brevo کام کر رہا ہے۔
- A–Z خالی ہونے کی وجہ: پرانا `/stations/<letter>` صرف `station_cache` (ڈیٹا بیس) اور میموری کی فہرستوں سے بنتا تھا، جو ہر restart پر خالی ہو جاتی تھیں۔
- Render Free کی ڈسک: مستقل ڈسک لگ ہی نہیں سکتی۔ `render.yaml` میں `plan: starter` + disk ہے، مگر سروس `render-free.yaml` جیسی Free ہے۔ ہینڈ آف کی بات غلط تھی۔

## branch `stage1-data-safety` میں ہو چکا (pytest: 190 پاس)
1. `app/persist.py`: قیمتی چھوٹا ڈیٹا (users, user_2fa, settings, favorites, station_likes, reviews, messages, apps, media_blobs, app_*)
   کی encrypted کاپی ایک **نجی** GitHub repo میں۔ ہر 10 منٹ (صرف تبدیلی پر) اور سرور رکنے سے پہلے۔ شروع میں ڈیٹا بیس خالی ہو تو کاپی واپس لوڈ۔
   خالی ڈیٹا بیس کبھی اچھی کاپی کی جگہ نہیں لیتا۔ ضرورت: Render پر `BACKUP_GITHUB_REPO` اور `BACKUP_GITHUB_TOKEN`۔
2. سیٹنگز کا متبادل: `SETTING_<KEY>` environment variables (مثلاً `SETTING_ADSENSE_CLIENT`, `SETTING_ADS_ENABLED`) اور `app/data/site_settings.json`۔
3. اسٹیشنز کی فہرست کوڈ کے ساتھ: `app/data/directory.jsonl.gz` (30,768 اسٹیشنز، 3.5 MB)، جسے GitHub Actions مہینے میں دو بار بناتا ہے
   (`tools/build_directory.py`, `.github/workflows/station-directory.yml`)۔ سرور پر لوڈ: 0.3 سیکنڈ، تقریباً 4 MB میموری۔ نئی فہرست الگ فائل میں بنتی ہے اور مکمل ہونے پر ہی بدلتی ہے۔
4. A–Z: ڈائریکٹری سے، 100 فی صفحہ، مقبول پہلے۔ گنتی: 0-9 (اور غیر لاطینی نام): 3760، A:1254، B:1009، C:1739، D:738، E:1174، F:949، G:620، H:754، I:402، J:401، K:1029، L:1336، M:1260، N:941، O:479، P:863، Q:124، R:7205، S:1709، T:997، U:198، V:403، W:1040، X:101، Y:146، Z:137۔
   sitemap-stations-0..13 بھرے ہوئے (0 میں 2201 URLs)۔ 14 اور 15 خالی (404)، کیونکہ https فلٹر کے بعد 14 حصے بنتے ہیں۔
5. GeoIP کی 120 MB فائل ہر restart پر ڈاؤن لوڈ ہونا بند (مستقل ڈسک نہ ہو تو)۔ واپس چلانے کے لیے `GEOIP_AUTO=1`۔
6. Docker میں gunicorn ورکر 3 کی جگہ 1 (اگر `WEB_CONCURRENCY` نہ دیا ہو)۔
7. ری سیٹ ای میل پس منظر میں۔
8. مرحلہ 2 کا حصہ: 2FA آن ہو تو پاس ورڈ بدلنے اور ای میل ری سیٹ دونوں پر Authenticator (یا recovery) کوڈ لازمی۔ پاس ورڈ بدلنے/ری سیٹ پر ای میل اطلاع (وقت + ڈیوائس)۔
9. `/healthz` میں `info`: stations, permanent_disk, data_backup, data_backup_last_ok, restore_at_start۔

## باقی (ترتیب سے)
- [ ] مالک: نجی repo + token + Render env (README نیچے)، پھر PR merge، پھر `/healthz` جانچ۔
- [ ] Render کی بینڈوڈتھ حد (4.97/5 GB) — سروس معطل تو نہیں؟ (مجھے سائٹ تک رسائی نہیں تھی)
- [ ] مرحلہ 2 باقی: نئی ڈیوائس لاگ اِن ای میل، غلط کوششوں کی روک کی جانچ، OWNER_EMAILS راستے پر 2FA۔
- [ ] مرحلہ 3: ہیڈر میں 1000 شہر، Cloudflare، اسلامک صفحات کی کیش، uptime monitor۔
- [ ] مرحلہ 4 سے 9۔
- [ ] دسمبر: "Neon کا پرانا ڈیٹا واپس لاؤ" (پرانا DATABASE_URL درکار)۔

## مالک کے کرنے کے کام (ایک بار)
1. GitHub پر نیا **Private** repo: `surmusic-backup` (خالی، README کے ساتھ)۔
2. GitHub → Settings → Developer settings → Fine-grained tokens → Generate: Repository access = صرف `surmusic-backup`، Permissions → Contents = Read and write، مدت 1 سال۔
3. Render → surmusic → Environment:
   - `BACKUP_GITHUB_REPO` = `mousainternational/surmusic-backup`
   - `BACKUP_GITHUB_TOKEN` = (token)
   - `DATABASE_URL` = `sqlite:////data/storage/surmusic.db` (پرانی Neon قیمت کہیں نجی جگہ محفوظ کریں، دسمبر میں درکار)
   - اختیاری: `SETTING_ADSENSE_CLIENT`, `SETTING_ADS_ENABLED=1`
4. PR merge کریں (شام 6 سے رات 11 کے علاوہ)۔ deploy کے بعد ایک آخری بار سائن اپ + ای میل تصدیق → ایڈمن۔ 10 منٹ بعد `/healthz` میں `data_backup_last_ok` میں وقت نظر آئے۔

## commits
- `914bf80` مرحلہ 1 (ڈیٹا، A–Z، GeoIP، ورکرز)
- `03a286c` GitHub Actions: پہلی اسٹیشن فہرست
- (اگلا) مرحلہ 2 کا حصہ + 100 فی صفحہ + healthz + یہ فائل
