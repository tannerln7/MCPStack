import type { Metadata } from "next";
import Link from "next/link";

import { PageContainer } from "@/components/page-container";
import { PageHeader } from "@/components/page-header";
import { StackCreationForm } from "@/components/stack-creation-form";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

export const metadata: Metadata = { title: "New Stack" };

export default function NewStackPage() {
  return (
    <PageContainer>
      <PageHeader
        eyebrow={
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink render={<Link href="/stacks" />}>
                  Stacks
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>New</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        }
        title="Create a Stack"
        description="Add an MCP server or application. MCPStack checks your settings and saves them to a local configuration file."
      />
      <StackCreationForm />
    </PageContainer>
  );
}
