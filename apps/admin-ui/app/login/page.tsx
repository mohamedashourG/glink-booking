import { Wordmark } from "@/components/Logo";
import { LoginForm } from "./LoginForm";

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  return (
    <main className="relative min-h-screen flex items-center justify-center px-4 bg-white">
      <div className="absolute inset-x-0 top-0 -z-10 h-64 bg-brand-100/60 [mask-image:linear-gradient(to_bottom,black,transparent)]" />

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
