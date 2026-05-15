import { LoginForm } from "./LoginForm";

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  return (
    <main className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
        <h1 className="text-xl font-semibold text-slate-900">glink admin</h1>
        <p className="text-sm text-slate-500 mt-1">Sign in with your cal.diy admin account.</p>
        <div className="mt-5">
          <LoginForm next={next ?? "/"} />
        </div>
      </div>
    </main>
  );
}
