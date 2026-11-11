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

COMMON = "hidebroken=true&order=clickcount&reverse=true&limit=300"


def tag(t, extra=""):
    return f"/json/stations/search?tag={urllib.parse.quote(t)}{extra}&{COMMON}"


def name(n, extra=""):
    return f"/json/stations/search?name={urllib.parse.quote(n)}{extra}&{COMMON}"


def lang(language, extra=""):
    return f"/json/stations/search?language={urllib.parse.quote(language)}{extra}&{COMMON}"


def country(code):
    return f"/json/stations/search?countrycode={code}&{COMMON}"


GROUPS = ["Islamic & spiritual", "Sufi, ghazal & classics", "Pakistani & South Asian languages",
          "News, talk & sports", "World music", "Lifestyle & learning", "World languages", "Cities"]
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
        seo_title="Naat Radio Live — Naat Sharif, Hamd & Nasheed Online Free",
        description="Listen to live naat radio free: Naat Sharif, Hamd and nasheed in Urdu, Punjabi and Arabic, around the clock.",
        intro="Live naat stations playing Naat Sharif, Hamd and nasheed day and night — beautiful recitations in Urdu, Punjabi, Arabic and more. Choose a station and let it play while you work, study or rest.",
        more="People find this page searching for naat sharif live, naat radio online, new naats, Urdu naat, Punjabi naat, hamd o naat, Islamic nasheed radio, naat sharif sunna, naat sharif sunao, new naat 2026 and the Urdu words نعت شریف, نعت ریڈیو and حمد و نعت. Every station here is free — no app and no sign-up needed.",
        paths=[tag("naat"), tag("naats"), tag("nasheed")]),
    "quran": dict(
        kind="genre", group="Islamic & spiritual", label="Quran",
        h1="Quran Radio — Live Quran Tilawat & Recitation", native="قرآن پاک تلاوت ریڈیو",
        seo_title="Quran Radio Live — Quran Tilawat & Recitation 24/7 Free",
        description="Listen to live Quran radio free: Quran Pak tilawat by famous qaris, recitation with translation, 24 hours a day.",
        intro="Live Quran recitation by well-known qaris, with translations and Islamic programmes, around the clock. Keep the Quran playing at home, in the office or on the go.",
        more="Also searched as Quran Pak live, Quran tilawat radio, Quran recitation online, Quran Sharif sunna, Holy Quran radio 24/7, Quran with Urdu translation, Arabic Quran radio, Quran Pak sunao, tilawat e Quran live and the Urdu words قرآن پاک, تلاوت قرآن and قرآن ریڈیو.",
        paths=[tag("quran"), tag("koran"), tag("quran recitation"), tag("tilawat"), name("quran"), name("qur'an"),
               name("holy quran"), name("quran majeed"), name("tilawat"), name("قرآن"), name("قران"), tag("quran", "&countrycode=PK"),
               tag("quran", "&countrycode=SA"), tag("quran", "&countrycode=EG"), tag("quran", "&countrycode=IR")]),
    "islamic": dict(
        kind="genre", group="Islamic & spiritual", label="Islamic",
        h1="Islamic Radio — Live Bayan, Dars & Islamic Talks", native="اسلامی ریڈیو",
        seo_title="Islamic Radio Live — Bayan, Dars, Islamic Lectures & Nasheed",
        description="Listen to live Islamic radio free: bayan, dars-e-Quran, hadith, Islamic lectures, duas and nasheed from stations worldwide.",
        intro="Live Islamic radio from around the world: Quran recitation, naat sharif, bayan and dars, hadith lessons, Islamic lectures, duas, nasheed and programmes for the whole family.",
        more="Also searched as Islamic radio live, Islamic bayan, Urdu bayan radio, dars e Quran, Quran radio, naat radio, Islamic lectures online, Islam radio and Muslim radio station.",
        paths=[tag("islamic"), tag("islam"), tag("muslim"), tag("islamic", "&countrycode=PK"), tag("religion", "&countrycode=PK"),
               tag("bayan"), name("bayan"), name("islamic")]),
    "pakistan-islamic": dict(
        kind="genre", group="Islamic & spiritual", label="Pakistani Islamic",
        h1="Pakistani Islamic Radio — Live Bayan, Naat & Quran from Pakistan", native="پاکستانی اسلامی ریڈیو",
        seo_title="Pakistani Islamic Radio Live — Bayan, Naat & Quran",
        description="Listen to live Pakistani Islamic radio free: Urdu bayan, naat, Quran tilawat, dars and Islamic programmes from stations in Pakistan.",
        intro="Live Islamic radio from Pakistan: Urdu bayan and taqreer, naat sharif, Quran tilawat, dars and religious programmes from stations across the country.",
        more="Also searched as Pakistani Islamic radio, Urdu Islamic radio, Pakistan Quran radio, Urdu bayan live, Islamic FM Pakistan and the Urdu words اسلامی ریڈیو پاکستان.",
        paths=[tag("islamic", "&countrycode=PK"), tag("quran", "&countrycode=PK"), tag("naat", "&countrycode=PK"),
               tag("religion", "&countrycode=PK"), tag("religious", "&countrycode=PK"), name("islam", "&countrycode=PK"),
               name("quran", "&countrycode=PK"), name("naat", "&countrycode=PK"), name("noor", "&countrycode=PK"),
               name("madni", "&countrycode=PK"), name("paigham", "&countrycode=PK"), name("deen", "&countrycode=PK"),
               name("huda", "&countrycode=PK"), name("rehmat", "&countrycode=PK"), name("hamd", "&countrycode=PK"),
               name("tilawat", "&countrycode=PK"), name("islamic", "&countrycode=PK"), name("ummat", "&countrycode=PK"),
               lang("urdu", "&tag=islamic"), lang("punjabi", "&tag=islamic")]),
    "bayan": dict(
        kind="genre", group="Islamic & spiritual", label="Bayan & Taqreer",
        h1="Bayan & Taqreer Radio — Live Urdu Islamic Lectures", native="بیان اور تقریر ریڈیو",
        seo_title="Bayan Radio Live — Urdu Bayan, Taqreer & Islamic Dars",
        description="Listen to live bayan radio free: Urdu bayan, taqreer, dars, Islamic lectures and religious talks from stations around the world.",
        intro="Live bayan and taqreer in Urdu and other languages: dars, Islamic lectures, Friday talks and religious programmes. Stations are listed by what they play; Sur Music does not endorse any one school of thought.",
        more="Also searched as Urdu bayan live, bayan radio, taqreer live, Islamic lectures online, dars e Quran, jumma bayan and the Urdu words بیان, تقریر and درس.",
        paths=[tag("bayan"), tag("dars"), tag("lecture"), name("bayan"), name("taqreer"), name("dars"),
               tag("islamic", "&language=urdu"), tag("islamic lectures"), tag("islamic lecture"), tag("dawah"),
               tag("islamic", "&language=english"), name("islamic lecture"), name("dawah"), name("yaqeen"),
               name("peace tv"), name("huda"), name("sunnah"), name("seerah"), name("khutba"), name("jumma")]),
    "majlis": dict(
        kind="genre", group="Islamic & spiritual", label="Majlis & Noha",
        h1="Majlis, Noha & Ahl-e-Bait Radio — Live", native="مجلس، نوحہ اور اہل بیت ریڈیو",
        seo_title="Majlis & Noha Radio Live — Ahl-e-Bait, Marsiya, Salam",
        description="Listen to live majlis and noha radio free: Ahl-e-Bait programmes, noha, marsiya, salam, manqabat and Muharram majalis from stations worldwide.",
        intro="Live majlis, noha, marsiya, salam and manqabat in memory of Ahl-e-Bait, with Muharram programmes. Stations are listed by what they play; Sur Music does not endorse any one school of thought.",
        more="Also searched as majlis live, noha radio, Ahl-e-Bait radio, Muharram majlis live, marsiya, manqabat, shia radio and the Urdu words مجلس, نوحہ, مرثیہ and اہل بیت.",
        paths=[tag("noha"), tag("majlis"), tag("shia"), tag("ahlebait"), tag("muharram"), name("noha"), name("majlis"),
               name("ahlebait"), name("ahl-e-bait"), name("ahl al bayt"), name("ahlulbayt"), name("karbala"), name("hussain"),
               name("najaf"), name("alkafeel"), name("kafeel"), name("ameed"), name("imam ali"), name("imam hussain"),
               name("zahra"), name("arbaeen"), name("nauha"), name("marsiya"), name("fatima"), tag("islamic", "&countrycode=IQ"),
               tag("islamic", "&countrycode=IR"), tag("quran", "&countrycode=IQ"), tag("ahlulbayt"), tag("ahl al bayt"),
               tag("shia", "&language=urdu"), tag("shia", "&language=english"), lang("urdu", "&tag=noha")]),
    "madani": dict(
        kind="genre", group="Islamic & spiritual", label="Madani & Dawat-e-Islami",
        h1="Madani & Dawat-e-Islami Radio — Live Naat, Bayan & Madani Channel", native="مدنی اور دعوت اسلامی ریڈیو",
        seo_title="Madani & Dawat-e-Islami Radio Live — Naat & Bayan",
        description="Listen to live Madani and Dawat-e-Islami radio free: naat, bayan, Madani programmes and Islamic talks from stations in Pakistan and worldwide.",
        intro="Live radio with Madani and Dawat-e-Islami programmes: naat sharif, bayan, madani muzakra and Islamic talks. Stations are listed by what they play; Sur Music does not endorse any one school of thought.",
        more="Also searched as Madani channel live, Dawat-e-Islami radio, Madani radio, Madani muzakra, Ilyas Qadri bayan live and the Urdu words مدنی چینل and دعوت اسلامی.",
        paths=[name("madani"), name("dawat"), name("dawateislami"), tag("madani"), tag("dawateislami"), name("ilyas")]),
    "hadith": dict(
        kind="genre", group="Islamic & spiritual", label="Hadith & Ahl-e-Hadith",
        h1="Hadith & Ahl-e-Hadith Radio — Live Dars, Tafseer & Hadith Lessons", native="حدیث اور اہل حدیث ریڈیو",
        seo_title="Hadith & Ahl-e-Hadith Radio Live — Dars & Tafseer",
        description="Listen to live hadith radio free: dars-e-hadith, tafseer, Quran and Sunnah lessons and Ahl-e-Hadith programmes from stations worldwide.",
        intro="Live hadith and Sunnah lessons, tafseer, dars and Islamic talks, including Ahl-e-Hadith programmes. Stations are listed by what they play; Sur Music does not endorse any one school of thought.",
        more="Also searched as hadith radio live, dars e hadith, Ahl-e-Hadith radio, tafseer live, Sunnah lessons and the Urdu words حدیث, اہل حدیث and تفسیر.",
        paths=[tag("hadith"), tag("tafseer"), tag("tafsir"), name("hadith"), name("ahle hadith"), name("ahl-e-hadith"),
               name("tafseer"), name("sunnah")]),
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
        seo_title="Qawwali Radio Live — Nusrat Fateh Ali Khan & Sabri Brothers",
        description="Listen to live qawwali radio free: classic and modern qawwali from Nusrat Fateh Ali Khan, Sabri Brothers, Aziz Mian and more.",
        intro="Live qawwali from stations that love the tradition — the timeless voices of Nusrat Fateh Ali Khan, the Sabri Brothers, Aziz Mian, Rahat Fateh Ali Khan and today's qawwals.",
        more="Also searched as qawwali live, Nusrat Fateh Ali Khan qawwali, Sufi qawwali radio, old qawwali, qawwali sunna, qawwali sunao, best qawwali online and the Urdu words قوالی, صوفی قوالی and نصرت فتح علی خان.",
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
        paths=[tag("ghazal"), tag("ghazals"), tag("gazal"), tag("gazals"), tag("urdu ghazal"), tag("jagjit singh"),
               name("ghazal"), name("gazal")]),
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
        seo_title="Indian Classical Radio Live — Raag, Hindustani & Carnatic",
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
        kind="genre", group="News, talk & sports", label="News", per=70, cap=800,
        h1="News Radio — Urdu, Hindi, Indian, Arabic & World News, Live", native="اردو خبریں · हिंदी समाचार · अख़बार",
        seo_title="News Radio Live — Urdu, Indian, Hindi & English News",
        description="Listen to live news radio free: Urdu news, Pakistan news, Indian and Hindi news, Arabic news and world English news in one place.",
        intro="Every live news channel in one list — Urdu and Punjabi khabrain from Pakistan, Indian and Hindi samachar, Arabic news and world English news. Pick any channel and press play.",
        more="Also searched as Urdu news live, Pakistan news radio, Indian news live, Bharat news, Hindi news, Hindi samachar, Arabic news, world news live, English news radio, BBC and Al Jazeera live, khabrain and پاکستان خبریں.",
        paths=[tag("news", "&countrycode=PK"), tag("news", "&language=urdu"), tag("news", "&language=punjabi"),
               lang("urdu", "&tag=talk"), name("news", "&countrycode=PK"), name("khabar", "&countrycode=PK"),
               name("khabrain", "&countrycode=PK"), name("geo", "&countrycode=PK"), name("ary", "&countrycode=PK"),
               name("express", "&countrycode=PK"), name("dawn", "&countrycode=PK"), name("samaa", "&countrycode=PK"),
               name("dunya", "&countrycode=PK"), name("92", "&countrycode=PK"), name("radio pakistan"), name("bbc urdu"), name("voa urdu"),
               tag("news", "&language=hindi"), tag("news", "&countrycode=IN"), name("samachar"), name("aaj tak", "&countrycode=IN"),
               name("ndtv"), name("zee news"), name("abp"), name("republic"), name("india today"), name("news18"),
               name("all india radio"), name("akashvani"),
               tag("news", "&language=arabic"), name("akhbar"), name("al jazeera"), name("al arabiya"), name("sky news arabia"),
               name("bbc arabic"), name("france 24"), name("monte carlo"),
               tag("news", "&language=english"), tag("world news"), name("bbc world"), name("cnn"), name("npr"),
               name("sky news"), name("dw "), name("euronews"), name("abc news"), name("bloomberg"), name("cbc"),
               name("nhk world"), name("reuters"), name("fox news"), name("lbc")]),
    "english-news": dict(
        kind="genre", group="News, talk & sports", label="World news",
        h1="World News Radio — Live English News & Talk", native="",
        seo_title="World News Radio Live — English News, Talk & Current Affairs",
        description="Listen to live English news radio free: world news, business, current affairs and talk stations from the UK, USA and beyond.",
        intro="Live English-language news and talk radio: world headlines, business, politics, science and current affairs from stations around the globe.",
        more="Also searched as news radio live, world news online, English news radio, talk radio and breaking news radio.",
        paths=[tag("news", "&language=english"), tag("talk", "&language=english"), tag("world news"),
               name("bbc world"), name("cnn"), name("npr"), name("sky news"), name("al jazeera"), name("france 24"),
               name("dw "), name("euronews"), name("abc news"), name("bloomberg"), name("cbc"), name("nhk world"),
               name("reuters"), name("fox news"), name("lbc"), name("rte news")]),
    "sports": dict(
        kind="genre", group="News, talk & sports", label="Sports & cricket",
        h1="Sports & Cricket Radio — Live Commentary & Talk", native="کرکٹ ریڈیو",
        seo_title="Sports & Cricket Radio Live — Commentary & Sports Talk",
        description="Listen to live sports radio free: cricket, football and sports talk stations with live commentary when matches are on.",
        intro="Live sports radio: cricket and football talk, sports news and live commentary (when the station carries the match).",
        more="Also searched as cricket radio live, cricket commentary radio, sports radio online and football radio.",
        paths=[tag("sports"), tag("cricket"), tag("football"), tag("sports talk"), tag("sport"), name("espn"),
               name("sports"), name("commentary"), name("ptv sports"), name("tsn"), name("talksport")]),

    "cricket": dict(
        kind="genre", group="News, talk & sports", label="Cricket",
        h1="Cricket Radio — Live Cricket Commentary", native="کرکٹ کمنٹری",
        seo_title="Cricket Radio Live — Live Commentary & Cricket Talk",
        description="Listen to live cricket radio free: ball-by-ball commentary when matches are on, cricket talk, news and analysis.",
        intro="Live cricket radio: commentary when the station carries the match, plus cricket talk, news and analysis.",
        more="Also searched as cricket commentary live, live cricket radio, cricket radio online, Pakistan cricket radio, ball by ball commentary and the Urdu words کرکٹ کمنٹری.",
        paths=[tag("cricket"), name("cricket"), name("commentary")]),
    "football": dict(
        kind="genre", group="News, talk & sports", label="Football",
        h1="Football Radio — Live Football Commentary & Talk", native="",
        seo_title="Football Radio Live — Commentary, Soccer & Sports Talk",
        description="Listen to live football radio free: match commentary, soccer talk and sports news from stations around the world.",
        intro="Live football (soccer) radio: match commentary when the station carries the game, plus football talk and news.",
        more="Also searched as football radio live, soccer radio, live football commentary, football talk radio and sports radio online.",
        paths=[tag("football"), tag("soccer"), name("football"), name("soccer")]),
    "hindi-news": dict(
        kind="genre", group="News, talk & sports", label="Indian news",
        h1="Hindi News Radio — Live Hindi Khabar", native="हिंदी समाचार रेडियो",
        seo_title="Hindi News Radio Live — Hindi Khabar & Samachar Online",
        description="Listen to live Hindi news radio free: Hindi khabar, samachar and talk from stations in India and around the world.",
        intro="Live Hindi news and talk radio: khabar, samachar, current affairs and discussions.",
        more="Also searched as Hindi news live, Hindi samachar radio, Hindi khabar online and news radio in Hindi.",
        paths=[tag("news", "&language=hindi"), lang("hindi", "&tag=talk"), name("samachar"),
               tag("news", "&countrycode=IN"), name("aaj tak", "&countrycode=IN"), name("ndtv"), name("zee news"),
               name("abp"), name("republic"), name("india today"), name("news18"), name("all india radio"),
               name("akashvani"), name("khabar", "&countrycode=IN")]),
    "arabic-news": dict(
        kind="genre", group="News, talk & sports", label="Arabic news",
        h1="Arabic News Radio — Live Arabic News & Talk", native="أخبار عربية مباشر",
        seo_title="Arabic News Radio Live — Arabic News & Talk Online",
        description="Listen to live Arabic news radio free: Arabic news, talk and current affairs from the Gulf, Egypt, the Levant and beyond.",
        intro="Live Arabic news and talk radio from the Middle East and North Africa.",
        more="Also searched as Arabic news live, Arabic radio news, Gulf news radio and Arabic talk radio.",
        paths=[tag("news", "&language=arabic"), lang("arabic", "&tag=talk"), name("akhbar"),
               name("al jazeera"), name("al arabiya"), name("sky news arabia"), name("bbc arabic"),
               name("france 24 arabic"), name("monte carlo"), name("rt arabic"), name("nile news"), name("alhurra"),
               name("خبر"), name("أخبار")]),

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
        seo_title="Classical Music Radio Live — Mozart, Beethoven & Piano",
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
        paths=[tag("talk"), tag("talk radio"), tag("politics"), tag("debate"), tag("comedy"), tag("interview"),
               lang("urdu", "&tag=talk"), lang("hindi", "&tag=talk"), lang("punjabi", "&tag=talk"),
               lang("arabic", "&tag=talk"), name("talk"), name("fm talk")]),
    "christian": dict(
        kind="genre", group="Islamic & spiritual", label="Christian",
        h1="Christian Radio — Live Worship, Gospel & Sermons", native="",
        seo_title="Christian Radio Live — Worship, Gospel & Sermons Online",
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

    "jewish": dict(
        kind="genre", group="Islamic & spiritual", label="Jewish & Hebrew",
        h1="Jewish Radio — Live Hebrew & Jewish Music", native="רדיו יהודי",
        seo_title="Jewish Radio Live — Hebrew Songs & Israeli Radio Online",
        description="Listen to live Jewish radio free: Hebrew songs, Jewish and Hasidic music, Israeli pop and Torah programmes.",
        intro="Live Jewish and Hebrew radio — Israeli pop, Hasidic and traditional Jewish music, and Torah and community programmes.",
        more="Also searched as Jewish music radio, Hebrew radio, Israeli radio online and רדיו בשידור חי.",
        paths=[tag("jewish"), lang("hebrew"), tag("hebrew")]),
    "persian": dict(
        kind="genre", group="Pakistani & South Asian languages", label="Persian (Farsi)",
        h1="Persian Radio — Live Farsi Music & News", native="رادیو فارسی",
        seo_title="Persian Radio Live — Farsi Songs, Persian Music & News",
        description="Listen to live Persian radio free: Farsi pop, traditional Persian music and news from Iran, Afghanistan and the diaspora.",
        intro="Live Persian-language radio — Farsi pop, classical Persian music, poetry and news.",
        more="Also searched as Farsi radio, Iranian radio online, Persian music live and رادیو آنلاین.",
        paths=[lang("persian"), tag("persian"), tag("farsi")]),

    # ------------------------------------------------------------------ Countries
    "pakistan": dict(
        kind="country", group="", label="Pakistan",
        h1="Pakistan Radio — Live Pakistani FM Stations", native="پاکستانی ریڈیو",
        seo_title="Pakistan Radio Live — Pakistani FM Stations Online Free",
        description="Listen to live Pakistani radio free: FM stations from Lahore, Karachi, Islamabad and all of Pakistan — music, news and more.",
        intro="All the live radio stations from Pakistan we can play in your browser: FM music stations, Urdu and Punjabi songs, news, naat and more from Lahore, Karachi, Islamabad, Peshawar, Quetta and beyond.",
        more="Also searched as Pakistani radio online, Pakistan FM live, FM 100 Pakistan, Radio Pakistan live, Lahore FM, Karachi FM and Islamabad FM.",
        paths=[country("PK"), name("fm 100", "&countrycode=PK"), name("fm 101", "&countrycode=PK"), name("fm 91", "&countrycode=PK"),
               name("fm 93", "&countrycode=PK"), name("fm 94", "&countrycode=PK"), name("fm 95", "&countrycode=PK"),
               name("fm 96", "&countrycode=PK"), name("fm 98", "&countrycode=PK"), name("fm 99", "&countrycode=PK"),
               name("mast fm", "&countrycode=PK"), name("hum fm", "&countrycode=PK"), name("city fm", "&countrycode=PK"),
               name("radio pakistan"), name("buraq", "&countrycode=PK"), name("power 99", "&countrycode=PK"),
               name("apna", "&countrycode=PK"), name("sunrise", "&countrycode=PK"), name("city fm 89", "&countrycode=PK"), name("apna karachi", "&countrycode=PK"), name("just music", "&countrycode=PK"), name("radio awaz", "&countrycode=PK"), name("hot fm", "&countrycode=PK"), name("samaa", "&countrycode=PK"), name("dil fm", "&countrycode=PK"), name("sunrise fm", "&countrycode=PK"), name("radio1", "&countrycode=PK"), name("saraiki", "&countrycode=PK"), name("pak filmi", "&countrycode=PK"), name("pbc", "&countrycode=PK"), name("suno pakistan", "&countrycode=PK"), name("saut ul quran", "&countrycode=PK"), name("dhamaal", "&countrycode=PK"), name("dilber", "&countrycode=PK"), name("rose fm", "&countrycode=PK"), name("jan fm", "&countrycode=PK"), name("fm 106", "&countrycode=PK"), name("fm 107", "&countrycode=PK"), name("fm 105", "&countrycode=PK"), name("fm 103", "&countrycode=PK"), name("fm 97", "&countrycode=PK"), name("fm 90", "&countrycode=PK"), name("fm 88", "&countrycode=PK"), name("fm 89", "&countrycode=PK"), name("fm 92", "&countrycode=PK")]),
    "india": dict(
        kind="country", group="", label="India",
        h1="India Radio — Live Indian FM Stations", native="भारतीय रेडियो",
        seo_title="India Radio Live — Indian FM Stations Online Free",
        description="Listen to live Indian radio free: FM stations from Mumbai, Delhi and across India — Hindi songs, regional music and news.",
        intro="Live radio from India: Hindi FM, Bollywood hits, regional language stations, devotional music and news.",
        more="Also searched as Indian radio online, India FM live, Hindi FM and Mumbai FM.",
        paths=[country("IN"), name("radio mirchi", "&countrycode=IN"), name("red fm", "&countrycode=IN"), name("big fm", "&countrycode=IN"),
               name("radio city", "&countrycode=IN"), name("fever", "&countrycode=IN"), name("vividh bharati"),
               name("hello fm", "&countrycode=IN"), name("ishq", "&countrycode=IN"), name("my fm", "&countrycode=IN"),
               name("radio one", "&countrycode=IN"), name("air fm", "&countrycode=IN"), name("fm gold"), name("fm rainbow"), name("air news"), name("all india radio"), name("air punjabi"), name("air kashmiri"), name("radio nasha", "&countrycode=IN"), name("radio indigo", "&countrycode=IN")]),
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
        description="Listen to live German radio free: pop, rock, schlager, news and talk from Germany, playing in your browser with no app and no sign-up.",
        intro="Live radio from Germany — pop, rock, schlager, news and talk.",
        more="Also searched as German radio online and Radio Deutschland live.",
        paths=[country("DE")]),
    "france": dict(
        kind="country", group="", label="France",
        h1="France Radio — Live French Stations", native="Radio française",
        seo_title="French Radio Live — France Radio Stations Online Free",
        description="Listen to live French radio free: French pop, chanson, news and talk from France, playing in your browser with no app and no sign-up.",
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
        seo_title=(f"Radio {_name} Live — {_name} FM & Online Stations" if len(_name) < 12 else
                   (f"Radio {_name} Live — Online Stations" if len(_name) <= 31 else f"Radio {_name} Live")),
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

# ------------------------------------------------------------------ lifestyle and learning
def _life(slug, label, h1, title, desc, intro, more, paths):
    TOPICS[slug] = dict(kind="genre", group="Lifestyle & learning", label=label, h1=h1, native="", seo_title=title,
                        description=desc, intro=intro, more=more, paths=paths)


_life("debates", "Debates & politics", "Debates & Politics Radio — Live Political Talk",
      "Debates and Politics Radio Live — Political Talk Online",
      "Listen to live debates and political radio free: political talk shows, parliamentary coverage, interviews and discussion from around the world.",
      "Live radio for debates and politics: political talk shows, election coverage, interviews, panel discussions and call-in programmes.",
      "Also searched as political debate live, election debate radio, parliament live radio, political talk shows and politics news radio.",
      [tag("debate"), tag("politics"), tag("political talk")])
_life("health", "Health & wellness", "Health & Wellness Radio — Live Health Talk",
      "Health and Wellness Radio Live — Health Talk Online Free",
      "Listen to live health and wellness radio free: health talk, medical news, fitness, mental wellbeing and healthy living from stations worldwide.",
      "Live health and wellness radio: doctors and experts answering questions, medical news, fitness, nutrition and mental wellbeing. Not a replacement for medical advice.",
      "Also searched as health radio live, wellness podcasts radio, fitness radio, medical talk radio and healthy living radio.",
      [tag("health"), tag("wellness"), tag("healthcare")])
_life("meditation", "Meditation & relax", "Meditation & Relaxation Radio — Calm Live Streams",
      "Meditation and Relaxation Radio Live — Calm Music Online",
      "Listen to live meditation and relaxation radio free: calm ambient music, spa sounds, sleep and mindfulness streams.",
      "Calm live streams for meditation, sleep and relaxation: ambient and spa music, soft piano and nature sounds, free in your browser.",
      "Also searched as meditation music radio, relaxing music live, sleep music radio, spa music and ambient radio.",
      [tag("meditation"), tag("relaxation"), tag("ambient"), tag("spa")])
_life("cooking", "Cooking & food", "Cooking & Food Radio — Live Food Talk",
      "Cooking and Food Radio Live — Recipes and Food Talk",
      "Listen to live cooking and food radio free: recipes, restaurant talk, chefs, food shows and kitchen company from stations worldwide.",
      "Live radio for people who love food: cooking shows, recipes, chefs, restaurant news and food talk to keep you company in the kitchen.",
      "Also searched as cooking radio live, recipe radio, food talk radio and chef interviews.",
      [tag("cooking"), tag("food"), tag("recipes")])
_life("kids", "Kids & family", "Kids & Family Radio — Live Children's Stations",
      "Kids and Family Radio Live — Songs and Stories Online",
      "Listen to live kids and family radio free: children's songs, stories, nursery rhymes and family-friendly shows.",
      "Live children's radio: songs, stories, nursery rhymes and family-friendly programmes for young listeners.",
      "Also searched as kids radio live, children's songs radio, nursery rhymes radio and family radio.",
      [tag("kids"), tag("children"), tag("childrens")])
_life("education", "Education & learning", "Education & Learning Radio — Live Educational Stations",
      "Education and Learning Radio Live — Learn on the Radio",
      "Listen to live education and learning radio free: lectures, language lessons, science, history and school programmes.",
      "Live educational radio: lectures, language lessons, science and history talks and learning programmes you can follow without a screen.",
      "Also searched as educational radio live, learning radio, language learning radio and lecture radio.",
      [tag("education"), tag("educational"), tag("learning")])
_life("business", "Business & finance", "Business & Finance Radio — Live Market News",
      "Business and Finance Radio Live — Market News Online",
      "Listen to live business and finance radio free: market news, economy, investing and money talk from around the world.",
      "Live business radio: market reports, economy news, investing and personal finance talk. For the numbers themselves, see our live gold, dollar and Bitcoin prices.",
      "Also searched as business news radio, finance radio live, stock market radio, economy news and money talk radio.",
      [tag("business"), tag("finance"), tag("economy")])
_life("comedy", "Comedy", "Comedy Radio — Live Comedy & Humour",
      "Comedy Radio Live — Stand-up and Humour Online Free",
      "Listen to live comedy radio free: stand-up, sketches, funny talk shows and humour from stations worldwide.",
      "Live comedy radio: stand-up, sketches, funny talk shows and light-hearted programmes to brighten your day.",
      "Also searched as comedy radio live, stand-up comedy radio, funny radio and humour radio.",
      [tag("comedy"), tag("humor")])
_life("technology", "Technology & science", "Technology & Science Radio — Live Tech Talk",
      "Technology and Science Radio Live — Tech Talk Online",
      "Listen to live technology and science radio free: tech news, gadgets, AI, space and science talk from around the world.",
      "Live technology and science radio: tech news, gadgets, artificial intelligence, space and science programmes.",
      "Also searched as tech radio live, technology news radio, science radio and AI talk radio.",
      [tag("technology"), tag("tech"), tag("science")])

# ------------------------------------------------------------------ languages (the "Language" button)
_LANGS = [("hindi", "Hindi", "हिन्दी रेडियो"), ("urdu", "Urdu", "اردو ریڈیو"), ("english", "English", ""),
          ("spanish", "Spanish", "Radio en español"), ("french", "French", "Radio en français"),
          ("german", "German", "Radio auf Deutsch"), ("italian", "Italian", "Radio italiana"),
          ("portuguese", "Portuguese", "Rádio em português"), ("russian", "Russian", "Русское радио"),
          ("turkish", "Turkish", "Türkçe radyo"), ("indonesian", "Indonesian", "Radio Indonesia"),
          ("japanese", "Japanese", "日本語ラジオ"), ("korean", "Korean", "한국어 라디오"),
          ("chinese", "Chinese", "中文广播"), ("swahili", "Swahili", "Redio ya Kiswahili"),
          ("thai", "Thai", "วิทยุไทย"), ("vietnamese", "Vietnamese", "Đài phát thanh Việt Nam"),
          ("polish", "Polish", "Radio po polsku"), ("dutch", "Dutch", "Radio in het Nederlands"),
          ("greek", "Greek", "Ελληνικό ραδιόφωνο"), ("hebrew", "Hebrew", "רדיו בעברית")]
for _lslug, _label, _native in _LANGS:
    if _lslug not in TOPICS:
        TOPICS[_lslug] = dict(
            kind="genre", group="World languages", label=_label,
            h1=f"{_label} Radio — Live {_label}-Language Stations", native=_native,
            seo_title=f"{_label} Radio Live — {_label} Stations Online Free",
            description=f"Listen to live {_label} radio free: music, news and talk in {_label} from stations around the "
                        "world, right in your browser.",
            intro=f"Live radio in {_label}: music, news, talk and more from stations around the world. Pick a station, "
                  "press play and keep browsing — the music keeps going.",
            more=f"Also searched as {_label} radio online, {_label} FM live, {_label} songs live, {_label} news radio "
                 f"and {_label} radio stations.",
            paths=[lang(_lslug)])


# ------------------------------------------------------------------ city pages (what "Lahore radio" searchers look for)
_CITIES = [   # (slug, name, country code, country name)
    ("lahore", "Lahore", "PK", "Pakistan"), ("karachi", "Karachi", "PK", "Pakistan"),
    ("islamabad", "Islamabad", "PK", "Pakistan"), ("rawalpindi", "Rawalpindi", "PK", "Pakistan"),
    ("faisalabad", "Faisalabad", "PK", "Pakistan"), ("multan", "Multan", "PK", "Pakistan"),
    ("peshawar", "Peshawar", "PK", "Pakistan"), ("quetta", "Quetta", "PK", "Pakistan"),
    ("hyderabad-sindh", "Hyderabad (Sindh)", "PK", "Pakistan"), ("sialkot", "Sialkot", "PK", "Pakistan"),
    ("gujranwala", "Gujranwala", "PK", "Pakistan"),
    ("mumbai", "Mumbai", "IN", "India"), ("delhi", "Delhi", "IN", "India"), ("kolkata", "Kolkata", "IN", "India"),
    ("chennai", "Chennai", "IN", "India"), ("bangalore", "Bangalore", "IN", "India"),
    ("hyderabad-india", "Hyderabad (India)", "IN", "India"), ("lucknow", "Lucknow", "IN", "India"),
    ("jaipur", "Jaipur", "IN", "India"), ("dhaka", "Dhaka", "BD", "Bangladesh"),
    ("dubai", "Dubai", "AE", "UAE"), ("abu-dhabi", "Abu Dhabi", "AE", "UAE"), ("riyadh", "Riyadh", "SA", "Saudi Arabia"),
    ("jeddah", "Jeddah", "SA", "Saudi Arabia"), ("doha", "Doha", "QA", "Qatar"),
    ("london", "London", "GB", "UK"), ("birmingham", "Birmingham", "GB", "UK"), ("manchester", "Manchester", "GB", "UK"),
    ("new-york", "New York", "US", "USA"), ("toronto", "Toronto", "CA", "Canada"), ("sydney", "Sydney", "AU", "Australia"),
]
CITY_SLUGS = []
for _s, _n, _cc, _cn in _CITIES:
    if _s in TOPICS:
        continue
    _q = _n.split(" (")[0]
    TOPICS[_s] = dict(
        kind="genre", group="Cities", label=_n,
        h1=f"{_n} Radio — Live FM Stations from {_n}", native="",
        seo_title=(f"{_n} Radio Live — {_n} FM Stations Online Free" if len(_n) <= 11 else f"{_n} Radio Live — Online Stations"),
        description=f"Listen to live radio from {_n}, {_cn} free: {_q} FM stations, music, news and talk playing in your browser.",
        intro=f"Live radio stations from {_n}, {_cn} — FM channels, local music, news and talk that play right here. Pick a station and press play.",
        more=f"Also searched as {_q} radio, {_q} FM live, {_q} radio stations online, FM radio {_q} and live radio {_q}.",
        paths=[f"/json/stations/search?state={urllib.parse.quote(_q)}&countrycode={_cc}&{COMMON}", name(_q, f"&countrycode={_cc}"),
               tag(_q.lower(), f"&countrycode={_cc}")])
    CITY_SLUGS.append(_s)


# Provinces and states (myTuner and Streema list stations by province too): Pakistan first, then India.
_PROVINCES = [
    ("punjab-pakistan", "Punjab", "PK", "Pakistan", ["Punjab"], "Lahore, Faisalabad, Rawalpindi, Multan, Gujranwala and Sialkot"),
    ("sindh", "Sindh", "PK", "Pakistan", ["Sindh"], "Karachi, Hyderabad, Sukkur and Larkana"),
    ("khyber-pakhtunkhwa", "Khyber Pakhtunkhwa", "PK", "Pakistan", ["Khyber Pakhtunkhwa", "KPK", "NWFP"], "Peshawar, Mardan, Abbottabad and Swat"),
    ("balochistan", "Balochistan", "PK", "Pakistan", ["Balochistan"], "Quetta, Gwadar and Turbat"),
    ("islamabad-capital-territory", "Islamabad Capital Territory", "PK", "Pakistan", ["Islamabad", "Islamabad Capital Territory"], "Islamabad"),
    ("azad-kashmir", "Azad Kashmir", "PK", "Pakistan", ["Azad Kashmir", "Azad Jammu and Kashmir", "AJK"], "Muzaffarabad and Mirpur"),
    ("gilgit-baltistan", "Gilgit-Baltistan", "PK", "Pakistan", ["Gilgit-Baltistan", "Gilgit Baltistan"], "Gilgit and Skardu"),
    ("maharashtra", "Maharashtra", "IN", "India", ["Maharashtra"], "Mumbai, Pune and Nagpur"),
    ("uttar-pradesh", "Uttar Pradesh", "IN", "India", ["Uttar Pradesh"], "Lucknow, Kanpur and Varanasi"),
    ("punjab-india", "Punjab (India)", "IN", "India", ["Punjab"], "Amritsar, Ludhiana and Jalandhar"),
    ("tamil-nadu", "Tamil Nadu", "IN", "India", ["Tamil Nadu"], "Chennai, Coimbatore and Madurai"),
    ("kerala", "Kerala", "IN", "India", ["Kerala"], "Kochi, Thiruvananthapuram and Kozhikode"),
    ("karnataka", "Karnataka", "IN", "India", ["Karnataka"], "Bangalore and Mysore"),
    ("west-bengal", "West Bengal", "IN", "India", ["West Bengal"], "Kolkata"),
    ("gujarat", "Gujarat", "IN", "India", ["Gujarat"], "Ahmedabad and Surat"),
    ("delhi-ncr", "Delhi NCR", "IN", "India", ["Delhi", "NCT of Delhi"], "New Delhi"),
]
PROVINCE_SLUGS = []
for _s, _n, _cc, _cn, _states, _cities in _PROVINCES:
    if _s in TOPICS:
        continue
    _plain = _n.split(" (")[0]
    TOPICS[_s] = dict(
        kind="genre", group="Cities", label=_n,
        h1=f"{_n} Radio — Live FM Stations from {_plain}, {_cn}", native="",
        seo_title=(f"{_n} Radio Live — FM Stations Online Free" if len(_n) <= 14 else f"{_n} Radio Live — FM Stations"),
        description=f"Listen to live radio from {_plain}, {_cn} free: FM stations from {_cities}, music, news and talk in your browser.",
        intro=f"Live radio stations from the province of {_plain} in {_cn} — FM channels from {_cities}. Pick a station and press play.",
        more=f"Also searched as {_plain} radio, {_plain} FM live, {_plain} radio stations online and FM radio in {_plain}.",
        paths=[f"/json/stations/search?state={urllib.parse.quote(st)}&countrycode={_cc}&{COMMON}" for st in _states])
    PROVINCE_SLUGS.append(_s)



# More cities, every country in the world: the main cities of each country (Babel's time-zone city names).
def _zone_cities():
    try:
        from babel import Locale
        from babel.core import get_global
    except ImportError:  # pragma: no cover
        return []
    zones = get_global("territory_zones")
    names = Locale("en").time_zones
    out = []
    for code, (cname, _cont, _native) in WORLD.items():
        seen = set()
        for z in zones.get(code) or []:
            city = (names.get(z) or {}).get("city") or z.split("/")[-1].replace("_", " ")
            if (not city or city in seen or city == cname or "Etc" in z or "/" in city or "," in city or "(" in city or len(city) > 24
                    or city.lower().startswith(("unknown", "utc"))):
                continue
            seen.add(city)
            out.append((code, cname, city))
    return out


for _cc, _cn, _city in _zone_cities():
    _s = _slug(_city)
    if not _s or _s in TOPICS or any(_t[0] == _s for _t in _CITIES):
        if _s and _s in TOPICS and TOPICS[_s].get("group") == "Cities" or not _s:
            continue
        _s = f"{_s}-{_cc.lower()}" if _s else ""
        if not _s or _s in TOPICS:
            continue
    _label = _city
    TOPICS[_s] = dict(
        kind="genre", group="Cities", label=_label,
        h1=f"{_label} Radio — Live FM Stations from {_label}", native="",
        seo_title=(f"{_label} Radio Live — {_label} FM Stations Online Free" if len(_label) <= 11 else
                   (f"{_label} Radio Live — Online Stations" if len(_label) <= 26 else f"{_label} Radio Live")),
        description=f"Listen to live radio from {_label}, {_cn} free: {_label} FM stations, music, news and talk playing in your browser.",
        intro=f"Live radio stations from {_label}, {_cn} — FM channels, local music, news and talk that play right here. Pick a station and press play.",
        more=f"Also searched as {_label} radio, {_label} FM live, {_label} radio stations online, FM radio {_label} and live radio {_label}.",
        paths=[f"/json/stations/search?state={urllib.parse.quote(_label)}&countrycode={_cc}&{COMMON}", name(_label, f"&countrycode={_cc}"),
               tag(_label.lower(), f"&countrycode={_cc}")])
    CITY_SLUGS.append(_s)


# The big cities of the world (by hand), so "radio <city>" searches land on a page for every large city.
_BIG = """JP:Tokyo,Osaka,Nagoya,Yokohama,Sapporo,Fukuoka,Kyoto;CN:Shanghai,Beijing,Guangzhou,Shenzhen,Chengdu,Wuhan,Chongqing,Tianjin,Hangzhou,Nanjing,Xian;HK:Hong Kong;TW:Taipei;KR:Seoul,Busan,Incheon;BR:Sao Paulo,Rio de Janeiro,Brasilia,Salvador,Fortaleza,Belo Horizonte,Recife,Porto Alegre,Curitiba,Manaus;MX:Mexico City,Guadalajara,Monterrey,Puebla,Tijuana,Cancun;EG:Cairo,Alexandria,Giza;TR:Istanbul,Ankara,Izmir,Bursa;NG:Lagos,Abuja,Kano,Ibadan;PH:Manila,Cebu,Davao;RU:Moscow,Saint Petersburg,Novosibirsk,Kazan,Sochi;ID:Jakarta,Surabaya,Bandung,Medan,Bali;FR:Paris,Marseille,Lyon,Toulouse,Nice;DE:Berlin,Hamburg,Munich,Cologne,Frankfurt;IT:Rome,Milan,Naples,Turin;ES:Madrid,Barcelona,Valencia,Seville;PT:Lisbon,Porto;NL:Amsterdam,Rotterdam;BE:Brussels;AT:Vienna;CH:Zurich,Geneva;SE:Stockholm,Gothenburg;NO:Oslo;DK:Copenhagen;FI:Helsinki;IE:Dublin;GR:Athens;PL:Warsaw,Krakow;CZ:Prague;HU:Budapest;RO:Bucharest;UA:Kyiv,Kharkiv,Odesa;RS:Belgrade;BG:Sofia;HR:Zagreb;CO:Bogota,Medellin,Cali,Barranquilla;PE:Lima;CL:Santiago;AR:Buenos Aires,Cordoba,Rosario;VE:Caracas;EC:Quito,Guayaquil;UY:Montevideo;CU:Havana;DO:Santo Domingo;US:Los Angeles,Chicago,Houston,Dallas,Miami,Atlanta,Philadelphia,Washington,San Francisco,Seattle,Boston,Las Vegas,Phoenix,Detroit,Denver;CA:Montreal,Vancouver,Calgary,Ottawa,Edmonton;AU:Melbourne,Brisbane,Perth,Adelaide,Canberra;NZ:Auckland,Wellington,Christchurch;ZA:Johannesburg,Cape Town,Durban,Pretoria;KE:Nairobi,Mombasa;GH:Accra;ET:Addis Ababa;CI:Abidjan;UG:Kampala;TZ:Dar es Salaam;MA:Casablanca,Rabat,Marrakech;DZ:Algiers;TN:Tunis;SN:Dakar;SD:Khartoum;AO:Luanda;CD:Kinshasa;SA:Mecca,Medina;AE:Sharjah;KW:Kuwait City;BH:Manama;OM:Muscat;JO:Amman;LB:Beirut;SY:Damascus;IQ:Baghdad,Basra,Erbil,Najaf,Karbala;IR:Tehran,Mashhad,Isfahan,Shiraz,Tabriz,Qom;IL:Tel Aviv,Jerusalem;AZ:Baku;GE:Tbilisi;AM:Yerevan;UZ:Tashkent;KZ:Almaty;NP:Kathmandu;LK:Colombo;AF:Kabul,Kandahar,Herat;VN:Hanoi,Ho Chi Minh City;TH:Bangkok,Chiang Mai;MY:Kuala Lumpur,Penang;SG:Singapore;KH:Phnom Penh;MM:Yangon;PK:Abbottabad,Bahawalpur,Sargodha,Sukkur,Larkana,Gujrat,Sheikhupura,Mardan,Muzaffarabad,Gilgit,Skardu,Mirpur;IN:Pune,Ahmedabad,Surat,Patna,Bhopal,Indore,Nagpur,Chandigarh,Amritsar,Srinagar,Kochi,Thiruvananthapuram,Visakhapatnam,Varanasi,Kanpur,Goa;BD:Chittagong,Sylhet;GB:Glasgow,Leeds,Liverpool,Bradford,Leicester,Edinburgh,Cardiff,Belfast,Sheffield,Bristol"""
for _grp in _BIG.split(";"):
    _cc, _names = _grp.split(":")
    for _city in _names.split(","):
        _cn = WORLD.get(_cc, (_cc,))[0]
        _s = _slug(_city)
        if not _s or _s in TOPICS:
            _s = f"{_s}-{_cc.lower()}" if _s else ""
        if not _s or _s in TOPICS:
            continue
        _label = _city
        TOPICS[_s] = dict(
            kind="genre", group="Cities", label=_label,
            h1=f"{_label} Radio — Live FM Stations from {_label}", native="",
            seo_title=(f"{_label} Radio Live — {_label} FM Stations Online Free" if len(_label) <= 11 else
                       (f"{_label} Radio Live — Online Stations" if len(_label) <= 26 else f"{_label} Radio Live")),
            description=f"Listen to live radio from {_label}, {_cn} free: {_label} FM stations, music, news and talk playing in your browser.",
            intro=f"Live radio stations from {_label}, {_cn} — FM channels, local music, news and talk that play right here. Pick a station and press play.",
            more=f"Also searched as {_label} radio, {_label} FM live, {_label} radio stations online, FM radio {_label} and live radio {_label}.",
            paths=[f"/json/stations/search?state={urllib.parse.quote(_label)}&countrycode={_cc}&{COMMON}", name(_label, f"&countrycode={_cc}"),
                   tag(_label.lower(), f"&countrycode={_cc}")])
        CITY_SLUGS.append(_s)

GENRE_PAGES = {k: v for k, v in TOPICS.items() if v["kind"] == "genre"}
COUNTRY_PAGES = {k: v for k, v in TOPICS.items() if v["kind"] == "country"}
CHIPS = ["naat", "quran", "islamic", "qawwali", "ghazal", "sufi", "punjabi", "pashto", "old-songs", "news",
         "lofi", "pakistan"]

# "Listen by type" strip: what people in each part of the world listen to most. It is chosen by the visitor's
# COUNTRY only (never a guess about a person's religion). The browser also puts the types a visitor played
# before at the front (site.js), so everyone quickly sees their own kind of radio, wherever they are.
_SOUTH_ASIA_MUSLIM = ["naat", "quran", "islamic", "qawwali", "ghazal", "sufi", "punjabi", "pashto", "old-songs",
                      "news", "lofi"]
_GULF = ["quran", "arabic", "islamic", "naat", "news", "malayalam", "punjabi", "qawwali", "old-songs", "english-news",
         "pop", "lofi"]
_ARAB = ["quran", "arabic", "islamic", "naat", "english-news", "pop", "classical", "lofi", "sports"]
_ENGLISH = ["pop", "english-news", "talk", "christian", "rock", "80s-90s", "country-music", "hip-hop", "jazz",
            "sports", "classical", "lofi"]
_EUROPE = ["pop", "dance", "rock", "english-news", "80s-90s", "classical", "jazz", "talk", "metal", "christian",
           "lofi", "islamic"]
_LATIN = ["latin", "pop", "christian", "rock", "80s-90s", "dance", "talk", "sports", "jazz", "lofi"]
_AFRICA = ["afrobeats", "pop", "christian", "islamic", "quran", "reggae", "english-news", "talk", "sports",
           "hip-hop", "dance"]
_EAST_ASIA = ["k-pop", "pop", "jazz", "classical", "lofi", "rock", "dance", "english-news", "christian"]
_DEFAULT = ["pop", "islamic", "english-news", "christian", "latin", "jazz", "classical", "rock", "talk",
            "lofi", "old-songs"]
REGION_CHIPS = {
    "PK": _SOUTH_ASIA_MUSLIM,
    "AF": ["pashto", "persian", "quran", "naat", "islamic", "news", "qawwali", "old-songs", "lofi"],
    "BD": ["bengali", "naat", "quran", "islamic", "qawwali", "old-songs", "news", "pop", "lofi"],
    "IN": ["bhajan", "old-songs", "punjabi", "ghazal", "qawwali", "sufi", "news", "tamil", "telugu", "malayalam",
           "marathi", "bengali", "gujarati", "naat", "gurbani", "lofi"],
    "NP": ["bhajan", "old-songs", "news", "pop", "lofi"], "LK": ["tamil", "pop", "christian", "news", "lofi"],
    "IR": ["persian", "quran", "islamic", "pop", "classical", "lofi"],
    "IL": ["jewish", "pop", "english-news", "rock", "classical", "jazz", "talk", "lofi"],
    "TR": ["quran", "islamic", "pop", "arabic", "classical", "lofi"],
    "ID": ["islamic", "quran", "naat", "pop", "k-pop", "dance", "lofi"],
    "MY": ["islamic", "quran", "naat", "pop", "k-pop", "tamil", "lofi"],
    "US": _ENGLISH + ["latin"], "CA": _ENGLISH + ["punjabi"], "GB": _ENGLISH[:5] + ["punjabi", "naat", "islamic"] + _ENGLISH[5:],
    "IE": _ENGLISH, "AU": _ENGLISH, "NZ": _ENGLISH,
}
for _c in ("SA", "AE", "QA", "OM", "KW", "BH"):
    REGION_CHIPS[_c] = _GULF
for _c in ("EG", "JO", "LB", "IQ", "SY", "PS", "YE", "MA", "DZ", "TN", "LY", "SD"):
    REGION_CHIPS[_c] = _ARAB
for _c in ("MX", "GT", "HN", "SV", "NI", "CR", "PA", "CU", "DO", "PR"):
    REGION_CHIPS[_c] = _LATIN
for _c in ("JP", "KR", "CN", "TW", "HK", "SG", "TH", "VN", "PH"):
    REGION_CHIPS[_c] = _EAST_ASIA
CONTINENT_CHIPS = {"europe": _EUROPE, "south-america": _LATIN, "africa": _AFRICA, "north-america": _LATIN,
                   "oceania": _ENGLISH, "middle-east": _ARAB, "asia": _DEFAULT}
CODE_TO_COUNTRY = {}            # ISO code -> country page slug (filled below, after the country list exists)


# Shown in the page text and keywords, but not as buttons in the "Listen by type" strip.
ISLAMIC_FAMILY = ("quran", "naat", "pakistan-islamic", "bayan", "majlis", "madani", "hadith")
HIDDEN_CHIPS = ("naat", "qawwali", "sufi") + tuple(k for k in ISLAMIC_FAMILY if k != "naat")   # all of them live under "Islamic"
SECT_PAGES = ("majlis", "madani", "hadith", "english-news", "hindi-news", "arabic-news")      # kept for search engines (sitemap), not listed as buttons or in the directory

# One page per big category, holding every channel of the types under it (like "Islamic" does).
MUSIC_FAMILY = ("bollywood", "lollywood", "hollywood", "ghazal", "qawwali", "sufi", "old-songs", "indian-classical", "pop",
                "rock", "hip-hop", "jazz", "classical", "dance", "lofi", "80s-90s", "latin", "country-music", "reggae",
                "afrobeats", "metal", "k-pop")
SPORTS_FAMILY = ("cricket", "football")
DAILY_FAMILY = ("talk", "debates", "comedy", "health", "meditation", "cooking", "kids", "education", "technology")
TOPICS["music"] = dict(
    kind="genre", group="Music", label="Music",
    h1="Music Radio — Live Bollywood, Lollywood, Hollywood, Ghazal, Qawwali, Pop & More", native="میوزک ریڈیو",
    seo_title="Music Radio Live — Bollywood, Ghazal, Qawwali, Pop",
    description="Listen to live music radio free: Bollywood, Lollywood, Hollywood, ghazal, qawwali, pop, rock and more, from stations worldwide.",
    intro="All live music radio in one place: Bollywood, Lollywood, Hollywood, ghazal, qawwali, Sufi, old songs, pop, rock and more.",
    more="Also searched as music radio, live music radio online, Bollywood radio, Pakistani songs radio and free online music stations.",
    per=40, cap=400,
    paths=list(dict.fromkeys(p for k in MUSIC_FAMILY if k in TOPICS for p in TOPICS[k]["paths"][:3])))
GENRE_PAGES["music"] = TOPICS["music"]
TOPICS["sports"]["paths"] = list(dict.fromkeys(TOPICS["sports"]["paths"] + [p for k in SPORTS_FAMILY for p in TOPICS[k]["paths"][:4]]))
TOPICS["daily-life"] = dict(
    kind="genre", group="Lifestyle & learning", label="Daily life",
    h1="Daily Life Radio — Live Talk, Health, Cooking, Kids & Education", native="روزمرہ زندگی ریڈیو",
    seo_title="Daily Life Radio Live — Talk, Health, Cooking, Kids",
    description="Listen to live daily life radio free: talk, health, cooking, comedy, kids, education, meditation and technology from stations worldwide.",
    intro="Everyday live radio on one page: talk shows, health, cooking, comedy, kids and family, education, meditation and technology.",
    more="Also searched as talk radio, health radio, cooking radio, kids radio, education radio and meditation radio live.",
    per=40, cap=300,
    paths=list(dict.fromkeys(p for k in DAILY_FAMILY if k in TOPICS for p in TOPICS[k]["paths"][:4])))
GENRE_PAGES["daily-life"] = TOPICS["daily-life"]

# One "Religious" page: every religious channel; the types (Islamic, Christian …) are shown on that page.
RELIGIOUS_TYPES = ("islamic", "christian", "bhajan", "gurbani", "jewish")
TOPICS["religious"] = dict(
    kind="genre", group="Islamic & spiritual", label="Religious",
    h1="Religious Radio — Live Islamic, Christian, Bhajan, Gurbani & More", native="مذہبی ریڈیو",
    seo_title="Religious Radio Live — Islamic, Christian, Bhajan",
    description="Listen to live religious radio free: Islamic, Quran and naat, Christian, bhajan, gurbani and Jewish stations from around the world.",
    intro="All live religious radio in one place: Islamic radio with Quran, naat and bayan, Christian, bhajan, gurbani and Hebrew stations.",
    more="Also searched as religious radio, Islamic radio, Christian radio, bhajan radio, gurbani radio and spiritual radio live.",
    per=60, cap=400,
    paths=list(dict.fromkeys(p for k in RELIGIOUS_TYPES if k in TOPICS for p in TOPICS[k]["paths"][:6])))
GENRE_PAGES["religious"] = TOPICS["religious"]

# One "Islamic" page that holds all of it: Quran, Naat, bayan and the other Islamic programmes.
TOPICS["islamic"]["paths"] = list(dict.fromkeys(
    TOPICS["islamic"]["paths"] + [p for k in ISLAMIC_FAMILY for p in TOPICS[k]["paths"]]))


def chips_for(code):
    """Chips for a visitor from this country: their own country first, then what people there listen to."""
    code = (code or "").upper()
    slug = CODE_TO_COUNTRY.get(code)
    if code in REGION_CHIPS:
        base = REGION_CHIPS[code]
    elif slug:
        base = CONTINENT_CHIPS.get(TOPICS[slug]["group"], _DEFAULT)
    else:
        base = _DEFAULT
    out = ([slug] if slug else []) + [k for k in base if k in TOPICS and k not in HIDDEN_CHIPS]
    return list(dict.fromkeys(out))[:16]


def topic_path(slug):
    t = TOPICS[slug]
    return f"/country/{slug}" if t["kind"] == "country" else f"/genre/{slug}"


def grouped(visible_only=False):
    """[(group heading, [(slug, topic), …]), …] — radio types (for the "All radio stations" page)."""
    return [(g, [(k, v) for k, v in TOPICS.items() if v["group"] == g and not (visible_only and k in SECT_PAGES)])
            for g in GROUPS]


def countries_in(continent):
    """[(slug, topic)] of one continent, A–Z."""
    return sorted(((k, v) for k, v in COUNTRY_PAGES.items() if v["group"] == continent), key=lambda kv: kv[1]["label"])


CODE_TO_COUNTRY.update({v: k for k, v in COUNTRY_CODES.items()})


# --------------------------------------------------------------------------------------------
# Extra "also searched as" words for the biggest pages: famous names, cities and common questions.
EXTRA_MORE = {
    "news": "Also searched as live news radio, breaking news live, world news today, US midterm elections and election night "
            "live, congressional and senate results, Europe news and politics, European economy and energy, Ukraine and "
            "Russia news, Middle East and Iran news, weather and storm warnings, news radio near me, war and "
            "conflict news, world affairs, business news radio, stock market and crypto news, gold price news, "
            "Urdu news live, Hindi news radio and Arabic news live. For the numbers behind the headlines, see our live "
            "gold, Bitcoin and dollar-rate prices.",
    "english-news": "Also searched as US election results radio, midterm election coverage, Europe news live, "
                    "political debates and analysis, BBC-style world news radio, English news live, global news, breaking news, "
                    "business and finance news radio, politics and current affairs, war and world news today.",
    "talk": "Also searched as talk radio live, news and talk radio, political talk shows, call-in radio, business and "
            "money talk, interviews and debates online.",
    "sports": "Also searched as live cricket commentary, Pakistan vs India radio commentary, PSL, Asia Cup, IPL and "
              "T20 World Cup commentary, cricket radio in Urdu and English, football radio live, NBA and NFL radio, "
              "sports talk radio, match commentary online and live score radio.",
    "quran": "Listeners look for recitations by Mishary Rashid Alafasy, Abdul Rahman Al-Sudais, Saud Al-Shuraim, "
             "Maher Al Muaiqly, Abdul Basit Abdus Samad, Saad Al-Ghamdi, Yasser Al-Dosari and Mahmoud Khalil Al-Husary. "
             "Quran stations from different countries are listed here, so the reciters differ from station to station. "
             "Many people listen to Quran radio in the morning, in the car, at work or before sleep, in the USA, UK, "
             "UAE, Saudi Arabia, Canada, Pakistan and everywhere else.",
    "naat": "Popular naat khwans include Owais Raza Qadri, Junaid Jamshed, Khalid Hasnain Khalid, Syed Fasihuddin "
            "Soharwardi, Hafiz Ahmed Raza Qadri, Sami Yusuf and Maher Zain. Titles people search for include Tajdar-e-Haram, "
            "Mustafa Jaan-e-Rehmat, Mera Dil Badal De, Ya Nabi Salam Alayka and Hasbi Rabbi. A naat praises the Prophet "
            "Muhammad (peace be upon him); a hamd praises Allah.",
    "qawwali": "Great qawwali names include Nusrat Fateh Ali Khan, the Sabri Brothers, Aziz Mian, Rahat Fateh Ali Khan, "
               "Amjad Sabri, Fareed Ayaz and Abu Muhammad, Rizwan and Muazzam, and Abida Parveen for Sufi kalam. "
               "Titles people search for include Allah Hoo, Ali Maula, Dam Mast Qalandar, Bhar Do Jholi Meri and "
               "Tajdar-e-Haram.",
    "islamic": "Listeners search for bayan, dars-e-Quran, hadith lessons, Islamic lectures in Urdu, Arabic and English, "
               "duas, Jummah khutbah and nasheed from stations in Pakistan, Saudi Arabia, the UAE, the UK and the USA.",
    "usa": "Also searched as radio in New York, Los Angeles, Chicago, Houston and Dallas, American news and talk radio, "
           "country music radio, hip-hop radio, Bollywood radio in the USA, Quran radio in the USA and Urdu radio in America.",
    "uk": "Also searched as London radio live, Manchester, Birmingham and Glasgow radio, British radio online, "
          "Asian radio UK, Urdu radio UK, Punjabi radio UK, Bollywood radio UK and Quran radio in the UK.",
    "uae": "Also searched as Dubai radio online, Abu Dhabi radio, Sharjah radio, Arabic radio UAE, Hindi radio UAE, "
           "Pakistani radio in Dubai, Quran radio UAE and Malayalam radio UAE.",
    "canada": "Also searched as Toronto radio live, Vancouver, Montreal, Calgary and Ottawa radio, Punjabi radio Canada, "
              "Urdu radio Canada, Bollywood radio Canada and CBC style news radio.",
    "saudi-arabia": "Also searched as Makkah radio, Madinah radio, Riyadh and Jeddah radio, Quran radio Saudi Arabia, "
                    "Arabic radio live, and Urdu and Hindi radio for people working in Saudi Arabia.",
    "india": "Also searched as Mumbai, Delhi, Kolkata, Chennai and Bengaluru radio, Hindi radio online, Bollywood radio, "
             "Tamil, Telugu, Malayalam and Punjabi radio, cricket commentary and old Hindi songs.",
    "pakistan": "Also searched as Lahore, Karachi, Islamabad, Rawalpindi, Peshawar and Quetta radio, Pakistani FM radio live, "
                "FM 100, FM 101 and FM 91, Urdu, Punjabi, Pashto and Sindhi radio, cricket commentary, naat and Quran radio.",
    "australia": "Also searched as Sydney, Melbourne, Brisbane, Perth and Adelaide radio, Australian news radio, "
                 "Punjabi and Hindi radio in Australia, Urdu radio Australia and Quran radio in Australia.",
    "pop": "Also searched as pop music player online, free online music player, pop hits radio, Top 40 radio player, "
           "new songs player, English pop songs online, Hindi pop and Urdu pop radio, music player for songs and radio.",
    "dance": "Also searched as EDM radio, EDM party mix, dance music player, club music radio, DJ mix radio, house and "
             "techno radio, party beats online, Pakistani and Indian DJ party songs, workout and gym music radio.",
    "lofi": "Also searched as relaxing music player, chill music radio, lo-fi beats to study and relax, calm instrumental "
            "music, peaceful background music, sleep and relaxation music online, good morning relaxing beats.",
    "meditation": "Also searched as relaxing music, meditation music player, calm instrumental music, sleep music, "
                  "yoga and mindfulness music, stress relief music, nature sounds and peaceful music online.",
    "old-songs": "Also searched as classic hits, old is gold songs, purane gaane, Hindi retro songs, Urdu old songs, "
                 "vintage vinyl and gramophone-style songs, golden era music, classic songs player online.",
    "80s-90s": "Also searched as classic hits radio, oldies music player, 80s and 90s hits online, retro music, "
               "throwback songs, vintage vinyl era music and golden oldies.",
    "classical": "Also searched as classical music player, instrumental music radio, piano and violin music, "
                 "orchestra radio, relaxing classical music and study music online.",
    "rock": "Also searched as rock music player, classic rock radio, hard rock and alternative rock online, "
            "guitar music radio and rock songs live.",
    "hip-hop": "Also searched as hip hop radio, rap music player, trap and R&B radio, new rap songs online.",
}
for _k, _t in EXTRA_MORE.items():
    if _k in TOPICS:
        TOPICS[_k]["more"] = (TOPICS[_k].get("more") or "").rstrip() + " " + _t


# ---------------------------------------------------------------------------------------------
# The category tabs (Music, News, Sports, Talk, Religious, Languages, Countries) and what opens under each.
# Everything about a kind of radio sits under one tab; nothing points at one school of thought.
NAV = [
    ("music", "Music", ["bollywood", "lollywood", "hollywood", "ghazal", "qawwali", "sufi", "old-songs", "indian-classical",
                         "pop", "rock", "hip-hop", "jazz", "classical", "dance", "lofi", "80s-90s", "latin", "country-music",
                         "reggae", "afrobeats", "metal", "k-pop"]),
    ("news", "News", ["news"]),
    ("sports", "Sports", ["sports", "cricket", "football"]),
    ("talk", "Talk", ["talk", "debates", "comedy", "health", "meditation", "cooking", "kids", "education", "business",
                       "technology"]),
    ("religious", "Religious", ["islamic", "christian", "bhajan", "gurbani", "jewish"]),
    ("languages", "Languages", ["punjabi", "pashto", "sindhi", "hindi", "urdu", "english", "arabic", "bengali", "tamil",
                                "telugu", "malayalam", "marathi", "gujarati", "persian", "spanish", "french", "german",
                                "italian", "portuguese", "russian", "turkish", "indonesian", "japanese", "korean",
                                "chinese", "swahili", "thai", "vietnamese", "polish", "dutch", "greek", "hebrew"]),
    ("countries", "Countries", []),     # filled by the page code: continents and the biggest countries
]
CAT_PAGES = {"bollywood": "Bollywood", "lollywood": "Lollywood", "hollywood": "Hollywood"}
TAB_OF = {slug: key for key, _label, slugs in NAV for slug in slugs}
TAB_OF.update({k: "religious" for k in ISLAMIC_FAMILY})
TAB_OF["music"] = "music"
TAB_OF.update({k: "countries" for k in CITY_SLUGS})
TAB_COUNTRIES = ["lahore", "karachi", "islamabad", "mumbai", "delhi", "dubai", "london", "pakistan", "india", "uk", "usa", "uae", "saudi-arabia", "canada", "australia", "germany", "france",
                 "turkey", "bangladesh"]
