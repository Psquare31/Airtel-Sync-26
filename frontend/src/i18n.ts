import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

export const LANGS = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'ta', label: 'தமிழ்' },
  { code: 'mr', label: 'मराठी' },
  { code: 'hinglish', label: 'Hinglish' },
]

const en = {
  tagline: 'Your business online in one sitting',
  heroTitle: 'One plan. One bill. Activated in days.',
  heroBody: 'Answer a few questions and get internet, business mobiles, WhatsApp, CCTV and more on one bill. No sales visit, no paperwork.',
  start: 'Start: takes 3 minutes',
  chooseLanguage: 'Choose your language',
  partnerMode: 'Partner-assisted session',
  trackOrder: 'Track an existing order',
  orderId: 'Order ID',
  go: 'Go',
  stepAdvisor: 'Advisor',
  stepQuote: 'Plan',
  stepKyc: 'Verify',
  stepSign: 'Sign',
  stepTrack: 'Track',
  typeMessage: 'Type your answer…',
  send: 'Send',
  listening: 'Listening… tap to stop',
  yourPlan: 'Your plan',
  perMonth: '/month',
  inclGst: 'incl. 18% GST',
  exclGst: 'excl. GST',
  oneTimeSetup: 'One-time setup',
  spreadSetup: 'Spread setup over 6 months',
  contract: 'Contract',
  months: 'months',
  included: 'Included',
  optional: 'Optional add-ons',
  locked: 'Not available yet',
  needsGstin: 'Needs GSTIN',
  continue: 'Continue',
  changeAnswers: 'Change my answers',
  talkToExpert: 'Talk to an expert',
  activationIn: 'Everything active in about {{days}} days',
  whyThis: 'Why this plan',
  consentTitle: 'Before we verify your business',
  consentBody: 'We only ask for what we need. Tick what you agree to:',
  required: 'Required',
  retention: 'Kept for',
  processors: 'Who processes your data',
  agree: 'Agree and continue',
  withdraw: 'You can withdraw consent any time from the tracker page or by messaging STOP.',
  kycTitle: 'Verify your business',
  kycBody: 'Upload a photo of each document. We read the details, check them against the GST and Udyam registries, and delete the photo immediately.',
  digilocker: 'Fetch from DigiLocker',
  upload: 'Upload / take photo',
  useSample: 'Use a sample',
  verifyNow: 'Verify now',
  verifying: 'Checking…',
  optionalDoc: 'Optional',
  kycIssues: 'A few things to fix',
  kycBlocked: "We can't finish this online",
  partnerHelp: 'Get a partner to help',
  esignTitle: 'Sign and confirm',
  otpHint: 'Enter the 6-digit OTP sent to your Aadhaar-linked mobile (demo: any 6 digits).',
  installSlot: 'Preferred installation slot',
  confirmOrder: 'Sign and place order',
  trackerTitle: 'Order status',
  expected: 'Expected by',
  services: 'Your services',
  updates: 'Updates',
  askOrder: 'Ask about your order…',
  ask: 'Ask',
  demoAdvance: 'Demo: next step',
  handoffTitle: "We've got it from here",
  handoffBody: 'An Accel Business expert will call you within 2 working hours.',
  backToChat: 'Back to chat',
  network: 'Connection problem. Please try again.',
}

type Dict = typeof en

