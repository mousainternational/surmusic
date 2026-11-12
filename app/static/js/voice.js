// © 2026 Mousa International Software House. All rights reserved.
// Sur Music — understands the words the phone's speech service hands back (English, Roman Urdu/Hindi, Urdu, Hindi).
// No server and no key: the phone does the listening, this only turns the sentence into a command.
(function (root) {
  'use strict';

  function norm(s) {
    return String(s || '').toLowerCase()
      .replace(/[ً-ٰٟ۔‌‍]/g, '')              // Arabic marks
      .replace(/ي/g, 'ی').replace(/ك/g, 'ک').replace(/[ۂۃہ]/g, 'ہ').replace(/ە/g, 'ہ')
      .replace(/[़]/g, '')                                              // Devanagari nukta (ज़ → ज)
      .replace(/[.,!?;:"'()\[\]{}\-_/\\|،؟۔]/g, ' ')
      .replace(/\s+/g, ' ').trim();
  }
  function has(t, words) {
    for (var i = 0; i < words.length; i++) {
      var w = words[i];
      if ((' ' + t + ' ').indexOf(' ' + w + ' ') !== -1) return true;
    }
    return false;
  }
  function stripWords(t, words) {
    var out = ' ' + t + ' ';
    words.forEach(function (w) { out = out.split(' ' + w + ' ').join('  '); out = out.split(' ' + w + ' ').join('  '); });
    return out.replace(/\s+/g, ' ').trim();
  }

  var STOP = ['stop', 'band', 'bund', 'roko', 'ruko', 'rok', 'bandh', 'بند', 'روکو', 'روک', 'رکو', 'رک', 'रोको', 'रुको', 'रोक', 'बंद', 'बन्द', 'बन्ध'];
  var PAUSE = ['pause', 'thehro', 'theher', 'ٹھہرو', 'ٹھہر', 'ठहरो', 'पॉज'];
  var NEXT = ['next', 'skip', 'agla', 'agle', 'aage', 'اگلا', 'اگلے', 'آگے', 'अगला', 'अगले', 'आगे'];
  var PREV = ['previous', 'back', 'pichla', 'pichle', 'pehla', 'پچھلا', 'پچھلے', 'پہلا', 'पिछला', 'पिछले', 'पहला'];
  var VOL_WORDS = ['volume', 'awaz', 'avaz', 'awaaz', 'sound', 'آواز', 'आवाज', 'वॉल्यूम', 'ولیوم'];
  var UP = ['up', 'louder', 'barhao', 'badhao', 'zyada', 'ziyada', 'tez', 'تیز', 'بڑھاو', 'بڑھاؤ', 'زیادہ', 'बढ़ाओ', 'बढाओ', 'ज्यादा', 'तेज', 'तेज़', 'increase'];
  var DOWN = ['down', 'lower', 'quieter', 'quiet', 'kam', 'kamm', 'dheere', 'ghatao', 'کم', 'دھیرے', 'گھٹاو', 'گھٹاؤ', 'कम', 'धीरे', 'घटाओ', 'decrease', 'reduce'];
  var PLAY = ['play', 'chalao', 'chalado', 'chala', 'chalo', 'lagao', 'lagado', 'laga', 'sunao', 'sunado', 'suna', 'start', 'چلاو', 'چلاؤ', 'چلا', 'چلاو', 'لگاو', 'لگاؤ', 'لگا', 'سناو', 'سناؤ', 'سنا', 'चलाओ', 'चला', 'चलो', 'लगाओ', 'लगा', 'सुनाओ', 'सुना', 'sunna'];
  var FILLER = ['radio', 'station', 'channel', 'please', 'plz', 'mujhe', 'mere', 'liye', 'ko', 'ka', 'ki', 'ke', 'koi', 'ek', 'the', 'a', 'me', 'on', 'to',
                'ریڈیو', 'اسٹیشن', 'چینل', 'مجھے', 'میرے', 'لیے', 'کو', 'کا', 'کی', 'کے', 'کوئی', 'ایک', 'پلیز', 'रेडियो', 'स्टेशन', 'चैनल', 'मुझे', 'मेरे', 'लिए', 'को', 'का', 'की', 'के', 'कोई', 'एक', 'प्लीज़', 'प्लीज'];

  // spoken name -> what to search for (Radio Browser understands these tags)
  var GENRES = [
    ['naat', ['naat', 'nat', 'naats', 'نعت', 'نعتیں', 'नात', 'नाअत', 'hamd', 'حمد']],
    ['quran', ['quran', 'koran', 'qur an', 'tilawat', 'tilawaat', 'قرآن', 'قران', 'تلاوت', 'कुरान', 'क़ुरान', 'कुरआन', 'तिलावत']],
    ['qawwali', ['qawwali', 'qawali', 'kawwali', 'قوالی', 'क़व्वाली', 'कव्वाली']],
    ['ghazal', ['ghazal', 'ghazals', 'غزل', 'غزلیں', 'ग़ज़ल', 'गज़ल', 'ग़ज़लें']],
    ['news', ['news', 'khabrein', 'khabren', 'khabar', 'خبریں', 'خبر', 'ख़बरें', 'खबरें', 'समाचार', 'खबर']],
    ['old songs', ['old songs', 'purane gane', 'purane geet', 'old gold', 'پرانے گانے', 'پرانے گیت', 'पुराने गाने', 'पुराने गीत']],
    ['sufi', ['sufi', 'sufiana', 'صوفی', 'صوفیانہ', 'सूफी', 'सूफ़ी']],
    ['meditation', ['relax', 'relaxing', 'calm', 'sukoon', 'سکون', 'پرسکون', 'सुकून']],
    ['punjabi', ['punjabi', 'panjabi', 'پنجابی', 'पंजाबी']]
  ];
  var CATS = { bollywood: ['bollywood', 'بالی ووڈ', 'बॉलीवुड'], lollywood: ['lollywood', 'لالی ووڈ', 'लॉलीवुड'], hollywood: ['hollywood', 'ہالی ووڈ', 'हॉलीवुड'] };

  // the word lists use the same spelling rules as the spoken text (marks and dots removed)
  [STOP, PAUSE, NEXT, PREV, VOL_WORDS, UP, DOWN, PLAY, FILLER].forEach(function (arr) { arr.forEach(function (w, i) { arr[i] = norm(w); }); });
  GENRES.forEach(function (g) { g[1] = g[1].map(norm); });
  Object.keys(CATS).forEach(function (k) { CATS[k] = CATS[k].map(norm); });

  var PODCAST = ['podcast', 'podcasts', 'پوڈکاسٹ', 'پوڈ کاسٹ', 'पॉडकास्ट'];
  var POD_TOPICS = [['ai', ['ai', 'artificial intelligence', 'اے آئی', 'ए आई', 'chatgpt']], ['technology', ['technology', 'tech', 'ٹیکنالوجی', 'टेक्नोलॉजी']],
                    ['business', ['business', 'بزنس', 'बिज़नेस', 'बिजनेस']], ['science', ['science', 'سائنس', 'साइंस']], ['islamic-scholars', ['bayan', 'بیان', 'scholars', 'बयान']]];
  PODCAST = PODCAST.map(norm); POD_TOPICS.forEach(function (p) { p[1] = p[1].map(norm); });

  /** @returns {{cmd:string, q?:string, cat?:string}|null} */
  function parse(text) {
    var t = norm(text);
    if (!t) return null;
    if (has(t, STOP) && !has(t, PLAY)) return { cmd: 'stop' };
    if (has(t, NEXT)) return { cmd: 'next' };
    if (has(t, PREV)) return { cmd: 'prev' };
    var vol = has(t, VOL_WORDS) || has(t, UP) || has(t, DOWN);
    if (vol && has(t, UP)) return { cmd: 'vol+' };
    if (vol && has(t, DOWN)) return { cmd: 'vol-' };
    if (has(t, PAUSE)) return { cmd: 'pause' };

    if (has(t, PODCAST)) { for (var j = 0; j < POD_TOPICS.length; j++) if (has(t, POD_TOPICS[j][1])) return { cmd: 'podcast', slug: POD_TOPICS[j][0] }; return { cmd: 'podcast', slug: 'top-pakistan' }; }
    var wantsPlay = has(t, PLAY);
    var q = stripWords(stripWords(t, PLAY), FILLER);
    for (var cat in CATS) if (has(t, CATS[cat])) return { cmd: 'category', cat: cat };
    for (var i = 0; i < GENRES.length; i++) {
      if (has(t, GENRES[i][1]) || GENRES[i][1].some(function (w) { return w.indexOf(' ') !== -1 && (' ' + t + ' ').indexOf(' ' + w + ' ') !== -1; })) {
        return { cmd: 'play', q: GENRES[i][0] };
      }
    }
    if (wantsPlay && !q) return { cmd: 'resume' };
    if (q) return { cmd: 'play', q: q };
    return null;
  }

  var api = { parse: parse, norm: norm };
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.SurVoice = api;
})(typeof window !== 'undefined' ? window : globalThis);
