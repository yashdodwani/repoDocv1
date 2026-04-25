import React, { useState, useEffect } from "react";
import axios from "axios";
import {
  ShieldCheck, Plus, Trash2, RefreshCw, Sparkles,
  ShieldAlert, Code2, FileWarning, CheckSquare, Square, X,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SEVERITY_CLASS = {
  critical: "text-red-400 border-red-700",
  warning: "text-amber-400 border-amber-700",
  info: "text-cyan-400 border-cyan-700",
};

const CATEGORY_ICON = {
  security: ShieldAlert,
  quality: Code2,
  compliance: FileWarning,
};

function PresetCard({ preset, onPick, busy }) {
  return (
    <button
      onClick={() => onPick(preset.key)}
      disabled={busy}
      data-testid={`preset-${preset.key}`}
      className="text-left border border-zinc-800 bg-[#111111] p-5 hover:bg-zinc-900 hover:border-emerald-700 transition-all disabled:opacity-50"
    >
      <div className="flex items-center gap-2 mb-2">
        <Sparkles size={14} className="text-emerald-400" />
        <span className="text-sm font-[Chivo] font-bold text-white">{preset.name}</span>
      </div>
      <p className="text-xs text-zinc-500 mb-3 leading-relaxed">{preset.description}</p>
      <div className="flex flex-wrap gap-1">
        {preset.rule_ids.map((rid) => (
          <span key={rid} className="text-[10px] font-mono text-zinc-500 border border-zinc-800 px-1.5 py-0.5">
            {rid}
          </span>
        ))}
      </div>
    </button>
  );
}

function RuleRow({ rule, enabled, onToggle, removable, onRemove }) {
  const Icon = CATEGORY_ICON[rule.category] || Code2;
  return (
    <div className="flex items-start gap-3 p-3 border border-zinc-800 bg-[#0F0F0F]" data-testid={`rule-${rule.builtin_id || rule.id}`}>
      <button onClick={onToggle} className="mt-0.5 text-zinc-300 hover:text-emerald-400">
        {enabled ? <CheckSquare size={16} /> : <Square size={16} />}
      </button>
      <Icon size={14} className="mt-1 text-zinc-500 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-white font-medium">{rule.name}</span>
          <span className={`text-[10px] font-mono px-1.5 py-0.5 border ${SEVERITY_CLASS[rule.severity] || SEVERITY_CLASS.info}`}>
            {rule.severity}
          </span>
          <span className="text-[10px] font-mono text-zinc-500 border border-zinc-800 px-1.5 py-0.5">
            {rule.type}
          </span>
        </div>
        <p className="text-xs text-zinc-500 mt-1">{rule.description}</p>
      </div>
      {removable && (
        <button onClick={onRemove} className="text-zinc-600 hover:text-red-400">
          <X size={14} />
        </button>
      )}
    </div>
  );
}

function CustomRuleForm({ onAdd }) {
  const [name, setName] = useState("");
  const [pattern, setPattern] = useState("");
  const [severity, setSeverity] = useState("warning");
  const [category, setCategory] = useState("quality");

  const handleAdd = () => {
    if (!name.trim() || !pattern.trim()) return;
    onAdd({
      id: `custom-${Date.now()}`,
      name: name.trim(),
      description: "Custom regex rule",
      category,
      type: "pattern",
      pattern: pattern.trim(),
      severity,
      enabled: true,
    });
    setName(""); setPattern("");
  };

  return (
    <div className="border border-dashed border-zinc-800 p-4 bg-[#0A0A0A]">
      <p className="text-xs font-mono text-zinc-500 uppercase mb-3 tracking-wider">Add Custom Regex Rule</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-2">
        <input
          value={name} onChange={(e) => setName(e.target.value)}
          placeholder="Rule name"
          data-testid="custom-rule-name"
          className="bg-[#0A0A0A] border border-zinc-800 text-white px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-emerald-400"
        />
        <input
          value={pattern} onChange={(e) => setPattern(e.target.value)}
          placeholder="Regex pattern (e.g. ^\\+.*TODO)"
          data-testid="custom-rule-pattern"
          className="bg-[#0A0A0A] border border-zinc-800 text-white px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-emerald-400"
        />
        <select
          value={category} onChange={(e) => setCategory(e.target.value)}
          className="bg-[#0A0A0A] border border-zinc-800 text-white px-3 py-2 text-sm font-mono"
        >
          <option value="security">security</option>
          <option value="quality">quality</option>
          <option value="compliance">compliance</option>
        </select>
        <select
          value={severity} onChange={(e) => setSeverity(e.target.value)}
          className="bg-[#0A0A0A] border border-zinc-800 text-white px-3 py-2 text-sm font-mono"
        >
          <option value="critical">critical</option>
          <option value="warning">warning</option>
          <option value="info">info</option>
        </select>
      </div>
      <button
        onClick={handleAdd}
        data-testid="custom-rule-add-btn"
        className="flex items-center gap-2 px-3 py-1.5 bg-zinc-800 text-white text-xs hover:bg-zinc-700"
      >
        <Plus size={12} /> Add Rule
      </button>
    </div>
  );
}

function GuardrailsBuilder({ builtin, onSave, onClose }) {
  const [name, setName] = useState("My Custom Ruleset");
  const [enabled, setEnabled] = useState(() => {
    const m = {};
    builtin.rules.forEach((r) => { m[r.id] = false; });
    return m;
  });
  const [customRules, setCustomRules] = useState([]);
  const [saving, setSaving] = useState(false);

  const toggle = (id) => setEnabled((p) => ({ ...p, [id]: !p[id] }));
  const removeCustom = (id) => setCustomRules((p) => p.filter((r) => r.id !== id));

  const handleSave = async () => {
    const rules = [
      ...builtin.rules
        .filter((r) => enabled[r.id])
        .map((r) => ({ ...r, builtin_id: r.id, enabled: true })),
      ...customRules,
    ];
    if (rules.length === 0) return;
    setSaving(true);
    try {
      await axios.post(`${API}/guardrails`, {
        name: name.trim() || "Custom Ruleset",
        description: "User-created ruleset",
        rules,
      });
      onSave();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="border border-zinc-800 bg-[#111111] p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-[Chivo] font-bold text-white uppercase tracking-widest">
          Build Custom Ruleset
        </h3>
        <button onClick={onClose} className="text-zinc-500 hover:text-white" data-testid="builder-close">
          <X size={16} />
        </button>
      </div>
      <input
        value={name} onChange={(e) => setName(e.target.value)}
        placeholder="Ruleset name"
        data-testid="ruleset-name-input"
        className="w-full bg-[#0A0A0A] border border-zinc-800 text-white px-3 py-2 text-sm font-mono mb-4 focus:outline-none focus:ring-1 focus:ring-emerald-400"
      />
      <p className="text-xs font-mono text-zinc-500 uppercase mb-2 tracking-wider">Built-in Rules</p>
      <div className="space-y-2 mb-4">
        {builtin.rules.map((r) => (
          <RuleRow
            key={r.id}
            rule={r}
            enabled={!!enabled[r.id]}
            onToggle={() => toggle(r.id)}
          />
        ))}
      </div>
      {customRules.length > 0 && (
        <>
          <p className="text-xs font-mono text-zinc-500 uppercase mb-2 tracking-wider">Custom Rules</p>
          <div className="space-y-2 mb-4">
            {customRules.map((r) => (
              <RuleRow
                key={r.id}
                rule={r}
                enabled
                onToggle={() => {}}
                removable
                onRemove={() => removeCustom(r.id)}
              />
            ))}
          </div>
        </>
      )}
      <CustomRuleForm onAdd={(r) => setCustomRules((p) => [...p, r])} />
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onClose} className="px-4 py-2 text-sm text-zinc-400 hover:text-white">Cancel</button>
        <button
          onClick={handleSave}
          disabled={saving}
          data-testid="save-ruleset-btn"
          className="px-5 py-2 bg-emerald-400 text-black text-sm font-bold hover:bg-emerald-300 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save Ruleset"}
        </button>
      </div>
    </div>
  );
}

