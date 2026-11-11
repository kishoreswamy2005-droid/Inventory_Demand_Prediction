import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ToastProvider } from "../context/ToastContext";
import { AuthProvider } from "../context/AuthContext";
import { Badge, ErrorBox, PageHeader, StatCard, statusTone } from "../components/ui";
import LoginPage from "../pages/LoginPage";

function wrap(ui: React.ReactNode) {
  return (
    <MemoryRouter>
      <ToastProvider>
        <AuthProvider>{ui}</AuthProvider>
      </ToastProvider>
    </MemoryRouter>
  );
}

describe("ui components", () => {
  it("renders a stat card with value and hint", () => {
    render(wrap(<StatCard label="Units sold" value={9975582} hint="Historical total" />));
    expect(screen.getByText("Units sold")).toBeInTheDocument();
    expect(screen.getByText("9,975,582")).toBeInTheDocument();
    expect(screen.getByText("Historical total")).toBeInTheDocument();
  });

  it("renders error box with alert role", () => {
    render(wrap(<ErrorBox message="Something broke" />));
    expect(screen.getByRole("alert")).toHaveTextContent("Something broke");
  });

  it("renders page header title and subtitle", () => {
    render(wrap(<PageHeader title="Inventory" subtitle="20 records" />));
    expect(screen.getByRole("heading", { name: "Inventory" })).toBeInTheDocument();
    expect(screen.getByText("20 records")).toBeInTheDocument();
  });

  it("maps inventory statuses to badge tones", () => {
    expect(statusTone("Critical Stock")).toBe("critical");
    expect(statusTone("Low Stock")).toBe("low");
    expect(statusTone("Overstocked")).toBe("overstock");
    expect(statusTone("Healthy Stock")).toBe("healthy");
  });

  it("renders badge children", () => {
    render(wrap(<Badge tone="critical">Critical</Badge>));
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });
});

describe("login page", () => {
  it("renders email/password form", () => {
    render(wrap(<LoginPage />));
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Register" })).toBeInTheDocument();
  });
});
