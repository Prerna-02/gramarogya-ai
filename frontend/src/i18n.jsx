import { createContext, useContext, useState } from 'react'

// Prototype Hindi/Marathi translations (Devanagari) — PENDING native-speaker
// review before real use. English is the reference.
export const LANGS = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिंदी' },
  { code: 'mr', label: 'मराठी' },
]

const T = {
  greeting: { en: 'Hello', hi: 'नमस्ते', mr: 'नमस्कार' },
  how_help: { en: 'How can we help you today?', hi: 'आज हम आपकी कैसे मदद कर सकते हैं?', mr: 'आज आम्ही तुमची कशी मदत करू शकतो?' },
  search_ph: { en: 'Search services or facilities', hi: 'सेवाएँ या अस्पताल खोजें', mr: 'सेवा किंवा रुग्णालये शोधा' },
  find_hospital: { en: 'Find Nearest Hospital', hi: 'नज़दीकी अस्पताल खोजें', mr: 'जवळचे रुग्णालय शोधा' },
  find_hospital_sub: { en: 'Check availability of doctors, beds and waiting time', hi: 'डॉक्टर, बेड और प्रतीक्षा समय की उपलब्धता देखें', mr: 'डॉक्टर, बेड आणि प्रतीक्षा वेळेची उपलब्धता पाहा' },
  quick_access: { en: 'Quick Access', hi: 'त्वरित पहुँच', mr: 'त्वरित प्रवेश' },
  qa_find: { en: 'Find Hospital', hi: 'अस्पताल खोजें', mr: 'रुग्णालय शोधा' },
  qa_emergency: { en: 'Emergency Help', hi: 'आपातकालीन मदद', mr: 'आणीबाणी मदत' },
  qa_outbreak: { en: 'Outbreak Alerts', hi: 'प्रकोप चेतावनी', mr: 'उद्रेक सूचना' },
  qa_ambulance: { en: 'Ambulance Call', hi: 'एम्बुलेंस बुलाएँ', mr: 'रुग्णवाहिका बोलवा' },
  recommended: { en: 'Recommended for You', hi: 'आपके लिए अनुशंसित', mr: 'तुमच्यासाठी शिफारस' },
  best_match: { en: 'Best Match', hi: 'सर्वोत्तम', mr: 'सर्वोत्तम' },
  other_nearby: { en: 'Other Nearby Hospitals', hi: 'अन्य नज़दीकी अस्पताल', mr: 'इतर जवळची रुग्णालये' },
  distance: { en: 'Distance', hi: 'दूरी', mr: 'अंतर' },
  waiting_time: { en: 'Est. waiting', hi: 'अनुमानित प्रतीक्षा', mr: 'अंदाजे प्रतीक्षा' },
  beds_available: { en: 'Beds available', hi: 'उपलब्ध बेड', mr: 'उपलब्ध बेड' },
  view_details: { en: 'View details', hi: 'विवरण देखें', mr: 'तपशील पाहा' },
  choose_service: { en: 'What do you need?', hi: 'आपको क्या चाहिए?', mr: 'तुम्हाला काय हवे आहे?' },
  svc_general: { en: 'General', hi: 'सामान्य', mr: 'सामान्य' },
  svc_fever: { en: 'Fever / Infection', hi: 'बुखार / संक्रमण', mr: 'ताप / संसर्ग' },
  svc_maternity: { en: 'Maternity', hi: 'मातृत्व', mr: 'प्रसूती' },
  svc_trauma: { en: 'Injury / Trauma', hi: 'चोट / आघात', mr: 'दुखापत / आघात' },
  svc_emergency: { en: 'Emergency', hi: 'आपातकाल', mr: 'आणीबाणी' },
  results: { en: 'Facilities for you', hi: 'आपके लिए अस्पताल', mr: 'तुमच्यासाठी रुग्णालये' },
  call: { en: 'Call', hi: 'कॉल करें', mr: 'कॉल करा' },
  directions: { en: 'Directions', hi: 'दिशा-निर्देश', mr: 'दिशा' },
  services_available: { en: 'Services available', hi: 'उपलब्ध सेवाएँ', mr: 'उपलब्ध सेवा' },
  emergency_help: { en: 'Emergency Help', hi: 'आपातकालीन मदद', mr: 'आणीबाणी मदत' },
  call_ambulance: { en: 'Call Ambulance (108)', hi: 'एम्बुलेंस बुलाएँ (108)', mr: 'रुग्णवाहिका बोलवा (१०८)' },
  emergency_numbers: { en: 'Emergency Numbers', hi: 'आपातकालीन नंबर', mr: 'आणीबाणी क्रमांक' },
  outbreak_title: { en: 'Outbreak Alert', hi: 'प्रकोप चेतावनी', mr: 'उद्रेक सूचना' },
  last_verified: { en: 'Last verified', hi: 'अंतिम सत्यापित', mr: 'शेवटचे सत्यापित' },
  call_before: { en: 'Availability may change — please call before a long journey.', hi: 'उपलब्धता बदल सकती है — कृपया लंबी यात्रा से पहले कॉल करें।', mr: 'उपलब्धता बदलू शकते — कृपया लांब प्रवासापूर्वी कॉल करा.' },
  st_Available: { en: 'Available', hi: 'उपलब्ध', mr: 'उपलब्ध' },
  st_Limited: { en: 'Limited', hi: 'सीमित', mr: 'मर्यादित' },
  st_Busy: { en: 'Busy', hi: 'व्यस्त', mr: 'व्यस्त' },
  nav_home: { en: 'Home', hi: 'होम', mr: 'मुख्यपृष्ठ' },
  nav_hospitals: { en: 'Hospitals', hi: 'अस्पताल', mr: 'रुग्णालये' },
  nav_alerts: { en: 'Alerts', hi: 'सूचनाएँ', mr: 'सूचना' },
  nav_emergency: { en: 'Emergency', hi: 'आपातकाल', mr: 'आणीबाणी' },
  back: { en: 'Back', hi: 'वापस', mr: 'मागे' },
  min: { en: 'min', hi: 'मिनट', mr: 'मिनिटे' },
  km: { en: 'km', hi: 'किमी', mr: 'किमी' },
  disclaimer: { en: 'Guidance only — this app does not diagnose. In an emergency call 108.', hi: 'केवल मार्गदर्शन — यह ऐप निदान नहीं करता। आपातकाल में 108 पर कॉल करें।', mr: 'फक्त मार्गदर्शन — हे ॲप निदान करत नाही. आणीबाणीत १०८ वर कॉल करा.' },
  no_outbreak: { en: 'No active outbreak alerts in your area right now.', hi: 'अभी आपके क्षेत्र में कोई सक्रिय प्रकोप चेतावनी नहीं है।', mr: 'सध्या तुमच्या भागात कोणतीही सक्रिय उद्रेक सूचना नाही.' },
  stay_safe: { en: 'Stay safe', hi: 'सुरक्षित रहें', mr: 'सुरक्षित राहा' },
}

const I18nContext = createContext(null)

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(localStorage.getItem('gramarogya_lang') || 'en')
  const setLang = (l) => { localStorage.setItem('gramarogya_lang', l); setLangState(l) }
  const t = (key) => (T[key]?.[lang] ?? T[key]?.en ?? key)
  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>
}

export const useI18n = () => useContext(I18nContext)
