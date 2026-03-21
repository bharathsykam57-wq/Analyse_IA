"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { loginSchema, LoginFormValues } from "@/features/auth/api/schemas";
import { useAuthStore } from "@/features/auth/store/authStore";
import { apiClient } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/shared/components/ui/Card";
import { Brain, Eye, EyeOff, Loader2, AlertCircle } from "lucide-react";
import Link from "next/link";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuthStore();
  const [showPassword, setShowPassword] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  const fillDemo = () => {
    setValue("email", "demo@analyse-ia.fr");
    setValue("password", "Demo1234!");
  };

  const onSubmit = async (data: LoginFormValues) => {
    setServerError(null);
    try {
      const response = await apiClient.post("auth/login", data);
      const { user, tokens } = response.data;
      const { access_token, refresh_token } = tokens;
      
      login(
        { id: user.id, email: user.email, full_name: user.full_name }, 
        access_token, 
        refresh_token
      );
      
      router.push("/dashboard");
    } catch (error: unknown) {
      const errorDetail =
        typeof error === "object" &&
        error !== null &&
        "response" in error &&
        typeof (error as { response?: { data?: { detail?: string } } }).response?.data?.detail === "string"
          ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null;
      setServerError(
        errorDetail || "Une erreur est survenue lors de la connexion."
      );
    }
  };

  return (
    <div className="w-full max-w-md mx-auto">
      <div className="flex justify-center mb-8">
        <div className="w-16 h-16 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center shadow-lg shadow-primary/10">
          <Brain className="w-8 h-8 text-primary" />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-2xl text-center text-white">Bon retour !</CardTitle>
          <CardDescription className="text-center text-gray-400">
            Connectez-vous pour accéder à votre espace
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
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-gray-200">Mot de passe</label>
                <Link href="#" className="text-sm text-primary hover:underline">
                  Oublié ?
                </Link>
              </div>
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

            <Button
              type="submit"
              className="w-full mt-2"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Connexion en cours...
                </>
              ) : (
                "Se connecter"
              )}
            </Button>

            <button
              type="button"
              onClick={fillDemo}
              className="w-full mt-2 px-4 py-2 rounded-md border border-white/10 bg-transparent text-sm text-gray-400 hover:text-white hover:border-white/30 hover:bg-white/5 transition-all"
            >
              Accès Démo
            </button>
          </form>
        </CardContent>

        <CardFooter className="flex justify-center border-t border-border mt-2 pt-6">
          <p className="text-sm text-gray-400">
            Pas encore de compte ?{" "}
            <Link href="/register" className="text-primary hover:underline font-medium">
              Créer un compte
            </Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}
