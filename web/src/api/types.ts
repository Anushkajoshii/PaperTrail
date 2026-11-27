// Friendly names for the types generated from the API's OpenAPI spec (npm run gen:api).
// The generated file is the single source of truth, so the UI breaks at compile time if the
// API changes shape.
import type { components } from "./schema";

type S = components["schemas"];

export type Check = S["Check"];
export type CheckView = S["CheckView"];
export type CheckAccepted = S["CheckAccepted"];
export type CheckSummary = S["CheckSummary"];
export type CreatorProfile = S["CreatorProfile"];
export type CompareView = S["CompareView"];
export type LedgerView = S["LedgerView"];
export type LedgerSummary = S["LedgerSummary"];
export type LedgerEntryView = S["LedgerEntryView"];
export type LedgerStatus = S["LedgerEntry"]["status"];
export type TimelineItem = S["TimelineItem"];
export type TrackRecord = S["TrackRecord"];
export type CreateCheckRequest = S["CreateCheckRequest"];
export type Claim = S["Claim"];
export type Evidence = S["Evidence"];
export type Verdict = S["Verdict"];
export type RedFlag = S["RedFlag"];
export type RegulatorySource = S["RegulatorySource"];
export type SebiRegistration = S["SebiRegistration"];
export type GlossaryTerm = S["GlossaryTerm"];
export type RulebookResponse = S["RulebookResponse"];
export type RuleEntry = S["RuleEntry"];
export type Health = S["Health"];

export type VerdictLabel = Verdict["label"];
export type CheckStatus = Check["status"];
export type Language = NonNullable<CreateCheckRequest["language_hint"]>;
