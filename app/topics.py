"""Radio "types" and countries — each one is its own page with its own words for Google.

Every entry becomes a page:
  kind "genre"   → /genre/<slug>     (Naat, Quran, Qawwali, Pashto, Jazz, News …)
  kind "country" → /country/<slug>   (Pakistan, India, UK, Saudi Arabia …)

Fields
  label   short name for chips and lists
  group   heading on the "All radio stations" page (/radio-stations)
  h1      page heading;  native: the same name in Urdu / Hindi / Arabic script (people search in it too)
  seo_title / description: what Google shows in its results
  intro   first paragraph;  more: a second paragraph under the list with the other ways people search for it
  paths   Radio Browser searches that fill the page (tags, language or country)

Google does not use a hidden "keywords" list; it reads the title, the description and the words on the page.
So the words people type (naat sharif live, quran tilawat radio, pakistani fm …) are written into the text here.
"""
import urllib.parse

COMMON = "hidebroken=true&order=clickcount&reverse=true&limit=100"


def tag(t, extra=""):
    return f"/json/stations/search?tag={urllib.parse.quote(t)}{extra}&{COMMON}"


def lang(language, extra=""):
    return f"/json/stations/search?language={urllib.parse.quote(language)}{extra}&{COMMON}"


def country(code):
    return f"/json/stations/search?countrycode={code}&{COMMON}"


GROUPS = ["Islamic & spiritual", "Sufi, ghazal & classics", "Pakistani & South Asian languages",
          "News, talk & sports", "World music"]
CONTINENTS = {          # slug: (heading, short words for the page text)
    "asia": ("Asia", "Asian"),
    "middle-east": ("Middle East & Gulf", "Middle Eastern and Gulf"),
    "europe": ("Europe", "European"),
    "africa": ("Africa", "African"),
    "north-america": ("North America & Caribbean", "North American and Caribbean"),
    "south-america": ("South America", "South American"),
    "oceania": ("Australia & Oceania", "Australian and Pacific"),
}

