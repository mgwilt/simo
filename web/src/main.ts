import { Room, RoomEvent, Track } from "livekit-client";
import "./style.css";

interface SessionResponse {
  aliasName: string;
  serverUrl: string;
  participantToken: string;
}

interface VoicePreview {
  id: string;
  label: string;
  description: string;
  instruction: string;
  cached: boolean;
}

interface VoicePreviewResponse {
  text: string;
  render_note: string;
  presets: VoicePreview[];
}

function requireElement<T extends Element>(selector: string): T {
  const element = document.querySelector<T>(selector);
  if (!element) {
    throw new Error(`Simo voice UI is missing ${selector}`);
  }
  return element;
}

const button = requireElement<HTMLButtonElement>("#toggle");
const status = requireElement<HTMLElement>("#status");
const alias = requireElement<HTMLElement>("#alias");
const orb = requireElement<HTMLElement>("#orb");
const audio = requireElement<HTMLAudioElement>("#remote-audio");
const previewCopy = requireElement<HTMLElement>("#preview-copy");
const previewGrid = requireElement<HTMLElement>("#preview-grid");
const previewStatus = requireElement<HTMLElement>("#preview-status");
const previewAudio = requireElement<HTMLAudioElement>("#preview-audio");

let room: Room | null = null;
let previewObjectUrl: string | null = null;

function setState(label: string, state: string): void {
  status.textContent = label;
  orb.dataset.state = state;
}

async function disconnect(): Promise<void> {
  if (room) {
    await room.disconnect(true);
    room = null;
  }
  button.textContent = "Start conversation";
  setState("Ready to connect", "idle");
}

async function connect(): Promise<void> {
  button.disabled = true;
  setState("Preparing the local room…", "loading");
  try {
    const response = await fetch("/api/session", { method: "POST" });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const session = (await response.json()) as SessionResponse;
    alias.textContent = session.aliasName;
    const nextRoom = new Room({ audioCaptureDefaults: { echoCancellation: true } });
    nextRoom.on(RoomEvent.Reconnecting, () => setState("Reconnecting…", "loading"));
    nextRoom.on(RoomEvent.Reconnected, () => setState("Listening", "listening"));
    nextRoom.on(RoomEvent.Disconnected, () => void disconnect());
    nextRoom.on(RoomEvent.AudioPlaybackStatusChanged, () => {
      if (!nextRoom.canPlaybackAudio) {
        setState("Tap to resume audio", "attention");
      }
    });
    nextRoom.on(RoomEvent.TrackSubscribed, (track, _publication, participant) => {
      if (track.kind !== Track.Kind.Audio || participant.identity !== "simo-alias") {
        track.stop();
        return;
      }
      track.attach(audio);
    });
    nextRoom.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
      const agentSpeaking = speakers.some((speaker) => speaker.identity === "simo-alias");
      setState(agentSpeaking ? "Speaking" : "Listening", agentSpeaking ? "speaking" : "listening");
    });
    room = nextRoom;
    await nextRoom.connect(session.serverUrl, session.participantToken);
    await nextRoom.startAudio();
    await nextRoom.localParticipant.setMicrophoneEnabled(true);
    button.textContent = "End conversation";
    setState("Listening", "listening");
  } catch (error) {
    await disconnect();
    setState(error instanceof Error ? error.message : "Unable to connect", "error");
  } finally {
    button.disabled = false;
  }
}

button.addEventListener("click", () => {
  if (room) {
    void disconnect();
  } else {
    void connect();
  }
});

function setPreviewButtonsDisabled(disabled: boolean): void {
  for (const selected of previewGrid.querySelectorAll<HTMLButtonElement>("button")) {
    selected.disabled = disabled;
  }
  button.disabled = disabled;
}

async function playPreview(preset: VoicePreview): Promise<void> {
  setPreviewButtonsDisabled(true);
  previewStatus.textContent = preset.cached
    ? `Loading ${preset.label}…`
    : `Rendering ${preset.label} locally… this can take about one minute.`;
  try {
    const response = await fetch(`/api/previews/${encodeURIComponent(preset.id)}`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const blob = await response.blob();
    if (previewObjectUrl) {
      URL.revokeObjectURL(previewObjectUrl);
    }
    previewObjectUrl = URL.createObjectURL(blob);
    previewAudio.src = previewObjectUrl;
    previewAudio.hidden = false;
    previewStatus.textContent = `${preset.label} is ready.`;
    try {
      await previewAudio.play();
    } catch {
      previewStatus.textContent = `${preset.label} is ready — tap play below.`;
    }
    preset.cached = true;
  } catch (error) {
    previewStatus.textContent = error instanceof Error ? error.message : "Unable to render preview";
  } finally {
    setPreviewButtonsDisabled(false);
  }
}

async function loadVoicePalette(): Promise<void> {
  try {
    const response = await fetch("/api/previews");
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const palette = (await response.json()) as VoicePreviewResponse;
    previewCopy.textContent = `Same line for every voice: “${palette.text}” ${palette.render_note}`;
    for (const preset of palette.presets) {
      const card = document.createElement("article");
      card.className = "preview-card";
      const heading = document.createElement("h3");
      heading.textContent = preset.label;
      const description = document.createElement("p");
      description.className = "preview-description";
      description.textContent = preset.description;
      const instruction = document.createElement("p");
      instruction.className = "preview-instruction";
      instruction.textContent = preset.instruction;
      const previewButton = document.createElement("button");
      previewButton.type = "button";
      previewButton.textContent = preset.cached ? "Play cached sample" : "Render & hear";
      previewButton.addEventListener("click", () => void playPreview(preset));
      card.append(heading, description, instruction, previewButton);
      previewGrid.append(card);
    }
  } catch (error) {
    previewCopy.textContent = error instanceof Error ? error.message : "Voice palette unavailable";
  }
}

void loadVoicePalette();

window.addEventListener("pagehide", () => {
  void disconnect();
  if (previewObjectUrl) {
    URL.revokeObjectURL(previewObjectUrl);
  }
});
