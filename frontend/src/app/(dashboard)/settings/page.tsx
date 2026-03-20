"use client";

import { useState } from "react";
import { 
  Settings, 
  User, 
  Bell, 
  Key, 
  ShieldCheck, 
  CreditCard, 
  Users, 
  Zap, 
  Globe, 
  Save,
  ChevronRight,
  Database
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/components/ui/Card";
import { useAuthStore } from "@/features/auth/store/authStore";
import { Input } from "@/shared/components/ui/Input";
import { Button } from "@/shared/components/ui/Button";
import { cn } from "@/shared/lib/utils";

export default function SettingsPage() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState("general");

  const tabs = [
    { id: "general", label: "Général", icon: User },
    { id: "security", label: "Sécurité", icon: ShieldCheck },
    { id: "workspace", label: "Espace de travail", icon: Database },
    { id: "billing", label: "Facturation", icon: CreditCard },
  ];

  return (
    <div className="min-h-full bg-[#050A15] p-6 lg:p-12 relative overflow-hidden">
      {/* Ambient backgrounds */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-blue-600/5 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-indigo-600/5 rounded-full blur-[120px] pointer-events-none" />

      <div className="max-w-6xl mx-auto space-y-10 relative z-10 animate-in fade-in slide-in-from-bottom-4 duration-700">
        
        {/* Page Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-2 border-b border-white/5">
          <div className="space-y-1">
            <h1 className="text-4xl font-extrabold text-white tracking-tight flex items-center gap-4">
              <div className="p-3 bg-blue-500/10 rounded-2xl border border-blue-500/20 shadow-inner group">
                <Settings className="w-8 h-8 text-blue-400 group-hover:rotate-90 transition-transform duration-500" />
              </div>
              Paramètres
            </h1>
            <p className="text-blue-200/50 text-lg font-medium ml-1">
              Configurez votre identité numérique et vos préférences analytiques.
            </p>
          </div>
          
          <Button className="bg-blue-600 hover:bg-blue-500 text-white gap-2 h-11 px-6 shadow-xl shadow-blue-900/40 rounded-xl transition-all font-bold">
            <Save className="w-4 h-4" />
            Sauvegarder les changements
          </Button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
          
          {/* Navigation Sidebar */}
          <div className="lg:col-span-3 space-y-2">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "w-full flex items-center justify-between p-4 rounded-2xl transition-all group",
                    activeTab === tab.id 
                      ? "bg-white/[0.05] border border-white/10 text-white shadow-lg" 
                      : "text-gray-400 hover:text-white hover:bg-white/[0.02]"
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "p-2 rounded-lg transition-colors",
                      activeTab === tab.id ? "bg-blue-500/20 text-blue-400" : "bg-white/5 text-gray-500 group-hover:text-gray-300"
                    )}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <span className="font-semibold text-sm tracking-wide">{tab.label}</span>
                  </div>
                  {activeTab === tab.id && <ChevronRight className="w-4 h-4 text-blue-500" />}
                </button>
              );
            })}
          </div>

          {/* Settings Content Area */}
          <div className="lg:col-span-9 space-y-8 animate-in fade-in duration-500">
            
            {activeTab === 'general' && (
              <div className="space-y-8">
                {/* Profile Section */}
                <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl shadow-2xl overflow-hidden group">
                  <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-1000 pointer-events-none" />
                  <CardHeader className="border-b border-white/5 pb-6">
                    <CardTitle className="text-xl text-white flex items-center gap-3">
                      <div className="w-1.5 h-6 bg-blue-500 rounded-full" />
                      Profil Utilisateur
                    </CardTitle>
                    <CardDescription>Vos informations publiques au sein de l&apos;organisation.</CardDescription>
                  </CardHeader>
                  <CardContent className="p-8 pt-10 space-y-8">
                    <div className="flex items-center gap-8">
                      <div className="relative group/avatar">
                        <div className="w-24 h-24 rounded-3xl bg-gradient-to-tr from-blue-900 to-indigo-600 flex items-center justify-center text-3xl font-black text-white shadow-2xl shadow-blue-900/40 ring-4 ring-white/5 group-hover/avatar:ring-blue-500/30 transition-all cursor-pointer">
                          {user?.email?.[0].toUpperCase() || "U"}
                        </div>
                        <button className="absolute -bottom-2 -right-2 p-2 bg-blue-600 hover:bg-blue-500 rounded-xl shadow-xl border-2 border-[#050A15] text-white transition-transform active:scale-90">
                          <Zap className="w-4 h-4" />
                        </button>
                      </div>
                      <div className="space-y-2">
                        <h4 className="text-lg font-bold text-white capitalize">{user?.email?.split('@')[0] || "Utilisateur"}</h4>
                        <p className="text-sm text-blue-300/60 font-medium">{user?.email}</p>
                        <div className="flex gap-2 pt-1">
                          <span className="px-3 py-1 bg-blue-500/10 border border-blue-500/20 text-blue-400 text-[10px] font-bold rounded-full uppercase tracking-tighter">Membre Enterprise</span>
                          <span className="px-3 py-1 bg-green-500/10 border border-green-500/20 text-green-400 text-[10px] font-bold rounded-full uppercase tracking-tighter">Vérifié</span>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8 pt-4">
                      <div className="space-y-3">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2">
                          Nom Complet 
                        </label>
                        <Input 
                          defaultValue={user?.full_name || "L’Analyste"} 
                          className="bg-black/40 border-white/10 hover:border-white/20 focus:border-blue-500/50 h-12 text-gray-200"
                        />
                      </div>
                      <div className="space-y-3">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2">
                          Rôle
                        </label>
                        <Input 
                          defaultValue="Chef de Projet Analytique" 
                          className="bg-black/40 border-white/10 hover:border-white/20 focus:border-blue-500/50 h-12 text-gray-200"
                        />
                      </div>
                      <div className="space-y-3 md:col-span-2">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2">
                          Bio / Signature
                        </label>
                        <textarea 
                          className="w-full bg-black/40 border border-white/10 hover:border-white/20 focus:border-blue-500/50 rounded-xl p-4 text-sm text-gray-200 min-h-[100px] outline-none transition-all"
                          placeholder="Décrivez votre expertise..."
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Notifications & Language */}
                <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                  <CardHeader className="border-b border-white/5">
                    <CardTitle className="text-xl text-white flex items-center gap-3">
                      <div className="w-1.5 h-6 bg-indigo-500 rounded-full" />
                      Préférences
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-8 grid grid-cols-1 md:grid-cols-2 gap-12">
                    <div className="space-y-6">
                      <h5 className="text-sm font-bold text-gray-300 flex items-center gap-2">
                        <Bell className="w-4 h-4 text-blue-400" />
                        Canaux de Notifications
                      </h5>
                      <div className="space-y-4">
                        {[
                          "Alertes de fin d&apos;analyse par email",
                          "Notifications bureau temps réel",
                          "Rapports hebdomadaires automatiques"
                        ].map((label, i) => (
                          <label key={i} className="flex items-center justify-between gap-4 cursor-pointer group">
                             <span className="text-sm text-gray-400 group-hover:text-gray-200 transition-colors">{label}</span>
                             <div className="w-10 h-6 bg-white/5 border border-white/10 rounded-full relative group-hover:border-blue-500/30 transition-all">
                               <div className="w-4 h-4 bg-gray-500 rounded-full absolute top-1 left-1" />
                             </div>
                          </label>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-6">
                      <h5 className="text-sm font-bold text-gray-300 flex items-center gap-2">
                        <Globe className="w-4 h-4 text-indigo-400" />
                        Langue & Localisation
                      </h5>
                      <div className="space-y-4">
                        <div className="space-y-2">
                          <label className="text-[10px] font-bold text-gray-500 uppercase">Langue d&apos;interface</label>
                          <select className="w-full bg-black/40 border border-white/10 rounded-lg p-2.5 text-sm text-white outline-none">
                            <option>Français (FR)</option>
                            <option>English (US)</option>
                            <option>Deutsch (DE)</option>
                          </select>
                        </div>
                        <div className="space-y-2">
                          <label className="text-[10px] font-bold text-gray-500 uppercase">Fuseau Horaire</label>
                          <select className="w-full bg-black/40 border border-white/10 rounded-lg p-2.5 text-sm text-white outline-none">
                            <option>(GMT+01:00) Paris, Bruxelles</option>
                            <option>(GMT+00:00) London</option>
                            <option>(GMT-05:00) New York</option>
                          </select>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}

            {activeTab === 'security' && (
              <div className="animate-in fade-in duration-500 space-y-6">
                <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                  <CardHeader className="border-b border-white/5">
                    <CardTitle className="text-xl text-white flex items-center gap-3">
                      <Key className="w-5 h-5 text-blue-500" />
                      Authentification
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-8 space-y-8">
                     <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                        <div className="space-y-3">
                           <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Nouveau mot de passe</label>
                           <Input type="password" placeholder="••••••••" className="bg-black/40 border-white/10 h-12" />
                        </div>
                        <div className="space-y-3">
                           <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Confirmer le mot de passe</label>
                           <Input type="password" placeholder="••••••••" className="bg-black/40 border-white/10 h-12" />
                        </div>
                     </div>
                     <Button variant="outline" className="border-blue-500/30 text-blue-400 hover:bg-blue-500 hover:text-white transition-all">
                       Réinitialiser le mot de passe
                     </Button>
                  </CardContent>
                </Card>

                <Card className="bg-red-500/[0.02] border-red-500/10 backdrop-blur-xl">
                   <CardHeader>
                     <CardTitle className="text-lg text-red-500">Zone de Danger</CardTitle>
                     <CardDescription>Actions irréversibles sur votre compte.</CardDescription>
                   </CardHeader>
                   <CardContent className="p-8 pt-0">
                      <Button variant="outline" className="border-red-500/20 text-red-500 hover:bg-red-500 hover:text-white">
                        Supprimer mon compte définitivement
                      </Button>
                   </CardContent>
                </Card>
              </div>
            )}

            {activeTab === 'workspace' && (
               <div className="animate-in fade-in duration-500">
                 <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                  <CardHeader className="border-b border-white/5">
                    <CardTitle className="text-xl text-white flex items-center gap-3">
                      <Users className="w-5 h-5 text-indigo-400" />
                      Équipe & Ressources
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-8 flex flex-col items-center justify-center text-center py-24 space-y-6">
                     <div className="w-20 h-20 rounded-full bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                        <Users className="w-10 h-10 text-indigo-400" />
                     </div>
                     <div className="max-w-md space-y-2">
                        <h4 className="text-lg font-bold text-white">Gestion Multi-utilisateurs</h4>
                        <p className="text-sm text-gray-400 italic">
                          Cette fonctionnalité est reservée aux comptes **Enterprise**. Contactez votre administrateur pour inviter des collaborateurs.
                        </p>
                     </div>
                     <Button className="bg-indigo-600 hover:bg-indigo-500">Découvrir les offres Team</Button>
                  </CardContent>
                </Card>
               </div>
            )}

            {activeTab === 'billing' && (
               <div className="animate-in fade-in duration-500">
                 <Card className="bg-blue-500/10 border-blue-500/20 backdrop-blur-xl">
                  <CardContent className="p-12 flex flex-col items-center text-center space-y-8">
                     <div className="p-4 bg-white/5 rounded-3xl border border-white/10 shadow-2xl relative">
                        <div className="absolute -top-2 -right-2 px-2 py-1 bg-blue-500 text-[10px] font-black italic rounded text-white animate-pulse">OFFRE ACTIVE</div>
                        <CreditCard className="w-12 h-12 text-blue-400" />
                     </div>
                     <div className="space-y-2">
                        <h4 className="text-3xl font-black text-white tracking-tighter">Plan Enterprise <span className="text-blue-500 italic">Unlimited</span></h4>
                        <p className="text-blue-200/50 font-medium">Facturation gérée par votre organisation mère.</p>
                     </div>
                     
                     <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full pt-4">
                        {[
                          { val: "Illimité", label: "Analyses / Mois" },
                          { val: "Priority", label: "Support Technique" },
                          { val: "SSO", label: "Sécurité" }
                        ].map((stat, i) => (
                           <div key={i} className="p-4 rounded-2xl bg-black/40 border border-white/5 space-y-1 group hover:border-blue-500/30 transition-all">
                              <p className="text-xl font-black text-white">{stat.val}</p>
                              <p className="text-[10px] uppercase font-bold text-gray-500 tracking-widest">{stat.label}</p>
                           </div>
                        ))}
                     </div>
                  </CardContent>
                </Card>
               </div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}
