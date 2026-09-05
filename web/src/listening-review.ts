import type { PlaybackMetrics, PlaybackRequest, PreviewPlayer } from "./preview-player";

export const LISTENING_SCHEMA = "simo.breeze.listening.v1";
export interface Clip { id: string; label: string; samples: number; pcm_sha256: string; wav_sha256: string }
interface Case { id: string; text: string; instruction: string; seed: number; clips: Clip[] }
export interface Deck { schema: string; deck_sha256: string; cases: Case[]; server_results?: boolean }
export interface BenchmarkManifest {
  schema: string; manifest_sha256: string; runtime_fingerprint: string; playback_policy: string;
  suites: Record<string, string[]>; instructions: Record<string, string>; assets_sha256: Record<string, string>;
}
type Answer = "yes" | "no" | "uncertain";
export interface Rating {
  clip_id: string; pcm_sha256: string; heard_fully: Answer; intelligible: Answer;
  complete_words: Answer; instruction: Answer; natural: Answer; gap_free: Answer; notes: string;
  answered?: string[];
}
export interface Attempt {
  ordinal: number; lane: "recorded" | "fresh"; clip_id?: string; case_id?: string;
  trial?: { suite: string; index: number; seed: number; instruction_id: string };
  status: "running" | "complete" | "stopped" | "failed"; started: string;
  metrics?: PlaybackMetrics; error?: string; producer?: unknown;
  benchmark_manifest?: BenchmarkManifest;
  listener: { heard: Answer; gaps: Answer; start: "unreported" | "prompt" | "delayed" | "uncertain"; notes: string; answered?: string[] };
}
const hex = (value: unknown, size: number): value is string => typeof value === "string" && new RegExp(`^[0-9a-f]{${size}}$`).test(value);

export function validateDeck(deck: Deck): void {
  if (deck.schema !== LISTENING_SCHEMA || !hex(deck.deck_sha256, 64) || !Array.isArray(deck.cases) || deck.cases.length !== 18) throw new Error("Invalid listening deck");
  const ids = new Set<string>();
  for (const item of deck.cases) {
    if (!hex(item.id, 32) || ids.has(item.id) || typeof item.text !== "string" || typeof item.instruction !== "string" || !Number.isInteger(item.seed) || item.clips?.length !== 4) throw new Error("Invalid listening case");
    ids.add(item.id);
    for (const [index, clip] of item.clips.entries()) {
      if (!hex(clip.id, 32) || ids.has(clip.id) || clip.label !== "ABCD"[index] || !hex(clip.pcm_sha256, 64) || !hex(clip.wav_sha256, 64) || !Number.isInteger(clip.samples) || clip.samples <= 0 || clip.samples > 120 * 24000) throw new Error("Invalid listening clip");
      ids.add(clip.id);
    }
  }
}

export function recordedRequest(deck: Deck, clip: Clip): PlaybackRequest {
  return {
    headers: { "X-Simo-Listening-Deck": deck.deck_sha256 },
    expectedHeaders: { "X-Simo-Listening-Deck": deck.deck_sha256, "X-Simo-Cache": "RECORDED", "X-Simo-PCM-SHA256": clip.pcm_sha256, "X-Simo-Audio-Samples": String(clip.samples) },
    recordedPCM: { samples: clip.samples, sha256: clip.pcm_sha256 },
    onResponse: response => {
      if (response.headers.has("X-Simo-Runtime-Fingerprint") || response.headers.has("X-Breeze-Request-ID")) throw new Error("Recorded audio was mislabeled as live inference");
    },
  };
}

