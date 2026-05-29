import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { RefreshCw, Trash2, ExternalLink } from "lucide-react";
import { API } from "../lib/api";

function StatusBadge({ status }) {
  const map = {
    completed: "text-emerald-400 border-emerald-700",
    failed: "text-red-400 border-red-700",
    queued: "text-zinc-400 border-zinc-700",
    cloning: "text-blue-400 border-blue-700",
    analyzing: "text-yellow-400 border-yellow-700",
    fixing: "text-orange-400 border-orange-700",
    verifying: "text-purple-400 border-purple-700",
    creating_pr: "text-cyan-400 border-cyan-700",
  };
  return (
    <span className={`text-xs font-mono px-2 py-0.5 border ${map[status] || map.queued}`}>
      {status}
    </span>
  );
}

export default function History() {
  const navigate = useNavigate();
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  const fetchAnalyses = async () => {
    try {
      const res = await axios.get(`${API}/analyses`);
      setAnalyses(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalyses();
  }, []);

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    try {
      await axios.delete(`${API}/analyses/${id}`);
      setAnalyses((prev) => prev.filter((a) => a.id !== id));
    } catch (e) {
      console.error(e);
    }
  };

  const filtered = filter === "all" ? analyses : analyses.filter((a) => a.status === filter);

  const filterOptions = [
    { value: "all", label: "All" },
    { value: "completed", label: "Completed" },
    { value: "failed", label: "Failed" },
  ];

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-[Chivo] font-bold text-white">History</h1>
          <p className="text-zinc-500 text-sm mt-1">All past analyses</p>
        </div>
        <button
          onClick={fetchAnalyses}
          className="p-2 border border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-900 transition-colors"
          data-testid="refresh-history-btn"
        >
          <RefreshCw size={14} />
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 mb-6 border-b border-zinc-800">
        {filterOptions.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setFilter(opt.value)}
            className={`px-4 py-2 text-sm font-mono transition-colors ${
              filter === opt.value
                ? "text-white border-b-2 border-emerald-400"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
            data-testid={`filter-${opt.value}`}
          >
            {opt.label}
            <span className="ml-2 text-xs text-zinc-600">
              {opt.value === "all"
                ? analyses.length
                : analyses.filter((a) => a.status === opt.value).length}
            </span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32">
          <RefreshCw size={16} className="text-zinc-600 animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="border border-zinc-800 p-12 text-center text-zinc-500 text-sm">
          No analyses found
        </div>
      ) : (
        <div className="border border-zinc-800 divide-y divide-zinc-800">
          {/* Header */}
          <div className="grid grid-cols-12 gap-4 px-4 py-2 text-xs font-mono text-zinc-600 uppercase">
            <div className="col-span-4">Repository</div>
            <div className="col-span-2">Status</div>
            <div className="col-span-1 text-center">Bugs</div>
            <div className="col-span-1 text-center">Fixed</div>
            <div className="col-span-3">Date</div>
            <div className="col-span-1"></div>
          </div>

          {filtered.map((analysis) => {
            const verifiedFixes = (analysis.fixes || []).filter((f) => f.verified).length;
            return (
              <div
                key={analysis.id}
                className="grid grid-cols-12 gap-4 px-4 py-3 hover:bg-zinc-900 cursor-pointer transition-colors items-center"
                onClick={() => navigate(`/analysis/${analysis.id}`)}
                data-testid={`history-row-${analysis.id}`}
              >
                <div className="col-span-4 min-w-0">
                  <span className="text-sm font-mono text-white truncate block">
                    {analysis.repo_name || analysis.repo_url}
                  </span>
                  {analysis.pr_url && (
                    <a
                      href={analysis.pr_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-cyan-400 flex items-center gap-1 hover:text-cyan-300"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <ExternalLink size={10} /> PR
                    </a>
                  )}
                </div>
                <div className="col-span-2">
                  <StatusBadge status={analysis.status} />
                </div>
                <div className="col-span-1 text-center text-sm font-mono text-red-400">
                  {analysis.bugs?.length || 0}
                </div>
                <div className="col-span-1 text-center text-sm font-mono text-emerald-400">
                  {verifiedFixes}
                </div>
                <div className="col-span-3 text-xs font-mono text-zinc-500">
                  {new Date(analysis.created_at).toLocaleString()}
                </div>
                <div className="col-span-1 flex justify-end">
                  <button
                    onClick={(e) => handleDelete(e, analysis.id)}
                    className="p-1 text-zinc-600 hover:text-red-400 transition-colors"
                    data-testid={`delete-btn-${analysis.id}`}
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
