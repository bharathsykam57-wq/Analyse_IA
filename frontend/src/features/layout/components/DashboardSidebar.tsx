"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  History,
  Settings,
  Download,
  BookOpen,
  User,
  Menu,
  X,
  ChevronDown,
  LogOut,
  Bell,
} from "lucide-react";
import { Button } from "@/shared/components/ui/Button";

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  badge?: string;
}

interface NavSection {
  label: string;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    label: "Principal",
    items: [
      {
        label: "Tableau de Bord",
        href: "/dashboard",
        icon: <LayoutDashboard className="w-5 h-5" />,
      },
    ],
  },
  {
    label: "Outils",
    items: [
      {
        label: "Historique",
        href: "/history",
        icon: <History className="w-5 h-5" />,
      },
      {
        label: "Exports",
        href: "/exports",
        icon: <Download className="w-5 h-5" />,
      },
    ],
  },
  {
    label: "Ressources",
    items: [
      {
        label: "Documentation",
        href: "/docs",
        icon: <BookOpen className="w-5 h-5" />,
      },
    ],
  },
  {
    label: "Compte",
    items: [
      {
        label: "Paramètres",
        href: "/settings",
        icon: <Settings className="w-5 h-5" />,
      },
      {
        label: "Infos Compte",
        href: "/account",
        icon: <User className="w-5 h-5" />,
      },
    ],
  },
];

export default function DashboardSidebar() {
  const pathname = usePathname();
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(["Principal", "Outils"])
  );

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
    <>
      {/* Mobile Toggle */}
      <div className="md:hidden fixed top-4 left-4 z-50">
        <Button
          size="icon"
          variant="outline"
          onClick={() => setIsMobileOpen(!isMobileOpen)}
          className="bg-gray-900/80 backdrop-blur-md border-gray-800"
        >
          {isMobileOpen ? (
            <X className="w-5 h-5" />
          ) : (
            <Menu className="w-5 h-5" />
          )}
        </Button>
      </div>

      {/* Sidebar */}
      <motion.div
        className={`fixed left-0 top-0 h-screen w-64 bg-gray-900/95 backdrop-blur-md border-r border-gray-800/50 z-40 transition-all duration-300 md:static md:bg-transparent md:backdrop-blur-none md:border-r md:border-gray-800/50 ${
          isMobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="flex flex-col h-full p-4 space-y-6">
          {/* Logo Area */}
          <div className="pt-8 md:pt-0">
            <Link href="/dashboard" className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <span className="text-white font-bold text-sm">AI</span>
              </div>
              <span className="font-bold text-lg text-white hidden md:block">
                Analyse IA
              </span>
            </Link>
          </div>

          {/* User Info */}
          <div className="hidden md:flex items-center gap-3 px-2 py-2 rounded-lg bg-white/[0.02] border border-white/5">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500/20 to-purple-500/20 border border-blue-500/30 flex items-center justify-center flex-shrink-0">
              <User className="w-4 h-4 text-blue-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-gray-400">Compte</p>
              <p className="text-sm text-white truncate">John Doe</p>
            </div>
            <Bell className="w-4 h-4 text-gray-500 flex-shrink-0" />
          </div>

          {/* Navigation Items */}
          <div className="flex-1 overflow-y-auto space-y-1">
            {navSections.map((section) => (
              <motion.div
                key={section.label}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3 }}
              >
                {/* Section Header */}
                <button
                  onClick={() => toggleSection(section.label)}
                  className="w-full flex items-center justify-between px-2 py-2 text-xs font-semibold text-gray-400 hover:text-gray-300 transition-colors uppercase tracking-wider"
                >
                  {section.label}
                  {expandedSections.has(section.label) && (
                    <ChevronDown className="w-4 h-4" />
                  )}
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
                            onClick={() => setIsMobileOpen(false)}
                            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 group relative overflow-hidden ${
                              active
                                ? "bg-blue-600/20 text-blue-300 border border-blue-500/30"
                                : "text-gray-400 hover:text-gray-200 hover:bg-white/[0.02]"
                            }`}
                          >
                            {active && (
                              <motion.div
                                className="absolute inset-0 bg-blue-600/5 -z-10"
                                layoutId="navIndicator"
                                transition={{ type: "spring", bounce: 0.2 }}
                              />
                            )}

                            <div
                              className={`p-1 rounded transition-all ${
                                active
                                  ? "bg-blue-500/20 text-blue-300"
                                  : "group-hover:bg-blue-500/10 text-gray-500 group-hover:text-blue-400"
                              }`}
                            >
                              {item.icon}
                            </div>

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
              </motion.div>
            ))}
          </div>

          {/* Bottom Actions */}
          <div className="border-t border-gray-800/50 pt-4 space-y-2">
            <Link href="/settings" className="w-full">
              <Button
                variant="outline"
                size="sm"
                className="w-full gap-2 bg-white/[0.02] border-white/10 hover:bg-white/[0.04]"
              >
                <Settings className="w-4 h-4" />
                <span className="hidden md:inline">Paramètres</span>
              </Button>
            </Link>

            <Button
              variant="outline"
              size="sm"
              className="w-full gap-2 text-red-400 border-red-500/20 hover:bg-red-500/10"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden md:inline">Déconnexion</span>
            </Button>
          </div>
        </div>
      </motion.div>

      {/* Mobile Overlay */}
      {isMobileOpen && (
        <motion.div
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
          onClick={() => setIsMobileOpen(false)}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        />
      )}
    </>
  );
}