export function validateProducer(payload: unknown, manifest: BenchmarkManifest, metrics: PlaybackMetrics): unknown {
  const envelope = payload as { manifest_sha256?: unknown; runtime?: { runtime_fingerprint?: unknown; busy?: unknown; last_request?: Record<string, unknown> } };
  const runtime = envelope?.runtime;
  const producer = runtime?.last_request;
  if (envelope?.manifest_sha256 !== manifest.manifest_sha256 || runtime?.runtime_fingerprint !== manifest.runtime_fingerprint || runtime?.busy !== false || !producer
    || producer.request_id !== metrics.requestId || producer.completed !== true || producer.eos_reached !== true || producer.cancelled !== false
    || producer.audio_samples !== metrics.receivedFrames || !Number.isInteger(producer.codec_frames) || (producer.codec_frames as number) <= 0
    || producer.audio_samples !== (producer.codec_frames as number) * 1920 || producer.audio_s !== metrics.receivedFrames / 24000) throw new Error("Matching completed producer evidence unavailable");
  return producer;
}

export class ListeningSession {
  readonly attempts: Attempt[] = [];
  readonly ratings = new Map<string, Rating>();
  readonly preferences = new Map<string, string>();
  readonly seenRequestIds = new Set<string>();
  started = new Date().toISOString();
  readonly deck: Deck;
  constructor(deck: Deck) { validateDeck(deck); this.deck = deck; }
  begin(lane: Attempt["lane"], details: Partial<Attempt>): Attempt {
    if (this.attempts.some(attempt => attempt.status === "running")) throw new Error("A listening trial is already running");
    const attempt: Attempt = { ...details, ordinal: this.attempts.length, lane, status: "running", started: new Date().toISOString(), listener: { heard: "uncertain", gaps: "uncertain", start: "unreported", notes: "", answered: [] } };
    this.attempts.push(attempt); return attempt;
  }
  freshRequest(manifest: BenchmarkManifest, attempt: Attempt): PlaybackRequest {
    if (!hex(manifest.manifest_sha256, 64) || !hex(manifest.runtime_fingerprint, 64) || manifest.schema !== "simo.breeze.https-benchmark.v1" || manifest.playback_policy !== "mlx-stream-v1" || !attempt.trial) throw new Error("Invalid fresh-trial manifest");
    return {
      body: { seed: attempt.trial.seed, instruction_id: attempt.trial.instruction_id },
      headers: { "Content-Type": "application/json", "X-Simo-Benchmark-Manifest": manifest.manifest_sha256, "X-Simo-Runtime-Fingerprint": manifest.runtime_fingerprint },
      expectedHeaders: { "X-Simo-Benchmark-Manifest": manifest.manifest_sha256, "X-Simo-Runtime-Fingerprint": manifest.runtime_fingerprint, "X-Simo-Playback-Policy": "mlx-stream-v1", "X-Simo-Cache": "BYPASS" },
      onResponse: response => {
        const id = response.headers.get("X-Breeze-Request-ID") ?? "";
        if (!/^api-[0-9a-f]{32}$/.test(id) || this.seenRequestIds.has(id)) throw new Error("Missing or reused producer request ID");
        this.seenRequestIds.add(id);
      },
      onEOF: async (metrics, signal) => {
        // EOF can precede sidecar lock cleanup. Retry only this exact ID, bounded
        // by attempts AND a wall deadline; a later request is never substituted.
        const controller = new AbortController();
        const abort = (): void => controller.abort(signal.reason);
        signal.addEventListener("abort", abort, { once: true });
        const timer = setTimeout(() => controller.abort(new Error("Producer evidence timed out; trial is not accepted")), 5000);
        try {
          signal.throwIfAborted();
          for (let retry = 0; retry < 40; retry++) {
            controller.signal.throwIfAborted();
            const response = await fetch(`/api/benchmarks/metrics/${metrics.requestId}`, { cache: "no-store", signal: controller.signal });
            if (response.ok) { attempt.producer = validateProducer(await response.json(), manifest, metrics); return; }
            if (response.status !== 409) break;
            await new Promise<void>((resolve, reject) => {
              const stop = (): void => { clearTimeout(pause); controller.signal.removeEventListener("abort", stop); reject(controller.signal.reason); };
              const pause = setTimeout(() => { controller.signal.removeEventListener("abort", stop); resolve(); }, 50);
              controller.signal.addEventListener("abort", stop, { once: true });
              if (controller.signal.aborted) stop();
            });
          }
          throw new Error("Producer evidence unavailable; trial is not accepted");
        } finally { clearTimeout(timer); signal.removeEventListener("abort", abort); }
      },
    };
  }
  export(conditions: string, manifest: BenchmarkManifest | null, browser: string): object {
    if (this.attempts.some(attempt => attempt.status === "running")) throw new Error("Stop or finish the current trial before exporting");
    return this.snapshot(conditions, manifest, browser);
  }
  snapshot(conditions: string, manifest: BenchmarkManifest | null, browser: string, view = { position: 0, clip: "A" }): Snapshot {
    return { schema: LISTENING_SCHEMA, deck_sha256: this.deck.deck_sha256, started: this.started, exported: new Date().toISOString(),
      conditions, browser, player: "preview-player/listening-v1", manifest, ratings: [...this.ratings.values()], preferences: [...this.preferences.entries()], attempts: this.attempts,
      view, quality_accepted: false, acoustic_onset: "unmeasured", limits: "Recorded clips do not measure synthesis. Browser receipt can be playback-paced; it is not unpaced producer RTF. Output estimates and worklet drains do not establish acoustic onset, intelligibility or mute/Bluetooth/device behavior." };
  }
  restore(data: Snapshot): boolean {
    const clips = new Map(this.deck.cases.flatMap(item => item.clips.map(clip => [clip.id, clip] as const)));
    if (data.schema !== LISTENING_SCHEMA || data.deck_sha256 !== this.deck.deck_sha256 || data.quality_accepted !== false || typeof data.conditions !== "string"
      || !Number.isFinite(Date.parse(data.started)) || !Array.isArray(data.ratings) || !Array.isArray(data.preferences) || !Array.isArray(data.attempts)
      || data.ratings.some(rating => clips.get(rating.clip_id)?.pcm_sha256 !== rating.pcm_sha256 || Object.keys(fields).some(key => !["yes", "no", "uncertain"].includes(rating[key as keyof typeof fields])))
      || data.attempts.some((attempt, index) => attempt.ordinal !== index || !["recorded", "fresh"].includes(attempt.lane) || !["running", "complete", "stopped", "failed"].includes(attempt.status) || !attempt.listener)
      || (data.view && (!Number.isInteger(data.view.position) || data.view.position < 0 || data.view.position >= 18 || !["A", "B", "C", "D"].includes(data.view.clip)))) throw new Error("Saved listening results do not match this deck");
    this.started = data.started;
    for (const rating of data.ratings) this.ratings.set(rating.clip_id, rating);
    for (const [id, value] of data.preferences) this.preferences.set(id, value);
    let interrupted = false;
    for (const attempt of data.attempts) {
      if (attempt.status === "running") { attempt.status = "stopped"; attempt.error = "Page closed before the trial finished; playback was not resumed."; interrupted = true; }
      if (attempt.metrics?.requestId) this.seenRequestIds.add(attempt.metrics.requestId);
      this.attempts.push(attempt);
    }
    return interrupted;
  }
}

