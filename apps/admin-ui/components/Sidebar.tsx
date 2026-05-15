"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, UserPlus, Upload } from "lucide-react";
import { Logo } from "./Logo";
import { SidebarUserMenu } from "./SidebarUserMenu";

type NavItem = {
  href: string;
  label: string;
  Icon: typeof Home;
  isActive: (pathname: string) => boolean;
};

const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    label: "Clients",
    Icon: Home,
    // Home covers the dashboard AND any client-detail route, since
    // those are children of the Clients section.
    isActive: (p) =>
      p === "/" ||
      (p.startsWith("/clients/") && !p.startsWith("/clients/new") && !p.startsWith("/clients/batch")),
  },
  { href: "/clients/new",   label: "Add client",      Icon: UserPlus, isActive: (p) => p.startsWith("/clients/new")   },
  { href: "/clients/batch", label: "Batch provision", Icon: Upload,   isActive: (p) => p.startsWith("/clients/batch") },
];

export function Sidebar({ adminEmail }: { adminEmail: string | null }) {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-[232px] flex-col border-r border-ink-200 bg-white sticky top-0 shrink-0">
      <Link
        href="/"
        aria-label="glink home"
        className="mx-3 mt-3 inline-flex w-fit items-center rounded-lg p-2 hover:bg-ink-100 transition-colors"
      >
        <Logo className="h-7 w-7" />
      </Link>

      <div className="px-3 mt-4 mb-1.5">
        <div className="eyebrow px-2">Workspace</div>
      </div>

      <nav className="flex-1 px-3 flex flex-col gap-0.5">
        {NAV_ITEMS.map(({ href, label, Icon, isActive }) => {
          const active = isActive(pathname);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={`group flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors ${
                active
                  ? "bg-brand-100 text-brand-700"
                  : "text-ink-600 hover:bg-ink-100 hover:text-ink-900"
              }`}
            >
              <Icon className="h-[18px] w-[18px] shrink-0" strokeWidth={active ? 2.2 : 1.8} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      {adminEmail && (
        <div className="border-t border-ink-100 p-3">
          <SidebarUserMenu email={adminEmail} />
        </div>
      )}
    </aside>
  );
}
