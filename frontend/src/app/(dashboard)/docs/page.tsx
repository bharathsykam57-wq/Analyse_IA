"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/components/ui/Card";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import {
  BookOpen,
  Search,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Code,
  Video,
  HelpCircle,
  Zap,
  AlertCircle,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface FAQ {
  id: string;
  category: "general" | "technical" | "data" | "models" | "account";
  question: string;
  answer: string;
}

interface Tutorial {
  id: string;
  title: string;
  description: string;
  duration: string;
  difficulty: "beginner" | "intermediate" | "advanced";
  icon: React.ReactNode;
}

const faqs: FAQ[] = [
  {
    id: "1",
    category: "general",
    question: "Qu'est-ce qu'Analyse IA?",
    answer:
      "Analyse IA est une plateforme complète d'analyse de données assistée par l'IA. Elle combine AutoML, RAG documentaire et un Agent IA pour automatiser vos analyses de données.",
  },
  {
    id: "2",
    category: "general",
    question: "Comment commencer?",
    answer:
      "1. Créez un compte\n2. Téléchargez vos données ou documents\n3. Posez une question ou sélectionnez une analyse\n4. Attendez les résultats\n5. Explorez et téléchargez vos résultats",
  },
  {
    id: "3",
    category: "data",
    question: "Quels formats de fichiers sont supportés?",
    answer:
      "Nous supportons: CSV, JSON, Excel, Parquet, et documents PDF. Taille maximale: 100MB par fichier. Vous pouvez télécharger plusieurs fichiers à la fois.",
  },
  {
    id: "4",
    category: "data",
    question: "Comment mes données sont-elles protégées?",
    answer:
      "Vos données sont chiffrées en transit (HTTPS) et au repos. Nous respectons le RGPD et les normes de sécurité ISO 27001. Vous pouvez supprimer vos données à tout moment.",
  },
  {
    id: "5",
    category: "models",
    question: "Comment choisir le bon modèle?",
    answer:
      "- Classification: Utilisez pour prédire des catégories\n- Regression: Pour prédire des valeurs continues\n- Anomaly Detection: Pour trouver des valeurs anormales\n- AutoML: Laisse la plateforme choisir automatiquement",
  },
  {
    id: "6",
    category: "models",
    question: "Qu'est-ce que la confiance (Confidence)?",
    answer:
      "La confiance indique le niveau de certitude du modèle dans ses prédictions. Entre 0% et 100%. Une confiance élevée (>80%) signifie que le modèle est très sûr de sa réponse.",
  },
  {
    id: "7",
    category: "technical",
    question: "Comment interpréter les erreurs?",
    answer:
      "Consultez la section d'erreur détaillée. Les erreurs courantes:\n- Données manquantes: Remplissez les valeurs manquantes\n- Types de données incompatibles: Convertissez les types\n- Ensemble de données trop petit: Ajoutez plus de données",
  },
  {
    id: "8",
    category: "account",
    question: "Comment changer mon mot de passe?",
    answer: "Allez dans Paramètres > Sécurité > Changer le mot de passe. Vous disposerez de 2FA (authentification à deux facteurs) pour plus de sécurité.",
  },
];

const tutorials: Tutorial[] = [
  {
    id: "1",
    title: "Débuter avec AutoML",
    description: "Apprenez à utiliser notre moteur AutoML pour entraîner des modèles rapidement",
    duration: "15 min",
    difficulty: "beginner",
    icon: <Zap className="w-6 h-6" />,
  },
  {
    id: "2",
    title: "Analyse d'Anomalies Avancée",
    description: "Techniques avancées pour détecter les anomalies dans vos données",
    duration: "30 min",
    difficulty: "advanced",
    icon: <AlertCircle className="w-6 h-6" />,
  },
  {
    id: "3",
    title: "Importation et Préparation des Données",
    description: "Guide complet pour préparer vos données pour l'analyse",
    duration: "20 min",
    difficulty: "beginner",
    icon: <Code className="w-6 h-6" />,
  },
  {
    id: "4",
    title: "Requêtes RAG Documentaires",
    description: "Comment utiliser le RAG pour analyser vos documents",
    duration: "25 min",
    difficulty: "intermediate",
    icon: <BookOpen className="w-6 h-6" />,
  },
  {
    id: "5",
    title: "Optimisation des Modèles",
    description: "Techniques pour améliorer les performances de vos modèles",
    duration: "40 min",
    difficulty: "advanced",
    icon: <Zap className="w-6 h-6" />,
  },
  {
    id: "6",
    title: "Dashboard et Visualisations",
    description: "Créez des tableaux de bord personnalisés",
    duration: "22 min",
    difficulty: "intermediate",
    icon: <Video className="w-6 h-6" />,
  },
];

export default function DocumentationPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedFaqs, setExpandedFaqs] = useState<Set<string>>(new Set());
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  const categories = [
    { value: "all", label: "Tous" },
    { value: "general", label: "Général" },
    { value: "technical", label: "Technique" },
    { value: "data", label: "Données" },
    { value: "models", label: "Modèles" },
    { value: "account", label: "Compte" },
  ];

  const filteredFaqs = faqs.filter((faq) => {
    const matchesSearch =
      faq.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
      faq.answer.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = selectedCategory === "all" || faq.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const toggleFaq = (id: string) => {
    const newExpanded = new Set(expandedFaqs);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedFaqs(newExpanded);
  };

  return (
    <div className="p-6 md:p-10 max-w-6xl mx-auto space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold font-sans text-white mb-2 tracking-tight flex items-center gap-3">
          <BookOpen className="w-8 h-8 text-blue-500" />
          Documentation & Aide
        </h1>
        <p className="text-blue-300/60 leading-relaxed">
          Trouvez les réponses à vos questions et apprenez à utiliser Analyse IA au mieux
        </p>
      </div>

      {/* Getting Started Cards */}
      <div className="grid md:grid-cols-3 gap-4">
        <Card className="bg-blue-500/10 border-blue-500/20 hover:bg-blue-500/15 transition-all duration-200 cursor-pointer group">
          <CardContent className="pt-6 pb-4 flex flex-col items-center text-center">
            <Zap className="w-8 h-8 text-blue-400 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-semibold text-white mb-1">Démarrage Rapide</h3>
            <p className="text-sm text-gray-400">
              Commencez en 5 minutes avec notre guide
            </p>
          </CardContent>
        </Card>

        <Card className="bg-purple-500/10 border-purple-500/20 hover:bg-purple-500/15 transition-all duration-200 cursor-pointer group">
          <CardContent className="pt-6 pb-4 flex flex-col items-center text-center">
            <Video className="w-8 h-8 text-purple-400 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-semibold text-white mb-1">Tutoriels Vidéo</h3>
            <p className="text-sm text-gray-400">
              Suivez nos tutoriels étape par étape
            </p>
          </CardContent>
        </Card>

        <Card className="bg-emerald-500/10 border-emerald-500/20 hover:bg-emerald-500/15 transition-all duration-200 cursor-pointer group">
          <CardContent className="pt-6 pb-4 flex flex-col items-center text-center">
            <Code className="w-8 h-8 text-emerald-400 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-semibold text-white mb-1">API Reference</h3>
            <p className="text-sm text-gray-400">
              Documentation technique complète
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tutorials Section */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
          <Video className="w-6 h-6 text-blue-400" />
          Tutoriels Recommandés
        </h2>
        <motion.div
          className="grid md:grid-cols-3 gap-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ staggerChildren: 0.1 }}
        >
          {tutorials.map((tutorial, index) => (
            <motion.div
              key={tutorial.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
            >
              <Card className="bg-white/[0.02] border-white/5 hover:bg-white/[0.04] transition-all duration-200 group cursor-pointer h-full">
                <CardHeader>
                  <div className="flex items-start justify-between mb-3">
                    <div className="text-blue-400 group-hover:scale-110 transition-transform">
                      {tutorial.icon}
                    </div>
                    <span
                      className={`text-xs font-medium px-2 py-1 rounded-full ${
                        tutorial.difficulty === "beginner"
                          ? "bg-emerald-500/10 text-emerald-300"
                          : tutorial.difficulty === "intermediate"
                          ? "bg-blue-500/10 text-blue-300"
                          : "bg-red-500/10 text-red-300"
                      }`}
                    >
                      {tutorial.difficulty === "beginner"
                        ? "Débutant"
                        : tutorial.difficulty === "intermediate"
                        ? "Intermédiaire"
                        : "Avancé"}
                    </span>
                  </div>
                  <CardTitle className="text-base text-white">{tutorial.title}</CardTitle>
                  <CardDescription className="text-gray-400 text-sm">
                    {tutorial.description}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-xs text-gray-500">{tutorial.duration}</div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </motion.div>
      </div>

      {/* FAQ Section */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
          <HelpCircle className="w-6 h-6 text-blue-400" />
          Questions Fréquemment Posées
        </h2>

        {/* Search and Filter */}
        <div className="space-y-4 mb-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <Input
              type="text"
              placeholder="Rechercher dans la FAQ..."
              value={searchQuery}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>

          {/* Category Filter */}
          <div className="flex flex-wrap gap-2">
            {categories.map((cat) => (
              <Button
                key={cat.value}
                variant={selectedCategory === cat.value ? "default" : "outline"}
                size="sm"
                onClick={() => setSelectedCategory(cat.value)}
              >
                {cat.label}
              </Button>
            ))}
          </div>
        </div>

        {/* FAQ Items */}
        <div className="space-y-3">
          {filteredFaqs.length === 0 ? (
            <Card className="bg-white/[0.02] border-white/5">
              <CardContent className="pt-8 pb-8 flex flex-col items-center justify-center text-center">
                <HelpCircle className="w-12 h-12 text-gray-600 mb-4" />
                <p className="text-gray-400 mb-2">Aucune question trouvée</p>
                <p className="text-gray-500 text-sm">
                  Essayez avec d&apos;autres mots-clés
                </p>
              </CardContent>
            </Card>
          ) : (
            <motion.div
              className="space-y-3"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ staggerChildren: 0.05 }}
            >
              {filteredFaqs.map((faq, index) => (
                <motion.div
                  key={faq.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                >
                  <Card
                    className="bg-white/[0.02] border-white/5 hover:bg-white/[0.04] transition-all duration-200 cursor-pointer"
                    onClick={() => toggleFaq(faq.id)}
                  >
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <CardTitle className="text-base text-white group-hover:text-blue-300 transition-colors">
                            {faq.question}
                          </CardTitle>
                        </div>
                        {expandedFaqs.has(faq.id) ? (
                          <ChevronUp className="w-5 h-5 text-gray-500 flex-shrink-0 mt-1" />
                        ) : (
                          <ChevronDown className="w-5 h-5 text-gray-500 flex-shrink-0 mt-1" />
                        )}
                      </div>
                    </CardHeader>

                    <AnimatePresence>
                      {expandedFaqs.has(faq.id) && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ duration: 0.2 }}
                        >
                          <CardContent className="pt-0 text-gray-400 text-sm whitespace-pre-line">
                            {faq.answer}
                          </CardContent>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </Card>
                </motion.div>
              ))}
            </motion.div>
          )}
        </div>
      </div>

      {/* Contact Support */}
      <Card className="bg-gradient-to-r from-blue-500/10 to-purple-500/10 border-blue-500/20">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <HelpCircle className="w-5 h-5 text-blue-400" />
            Besoin d&apos;Aide Supplémentaire?
          </CardTitle>
          <CardDescription className="text-gray-400">
            Contactez notre équipe de support pour des questions non résolues
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-2 gap-4">
            <a
              href="mailto:support@analyse-ia.com"
              className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-md text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              Envoyer un E-mail
            </a>
            <a
              href="https://docs.analyse-ia.com"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-md text-sm font-medium border border-border bg-card hover:bg-border text-foreground hover:text-white transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              Documentation Complète
            </a>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
