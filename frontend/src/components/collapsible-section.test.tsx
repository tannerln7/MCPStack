import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CollapsibleSection } from "@/components/collapsible-section";

afterEach(cleanup);

describe("CollapsibleSection", () => {
  it("keeps relationship content collapsed until requested", () => {
    render(
      <CollapsibleSection title="Configuration relationships">
        <p>Endpoint link</p>
      </CollapsibleSection>,
    );

    expect(screen.queryByText("Endpoint link")).not.toBeInTheDocument();
    const trigger = screen.getByRole("button", {
      name: /configuration relationships/i,
    });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(trigger);
    expect(screen.getByText("Endpoint link")).toBeInTheDocument();
  });

  it("allows long header text to wrap inside the trigger", () => {
    render(
      <CollapsibleSection
        title="Configuration relationships with an exceptionally long unbroken-resource-identifier"
        description="A long description remains inside the available mobile width instead of inheriting nowrap button styling."
      >
        <p>Content</p>
      </CollapsibleSection>,
    );

    const trigger = screen.getByRole("button", {
      name: /configuration relationships/i,
    });
    expect(trigger).toHaveClass("whitespace-normal", "min-w-0");
    expect(screen.getByText(/exceptionally long/)).toHaveClass(
      "[overflow-wrap:anywhere]",
    );
  });
});
