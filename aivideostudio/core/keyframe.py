import enum
from dataclasses import dataclass, field

class EasingType(enum.Enum):
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    STEP = "step"

@dataclass
class Keyframe:
    time: float
    value: float
    easing: EasingType = EasingType.LINEAR

@dataclass
class KeyframeTrack:
    property_name: str
    keyframes: list = field(default_factory=list)

    def add(self, time, value, easing=EasingType.LINEAR):
        kf = Keyframe(time=time, value=value, easing=easing)
        self.keyframes.append(kf)
        self.keyframes.sort(key=lambda k: k.time)
        return kf

    def evaluate(self, t):
        if not self.keyframes:
            return 0.0
        if len(self.keyframes) == 1:
            return self.keyframes[0].value
        if t <= self.keyframes[0].time:
            return self.keyframes[0].value
        if t >= self.keyframes[-1].time:
            return self.keyframes[-1].value
        for i in range(len(self.keyframes) - 1):
            k0, k1 = self.keyframes[i], self.keyframes[i + 1]
            if k0.time <= t <= k1.time:
                dt = k1.time - k0.time
                p = (t - k0.time) / dt if dt else 0
                e = self._ease(p, k1.easing)
                return k0.value + (k1.value - k0.value) * e
        return self.keyframes[-1].value

    @staticmethod
    def _ease(t, easing):
        if easing == EasingType.LINEAR:
            return t
        elif easing == EasingType.EASE_IN:
            return t * t
        elif easing == EasingType.EASE_OUT:
            return 1 - (1 - t) ** 2
        elif easing == EasingType.EASE_IN_OUT:
            return 3 * t**2 - 2 * t**3
        elif easing == EasingType.STEP:
            return 0.0 if t < 1.0 else 1.0
        return t
