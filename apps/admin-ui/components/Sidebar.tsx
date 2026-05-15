"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, UserPlus, Upload } from "lucide-react";
import { Logo } from "./Logo";
import { Tooltip } from "./Tooltip";
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
  { href: "/clients/new",    label: "Add client",      Icon: UserPlus, isActive: (p) => p.startsWith("/clients/new") },
  { href: "/clients/batch",  label: "Batch provision", Icon: Upload,   isActive: (p) => p.startsWith("/clients/batch") },
];

export function Sidebar({ adminEmail }: { adminEmail: string | null }) {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-[56px] flex-col items-center border-r border-ink-200 bg-white py-3 sticky top-0">
      <Tooltip label="glink admin">
        <Link
          href="/"
          className="mb-5 flex h-9 w-9 items-center justify-center rounded-lg hover:bg-ink-100 transition-colors"
          aria-label="glink home"
        >
          <Logo className="h-7 w-7" priority />
        </Link>
      </Tooltip>

      <nav className="flex flex-1 flex-col items-center gap-1">
        {NAV_ITEMS.map(({ href, label, Icon, isActive }) => {
          const active = isActive(pathname);
          return (
            <Tooltip key={href} label={label}>
              <Link
                href={href}
                aria-label={label}
                aria-current={active ? "page" : undefined}
                className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors ${
                  active
                    ? "bg-brand-100 text-brand-700"
                    : "text-ink-500 hover:bg-ink-100 hover:text-ink-900"
                }`}
              >
                <Icon className="h-[17px] w-[17px]" strokeWidth={active ? 2.2 : 1.8} />
              </Link>
            </Tooltip>
          );
        })}
      </nav>

      {adminEmail && <SidebarUserMenu email={adminEmail} />}
    </aside>
  );
}
