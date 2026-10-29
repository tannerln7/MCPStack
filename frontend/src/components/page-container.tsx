import type { ReactNode } from "react";

export function PageContainer({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="mx-auto w-full max-w-7xl px-5 py-8 sm:px-8 lg:px-10 lg:py-10">
      {children}
    </div>
  );
}