const hi: Dict = {
  tagline: 'एक बार में आपका बिज़नेस ऑनलाइन',
  heroTitle: 'एक प्लान। एक बिल। कुछ ही दिनों में चालू।',
  heroBody: 'कुछ सवालों के जवाब दें और इंटरनेट, बिज़नेस मोबाइल, WhatsApp, CCTV सब एक बिल पर पाएँ। न सेल्स विज़िट, न कागज़ी काम।',
  start: 'शुरू करें: 3 मिनट लगेंगे',
  chooseLanguage: 'अपनी भाषा चुनें',
  partnerMode: 'पार्टनर की मदद से',
  trackOrder: 'अपना ऑर्डर देखें',
  orderId: 'ऑर्डर ID',
  go: 'देखें',
  stepAdvisor: 'सलाह',
  stepQuote: 'प्लान',
  stepKyc: 'वेरिफ़ाई',
  stepSign: 'साइन',
  stepTrack: 'ट्रैक',
  typeMessage: 'अपना जवाब लिखें…',
  send: 'भेजें',
  listening: 'सुन रहे हैं… रोकने के लिए टैप करें',
  yourPlan: 'आपका प्लान',
  perMonth: '/महीना',
  inclGst: '18% GST सहित',
  exclGst: 'GST अलग',
  oneTimeSetup: 'एक बार का सेटअप',
  spreadSetup: 'सेटअप 6 महीनों में बाँटें',
  contract: 'कॉन्ट्रैक्ट',
  months: 'महीने',
  included: 'शामिल',
  optional: 'वैकल्पिक ऐड-ऑन',
  locked: 'अभी उपलब्ध नहीं',
  needsGstin: 'GSTIN ज़रूरी',
  continue: 'आगे बढ़ें',
  changeAnswers: 'जवाब बदलें',
  talkToExpert: 'एक्सपर्ट से बात करें',
  activationIn: 'लगभग {{days}} दिनों में सब चालू',
  whyThis: 'यह प्लान क्यों',
  consentTitle: 'वेरिफ़िकेशन से पहले',
  consentBody: 'हम सिर्फ़ ज़रूरी जानकारी लेते हैं। जिस पर सहमत हैं उसे चुनें:',
  required: 'ज़रूरी',
  retention: 'कब तक रखेंगे',
  processors: 'आपका डेटा कौन प्रोसेस करता है',
  agree: 'सहमत हूँ, आगे बढ़ें',
  withdraw: 'आप कभी भी ट्रैकर पेज से या STOP भेजकर सहमति वापस ले सकते हैं।',
  kycTitle: 'अपना बिज़नेस वेरिफ़ाई करें',
  kycBody: 'हर दस्तावेज़ की फ़ोटो अपलोड करें। हम जानकारी पढ़कर GST और उद्यम रजिस्ट्री से मिलाते हैं, और फ़ोटो तुरंत हटा देते हैं।',
  digilocker: 'DigiLocker से लाएँ',
  upload: 'फ़ोटो अपलोड करें',
  useSample: 'सैंपल चुनें',
  verifyNow: 'अभी वेरिफ़ाई करें',
  verifying: 'जाँच हो रही है…',
  optionalDoc: 'वैकल्पिक',
  kycIssues: 'कुछ चीज़ें ठीक करनी हैं',
  kycBlocked: 'यह ऑनलाइन पूरा नहीं हो सकता',
  partnerHelp: 'पार्टनर से मदद लें',
  esignTitle: 'साइन करें और कन्फ़र्म करें',
  otpHint: 'आधार से जुड़े मोबाइल पर आया 6 अंकों का OTP डालें (डेमो: कोई भी 6 अंक)।',
  installSlot: 'इंस्टॉलेशन का समय',
  confirmOrder: 'साइन करें और ऑर्डर दें',
  trackerTitle: 'ऑर्डर की स्थिति',
  expected: 'अनुमानित तारीख',
  services: 'आपकी सेवाएँ',
  updates: 'अपडेट',
  askOrder: 'अपने ऑर्डर के बारे में पूछें…',
  ask: 'पूछें',
  demoAdvance: 'डेमो: अगला स्टेप',
  handoffTitle: 'अब हम संभाल लेंगे',
  handoffBody: 'Accel Business के एक्सपर्ट 2 कामकाजी घंटों में कॉल करेंगे।',
  backToChat: 'चैट पर लौटें',
  network: 'कनेक्शन में दिक्कत। फिर से कोशिश करें।',
}

const ta: Dict = {
  ...en,
  tagline: 'ஒரே முறையில் உங்கள் தொழில் ஆன்லைனில்',
  heroTitle: 'ஒரு திட்டம். ஒரு பில். சில நாட்களில் செயல்படும்.',
  heroBody: 'சில கேள்விகளுக்கு பதில் சொல்லுங்கள். இணையம், மொபைல், WhatsApp, CCTV அனைத்தும் ஒரே பில்லில்.',
  start: 'தொடங்கு: 3 நிமிடங்கள்',
  chooseLanguage: 'மொழியைத் தேர்ந்தெடுக்கவும்',
  typeMessage: 'உங்கள் பதிலை எழுதுங்கள்…',
  send: 'அனுப்பு',
  yourPlan: 'உங்கள் திட்டம்',
  perMonth: '/மாதம்',
  continue: 'தொடரவும்',
  included: 'சேர்க்கப்பட்டது',
  optional: 'கூடுதல் சேவைகள்',
  kycTitle: 'உங்கள் தொழிலைச் சரிபார்க்கவும்',
  verifyNow: 'இப்போது சரிபார்க்கவும்',
  trackerTitle: 'ஆர்டர் நிலை',
}

i18n.use(initReactI18next).init({
  resources: { en: { t: en }, hi: { t: hi }, ta: { t: ta }, mr: { t: hi }, hinglish: { t: en } },
  lng: (() => {
    try {
      return localStorage.getItem('lang') || 'en'
    } catch {
      return 'en'
    }
  })(),
  fallbackLng: 'en',
  defaultNS: 't',
  interpolation: { escapeValue: false },
})

export function setLanguage(code: string) {
  i18n.changeLanguage(code)
  document.documentElement.lang = code === 'hinglish' ? 'hi-Latn' : code
  try {
    localStorage.setItem('lang', code)
  } catch {
    /* private mode */
  }
}

export const inr = (n: number) => '₹' + Math.round(n).toLocaleString('en-IN')

export default i18n
