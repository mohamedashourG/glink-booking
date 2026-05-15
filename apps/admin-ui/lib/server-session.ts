// Server-only helpers for reading the session cookie + bouncing on bad token.
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { adminApi, SESSION_COOKIE, type ApiError } from "@/lib/api";

export async function getSessionToken(): Promise<string | null> {
  const jar = await cookies();
  return jar.get(SESSION_COOKIE)?.value ?? null;
}

/** Returns the token; redirects to /login on missing or invalid. Use in pages. */
export async function requireToken(): Promise<{ token: string; email: string }> {
  const token = await getSessionToken();
  if (!token) redirect("/login");
  try {
    const me = await adminApi.me(token);
    return { token, email: me.email };
  } catch (err) {
    if ((err as ApiError).status === 401) {
      const jar = await cookies();
      jar.delete(SESSION_COOKIE);
      redirect("/login");
    }
    throw err;
  }
}
