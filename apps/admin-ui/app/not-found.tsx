import Link from "next/link";
import { Compass } from "lucide-react";

export default function NotFound() {
  return (
    <main className="min-h-screen flex items-center justify-center px-4">
      <div className="text-center max-w-sm animate-fade-in">
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-100 text-brand-600 mx-auto">
          <Compass className="h-6 w-6" />
        </div>
        <h1 className="mt-4 text-2xl font-semibold text-ink-900 tracking-tight">Not found</h1>
        <p className="mt-2 text-sm text-ink-500">
          That page doesn&apos;t exist — maybe the slug was wrong, or the client was removed.
        </p>
        <Link href="/" className="btn-primary mt-5">Back to dashboard</Link>
      </div>
    </main>
  );
}
