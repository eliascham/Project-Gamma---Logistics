import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
  }),
}));

// Mock the API client to avoid real fetch calls
vi.mock("@/lib/api-client", () => ({
  getDocuments: vi.fn().mockResolvedValue({
    documents: [],
    total: 0,
    page: 1,
    per_page: 20,
  }),
}));

// Import after mocks
import Dashboard from "@/app/page";

describe("Dashboard", () => {
  it("renders the dashboard heading", () => {
    render(<Dashboard />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("renders the description", () => {
    render(<Dashboard />);
    expect(
      screen.getByText("Logistics document processing overview"),
    ).toBeInTheDocument();
  });

  it("renders stat cards", () => {
    render(<Dashboard />);
    expect(screen.getByText("Total Documents")).toBeInTheDocument();
    expect(screen.getByText("Pending Extraction")).toBeInTheDocument();
    expect(screen.getByText("Extracted")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("renders quick action buttons", () => {
    render(<Dashboard />);
    expect(screen.getByText("Upload Document")).toBeInTheDocument();
    expect(screen.getByText("View Documents")).toBeInTheDocument();
  });
});
