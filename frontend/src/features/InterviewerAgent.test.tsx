import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { InterviewerAgent } from "./InterviewerAgent";

vi.mock("@react-three/fiber", () => ({
  Canvas: ({ children }: { children?: ReactNode }) => <div data-testid="r3f-canvas">{children}</div>,
  useFrame: () => {},
  useThree: () => ({
    viewport: { width: 4, height: 3 },
    camera: { position: { set: () => {} }, zoom: 1, lookAt: () => {}, updateProjectionMatrix: () => {} },
  }),
}));

vi.mock("@react-three/drei", () => {
  const useGLTF = Object.assign(
    () => ({
      scene: { traverse: () => {} },
      animations: [],
    }),
    { preload: () => {} },
  );
  return {
    ContactShadows: () => null,
    Loader: () => null,
    useAnimations: () => ({ actions: {} }),
    useTexture: () => ({ image: { width: 1024, height: 1024 } }),
    useGLTF,
  };
});

describe("InterviewerAgent", () => {
  it("renders the 3D interviewer panel", () => {
    render(<InterviewerAgent presenter={{ mode: "digital_human_3d", glb_url: "/portrait" }} />);
    expect(document.querySelector('[data-testid="interviewer-portrait-3d"]')).toBeTruthy();
  });

  it("renders static photo when configured", () => {
    render(
      <InterviewerAgent presenter={{ mode: "static_photo", image_url: "/mock-interviewer-host.jpg" }} />,
    );
    expect(document.querySelector('img[src="/mock-interviewer-host.jpg"]')).toBeTruthy();
  });
});