TOPICS = {
    # ------------------------------------------------------------------ Islamic & spiritual
    "naat": dict(
        kind="genre", group="Islamic & spiritual", label="Naat",
        h1="Naat Radio — Live Naat Sharif & Hamd", native="نعت شریف ریڈیو",
        seo_title="Naat Radio Live — Naat Sharif, Hamd & Islamic Nasheed Online Free",
        description="Listen to live naat radio free: Naat Sharif, Hamd and nasheed in Urdu, Punjabi and Arabic, around the clock.",
        intro="Live naat stations playing Naat Sharif, Hamd and nasheed day and night — beautiful recitations in Urdu, Punjabi, Arabic and more. Choose a station and let it play while you work, study or rest.",
        more="People find this page searching for naat sharif live, naat radio online, new naats, Urdu naat, Punjabi naat, hamd o naat, Islamic nasheed radio and naat sharif sunna. Every station here is free — no app and no sign-up needed.",
        paths=[tag("naat"), tag("naats"), tag("nasheed")]),
    "quran": dict(
        kind="genre", group="Islamic & spiritual", label="Quran",
        h1="Quran Radio — Live Quran Tilawat & Recitation", native="قرآن پاک تلاوت ریڈیو",
        seo_title="Quran Radio Live — Quran Tilawat & Recitation Online 24/7 Free",
        description="Listen to live Quran radio free: Quran Pak tilawat by famous qaris, recitation with translation, 24 hours a day.",
        intro="Live Quran recitation by well-known qaris, with translations and Islamic programmes, around the clock. Keep the Quran playing at home, in the office or on the go.",
        more="Also searched as Quran Pak live, Quran tilawat radio, Quran recitation online, Quran Sharif sunna, Holy Quran radio 24/7, Quran with Urdu translation and Arabic Quran radio.",
        paths=[tag("quran"), tag("koran"), tag("quran recitation")]),
    "islamic": dict(
        kind="genre", group="Islamic & spiritual", label="Islamic",
        h1="Islamic Radio — Live Bayan, Dars & Islamic Talks", native="اسلامی ریڈیو",
        seo_title="Islamic Radio Live — Bayan, Dars, Islamic Lectures & Nasheed",
        description="Listen to live Islamic radio free: bayan, dars-e-Quran, hadith, Islamic lectures, duas and nasheed from stations worldwide.",
        intro="Live Islamic radio from around the world: bayan and dars, Quran and hadith lessons, Islamic lectures, duas, nasheed and programmes for the whole family.",
        more="Also searched as Islamic radio live, Islamic bayan, Urdu bayan radio, dars e Quran, Islamic lectures online, Islam radio and Muslim radio station.",
        paths=[tag("islamic"), tag("islam"), tag("muslim")]),
    "arabic": dict(
        kind="genre", group="Islamic & spiritual", label="Arabic",
        h1="Arabic Radio — Live Arabic Music, Quran & News", native="راديو عربي مباشر",
        seo_title="Arabic Radio Live — Arabic Songs, Quran & News Online Free",
        description="Listen to live Arabic radio free: Arabic songs, Khaleeji music, Quran and news from Saudi Arabia, UAE, Egypt and more.",
        intro="Live Arabic radio stations from the Gulf, Egypt, the Levant and North Africa — Arabic pop, Khaleeji and classic songs, Quran recitation and Arabic news.",
        more="Also searched as Arabic radio online, Arabic songs radio, Khaleeji radio, Saudi radio, Egypt radio and راديو مباشر.",
        paths=[lang("arabic"), tag("arabic"), tag("arabic music")]),
    "bhajan": dict(
        kind="genre", group="Islamic & spiritual", label="Bhajan",
        h1="Bhajan Radio — Live Bhajans & Devotional Songs", native="भजन रेडियो",
        seo_title="Bhajan Radio Live — Devotional Songs, Aarti & Kirtan Online",
        description="Listen to live bhajan radio free: Hindi bhajans, aarti, kirtan, mantras and devotional songs, 24/7.",
        intro="Live devotional radio: Hindi bhajans, aarti, kirtan, mantras and spiritual songs, playing day and night.",
        more="Also searched as bhajan radio online, devotional songs live, aarti radio, bhakti songs and mantra radio.",
        paths=[tag("bhajan"), tag("devotional"), tag("bhakti")]),
    "gurbani": dict(
        kind="genre", group="Islamic & spiritual", label="Gurbani",
        h1="Gurbani Radio — Live Gurbani Kirtan", native="ਗੁਰਬਾਣੀ ਰੇਡੀਓ",
        seo_title="Gurbani Radio Live — Gurbani Kirtan & Katha Online Free",
        description="Listen to live Gurbani radio free: Gurbani kirtan, katha and Sikh devotional programmes from around the world.",
        intro="Live Gurbani kirtan, katha and Sikh devotional radio, streaming around the clock.",
        more="Also searched as Gurbani live, Gurbani kirtan radio, Sikh radio and Punjabi Gurbani.",
        paths=[tag("gurbani"), tag("sikh"), tag("kirtan")]),

    # ------------------------------------------------------------------ Sufi, ghazal & classics
    "qawwali": dict(
        kind="genre", group="Sufi, ghazal & classics", label="Qawwali",
        h1="Qawwali Radio — Live Sufi Qawwali", native="قوالی ریڈیو",
        seo_title="Qawwali Radio Live — Nusrat Fateh Ali Khan, Sabri Brothers & More",
        description="Listen to live qawwali radio free: classic and modern qawwali from Nusrat Fateh Ali Khan, Sabri Brothers, Aziz Mian and more.",
        intro="Live qawwali from stations that love the tradition — the timeless voices of Nusrat Fateh Ali Khan, the Sabri Brothers, Aziz Mian, Rahat Fateh Ali Khan and today's qawwals.",
        more="Also searched as qawwali live, Nusrat Fateh Ali Khan qawwali, Sufi qawwali radio, old qawwali, qawwali sunna and best qawwali online.",
        paths=[tag("qawwali"), tag("qawali")]),
    "sufi": dict(
        kind="genre", group="Sufi, ghazal & classics", label="Sufi",
        h1="Sufi Music Radio — Live Sufi Kalam", native="صوفی کلام ریڈیو",
        seo_title="Sufi Music Radio Live — Sufi Kalam, Kafi & Dhamal Online",
        description="Listen to live Sufi music radio free: Sufi kalam, kafi, dhamal and spiritual songs from Pakistan and India.",
        intro="Live Sufi music: the poetry of Bulleh Shah, Shah Hussain and Baba Farid, kafi, dhamal and spiritual songs that have been sung for centuries.",
        more="Also searched as Sufi songs live, Sufi kalam, Bulleh Shah kalam, kafi radio, dhamal and Sufi music online.",
        paths=[tag("sufi"), tag("sufi music")]),
    "ghazal": dict(
        kind="genre", group="Sufi, ghazal & classics", label="Ghazal",
        h1="Ghazal Radio — Live Urdu & Hindi Ghazals", native="غزل ریڈیو",
        seo_title="Ghazal Radio Live — Mehdi Hassan, Ghulam Ali, Jagjit Singh",
        description="Listen to live ghazal radio free: Urdu and Hindi ghazals by Mehdi Hassan, Ghulam Ali, Jagjit Singh, Farida Khanum and more.",
        intro="Slow down with live ghazal radio: Urdu and Hindi poetry sung by Mehdi Hassan, Ghulam Ali, Jagjit Singh, Farida Khanum, Iqbal Bano and other masters.",
        more="Also searched as ghazal live, Urdu ghazal, Mehdi Hassan ghazal, Jagjit Singh ghazals, old ghazals and ghazal radio online.",
        paths=[tag("ghazal"), tag("ghazals")]),
    "old-songs": dict(
        kind="genre", group="Sufi, ghazal & classics", label="Old songs",
        h1="Old Songs Radio — Purane Geet Live", native="پرانے گانے · पुराने गाने",
        seo_title="Old Hindi & Urdu Songs Radio Live — Purane Geet Online Free",
        description="Listen to live old songs radio free: golden-era Hindi and Urdu film songs from the 50s to the 90s.",
        intro="Purane geet that never get old: golden-era film songs from Lata, Rafi, Kishore, Noor Jehan, Mehdi Hassan and more.",
        more="Also searched as old Hindi songs, purane gane, old Pakistani songs, Noor Jehan songs, Lata Rafi songs, 70s 80s 90s songs and retro radio.",
        paths=[tag("old hindi songs"), tag("retro"), tag("oldies", "&language=hindi")]),
    "indian-classical": dict(
        kind="genre", group="Sufi, ghazal & classics", label="Classical (raag)",
        h1="Indian Classical Radio — Live Raag, Hindustani & Carnatic", native="शास्त्रीय संगीत",
        seo_title="Indian Classical Music Radio Live — Raag, Hindustani & Carnatic",
        description="Listen to live Indian classical music radio free: raag, Hindustani vocal and instrumental, sitar, Carnatic music.",
        intro="Live classical music of the subcontinent: raag and khayal, sitar, sarod, flute and Carnatic concerts.",
        more="Also searched as raag radio, Hindustani classical music, sitar music, Carnatic radio and classical music India.",
        paths=[tag("indian classical"), tag("hindustani"), tag("carnatic")]),

    # ------------------------------------------------------------------ Pakistani & South Asian languages
    "punjabi": dict(
        kind="genre", group="Pakistani & South Asian languages", label="Punjabi",
        h1="Punjabi Radio — Live Punjabi Songs & Bhangra", native="پنجابی ریڈیو · ਪੰਜਾਬੀ ਰੇਡੀਓ",
        seo_title="Punjabi Radio Live — Punjabi Songs, Bhangra & Lok Geet",
        description="Listen to live Punjabi radio free: new Punjabi songs, bhangra, folk lok geet and classic hits.",
        intro="Live Punjabi radio: new Punjabi pop, bhangra beats, folk lok geet and the classics — from both sides of Punjab and the Punjabi diaspora.",
        more="Also searched as Punjabi songs live, Punjabi FM, bhangra radio, Punjabi radio Canada, Punjabi radio UK and Punjabi lok geet.",
        paths=[tag("punjabi"), tag("bhangra"), lang("punjabi")]),
    "pashto": dict(
        kind="genre", group="Pakistani & South Asian languages", label="Pashto",
        h1="Pashto Radio — Live Pashto Songs & News", native="پښتو راډیو",
        seo_title="Pashto Radio Live — Pashto Songs, Tappay & Pashto News",
        description="Listen to live Pashto radio free: Pashto songs, tappay, ghazals and Pashto news from Pakistan and Afghanistan.",
        intro="Live Pashto radio from Peshawar, Khyber Pakhtunkhwa, Quetta and Afghanistan — Pashto songs, tappay, Rahman Baba poetry and news.",
        more="Also searched as Pashto songs live, Pashto FM, Pashto radio online, Pashto news and پښتو سندرې.",
        paths=[lang("pashto"), tag("pashto"), tag("pushto")]),
    "sindhi": dict(
        kind="genre", group="Pakistani & South Asian languages", label="Sindhi",
        h1="Sindhi Radio — Live Sindhi Songs & Sufi Kalam", native="سنڌي ريڊيو",
        seo_title="Sindhi Radio Live — Sindhi Songs, Shah Latif Kalam & News",
        description="Listen to live Sindhi radio free: Sindhi songs, Shah Abdul Latif Bhittai kalam and Sindhi programmes.",
        intro="Live Sindhi radio: Sindhi songs, Sufi kalam of Shah Abdul Latif Bhittai and Sachal Sarmast, and programmes from Sindh.",
        more="Also searched as Sindhi songs live, Sindhi FM, Sindhi radio online and Shah Latif kalam.",
        paths=[lang("sindhi"), tag("sindhi")]),
    "bengali": dict(
        kind="genre", group="Pakistani & South Asian languages", label="Bangla",
        h1="Bangla Radio — Live Bengali Songs & News", native="বাংলা রেডিও",
        seo_title="Bangla Radio Live — Bengali Songs, FM & News Online Free",
        description="Listen to live Bangla radio free: Bengali songs, Bangladesh FM stations, Kolkata radio and Bangla news.",
        intro="Live Bengali radio from Bangladesh and West Bengal — Bangla songs, Rabindra Sangeet, FM hits and news.",
        more="Also searched as Bangla radio online, Bangladesh FM, Bengali songs live and Kolkata FM.",
        paths=[lang("bengali"), tag("bangla"), tag("bengali")]),
    "tamil": dict(
        kind="genre", group="Pakistani & South Asian languages", label="Tamil",
        h1="Tamil Radio — Live Tamil Songs", native="தமிழ் வானொலி",
        seo_title="Tamil Radio Live — Tamil Songs & Tamil FM Online Free",
        description="Listen to live Tamil radio free: Tamil film songs, Ilaiyaraaja and A. R. Rahman hits and Tamil FM stations.",
        intro="Live Tamil radio from Tamil Nadu, Sri Lanka and the diaspora — film songs, classics and Tamil FM.",
        more="Also searched as Tamil FM live, Tamil songs radio and Tamil radio online.",
        paths=[lang("tamil"), tag("tamil")]),
    "telugu": dict(
        kind="genre", group="Pakistani & South Asian languages", label="Telugu",
        h1="Telugu Radio — Live Telugu Songs", native="తెలుగు రేడియో",
        seo_title="Telugu Radio Live — Telugu Songs & FM Online Free",
        description="Listen to live Telugu radio free: Telugu film songs, old and new hits, devotional songs and Telugu FM.",
        intro="Live Telugu radio — Tollywood film songs, melodies, devotional music and FM stations.",
        more="Also searched as Telugu FM live, Telugu songs radio and Telugu radio online.",
        paths=[lang("telugu"), tag("telugu")]),
    "malayalam": dict(
        kind="genre", group="Pakistani & South Asian languages", label="Malayalam",
        h1="Malayalam Radio — Live Malayalam Songs", native="മലയാളം റേഡിയോ",
        seo_title="Malayalam Radio Live — Malayalam Songs & FM Online Free",
        description="Listen to live Malayalam radio free: Malayalam film songs, Gulf Malayalam radio and Kerala FM stations.",
        intro="Live Malayalam radio from Kerala and the Gulf — film songs, melodies and Malayalam FM.",
        more="Also searched as Malayalam FM live, Malayalam songs radio and Gulf Malayalam radio.",
        paths=[lang("malayalam"), tag("malayalam")]),
    "marathi": dict(
        kind="genre", group="Pakistani & South Asian languages", label="Marathi",
        h1="Marathi Radio — Live Marathi Songs", native="मराठी रेडिओ",
        seo_title="Marathi Radio Live — Marathi Songs & FM Online Free",
        description="Listen to live Marathi radio free: Marathi film songs, natya sangeet, bhavgeet and Marathi FM.",
        intro="Live Marathi radio — film songs, bhavgeet, natya sangeet and FM stations from Maharashtra.",
        more="Also searched as Marathi FM live and Marathi songs radio.",
        paths=[lang("marathi"), tag("marathi")]),
    "gujarati": dict(
        kind="genre", group="Pakistani & South Asian languages", label="Gujarati",
        h1="Gujarati Radio — Live Gujarati Songs & Garba", native="ગુજરાતી રેડિયો",
        seo_title="Gujarati Radio Live — Gujarati Songs, Garba & FM Online",
        description="Listen to live Gujarati radio free: Gujarati songs, garba, bhajans and Gujarati FM stations.",
        intro="Live Gujarati radio — songs, garba, folk music and bhajans from Gujarat and the diaspora.",
        more="Also searched as Gujarati FM live, garba radio and Gujarati songs online.",
        paths=[lang("gujarati"), tag("gujarati")]),

    # ------------------------------------------------------------------ News, talk & sports
    "news": dict(
        kind="genre", group="News, talk & sports", label="Urdu news",
        h1="Urdu & Hindi News Radio — Live", native="اردو خبریں · हिंदी समाचार",
        seo_title="Urdu News Radio Live — Pakistani & Hindi News Online",
        description="Listen to live Urdu and Hindi news radio free: news, current affairs and talk from Pakistan and India.",
        intro="Live news and current affairs in Urdu and Hindi from radio stations in Pakistan and India.",
        more="Also searched as Urdu news live, Pakistan news radio, Hindi samachar, khabrein, Pakistani news live and Urdu FM news.",
        paths=[tag("news", "&language=urdu"), tag("news", "&countrycode=PK"), tag("news", "&language=hindi")]),
    "english-news": dict(
        kind="genre", group="News, talk & sports", label="World news",
        h1="World News Radio — Live English News & Talk", native="",
        seo_title="World News Radio Live — English News, Talk & Current Affairs",
        description="Listen to live English news radio free: world news, business, current affairs and talk stations from the UK, USA and beyond.",
        intro="Live English-language news and talk radio: world headlines, business, politics, science and current affairs from stations around the globe.",
        more="Also searched as news radio live, world news online, English news radio, talk radio and breaking news radio.",
        paths=[tag("news", "&language=english"), tag("talk", "&language=english"), tag("world news")]),
    "sports": dict(
        kind="genre", group="News, talk & sports", label="Sports & cricket",
        h1="Sports & Cricket Radio — Live Commentary & Talk", native="کرکٹ ریڈیو",
        seo_title="Sports & Cricket Radio Live — Commentary, Football & Sports Talk",
        description="Listen to live sports radio free: cricket, football and sports talk stations with live commentary when matches are on.",
        intro="Live sports radio: cricket and football talk, sports news and live commentary (when the station carries the match).",
        more="Also searched as cricket radio live, cricket commentary radio, sports radio online and football radio.",
        paths=[tag("sports"), tag("cricket"), tag("football")]),

    # ------------------------------------------------------------------ World music
    "pop": dict(
        kind="genre", group="World music", label="Pop",
        h1="Pop Music Radio — Live Pop Hits", native="",
        seo_title="Pop Radio Live — Top Pop Hits Online Free",
        description="Listen to live pop radio free: today's pop hits, chart toppers and pop classics from stations worldwide.",
        intro="Live pop music radio — the latest hits, chart toppers and favourite pop songs from around the world.",
        more="Also searched as pop radio online, top hits radio, chart music live and pop songs radio.",
        paths=[tag("pop")]),
    "rock": dict(
        kind="genre", group="World music", label="Rock",
        h1="Rock Radio — Live Rock & Classic Rock", native="",
        seo_title="Rock Radio Live — Classic Rock, Alternative & Metal Online",
        description="Listen to live rock radio free: classic rock, alternative, hard rock and metal stations.",
        intro="Live rock radio: classic rock anthems, alternative, indie, hard rock and metal.",
        more="Also searched as rock radio online, classic rock live and alternative radio.",
        paths=[tag("rock"), tag("classic rock")]),
    "jazz": dict(
        kind="genre", group="World music", label="Jazz",
        h1="Jazz Radio — Live Jazz, Blues & Smooth Jazz", native="",
        seo_title="Jazz Radio Live — Smooth Jazz, Blues & Classic Jazz Online",
        description="Listen to live jazz radio free: smooth jazz, classic jazz, blues and soul, 24/7.",
        intro="Live jazz radio — smooth jazz for work and study, classic jazz, blues and soul.",
        more="Also searched as smooth jazz radio, jazz music online and blues radio.",
        paths=[tag("jazz"), tag("smooth jazz"), tag("blues")]),
    "classical": dict(
        kind="genre", group="World music", label="Classical",
        h1="Classical Music Radio — Live Orchestra & Piano", native="",
        seo_title="Classical Music Radio Live — Mozart, Beethoven, Piano & Orchestra",
        description="Listen to live classical music radio free: orchestra, piano, opera and relaxing classical music.",
        intro="Live classical radio — symphonies, piano, violin and opera from Mozart, Beethoven, Bach and more. Great for focus and calm.",
        more="Also searched as classical radio online, piano music radio and music for studying.",
        paths=[tag("classical"), tag("piano")]),
    "lofi": dict(
        kind="genre", group="World music", label="Lo-fi & chill",
        h1="Lo-fi & Chill Radio — Music for Study, Sleep & Relax", native="",
        seo_title="Lo-fi Radio Live — Chill Beats to Study, Relax & Sleep",
        description="Listen to live lo-fi and chill radio free: lofi beats, chillout, ambient and relaxing music for study and sleep.",
        intro="Live lo-fi and chill radio — calm beats, chillout, ambient and lounge music to study, work, relax or sleep.",
        more="Also searched as lofi radio, chill music live, study music, sleep music and relaxing radio.",
        paths=[tag("lofi"), tag("chillout"), tag("ambient")]),
    "dance": dict(
        kind="genre", group="World music", label="Dance & EDM",
        h1="Dance & EDM Radio — Live House, Trance & Electronic", native="",
        seo_title="Dance Radio Live — EDM, House, Trance & Electronic Music",
        description="Listen to live dance and EDM radio free: house, trance, techno and electronic hits.",
        intro="Live dance radio: EDM, house, trance, techno and electronic party music.",
        more="Also searched as EDM radio, house music live, trance radio and electronic music online.",
        paths=[tag("dance"), tag("electronic"), tag("house")]),
    "hip-hop": dict(
        kind="genre", group="World music", label="Hip-hop & R&B",
        h1="Hip-hop & R&B Radio — Live Rap & R&B Hits", native="",
        seo_title="Hip-hop Radio Live — Rap, R&B & Urban Hits Online",
        description="Listen to live hip-hop and R&B radio free: rap, R&B, urban hits and desi hip-hop.",
        intro="Live hip-hop and R&B radio — rap, R&B, urban and trap from around the world.",
        more="Also searched as rap radio, R&B radio online and hip hop music live.",
        paths=[tag("hip hop"), tag("rnb"), tag("rap")]),
    "country-music": dict(
        kind="genre", group="World music", label="Country",
        h1="Country Music Radio — Live Country Hits", native="",
        seo_title="Country Music Radio Live — New & Classic Country Online",
        description="Listen to live country music radio free: new country hits and classic country favourites.",
        intro="Live country music radio — today's country hits and the classics.",
        more="Also searched as country radio online and country songs live.",
        paths=[tag("country")]),

    "talk": dict(
        kind="genre", group="News, talk & sports", label="Talk radio",
        h1="Talk Radio — Live Talk Shows & Phone-ins", native="",
        seo_title="Talk Radio Live — Talk Shows, Interviews & Phone-ins Online",
        description="Listen to live talk radio free: talk shows, interviews, debates and phone-in programmes from the USA, UK and around the world.",
        intro="Live talk radio — talk shows, interviews, call-ins, debates and spoken-word programmes. Great company for driving, working or relaxing, and easy to follow without a screen.",
        more="Also searched as talk radio online, talk shows live, spoken word radio and AM talk radio.",
        paths=[tag("talk"), tag("talk radio")]),
    "christian": dict(
        kind="genre", group="Islamic & spiritual", label="Christian",
        h1="Christian Radio — Live Worship, Gospel & Sermons", native="",
        seo_title="Christian Radio Live — Worship Music, Gospel & Sermons Online",
        description="Listen to live Christian radio free: worship music, gospel, contemporary Christian hits, sermons and Bible teaching.",
        intro="Live Christian radio — praise and worship, gospel, contemporary Christian music, hymns, sermons and Bible teaching from stations around the world.",
        more="Also searched as Christian music radio, gospel radio live, worship radio and Bible radio.",
        paths=[tag("christian"), tag("gospel"), tag("worship")]),
    "latin": dict(
        kind="genre", group="World music", label="Latin",
        h1="Latin Radio — Live Reggaeton, Salsa & Latin Pop", native="Radio latina",
        seo_title="Latin Radio Live — Reggaeton, Salsa, Bachata & Latin Pop",
        description="Listen to live Latin radio free: reggaeton, salsa, bachata, regional Mexican and Latin pop stations.",
        intro="Live Latin radio — reggaeton, salsa, bachata, cumbia, regional Mexican and Latin pop from the USA, Mexico, Spain and Latin America.",
        more="Also searched as radio latina en vivo, reggaeton radio, salsa radio and Spanish radio online.",
        paths=[tag("latin"), tag("reggaeton"), tag("salsa")]),
    "80s-90s": dict(
        kind="genre", group="World music", label="80s & 90s",
        h1="80s & 90s Radio — Live Retro Hits", native="",
        seo_title="80s & 90s Radio Live — Retro Hits & Classic Pop Online",
        description="Listen to live 80s and 90s radio free: the biggest retro hits, classic pop, rock and dance from both decades.",
        intro="Live 80s and 90s radio — retro pop, rock, dance and the classic hits you grew up with.",
        more="Also searched as 80s radio, 90s radio, oldies radio, retro hits and classic hits radio.",
        paths=[tag("80s"), tag("90s"), tag("oldies")]),
    "reggae": dict(
        kind="genre", group="World music", label="Reggae",
        h1="Reggae Radio — Live Reggae & Dancehall", native="",
        seo_title="Reggae Radio Live — Roots Reggae, Dancehall & Afrobeats",
        description="Listen to live reggae radio free: roots reggae, dancehall, dub and Caribbean music.",
        intro="Live reggae radio — roots reggae, dancehall, dub and the sound of the Caribbean.",
        more="Also searched as reggae radio online, dancehall radio and Jamaican radio.",
        paths=[tag("reggae"), tag("dancehall")]),
    "afrobeats": dict(
        kind="genre", group="World music", label="Afrobeats",
        h1="Afrobeats Radio — Live African Music", native="",
        seo_title="Afrobeats Radio Live — Afrobeats, Amapiano & African Music",
        description="Listen to live Afrobeats radio free: Afrobeats, amapiano, highlife, bongo and African hits.",
        intro="Live African music radio — Afrobeats, amapiano, highlife, bongo flava and the hits of Nigeria, Ghana, South Africa and Kenya.",
        more="Also searched as Afrobeats radio, amapiano radio, African music radio and Naija radio.",
        paths=[tag("afrobeats"), tag("afrobeat"), tag("african")]),
    "metal": dict(
        kind="genre", group="World music", label="Metal",
        h1="Metal Radio — Live Heavy Metal & Hard Rock", native="",
        seo_title="Metal Radio Live — Heavy Metal, Hard Rock & Metalcore",
        description="Listen to live metal radio free: heavy metal, hard rock, thrash and metalcore stations.",
        intro="Live metal radio — heavy metal, hard rock, thrash, power metal and metalcore.",
        more="Also searched as heavy metal radio and hard rock radio online.",
        paths=[tag("metal"), tag("heavy metal"), tag("hard rock")]),
    "k-pop": dict(
        kind="genre", group="World music", label="K-pop & J-pop",
        h1="K-pop & J-pop Radio — Live Korean & Japanese Pop", native="케이팝 · Jポップ",
        seo_title="K-pop Radio Live — Korean Pop, J-pop & Anime Music",
        description="Listen to live K-pop and J-pop radio free: Korean pop, Japanese pop and anime songs.",
        intro="Live K-pop and J-pop radio — the latest Korean and Japanese pop, idol groups and anime songs.",
        more="Also searched as K-pop radio, Korean music radio, J-pop radio and anime radio.",
        paths=[tag("kpop"), tag("k-pop"), tag("jpop")]),

    # ------------------------------------------------------------------ Countries
    "pakistan": dict(
        kind="country", group="", label="Pakistan",
        h1="Pakistan Radio — Live Pakistani FM Stations", native="پاکستانی ریڈیو",
        seo_title="Pakistan Radio Live — Pakistani FM Stations Online Free",
        description="Listen to live Pakistani radio free: FM stations from Lahore, Karachi, Islamabad and all of Pakistan — music, news and more.",
        intro="All the live radio stations from Pakistan we can play in your browser: FM music stations, Urdu and Punjabi songs, news, naat and more from Lahore, Karachi, Islamabad, Peshawar, Quetta and beyond.",
        more="Also searched as Pakistani radio online, Pakistan FM live, FM 100 Pakistan, Radio Pakistan live, Lahore FM, Karachi FM and Islamabad FM.",
        paths=[country("PK")]),
    "india": dict(
        kind="country", group="", label="India",
        h1="India Radio — Live Indian FM Stations", native="भारतीय रेडियो",
        seo_title="India Radio Live — Indian FM Stations Online Free",
        description="Listen to live Indian radio free: FM stations from Mumbai, Delhi and across India — Hindi songs, regional music and news.",
        intro="Live radio from India: Hindi FM, Bollywood hits, regional language stations, devotional music and news.",
        more="Also searched as Indian radio online, India FM live, Hindi FM and Mumbai FM.",
        paths=[country("IN")]),
    "bangladesh": dict(
        kind="country", group="", label="Bangladesh",
        h1="Bangladesh Radio — Live Bangladeshi FM", native="বাংলাদেশ রেডিও",
        seo_title="Bangladesh Radio Live — Bangladeshi FM Stations Online",
        description="Listen to live Bangladeshi radio free: FM stations from Dhaka and across Bangladesh.",
        intro="Live radio from Bangladesh — Bangla songs, FM hits and news from Dhaka and beyond.",
        more="Also searched as Bangladesh FM live and Dhaka FM.",
        paths=[country("BD")]),
    "afghanistan": dict(
        kind="country", group="", label="Afghanistan",
        h1="Afghanistan Radio — Live Afghan Stations", native="د افغانستان راډیو",
        seo_title="Afghanistan Radio Live — Afghan Pashto & Dari Stations",
        description="Listen to live Afghan radio free: Pashto and Dari music, news and programmes from Afghanistan.",
        intro="Live radio from Afghanistan — Pashto and Dari songs, Afghan music and news.",
        more="Also searched as Afghan radio online, Afghan songs and Dari radio.",
        paths=[country("AF")]),
    "saudi-arabia": dict(
        kind="country", group="", label="Saudi Arabia",
        h1="Saudi Arabia Radio — Live Saudi Stations", native="راديو السعودية",
        seo_title="Saudi Arabia Radio Live — Saudi FM, Quran & Arabic Stations",
        description="Listen to live Saudi radio free: Quran radio from Makkah, Arabic music and news stations from Saudi Arabia.",
        intro="Live radio from Saudi Arabia — Quran stations, Arabic and Khaleeji music and news. Also useful for Pakistanis and Indians living in the Kingdom.",
        more="Also searched as Saudi radio online, Makkah radio live and Saudi FM.",
        paths=[country("SA")]),
    "uae": dict(
        kind="country", group="", label="UAE (Dubai)",
        h1="UAE Radio — Live Dubai & Abu Dhabi Stations", native="راديو الإمارات",
        seo_title="UAE Radio Live — Dubai FM, Hindi, Urdu & Arabic Stations",
        description="Listen to live UAE radio free: Dubai and Abu Dhabi FM stations in Arabic, English, Hindi, Urdu and Malayalam.",
        intro="Live radio from the UAE — Dubai and Abu Dhabi FM stations in Arabic, English, Hindi, Urdu and Malayalam.",
        more="Also searched as Dubai radio online, Dubai FM live, UAE Hindi radio and Abu Dhabi radio.",
        paths=[country("AE")]),
    "qatar": dict(
        kind="country", group="", label="Qatar",
        h1="Qatar Radio — Live Doha Stations", native="راديو قطر",
        seo_title="Qatar Radio Live — Doha FM Stations Online",
        description="Listen to live Qatar radio free: Doha FM stations, Arabic music, Quran and news.",
        intro="Live radio from Qatar — Arabic music, Quran and news from Doha.",
        more="Also searched as Qatar FM and Doha radio online.",
        paths=[country("QA")]),
    "oman": dict(
        kind="country", group="", label="Oman",
        h1="Oman Radio — Live Omani Stations", native="راديو عمان",
        seo_title="Oman Radio Live — Muscat FM Stations Online",
        description="Listen to live Oman radio free: Muscat FM stations, Arabic music and news.",
        intro="Live radio from Oman — Arabic music, Quran and news from Muscat and beyond.",
        more="Also searched as Oman FM and Muscat radio.",
        paths=[country("OM")]),
    "uk": dict(
        kind="country", group="", label="UK",
        h1="UK Radio — Live British Stations", native="",
        seo_title="UK Radio Live — British Radio Stations Online Free",
        description="Listen to live UK radio free: British music, news and talk stations, plus Asian radio stations from the UK.",
        intro="Live radio from the United Kingdom — pop, rock, news and talk, and the UK's Asian, Urdu and Punjabi stations.",
        more="Also searched as UK radio online, British radio live, London radio and UK Asian radio.",
        paths=[country("GB")]),
    "usa": dict(
        kind="country", group="", label="USA",
        h1="USA Radio — Live American Stations", native="",
        seo_title="USA Radio Live — American Radio Stations Online Free",
        description="Listen to live American radio free: US music, news, talk and sports stations.",
        intro="Live radio from the United States — hits, country, rock, jazz, news, talk and sports.",
        more="Also searched as American radio online, US radio live and New York radio.",
        paths=[country("US")]),
    "canada": dict(
        kind="country", group="", label="Canada",
        h1="Canada Radio — Live Canadian Stations", native="",
        seo_title="Canada Radio Live — Canadian Radio Stations Online Free",
        description="Listen to live Canadian radio free: music, news and talk, including Punjabi and South Asian stations in Canada.",
        intro="Live radio from Canada — music, news and talk, and Canada's Punjabi, Hindi and Urdu stations.",
        more="Also searched as Canadian radio online, Toronto radio and Punjabi radio Canada.",
        paths=[country("CA")]),
    "australia": dict(
        kind="country", group="", label="Australia",
        h1="Australia Radio — Live Australian Stations", native="",
        seo_title="Australia Radio Live — Australian Radio Stations Online Free",
        description="Listen to live Australian radio free: music, news and talk stations from across Australia.",
        intro="Live radio from Australia — hits, news and talk, and community stations.",
        more="Also searched as Australian radio online and Sydney radio.",
        paths=[country("AU")]),
    "turkey": dict(
        kind="country", group="", label="Turkey",
        h1="Turkey Radio — Live Turkish Stations", native="Türk radyosu",
        seo_title="Turkish Radio Live — Turkey Radio Stations Online Free",
        description="Listen to live Turkish radio free: Turkish pop, folk, arabesque and news from Turkey.",
        intro="Live radio from Turkey — Turkish pop, folk, arabesque and news.",
        more="Also searched as Turkish radio online and Türkçe radyo canlı.",
        paths=[country("TR")]),
    "germany": dict(
        kind="country", group="", label="Germany",
        h1="Germany Radio — Live German Stations", native="Deutsches Radio",
        seo_title="German Radio Live — Germany Radio Stations Online Free",
        description="Listen to live German radio free: music, news and talk from Germany.",
        intro="Live radio from Germany — pop, rock, schlager, news and talk.",
        more="Also searched as German radio online and Radio Deutschland live.",
        paths=[country("DE")]),
    "france": dict(
        kind="country", group="", label="France",
        h1="France Radio — Live French Stations", native="Radio française",
        seo_title="French Radio Live — France Radio Stations Online Free",
        description="Listen to live French radio free: music, news and talk from France.",
        intro="Live radio from France — French pop, chanson, news and talk.",
        more="Also searched as French radio online and radio France en direct.",
        paths=[country("FR")]),
}


