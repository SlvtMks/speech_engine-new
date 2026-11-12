"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type AgentReply = {
  text: string;
  next_step: string;
  intent: string;
  status: string;
  handoff: boolean;
  finish: boolean;
};

type CallMessage = {
  id: string;
  role: "agent" | "customer";
  text: string;
  intent?: string | null;
  step?: string | null;
  audio_path?: string | null;
};

type CallState = {
  id: string;
  current_step: string;
  status: string;
  direction: string;
  external_call_id?: string | null;
  messages: CallMessage[];
};

type CallResponse = {
  call: CallState;
  reply: AgentReply;
  audio_path?: string | null;
  telephony?: {
    provider: string;
    external_call_id: string;
    status: string;
  };
};

type VoiceStatus = {
  configured_provider: string;
  active_provider: string;
  premium_available: boolean;
  xtts_reference_present: boolean;
  xtts_reference_wav: string;
  xtts_model: string;
  xtts_language: string;
  fallback_provider: string;
};

const quickReplies = [
  "Да, удобно, расскажите",
  "Нет, мне не интересно",
  "Сколько это стоит?",
  "Перезвоните завтра",
  "Соедините с менеджером",
];

const defaultVoiceInstructions =
  "Говорить естественно, спокойно и дружелюбно, как оператор по телефону. Темп средний, без дикторской подачи. Делать короткие паузы перед вопросами.";

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export default function HomePage() {
  const backendBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

  const [phone, setPhone] = useState("+79990000000");
  const [name, setName] = useState("Тестовый клиент");
  const [direction, setDirection] = useState<"outbound" | "inbound">("outbound");
  const [synthesize, setSynthesize] = useState(false);
  const [voiceInstructions, setVoiceInstructions] = useState(defaultVoiceInstructions);
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus | null>(null);
  const [customerText, setCustomerText] = useState("");
  const [call, setCall] = useState<CallState | null>(null);
  const [lastReply, setLastReply] = useState<AgentReply | null>(null);
  const [audioPath, setAudioPath] = useState<string | null>(null);
  const [telephonyStatus, setTelephonyStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadVoiceStatus() {
      try {
        const res = await fetch(`${backendBaseUrl}/voice/status`);
        if (!res.ok) return;
        const data = (await res.json()) as VoiceStatus;
        if (!cancelled) setVoiceStatus(data);
      } catch {
        if (!cancelled) setVoiceStatus(null);
      }
    }

    loadVoiceStatus();
    return () => {
      cancelled = true;
    };
  }, [backendBaseUrl]);

  const audioUrl = useMemo(() => {
    if (!audioPath) return null;
    const filename = audioPath.split(/[\\/]/).pop();
    return filename ? `${backendBaseUrl}/audio/${encodeURIComponent(filename)}` : null;
  }, [audioPath, backendBaseUrl]);

  const voiceLabel = voiceStatus
    ? voiceStatus.active_provider === "xtts"
      ? `XTTS v2, референс: ${voiceStatus.xtts_reference_wav || "не найден"}`
      : `Fallback: ${voiceStatus.fallback_provider}`
    : "Статус голоса загрузится после запуска backend";

  async function startCall(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    setAudioPath(null);

    try {
      const res = await fetch(`${backendBaseUrl}/calls/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone,
          name,
          direction,
          synthesize,
          speaker: "aidar",
          voice_instructions: voiceInstructions,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Start failed: ${res.status}`);
      }

      const data = (await res.json()) as CallResponse;
      setCall(data.call);
      setLastReply(data.reply);
      setAudioPath(data.audio_path ?? null);
      setTelephonyStatus(
        data.telephony
          ? `${data.telephony.provider}: ${data.telephony.status} (${data.telephony.external_call_id})`
          : null,
      );
      setCustomerText("");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Не удалось начать демо-звонок."));
    } finally {
      setLoading(false);
    }
  }

  async function sendCustomerReply(e?: FormEvent, preset?: string) {
    e?.preventDefault();
    if (!call) return;

    const text = (preset ?? customerText).trim();
    if (!text) {
      setError("Введите реплику клиента.");
      return;
    }

    setError(null);
    setLoading(true);
    setAudioPath(null);

    try {
      const res = await fetch(`${backendBaseUrl}/calls/${call.id}/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          synthesize,
          speaker: "aidar",
          voice_instructions: voiceInstructions,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Respond failed: ${res.status}`);
      }

      const data = (await res.json()) as CallResponse;
      setCall(data.call);
      setLastReply(data.reply);
      setAudioPath(data.audio_path ?? null);
      setCustomerText("");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Не удалось получить ответ агента."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="grid gap-6 border-b border-slate-200 pb-6 md:grid-cols-[1.2fr_0.8fr] dark:border-slate-800">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700 dark:text-emerald-300">
            MVP голосового агента
          </p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl dark:text-slate-50">
            Сценарный ИИ-робот для обработки звонков
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600 dark:text-slate-300">
            Демо показывает честную основу под задачу клиента: лид, сценарий холодного звонка,
            реплики клиента, ответ агента, статус разговора, история и mock-телефония для будущего
            подключения SIP или АТС.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <div className="text-2xl font-semibold text-slate-950 dark:text-slate-50">STT/TTS</div>
            <div className="mt-1 text-slate-500 dark:text-slate-400">Распознавание и голос</div>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <div className="text-2xl font-semibold text-slate-950 dark:text-slate-50">JSON</div>
            <div className="mt-1 text-slate-500 dark:text-slate-400">Обучение сценариями</div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[380px_1fr]">
        <aside className="space-y-4">
          <form onSubmit={startCall} className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <h2 className="text-lg font-semibold">Новый демо-звонок</h2>
            <div className="mt-4 space-y-3">
              <label className="block text-sm">
                <span className="text-slate-600 dark:text-slate-300">Телефон</span>
                <input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-emerald-500 dark:border-slate-700 dark:bg-slate-950"
                />
              </label>
              <label className="block text-sm">
                <span className="text-slate-600 dark:text-slate-300">Имя</span>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-emerald-500 dark:border-slate-700 dark:bg-slate-950"
                />
              </label>
              <label className="block text-sm">
                <span className="text-slate-600 dark:text-slate-300">Направление</span>
                <select
                  value={direction}
                  onChange={(e) => setDirection(e.target.value as "outbound" | "inbound")}
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-emerald-500 dark:border-slate-700 dark:bg-slate-950"
                >
                  <option value="outbound">Исходящий</option>
                  <option value="inbound">Входящий</option>
                </select>
              </label>
              <label className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={synthesize}
                  onChange={(e) => setSynthesize(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-slate-300"
                />
                <span>
                  Озвучивать ответы через TTS
                  <span className="mt-1 block text-xs text-slate-500 dark:text-slate-400">{voiceLabel}</span>
                </span>
              </label>
              <label className="block text-sm">
                <span className="text-slate-600 dark:text-slate-300">Стиль голоса</span>
                <textarea
                  value={voiceInstructions}
                  onChange={(e) => setVoiceInstructions(e.target.value)}
                  rows={4}
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-emerald-500 dark:border-slate-700 dark:bg-slate-950"
                />
                <span className="mt-1 block text-xs text-slate-500 dark:text-slate-400">
                  Для XTTS стиль в основном задают референс-голос и текст сценария; поле оставлено для совместимости сценария.
                </span>
              </label>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="mt-4 w-full rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-slate-100 dark:text-slate-950"
            >
              {loading ? "Запуск..." : "Начать звонок"}
            </button>
          </form>

          <div className="rounded-lg border border-slate-200 bg-white p-5 text-sm dark:border-slate-800 dark:bg-slate-900">
            <h3 className="font-semibold">Статус</h3>
            <dl className="mt-3 space-y-2">
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">Шаг</dt>
                <dd className="font-medium">{call?.current_step ?? "-"}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">Статус</dt>
                <dd className="font-medium">{call?.status ?? "-"}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">Интент</dt>
                <dd className="font-medium">{lastReply?.intent ?? "-"}</dd>
              </div>
            </dl>
            {telephonyStatus && (
              <p className="mt-3 rounded-md bg-slate-100 p-2 text-xs text-slate-600 dark:bg-slate-950 dark:text-slate-300">
                {telephonyStatus}
              </p>
            )}
          </div>
        </aside>

        <section className="space-y-4">
          {error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-200">
              {error}
            </div>
          )}

          <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold">Диалог</h2>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600 dark:bg-slate-950 dark:text-slate-300">
                {call ? `call ${call.id.slice(0, 8)}` : "звонок не начат"}
              </span>
            </div>

            <div className="mt-4 min-h-80 space-y-3 rounded-md border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-950">
              {call?.messages.length ? (
                call.messages.map((message) => (
                  <div
                    key={message.id}
                    className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                      message.role === "agent"
                        ? "bg-white text-slate-900 shadow-sm dark:bg-slate-900 dark:text-slate-50"
                        : "ml-auto bg-emerald-600 text-white"
                    }`}
                  >
                    <div className="mb-1 text-[11px] uppercase tracking-wide opacity-70">
                      {message.role === "agent" ? "Агент" : "Клиент"}
                      {message.intent ? ` / ${message.intent}` : ""}
                    </div>
                    <div>{message.text}</div>
                  </div>
                ))
              ) : (
                <div className="flex h-72 items-center justify-center text-sm text-slate-500">
                  Начните демо-звонок, чтобы увидеть сценарий.
                </div>
              )}
            </div>

            {audioUrl && (
              <div className="mt-4 rounded-md border border-slate-200 p-3 dark:border-slate-800">
                <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                  Последний голосовой ответ
                </div>
                <audio controls src={audioUrl} className="w-full" />
              </div>
            )}
          </div>

          <form onSubmit={(e) => sendCustomerReply(e)} className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <h3 className="font-semibold">Реплика клиента</h3>
            <textarea
              value={customerText}
              onChange={(e) => setCustomerText(e.target.value)}
              disabled={!call || Boolean(lastReply?.finish || lastReply?.handoff)}
              rows={3}
              className="mt-3 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-emerald-500 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950"
              placeholder="Например: Да, удобно, расскажите"
            />
            <div className="mt-3 flex flex-wrap gap-2">
              {quickReplies.map((reply) => (
                <button
                  key={reply}
                  type="button"
                  disabled={!call || loading || Boolean(lastReply?.finish || lastReply?.handoff)}
                  onClick={() => sendCustomerReply(undefined, reply)}
                  className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-700 transition hover:border-emerald-500 hover:text-emerald-700 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
                >
                  {reply}
                </button>
              ))}
            </div>
            <button
              type="submit"
              disabled={!call || loading || Boolean(lastReply?.finish || lastReply?.handoff)}
              className="mt-4 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Обработка..." : "Отправить реплику"}
            </button>
          </form>
        </section>
      </section>
    </div>
  );
}
