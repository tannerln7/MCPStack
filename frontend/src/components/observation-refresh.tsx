"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export function ObservationRefresh({
  intervalMs = 10000,
}: Readonly<{ intervalMs?: number }>) {
  const router = useRouter();
  useEffect(() => {
    const timer = window.setInterval(() => router.refresh(), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs, router]);
  return null;
}
