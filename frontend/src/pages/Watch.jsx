import React, { useState, useEffect } from "react";
import axios from "axios";
import {
  Eye, Plus, Trash2, RefreshCw, GitBranch, GitPullRequest,
  AlertCircle, CheckCircle2, ExternalLink, Zap, Power, Rewind,
} from "lucide-react";
import { API } from "../lib/api";

function AddRepoForm({ guardrails, onAdd }) {
  const [repoUrl, setRepoUrl] = useState("");
  const [chatId, setChatId] = useState("");
  const [gid, setGid] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    if (!repoUrl.trim()) return;
    setBusy(true); setErr("");
    try {
      await axios.post(`${API}/watched-repos`, {
        repo_url: repoUrl.trim(),
        telegram_chat_id: chatId.trim(),
        guardrails_id: gid || null,
      });
      setRepoUrl(""); setChatId(""); setGid("");
      onAdd();
    } catch (e) {
      setErr(e.response?.data?.detail || "Failed to add");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border border-zinc-800 bg-[#111111] p-6 mb-8">
      <h2 className="text-sm font-[Chivo] font-bold text-white uppercase tracking-widest mb-4">
        Watch a New Repo
      </h2>
      <form onSubmit={submit} className="space-y-3">
        <input
          type="url"
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          placeholder="https://github.com/user/repo"
          required
          data-testid="watch-repo-url"
          className="w-full bg-[#0A0A0A] border border-zinc-800 text-white px-4 py-2.5 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-emerald-400"
        />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <select
            value={gid}
            onChange={(e) => setGid(e.target.value)}
            data-testid="watch-guardrails-select"
            className="bg-[#0A0A0A] border border-zinc-800 text-white px-3 py-2.5 text-sm font-mono"
          >
            <option value="">— No guardrails (clean polling only) —</option>
            {guardrails.map((g) => (
              <option key={g.id} value={g.id}>{g.name} ({g.rules.length} rules)</option>
            ))}
          </select>
          <input
            value={chatId}
            onChange={(e) => setChatId(e.target.value)}
            placeholder="Telegram chat ID (optional)"
            data-testid="watch-chat-id"
            className="bg-[#0A0A0A] border border-zinc-800 text-white px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-emerald-400"
          />
        </div>
        {err && <p className="text-red-400 text-xs font-mono">{err}</p>}
        <button
          type="submit"
          disabled={busy}
          data-testid="watch-add-btn"
          className="flex items-center gap-2 px-5 py-2.5 bg-emerald-400 text-black text-sm font-bold hover:bg-emerald-300 disabled:opacity-50"
        >
          <Plus size={14} /> {busy ? "Adding…" : "Watch Repo"}
        </button>
        <p className="text-zinc-600 text-xs font-mono">
          Polls every 5 minutes across all branches. Violations open a GitHub issue + auto-fix PR back on the same branch.
        </p>
      </form>
    </div>
  );
}

function WatchedRepoCard({ watched, guardrails, onUpdate, onDelete, onCheckNow, onReplay, onShowEvents, expanded }) {
  const gname = guardrails.find((g) => g.id === watched.guardrails_id)?.name || "—";
  const branchCount = Object.keys(watched.last_commits || {}).length;
  return (
    <div className="border border-zinc-800 bg-[#111111] p-4" data-testid={`watched-${watched.id}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Eye size={14} className={watched.active ? "text-emerald-400" : "text-zinc-600"} />
            <span className="text-sm font-mono text-white truncate">{watched.repo_name || watched.repo_url}</span>
            {!watched.active && (
              <span className="text-[10px] font-mono text-zinc-500 border border-zinc-700 px-1.5 py-0.5">paused</span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs font-mono text-zinc-500">
            <span><GitBranch size={10} className="inline mr-1" />{branchCount} branches tracked</span>
            <span>guardrails: <span className="text-zinc-300">{gname}</span></span>
            <span>events: {watched.events_count || 0}</span>
            <span className="text-amber-400">issues: {watched.issues_count || 0}</span>
            {watched.last_checked_at && (
              <span>last check: {new Date(watched.last_checked_at).toLocaleTimeString()}</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={onReplay}
            title="Replay last commit (demo)"
            data-testid={`replay-${watched.id}`}
            className="p-2 border border-amber-700/50 text-amber-400 hover:bg-amber-400/10"
          >
            <Rewind size={12} />
          </button>
          <button
            onClick={onCheckNow}
            title="Check now"
            data-testid={`check-now-${watched.id}`}
            className="p-2 border border-zinc-800 text-zinc-400 hover:text-emerald-400"
          >
            <Zap size={12} />
          </button>
          <button
            onClick={() => onUpdate({ active: !watched.active })}
            title={watched.active ? "Pause" : "Resume"}
            data-testid={`toggle-${watched.id}`}
            className="p-2 border border-zinc-800 text-zinc-400 hover:text-white"
          >
            <Power size={12} />
          </button>
          <button
            onClick={onShowEvents}
            data-testid={`events-${watched.id}`}
            className="px-2 py-2 border border-zinc-800 text-zinc-400 hover:text-white text-xs"
          >
            {expanded ? "Hide" : "Events"}
          </button>
          <button
            onClick={onDelete}
            title="Delete"
            data-testid={`delete-watched-${watched.id}`}
            className="p-2 border border-zinc-800 text-zinc-600 hover:text-red-400"
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>
    </div>
  );
}

function EventRow({ event }) {
  const Icon = event.status === "issues_found" ? AlertCircle : CheckCircle2;
  const iconCls = event.status === "issues_found" ? "text-amber-400" : "text-emerald-400";
  return (
    <div className="border border-zinc-800 bg-[#0F0F0F] p-3" data-testid={`event-${event.id}`}>
      <div className="flex items-center gap-2 mb-1">
        <Icon size={12} className={iconCls} />
        <span className="text-xs font-mono text-white">
          {event.repo_name} · <span className="text-zinc-400">{event.branch}</span> · <span className="text-zinc-500">{event.commit_sha?.slice(0, 8)}</span>
        </span>
        <span className="ml-auto text-[10px] font-mono text-zinc-600">
          {new Date(event.created_at).toLocaleString()}
        </span>
      </div>
      {event.commit_message && (
        <p className="text-xs text-zinc-500 ml-4 mb-2 italic truncate">"{event.commit_message}"</p>
      )}
      {event.issues?.length > 0 && (
        <div className="ml-4 mb-2 space-y-1">
          {event.issues.slice(0, 5).map((v, i) => (
            <div key={i} className="text-xs">
              <span className={`text-[10px] font-mono px-1.5 py-0.5 border mr-2 ${
                v.severity === "critical" ? "text-red-400 border-red-700"
                  : v.severity === "warning" ? "text-amber-400 border-amber-700"
                  : "text-cyan-400 border-cyan-700"
              }`}>
                {v.severity}
              </span>
              <span className="text-zinc-300">{v.rule_name}</span>
              <span className="text-zinc-500"> in </span>
              <span className="font-mono text-zinc-400">{v.file}</span>
            </div>
          ))}
        </div>
      )}
      <div className="ml-4 flex items-center gap-3 text-xs font-mono">
        {event.github_issue_url && (
          <a href={event.github_issue_url} target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline flex items-center gap-1">
            <ExternalLink size={10} /> issue
          </a>
        )}
        {event.pr_url && (
          <a href={event.pr_url} target="_blank" rel="noreferrer" className="text-emerald-400 hover:underline flex items-center gap-1">
            <GitPullRequest size={10} /> PR
          </a>
        )}
      </div>
    </div>
  );
}

export default function Watch() {
  const [watched, setWatched] = useState([]);
  const [guardrails, setGuardrails] = useState([]);
  const [allEvents, setAllEvents] = useState([]);
  const [expandedId, setExpandedId] = useState(null);

  const fetchAll = async () => {
    const [w, g, e] = await Promise.all([
      axios.get(`${API}/watched-repos`),
      axios.get(`${API}/guardrails`),
      axios.get(`${API}/watch-events?limit=50`),
    ]);
    setWatched(w.data);
    setGuardrails(g.data);
    setAllEvents(e.data);
  };

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 5000);
    return () => clearInterval(t);
  }, []);

  const handleDelete = async (id) => {
    if (!window.confirm("Stop watching this repo?")) return;
    await axios.delete(`${API}/watched-repos/${id}`);
    fetchAll();
  };

  const handleUpdate = async (id, body) => {
    await axios.put(`${API}/watched-repos/${id}`, body);
    fetchAll();
  };

  const handleCheckNow = async (id) => {
    await axios.post(`${API}/watched-repos/${id}/check-now`);
    setTimeout(fetchAll, 4000);
  };

  const handleReplay = async (id) => {
    if (!window.confirm("Replay the last commit? This will re-evaluate the current HEAD against guardrails — perfect for live demos.")) return;
    await axios.post(`${API}/watched-repos/${id}/replay`);
    setTimeout(fetchAll, 4000);
    setTimeout(fetchAll, 15000);
    setTimeout(fetchAll, 30000);
  };

  const eventsForRepo = (id) => allEvents.filter((e) => e.watched_repo_id === id);

  return (
    <div className="max-w-6xl mx-auto px-6 py-8" data-testid="watch-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-[Chivo] font-bold text-white tracking-tight">Continuous Watch</h1>
          <p className="text-zinc-500 text-sm mt-1">
            Auto-monitor repos. Detect bad commits. Open issues + fix PRs. All on autopilot.
          </p>
        </div>
        <button
          onClick={fetchAll}
          className="p-2 border border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-900"
          data-testid="watch-refresh"
        >
          <RefreshCw size={14} />
        </button>
      </div>

      <AddRepoForm guardrails={guardrails} onAdd={fetchAll} />

      <h2 className="text-xs font-[Chivo] font-bold text-zinc-500 uppercase tracking-widest mb-3">
        Watched Repos ({watched.length})
      </h2>
      {watched.length === 0 ? (
        <div className="border border-zinc-800 p-12 text-center mb-8">
          <Eye size={32} className="text-zinc-700 mx-auto mb-3" />
          <p className="text-zinc-500 text-sm">No repos under watch yet. Add one above to get started.</p>
        </div>
      ) : (
        <div className="space-y-3 mb-8">
          {watched.map((w) => (
            <div key={w.id}>
              <WatchedRepoCard
                watched={w}
                guardrails={guardrails}
                onUpdate={(body) => handleUpdate(w.id, body)}
                onDelete={() => handleDelete(w.id)}
                onCheckNow={() => handleCheckNow(w.id)}
                onReplay={() => handleReplay(w.id)}
                onShowEvents={() => setExpandedId(expandedId === w.id ? null : w.id)}
                expanded={expandedId === w.id}
              />
              {expandedId === w.id && (
                <div className="mt-2 ml-4 space-y-2" data-testid={`events-list-${w.id}`}>
                  {eventsForRepo(w.id).length === 0 ? (
                    <p className="text-xs text-zinc-600 font-mono py-2">No events yet for this repo.</p>
                  ) : (
                    eventsForRepo(w.id).slice(0, 10).map((e) => <EventRow key={e.id} event={e} />)
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <h2 className="text-xs font-[Chivo] font-bold text-zinc-500 uppercase tracking-widest mb-3">
        Recent Activity Across All Repos
      </h2>
      {allEvents.length === 0 ? (
        <div className="border border-zinc-800 p-8 text-center">
          <p className="text-zinc-500 text-sm font-mono">No commit events recorded yet.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {allEvents.slice(0, 15).map((e) => <EventRow key={e.id} event={e} />)}
        </div>
      )}
    </div>
  );
}