# ---------------------------------------------------------------- every other country in the world (generated)

_MIDDLE_EAST = set("AE BH CY EG IL IQ IR JO KW LB OM PS QA SA SY TR YE".split())
_SOUTH_AMERICA = set("AR BO BR CL CO EC FK GF GY PE PY SR UY VE".split())
_FIX = {"IS": "europe", "FO": "europe", "PT": "europe", "XK": "europe", "GL": "north-america", "BM": "north-america",
        "CV": "africa", "SH": "africa", "MG": "africa", "KM": "africa", "MU": "africa", "SC": "africa",
        "RE": "africa", "YT": "africa", "MV": "asia", "IO": "asia", "CC": "asia", "CX": "asia"}
_SKIP = {"AQ", "BV", "HM", "TF", "UM", "GS", "AC", "CP", "DG", "TA", "EA", "IC", "CQ", "EU", "EZ", "UN", "ZZ",
         "QO", "XA", "XB", "SJ", "PN"}
_ZONE_TO = {"Asia": "asia", "Europe": "europe", "Africa": "africa", "America": "north-america",
            "Australia": "oceania", "Pacific": "oceania"}


def _slug(text):
    import re
    import unicodedata
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower().replace("&", "and")).strip("-")


def _world():
    """{code: (english name, continent slug, name in the country's own language)} for every country."""
    try:
        from babel import Locale
        from babel.core import get_global
    except ImportError:  # pragma: no cover
        return {}
    zones, languages = get_global("territory_zones"), get_global("territory_languages")
    out = {}
    for code, name in Locale("en").territories.items():
        if len(code) != 2 or not code.isalpha() or code in _SKIP:
            continue
        if code in _FIX:
            cont = _FIX[code]
        elif code in _MIDDLE_EAST:
            cont = "middle-east"
        elif code in _SOUTH_AMERICA:
            cont = "south-america"
        else:
            heads = [z.split("/")[0] for z in zones.get(code) or []]
            main = [h for h in heads if h in ("Asia", "Europe", "Africa", "America", "Australia")] or heads
            cont = _ZONE_TO.get(max(set(main), key=main.count)) if main else None
        if not cont:
            continue
        native = ""
        official = sorted(((v.get("population_percent", 0), lang) for lang, v in (languages.get(code) or {}).items()
                           if v.get("official_status")), reverse=True)
        if official:
            try:
                native = Locale.parse(official[0][1]).territories.get(code, "")
            except Exception:
                native = ""
        out[code] = (name, cont, native if native and native != name else "")
    return out


