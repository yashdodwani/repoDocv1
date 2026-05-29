import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { ArrowLeft, ExternalLink, GitPullRequest, RefreshCw } from "lucide-react";
import AgentStepper from "@/components/AgentStepper";
import LogStream from "@/components/LogStream";
import BugCard from "@/components/BugCard";
import CodeDiff from "@/components/CodeDiff";
import { API } from "../lib/api";

const RUNNING_STATUSES = ["queued", "cloning", "analyzing", "fixing", "verifying", "creating_pr"];

function StatusBadge({ status }) {
  const map = {
    queued: "text-zinc-400 border-zinc-700 bg-zinc-900",
    cloning: "text-blue-400 border-blue-700 bg-blue-900/20",
    analyzing: "text-yellow-400 border-yellow-700 bg-yellow-900/20",
    fixing: "text-orange-400 border-orange-700 bg-orange-900/20",
    verifying: "text-purple-400 border-purple-700 bg-purple-900/20",
    creating_pr: "text-cyan-400 border-cyan-700 bg-cyan-900/20",
    completed: "text-emerald-400 border-emerald-700 bg-emerald-900/20",
    failed: "text-red-400 border-red-700 bg-red-900/20",
  };
  return (
    <span className={`text-xs font-mono px-2 py-1 border ${map[status] || map.queued}`} data-testid="status-badge">
      {status}
    </span>
  );
}

