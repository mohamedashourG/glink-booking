import { notFound } from "next/navigation";
import { calBase, findClient, readManifest } from "@/lib/manifest";

// Static export: generate exactly one page per provisioned client at build
// time. Anything else 404s — set dynamicParams=false so Next doesn't try to
// render unknown slugs on the fly (we have no runtime).
export const dynamicParams = false;

export async function generateStaticParams() {
  return readManifest().map((c) => ({ slug: c.slug }));
}

export default async function ClientFallbackPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const client = findClient(slug);
  if (!client) notFound();

  const mailto = `mailto:${client.email}?subject=${encodeURIComponent(`Reaching out — booking page is offline`)}`;
  const retryUrl = `${calBase().replace(/\/$/, "")}/${slug}`;

  return (
    <main>
      <div className="card">
        <h1>Booking temporarily unavailable</h1>
        <p>
          The booking page for <strong>{client.full_name}</strong> is offline right now.
          {client.calendly_url
            ? " Use the embed below to grab a slot, or email directly:"
            : " The fastest way to reach them is by email:"}
        </p>
        <a className="cta" href={mailto}>
          Email {client.full_name} directly at {client.email}
        </a>
        <p style={{ marginTop: 24 }}>
          <a className="muted-link" href={retryUrl}>Try the booking page again →</a>
        </p>
      </div>

      {client.calendly_url && (
        <div className="card">
          <h2>Or book via Calendly</h2>
          <p>
            We&apos;ve also published this host&apos;s calendar on Calendly as a backup. Pick a time
            below — it goes straight onto their calendar.
          </p>
          <iframe
            className="calendly-frame"
            src={client.calendly_url}
            title={`Book a time with ${client.full_name} via Calendly`}
            // No JS needed; Calendly's standard URL renders fine in an iframe.
            // sandbox kept permissive enough for Calendly's own scripts inside the iframe.
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox"
          />
        </div>
      )}
    </main>
  );
}
