"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Zap,
  FileText,
  DollarSign,
  Shield,
  MessageSquare,
  Loader2,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth-context";
import { ThemeToggle } from "@/components/ui/theme-toggle";

// ── SVG Icons ──

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-5" aria-hidden="true">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  );
}

function MicrosoftIcon() {
  return (
    <svg viewBox="0 0 23 23" className="size-5" aria-hidden="true">
      <rect x="1" y="1" width="10" height="10" fill="#F25022" />
      <rect x="12" y="1" width="10" height="10" fill="#7FBA00" />
      <rect x="1" y="12" width="10" height="10" fill="#00A4EF" />
      <rect x="12" y="12" width="10" height="10" fill="#FFB900" />
    </svg>
  );
}

// ── Feature bullets ──

const features = [
  {
    icon: FileText,
    title: "Document Intelligence",
    desc: "Auto-extract data from freight invoices and BOLs",
  },
  {
    icon: DollarSign,
    title: "Cost Allocation",
    desc: "AI-powered GL mapping with confidence scoring",
  },
  {
    icon: Shield,
    title: "Guardrails & Audit",
    desc: "Full audit trail with human-in-the-loop review",
  },
  {
    icon: MessageSquare,
    title: "Operational Q&A",
    desc: "Ask questions about your SOPs and procedures",
  },
];

// ── Animations ──

const fadeInUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
};

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1, delayChildren: 0.2 } },
};

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState<"google" | "microsoft" | "email" | null>(null);

  const handleSSO = async (provider: "google" | "microsoft") => {
    setLoading(provider);
    // Simulate SSO redirect delay
    await new Promise((r) => setTimeout(r, 1200));
    login({
      name: "Elias C.",
      email: "elias@company.com",
      method: provider,
    });
  };

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setLoading("email");
    await new Promise((r) => setTimeout(r, 800));
    login({
      name: email.split("@")[0],
      email,
      method: "email",
    });
  };

  return (
    <div className="flex min-h-screen">
      {/* ── Left Panel: Branding ── */}
      <motion.div
        initial={{ opacity: 0, x: -30 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="hidden lg:flex lg:w-[45%] flex-col justify-between bg-gradient-to-br from-zinc-900 via-zinc-900 to-zinc-800 dark:from-zinc-950 dark:via-zinc-900 dark:to-zinc-800 p-12 text-white relative overflow-hidden"
      >
        {/* Background pattern */}
        <div className="absolute inset-0 opacity-[0.03]">
          <div
            className="absolute inset-0"
            style={{
              backgroundImage:
                "radial-gradient(circle at 1px 1px, white 1px, transparent 0)",
              backgroundSize: "40px 40px",
            }}
          />
        </div>

        {/* Accent glow */}
        <div className="absolute -bottom-32 -left-32 size-96 rounded-full bg-primary/20 blur-[128px]" />
        <div className="absolute -top-32 -right-32 size-64 rounded-full bg-primary/10 blur-[100px]" />

        <div className="relative z-10">
          {/* Logo */}
          <div className="flex items-center gap-3 mb-2">
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary">
              <Zap className="size-5 text-primary-foreground" />
            </div>
            <span className="text-xl font-bold tracking-tight">
              Project Gamma
            </span>
          </div>
          <p className="text-zinc-400 text-sm ml-[52px]">
            Logistics Operations Intelligence
          </p>
        </div>

        {/* Feature list */}
        <motion.div
          variants={stagger}
          initial="hidden"
          animate="show"
          className="relative z-10 space-y-6"
        >
          {features.map((f) => (
            <motion.div
              key={f.title}
              variants={fadeInUp}
              className="flex items-start gap-4"
            >
              <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-white/[0.08] border border-white/[0.06]">
                <f.icon className="size-5 text-zinc-300" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-zinc-100">
                  {f.title}
                </h3>
                <p className="text-sm text-zinc-400 mt-0.5">{f.desc}</p>
              </div>
            </motion.div>
          ))}
        </motion.div>

        <div className="relative z-10">
          <p className="text-xs text-zinc-500">
            Powered by Claude AI &middot; On-Prem Ready &middot; Enterprise Grade
          </p>
        </div>
      </motion.div>

      {/* ── Right Panel: Login Form ── */}
      <div className="flex flex-1 items-center justify-center p-6 sm:p-12 bg-background">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="w-full max-w-[420px] space-y-8"
        >
          {/* Mobile logo (hidden on lg) */}
          <div className="lg:hidden flex items-center gap-3 mb-4">
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary">
              <Zap className="size-4 text-primary-foreground" />
            </div>
            <span className="text-lg font-bold tracking-tight">
              Project Gamma
            </span>
          </div>

          {/* Heading */}
          <div>
            <h2 className="text-2xl font-bold tracking-tight">
              Welcome back
            </h2>
            <p className="text-muted-foreground mt-1.5 text-sm">
              Sign in to access your logistics operations dashboard
            </p>
          </div>

          {/* SSO Buttons */}
          <div className="space-y-3">
            <Button
              variant="outline"
              size="lg"
              className="w-full gap-3 h-12 text-sm font-medium"
              onClick={() => handleSSO("google")}
              disabled={loading !== null}
            >
              {loading === "google" ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                <GoogleIcon />
              )}
              Continue with Google
            </Button>

            <Button
              variant="outline"
              size="lg"
              className="w-full gap-3 h-12 text-sm font-medium"
              onClick={() => handleSSO("microsoft")}
              disabled={loading !== null}
            >
              {loading === "microsoft" ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                <MicrosoftIcon />
              )}
              Continue with Microsoft
            </Button>
          </div>

          {/* Divider */}
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-3 text-muted-foreground">
                or continue with email
              </span>
            </div>
          </div>

          {/* Email Form */}
          <form onSubmit={handleEmailLogin} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm">
                Email address
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading !== null}
                className="h-11"
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-sm">
                  Password
                </Label>
                <button
                  type="button"
                  className="text-xs text-primary hover:underline"
                  tabIndex={-1}
                >
                  Forgot password?
                </button>
              </div>
              <Input
                id="password"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading !== null}
                className="h-11"
              />
            </div>
            <Button
              type="submit"
              size="lg"
              className="w-full h-12 gap-2 text-sm font-medium"
              disabled={loading !== null || !email}
            >
              {loading === "email" ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <>
                  Sign in
                  <ArrowRight className="size-4" />
                </>
              )}
            </Button>
          </form>

          {/* Footer */}
          <div className="flex items-center justify-between pt-4">
            <p className="text-xs text-muted-foreground">
              Protected by enterprise-grade security
            </p>
            <ThemeToggle />
          </div>
        </motion.div>
      </div>
    </div>
  );
}