function SavedRulesetCard({ guardrails, onDelete }) {
  const counts = guardrails.rules.reduce(
    (acc, r) => {
      acc[r.severity] = (acc[r.severity] || 0) + 1;
      return acc;
    },
    {}
  );
  return (
    <div
      className="border border-zinc-800 bg-[#111111] p-4 flex items-start justify-between gap-4"
      data-testid={`saved-ruleset-${guardrails.id}`}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <ShieldCheck size={14} className="text-emerald-400" />
          <span className="text-sm font-[Chivo] font-bold text-white truncate">{guardrails.name}</span>
        </div>
        <p className="text-xs text-zinc-500 mb-2">{guardrails.description || "—"}</p>
        <div className="flex items-center gap-3 text-xs font-mono text-zinc-500">
          <span>{guardrails.rules.length} rules</span>
          {counts.critical && <span className="text-red-400">{counts.critical} critical</span>}
          {counts.warning && <span className="text-amber-400">{counts.warning} warning</span>}
          {counts.info && <span className="text-cyan-400">{counts.info} info</span>}
        </div>
      </div>
      <button
        onClick={onDelete}
        className="text-zinc-600 hover:text-red-400 p-1"
        data-testid={`delete-ruleset-${guardrails.id}`}
        title="Delete ruleset"
      >
        <Trash2 size={14} />
      </button>
    </div>
  );
}

