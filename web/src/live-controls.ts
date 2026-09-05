export interface LiveSettings {
  prompt: string;
  voice_instruction: string;
  max_tokens: number;
  revision: number;
  voice_editable: boolean;
  seed: number;
  cfg_scale: number;
  scope: string;
}

export function settingsPayload(settings: LiveSettings): Record<string, string | number> {
  return { prompt: settings.prompt, voice_instruction: settings.voice_instruction,
    max_tokens: settings.max_tokens, revision: settings.revision };
}

export async function requestSettings(settings?: LiveSettings): Promise<LiveSettings> {
  const response = await fetch("/api/controls", {
    method: settings ? "PUT" : "GET",
    cache: "no-store", credentials: "same-origin", signal: AbortSignal.timeout(8000),
    ...(settings ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(settingsPayload(settings)) } : {}),
  });
  if (!response.ok) {
    if (response.status === 409) throw new Error("Another tab changed the settings. Reload settings before applying your edits.");
    throw new Error(`Settings request failed (${response.status}). Your edits remain here; reload settings to check what is active.`);
  }
  const value = await response.json() as LiveSettings;
  if (!value || typeof value.prompt !== "string" || typeof value.voice_instruction !== "string"
    || !Number.isInteger(value.revision) || !Number.isInteger(value.max_tokens)
    || typeof value.voice_editable !== "boolean") throw new Error("Invalid settings response");
  return value;
}

export function mountLiveControls(form: HTMLFormElement): void {
  const prompt = form.querySelector<HTMLTextAreaElement>("#conversation-prompt")!;
  const voice = form.querySelector<HTMLTextAreaElement>("#voice-prompt")!;
  const budget = form.querySelector<HTMLElement>("#response-budget")!;
  const status = form.querySelector<HTMLElement>("#controls-status")!;
  const metadata = form.querySelector<HTMLElement>("#voice-settings")!;
  const apply = form.querySelector<HTMLButtonElement>("#apply-controls")!;
  const reload = form.querySelector<HTMLButtonElement>("#reload-controls")!;
  const fields = form.querySelector<HTMLFieldSetElement>("#controls-fields")!;
  let current: LiveSettings | null = null;
  let busy = false;

  const show = (settings: LiveSettings): void => {
    current = settings;
    prompt.value = settings.prompt; voice.value = settings.voice_instruction;
    voice.disabled = !settings.voice_editable;
    const choices = new Map([[128, "Brief"], [512, "Flexible"], [1024, "Long"], [2048, "Extended"]]);
    if (!choices.has(settings.max_tokens)) choices.set(settings.max_tokens, "Configured");
    budget.replaceChildren();
    for (const [value, label] of choices) {
      const choice = document.createElement("label");
      const radio = document.createElement("input");
      radio.type = "radio"; radio.name = "max_tokens"; radio.value = String(value);
      radio.checked = value === settings.max_tokens;
      choice.append(radio, document.createTextNode(`${label} · ${value} tokens`));
      budget.append(choice);
    }
    metadata.textContent = settings.voice_editable
      ? `Breeze voice design · fixed seed ${settings.seed} · CFG ${settings.cfg_scale}. This describes a voice, not a locked speaker.`
      : "This backend does not support editable voice instructions.";
  };

  const run = async (save: boolean): Promise<void> => {
    if (busy || (save && !current)) return;
    const selected = budget.querySelector<HTMLInputElement>('input:checked');
    const next = save && current ? { ...current, prompt: prompt.value,
      voice_instruction: voice.value, max_tokens: Number(selected?.value) } : undefined;
    busy = true; fields.disabled = true; reload.disabled = true; apply.disabled = true;
    status.textContent = save ? "Applying…" : "Loading active settings…";
    try {
      const settings = await requestSettings(next);
      show(settings);
      status.textContent = save
        ? `Applied revision ${settings.revision}. The next response and next speech generation use these settings; audio already underway is unchanged.`
        : `Active revision ${settings.revision}. ${settings.scope}.`;
    } catch (error) {
      status.textContent = error instanceof Error ? error.message : "Unable to update settings";
    } finally {
      busy = false; fields.disabled = current === null; reload.disabled = false; apply.disabled = current === null;
    }
  };
  form.addEventListener("submit", event => { event.preventDefault(); void run(true); });
  form.addEventListener("input", () => { if (!busy) status.textContent = "Unapplied edits — tap Apply now."; });
  reload.addEventListener("click", () => { void run(false); });
  void run(false);
}
