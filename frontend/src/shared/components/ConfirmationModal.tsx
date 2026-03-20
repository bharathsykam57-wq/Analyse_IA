"use client";

import { useState } from "react";
import { AlertTriangle, Eye, EyeOff } from "lucide-react";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { motion } from "framer-motion";

interface ConfirmationModalProps {
  isOpen: boolean;
  title: string;
  description: string;
  isDangerous?: boolean;
  requireEmail?: string; // If set, user must type this email to confirm
  requirePassword?: boolean; // If true, show password input
  onConfirm: (password?: string) => void;
  onCancel: () => void;
  confirmLabel?: string;
  cancelLabel?: string;
  isLoading?: boolean;
}

export function ConfirmationModal({
  isOpen,
  title,
  description,
  isDangerous = false,
  requireEmail,
  requirePassword = false,
  onConfirm,
  onCancel,
  confirmLabel = "Confirmer",
  cancelLabel = "Annuler",
  isLoading = false,
}: ConfirmationModalProps) {
  const [emailInput, setEmailInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [understood, setUnderstood] = useState(false);

  const isConfirmDisabled =
    isLoading ||
    (requireEmail && emailInput !== requireEmail) ||
    (requirePassword && !passwordInput) ||
    (isDangerous && !understood);

  const handleConfirm = () => {
    onConfirm(passwordInput || undefined);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <motion.div
        className="bg-[#0F1F3D] border border-red-500/20 rounded-xl shadow-2xl shadow-red-900/20 p-8 max-w-md w-full"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
      >
        {/* Header */}
        <div className="flex items-start gap-4 mb-4">
          {isDangerous && (
            <div className="p-2 bg-red-500/10 rounded-lg flex-shrink-0">
              <AlertTriangle className="w-6 h-6 text-red-500" />
            </div>
          )}
          <div className="flex-1">
            <h2 className={`text-xl font-bold ${isDangerous ? 'text-red-500' : 'text-white'}`}>
              {title}
            </h2>
            <p className="text-sm text-gray-400 mt-1">{description}</p>
          </div>
        </div>

        {/* Email Confirmation */}
        {requireEmail && (
          <div className="mb-4 space-y-2">
            <label className="text-sm font-medium text-gray-300">
              Confirmez votre adresse email
            </label>
            <Input
              type="email"
              placeholder="Entrez votre email"
              value={emailInput}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmailInput(e.target.value)}
              className="w-full"
            />
            {emailInput && emailInput !== requireEmail && (
              <p className="text-xs text-red-500">L&apos;email ne correspond pas</p>
            )}
          </div>
        )}

        {/* Password Confirmation */}
        {requirePassword && (
          <div className="mb-4 space-y-2">
            <label className="text-sm font-medium text-gray-300">
              Confirmez votre mot de passe
            </label>
            <div className="relative">
              <Input
                type={showPassword ? "text" : "password"}
                placeholder="Entrez votre mot de passe"
                value={passwordInput}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPasswordInput(e.target.value)}
                className="w-full pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-300"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
        )}

        {/* Danger Confirmation Checkbox */}
        {isDangerous && (
          <div className="mb-6 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={understood}
                onChange={(e) => setUnderstood(e.target.checked)}
                className="w-4 h-4 rounded border-red-500/50 accent-red-600"
              />
              <span className="text-sm text-red-400">
                Je comprends que cette action est irréversible
              </span>
            </label>
          </div>
        )}

        {/* Buttons */}
        <div className="flex gap-3 pt-4 border-t border-gray-700/50">
          <Button
            variant="ghost"
            onClick={onCancel}
            disabled={isLoading}
            className="flex-1"
          >
            {cancelLabel}
          </Button>
          <Button
            variant={isDangerous ? "destructive" : "default"}
            onClick={handleConfirm}
            disabled={isConfirmDisabled}
            className="flex-1"
          >
            {isLoading ? "Traitement..." : confirmLabel}
          </Button>
        </div>
      </motion.div>
    </div>
  );
}
