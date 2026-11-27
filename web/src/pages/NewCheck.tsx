import { FileText, Link2, LoaderCircle, Sparkles, Upload } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { ApiError, api } from "../api/client";
import type { Language } from "../api/types";
import { PageHeader } from "../components/States";
import { Term } from "../components/Term";
import { useI18n } from "../lib/i18n";

type Mode = "text" | "url" | "file";

const MAX_CHARS = 50_000;
const TEXT_TYPES = [".srt", ".vtt", ".txt"];
const MEDIA_TYPES = [".mp3", ".mp4", ".m4a", ".wav", ".webm", ".ogg", ".flac"];

// Synthetic samples (they imitate common patterns; no real creator is quoted).
const SAMPLES: { label: string; handle: string; text: string }[] = [
  {
    label: "Hinglish reel",
    handle: "@demo_finfluencer",
    text:
      "Namaste doston, aaj main aapko ek multibagger stock bataunga. Main SEBI registered advisor hoon, toh aap mujh par bharosa kar sakte ho. TATAMOTORS ka target ₹1500 hai, March tak pakka jayega. Pichle saal is stock ne 300% return diya tha. Mere premium Telegram group mein guaranteed 5% har mahine milega, bilkul risk-free.",
  },
  {
    label: "English post",
    handle: "@demo_markets",
    text:
      "Nifty 50 hit an all-time high of 26,277 on 27 September 2024. RELIANCE reported a net profit of ₹19,000 crore in the September quarter. My model portfolio returned 85% in 2023, beating every mutual fund. Personally, I think banking stocks look attractive.",
  },
  {
    label: "Hindi clip",
    handle: "@demo_hindi",
    text: "दोस्तों, इस शेयर ने पिछले साल 200% रिटर्न दिया। मेरे साथ जुड़ो, हर महीने 10% की गारंटी है।",
  },
];

