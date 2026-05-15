// Root index page — usually nobody lands here directly (the routing layer
// in front of cal.diy maps a slug like /<slug> straight to the matching
// per-client page). This index is just a sane placeholder.
import { calBase } from "@/lib/manifest";

export default function HomePage() {
  return (
    <main>
      <div className="card">
        <h1>Booking temporarily unavailable</h1>
        <p>The booking page is offline. Please try again in a moment.</p>
        <a className="muted-link" href={calBase()}>Try the booking page again →</a>
      </div>
    </main>
  );
}
