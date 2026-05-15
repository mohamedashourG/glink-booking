import Link from "next/link";
import { Wordmark } from "./Logo";
import { UserMenu } from "./UserMenu";
import { NavTabs } from "./NavTabs";

export function Nav({ adminEmail }: { adminEmail: string | null }) {
  return (
    <header className="sticky top-0 z-30 border-b border-ink-200/70 bg-white/80 backdrop-blur supports-[backdrop-filter]:bg-white/60">
      <div className="mx-auto max-w-7xl px-6">
        <div className="flex h-14 items-center justify-between">
          <div className="flex items-center gap-8">
            <Link href="/" aria-label="glink home" className="-m-1 p-1">
              <Wordmark />
            </Link>
            {adminEmail && <NavTabs />}
          </div>
          {adminEmail && <UserMenu email={adminEmail} />}
        </div>
      </div>
    </header>
  );
}