export function NewCheck() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("text");
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [handle, setHandle] = useState("");
  const [name, setName] = useState("");
  const [language, setLanguage] = useState<Language | "">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const ready =
    (mode === "text" && text.trim().length >= 10 && text.length <= MAX_CHARS) ||
    (mode === "url" && /^https?:\/\/\S+\.\S+/.test(url.trim())) ||
    (mode === "file" && file !== null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    const common = {
      creator_handle: handle.trim() || undefined,
      creator_name: name.trim() || undefined,
      language_hint: language || undefined,
    };
    try {
      const accepted =
        mode === "file" && file
          ? await api.uploadCheck(file, { creatorHandle: common.creator_handle, creatorName: common.creator_name, language: common.language_hint })
          : await api.createCheck(mode === "text" ? { kind: "text", text, ...common } : { kind: "article_url", url: url.trim(), ...common });
      navigate(`/checks/${accepted.id}`);
    } catch (err) {
      const e2 = err as ApiError;
      setError(e2.code === "rate_limited" ? `Too many checks in a short time. Please wait ${e2.retryAfter ?? 60} seconds.` : e2.message);
      setBusy(false);
    }
  }

  const tabs: { id: Mode; label: string; icon: typeof FileText }[] = [
    { id: "text", label: t("form.tab.text"), icon: FileText },
    { id: "url", label: t("form.tab.url"), icon: Link2 },
    { id: "file", label: t("form.tab.file"), icon: Upload },
  ];
  const isMedia = file ? MEDIA_TYPES.some((ext) => file.name.toLowerCase().endsWith(ext)) : false;

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <PageHeader eyebrow="New check" title={t("form.title")}>
        {t("form.subtitle")}
      </PageHeader>

      <form onSubmit={submit} className="card p-6 sm:p-8" noValidate>
        <fieldset>
          <legend className="text-sm font-semibold">1. What do you want to check?</legend>
          <div role="tablist" aria-label="Input type" className="mt-3 grid grid-cols-3 gap-2 rounded-xl bg-slate-100 p-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={mode === tab.id}
                onClick={() => setMode(tab.id)}
                className={`flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition ${mode === tab.id ? "bg-white text-ink shadow-sm" : "text-slate-600 hover:text-ink"}`}
              >
                <tab.icon className="h-4 w-4" aria-hidden="true" />
                <span className="hidden sm:inline">{tab.label}</span>
              </button>
            ))}
          </div>

          <div className="mt-5">
            {mode === "text" && (
              <div>
                <label htmlFor="text" className="sr-only">
                  Content to check
                </label>
                <textarea
                  id="text"
                  className="input min-h-48 resize-y leading-relaxed"
                  placeholder="Paste a caption, post, transcript or forwarded message…"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  maxLength={MAX_CHARS}
                />
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                  <span className="inline-flex flex-wrap items-center gap-2">
                    <Sparkles className="h-3.5 w-3.5 text-brand-600" aria-hidden="true" /> {t("form.sample")}:
                    {SAMPLES.map((s) => (
                      <button
                        key={s.label}
                        type="button"
                        className="rounded-full border border-slate-200 px-2.5 py-0.5 hover:border-brand-600 hover:text-brand-700"
                        onClick={() => {
                          setText(s.text);
                          setHandle(s.handle);
                        }}
                      >
                        {s.label}
                      </button>
                    ))}
                  </span>
                  <span>
                    {text.length.toLocaleString("en-IN")} / {MAX_CHARS.toLocaleString("en-IN")}
                  </span>
                </div>
              </div>
            )}

            {mode === "url" && (
              <div>
                <label htmlFor="url" className="text-sm text-slate-600">
                  Link to a public article or web page
                </label>
                <input id="url" type="url" inputMode="url" className="input mt-2" placeholder="https://…" value={url} onChange={(e) => setUrl(e.target.value)} />
                <p className="mt-2 text-xs leading-relaxed text-slate-500">
                  We read the page's text safely. YouTube and Instagram links can't be downloaded, as that breaks their terms; upload the clip's subtitles instead.
                </p>
              </div>
            )}

            {mode === "file" && (
              <div>
                <button
                  type="button"
                  onClick={() => fileInput.current?.click()}
                  className="flex w-full flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center hover:border-brand-600"
                >
                  <Upload className="h-7 w-7 text-brand-600" aria-hidden="true" />
                  <span className="font-medium">{file ? file.name : "Choose a file"}</span>
                  <span className="text-xs text-slate-500">Subtitles (.srt, .vtt) or a transcript (.txt). Audio and video need cloud transcription.</span>
                </button>
                <input
                  ref={fileInput}
                  type="file"
                  className="sr-only"
                  accept={[...TEXT_TYPES, ...MEDIA_TYPES].join(",")}
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  aria-label="File to check"
                />
                {isMedia && (
                  <p className="mt-3 rounded-xl bg-amber-50 px-4 py-3 text-xs leading-relaxed text-misleading">
                    Audio and video are transcribed with Amazon Transcribe in the cloud version. Running locally, please upload subtitles or a transcript instead.
                  </p>
                )}
              </div>
            )}
          </div>
        </fieldset>

        <fieldset className="mt-8 grid gap-5 sm:grid-cols-2">
          <legend className="col-span-full text-sm font-semibold">2. Who said it? (optional)</legend>
          <div>
            <label htmlFor="handle" className="text-sm text-slate-600">
              {t("form.creator")}
            </label>
            <input id="handle" className="input mt-2" placeholder="@creatorname" value={handle} onChange={(e) => setHandle(e.target.value)} maxLength={100} />
            <p className="mt-1.5 text-xs text-slate-500">{t("form.creator.help")}</p>
          </div>
          <div>
            <label htmlFor="name" className="text-sm text-slate-600">
              {t("form.name")}
            </label>
            <input id="name" className="input mt-2" placeholder="As shown on SEBI's register" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
            <p className="mt-1.5 text-xs text-slate-500">
              Helps match the <Term term="Research Analyst">SEBI register</Term>.
            </p>
          </div>
          <div>
            <label htmlFor="lang" className="text-sm text-slate-600">
              {t("form.language")}
            </label>
            <select id="lang" className="input mt-2" value={language} onChange={(e) => setLanguage(e.target.value as Language | "")}>
              <option value="">{t("form.language.auto")}</option>
              <option value="en">English</option>
              <option value="hi">Hindi</option>
              <option value="hinglish">Hinglish</option>
            </select>
          </div>
        </fieldset>

        {error && (
          <p role="alert" className="mt-6 rounded-xl bg-contradicted-bg px-4 py-3 text-sm text-contradicted">
            {error}
          </p>
        )}

        <div className="mt-8 flex flex-col-reverse items-stretch gap-4 border-t border-slate-100 pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs leading-relaxed text-slate-500">Not financial advice. Verdicts are about claims, not people.</p>
          <button type="submit" className="btn-primary" disabled={!ready || busy}>
            {busy && <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />}
            {t("form.submit")}
          </button>
        </div>
      </form>
    </div>
  );
}
