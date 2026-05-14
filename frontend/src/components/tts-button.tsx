"use client";

import { useCallback, useState } from "react";

interface TtsButtonProps {
  text: string;
  lang?: string;
  label?: string;
}

export function TtsButton({
  text,
  lang = "ja-JP",
  label = "▶",
}: TtsButtonProps) {
  const [speaking, setSpeaking] = useState(false);

  const speak = useCallback(() => {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    utt.lang = lang;
    utt.onstart = () => setSpeaking(true);
    utt.onend = () => setSpeaking(false);
    utt.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utt);
  }, [text, lang]);

  return (
    <button
      aria-label={`Speak: ${text}`}
      className={`btn btn-ghost btn-sm tts-btn${speaking ? " tts-btn-speaking" : ""}`}
      onClick={speak}
      type="button"
    >
      {label}
    </button>
  );
}
