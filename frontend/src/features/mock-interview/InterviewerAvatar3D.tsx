import {
  Component,
  Suspense,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  type ReactNode,
} from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { ContactShadows, Loader, useAnimations, useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { SkeletonUtils } from "three-stdlib";
import {
  getInterviewerAnalyser,
  getInterviewerAudioContext,
  mouthFromSpectrum,
  subscribeInterviewerPose,
  type InterviewerPose,
} from "../interviewerMotion";
import InterviewerPortrait3D, {
  DEFAULT_PORTRAIT_URL,
  isPortrait3DModelUrl,
} from "./InterviewerPortrait3D";

export type InterviewerAvatarExpression = "neutral" | "friendly" | "thinking";

export type InterviewerAvatar3DProps = {
  speaking?: boolean;
  analyser?: AnalyserNode | null;
  expression?: InterviewerAvatarExpression;
  /** GLB path, or `/portrait` for photo-real 3D portrait from portraitUrl. */
  modelUrl?: string;
  /** Portrait image for `/portrait` mode (defaults to bundled studio photo). */
  portraitUrl?: string;
  className?: string;
  height?: string;
};

/** Female half-body human (Ready Player Me / visage). Override via presenter glb_url. */
export const DEFAULT_INTERVIEWER_GLB = "/models/interviewer-female.glb";

const BUST_SCALE = 1;
const BUST_HEIGHT = 1;
const PORTRAIT_CROP = 0.35;
const FACE_Y = 0;
const TARGET_HEIGHT_M = 1.65;

useGLTF.preload(DEFAULT_INTERVIEWER_GLB);

type AvatarProps = {
  speaking: boolean;
  analyser: AnalyserNode | null | undefined;
  expression: InterviewerAvatarExpression;
  modelUrl: string;
};

type FaceMesh = THREE.Mesh | THREE.SkinnedMesh;

type MorphIndices = {
  open?: number;
  wide?: number;
  smile?: number;
  blinkL?: number;
  blinkR?: number;
  blink?: number;
};

function indexMorphs(dict: Record<string, number> | undefined): MorphIndices {
  const out: MorphIndices = {};
  if (!dict) return out;
  for (const [name, index] of Object.entries(dict)) {
    const key = name.toLowerCase();
    if (/open|mouth|jaw|aa|oh|viseme/i.test(key) && out.open === undefined) out.open = index;
    if (/wide|stretch|smile/i.test(key) && out.wide === undefined) out.wide = index;
    if (/smile|happy/i.test(key) && out.smile === undefined) out.smile = index;
    if (/blink.*left|eye.*left.*blink/i.test(key) && out.blinkL === undefined) out.blinkL = index;
    if (/blink.*right|eye.*right.*blink/i.test(key) && out.blinkR === undefined) out.blinkR = index;
    if (/^blink$/i.test(key) || (key.includes("blink") && out.blink === undefined)) out.blink = index;
  }
  return out;
}

const SKIN_MESH_HINT =
  /base|body|head|skin|face|avatar|ch03|kira_base|wolf3d_avatar|wolf3d_head|wolf3d_body/i;
const HIDE_MESH_HINT =
  /beard|footwear|bottom|pants|feet|shoe|teeth|eyeleft|eyeright|eye_left|eye_right|glass|sphere/i;

function isSkinMesh(name: string): boolean {
  const n = name.toLowerCase();
  if (HIDE_MESH_HINT.test(n)) return false;
  if (/hair|shirt|outfit|top|transparent/i.test(n) && !SKIN_MESH_HINT.test(n)) return false;
  return SKIN_MESH_HINT.test(n) || n.length === 0;
}

function pickFaceMesh(root: THREE.Object3D): FaceMesh | null {
  let preferred: FaceMesh | null = null;
  let best: FaceMesh | null = null;
  let bestScore = -1;

  root.traverse((obj) => {
    if (!(obj instanceof THREE.Mesh)) return;
    const name = obj.name;
    if (/Ch03_Body|Kira_Base|Wolf3D_Avatar|Wolf3D_Head|Wolf3D_Body/i.test(name) && !/transparent/i.test(name)) {
      preferred = obj;
    }
    if (!isSkinMesh(name)) return;

    const morphCount = obj.morphTargetDictionary
      ? Object.keys(obj.morphTargetDictionary).length
      : 0;
    const verts = obj.geometry.attributes.position?.count ?? 0;
    const score = morphCount * 50_000 + verts;
    if (score > bestScore) {
      bestScore = score;
      best = obj;
    }
  });

  return preferred ?? best;
}

function hideNonInterviewerParts(root: THREE.Object3D) {
  root.traverse((obj) => {
    if (!(obj instanceof THREE.Mesh)) return;
    const n = obj.name.toLowerCase();
    if (/beard|footwear|bottom|pants|feet|shoe|teeth|glass|sphere/i.test(n)) {
      obj.visible = false;
    }
  });
}

function findBoneMatch(root: THREE.Object3D, test: (name: string) => boolean): THREE.Bone | null {
  let found: THREE.Bone | null = null;
  root.traverse((obj) => {
    if (found) return;
    if (obj instanceof THREE.Bone && test(obj.name)) found = obj;
  });
  return found;
}

function updateSkeletons(root: THREE.Object3D) {
  root.traverse((obj) => {
    if (obj instanceof THREE.SkinnedMesh) {
      obj.skeleton?.update();
    }
  });
}

function measureBounds(root: THREE.Object3D): THREE.Box3 {
  updateSkeletons(root);
  root.updateWorldMatrix(true, true);
  return new THREE.Box3().setFromObject(root);
}

/** Center model and scale to ~human height (skinned bind-pose boxes are often wrong). */
function normalizeCharacter(root: THREE.Object3D) {
  let box = measureBounds(root);
  if (box.isEmpty()) return;

  let size = box.getSize(new THREE.Vector3());
  let h = Math.max(size.y, 1e-5);

  if (h > 2.4 || h < 0.35) {
    root.scale.multiplyScalar(TARGET_HEIGHT_M / h);
    root.updateWorldMatrix(true, true);
    box = measureBounds(root);
    size = box.getSize(new THREE.Vector3());
    h = Math.max(size.y, 1e-5);
  }

  const center = box.getCenter(new THREE.Vector3());
  root.position.x -= center.x;
  root.position.z -= center.z;
  root.position.y -= box.min.y;
}

function fitPortraitCamera(
  root: THREE.Object3D,
  camera: THREE.Camera,
  viewportAspect: number,
) {
  const box = measureBounds(root);
  const cam = camera as THREE.PerspectiveCamera;

  if (box.isEmpty()) {
    cam.position.set(0, 1.42, 2.15);
    cam.lookAt(0, 1.38, 0);
    cam.updateProjectionMatrix();
    return;
  }

  const fullH = box.max.y - box.min.y;
  const top = box.max.y;
  const cropBottom = box.min.y + fullH * PORTRAIT_CROP;
  const crop = new THREE.Box3(
    new THREE.Vector3(box.min.x, cropBottom, box.min.z),
    new THREE.Vector3(box.max.x, top + fullH * 0.03, box.max.z),
  );
  const size = crop.getSize(new THREE.Vector3());
  if (size.y < 0.05 || !Number.isFinite(size.y)) {
    cam.position.set(0, 1.42, 2.15);
    cam.lookAt(0, 1.38, 0);
    cam.updateProjectionMatrix();
    return;
  }

  const center = crop.getCenter(new THREE.Vector3());
  const focus = new THREE.Vector3(center.x, center.y + size.y * 0.04, center.z);
  const fitSize = Math.max(size.y * 0.95, (size.x * 1.08) / Math.max(viewportAspect, 0.5));

  const fovRad = (cam.fov * Math.PI) / 180;
  const distance = (fitSize * 0.5) / Math.tan(fovRad / 2);

  cam.position.set(focus.x, focus.y, focus.z + distance * 1.15);
  cam.near = Math.max(0.02, distance / 50);
  cam.far = Math.max(20, distance * 40);
  cam.lookAt(focus);
  cam.updateProjectionMatrix();
}

function enhanceSkinMaterials(root: THREE.Object3D) {
  root.traverse((obj) => {
    if (!(obj instanceof THREE.Mesh)) return;
    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
    mats.forEach((m) => {
      if (m instanceof THREE.MeshStandardMaterial) {
        m.roughness = Math.min(m.roughness, 0.62);
        m.metalness = Math.min(m.metalness, 0.06);
        m.side = THREE.FrontSide;
      }
    });
  });
}

function InterviewBust({ speaking, analyser, expression, modelUrl }: AvatarProps) {
  const rig = useRef<THREE.Group>(null);
  const face = useRef<FaceMesh | null>(null);
  const headBone = useRef<THREE.Bone | null>(null);
  const jawBone = useRef<THREE.Bone | null>(null);
  const leftEye = useRef<THREE.Bone | null>(null);
  const rightEye = useRef<THREE.Bone | null>(null);
  const jawRestX = useRef(0);
  const headRestX = useRef(0);
  const morphs = useRef<MorphIndices>({});
  const poseRef = useRef<InterviewerPose>({
    speaking: false,
    jaw: 0.04,
    width: 0.22,
    round: 0.08,
    blink: 0,
    nod: 0,
    tilt: 0,
    expression: 0.35,
  });
  const blinkSmooth = useRef(0);
  const fitFrames = useRef(0);
  const { camera, size, invalidate } = useThree();
  const data = useMemo(
    () =>
      new Uint8Array(
        analyser?.frequencyBinCount || getInterviewerAnalyser()?.frequencyBinCount || 256,
      ),
    [analyser],
  );

  useEffect(() => subscribeInterviewerPose((p) => {
    poseRef.current = p;
  }), []);

  const { scene, animations } = useGLTF(modelUrl);
  const model = useMemo(() => {
    const clone = SkeletonUtils.clone(scene);
    hideNonInterviewerParts(clone);
    normalizeCharacter(clone);
    enhanceSkinMaterials(clone);
    face.current = pickFaceMesh(clone);
    morphs.current = indexMorphs(face.current?.morphTargetDictionary ?? undefined);
    headBone.current = findBoneMatch(clone, (n) => /^head$/i.test(n));
    jawBone.current = findBoneMatch(clone, (n) => /^jaw$/i.test(n));
    leftEye.current = findBoneMatch(clone, (n) => /^lefteye$/i.test(n));
    rightEye.current = findBoneMatch(clone, (n) => /^righteye$/i.test(n));
    if (jawBone.current) jawRestX.current = jawBone.current.rotation.x;
    if (headBone.current) headRestX.current = headBone.current.rotation.x;
    return clone;
  }, [scene]);

  const { actions } = useAnimations(animations, model);
  useEffect(() => {
    const idle = actions.idle_eyes ?? actions.idle_eyes_2;
    if (!idle) return;
    idle.reset().setEffectiveTimeScale(0.85).setEffectiveWeight(1).fadeIn(0.4).play();
    return () => {
      idle.fadeOut(0.2);
    };
  }, [actions]);

  useLayoutEffect(() => {
    fitFrames.current = 0;
    if (!rig.current) return;
    fitPortraitCamera(rig.current, camera, size.width / Math.max(size.height, 1));
    invalidate();
  }, [camera, invalidate, model, size.width, size.height]);

  useFrame((state, dt) => {
    if (fitFrames.current < 8 && rig.current) {
      fitPortraitCamera(rig.current, camera, size.width / Math.max(size.height, 1));
      fitFrames.current += 1;
      invalidate();
    }

    const t = state.clock.elapsedTime;
    const pose = poseRef.current;
    const voiceActive = speaking || pose.speaking;
    const audioNode = analyser ?? getInterviewerAnalyser();
    const sampleRate =
      audioNode?.context.sampleRate ??
      getInterviewerAudioContext()?.sampleRate ??
      44100;

    if (rig.current) {
      rig.current.rotation.y = FACE_Y + Math.sin(t * 0.18) * 0.02;
    }

    let mouth = { jaw: 0.03, width: 0.2, round: 0.08 };
    if (voiceActive && audioNode) {
      try {
        audioNode.getByteFrequencyData(data);
        mouth = mouthFromSpectrum(data, sampleRate);
      } catch {
        mouth = { jaw: pose.jaw, width: pose.width, round: pose.round };
      }
    } else if (voiceActive) {
      mouth = { jaw: pose.jaw, width: pose.width, round: pose.round };
    }

    const jawOpen = THREE.MathUtils.clamp(mouth.jaw * 0.95, 0, 1);
    const mouthWide = THREE.MathUtils.clamp(mouth.width * 0.55, 0, 1);

    blinkSmooth.current = THREE.MathUtils.damp(
      blinkSmooth.current,
      pose.blink,
      voiceActive && jawOpen > 0.12 ? 4 : 8,
      dt,
    );
    const blinkAmt = THREE.MathUtils.clamp(blinkSmooth.current, 0, 1);

    const mesh = face.current;
    const idx = morphs.current;
    const influences = mesh?.morphTargetInfluences;
    if (influences) {
      if (idx.open !== undefined) influences[idx.open] = jawOpen;
      if (idx.wide !== undefined) influences[idx.wide] = mouthWide;
      if (idx.smile !== undefined) {
        influences[idx.smile] =
          expression === "friendly" ? 0.2 + jawOpen * 0.1 : expression === "thinking" ? 0.04 : 0.06;
      }
      const eyeShut = blinkAmt * (1 - jawOpen * 0.35);
      if (idx.blinkL !== undefined) influences[idx.blinkL] = eyeShut;
      if (idx.blinkR !== undefined) influences[idx.blinkR] = eyeShut;
      if (idx.blink !== undefined) influences[idx.blink] = eyeShut;
    }

    const jaw = jawBone.current;
    if (jaw) {
      jaw.rotation.x = THREE.MathUtils.lerp(jaw.rotation.x, jawRestX.current + jawOpen * 0.35, 0.28);
    }

    const head = headBone.current;
    if (head) {
      const nod =
        headRestX.current +
        jawOpen * 0.05 +
        (expression === "friendly" ? 0.01 : 0) +
        pose.nod * 0.02;
      head.rotation.x = THREE.MathUtils.lerp(head.rotation.x, nod, 0.18);
      head.rotation.z = THREE.MathUtils.lerp(head.rotation.z, pose.tilt * 0.016, 0.15);
    } else if (mesh && !influences && jawOpen > 0.02) {
      mesh.rotation.x = THREE.MathUtils.lerp(mesh.rotation.x, jawOpen * 0.022, 0.15);
    }

    const eyeShut = blinkAmt * 0.1;
    if (leftEye.current) {
      leftEye.current.rotation.x = THREE.MathUtils.lerp(leftEye.current.rotation.x, -eyeShut, 0.32);
    }
    if (rightEye.current) {
      rightEye.current.rotation.x = THREE.MathUtils.lerp(rightEye.current.rotation.x, -eyeShut, 0.32);
    }
  });

  return (
    <group ref={rig} scale={[BUST_SCALE, BUST_SCALE * BUST_HEIGHT, BUST_SCALE]} rotation={[0, FACE_Y, 0]}>
      <primitive object={model} />
    </group>
  );
}

function Scene(props: AvatarProps) {
  return (
    <>
      <ambientLight intensity={0.58} color="#fff8f2" />
      <directionalLight position={[2, 3.6, 2.6]} intensity={1.8} castShadow color="#fffaf5" />
      <directionalLight position={[-2.2, 2, 2]} intensity={0.52} color="#dce8ff" />
      <directionalLight position={[0.5, 2.8, -1.8]} intensity={0.28} color="#ffd8c8" />
      <pointLight position={[0.4, 1.5, 1.4]} intensity={0.42} color="#ffe8dc" distance={5.5} />
      <InterviewBust {...props} />
      <ContactShadows position={[0, -0.02, 0]} opacity={0.24} scale={2.3} blur={2.8} far={1.3} />
    </>
  );
}

class CanvasErrorBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) return this.props.fallback;
    return this.props.children;
  }
}

