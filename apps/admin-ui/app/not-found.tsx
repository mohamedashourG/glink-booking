import Link from "next/link";

export default function NotFound() {
  return (
    <main className="min-h-screen flex items-center justify-center px-4">
      <div className="text-center">
        <h1 className="text-2xl font-semibold text-slate-900">Not found</h1>
        <p className="text-sm text-slate-500 mt-1">That page doesn’t exist.</p>
        <Link href="/" className="mt-4 inline-block text-sm text-blue-700 underline">← Back to dashboard</Link>
      </div>
    </main>
  );
}
