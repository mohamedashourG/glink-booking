import { calBase } from "@/lib/manifest";

export default function NotFound() {
  return (
    <main>
      <div className="card">
        <h1>Not found</h1>
        <p>That page doesn&apos;t exist. If you reached this from a booking link, please contact the host directly.</p>
        <a className="muted-link" href={calBase()}>Try the booking page →</a>
      </div>
    </main>
  );
}