export interface Snapshot {
  schema: string; deck_sha256: string; started: string; exported: string; conditions: string; browser: string;
  player: string; manifest: BenchmarkManifest | null; ratings: Rating[]; preferences: [string, string][]; attempts: Attempt[];
  view?: { position: number; clip: string }; quality_accepted: false; acoustic_onset: string; limits: string;
}
interface Draft { session_id: string; revision: number; pending: string | null; latest: Snapshot | null }
const savedSchema = "simo.breeze.listening.saved.v1";
const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

/** One in-flight write, immutable retry bytes, and a synchronous local recovery draft. */
export class ListeningAutosave {
  private draft: Draft;
  private storage: Pick<Storage, "getItem" | "setItem"> | null;
  private readonly key: string;
  private inFlight: Promise<void> | null = null;
  private storageFailed = false;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private readonly deck: string;
  private readonly notify: (message: string) => void;
  conflict = false;
  constructor(deck: string, storage: Pick<Storage, "getItem" | "setItem"> | null, notify: (message: string) => void) {
    this.deck = deck; this.notify = notify;
    this.storage = storage; this.key = `simo-listening-v1:${deck}`;
    this.draft = { session_id: crypto.randomUUID().replaceAll("-", ""), revision: 0, pending: null, latest: null };
    let raw: string | null = null;
    try { raw = storage?.getItem(this.key) ?? null; } catch { this.storageFailed = true; }
    if (raw) {
      const data = JSON.parse(raw) as Draft;
      if (!hex(data.session_id, 32) || !Number.isInteger(data.revision) || data.revision < 0 || data.revision > 2000 || (data.pending !== null && typeof data.pending !== "string") || (data.latest && data.latest.deck_sha256 !== deck)) throw new Error("Local recovery draft is invalid; it has not been overwritten");
      if (data.pending) {
        const pending = JSON.parse(data.pending) as { revision: number; snapshot: Snapshot };
        if (pending.revision !== data.revision + 1 || pending.snapshot?.deck_sha256 !== deck) throw new Error("Local pending save is invalid; it has not been overwritten");
      }
      this.draft = data;
    }
    this.storageFailed ||= storage === null;
  }
  private message(value: string): void { this.notify(value + (this.storageFailed ? " Browser recovery unavailable; keep this page open until saved." : "")); }
  private retain(): void {
    try { this.storage?.setItem(this.key, JSON.stringify(this.draft)); } catch { this.storageFailed = true; }
  }
  private async request(options?: RequestInit): Promise<{ ok: boolean; status: number; data: unknown }> {
    const controller = new AbortController();
    let timeout: ReturnType<typeof setTimeout> | undefined;
    const deadline = new Promise<never>((_resolve, reject) => { timeout = setTimeout(() => { controller.abort(); reject(new Error("Server response timed out; tap Retry save.")); }, 10000); });
    try {
      return await Promise.race([deadline, (async () => {
        const response = await fetch(`/api/listening/results/${this.draft.session_id}`, { ...options, cache: "no-store", signal: controller.signal, headers: { "Content-Type": "application/json", "X-Simo-Listening-Deck": this.deck } });
        if (!response.ok) return { ok: false, status: response.status, data: null };
        const raw = await response.text();
        if (raw.length > 256 * 1024 + 1024) throw new Error("Saved server response exceeds limit");
        return { ok: true, status: response.status, data: JSON.parse(raw) as unknown };
      })()]);
    } finally { clearTimeout(timeout); controller.abort(); }
  }
  async restore(): Promise<Snapshot | null> {
    if (this.draft.pending) { await this.flush(); if (this.draft.pending) return clone(this.draft.latest); }
    if (!this.draft.revision) return clone(this.draft.latest);
    try {
      const response = await this.request();
      if (!response.ok) throw new Error("Could not load saved results. Your local draft is retained; tap Retry save.");
      const data = response.data as { schema: string; session_id: string; revision: number; snapshot: Snapshot };
      if (data.schema !== savedSchema || data.session_id !== this.draft.session_id || !Number.isInteger(data.revision) || data.revision < this.draft.revision || data.snapshot?.deck_sha256 !== this.deck) throw new Error("Saved session identity mismatch");
      this.draft.revision = data.revision; this.draft.latest = data.snapshot; this.retain(); this.message("Saved on this server · restored session");
    } catch (error) { this.message(String(error)); }
    return clone(this.draft.latest);
  }
  save(snapshot: Snapshot): void {
    this.draft.latest = clone(snapshot);
    if (!this.draft.pending) this.draft.pending = JSON.stringify({ revision: this.draft.revision + 1, snapshot: this.draft.latest });
    this.retain(); this.message(this.conflict ? "Save conflict. Your draft is safe here; save it as a separate session." : "Saving…");
    clearTimeout(this.timer);
    if (!this.conflict) this.timer = setTimeout(() => { void this.flush(); }, 300);
  }
  flush(): Promise<void> {
    clearTimeout(this.timer);
    if (this.inFlight) return this.inFlight;
    this.inFlight = this.send().finally(() => { this.inFlight = null; });
    return this.inFlight;
  }
  private async send(): Promise<void> {
    if (this.conflict) return;
    try {
      while (this.draft.pending) {
        const body = this.draft.pending;
        const pending = JSON.parse(body) as { revision: number; snapshot: Snapshot };
        const response = await this.request({ method: "PUT", body });
        if (response.status === 409) { this.conflict = true; throw new Error("Save conflict. Another tab changed this session; save your draft as a separate session."); }
        if (!response.ok) throw new Error(`Server save failed (${response.status}). Your draft is retained; tap Retry save.`);
        const ack = response.data as { schema: string; session_id: string; revision: number; deck_sha256: string };
        if (ack.schema !== savedSchema || ack.session_id !== this.draft.session_id || ack.revision !== pending.revision || ack.deck_sha256 !== this.deck) throw new Error("Save acknowledgment mismatch; tap Retry save.");
        this.draft.revision = pending.revision;
        this.draft.pending = JSON.stringify(this.draft.latest) === JSON.stringify(pending.snapshot) ? null : JSON.stringify({ revision: this.draft.revision + 1, snapshot: this.draft.latest });
        this.retain();
      }
      this.message("Saved on this server");
    } catch (error) { this.message(`Not saved: ${error instanceof Error ? error.message : String(error)}`); }
  }
  async separateSession(): Promise<void> {
    if (this.inFlight) await this.inFlight;
    if (!this.conflict || !this.draft.latest) return;
    this.draft = { session_id: crypto.randomUUID().replaceAll("-", ""), revision: 0, pending: null, latest: this.draft.latest };
    this.conflict = false; this.save(this.draft.latest!); await this.flush();
  }
}

