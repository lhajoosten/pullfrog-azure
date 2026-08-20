import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SystemStatus } from "./SystemStatus";

describe("SystemStatus", () => {
  it("shows a healthy control plane", () => {
    render(
      <SystemStatus state="healthy" message="Control plane is reachable" />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Control plane is reachable",
    );
  });
});
