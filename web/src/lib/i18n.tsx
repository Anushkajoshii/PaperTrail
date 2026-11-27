/* Lightweight English / Hindi interface strings.
 *
 * The interface chrome (navigation, landing page, form labels, progress steps) is translated.
 * Results content (claims, explanations, SEBI sources) stays in the language the analysis
 * produced, with original quotes always shown as spoken.
 */
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type UiLang = "en" | "hi";

const en = {
  "nav.check": "Check content",
  "nav.ledger": "Claim Ledger",
  "nav.rulebook": "SEBI rulebook",
  "nav.glossary": "Glossary",
  "nav.how": "How it works",
  "lang.toggle": "हिन्दी",
  "hero.eyebrow": "For Indian investors",
  "hero.title": "Check the claims, not the hype.",
  "hero.subtitle":
    "PaperTrail checks what finance creators say. It finds every checkable claim, weighs the evidence from trusted sources, and shows which statements official SEBI material warns about, in plain language.",
  "hero.cta": "Check a video or post",
  "hero.secondary": "See how it works",
  "hero.note": "Free to try. Not financial advice.",
  "how.title": "How a check works",
  "how.1.title": "Share the content",
  "how.1.body": "Paste text, add an article link, or upload subtitles. Hindi, English and Hinglish all work.",
  "how.2.title": "We find the claims",
  "how.2.body": "Only checkable facts, such as returns, targets, results and credentials, each with the exact words used.",
  "how.3.title": "We weigh the evidence",
  "how.3.body": "Exchange data, filings, regulators and established news, each rated for reliability, recency and relevance.",
  "how.4.title": "You see the verdict and why",
  "how.4.body": "Supported, contradicted, misleading or not verifiable, with sources, gaps and an honest confidence note.",
  "form.title": "Check finance content",
  "form.subtitle": "Share what a creator said. We'll check each claim against trusted sources and SEBI's rulebook.",
  "form.tab.text": "Paste text",
  "form.tab.url": "Article link",
  "form.tab.file": "Upload file",
  "form.creator": "Creator (optional)",
  "form.creator.help": "Their handle, like @creatorname. Used to check SEBI registration and group checks.",
  "form.name": "Registered or legal name (optional)",
  "form.language": "Language",
  "form.language.auto": "Detect automatically",
  "form.submit": "Start check",
  "form.sample": "Try a sample",
  "progress.title": "Checking the content",
  "progress.subtitle": "This usually takes under a minute. You can keep this page open.",
  "footer.disclaimer":
    "PaperTrail assesses specific claims against available evidence. It is not financial advice and never recommends buying or selling securities. Verdicts are about claims, not people.",
};

const hi: typeof en = {
  "nav.check": "कंटेंट जाँचें",
  "nav.ledger": "स्टॉक कॉल रिकॉर्ड",
  "nav.rulebook": "सेबी नियम-पुस्तिका",
  "nav.glossary": "शब्दावली",
  "nav.how": "यह कैसे काम करता है",
  "lang.toggle": "English",
  "hero.eyebrow": "भारतीय निवेशकों के लिए",
  "hero.title": "दावों की जाँच करें, हाइप की नहीं।",
  "hero.subtitle":
    "PaperTrail फ़ाइनेंस क्रिएटर्स की बातों की जाँच करता है। यह हर जाँचने लायक दावे को ढूँढता है, भरोसेमंद स्रोतों से सबूत परखता है, और सरल भाषा में बताता है कि सेबी के आधिकारिक दस्तावेज़ किन बातों के बारे में चेतावनी देते हैं।",
  "hero.cta": "वीडियो या पोस्ट जाँचें",
  "hero.secondary": "देखें यह कैसे काम करता है",
  "hero.note": "मुफ़्त आज़माएँ। यह वित्तीय सलाह नहीं है।",
  "how.title": "जाँच कैसे होती है",
  "how.1.title": "कंटेंट साझा करें",
  "how.1.body": "टेक्स्ट पेस्ट करें, लेख का लिंक दें, या सबटाइटल अपलोड करें। हिंदी, अंग्रेज़ी और हिंग्लिश सभी चलती हैं।",
  "how.2.title": "हम दावे ढूँढते हैं",
  "how.2.body": "सिर्फ़ जाँचने लायक तथ्य, जैसे रिटर्न, टारगेट, नतीजे और रजिस्ट्रेशन, बोले गए सटीक शब्दों के साथ।",
  "how.3.title": "हम सबूत परखते हैं",
  "how.3.body": "एक्सचेंज डेटा, कंपनी फ़ाइलिंग, नियामक और प्रतिष्ठित समाचार, हर स्रोत की विश्वसनीयता, ताज़गी और प्रासंगिकता के साथ।",
  "how.4.title": "आपको फ़ैसला और कारण दिखता है",
  "how.4.body": "समर्थित, खंडित, भ्रामक या असत्यापित, स्रोतों, कमियों और ईमानदार भरोसे के स्तर के साथ।",
  "form.title": "फ़ाइनेंस कंटेंट जाँचें",
  "form.subtitle": "क्रिएटर ने जो कहा उसे साझा करें। हम हर दावे को भरोसेमंद स्रोतों और सेबी के नियमों से मिलाएँगे।",
  "form.tab.text": "टेक्स्ट पेस्ट करें",
  "form.tab.url": "लेख का लिंक",
  "form.tab.file": "फ़ाइल अपलोड करें",
  "form.creator": "क्रिएटर (वैकल्पिक)",
  "form.creator.help": "उनका हैंडल, जैसे @creatorname। सेबी रजिस्ट्रेशन जाँचने और जाँचों को समूह में रखने के लिए।",
  "form.name": "रजिस्टर्ड या क़ानूनी नाम (वैकल्पिक)",
  "form.language": "भाषा",
  "form.language.auto": "स्वतः पहचानें",
  "form.submit": "जाँच शुरू करें",
  "form.sample": "नमूना आज़माएँ",
  "progress.title": "कंटेंट की जाँच हो रही है",
  "progress.subtitle": "आमतौर पर एक मिनट से कम लगता है। यह पेज खुला रख सकते हैं।",
  "footer.disclaimer":
    "PaperTrail उपलब्ध सबूतों के आधार पर विशिष्ट दावों का आकलन करता है। यह वित्तीय सलाह नहीं है और कभी भी किसी प्रतिभूति को ख़रीदने या बेचने की सलाह नहीं देता। फ़ैसले दावों के बारे में हैं, लोगों के बारे में नहीं।",
};

export type MessageKey = keyof typeof en;
const MESSAGES: Record<UiLang, typeof en> = { en, hi };

interface I18n {
  lang: UiLang;
  setLang: (l: UiLang) => void;
  t: (key: MessageKey) => string;
}

const Ctx = createContext<I18n>({ lang: "en", setLang: () => {}, t: (k) => en[k] });

function initialLang(): UiLang {
  try {
    return localStorage.getItem("pt-lang") === "hi" ? "hi" : "en";
  } catch {
    return "en";
  }
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<UiLang>(initialLang);
  useEffect(() => {
    document.documentElement.lang = lang;
    try {
      localStorage.setItem("pt-lang", lang);
    } catch {
      /* private mode */
    }
  }, [lang]);
  return <Ctx.Provider value={{ lang, setLang, t: (k) => MESSAGES[lang][k] }}>{children}</Ctx.Provider>;
}

export const useI18n = () => useContext(Ctx);