function node<K extends keyof HTMLElementTagNameMap>(tag: K, text = ""): HTMLElementTagNameMap[K] {
  const element = document.createElement(tag); element.textContent = text; return element;
}
const fields = { heard_fully: "Heard the whole clip", intelligible: "Easy to understand", complete_words: "All words correct", instruction: "Instruction followed", natural: "No unnatural artifacts", gap_free: "No audible gaps" } as const;
function radios(label: string, name: string, options: string[], selected: string | undefined, change: (value: string) => void): HTMLFieldSetElement {
  const group = node("fieldset"); group.append(node("legend", label));
  const choices = node("div"); choices.className = "listening-choices";
  for (const value of options) {
    const wrapper = node("label"); const input = node("input"); input.type = "radio"; input.name = name; input.value = value; input.checked = value === selected;
    input.addEventListener("change", () => { if (input.checked) change(value); });
    wrapper.append(input, node("span", ({ yes: "Yes", no: "No", uncertain: "Unsure", tie: "Tie", unreported: "Not rated", prompt: "Quick", delayed: "Slow" } as Record<string, string>)[value] ?? value)); choices.append(wrapper);
  }
  group.append(choices); return group;
}

/** Loading/advancing/exporting never constructs a player. Only explicit tap handlers do. */
export async function mountListening(root: HTMLElement, createPlayer: () => PreviewPlayer): Promise<boolean> {
  const response = await fetch("/api/listening", { cache: "no-store" });
  if (response.status === 404) return false;
  if (!response.ok) throw new Error("Listening deck unavailable");
  const session = new ListeningSession(await response.json() as Deck);
  let manifest: BenchmarkManifest | null = null;
  try { const benchmark = await fetch("/api/benchmarks", { cache: "no-store" }); if (benchmark.ok) manifest = await benchmark.json() as BenchmarkManifest; } catch { /* Recorded listening remains available. */ }
  let player: PreviewPlayer | null = null;
  let running = false;
  let position = 0;
  let selectedClip = "A";
  const status = node("p", "Nothing plays until you tap."); status.setAttribute("role", "status");
  const saveStatus = node("p", session.deck.server_results ? "Results save automatically to this local server." : "Server saving is not configured. Download a backup before leaving.");
  saveStatus.setAttribute("role", "status"); saveStatus.className = "listening-save";
  let storage: Storage | null = null;
  try { storage = window.localStorage; } catch { /* Server saving still works without browser storage. */ }
  const autosave = session.deck.server_results ? new ListeningAutosave(session.deck.deck_sha256, storage, message => { saveStatus.textContent = message; separate.hidden = !autosave?.conflict; }) : null;
  const retry = node("button", "Retry save"); retry.addEventListener("click", () => { void autosave?.flush(); });
  const separate = node("button", "Save draft as separate session"); separate.hidden = true; separate.addEventListener("click", () => { void autosave?.separateSession(); });
  const conditions = node("textarea"); conditions.maxLength = 4096; conditions.placeholder = "Device, headphones, Bluetooth, volume or network (optional; avoid personal details).";
  let recovered = false;
  if (autosave) {
    const restored = await autosave.restore();
    if (restored) {
      recovered = session.restore(restored); conditions.value = restored.conditions;
      position = restored.view?.position ?? 0; selectedClip = restored.view?.clip ?? "A";
    }
  }
  function save(): void { autosave?.save(session.snapshot(conditions.value, manifest, navigator.userAgent, { position, clip: selectedClip })); }
  conditions.addEventListener("input", save);
  const settings = node("details"); settings.append(node("summary", "Test conditions & backup"));
  const conditionLabel = node("label", "Test conditions"); conditionLabel.append(conditions);
  const download = node("button", "Download backup");
  download.addEventListener("click", () => {
    try {
      const data = session.export(conditions.value, manifest, navigator.userAgent);
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const anchor = node("a"); anchor.href = url; anchor.download = `simo-listening-${session.deck.deck_sha256.slice(0, 12)}.json`; anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { status.textContent = String(error); }
  });
  settings.append(conditionLabel, download);
  const caseArea = node("section"); const ratingArea = node("section"); const observations = node("section");
  const heading = node("h3"); const line = node("blockquote"); const instruction = node("p");
  const progress = node("p");
  const play = node("button", "Hear A"); const stop = node("button", "Stop"); stop.disabled = true;
  stop.addEventListener("click", () => player?.stop());
  window.addEventListener("pagehide", () => player?.stop());
  const actions = node("div"); actions.className = "listening-actions"; actions.append(play, stop);
  const previous = node("button", "Previous"); const next = node("button", "Next comparison");
  const nav = node("div"); nav.className = "listening-nav"; nav.append(previous, next);
  let clipPicker: HTMLFieldSetElement;
  const lockedInputs: HTMLFieldSetElement[] = [];
  let fresh: HTMLButtonElement | null = null;
  function busy(value: boolean): void {
    running = value;
    for (const action of [play, previous, next, download, ...(fresh ? [fresh] : [])]) action.disabled = value;
    for (const group of [clipPicker, ...lockedInputs]) group.disabled = value;
    stop.disabled = !value;
  }
  function observe(attempt: Attempt): void {
    function answer(key: "heard" | "gaps" | "start", value: string): void {
      if (key === "start") attempt.listener.start = value as Attempt["listener"]["start"];
      else attempt.listener[key] = value as Answer;
      if (attempt.listener.answered && !attempt.listener.answered.includes(key)) attempt.listener.answered.push(key);
      save();
    }
    observations.replaceChildren(node("h3", `Attempt ${attempt.ordinal + 1}: ${attempt.status}`));
    observations.append(
      radios("Heard the full clip?", `attempt-${attempt.ordinal}-heard`, ["yes", "no", "uncertain"], undefined, value => answer("heard", value)),
      radios("Heard any gaps?", `attempt-${attempt.ordinal}-gaps`, ["yes", "no", "uncertain"], undefined, value => answer("gaps", value)),
      radios("How did the start feel?", `attempt-${attempt.ordinal}-start`, ["prompt", "delayed", "uncertain"], attempt.listener.start === "unreported" ? undefined : attempt.listener.start, value => answer("start", value)));
    // Existing observations are shown on resume, but default uncertainty remains unselected.
    for (const key of ["heard", "gaps"] as const) {
      if (attempt.listener[key] !== "uncertain" || attempt.listener.answered?.includes(key)) for (const input of observations.querySelectorAll("input")) if (input.name === `attempt-${attempt.ordinal}-${key}`) input.checked = input.value === attempt.listener[key];
    }
    const label = node("label", "Attempt notes (optional)"); const notes = node("textarea"); notes.maxLength = 4096; notes.value = attempt.listener.notes;
    notes.addEventListener("input", () => { attempt.listener.notes = notes.value; save(); }); label.append(notes); observations.append(label);
  }
  async function run(attempt: Attempt, url: string, request: PlaybackRequest): Promise<void> {
    busy(true); observations.replaceChildren(); save(); void autosave?.flush();
    try {
      player = createPlayer(); // Synchronous inside the explicit tap: preserve mobile audio activation.
      const metrics = await player.play(url, value => {
        attempt.metrics = value; status.textContent = `${attempt.lane} attempt ${attempt.ordinal + 1}: ${value.state}; ${value.underruns} queue underruns (not acoustic timing).`;
      }, attempt.lane === "recorded" ? { name: "complete-clip" } : { name: "mlx-stream-v1", runtimeFingerprint: attempt.benchmark_manifest!.runtime_fingerprint }, request);
      attempt.metrics = metrics; attempt.status = "complete";
    } catch (error) {
      attempt.metrics = player ? { ...player.metrics } : undefined;
      attempt.status = error instanceof DOMException && error.name === "AbortError" ? "stopped" : "failed";
      attempt.error = error instanceof Error ? error.message : String(error);
    } finally {
      player = null; busy(false); observe(attempt); save(); void autosave?.flush();
      status.textContent = `Attempt ${attempt.ordinal + 1} ${attempt.status}${attempt.error ? `: ${attempt.error}` : ""}.`;
    }
  }
  play.addEventListener("click", () => {
    if (running) return;
    const item = session.deck.cases[position]; const clip = item.clips.find(value => value.label === selectedClip)!;
    void run(session.begin("recorded", { clip_id: clip.id, case_id: item.id }), `/api/listening/clips/${clip.id}`, recordedRequest(session.deck, clip));
  });
  function updateProgress(): void {
    const answered = [...session.ratings.values()].filter(rating => (rating.answered?.length ?? 6) === 6).length;
    progress.textContent = `${answered} of 72 clips fully rated · skipping is fine`;
  }
  function renderRating(): void {
    const item = session.deck.cases[position]; const clip = item.clips.find(value => value.label === selectedClip)!;
    play.textContent = `Hear ${clip.label}`;
    const prior = session.ratings.get(clip.id);
    const rating: Rating = prior ?? { clip_id: clip.id, pcm_sha256: clip.pcm_sha256, heard_fully: "uncertain", intelligible: "uncertain", complete_words: "uncertain", instruction: "uncertain", natural: "uncertain", gap_free: "uncertain", notes: "", answered: [] };
    ratingArea.replaceChildren(node("h3", `Rate clip ${clip.label}`));
    for (const [field, label] of Object.entries(fields)) {
      const key = field as keyof typeof fields;
      ratingArea.append(radios(label, `clip-${clip.id}-${key}`, ["yes", "no", "uncertain"], prior && (!rating.answered || rating.answered.includes(key)) ? rating[key] : undefined, value => {
        rating[key] = value as Answer;
        if (rating.answered && !rating.answered.includes(key)) rating.answered.push(key);
        session.ratings.set(clip.id, rating); updateProgress(); save();
      }));
    }
    const notesGroup = node("details"); notesGroup.append(node("summary", "Clip notes (optional)"));
    const notesLabel = node("label", "Missing, repeated or cut-off words; artifacts or uncertainty");
    const notes = node("textarea"); notes.maxLength = 4096; notes.value = rating.notes;
    notes.addEventListener("input", () => { rating.notes = notes.value; session.ratings.set(clip.id, rating); save(); });
    notesLabel.append(notes); notesGroup.append(notesLabel); ratingArea.append(notesGroup);
    ratingArea.append(radios("Preferred version (optional)", `preference-${item.id}`, ["A", "B", "C", "D", "tie", "uncertain"], session.preferences.get(item.id), value => { session.preferences.set(item.id, value); save(); }));
    updateProgress();
  }
  clipPicker = radios("Choose a clip", "listening-clip", ["A", "B", "C", "D"], selectedClip, value => { if (running) return; selectedClip = value; renderRating(); save(); });
  clipPicker.className = "listening-clip-picker";
  caseArea.append(heading, line, instruction, clipPicker, ratingArea, progress, nav);
  function renderCase(): void {
    const item = session.deck.cases[position];
    heading.textContent = `Comparison ${position + 1} of ${session.deck.cases.length}`; line.textContent = item.text; instruction.textContent = item.instruction;
    for (const input of clipPicker.querySelectorAll("input")) input.checked = input.value === selectedClip;
    renderRating();
  }
  previous.addEventListener("click", () => { if (!running) { position = (position + 17) % 18; selectedClip = "A"; renderCase(); save(); } });
  next.addEventListener("click", () => { if (!running) { position = (position + 1) % 18; selectedClip = "A"; renderCase(); save(); } });
  const trials = node("details"); trials.append(node("summary", "Try live generation"));
  if (manifest) {
    const selected = { suite: "short", index: 0, seed: 17, instruction_id: "default" };
    const description = node("p");
    const refresh = (): void => { description.textContent = `${manifest!.suites[selected.suite][selected.index]} Instruction: ${manifest!.instructions[selected.instruction_id]}`; };
    const text = radios("Test line", "fresh-line", Object.entries(manifest.suites).flatMap(([suite, texts]) => texts.map((_, index) => `${suite}:${index + 1}`)), "short:1", value => { const [suite, index] = value.split(":"); selected.suite = suite; selected.index = Number(index) - 1; refresh(); });
    const delivery = radios("Instruction", "fresh-instruction", Object.keys(manifest.instructions), selected.instruction_id, value => { selected.instruction_id = value; refresh(); });
    const seed = radios("Seed", "fresh-seed", ["17", "29", "42"], "17", value => { selected.seed = Number(value); });
    lockedInputs.push(text, delivery, seed);
    fresh = node("button", "Hear a fresh trial"); fresh.addEventListener("click", () => {
      if (running) return;
      const attempt = session.begin("fresh", { trial: { ...selected }, benchmark_manifest: clone(manifest!) });
      try { void run(attempt, `/api/benchmarks/${selected.suite}/${selected.index}/stream`, session.freshRequest(attempt.benchmark_manifest!, attempt)); }
      catch (error) { attempt.status = "failed"; attempt.error = String(error); status.textContent = String(error); observe(attempt); save(); }
    });
    refresh(); trials.append(node("p", "Uncached live candidate, separate from the blinded recordings. This does not run or accept the release suite."), text, delivery, seed, description, fresh);
  } else trials.append(node("p", "Live trials are currently unavailable. Recorded comparisons still work."));
  root.append(node("h2", "Listen & compare"), node("p", "Tap a clip, listen, then rate it. A–D hide the recipes. No microphone is used."),
    saveStatus, ...(autosave ? [retry, separate] : []), caseArea, actions, status, observations, trials, settings,
    node("p", session.deck.server_results
      ? "Ratings, notes and playback diagnostics save to this local server, not conversational memory. Automatic resume requires browser storage. Fast remains unaccepted; software timing is not physical sound onset."
      : "Server saving is disabled. Download a backup before leaving. Fast remains unaccepted; software timing is not physical sound onset."));
  renderCase();
  if (session.attempts.length) observe(session.attempts[session.attempts.length - 1]);
  if (recovered) { status.textContent = "The interrupted trial was retained as stopped. Tap Hear to try again."; save(); }
  return true;
}
