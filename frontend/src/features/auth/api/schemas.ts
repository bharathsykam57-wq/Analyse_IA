import { z } from "zod";

// Zod handles both runtime validation and TypeScript type derivation automatically

export const loginSchema = z.object({
  email: z.string().min(1, { message: "L'e-mail est requis" }).email({ message: "Format d'e-mail invalide" }),
  password: z.string().min(6, { message: "Le mot de passe doit comporter au moins 6 caractères" }),
});

export type LoginFormValues = z.infer<typeof loginSchema>;

export const registerSchema = z.object({
  full_name: z.string().min(2, { message: "Le nom doit comporter au moins 2 caractères" }),
  email: z.string().email({ message: "Format d'e-mail invalide" }),
  password: z.string()
    .min(8, { message: "Le mot de passe doit comporter au moins 8 caractères" })
    .regex(/[A-Z]/, { message: "Doit contenir une majuscule" })
    .regex(/[0-9]/, { message: "Doit contenir un chiffre" })
    .regex(/[^A-Za-z0-9]/, { message: "Doit contenir un caractère spécial" }),
  confirm_password: z.string()
}).refine((data) => data.password === data.confirm_password, {
  message: "Les mots de passe ne correspondent pas",
  path: ["confirm_password"], 
});

export type RegisterFormValues = z.infer<typeof registerSchema>;
