import { Sidebar } from "./Sidebar";

// Two-column shell: a fixed-width left rail (Sidebar) + scrollable main column.
// The page passes the admin email so the user-menu can render its avatar; pass
// null on auth-less pages (the rail won't render the menu).
export function AppShell({
  adminEmail,
  children,
}: {
  adminEmail: string | null;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar adminEmail={adminEmail} />
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
}