WORLD = _world()
_HAND = {"PK": "pakistan", "IN": "india", "BD": "bangladesh", "AF": "afghanistan", "SA": "saudi-arabia",
         "AE": "uae", "QA": "qatar", "OM": "oman", "GB": "uk", "US": "usa", "CA": "canada", "AU": "australia",
         "TR": "turkey", "DE": "germany", "FR": "france"}
COUNTRY_CODES = {}                                  # slug -> ISO code (for station counts)
for _code, (_name, _cont, _native) in sorted(WORLD.items(), key=lambda kv: kv[1][0]):
    if _code in _HAND:
        _t = TOPICS[_HAND[_code]]
        _t["group"], _t["code"] = _cont, _code
        COUNTRY_CODES[_HAND[_code]] = _code
        continue
    _s = _slug(_name)
    if not _s or _s in TOPICS:
        continue
    _also = f"radio {_native}, " if _native else ""
    TOPICS[_s] = dict(
        kind="country", group=_cont, code=_code, label=_name,
        h1=f"{_name} Radio — Live Radio Stations from {_name}", native=_native,
        seo_title=f"{_name} Radio Live — Listen to {_name} Radio Stations Online Free",
        description=f"Listen to live radio from {_name} free: music, news and talk stations from {_name}, "
                    "playing right in your browser — no app and no sign-up.",
        intro=f"All the live radio stations from {_name} that play in your browser: music, news, talk, sports and "
              f"local FM. Pick a station, press play and keep browsing — the music keeps going.",
        more=f"Also searched as {_name} radio online, {_name} FM live, {_name} radio stations, {_also}"
             f"live radio {_name} and {CONTINENTS[_cont][1]} radio.",
        paths=[country(_code)])
    COUNTRY_CODES[_s] = _code

for _k, _t in TOPICS.items():                       # a hand-written country Babel did not know
    if _t["kind"] == "country" and not _t["group"]:
        _t["group"] = "asia"

GENRE_PAGES = {k: v for k, v in TOPICS.items() if v["kind"] == "genre"}
COUNTRY_PAGES = {k: v for k, v in TOPICS.items() if v["kind"] == "country"}
CHIPS = ["naat", "quran", "islamic", "qawwali", "ghazal", "sufi", "punjabi", "pashto", "old-songs", "news",
         "lofi", "pakistan"]


def topic_path(slug):
    t = TOPICS[slug]
    return f"/country/{slug}" if t["kind"] == "country" else f"/genre/{slug}"


def grouped():
    """[(group heading, [(slug, topic), …]), …] — radio types (for the "All radio stations" page)."""
    return [(g, [(k, v) for k, v in TOPICS.items() if v["group"] == g]) for g in GROUPS]


def countries_in(continent):
    """[(slug, topic)] of one continent, A–Z."""
    return sorted(((k, v) for k, v in COUNTRY_PAGES.items() if v["group"] == continent), key=lambda kv: kv[1]["label"])