export default function AnalysisDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("bugs");

  const fetchAnalysis = async () => {
    try {
      const res = await axios.get(`${API}/analyses/${id}`);
      setAnalysis(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalysis();
  }, [id]);

  // Poll while running
  useEffect(() => {
    if (!analysis || !RUNNING_STATUSES.includes(analysis.status)) return;
    const timer = setInterval(fetchAnalysis, 2000);
    return () => clearInterval(timer);
  }, [analysis?.status]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw size={20} className="text-zinc-600 animate-spin" />
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="max-w-6xl mx-auto px-6 py-8 text-zinc-500">Analysis not found.</div>
    );
  }

  const isRunning = RUNNING_STATUSES.includes(analysis.status);
  const verifiedFixes = (analysis.fixes || []).filter((f) => f.verified);
  const tabs = [
    { key: "bugs", label: `Bugs (${analysis.bugs?.length || 0})` },
    { key: "fixes", label: `Fixes (${analysis.fixes?.length || 0})` },
    { key: "logs", label: `Logs (${analysis.logs?.length || 0})` },
  ];

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-start gap-4 mb-6">
        <button
          onClick={() => navigate("/")}
          className="p-2 border border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-900 transition-colors shrink-0"
          data-testid="back-btn"
        >
          <ArrowLeft size={14} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap mb-1">
            <h1 className="text-xl font-[Chivo] font-bold text-white truncate" data-testid="analysis-repo-name">
              {analysis.repo_name || analysis.repo_url}
            </h1>
            <StatusBadge status={analysis.status} />
            {isRunning && <RefreshCw size={12} className="text-emerald-400 animate-spin" />}
          </div>
          <a
            href={analysis.repo_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-mono text-zinc-500 hover:text-zinc-300 flex items-center gap-1"
          >
            {analysis.repo_url} <ExternalLink size={10} />
          </a>
        </div>

        {analysis.pr_url && (
          <a
            href={analysis.pr_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 bg-emerald-400 text-black text-sm font-bold hover:bg-emerald-300 transition-colors shrink-0"
            data-testid="pr-link"
          >
            <GitPullRequest size={14} />
            View PR
          </a>
        )}
      </div>

      {/* Summary bar */}
      {analysis.status === "completed" && (
        <div className="grid grid-cols-3 border border-zinc-800 mb-6">
          <div className="p-4 border-r border-zinc-800">
            <div className="text-xs font-mono text-zinc-500 mb-1">Bugs Found</div>
            <div className="text-2xl font-[Chivo] font-bold text-red-400">{analysis.bugs?.length || 0}</div>
          </div>
          <div className="p-4 border-r border-zinc-800">
            <div className="text-xs font-mono text-zinc-500 mb-1">Fixes Verified</div>
            <div className="text-2xl font-[Chivo] font-bold text-emerald-400">{verifiedFixes.length}</div>
          </div>
          <div className="p-4">
            <div className="text-xs font-mono text-zinc-500 mb-1">Language</div>
            <div className="text-2xl font-[Chivo] font-bold text-white capitalize">
              {analysis.file_map?.language || "—"}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Agent Loop */}
        <div className="lg:col-span-1">
          <div className="border border-zinc-800 bg-[#111111] p-4">
            <h2 className="text-xs font-[Chivo] font-bold text-zinc-400 uppercase tracking-widest mb-4">
              Agent Loop
            </h2>
            <AgentStepper steps={analysis.agent_steps || []} />
          </div>

          {/* Error display */}
          {analysis.error && (
            <div className="mt-4 border border-red-800 bg-red-900/10 p-3" data-testid="analysis-error">
              <p className="text-xs font-mono text-red-400">{analysis.error}</p>
            </div>
          )}

          {/* File Map */}
          {analysis.file_map && (
            <div className="mt-4 border border-zinc-800 bg-[#111111] p-4">
              <h3 className="text-xs font-[Chivo] font-bold text-zinc-400 uppercase tracking-widest mb-3">
                File Map
              </h3>
              <div className="space-y-1.5 text-xs font-mono">
                <div className="flex justify-between">
                  <span className="text-zinc-500">language</span>
                  <span className="text-white">{analysis.file_map.language}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">total files</span>
                  <span className="text-white">{analysis.file_map.total_files}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">test files</span>
                  <span className="text-white">{analysis.file_map.test_files?.length || 0}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right: Tabs */}
        <div className="lg:col-span-2">
          {/* Tab bar */}
          <div className="flex border-b border-zinc-800 mb-4">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-4 py-2 text-sm font-mono transition-colors ${
                  activeTab === tab.key
                    ? "text-white border-b-2 border-emerald-400"
                    : "text-zinc-500 hover:text-zinc-300"
                }`}
                data-testid={`tab-${tab.key}`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Bugs Tab */}
          {activeTab === "bugs" && (
            <div className="space-y-3" data-testid="bugs-tab">
              {(analysis.bugs || []).length === 0 ? (
                <div className="border border-zinc-800 p-8 text-center text-zinc-500 text-sm">
                  {isRunning ? "Analyzing..." : "No bugs found"}
                </div>
              ) : (
                (analysis.bugs || []).map((bug) => {
                  const fix = (analysis.fixes || []).find((f) => f.bug_id === bug.id);
                  return <BugCard key={bug.id} bug={bug} fix={fix} />;
                })
              )}
            </div>
          )}

          {/* Fixes Tab */}
          {activeTab === "fixes" && (
            <div className="space-y-4" data-testid="fixes-tab">
              {(analysis.fixes || []).length === 0 ? (
                <div className="border border-zinc-800 p-8 text-center text-zinc-500 text-sm">
                  {isRunning ? "Generating fixes..." : "No fixes generated"}
                </div>
              ) : (
                (analysis.fixes || []).map((fix) => (
                  <div key={fix.id} className="space-y-2">
                    <div className="flex items-center gap-2 text-xs font-mono">
                      <span className={fix.verified ? "text-emerald-400" : "text-yellow-400"}>
                        {fix.verified ? "verified" : "unverified"}
                      </span>
                      <span className="text-zinc-600">{fix.file}</span>
                    </div>
                    {fix.explanation && (
                      <p className="text-sm text-zinc-300">{fix.explanation}</p>
                    )}
                    <CodeDiff
                      originalCode={fix.original_code}
                      fixedCode={fix.fixed_code}
                      diff={fix.diff}
                      file={fix.file}
                    />
                  </div>
                ))
              )}
            </div>
          )}

          {/* Logs Tab */}
          {activeTab === "logs" && (
            <LogStream logs={analysis.logs || []} isRunning={isRunning} />
          )}
        </div>
      </div>
    </div>
  );
}
