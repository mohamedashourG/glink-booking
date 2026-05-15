// Reads the clients.json manifest written by the provisioning CLI at
// glink-booking/.data/clients.json. Default path is two levels up from
// apps/fallback (the Next.js project root) — override with the
// CLIENTS_MANIFEST_PATH env var when building from somewhere else.
//
// Read at BUILD time only. The static export bundles all pages it
// generates; nothing in here runs at request time.
import fs from "node:fs";
import path from "node:path";

export type Client = {
  slug: string;
  full_name: string;
  email: string;
  calendly_url: string | null;
};

const DEFAULT_MANIFEST = path.resolve(process.cwd(), "..", "..", ".data", "clients.json");

export function manifestPath(): string {
  return process.env.CLIENTS_MANIFEST_PATH || DEFAULT_MANIFEST;
}

export function readManifest(): Client[] {
  const p = manifestPath();
  if (!fs.existsSync(p)) {
    // Empty manifest is fine — yields zero static routes; the build still
    // produces an index page + a 404. Useful for fresh checkouts.
    console.warn(`[fallback] no manifest at ${p} — building with zero client routes`);
    return [];
  }
  const raw = fs.readFileSync(p, "utf8");
  const data = JSON.parse(raw) as Client[];
  // Defensive: drop entries missing the bare-minimum fields the page needs.
  return data.filter((c) => c && c.slug && c.full_name && c.email);
}

export function findClient(slug: string): Client | undefined {
  return readManifest().find((c) => c.slug === slug);
}

export function calBase(): string {
  return process.env.CAL_PUBLIC_BASE || "http://localhost:3000";
}
