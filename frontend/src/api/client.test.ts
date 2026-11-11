import { describe, expect, it } from "vitest";
import { errorMessage } from "./client";

describe("errorMessage", () => {
  it("returns backend detail string when present", () => {
    const err = { response: { data: { detail: "Unknown Store ID: S999" } } };
    expect(errorMessage(err)).toBe("Unknown Store ID: S999");
  });

  it("joins field validation errors", () => {
    const err = {
      response: {
        data: {
          detail: "Validation failed",
          errors: [{ field: "password", message: "Too short" }],
        },
      },
    };
    expect(errorMessage(err)).toBe("password: Too short");
  });

  it("reports network failures clearly", () => {
    expect(errorMessage({ message: "Network Error" })).toContain("Cannot reach the API");
  });

  it("falls back to a generic message", () => {
    expect(errorMessage(undefined)).toBe("Unexpected error");
  });
});
