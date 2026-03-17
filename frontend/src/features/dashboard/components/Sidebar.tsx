"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  LayoutDashboard, 
  UploadCloud, 
  History, 
  Shield, 
  Settings, 
  LogOut, 
  Download,
  BookOpen,
  User,
  ChevronDown
} from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { useAuthStore } from "@/features/auth/store/authStore";
import { useChatStore } from "@/features/agent/store/chatStore";
import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

interface SidebarProps {
  className?: string;
  onLinkClick?: () => void;
}

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

interface NavSection {
  label: string;
  items: NavItem[];
}

export function Sidebar({ className, onLinkClick }: SidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();
  const { language, setLanguage } = useChatStore();
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(["main", "tools"])
  );

  const isFrench = language === 'fr';

  const navSections: NavSection[] = [
    {
      label: "main",
      items: [
        { 
          label: isFrench ? "Tableau de Bord" : "Dashboard", 
          href: "/dashboard", 
          icon: LayoutDashboard 
        },
        { 
          label: isFrench ? "Téléversement" : "Upload", 
          href: "/upload", 
          icon: UploadCloud 
        },
      ],
    },
    {
      label: "tools",
      items: [
        { 
          label: isFrench ? "Historique" : "History", 
          href: "/history", 
          icon: History 
        },
        { 
          label: isFrench ? "Exports" : "Exports", 
          href: "/exports", 
          icon: Download 
        },
      ],
    },
    {
      label: "resources",
      items: [
        { 
          label: isFrench ? "Documentation" : "Documentation", 
          href: "/docs", 
          icon: BookOpen 
        },
        { 
          label: isFrench ? "RGPD & Confidentialité" : "GDPR & Privacy", 
          href: "/rgpd", 
          icon: Shield 
        },
      ],
    },
    {
      label: "account",
      items: [
        { 
          label: isFrench ? "Paramètres" : "Settings", 
          href: "/settings", 
          icon: Settings 
        },
        { 
          label: isFrench ? "Compte" : "Account", 
          href: "/account", 
          icon: User 
        },
      ],
    },
  ];

  const toggleSection = (label: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(label)) {
      newExpanded.delete(label);
    } else {
      newExpanded.add(label);
    }
    setExpandedSections(newExpanded);
  };

  const isActive = (href: string) => {
    if (href === "/dashboard") {
      return pathname === "/dashboard" || pathname === "/dashboard/";
    }
    return pathname?.startsWith(href);
  };

  return (
    <div className={cn("flex flex-col h-full bg-[rgba(15,31,61,0.8)] backdrop-blur-xl border-r border-border text-gray-300 transition-all", className)}>
      {/* Logo */}
      <div className="p-6">
        <Link href="/dashboard" className="flex items-center gap-2 group cursor-pointer hover:opacity-90 transition-opacity">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center group-hover:scale-105 transition-transform shadow-lg shadow-blue-900/40">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-xl font-bold font-sans text-white tracking-tight">
            Analyse <span className="text-blue-500">IA</span>
          </h1>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 space-y-3 mt-4 overflow-y-auto">
        {navSections.map((section) => (
          <div key={section.label}>
            {/* Section Header */}
            <button
              onClick={() => toggleSection(section.label)}
              className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold text-gray-500 hover:text-gray-300 uppercase tracking-wider transition-colors"
            >
              <span>
                {section.label === "main" 
                  ? (isFrench ? "Principal" : "Main")
                  : section.label === "tools"
                  ? (isFrench ? "Outils" : "Tools")
                  : section.label === "resources"
                  ? (isFrench ? "Ressources" : "Resources")
                  : (isFrench ? "Compte" : "Account")}
              </span>
              <motion.div
                animate={{ rotate: expandedSections.has(section.label) ? 180 : 0 }}
                transition={{ duration: 0.2 }}
              >
                <ChevronDown className="w-4 h-4" />
              </motion.div>
            </button>

            {/* Section Items */}
            <AnimatePresence>
              {expandedSections.has(section.label) && (
                <motion.div
                  className="space-y-1"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  {section.items.map((item) => {
                    const active = isActive(item.href);
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={onLinkClick}
                        className={cn(
                          "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 group",
                          active
                            ? "bg-blue-600/15 text-blue-400 font-semibold shadow-[inset_4px_0_0_0_#2563EB]"
                            : "hover:bg-blue-600/10 hover:text-white"
                        )}
                      >
                        <item.icon 
                          className={cn(
                            "w-5 h-5 transition-transform group-hover:scale-110",
                            active ? "text-blue-500" : "text-gray-400"
                          )} 
                        />
                        <span className="flex-1">{item.label}</span>
                        {item.badge && (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-blue-600/20 text-blue-300">
                            {item.badge}
                          </span>
                        )}
                      </Link>
                    );
                  })}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 mt-auto border-t border-border bg-[#0A1628]/50 pb-24">
        <div className="flex items-center justify-between gap-3 px-1">
          <Link 
            href="/account"
            className="flex items-center gap-3 min-w-0 flex-1 hover:bg-white/5 p-2 rounded-xl transition-all group"
          >
            <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white font-bold shadow-lg shadow-blue-900/40 ring-2 ring-white/5 group-hover:ring-blue-500/50 transition-all ml-1 flex-shrink-0">
              {user?.email?.[0].toUpperCase() || "U"}
            </div>
            <div className="min-w-0">
              <p className="text-xs font-bold text-white truncate" title={user?.email || "user@example.com"}>
                {user?.email?.split('@')[0] || "Utilisateur"}
              </p>
              <p className="text-[10px] text-blue-400 font-medium truncate uppercase tracking-wider">
                Compte PRO
              </p>
            </div>
          </Link>

          <button 
            onClick={logout}
            className="p-2.5 text-gray-400 hover:text-red-400 hover:bg-red-500/10 rounded-xl transition-all flex-shrink-0 mr-1"
            title={isFrench ? "Déconnexion" : "Logout"}
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
