import Link from "next/link";
import { Users, ShieldCheck, AlertCircle, UserPlus, Upload } from "lucide-react";
import { adminApi } from "@/lib/api";
import { requireToken } from "@/lib/server-session";
import { AppShell } from "@/components/AppShell";
import { Stat } from "@/components/Stat";
import { ClientsTable } from "@/components/ClientsTable";

export default async function Dashboard() {
  const { token, email } = await requireToken();
  const { clients } = await adminApi.listClients(token);

  const platformCount = clients.filter((c) => c.webhook_coverage === "platform").length;
  const perUserCount = clients.filter((c) => c.webhook_coverage === "per-user").length;
  const noneCount = clients.filter((c) => c.webhook_coverage === "none").length;
  const publicBase = process.env.CAL_PUBLIC_BASE || "http://localhost:3000";

  return (
    <AppShell adminEmail={email}>
      <main className="mx-auto max-w-7xl px-8 py-8 animate-fade-in">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between mb-6">
          <div>
            <h1 className="text-[1.65rem] font-semibold text-ink-900 tracking-tight">Clients</h1>
            <p className="text-sm text-ink-500 mt-1">
              Provisioned booking links and webhook coverage across your portfolio.
            </p>
          </div>
          <div className="flex gap-2">
            <Link href="/clients/batch" className="btn-secondary">
              <Upload className="h-4 w-4" />
              Batch upload
            </Link>
            <Link href="/clients/new" className="btn-primary">
              <UserPlus className="h-4 w-4" />
              Add client
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <Stat label="Total clients" value={clients.length} Icon={Users} tone="brand" />
          <Stat
            label="Platform webhook"
            value={platformCount}
            Icon={ShieldCheck}
            tone="success"
            hint={platformCount === clients.length && clients.length > 0 ? "All clients covered" : "Bookings flow through receiver"}
          />
          <Stat
            label="Needs attention"
            value={perUserCount + noneCount}
            Icon={AlertCircle}
            tone={perUserCount + noneCount === 0 ? "success" : "warn"}
            hint={
              noneCount > 0
                ? `${noneCount} with no webhook`
                : perUserCount > 0
                  ? `${perUserCount} on legacy per-user webhook`
                  : "All good"
            }
          />
        </div>

        <ClientsTable clients={clients} publicBase={publicBase} />
      </main>
    </AppShell>
  );
}
