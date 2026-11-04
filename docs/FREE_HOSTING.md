# Sur Music — FREE internet par live karna (Render + Neon)

**Kharcha: Rs 0.** Address hoga `https://surmusic.onrender.com` (ya isi tarah ka). Apna domain (jaise `surmusic.pk`) baad mein khareed kar isi par lag sakta hai.

## Free plan ki 4 haqiqatein (pehle parh lein)
1. **Website so jati hai:** 15 minute koi na aaye to Render isay band kar deta hai; agla visitor ~1 minute intezar karta hai. Hal: step 6 (UptimeRobot, free).
2. **Database Neon par:** 1 GB jagah, mahine ke 100 compute-hours, hamesha free (credit card nahi). Website **kam-database mode** mein chalti hai (sunne aur page dekhne par database nahi jaagta; data 15 minute mein ek dafa jata hai), is liye yeh ghante kaafi der chalte hain. Neon mein compute size **0.25** rakhein aur Render par `WEB_CONCURRENCY` = **1**.
3. **APK upload nahi hogi** (free server ki disk restart par saaf ho jati hai): APK GitHub **Releases** par rakh kar us ka link Admin → App downloads mein dalein. JazzCash/NayaPay **QR images theek chalti hain** (database mein mehfooz hoti hain).
4. **Google AdSense ke liye apna domain chahiye:** `onrender.com` wale address par AdSense approval nahi milti. Ads ke waqt domain khareedna hoga (~Rs 3,000–4,000 saal).
   Visitors ka **mulk aur shehar** dikhta hai: website DB-IP database (~120 MB) khud download karti hai. Free server har restart par isay dobara download karta hai (kuch minute), us dauran sirf mulk dikhta hai.

---

## Step 1 — Code GitHub par (private)
1. **desktop.github.com** se **GitHub Desktop** install karein, apne GitHub account se sign in.
2. File → **Add local repository** → `surmusic-web` folder chunein → "create a repository" → Name: `surmusic-web` → **Create**.
3. **Publish repository** → ✅ **Keep this code private** → Publish.
   (`.env` aur `data` folder khud bahar rehte hain — un mein aap ke password/data hain, woh GitHub par nahi jane chahiye.)

## Step 2 — Free database (Neon)
1. **neon.com** → Sign up (GitHub se) → **Create project**: name `surmusic`, Postgres 17, region **AWS Asia Pacific (Singapore)**.
2. Dashboard → **Connect** → **Connection pooling ko OFF** karein → jo string dikhe (`postgresql://…neon.tech/neondb?sslmode=require…`) **copy** karke Notepad mein rakh lein. Yeh password jaisi hai — kisi ko na dein.

## Step 3 — Free website server (Render)
1. **render.com** → Sign up (GitHub se) → GitHub ko `surmusic-web` repository ki ijazat dein.
2. **New +** → **Blueprint** → `surmusic-web` chunein → **Blueprint Path**: `render-free.yaml`.
3. Render yeh values poochega:
   | Naam | Kya likhna hai |
   | --- | --- |
   | `SITE_URL` | `https://surmusic.onrender.com` (baad mein asal address se theek kar sakte hain) |
   | `DATABASE_URL` | Step 2 wali Neon string |
   | `ADMIN_EMAIL` | apni email |
   | `ADMIN_PASSWORD` | naya mazboot password (12+ characters) |
   | `SMTP_…` | khali chhor dein (email baad mein — README §5) |
4. **Apply / Deploy** → 5–10 minute. Upar jo address dikhe (`https://surmusic-xxxx.onrender.com`) kholein.
5. Agar address `SITE_URL` se mukhtalif hai: service → **Environment** → `SITE_URL` theek karein → Save.

## Step 4 — Admin panel
`https://AAPKA-ADDRESS/login` → `ADMIN_EMAIL` + `ADMIN_PASSWORD` → admin dashboard.
Phir Render → Environment → **`ADMIN_PASSWORD` delete** karein → Save (admin account rehta hai; sirf variable hatta hai).

## Step 5 — APK aur Chrome extension
GitHub par apni Android repository → **Releases** → *Draft a new release* → `SurMusic-1.0.0.apk` upload → Publish → APK par right-click → **Copy link** → Admin → **App downloads** → Android ka link wahan paste → Save.

## Step 6 — Website ko jagta rakhna (optional, free)
**uptimerobot.com** → free account → **New monitor** → HTTP(s) → URL: `https://AAPKA-ADDRESS/ping` → har **5 minute**. (`/ping` database ko nahi jagata, is liye Neon ke free hours bachte hain.)

## Update karna
`surmusic-web` mein tabdeeli → GitHub Desktop → **Commit** → **Push origin** → Render khud nayi website laga deta hai.

## Masla ho to
* Render → service → **Logs** (laal lines) ka screenshot bhejein.
* "Admin password bhool gaya": Render → Environment → `ADMIN_EMAIL` mein **nayi** email + `ADMIN_PASSWORD` → Save → us se sign in → purane admin ka password My account / Users se badlein → variable phir delete.
