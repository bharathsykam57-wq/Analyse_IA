"use client";

import { useState, useEffect } from "react";
import { Sidebar } from "@/features/dashboard/components/Sidebar";
import { Menu, X, Globe } from "lucide-react";
import { useChatStore } from "@/features/agent/store/chatStore";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const { language, setLanguage } = useChatStore();
  const isFrench = language === 'fr';

  // Close mobile sidebar on route change cleanup by relying on the Link onClick
  
  // Prevent scrolling on body when mobile menu is open
  useEffect(() => {
    if (isMobileOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
  }, [isMobileOpen]);

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      
      {/* Desktop Sidebar */}
      <div className="hidden md:flex w-[220px] flex-shrink-0 z-20 shadow-2xl shadow-blue-900/10">
        <Sidebar className="w-full" />
      </div>

      {/* Mobile Sidebar Overlay */}
      {isMobileOpen && (
        <div 
          className="md:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      {/* Mobile Sidebar Drawer */}
      <div 
        className={`md:hidden fixed inset-y-0 left-0 z-50 w-72 transform transition-transform duration-300 ease-in-out shadow-2xl ${
          isMobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <Sidebar 
          className="w-full" 
          onLinkClick={() => setIsMobileOpen(false)} 
        />
        <button
          className="absolute top-6 -right-12 p-2 bg-card rounded-lg text-gray-400 hover:text-white border border-border"
          onClick={() => setIsMobileOpen(false)}
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        {/* Mobile Header Toggle */}
        <div className="md:hidden flex items-center p-4 border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-10">
          <button
            onClick={() => setIsMobileOpen(true)}
            className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors"
          >
            <Menu className="w-6 h-6" />
          </button>
          <button
            onClick={() => setLanguage(isFrench ? 'en' : 'fr')}
            className="ml-2 p-2 text-gray-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors flex items-center gap-1 text-xs font-semibold"
          >
            <Globe className="w-4 h-4 text-blue-400" />
            {isFrench ? "EN" : "FR"}
          </button>
          <span className="ml-3 font-semibold text-white tracking-tight">Analyse IA</span>
        </div>

        <main className="flex-1 overflow-y-auto w-full h-full relative scroll-smooth">
          {children}
        </main>
      </div>
    </div>
  );
}
