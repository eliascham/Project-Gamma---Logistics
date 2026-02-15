import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { DocumentList } from "@/components/documents/document-list";
import type { Document } from "@/types/document";

const mockDocuments: Document[] = [
  {
    id: "1",
    filename: "stored-1.pdf",
    original_filename: "freight-invoice-001.pdf",
    file_type: "pdf",
    mime_type: "application/pdf",
    file_size: 245000,
    status: "pending",
    page_count: 3,
    notes: null,
    created_at: "2026-02-15T10:00:00Z",
    updated_at: "2026-02-15T10:00:00Z",
  },
  {
    id: "2",
    filename: "stored-2.csv",
    original_filename: "cost-report.csv",
    file_type: "csv",
    mime_type: "text/csv",
    file_size: 1200,
    status: "extracted",
    page_count: null,
    notes: null,
    created_at: "2026-02-14T08:30:00Z",
    updated_at: "2026-02-14T09:00:00Z",
  },
  {
    id: "3",
    filename: "stored-3.pdf",
    original_filename: "bol-scan.pdf",
    file_type: "pdf",
    mime_type: "application/pdf",
    file_size: 5400000,
    status: "failed",
    page_count: null,
    notes: null,
    created_at: "2026-02-13T15:00:00Z",
    updated_at: "2026-02-13T15:01:00Z",
  },
];

describe("DocumentList", () => {
  it("renders a table with document rows", () => {
    render(<DocumentList documents={mockDocuments} />);
    expect(screen.getByText("freight-invoice-001.pdf")).toBeInTheDocument();
    expect(screen.getByText("cost-report.csv")).toBeInTheDocument();
    expect(screen.getByText("bol-scan.pdf")).toBeInTheDocument();
  });

  it("renders status badges", () => {
    render(<DocumentList documents={mockDocuments} />);
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByText("extracted")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
  });

  it("renders file types", () => {
    render(<DocumentList documents={mockDocuments} />);
    const pdfCells = screen.getAllByText("pdf");
    expect(pdfCells.length).toBe(2);
    expect(screen.getByText("csv")).toBeInTheDocument();
  });

  it("shows empty state when no documents", () => {
    render(<DocumentList documents={[]} />);
    expect(screen.getByText("No documents uploaded yet.")).toBeInTheDocument();
  });

  it("renders table headers", () => {
    render(<DocumentList documents={mockDocuments} />);
    expect(screen.getByText("Filename")).toBeInTheDocument();
    expect(screen.getByText("Type")).toBeInTheDocument();
    expect(screen.getByText("Size")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Uploaded")).toBeInTheDocument();
  });
});
