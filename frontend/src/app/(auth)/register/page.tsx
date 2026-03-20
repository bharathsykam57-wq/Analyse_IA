"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { registerSchema, RegisterFormValues } from "@/features/auth/api/schemas";
import { apiClient } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/shared/components/ui/Card";
import { Brain, Eye, EyeOff, Loader2, AlertCircle } from "lucide-react";
import Link from "next/link";

export default function RegisterPage() {
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterFormValues) => {
    setServerError(null);
    try {
      await apiClient.post("auth/register", {
        full_name: data.full_name,
        email: data.email,
        password: data.password
      });
      // Spec requires a slight delay before shifting to the login flow after registration
      await new Promise(resolve => setTimeout(resolve, 800));
      router.push("/login");
    } catch (error: unknown) {
      const errorDetail =
        typeof error === "object" &&
        error !== null &&
        "response" in error &&
        typeof (error as { response?: { data?: { detail?: string } } }).response?.data?.detail === "string"
          ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null;
      setServerError(
        errorDetail || "Une erreur est survenue lors de l'inscription."
      );
    }
  };

  return (
    <div className="w-full max-w-md mx-auto py-8">
      <div className="flex justify-center mb-6">
        <div className="w-16 h-16 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center shadow-lg shadow-primary/10">
          <Brain className="w-8 h-8 text-primary" />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-2xl text-center text-white">Créer un compte</CardTitle>
          <CardDescription className="text-center text-gray-400">
            Rejoignez la plateforme Analyse IA
          </CardDescription>
        </CardHeader>

        <CardContent>
          {serverError && (
            <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center gap-2 text-sm text-red-500">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <p>{serverError}</p>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-200">Nom complet</label>
              <Input
                type="text"
                placeholder="John Doe"
                {...register("full_name")}
                className={errors.full_name ? "border-red-500/50 focus-visible:ring-red-500" : ""}
              />
              {errors.full_name && (
                <span className="text-sm text-red-500">{errors.full_name.message}</span>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-200">E-mail</label>
              <Input
                type="email"
                placeholder="nom@entreprise.com"
                {...register("email")}
                className={errors.email ? "border-red-500/50 focus-visible:ring-red-500" : ""}
              />
              {errors.email && (
                <span className="text-sm text-red-500">{errors.email.message}</span>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-200">Mot de passe</label>
              <div className="relative">
                <Input
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  {...register("password")}
                  className={errors.password ? "border-red-500/50 focus-visible:ring-red-500" : ""}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.password && (
                <span className="text-sm text-red-500">{errors.password.message}</span>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-200">Confirmer le mot de passe</label>
              <div className="relative">
                <Input
                  type={showConfirmPassword ? "text" : "password"}
                  placeholder="••••••••"
                  {...register("confirm_password")}
                  className={errors.confirm_password ? "border-red-500/50 focus-visible:ring-red-500" : ""}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                >
                  {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.confirm_password && (
                <span className="text-sm text-red-500">{errors.confirm_password.message}</span>
              )}
            </div>

            <Button
              type="submit"
              className="w-full mt-4"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Création en cours...
                </>
              ) : (
                "Créer mon compte"
              )}
            </Button>
          </form>
        </CardContent>

        <CardFooter className="flex justify-center border-t border-border mt-2 pt-6">
          <p className="text-sm text-gray-400">
            Déjà inscrit ?{" "}
            <Link href="/login" className="text-primary hover:underline font-medium">
              Se connecter
            </Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}
