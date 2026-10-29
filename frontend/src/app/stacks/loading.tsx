import { PageContainer } from "@/components/page-container";
import { Skeleton } from "@/components/ui/skeleton";

export default function StacksLoading() {
  return (
    <PageContainer>
      <section
        aria-busy="true"
        aria-label="Loading configured stacks"
        className="grid gap-8"
      >
        <div className="grid gap-3">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-10 w-52" />
          <Skeleton className="h-5 max-w-2xl" />
        </div>
        <div className="grid gap-4">
          <Skeleton className="h-20" />
          <Skeleton className="h-72" />
        </div>
      </section>
    </PageContainer>
  );
}
