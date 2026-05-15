import { Wordmark } from "@/components/Logo";
import { LoginForm } from "./LoginForm";

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  return (
    <main className="relative min-h-screen overflow-hidden flex items-center justify-center px-4">
      <div className="absolute inset-0 -z-10 bg-grid opacity-40 [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)]" />
      <div className="absolute -top-32 left-1/2 -translate-x-1/2 -z-10 h-[500px] w-[700px] rounded-full bg-brand-200/40 blur-3xl" />

      <div className="w-full max-w-md animate-fade-in">
        <div className="flex justify-center mb-6">
          <Wordmark />
        </div>

        <div className="card card-pad shadow-pop">
          <h1 className="text-xl font-semibold text-ink-900 text-center">Welcome back</h1>
          <p className="text-sm text-ink-500 mt-1 text-center">
            Sign in with your cal.diy admin account.
          </p>
          <div className="mt-6">
            <LoginForm next={next ?? "/"} />
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-ink-500">
          Trouble signing in? Your account needs <span className="chip-mono">role=ADMIN</span> on cal.diy.
        </p>
      </div>
    </main>
  );
}