export default function InterviewerAvatar3D({
  speaking = false,
  analyser = null,
  expression = "neutral",
  modelUrl,
  portraitUrl,
  className,
}: InterviewerAvatar3DProps) {
  const glb = modelUrl?.trim() || "/portrait";
  if (isPortrait3DModelUrl(glb)) {
    return (
      <InterviewerPortrait3D
        className={className}
        textureUrl={portraitUrl?.trim() || DEFAULT_PORTRAIT_URL}
        speaking={speaking}
        analyser={analyser}
        expression={expression}
      />
    );
  }

  return (
    <div
      className={className}
      data-testid="interviewer-avatar-3d"
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
    >
      <CanvasErrorBoundary
        fallback={
          <div className="flex h-full flex-col items-center justify-center gap-2 bg-slate-900 px-4 text-center text-sm text-slate-400">
            <p>3D interviewer could not load.</p>
            <p className="text-xs">Check {glb} — use a human GLB with Head/jaw bones or morph targets.</p>
          </div>
        }
      >
        <Canvas
          shadows
          dpr={[1, 2]}
          gl={{
            antialias: true,
            alpha: false,
            powerPreference: "high-performance",
            toneMapping: THREE.ACESFilmicToneMapping,
            toneMappingExposure: 1.18,
          }}
          camera={{ fov: 33, near: 0.02, far: 50, position: [0, 0, 2.4] }}
          style={{ width: "100%", height: "100%", display: "block" }}
          onCreated={({ gl }) => {
            gl.setClearColor("#0f141c");
          }}
        >
          <Suspense fallback={null}>
            <Scene
              key={glb}
              modelUrl={glb}
              speaking={speaking}
              analyser={analyser}
              expression={expression}
            />
          </Suspense>
          <Loader containerStyles={{ background: "transparent" }} innerStyles={{ background: "#334155" }} />
        </Canvas>
      </CanvasErrorBoundary>
    </div>
  );
}
