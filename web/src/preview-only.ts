import { PreviewPlayer, playbackPolicy, type PlaybackPolicy } from "./preview-player";
import "./preview-only.css";
import { mountListening } from "./listening-review";

interface Preset { id: string; label: string; description: string; instruction: string; cached: boolean }
interface Listing { text: string; experimental_recipe: string; playback_policy: string; runtime_fingerprint: string; presets: Preset[] }

function element<T extends HTMLElement>(selector: string): T {
  const found = document.querySelector<T>(selector);
  if (!found) throw new Error(`Missing preview element ${selector}`);
  return found;
}
const grid = element("#preview-grid");
const status = element("#preview-status");
const stop = element<HTMLButtonElement>("#preview-stop");
let current: PreviewPlayer | null = null;
let policy: PlaybackPolicy = { name: "complete-clip" };
stop.addEventListener("click", () => current?.stop());
window.addEventListener("pagehide", () => current?.stop());

async function play(preset: Preset): Promise<void> {
  if (current) return;
  const buttons = grid.querySelectorAll<HTMLButtonElement>("button");
  buttons.forEach(button => { button.disabled = true; });
  stop.hidden = false;
  status.textContent = `Buffering ${preset.label} for smooth playback…`;
  try {
    const player = new PreviewPlayer(); // Resume AudioContext inside the tap handler.
    current = player;
    await player.play(`/api/previews/${encodeURIComponent(preset.id)}/stream`, metrics => {
      status.textContent = metrics.state === "rebuffering"
        ? `Rebuffering ${preset.label}… ${(metrics.bufferedFrames / 24000).toFixed(1)} seconds queued`
        : metrics.firstPlaybackMs === null
        ? `Buffering ${preset.label}… ${(metrics.receivedFrames / 24000).toFixed(1)} seconds received`
        : `Playing ${preset.label} · ${metrics.underruns} reported underruns`;
    }, policy);
    status.textContent = `${preset.label} finished. How did the voice and delivery sound?`;
  } catch (error) {
    status.textContent = error instanceof DOMException && error.name === "AbortError"
      ? "Stopped. Ready to try another voice."
      : error instanceof Error ? error.message : "Preview failed";
  } finally {
    current = null;
    stop.hidden = true;
    buttons.forEach(button => { button.disabled = false; });
  }
}

async function load(): Promise<void> {
  const response = await fetch("/api/previews", { cache: "no-store" });
  if (!response.ok) throw new Error(await response.text());
  const listing = await response.json() as Listing;
  if (listing.experimental_recipe !== "mlx-int8-v1") {
    throw new Error("Unexpected preview runtime or playback policy");
  }
  policy = playbackPolicy(listing.playback_policy, listing.runtime_fingerprint);
  element("#playback-policy").textContent = policy.name === "mlx-stream-v1"
    ? "Experimental 8-bit MLX · not accepted Fast. Playback starts with a 640ms reserve and a bounded two-second queue. A connection failure can interrupt audio already started."
    : "Experimental 8-bit MLX · not accepted Fast. The complete clip is buffered before playback.";
  element("#preview-copy").textContent = listing.text;
  for (const preset of listing.presets) {
    const card = document.createElement("article");
    const title = document.createElement("h2"); title.textContent = preset.label;
    const detail = document.createElement("p"); detail.textContent = preset.description;
    const instruction = document.createElement("p"); instruction.className = "instruction"; instruction.textContent = preset.instruction;
    const button = document.createElement("button"); button.textContent = "Hear this voice";
    button.addEventListener("click", () => { void play(preset); });
    card.append(title, detail, instruction, button); grid.append(card);
  }
  status.textContent = "Choose a voice. No microphone needed.";
}
void load().catch(error => { status.textContent = error instanceof Error ? error.message : "Unable to load previews"; });
void mountListening(element("#listening-review"), () => new PreviewPlayer()).then(enabled => {
  if (!enabled) return;
  current?.stop();
  for (const selector of ["#preview-grid", "#preview-copy", ".playback"]) element(selector).hidden = true;
  element("h1").textContent = "Compare the voices. Test the stream.";
  element(".intro").textContent = "Blinded saved clips and separate fresh trials. Tap to listen; no microphone needed.";
}).catch(error => {
  element("#listening-review").textContent = `Listening interface unavailable: ${String(error)}`;
});