export default function Guardrails() {
  const [builtin, setBuiltin] = useState({ rules: [], presets: [] });
  const [saved, setSaved] = useState([]);
  const [building, setBuilding] = useState(false);
  const [busy, setBusy] = useState(false);

  const fetchAll = async () => {
    const [b, g] = await Promise.all([
      axios.get(`${API}/guardrails/builtin`),
      axios.get(`${API}/guardrails`),
    ]);
    setBuiltin(b.data);
    setSaved(g.data);
  };

  useEffect(() => { fetchAll(); }, []);

  const handlePickPreset = async (key) => {
    setBusy(true);
    try {
      await axios.post(`${API}/guardrails/from-preset`, { preset: key });
      await fetchAll();
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this ruleset? Watched repos using it will be detached.")) return;
    await axios.delete(`${API}/guardrails/${id}`);
    fetchAll();
  };

  return (
    <div className="max-w-6xl mx-auto px-6 py-8" data-testid="guardrails-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-[Chivo] font-bold text-white tracking-tight">Guardrails</h1>
          <p className="text-zinc-500 text-sm mt-1">
            Define organizational coding rules. Every new commit is evaluated before bad code spreads.
          </p>
        </div>
        <button
          onClick={fetchAll}
          className="p-2 border border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-900"
          data-testid="guardrails-refresh"
        >
          <RefreshCw size={14} />
        </button>
      </div>

      <h2 className="text-xs font-[Chivo] font-bold text-zinc-500 uppercase tracking-widest mb-3">
        Quick Start — Presets
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
        {builtin.presets.map((p) => (
          <PresetCard key={p.key} preset={p} onPick={handlePickPreset} busy={busy} />
        ))}
      </div>

      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-[Chivo] font-bold text-zinc-500 uppercase tracking-widest">
          Saved Rulesets ({saved.length})
        </h2>
        {!building && (
          <button
            onClick={() => setBuilding(true)}
            data-testid="open-builder-btn"
            className="flex items-center gap-2 px-3 py-1.5 bg-white text-black text-xs font-bold hover:bg-zinc-200"
          >
            <Plus size={12} /> Build Custom
          </button>
        )}
      </div>

      {building && (
        <div className="mb-6">
          <GuardrailsBuilder
            builtin={builtin}
            onSave={() => { setBuilding(false); fetchAll(); }}
            onClose={() => setBuilding(false)}
          />
        </div>
      )}

      {saved.length === 0 ? (
        <div className="border border-zinc-800 p-12 text-center">
          <ShieldCheck size={32} className="text-zinc-700 mx-auto mb-3" />
          <p className="text-zinc-500 text-sm">No rulesets yet. Pick a preset or build a custom one.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {saved.map((g) => (
            <SavedRulesetCard key={g.id} guardrails={g} onDelete={() => handleDelete(g.id)} />
          ))}
        </div>
      )}
    </div>
  );
}
