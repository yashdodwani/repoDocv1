import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { Play, RefreshCw, GitBranch, Bug, CheckCircle, GitPullRequest } from "lucide-react";
import { API } from "../lib/api";

function StatCard({ label, value, icon: Icon, color }) {
  return (
    <div className="border border-zinc-800 bg-[#111111] p-4" data-testid={`stat-${label.toLowerCase().replace(/\s/g, '-')}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-mono text-zinc-500 uppercase tracking-wider">{label}</span>
        <Icon size={14} className={color} />
      </div>
      <div className={`text-3xl font-[Chivo] font-bold ${color}`}>{value}</div>
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    queued: "text-zinc-400 border-zinc-700",
    cloning: "text-blue-400 border-blue-700",
    analyzing: "text-yellow-400 border-yellow-700",
    fixing: "text-orange-400 border-orange-700",
    verifying: "text-purple-400 border-purple-700",
    creating_pr: "text-cyan-400 border-cyan-700",
    completed: "text-emerald-400 border-emerald-700",
    failed: "text-red-400 border-red-700",
  };
  return (
    <span className={`text-xs font-mono px-2 py-0.5 border ${map[status] || map.queued}`}>
      {status}
    </span>
  );
}

const RUNNING_STATUSES = ["queued", "cloning", "analyzing", "fixing", "verifying", "creating_pr"];

export default function Dashboard() {
  const navigate = useNavigate();
  const [repoUrl, setRepoUrl] = useState("");
  const [analyses, setAnalyses] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchData = async () => {
    try {
      const [analysesRes, statsRes] = await Promise.all([
        axios.get(`${API}/analyses`),
        axios.get(`${API}/stats`),
      ]);
      setAnalyses(analysesRes.data);
      setStats(statsRes.data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!repoUrl.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await axios.post(`${API}/analyses`, { repo_url: repoUrl.trim() });
      setRepoUrl("");
      navigate(`/analysis/${res.data.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to start analysis");
    } finally {
      setLoading(false);
    }
  };

  const hasRunning = analyses.some((a) => RUNNING_STATUSES.includes(a.status));

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-[Chivo] font-bold text-white tracking-tight">repoDoc</h1>
          <p className="text-zinc-500 text-sm mt-1">Autonomous bug detection & fixing agent</p>
        </div>
        <button
          onClick={fetchData}
          className="p-2 border border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-900 transition-colors"
          data-testid="refresh-btn"
        >
          <RefreshCw size={14} />
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard label="Analyses" value={stats.total_analyses} icon={GitBranch} color="text-white" />
          <StatCard label="Bugs Found" value={stats.bugs_found} icon={Bug} color="text-red-400" />
          <StatCard label="Fixes Applied" value={stats.fixes_applied} icon={CheckCircle} color="text-emerald-400" />
          <StatCard label="PRs Created" value={stats.prs_created} icon={GitPullRequest} color="text-cyan-400" />
        </div>
      )}

      {/* Submit Form */}
      <div className="border border-zinc-800 bg-[#111111] p-6 mb-8">
        <h2 className="text-sm font-[Chivo] font-bold text-white uppercase tracking-widest mb-4">
          New Analysis
        </h2>
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            type="url"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            placeholder="https://github.com/user/repo"
            className="flex-1 bg-[#0A0A0A] border border-zinc-800 text-white placeholder:text-zinc-600 px-4 py-2.5 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-emerald-400"
            data-testid="repo-url-input"
            required
          />
          <button
            type="submit"
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2.5 bg-white text-black text-sm font-bold hover:bg-zinc-200 transition-colors disabled:opacity-50"
            data-testid="analyze-btn"
          >
            {loading ? (
              <RefreshCw size={14} className="animate-spin" />
            ) : (
              <Play size={14} />
            )}
            Analyze
          </button>
        </form>
        {error && (
          <p className="text-red-400 text-xs font-mono mt-2" data-testid="analyze-error">{error}</p>
        )}
          <p className="text-zinc-600 text-xs font-mono mt-3">
            Supports public GitHub repos. Detects failing tests, lint errors &amp; logical bugs.
          </p>
      </div>

      {/* Running / Recent */}
      {analyses.length > 0 && (
        <div>
          {hasRunning && (
            <div className="mb-6">
              <h2 className="text-xs font-[Chivo] font-bold text-emerald-400 uppercase tracking-widest mb-3">
                Active
              </h2>
              <div className="space-y-2">
                {analyses.filter((a) => RUNNING_STATUSES.includes(a.status)).map((a) => (
                  <AnalysisRow key={a.id} analysis={a} navigate={navigate} />
                ))}
              </div>
            </div>
          )}
          <h2 className="text-xs font-[Chivo] font-bold text-zinc-500 uppercase tracking-widest mb-3">
            Recent
          </h2>
          <div className="space-y-2">
            {analyses.filter((a) => !RUNNING_STATUSES.includes(a.status)).slice(0, 10).map((a) => (
              <AnalysisRow key={a.id} analysis={a} navigate={navigate} />
            ))}
          </div>
        </div>
      )}

      {analyses.length === 0 && (
        <div className="border border-zinc-800 p-12 text-center">
          <GitBranch size={32} className="text-zinc-700 mx-auto mb-3" />
          <p className="text-zinc-500 text-sm">No analyses yet. Submit a GitHub repo URL to get started.</p>
        </div>
      )}
    </div>
  );
}

function AnalysisRow({ analysis, navigate }) {
  return (
    <button
      onClick={() => navigate(`/analysis/${analysis.id}`)}
      className="w-full flex items-center gap-4 p-3 border border-zinc-800 bg-[#111111] hover:bg-zinc-900 transition-colors text-left"
      data-testid={`analysis-row-${analysis.id}`}
    >
      <div className="flex-1 min-w-0">
        <span className="text-sm font-mono text-white truncate block">
          {analysis.repo_name || analysis.repo_url}
        </span>
        <span className="text-xs font-mono text-zinc-600">
          {new Date(analysis.created_at).toLocaleString()}
        </span>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        {analysis.bugs?.length > 0 && (
          <span className="text-xs font-mono text-red-400">{analysis.bugs.length} bugs</span>
        )}
        {analysis.fixes?.filter((f) => f.verified).length > 0 && (
          <span className="text-xs font-mono text-emerald-400">
            {analysis.fixes.filter((f) => f.verified).length} fixed
          </span>
        )}
        <StatusBadge status={analysis.status} />
      </div>
    </button>
  );
}
