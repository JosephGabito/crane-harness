import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";


// Test isolation
afterEach(() => {
  cleanup();
});
