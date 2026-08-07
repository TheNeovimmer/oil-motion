export type FrameAnimatorOptions = {
  frameCount: number;
  initialFrame?: number;
  circular?: boolean;
  smoothTime?: number;
  maxSpeed?: number;
  reducedMotion?: boolean;
  render: (frame: number) => void;
};

export type FrameAnimator = {
  setTarget(frame: number): void;
  setDirection(x: number, y: number, startAngle?: number): void;
  setProgress(progress: number): void;
  getCurrentFrame(): number;
  destroy(): void;
};

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const wrap = (value: number, length: number) =>
  ((value % length) + length) % length;

const shortestCircularDelta = (
  from: number,
  to: number,
  frameCount: number,
) => {
  let delta = wrap(to, frameCount) - wrap(from, frameCount);
  if (delta > frameCount / 2) delta -= frameCount;
  if (delta < -frameCount / 2) delta += frameCount;
  return delta;
};

const smoothDamp = (
  current: number,
  target: number,
  velocity: number,
  smoothTime: number,
  maxSpeed: number,
  deltaTime: number,
): [number, number] => {
  const safeTime = Math.max(0.0001, smoothTime);
  const omega = 2 / safeTime;
  const x = omega * deltaTime;
  const decay = 1 / (1 + x + 0.48 * x * x + 0.235 * x * x * x);
  const originalTarget = target;
  const maxChange = maxSpeed * safeTime;
  const change = clamp(current - target, -maxChange, maxChange);
  const limitedTarget = current - change;
  const temp = (velocity + omega * change) * deltaTime;
  let nextVelocity = (velocity - omega * temp) * decay;
  let nextPosition = limitedTarget + (change + temp) * decay;

  if (
    (originalTarget - current > 0) ===
    (nextPosition > originalTarget)
  ) {
    nextPosition = originalTarget;
    nextVelocity = 0;
  }
  return [nextPosition, nextVelocity];
};

export function createFrameAnimator(
  options: FrameAnimatorOptions,
): FrameAnimator {
  const frameCount = Math.max(1, Math.floor(options.frameCount));
  const circular = options.circular ?? false;
  const smoothTime = options.smoothTime ?? 0.11;
  const maxSpeed = options.maxSpeed ?? frameCount * 2;
  const reducedMotion = options.reducedMotion ?? false;
  let position = clamp(options.initialFrame ?? 0, 0, frameCount - 1);
  let target = position;
  let velocity = 0;
  let lastFrame = -1;
  let lastTime = 0;
  let raf = 0;
  let destroyed = false;

  const normalizeFrame = (frame: number) =>
    circular
      ? wrap(frame, frameCount)
      : clamp(frame, 0, frameCount - 1);

  const render = () => {
    const frame = Math.round(normalizeFrame(position));
    if (frame !== lastFrame) {
      options.render(frame);
      lastFrame = frame;
    }
  };

  const loop = (now: number) => {
    raf = 0;
    if (destroyed) return;
    const deltaTime = lastTime
      ? Math.min((now - lastTime) / 1000, 1 / 30)
      : 1 / 60;
    lastTime = now;

    if (reducedMotion) {
      position = target;
      velocity = 0;
    } else {
      [position, velocity] = smoothDamp(
        position,
        target,
        velocity,
        smoothTime,
        maxSpeed,
        deltaTime,
      );
    }
    render();

    if (Math.abs(target - position) > 0.002 || Math.abs(velocity) > 0.002) {
      raf = requestAnimationFrame(loop);
    }
  };

  const schedule = () => {
    if (!raf && !destroyed) raf = requestAnimationFrame(loop);
  };

  render();

  return {
    setTarget(frame: number) {
      const normalized = normalizeFrame(frame);
      target = circular
        ? position + shortestCircularDelta(position, normalized, frameCount)
        : normalized;
      schedule();
    },
    setDirection(x: number, y: number, startAngle = -Math.PI * 0.75) {
      const angle = Math.atan2(y, x);
      const turn = Math.PI * 2;
      const normalized = ((angle - startAngle + turn) % turn) / turn;
      this.setTarget(normalized * frameCount);
    },
    setProgress(progress: number) {
      this.setTarget(clamp(progress, 0, 1) * (frameCount - 1));
    },
    getCurrentFrame() {
      return normalizeFrame(position);
    },
    destroy() {
      destroyed = true;
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
    },
  };
}
export function createCssSpriteRenderer(
  element: HTMLElement,
  columns: number,
  rows: number,
) {
  const safeColumns = Math.max(1, Math.floor(columns));
  const safeRows = Math.max(1, Math.floor(rows));
  element.style.backgroundSize = `${safeColumns * 100}% ${safeRows * 100}%`;

  return (frame: number) => {
    const column = frame % safeColumns;
    const row = Math.floor(frame / safeColumns);
    const x = safeColumns === 1 ? 0 : (column / (safeColumns - 1)) * 100;
    const y = safeRows === 1 ? 0 : (row / (safeRows - 1)) * 100;
    element.style.backgroundPosition = `${x}% ${y}%`;
  };
}
