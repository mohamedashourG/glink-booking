"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGrid, UserPlus, Upload } from "lucide-react";

const TABS = [
  { href: "/", label: "Clients", Icon: LayoutGrid, exact: true },
  { href: "/clients/new", label: "Add", Icon: UserPlus, exact: false },
  { href: "/clients/batch", label: "Batch", Icon: Upload, exact: false },
];

export function NavTabs() {
  const pathname = usePathname();
  return (
    <nav className="hidden md:flex items-center gap-1">
      {TABS.map(({ href, label, Icon, exact }) => {
        const active = exact ? pathname === href : pathname === href || pathname.startsWith(href + "/");
        return (
          <Link
            key={href}
            href={href}
            className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors
              ${active
                ? "bg-brand-50 text-brand-700"
                : "text-ink-600 hover:bg-ink-100 hover:text-ink-900"}`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
