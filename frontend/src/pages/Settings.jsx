import React, { useState, useEffect } from "react";
import axios from "axios";
import { Save, Eye, EyeOff, CheckCircle, AlertCircle, ExternalLink } from "lucide-react";
import { API } from "../lib/api";

function SettingSection({ title, description, children }) {
  return (
    <div className="border border-zinc-800 bg-[#111111] p-6">
      <h2 className="text-sm font-[Chivo] font-bold text-white uppercase tracking-widest mb-1">{title}</h2>
      <p className="text-xs text-zinc-500 mb-4">{description}</p>
      {children}
    </div>
  );
}

export default function Settings() {
  const [settings, setSettings] = useState({ github_token: "", telegram_bot_token: "", telegram_chat_id: "" });
  const [showGH, setShowGH] = useState(false);
  const [showTG, setShowTG] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [settingsRes, healthRes] = await Promise.all([
          axios.get(`${API}/settings`),
          axios.get(`${API}/health`),
        ]);
        const data = settingsRes.data;
        setSettings({
          github_token: data.github_token || "",
          telegram_bot_token: data.telegram_bot_token || "",
          telegram_chat_id: data.telegram_chat_id || "",
        });
        setHealth(healthRes.data);
      } catch (e) {
        console.error(e);
      }
    };
    load();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      await axios.post(`${API}/settings`, settings);
      setSaved(true);
      const healthRes = await axios.get(`${API}/health`);
      setHealth(healthRes.data);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-[Chivo] font-bold text-white">Settings</h1>
        <p className="text-zinc-500 text-sm mt-1">Configure GitHub and Telegram integrations</p>
      </div>

      {/* Service status */}
      {health && (
        <div className="flex gap-4 mb-6">
          <div className={`flex items-center gap-2 text-xs font-mono ${health.github ? "text-emerald-400" : "text-zinc-500"}`}>
            {health.github ? <CheckCircle size={12} /> : <AlertCircle size={12} />}
            GitHub {health.github ? "connected" : "not configured"}
          </div>
          <div className={`flex items-center gap-2 text-xs font-mono ${health.telegram ? "text-emerald-400" : "text-zinc-500"}`}>
            {health.telegram ? <CheckCircle size={12} /> : <AlertCircle size={12} />}
            Telegram {health.telegram ? "connected" : "not configured"}
          </div>
        </div>
      )}

      <div className="space-y-4">
        {/* GitHub Settings */}
        <SettingSection
          title="GitHub Integration"
            description="Required for creating Pull Requests. Your PAT must have Contents and Pull Requests read/write permissions."
        >
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-mono text-zinc-400 mb-1">
                Personal Access Token (PAT)
              </label>
              <div className="flex gap-2">
                <input
                  type={showGH ? "text" : "password"}
                  value={settings.github_token}
                  onChange={(e) => setSettings((s) => ({ ...s, github_token: e.target.value }))}
                  placeholder="ghp_xxxxxxxxxxxxxxxxxxxx  OR  github_pat_11..."
                  className="flex-1 bg-[#0A0A0A] border border-zinc-800 text-white placeholder:text-zinc-600 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-emerald-400"
                  data-testid="github-token-input"
                />
                <button
                  onClick={() => setShowGH(!showGH)}
                  className="p-2 border border-zinc-800 text-zinc-500 hover:text-white transition-colors"
                >
                  {showGH ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            {/* PAT Instructions */}
            <div className="bg-[#0A0A0A] border border-zinc-800 p-3 space-y-2">
              <p className="text-xs font-mono text-zinc-400 font-bold">Option A — Classic PAT (easiest):</p>
              <ol className="text-xs font-mono text-zinc-500 space-y-0.5 list-decimal list-inside">
                <li>Go to <span className="text-white">github.com/settings/tokens</span></li>
                <li>Click <span className="text-emerald-400">Generate new token (classic)</span></li>
                <li>Enable scope: <span className="text-emerald-400">repo</span> (full control)</li>
                <li>Copy token starting with <span className="text-white">ghp_</span></li>
              </ol>
              <p className="text-xs font-mono text-zinc-400 font-bold mt-2">Option B — Fine-grained PAT:</p>
              <ol className="text-xs font-mono text-zinc-500 space-y-0.5 list-decimal list-inside">
                <li>Go to <span className="text-white">github.com/settings/tokens</span> → Fine-grained</li>
                <li>Select repository: <span className="text-emerald-400">yashdodwani/AuditRx</span> (or All)</li>
                <li>Permissions: <span className="text-emerald-400">Contents → Read &amp; write</span></li>
                <li>Permissions: <span className="text-emerald-400">Pull requests → Read &amp; write</span></li>
              </ol>
            </div>

            <a
              href="https://github.com/settings/tokens/new?scopes=repo&description=RepoDoctor"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-mono"
              data-testid="github-token-link"
            >
              Create Classic GitHub PAT (recommended) <ExternalLink size={10} />
            </a>
          </div>
        </SettingSection>

        {/* Telegram Settings */}
        <SettingSection
          title="Telegram Bot"
          description="Optional. Create a bot via @BotFather and paste the token here to receive live updates and trigger analyses from Telegram."
        >
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-mono text-zinc-400 mb-1">Bot Token</label>
              <div className="flex gap-2">
                <input
                  type={showTG ? "text" : "password"}
                  value={settings.telegram_bot_token}
                  onChange={(e) => setSettings((s) => ({ ...s, telegram_bot_token: e.target.value }))}
                  placeholder="1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ"
                  className="flex-1 bg-[#0A0A0A] border border-zinc-800 text-white placeholder:text-zinc-600 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-emerald-400"
                  data-testid="telegram-token-input"
                />
                <button
                  onClick={() => setShowTG(!showTG)}
                  className="p-2 border border-zinc-800 text-zinc-500 hover:text-white transition-colors"
                >
                  {showTG ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>
            <div>
              <label className="block text-xs font-mono text-zinc-400 mb-1">
                Default Chat ID <span className="text-zinc-600">(optional)</span>
              </label>
              <input
                type="text"
                value={settings.telegram_chat_id}
                onChange={(e) => setSettings((s) => ({ ...s, telegram_chat_id: e.target.value }))}
                placeholder="Your Telegram Chat ID"
                className="w-full bg-[#0A0A0A] border border-zinc-800 text-white placeholder:text-zinc-600 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-emerald-400"
                data-testid="telegram-chat-id-input"
              />
            </div>
            <div className="bg-[#0A0A0A] border border-zinc-800 p-3">
              <p className="text-xs font-mono text-zinc-400 mb-1">How to get your Bot Token:</p>
              <ol className="text-xs font-mono text-zinc-500 space-y-0.5 list-decimal list-inside">
                <li>Open Telegram and search for <span className="text-white">@BotFather</span></li>
                <li>Send <span className="text-emerald-400">/newbot</span></li>
                <li>Follow the prompts and copy the token</li>
              </ol>
              <p className="text-xs font-mono text-zinc-400 mt-2 mb-1">Telegram Commands:</p>
              <code className="text-xs text-emerald-400">/analyze https://github.com/user/repo</code>
            </div>
          </div>
        </SettingSection>

        {/* Save */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-6 py-2.5 bg-white text-black text-sm font-bold hover:bg-zinc-200 transition-colors disabled:opacity-50"
            data-testid="settings-save-btn"
          >
            {saving ? (
              <span className="text-sm">Saving...</span>
            ) : (
              <>
                <Save size={14} />
                Save Settings
              </>
            )}
          </button>
          {saved && (
            <span className="flex items-center gap-1 text-sm text-emerald-400 font-mono" data-testid="settings-saved">
              <CheckCircle size={14} /> Saved
            </span>
          )}
          {error && (
            <span className="text-sm text-red-400 font-mono" data-testid="settings-error">{error}</span>
          )}
        </div>
      </div>
    </div>
  );
}
