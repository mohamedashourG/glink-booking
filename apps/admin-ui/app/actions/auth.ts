"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { adminApi, SESSION_COOKIE } from "@/lib/api";

export type LoginActionResult = { error: string } | undefined;

export async function loginAction(_prev: LoginActionResult, formData: FormData): Promise<LoginActionResult> {
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");
  const next = String(formData.get("next") ?? "/") || "/";
  if (!email || !password) {
    return { error: "Email and password are required." };
  }
  try {
    const res = await adminApi.login(email, password);
    const ttl = Math.max(60, Math.floor(res.expires_at - Date.now() / 1000));
    const jar = await cookies();
    jar.set(SESSION_COOKIE, res.token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: ttl,
    });
  } catch (err) {
    // Do not leak which side failed.
    return { error: "Invalid credentials or not authorized." };
  }
  // redirect() throws — must NOT be inside try
  redirect(next.startsWith("/") ? next : "/");
}

export async function logoutAction(): Promise<void> {
  const jar = await cookies();
  jar.delete(SESSION_COOKIE);
  redirect("/login");
}
