import { Component, Suspense, useLayoutEffect, useMemo, useRef, type ReactNode } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Loader, useTexture } from "@react-three/drei";
import * as THREE from "three";
import {
  getInterviewerAnalyser,
  getInterviewerAudioContext,
  mouthFromSpectrum,
} from "../interviewerMotion";
import type { InterviewerAvatarExpression } from "./InterviewerAvatar3D";

export const DEFAULT_PORTRAIT_URL = "/interviewer-portrait.png";

export function isPortrait3DModelUrl(modelUrl?: string | null): boolean {
  const v = modelUrl?.trim().toLowerCase() ?? "";
  if (!v || v === "/portrait" || v === "portrait" || v === "/models/interviewer-portrait") return true;
  return v.endsWith("/interviewer-portrait") || v.includes("portrait-3d");
}

type SceneProps = {
  textureUrl: string;
  speaking: boolean;
  expression: InterviewerAvatarExpression;
  analyser?: AnalyserNode | null;
};

/** Studio portrait on a subtle curved mesh + voice-driven motion (matches reference photo). */
function PortraitScene({ textureUrl, speaking, expression, analyser }: SceneProps) {
  const tex = useTexture(textureUrl);
  const group = useRef<THREE.Group>(null);
  const { viewport, camera } = useThree();
  const data = useMemo(
    () =>
      new Uint8Array(
        analyser?.frequencyBinCount || getInterviewerAnalyser()?.frequencyBinCount || 256,
      ),
    [analyser],
  );

  const { planeH, curveGeo } = useMemo(() => {
    tex.colorSpace = THREE.SRGBColorSpace;
    const img = tex.image as { width?: number; height?: number } | undefined;
    const iw = img?.width ?? 1024;
    const ih = img?.height ?? 1024;
    const aspect = iw / ih;

    const vh = viewport.height * 0.98;
    const vw = vh * aspect;
    const w = Math.min(vw, viewport.width * 0.98);
    const h = w / aspect;

    const segW = 48;
    const segH = 48;
    const geo = new THREE.PlaneGeometry(w, h, segW, segH);
    const pos = geo.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const z = -0.22 * (1 - Math.cos((x / w) * Math.PI * 0.5)) * 0.15;
      pos.setZ(i, z);
    }
    pos.needsUpdate = true;
    geo.computeVertexNormals();

    return { planeH: h, curveGeo: geo };
  }, [tex, viewport.height, viewport.width]);

  useFrame((_, dt) => {
    const g = group.current;
    if (!g) return;

    const audioNode = analyser ?? getInterviewerAnalyser();
    const sampleRate =
      audioNode?.context.sampleRate ??
      getInterviewerAudioContext()?.sampleRate ??
      44100;

    let jaw = 0.04;
    if (speaking && audioNode) {
      try {
        audioNode.getByteFrequencyData(data);
        jaw = mouthFromSpectrum(data, sampleRate).jaw;
      } catch {
        jaw = 0.12;
      }
    } else if (speaking) {
      jaw = 0.14;
    }

    const talk = THREE.MathUtils.clamp(jaw, 0, 1);
    const friendly = expression === "friendly" ? 0.012 : 0;
    const targetScale = 1 + talk * 0.018 + friendly;
    g.scale.y = THREE.MathUtils.lerp(g.scale.y, targetScale, 1 - Math.pow(0.001, dt));
    g.scale.x = THREE.MathUtils.lerp(g.scale.x, 1 + talk * 0.006, 1 - Math.pow(0.001, dt));
    g.position.y = THREE.MathUtils.lerp(g.position.y, talk * 0.008, 0.12);
  });

  useLayoutEffect(() => {
    const cam = camera as THREE.OrthographicCamera;
    const safeH = Math.max(planeH, 0.01);
    const safeVp = Math.max(viewport.height, 0.01);
    cam.position.set(0, 0, 4);
    cam.zoom = Math.max(0.01, safeVp / safeH);
    cam.lookAt(0, 0, 0);
    cam.updateProjectionMatrix();
  }, [camera, planeH, viewport.height]);

  return (
    <>
      <color attach="background" args={["#ffffff"]} />
      <ambientLight intensity={0.95} />
      <directionalLight position={[2, 3, 4]} intensity={0.35} />
      <group ref={group}>
        <mesh geometry={curveGeo} position={[0, 0, 0]}>
          <meshBasicMaterial map={tex} toneMapped={false} />
        </mesh>
      </group>
    </>
  );
}

export type InterviewerPortrait3DProps = {
  textureUrl?: string;
  speaking?: boolean;
  expression?: InterviewerAvatarExpression;
  analyser?: AnalyserNode | null;
  className?: string;
};

class PortraitCanvasErrorBoundary extends Component<
  { children: ReactNode; textureUrl: string },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <img
          src={this.props.textureUrl}
          alt=""
          className="absolute inset-0 h-full w-full object-cover object-[center_18%] bg-white"
        />
      );
    }
    return this.props.children;
  }
}

export default function InterviewerPortrait3D({
  textureUrl = DEFAULT_PORTRAIT_URL,
  speaking = false,
  expression = "neutral",
  analyser = null,
  className,
}: InterviewerPortrait3DProps) {
  const url = textureUrl.trim() || DEFAULT_PORTRAIT_URL;

  return (
    <div
      className={className}
      data-testid="interviewer-portrait-3d"
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", background: "#fff" }}
    >
      <PortraitCanvasErrorBoundary textureUrl={url}>
        <Canvas
          orthographic
          dpr={[1, 2]}
          gl={{ antialias: true, alpha: false }}
          camera={{ position: [0, 0, 4], zoom: 1, near: 0.1, far: 20 }}
          style={{ width: "100%", height: "100%", display: "block" }}
        >
          <Suspense fallback={null}>
            <PortraitScene
              textureUrl={url}
              speaking={speaking}
              expression={expression}
              analyser={analyser}
            />
          </Suspense>
          <Loader containerStyles={{ background: "transparent" }} innerStyles={{ background: "#94a3b8" }} />
        </Canvas>
      </PortraitCanvasErrorBoundary>
    </div>
  );
}
