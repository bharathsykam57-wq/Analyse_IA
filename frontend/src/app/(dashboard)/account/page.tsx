"use client";

import { useState, useEffect } from "react";
import type { Metadata } from "next";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/components/ui/Card";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import {
  User,
  Key,
  Copy,
  RefreshCw,
  Trash2,
  AlertCircle,
  CheckCircle2,
  Eye,
  EyeOff,
  CreditCard,
  LogOut,
  Shield,
} from "lucide-react";
import { motion } from "framer-motion";
import { format } from "date-fns";
import { fr } from "date-fns/locale";

interface ApiKey {
  id: string;
  name: string;
  key: string;
  shortKey: string;
  created_at: string;
  last_used: string | null;
  is_active: boolean;
}

interface Account {
  id: string;
  email: string;
  name: string;
  profile_picture_url: string | null;
  created_at: string;
  subscription_plan: "free" | "pro" | "enterprise";
  provider_type: "password" | "oauth";
  two_factor_enabled: boolean;
}

export default function AccountPage() {
  const [showApiKey, setShowApiKey] = useState<Record<string, boolean>>({});
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  
  // Client-side data state
  const [account, setAccount] = useState<Account | null>(null);
  const [accountLoading, setAccountLoading] = useState(true);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [keysLoading, setKeysLoading] = useState(true);

  // Load data on mount (client-side only)
  useEffect(() => {
    const loadData = async () => {
      try {
        // Mock account data
        await new Promise((resolve) => setTimeout(resolve, 300));
        setAccount({
          id: "user-123",
          email: "user@example.com",
          name: "John Doe",
          profile_picture_url: null,
          created_at: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString(),
          subscription_plan: "pro",
          provider_type: "password",
          two_factor_enabled: true,
        });
        setAccountLoading(false);
        
        // Mock API keys data
        await new Promise((resolve) => setTimeout(resolve, 300));
        setApiKeys([
          {
            id: "key-1",
            name: "Production API Key",
            key: "sk_live_abcdef1234567890",
            shortKey: "sk_live_...7890",
            created_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
            last_used: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
            is_active: true,
          },
          {
            id: "key-2",
            name: "Development API Key",
            key: "sk_test_0987654321fedcba",
            shortKey: "sk_test_...dcba",
            created_at: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString(),
            last_used: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
            is_active: true,
          },
        ]);
        setKeysLoading(false);
      } catch (error) {
        console.error("Error loading account data:", error);
        setAccountLoading(false);
        setKeysLoading(false);
      }
    };
    
    loadData();
  }, []);

  const handleCopyKey = (key: string, id: string) => {
    navigator.clipboard.writeText(key);
    setCopiedKey(id);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const handleDeleteKey = async (id: string) => {
    setDeletingKey(id);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setDeletingKey(null);
    setShowDeleteConfirm(false);
  };

  const handleCreateNewKey = async () => {
    // Create new API key
    await new Promise((resolve) => setTimeout(resolve, 1000));
  };

  return (
    <div className="p-6 md:p-10 max-w-6xl mx-auto space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold font-sans text-white mb-2 tracking-tight flex items-center gap-3">
          <User className="w-8 h-8 text-blue-500" />
          Paramètres du Compte
        </h1>
        <p className="text-blue-300/60 leading-relaxed">
          Gérez votre profil, votre sécurité et vos clés API
        </p>
      </div>

      {/* Profile Section */}
      <Card className="bg-white/[0.02] border-white/5">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <User className="w-5 h-5 text-blue-400" />
            Informations du Compte
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {accountLoading ? (
            <div className="text-gray-400">Chargement...</div>
          ) : account ? (
            <>
              {/* Profile Picture */}
              <div className="flex flex-col sm:flex-row sm:items-end gap-4">
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-lg bg-gradient-to-br from-blue-500/20 to-purple-500/20 border border-blue-500/30 flex items-center justify-center">
                    <User className="w-8 h-8 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Photo de profil</p>
                    <p className="text-white font-medium">{account.name}</p>
                  </div>
                </div>
                <Button variant="outline" size="sm">
                  Modifier
                </Button>
              </div>

              {/* Account Details */}
              <div className="grid md:grid-cols-2 gap-4 pt-4 border-t border-white/5">
                <div>
                  <p className="text-sm text-gray-500 mb-1">Email</p>
                  <p className="text-white font-medium">{account.email}</p>
                </div>

                <div>
                  <p className="text-sm text-gray-500 mb-1">Plan d'Abonnement</p>
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium capitalize">
                      {account.subscription_plan === "free"
                        ? "Gratuit"
                        : account.subscription_plan === "pro"
                        ? "Pro"
                        : "Enterprise"}
                    </span>
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${
                        account.subscription_plan === "enterprise"
                          ? "bg-amber-500/10 text-amber-300"
                          : account.subscription_plan === "pro"
                          ? "bg-blue-500/10 text-blue-300"
                          : "bg-gray-500/10 text-gray-300"
                      }`}
                    >
                      Actif
                    </span>
                  </div>
                </div>

                <div>
                  <p className="text-sm text-gray-500 mb-1">Inscrit depuis</p>
                  <p className="text-white font-medium">
                    {format(new Date(account.created_at), "d MMMM yyyy", {
                      locale: fr,
                    })}
                  </p>
                </div>

                <div>
                  <p className="text-sm text-gray-500 mb-1">Authentification</p>
                  <div className="flex items-center gap-2">
                    <Shield className="w-4 h-4 text-green-400" />
                    <span className="text-white font-medium text-sm">
                      {account.two_factor_enabled ? "2FA Activé" : "2FA Désactivé"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Subscription Button */}
              <div className="pt-4 border-t border-white/5">
                <Button className="gap-2 bg-blue-600 hover:bg-blue-700">
                  <CreditCard className="w-4 h-4" />
                  Gérer l'Abonnement
                </Button>
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>

      {/* API Keys Section */}
      <Card className="bg-white/[0.02] border-white/5">
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              <Key className="w-5 h-5 text-blue-400" />
              Clés API
            </CardTitle>
            <CardDescription className="mt-1">
              Gérez vos clés API pour l'intégration avec d'autres services
            </CardDescription>
          </div>
          <Button
            size="sm"
            className="gap-1.5 bg-blue-600 hover:bg-blue-700"
            onClick={handleCreateNewKey}
          >
            <Key className="w-3.5 h-3.5" />
            Créer une Clé
          </Button>
        </CardHeader>

        <CardContent className="space-y-4">
          {keysLoading ? (
            <div className="text-gray-400">Chargement...</div>
          ) : apiKeys && apiKeys.length > 0 ? (
            <motion.div
              className="space-y-3"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ staggerChildren: 0.1 }}
            >
              {apiKeys.map((key, index) => (
                <motion.div
                  key={key.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                >
                  <Card className="bg-white/[0.02] border-white/5">
                    <CardContent className="p-4">
                      <div className="flex flex-col md:flex-row md:items-center gap-4">
                        {/* Key Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2">
                            <h4 className="font-medium text-white truncate">
                              {key.name}
                            </h4>
                            {key.is_active ? (
                              <span className="flex items-center gap-1 text-xs text-emerald-300 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                                <CheckCircle2 className="w-3 h-3" />
                                Actif
                              </span>
                            ) : (
                              <span className="flex items-center gap-1 text-xs text-gray-400 bg-gray-500/10 px-2 py-0.5 rounded-full">
                                <AlertCircle className="w-3 h-3" />
                                Inactif
                              </span>
                            )}
                          </div>

                          <div className="flex items-center gap-2 mb-2">
                            <code
                              className={`text-xs px-2 py-1 rounded bg-gray-900/50 border border-gray-800 ${
                                showApiKey[key.id]
                                  ? "text-white font-mono"
                                  : "text-gray-500"
                              }`}
                            >
                              {showApiKey[key.id] ? key.key : key.shortKey}
                            </code>
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-7 w-7"
                              onClick={() =>
                                setShowApiKey((prev) => ({
                                  ...prev,
                                  [key.id]: !prev[key.id],
                                }))
                              }
                            >
                              {showApiKey[key.id] ? (
                                <EyeOff className="w-3.5 h-3.5" />
                              ) : (
                                <Eye className="w-3.5 h-3.5" />
                              )}
                            </Button>
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-7 w-7"
                              onClick={() => handleCopyKey(key.key, key.id)}
                            >
                              {copiedKey === key.id ? (
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                            </Button>
                          </div>

                          <div className="flex flex-wrap gap-4 text-xs text-gray-500">
                            <div>
                              Créée:{" "}
                              {format(
                                new Date(key.created_at),
                                "d MMM yyyy",
                                { locale: fr }
                              )}
                            </div>
                            {key.last_used && (
                              <div>
                                Dernière utilisation:{" "}
                                {format(
                                  new Date(key.last_used),
                                  "d MMM yyyy HH:mm",
                                  { locale: fr }
                                )}
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex gap-2 flex-shrink-0">
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-1.5"
                          >
                            <RefreshCw className="w-3.5 h-3.5" />
                            Régénérer
                          </Button>

                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                            onClick={() => {
                              setDeletingKey(key.id);
                              setShowDeleteConfirm(true);
                            }}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </motion.div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              Aucune clé API créée. Cliquez sur "Créer une Clé" pour commencer.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card className="bg-red-500/5 border-red-500/20">
        <CardHeader>
          <CardTitle className="text-lg text-red-400 flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            Zone Dangereuse
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h4 className="font-medium text-white mb-2">Logout Partout</h4>
            <p className="text-sm text-gray-400 mb-3">
              Déconnectez-vous de toutes les sessions actives
            </p>
            <Button
              variant="outline"
              className="gap-2 border-red-500/20 text-red-400 hover:bg-red-500/10"
            >
              <LogOut className="w-4 h-4" />
              Déconnecter Partout
            </Button>
          </div>

          <div className="border-t border-red-500/20 pt-4">
            <h4 className="font-medium text-white mb-2">Supprimer le Compte</h4>
            <p className="text-sm text-gray-400 mb-3">
              Supprimez définitivement votre compte et toutes les données associées
            </p>
            <Button
              variant="outline"
              className="gap-2 border-red-500/30 text-red-400 hover:bg-red-500/10"
            >
              <Trash2 className="w-4 h-4" />
              Supprimer le Compte
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Delete Confirmation */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <Card className="bg-gray-900 border-red-500/20 max-w-sm">
            <CardHeader>
              <CardTitle className="text-red-400 flex items-center gap-2">
                <AlertCircle className="w-5 h-5" />
                Confirmer la Suppression
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-400 mb-6">
                Êtes-vous sûr de vouloir supprimer cette clé API? Cette action ne peut pas être annulée.
              </p>
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={deletingKey !== null}
                >
                  Annuler
                </Button>
                <Button
                  className="bg-red-600 hover:bg-red-700"
                  onClick={() => handleDeleteKey(deletingKey!)}
                  disabled={deletingKey === null}
                >
                  {deletingKey ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                      Suppression...
                    </>
                  ) : (
                    "Supprimer"
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

// Import Loader2 for animate spin
import { Loader2 } from "lucide-react";
