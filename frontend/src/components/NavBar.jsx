import React from "react";
import { Link, useLocation } from "react-router-dom";
import { GitBranch, Settings, Clock, LayoutDashboard, ShieldCheck, Eye } from "lucide-react";

const navLinks = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/watch", label: "Watch", icon: Eye },
  { path: "/guardrails", label: "Guardrails", icon: ShieldCheck },
  { path: "/history", label: "History", icon: Clock },
  { path: "/settings", label: "Settings", icon: Settings },
];

export default function NavBar() {
  const { pathname } = useLocation();

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-14 bg-[#0A0A0A] border-b border-zinc-800 flex items-center px-6">
      <Link to="/" className="flex items-center gap-2 mr-8" data-testid="nav-logo">
        <div className="w-7 h-7 bg-emerald-400 flex items-center justify-center">
          <GitBranch size={14} className="text-black" strokeWidth={2.5} />
        </div>
        <span className="font-[Chivo] font-bold text-white tracking-tight">
          repoDoc
        </span>
      </Link>

      <nav className="flex items-center gap-1">
        {navLinks.map(({ path, label, icon: Icon }) => {
          const active = pathname === path;
          return (
            <Link
              key={path}
              to={path}
              data-testid={`nav-${label.toLowerCase()}`}
              className={`flex items-center gap-2 px-3 py-1.5 text-sm transition-colors duration-200 ${
                active
                  ? "text-white bg-zinc-800"
                  : "text-zinc-400 hover:text-white hover:bg-zinc-900"
              }`}
            >
              <Icon size={14} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="ml-auto flex items-center gap-2">
        <span className="text-xs font-mono text-zinc-500">
          autonomous bug fixer
        </span>
        <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
      </div>
    </header>
  );
}
